"""Authenticated algorithm-first selection, previews and stopped batch creation.

Existing camera, server, resource and task tables remain authoritative. Preview
tokens are signed using the application's existing secret and cause no writes.
Only the final create call writes private idempotency receipts and new stopped
tasks. Existing-task editing continues through the original editor.
"""
import base64
import contextlib
from functools import wraps
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
import uuid

from service.algorithm_first_rules import (WorkflowError, field, identity, library_ids,
    requested_libraries, edit_path, geometry_requirement, default_name, compatible,
    scalar_options, selection, literal, display_name, setup_status, default_count_parameters,
    default_detection_type, detection_setup)
from service.algorithm_configuration_contract import runtime_issue, observed_runtime, KINDS
from service.count_algorithm_family import is_count_model_name, count_template_matches

VERSION = 'algorithm-first-backend-v4'
MAX_BODY = 256 * 1024
TTL = 600
IDENT = re.compile(r'[a-f0-9]{32}')
_ORIGINALS = {}
_LEGACY_SYSTEM_NOTE = '通过算法优先向导创建；已停用，请确认逐摄像机参数后启动'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _id(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise WorkflowError('请求编号无效')
    return value


def _root():
    return Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parents[2])))


def _process_ticks(pid):
    try:
        raw = (Path('/proc') / str(int(pid)) / 'stat').read_text(encoding='utf-8')
        return raw[raw.rindex(')') + 2:].split()[19]
    except (OSError, ValueError, IndexError):
        return None


def _alive(record):
    if os.name == 'nt':
        return True  # Production is Linux; never send a Windows kill signal.
    ticks = _process_ticks(record.get('pid', 0))
    return ticks is not None and ticks == record.get('process_ticks')


class Journal:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else _root() / 'platform_ops/state/algorithm-first'

    def _check(self):
        for part in [self.directory] + list(self.directory.parents):
            if part.is_symlink():
                raise WorkflowError('批量任务记录目录无效', 409)

    def load(self, request_id):
        self._check()
        path = self.directory / (_id(request_id) + '.json')
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BODY:
            raise WorkflowError('批量任务记录无效', 409)
        return json.loads(path.read_text(encoding='utf-8'))

    def save(self, record):
        self._check()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / (_id(record['request_id']) + '.json')
        temporary = self.directory / ('.' + uuid.uuid4().hex + '.tmp')
        try:
            descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(_json(record)); stream.flush(); os.fsync(stream.fileno())
            os.replace(str(temporary), str(path))
            if os.name != 'nt':
                directory = os.open(str(self.directory), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if temporary.exists():
                temporary.unlink()

    @contextlib.contextmanager
    def lock(self, key, blocking=True):
        self._check()
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,90}', key):
            raise WorkflowError('批量任务锁编号无效')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / ('.' + key + '.lock')
        if path.is_symlink():
            raise WorkflowError('批量任务锁路径无效', 409)
        descriptor = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(descriptor, 'r+b')
        acquired = False
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(stream.fileno()).st_size == 0:
                    stream.write(b'0'); stream.flush()
                deadline = time.monotonic() + 4
                while True:
                    try:
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        acquired = True; break
                    except OSError:
                        if not blocking:
                            yield False; return
                        if time.monotonic() >= deadline:
                            raise WorkflowError('同一请求正在处理，请查询执行结果', 409)
                        time.sleep(0.05)
            else:
                import fcntl
                deadline = time.monotonic() + 4
                while True:
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True; break
                    except BlockingIOError:
                        if not blocking:
                            yield False; return
                        if time.monotonic() >= deadline:
                            raise WorkflowError('同一请求正在处理，请查询执行结果', 409)
                        time.sleep(0.05)
            yield True
        finally:
            if acquired:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            stream.close()


@contextlib.contextmanager
def equipment_locks(db, equipment_ids, journal=None):
    """Hold all camera locks on one connection across legacy commits."""
    camera_ids = sorted({identity(value, '摄像机') for value in equipment_ids})
    if not camera_ids:
        yield
        return
    if db.engine.dialect.name == 'sqlite':
        journal = journal or Journal()
        with contextlib.ExitStack() as stack:
            for camera_id in camera_ids:
                stack.enter_context(journal.lock('equipment-' + str(camera_id)))
            yield
        return
    if db.engine.dialect.name not in ('mysql', 'mariadb'):
        raise WorkflowError('当前数据库暂不支持安全批量创建', 409)
    from sqlalchemy import text
    connection = db.engine.connect()
    deadline = time.monotonic() + 4
    held = []
    try:
        for camera_id in camera_ids:
            name = 'aiplatform.algorithm.camera.' + str(camera_id)
            seconds = max(0, int(deadline - time.monotonic() + 0.999))
            acquired = connection.execute(text('SELECT GET_LOCK(:name, :seconds)'),
                                          {'name': name, 'seconds': seconds}).scalar()
            if acquired != 1:
                raise WorkflowError('该摄像机正在配置，请稍后重试', 409)
            held.append(name)
        yield
    finally:
        try:
            for name in reversed(held):
                connection.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': name})
        except Exception:
            connection.invalidate()
        finally:
            connection.close()


def equipment_lock(db, equipment_id, journal=None):
    return equipment_locks(db, (equipment_id,), journal)


def _dependencies():
    from data.exts import db
    from model.algorithm import Algorithm_config, Algorithm_config_history, Algorithm_library, Algorithm_test_type, Model_template_config, Model_template_small
    from model.equipment import Equipment, Resource_usage, Computing_equipment
    from model.admin import Mine
    return {'db': db, 'Config': Algorithm_config, 'History': Algorithm_config_history, 'Library': Algorithm_library,
            'TestType': Algorithm_test_type, 'Template': Model_template_config,
            'Small': Model_template_small, 'Equipment': Equipment, 'Resource': Resource_usage,
            'Host': Computing_equipment, 'Mine': Mine}


class Workflow:
    def __init__(self, dependencies=None, journal=None, secret=None, clock=None,
                 admission=None, creator=None, locker=None, batch_admission=None, starter=None):
        self.d = dependencies or _dependencies()
        self.db = self.d['db']
        self.session = self.db.session
        self.journal = journal or Journal()
        self.secret = secret
        self.clock = clock or time.time
        self.admission = admission
        self.creator = creator
        self.locker = locker or (lambda camera: equipment_lock(self.db, camera, self.journal))
        self.batch_admission = batch_admission
        self.starter = starter

    def _all(self, model):
        return self.session.query(self.d[model]).all()

    def _get(self, model, value):
        table = self.d[model]
        return self.session.query(table).filter(table.id == identity(value)).first()

    def _library(self, value):
        library = self._get('Library', value)
        if library is None:
            raise WorkflowError('算法不存在，请刷新后重新选择', 404)
        return library

    def _cards(self, library=None):
        if self.admission is None:
            try:
                from service.resource_admission import snapshot
                states = snapshot().get('cards', {})
            except Exception:
                states = {}
        else:
            states = self.admission()
        hosts = {row.id: row for row in self._all('Host')}
        cards = []
        for row in self._all('Resource'):
            host = hosts.get(row.computing_id)
            status = states.get(str(row.id), {})
            valid = host is not None and str(field(host, 'server_type', 1)) == '1' and (library is None or compatible(library, row))
            admission_disabled = status.get('disabled', True)
            cards.append({'id': row.id, 'name': '{} · 卡 {}'.format(field(row, 'dev_get_target', '') or '加速卡', row.dev_id),
                          'computing_id': row.computing_id, 'dev_id': row.dev_id,
                          'computing_name': field(host, 'computing_name', '') if host else '',
                          # Creation only saves a stopped draft. Live admission is
                          # checked again when the configured task actually starts.
                          'disabled': not valid, 'draft_disabled': not valid,
                          'admission_disabled': bool(admission_disabled),
                          'reason': ('硬件型号与算法不兼容或服务器不存在' if not valid else
                          status.get('reason', '资源状态未知，启动时重新检查') if admission_disabled else ''),
                          'utilization': status.get('utilization'), 'selection_score': status.get('selection_score'),
                          'recommended': False})
        def score(row):
            value = row.get('selection_score')
            return value if isinstance(value, (int, float)) else row['utilization'] if isinstance(row['utilization'], (int, float)) else 101
        cards.sort(key=lambda row: (row['disabled'], row['admission_disabled'], str(row['dev_id']) != '0', score(row), row['id']))
        first = next((row for row in cards if not row['disabled']), None)
        if first:
            first['recommended'] = True
        return cards

    def _resource_default(self, cards, camera_id=None, configs=None):
        """Keep the camera's binding; otherwise fill chip 0 before other chips."""
        result = {'resource_id': None, 'source': 'chip_zero_first', 'reason': ''}
        candidates = [card for card in cards if not card['disabled']]
        if camera_id not in (None, ''):
            camera_id = identity(camera_id, '摄像机')
            existing = [row for row in (self._all('Config') if configs is None else configs)
                        if str(field(row, 'Equipment_id')) == str(camera_id)]
            # A stale stopped draft must not defeat the sole running binding.
            running = [row for row in existing if str(field(row, 'status')) == '1']
            bindings = set()
            for row in running or existing:
                ids = [field(row, 'resource_id')]
                children = literal(field(row, 'model_algo_data_ori'))
                if isinstance(children, list):
                    ids.extend(field(child, 'resource_id') for child in children)
                for resource_id in ids:
                    if not resource_id:
                        continue
                    resource = self._get('Resource', resource_id)
                    if resource is not None:
                        bindings.add((str(resource.computing_id), str(resource.dev_id)))
            if len(bindings) > 1:
                return dict(result, source='camera_conflict', reason='同一摄像机已有任务使用多个芯片，请先确认并统一算力配置')
            if bindings:
                bound = next(iter(bindings))
                result['source'] = 'camera_running' if running else 'camera_configured'
                candidates = [card for card in candidates if (str(card['computing_id']), str(card['dev_id'])) == bound]
                if not candidates:
                    return dict(result, reason='同一摄像机已有绑定芯片与当前算法不兼容或资源已不存在，请先检查已有配置')
        if candidates:
            result['resource_id'] = candidates[0]['id']
            result['resource_name'] = candidates[0]['name']
            result['computing_name'] = candidates[0]['computing_name']
            result['admission_disabled'] = candidates[0]['admission_disabled']
            result['admission_reason'] = candidates[0]['reason']
        elif not result['reason']:
            result['reason'] = '没有兼容的算力卡'
        return result

    def resource_default(self, equipment_id=None, algorithm_id=None):
        library = self._library(algorithm_id) if algorithm_id not in (None, '') else None
        cards = self._cards(library)
        result = self._resource_default(cards, equipment_id)
        result['resources'] = cards
        return result

    def catalog(self, can_create=False):
        algorithms = [{'id': row.id, 'name': row.algorithm_name, 'display_name': display_name(row),
                       'model_name': field(row, 'model_name', ''), 'analysis_type': field(row, 'analysis_type', ''),
                       'version': field(row, 'algorithm_version', ''),
                       'status': str(row.algorithm_status), 'vendor': str(field(row, 'algorithm_trade_type', '')),
                       'enabled': str(row.algorithm_status) == '1'} for row in self._all('Library')]
        parents = {row.parent_id for row in self._all('Equipment') if row.parent_id}
        return {'can_create': bool(can_create), 'algorithms': algorithms,
                'units': [{'id': row.id, 'name': row.mine_name} for row in self._all('Mine')],
                'recorders': [{'id': row.id, 'name': row.equipment_name, 'mine_id': row.Mine_id}
                              for row in self._all('Equipment') if row.id in parents]}

    def options(self, algorithm_id):
        library = self._library(algorithm_id)
        templates = []
        for row in self._all('Template'):
            if not count_template_matches(library.model_name, row.model_name, row.model_template_config_type_id,
                                          field(library, 'analysis_type')):
                continue
            # Installation may add a name-only placeholder. The established
            # configured count template is usable without rewriting that row.
            if (is_count_model_name(row.model_name) and str(row.model_template_config_type_id) == '3'
                    and str(field(row, 'model_type', '1')) != '1'):
                continue
            item = {'id': row.id, 'name': row.model_name,
                    'type_id': row.model_template_config_type_id}
            issue = runtime_issue(row)
            item.update(disabled=bool(issue), reason=issue)
            item.update(geometry_requirement(library, row)); templates.append(item)
        requested = display_name(library)
        if is_count_model_name(requested):
            templates.sort(key=lambda item: (item['disabled'],
                requested in ('人数统计_全身', '人数统计_头肩') and str(item['name']).strip() != requested,
                str(item['name']).strip() not in ('人数统计', '人员计数'), item['id']))
        cards = self._cards(library)
        chosen = next((row for row in cards if row['recommended']), None)
        return {'templates': templates, 'resources': cards,
                'defaults': {'template_id': next((t['id'] for t in templates if not t['disabled']), None),
                             'resource_id': chosen['id'] if chosen else None,
                             'confidence': 0.6, 'interval_time': 2, 'interval_frames': 2, 'stream_type': 'legacy'},
                'always_stopped': True}

    def _existing(self):
        libraries = {row.id: row for row in self._all('Library')}
        result = {}
        for row in self._all('Config'):
            records = result.setdefault(int(row.Equipment_id), [])
            try:
                ids = library_ids(row)
            except WorkflowError:
                records.append({'algorithm_id': None, 'algorithm_name': '已有高级配置待检查',
                                'conf_id': row.id, 'status': str(row.status), 'edit_path': '/sfgl', 'unresolved': True})
                continue
            for algorithm_id in sorted(ids):
                library = libraries.get(algorithm_id)
                records.append({'algorithm_id': algorithm_id, 'algorithm_name': field(library, 'algorithm_name', '算法'),
                                'display_name': display_name(library) if library else '算法 #' + str(algorithm_id),
                                'model_name': field(library, 'model_name', ''),
                                'version': field(library, 'algorithm_version', ''),
                                'conf_id': row.id, 'status': str(row.status), 'edit_path': edit_path(row)})
        return result

    def _cameras(self, library):
        rows = self._all('Equipment')
        lookup = {row.id: row for row in rows}
        parents = {row.parent_id for row in rows if row.parent_id}
        units = {row.id: row.mine_name for row in self._all('Mine')}
        configured = self._existing()
        result = []
        for row in rows:
            if row.id in parents or (row.equipment_type in ('录像机', '视频中心存储', '特殊摄像头', 'AI双光摄像头') and not row.parent_id):
                continue
            previous = configured.get(row.id, [])
            duplicate = next((item for item in previous if item.get('algorithm_id') == library.id or item.get('unresolved')), None)
            reason = ('已配置当前算法，请编辑原任务' if duplicate and not duplicate.get('unresolved') else
                      '已有高级配置无法确认算法，请先检查原任务' if duplicate else
                      '摄像机已停用' if str(row.user_status) != '1' else
                      '摄像机所属单位未配置' if not row.Mine_id else
                      '算法包已停止，请先启用算法包' if str(library.algorithm_status) != '1' else '')
            parent = lookup.get(row.parent_id)
            result.append({'id': row.id, 'name': row.equipment_name, 'ip': row.equipment_ip,
                           'channel': row.equipment_aisles, 'mine_id': row.Mine_id,
                           'mine_name': units.get(row.Mine_id, ''), 'parent_id': row.parent_id,
                           'parent_name': field(parent, 'equipment_name', ''), 'online': row.online,
                           'disabled': bool(reason), 'disabled_reason': reason, 'existing': previous,
                           'default_name': default_name(row, library)})
        return result

    def cameras(self, algorithm_id, mine_id=None, parent_id=None, search='', page=1, per_page=30):
        library = self._library(algorithm_id)
        page, per_page = int(page), int(per_page)
        if not 1 <= page <= 100000 or not 1 <= per_page <= 100 or len(str(search)) > 100:
            raise WorkflowError('分页或搜索参数无效')
        rows = self._cameras(library)
        if mine_id not in (None, ''):
            rows = [row for row in rows if row['mine_id'] == identity(mine_id, '单位')]
        if parent_id not in (None, ''):
            rows = [row for row in rows if row['parent_id'] == identity(parent_id, '录像机')]
        if search:
            query = str(search).strip().lower()
            rows = [row for row in rows if query in str(row['name'] or '').lower() or query in str(row['ip'] or '').lower()]
        return {'items': rows[(page - 1) * per_page:page * per_page], 'total': len(rows), 'page': page, 'per_page': per_page}

    def _prepared(self, request):
        library = self._library(request['algorithm_id'])
        if str(library.algorithm_status) != '1':
            raise WorkflowError('算法包已停止，请先启用算法包', 409)
        available = self.options(library.id)
        camera_map = {row['id']: row for row in self._cameras(library)}
        raw_cameras = {row.id: row for row in self._all('Equipment')}
        overrides = {row['equipment_id']: row for row in request['overrides']}
        resources = {row['id']: row for row in available['resources']}
        templates = {row['id']: row for row in available['templates']}
        existing_names = {row.conf_name for row in self._all('Config')}
        tests = [row for row in self._all('TestType') if row.Algorithm_library_id == library.id]
        try:
            detection = default_detection_type(library.id, tests)
        except WorkflowError:
            detection = None
        smalls = [row for row in self._all('Small') if row.template_small_name == field(library, 'template_small_name')]
        configs = self._all('Config')
        items, payloads = [], {}
        for camera_id in request['camera_ids']:
            row = camera_map.get(camera_id)
            raw = raw_cameras.get(camera_id)
            item = {'equipment_id': camera_id, 'name': row['name'] if row else '摄像机', 'eligible': False,
                    'reason': row['disabled_reason'] if row else '摄像机通道不存在或不是可配置的叶通道'}
            items.append(item)
            if row is None or row['disabled']:
                continue
            override = overrides.get(camera_id, {})
            options = dict(request['options']); options.update({k: v for k, v in override.items() if k not in ('equipment_id', 'conf_name')})
            options = scalar_options(options)
            template_id = options.get('template_id') or available['defaults']['template_id']
            template = templates.get(template_id)
            recommendation = self._resource_default(available['resources'], camera_id, configs)
            resource_id = options.get('resource_id') or recommendation['resource_id']
            resource = resources.get(resource_id)
            if not template or detection is None:
                item['reason'] = '算法模板或检测类型不完整，请先完善算法包'; continue
            if template.get('disabled'):
                item['reason'] = template['reason']; continue
            if recommendation['reason']:
                item['reason'] = recommendation['reason']; continue
            if not resource or resource['disabled']:
                item['reason'] = resource['reason'] if resource else '没有可用且兼容的算力卡'; continue
            if recommendation['source'].startswith('camera_'):
                bound = resources.get(recommendation['resource_id'])
                if bound and (str(bound['computing_id']), str(bound['dev_id'])) != (str(resource['computing_id']), str(resource['dev_id'])):
                    item['reason'] = '所选芯片与摄像机已有绑定不一致：请使用 {} · {}'.format(bound['computing_name'], bound['name']); continue
            name = override.get('conf_name') or row['default_name']
            if name in existing_names:
                if override.get('conf_name'):
                    item['reason'] = '任务名称已存在，请逐摄像机修改名称'; continue
                suffix = '-' + str(camera_id) + '-' + str(library.id)
                name = name[:32 - len(suffix)] + suffix
            if name in existing_names:
                item['reason'] = '自动任务名称已存在，请逐摄像机修改名称'; continue
            existing_names.add(name)
            choice = options['stream_type']
            running = {field(conf, 'stream_type') or 'legacy' for conf in configs
                       if int(conf.Equipment_id) == camera_id and str(conf.status) == '1'}
            if choice == 'legacy' and len(running) == 1:
                choice = next(iter(running))
            payload = {'conf_name': name, 'Algorithm_library_id': library.id, 'Mine_id': row['mine_id'],
                       'Equipment_id': camera_id, 'status': '2', 'test_type_id': detection['test_type_id'],
                       'resource_id': resource_id, 'computing_id': resource['computing_id'],
                       'model_template_config_id': template_id, 'model_template_type_id': template['type_id'],
                       'template_small_id': smalls[0].id if smalls else None,
                       'confidence': format(options['confidence'] * 100, '.10g'), 'interval_time': options['interval_time'],
                       'stream_type': choice, 'conf_area': [], 'cross_line_area': None,
                       'img_resolution': field(raw, 'equipment_width_height'), 'label_list': list(detection['label_list']),
                       'duration_time': 0, 'image_draw_type': 1, 'sensitivity': options['interval_frames'], 'res_type': '1',
                       'shield_status': '2', 'draw_type': '1', 'image_count': '5', 'priority': '1',
                       'defense_time_start': '00:00:00', 'defense_time_end': '23:59:59',
                       'Algorithm_config_ps': None}
            count_parameters = default_count_parameters(library, self._get('Template', template_id), smalls[0] if smalls else None)
            if count_parameters is not None:
                payload['template_data'] = json.dumps(count_parameters, ensure_ascii=False)
            item.update(eligible=True, reason='', conf_name=name, resource_id=resource_id,
                        computing_id=resource['computing_id'], template_id=template_id,
                        resource_name=resource['name'], computing_name=resource['computing_name'],
                        resource_source='explicit' if options.get('resource_id') else recommendation['source'],
                        admission_note=resource['reason'] if resource['admission_disabled'] else '',
                        needs_setup=bool(template['should_confirm_geometry']), metadata=template,
                        stream_type=choice, stopped=True)
            payloads[camera_id] = payload
        return items, payloads

    def _key(self):
        if self.secret is not None:
            value = self.secret
        else:
            from flask import current_app
            value = current_app.config.get('JWT_SECRET_KEY') or current_app.config.get('SECRET_KEY')
        if not isinstance(value, (str, bytes)) or not value:
            raise WorkflowError('预览签名配置不可用', 503)
        return value.encode('utf-8') if isinstance(value, str) else value

    def _token(self, payload):
        raw = _json(payload).encode('utf-8')
        encoded = base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
        signature = hmac.new(self._key(), encoded.encode('ascii'), hashlib.sha256).hexdigest()
        return encoded + '.' + signature

    def _verify(self, token, actor):
        if not isinstance(token, str) or len(token) > MAX_BODY or token.count('.') != 1:
            raise WorkflowError('预览已失效，请重新预览', 409)
        encoded, signature = token.rsplit('.', 1)
        expected = hmac.new(self._key(), encoded.encode('ascii'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise WorkflowError('预览已失效，请重新预览', 409)
        try:
            value = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8'))
        except Exception:
            raise WorkflowError('预览已失效，请重新预览', 409)
        if value.get('actor') != str(actor) or value.get('expires', 0) < self.clock() or value.get('version') != VERSION:
            raise WorkflowError('预览已过期或账号不一致，请重新预览', 409)
        value['request'] = selection(value['request'])
        if not isinstance(value.get('approved_ids'), list):
            raise WorkflowError('预览已失效，请重新预览', 409)
        return value

    def preview(self, body, actor):
        prepared = selection(body)
        items, payloads = self._prepared(prepared)
        # Freeze every reviewed default. An address/name/resource changing after
        # preview must not silently choose another card or create a skipped row.
        frozen = {row['equipment_id']: dict(row) for row in prepared['overrides']}
        for camera_id, payload in payloads.items():
            frozen.setdefault(camera_id, {'equipment_id': camera_id}).update(
                conf_name=payload['conf_name'], resource_id=payload['resource_id'],
                template_id=payload['model_template_config_id'], stream_type=payload['stream_type'])
        prepared['overrides'] = list(frozen.values())
        return {'plan_id': self._token({'version': VERSION, 'actor': str(actor),
                'expires': self.clock() + TTL, 'request': prepared,
                'approved_ids': sorted(payloads)}), 'expires_in': TTL,
                'items': items, 'summary': {'eligible': sum(row['eligible'] for row in items),
                'skipped': sum(not row['eligible'] for row in items)}, 'always_stopped': True}

    def _create_one(self, payload):
        if self.creator is not None:
            return self.creator(payload)
        from service import algorithm_model_service as service
        original = _ORIGINALS.get('add_algorithm_config', service.add_algorithm_config)
        # The batch's single outer admission guard has already checked all
        # cards. Stopped drafts need no inference warmup reservation. Retain
        # all original normalization/create logic.
        raw = getattr(original, '__wrapped__', None)
        if raw is None or getattr(raw, '__name__', '') != 'add_algorithm_config':
            raise WorkflowError('当前创建入口无法安全复用，请使用原配置页面', 409)
        return raw(payload)

    def _admit(self, payloads, action):
        if not payloads:
            return action()
        if self.batch_admission is not None:
            return self.batch_admission(payloads, action)
        from service.resource_admission import guard
        @guard('create', reserve_warmup=False)
        def admitted(body):
            return action()
        return admitted({'model_data': list(payloads.values())})

    def runtime_issues(self, config=None, payload=None):
        base = {k: field(config, k) for k in ('Algorithm_library_id', 'model_template_config_id')}
        values = payload or {}
        models = values.get('model_data')
        if not isinstance(models, list):
            base.update({k: values[k] for k in base if k in values})
            children = literal(field(config, 'model_algo_data_ori')) or literal(field(config, 'model_algo_data')) or []
            models = [base] + (children if isinstance(children, list) else [])
        advanced = len(models) > 1 or str(field(config, 'multimodels_type', '0')) == '1'
        issues = []
        counts = 0
        for model in models:
            if not isinstance(model, dict):
                continue
            template_id = model.get('model_template_config_id') or model.get('template_id')
            template = self._get('Template', template_id) if template_id else None
            library_id = model.get('Algorithm_library_id')
            library = self._get('Library', library_id) if library_id else None
            name = str(field(library, 'model_name', '') or '')
            if advanced and name in KINDS:
                issues.append(runtime_issue({'model_name': name, 'model_template_config_type_id': 4}, True))
            elif template is not None:
                issue = runtime_issue(template, advanced)
                if issue:
                    issues.append(issue)
                if (is_count_model_name(name) or is_count_model_name(template.model_name)) and not count_template_matches(
                        name, template.model_name, template.model_template_config_type_id, field(library, 'analysis_type')):
                    issues.append('与算法匹配的模板')
                if str(template.model_template_config_type_id) == '3':
                    counts += 1
        if counts > 1:
            issues.append('同一高级任务不能包含多个计数模型，请为各算法创建独立任务')
        return list(dict.fromkeys(issues))

    def runtime_state(self, config):
        from service.algorithm_runtime_status import read_reports
        library = self._get('Library', config.Algorithm_library_id)
        return observed_runtime(config, read_reports(), KINDS.get(field(library, 'model_name')))

    def stream_resource_issue(self, config, payload=None):
        values = {k: field(config, k) for k in ('id', 'Equipment_id', 'resource_id', 'computing_id', 'multimodels_type')}
        values.update(payload or {})
        if str(values.get('multimodels_type')) == '1' or len(values.get('model_data') or []) > 1:
            return ''
        camera_id = values.get('Equipment_id') or values.get('equipment_name')
        resource_id = values.get('resource_id')
        if not camera_id or not resource_id:
            return ''
        selected = self._get('Resource', resource_id)
        if selected is None:
            return ''
        key = (str(selected.computing_id), str(selected.dev_id))
        for other in self._all('Config'):
            if (str(other.Equipment_id) != str(camera_id) or str(other.status) != '1'
                    or str(other.id) == str(values.get('id')) or str(field(other, 'multimodels_type')) == '1'):
                continue
            resource = self._get('Resource', other.resource_id) if other.resource_id else None
            if resource and key != (str(resource.computing_id), str(resource.dev_id)):
                return '同一摄像机并行算法需使用同一算力卡；现有任务“{}”使用芯片 {}（资源 {}），请统一后启动'.format(other.conf_name, resource.dev_id, resource.id)
        return ''

    def task_setup(self, config, payload=None):
        names = ('id', 'Equipment_id', 'Mine_id', 'Algorithm_library_id', 'resource_id', 'computing_id',
                 'model_template_config_id', 'confidence', 'interval_time', 'sensitivity', 'conf_area',
                 'cross_line_area', 'template_data', 'conf_img_resolution', 'model_algo_data_ori',
                 'Algorithm_test_type_id', 'label_list')
        saved = {name: field(config, name) for name in names}
        if payload is not None:
            values = dict(payload)
            if isinstance(values.get('model_data'), list) and values['model_data']:
                values.update(values['model_data'][0])
                values['model_algo_data_ori'] = values['model_data'][1:]
            if 'img_resolution' in values:
                values['conf_img_resolution'] = values['img_resolution']
            if 'test_type_id' in values:
                values['Algorithm_test_type_id'] = values['test_type_id']
            saved.update({name: value for name, value in values.items() if name in names})
        template_id = saved.get('model_template_config_id')
        template = self._get('Template', template_id) if template_id else None
        from service.person_count_contract import normalize_cross_line_area
        from service.algorithm_config_safety import model_roi
        def calibration_ready(values):
            from types import SimpleNamespace
            from service.uniqueness_platform import require_ready
            snapshot = dict(values)
            snapshot['Equipment_id'] = identity(snapshot.get('Equipment_id'), '摄像机')
            require_ready(SimpleNamespace(**snapshot))
        result = setup_status(saved, template, normalize_cross_line_area, model_roi, calibration_ready)
        tests = self._all('TestType')
        result['setup_missing'].extend(detection_setup(saved, tests))
        library_id = saved.get('Algorithm_library_id')
        library = self._get('Library', library_id) if library_id else None
        if library is None or template is None or not count_template_matches(
                library.model_name, template.model_name, template.model_template_config_type_id, field(library, 'analysis_type')):
            result['setup_missing'].append('与算法匹配的模板')
        try:
            children = literal(saved.get('model_algo_data_ori')) or []
            if not isinstance(children, list):
                raise ValueError()
            for child in children:
                if not isinstance(child, dict):
                    raise ValueError()
                combined = dict(saved); combined.update(child)
                if 'test_type_id' in child:
                    combined['Algorithm_test_type_id'] = child['test_type_id']
                combined['model_template_config_id'] = child.get('model_template_config_id') or child.get('template_id')
                combined['conf_img_resolution'] = child.get('img_resolution') or child.get('conf_img_resolution') or saved.get('conf_img_resolution')
                child_template = self._get('Template', combined['model_template_config_id']) if combined['model_template_config_id'] else None
                child_result = setup_status(combined, child_template, normalize_cross_line_area, model_roi, calibration_ready)
                result['setup_missing'].extend(child_result['setup_missing'])
                result['setup_missing'].extend(detection_setup(combined, tests))
                child_library = self._get('Library', combined.get('Algorithm_library_id'))
                if child_library is None or child_template is None or not count_template_matches(
                        child_library.model_name, child_template.model_name, child_template.model_template_config_type_id,
                        field(child_library, 'analysis_type')):
                    result['setup_missing'].append('与算法匹配的模板')
        except (WorkflowError, ValueError, TypeError):
            result['setup_missing'].append('高级模型逐摄像机参数')
        result['setup_missing'].extend(self.runtime_issues(config, payload))
        resource_issue = self.stream_resource_issue(config, payload)
        if resource_issue:
            result['setup_missing'].append(resource_issue)
        result['setup_missing'] = list(dict.fromkeys(result['setup_missing']))
        result.update(setup_complete=not result['setup_missing'], needs_setup=bool(result['setup_missing']),
                      setup_message='已完成逐摄像机配置' if not result['setup_missing'] else '请先完成：' + '、'.join(result['setup_missing']))
        smalls = ([row for row in self._all('Small') if row.template_small_name == field(library, 'template_small_name')]
                  if library is not None else [])
        suggested = default_count_parameters(library, template, smalls[0] if smalls else None)
        if suggested is not None:
            result['setup_defaults'] = {'template_data': suggested,
                                        'Algorithm_library_id': saved.get('Algorithm_library_id'),
                                        'model_template_config_id': saved.get('model_template_config_id'),
                                        'equipment_id': saved.get('Equipment_id')}
        return result

    def _clear_system_notes(self, request_id, actor, config_ids=None):
        """Clear exact generated text only after its created ID is durable."""
        from sqlalchemy import func
        record = self._activation_job(request_id, actor)
        algorithm_id = identity(record['selection']['algorithm_id'], '算法')
        allowed = None if config_ids is None else set(config_ids)
        tag = '[batch:' + request_id + ']'
        pure = (tag, _LEGACY_SYSTEM_NOTE, _LEGACY_SYSTEM_NOTE + ' ' + tag)
        # HEX compares exact UTF-8 bytes on both MySQL and SQLite, avoiding
        # MySQL's case/trailing-space insensitive text collation rules.
        pure_hex = tuple(value.encode('utf-8').hex().upper() for value in pure)
        Config, History = self.d['Config'], self.d['History']
        changed = 0
        try:
            self.session.rollback()
            for item in record.get('items', []):
                config_id = item.get('conf_id')
                if item.get('status') != 'created' or not config_id or (allowed is not None and config_id not in allowed):
                    continue
                camera_id = identity(item.get('equipment_id'), '摄像机')
                config = self.session.query(Config).filter(Config.id == config_id).populate_existing().with_for_update().first()
                if config is None or int(config.Equipment_id) != camera_id or int(config.Algorithm_library_id) != algorithm_id:
                    continue
                # CAS protects a human edit made between the read and write;
                # even mixed human/system text is retained in its entirety.
                if config.Algorithm_config_ps in pure:
                    changed += self.session.query(Config).filter(Config.id == config_id,
                        Config.Equipment_id == camera_id, Config.Algorithm_library_id == algorithm_id,
                        func.hex(Config.Algorithm_config_ps) == config.Algorithm_config_ps.encode('utf-8').hex().upper()).update(
                            {Config.Algorithm_config_ps: None, Config.update_time: Config.update_time},
                            synchronize_session=False)
                changed += self.session.query(History).filter(History.config_id == config_id,
                    History.Equipment_id == camera_id, History.Algorithm_library_id == algorithm_id,
                    func.hex(History.Algorithm_config_ps).in_(pure_hex)).update(
                        {History.Algorithm_config_ps: None, History.update_time: History.update_time},
                        synchronize_session=False)
            if changed:
                self.session.commit()
            else:
                self.session.rollback()
            return changed
        except Exception:
            self.session.rollback()
            raise

    def task_context(self, config_id, actor):
        config_id = identity(config_id, '任务')
        config = self._get('Config', config_id)
        if config is None:
            raise WorkflowError('尚未找到本账号的批次任务', 404)
        self.journal._check()
        matches, changed = [], False
        if self.journal.directory.is_dir():
            for path in sorted(self.journal.directory.glob('*.json')):
                if not IDENT.fullmatch(path.stem):
                    continue
                try:
                    record = self.journal.load(path.stem)
                except (OSError, ValueError):
                    continue
                if record is None or record.get('actor') != str(actor):
                    continue
                for item in record.get('items', []):
                    if item.get('status') != 'created' or item.get('conf_id') != config_id:
                        continue
                    camera_id = item.get('equipment_id')
                    algorithm_id = record.get('selection', {}).get('algorithm_id')
                    if camera_id != config.Equipment_id or algorithm_id != config.Algorithm_library_id:
                        changed = True
                        continue
                    matches.append({'request_id': record['request_id'], 'conf_id': config_id,
                                    'equipment_id': camera_id, 'algorithm_id': algorithm_id,
                                    'edit_path': edit_path(config)})
        if len(matches) > 1 or changed:
            raise WorkflowError('批次任务关联已变化，请核实当前配置', 409)
        if not matches:
            raise WorkflowError('尚未找到本账号的批次任务', 404)
        return matches[0]

    def batch_owned(self, config):
        # A user may edit the visible remarks. Persisted created IDs remain the
        # authoritative membership source and are never inferred from names/IPs.
        config_id = int(field(config, 'id'))
        marker = re.search(r'\[batch:([a-f0-9]{32})\]', str(field(config, 'Algorithm_config_ps', '') or ''))
        if marker:
            return True
        self.journal._check()
        if self.journal.directory.is_dir():
            for path in self.journal.directory.glob('*.json'):
                if not IDENT.fullmatch(path.stem):
                    continue
                try:
                    record = self.journal.load(path.stem)
                except (OSError, ValueError):
                    continue
                if record is None:
                    continue
                if any(item.get('status') == 'created' and item.get('conf_id') == config_id for item in record.get('items', [])):
                    return True
        return False

    def public_job(self, record):
        result = {key: record[key] for key in ('request_id', 'status', 'summary', 'created_at', 'updated_at') if key in record}
        result['items'] = []
        for original in record.get('items', []):
            item = dict(original)
            if item.get('status') == 'created' and item.get('conf_id'):
                config = self._get('Config', item['conf_id'])
                if config is None:
                    item.update(deleted=True, setup_complete=False, needs_setup=False,
                                setup_missing=['任务已删除'], setup_message='任务已删除')
                else:
                    item.update(deleted=False, stopped=str(config.status) == '2', run_status=str(config.status), **self.task_setup(config))
                    item.update(self.runtime_state(config))
                    path = edit_path(config)
                    item['edit_path'] = (path + ('&' if '?' in path else '?') + 'batch_request_id=' + record['request_id']
                                         + '&batch_equipment_id=' + str(item['equipment_id']))
                recent = [value for value in record.get('activations', {}).values()
                          if value.get('conf_id') == item['conf_id'] and value.get('equipment_id') == item['equipment_id']]
                latest = max(recent, key=lambda value: (value.get('sequence', 0), value.get('created_at', 0))) if recent else None
                item['start_status'] = latest.get('status') if latest else None
                item['start_message'] = latest.get('message', '') if latest else ''
            result['items'].append(item)
        return result

    def _activation_job(self, request_id, actor):
        record = self.journal.load(_id(request_id))
        if not record or record.get('actor') != str(actor):
            raise WorkflowError('尚未找到本账号的批量执行记录', 404)
        return record

    def _activation_view(self, intent, pending_active=False):
        result = {name: intent.get(name) for name in
                  ('intent_id', 'equipment_id', 'conf_id', 'status', 'message')}
        if result['status'] == 'pending' and not pending_active:
            result.update(status='unknown', message='启动结果尚未确认，请核实当前任务状态；本意图不会重复执行')
        config = self.session.query(self.d['Config']).filter(
            self.d['Config'].id == intent['conf_id']).populate_existing().first()
        associated = (config is not None and int(config.Equipment_id) == intent['equipment_id']
                      and int(config.Algorithm_library_id) == intent.get('algorithm_id'))
        readiness = self.task_setup(config) if associated else {'setup_complete': False}
        result.update(run_status=str(config.status) if config is not None else None,
                      setup_complete=readiness['setup_complete'],
                      terminal=result['status'] != 'pending', runtime_healthy=None)
        result['activation_accepted'] = associated and result['status'] in ('started', 'already_running') and result['run_status'] == '1'
        if associated:
            result.update(self.runtime_state(config))
        result['retry_allowed'] = associated and result['status'] in ('blocked', 'failed') and result['run_status'] == '2'
        if not associated:
            result['message'] = '任务已删除或关联已变更；请核实当前任务，本意图不会重新执行'
        elif result['status'] in ('blocked', 'failed') and not readiness['setup_complete']:
            result['message'] = readiness['setup_message']
        elif result['status'] in ('started', 'already_running') and result['run_status'] != '1':
            result['message'] = '当前任务已停止或删除；原启动意图已处理，不会自动重新启动'
        return result

    def activation_result(self, request_id, intent_id, actor):
        intent_id = _id(intent_id)
        record = self._activation_job(request_id, actor)
        intent = record.get('activations', {}).get(intent_id)
        if intent is None:
            raise WorkflowError('尚未找到该保存操作的启动记录，请核实当前任务状态', 404)
        active = False
        if intent.get('status') == 'pending':
            # A dead writer's pending receipt is uncertain, never permission
            # to replay its mutation. GET performs no journal or task writes.
            with self.journal.lock('request-' + request_id, blocking=False) as acquired:
                active = not acquired
                if acquired:
                    record = self._activation_job(request_id, actor)
                    intent = record.get('activations', {}).get(intent_id, intent)
        return self._activation_view(intent, pending_active=active)

    def _start_one(self, config_id):
        payload = {'id': config_id, 'status': '运行'}
        if self.starter is not None:
            return self.starter(payload)
        from service.algorithm_model_service import algorithm_conf_update_service
        # The original resource guard and the batch readiness guard stay in
        # force, including genuine pending model-loading reservations.
        return algorithm_conf_update_service(payload)

    def activate(self, request_id, body, actor):
        if not isinstance(body, dict) or set(body) != {'equipment_id', 'conf_id', 'intent_id'}:
            raise WorkflowError('逐路启动参数无效')
        intent_id = _id(body['intent_id'])
        camera_id = identity(body['equipment_id'], '摄像机')
        config_id = identity(body['conf_id'], '任务')
        self._activation_job(request_id, actor)
        with self.journal.lock('request-' + request_id):
            record = self._activation_job(request_id, actor)
            # This is an explicit authenticated write flow. Read-only result
            # and context requests never perform business-note cleanup.
            self._clear_system_notes(request_id, actor)
            intents = record.setdefault('activations', {})
            previous = intents.get(intent_id)
            if previous is not None:
                if previous.get('equipment_id') != camera_id or previous.get('conf_id') != config_id:
                    raise WorkflowError('启动意图编号已用于其他任务', 409)
                return self._activation_view(previous)
            created = [item for item in record.get('items', []) if item.get('status') == 'created'
                       and item.get('equipment_id') == camera_id and item.get('conf_id') == config_id]
            if len(created) != 1 or record.get('status') != 'completed':
                raise WorkflowError('仅可启动本账号该已完成批次精确创建的任务', 409)
            if len(intents) >= 200:
                raise WorkflowError('本批启动尝试较多，请通过原算法配置列表核实后操作', 409)
            intent = {'intent_id': intent_id, 'equipment_id': camera_id, 'conf_id': config_id,
                      'algorithm_id': identity(record['selection']['algorithm_id'], '算法'),
                      'status': 'pending', 'message': '正在提交本路运行状态', 'created_at': self.clock(),
                      'updated_at': self.clock(),
                      'sequence': max([value.get('sequence', 0) for value in intents.values()] + [0]) + 1}
            intents[intent_id] = intent
            record['updated_at'] = self.clock()
            if len(_json(record).encode('utf-8')) > MAX_BODY - 2048:
                raise WorkflowError('本批执行记录已满，请通过原算法配置列表核实后操作', 409)
            # Persist before any state mutation. A crash can leave uncertainty
            # but can never make the same intent execute a second time.
            self.journal.save(record)
            called = False
            try:
                with self.locker(camera_id):
                    self.session.rollback()
                    config = self.session.query(self.d['Config']).filter(
                        self.d['Config'].id == config_id).populate_existing().with_for_update().first()
                    if config is None or int(config.Equipment_id) != camera_id or int(config.Algorithm_library_id) != int(record['selection']['algorithm_id']):
                        raise WorkflowError('任务已删除或摄像机、算法关联已变更，请核实后重新配置', 409)
                    ready = self.task_setup(config)
                    if not ready['setup_complete']:
                        raise WorkflowError(ready['setup_message'], 409)
                    if str(config.status) not in ('1', '2'):
                        raise WorkflowError('当前任务状态无效，请刷新后核实', 409)
                    was_running = str(config.status) == '1'
                    called = True
                    outcome = self._start_one(config_id)
                    self.session.rollback()
                    actual = self.session.query(self.d['Config']).filter(
                        self.d['Config'].id == config_id).populate_existing().first()
                    code = outcome.get('code') if isinstance(outcome, dict) else None
                    if code == 200 and actual is not None and str(actual.status) == '1':
                        intent.update(status='already_running' if was_running else 'started',
                                      message='已提交运行状态；算法实际健康状态请在配置列表查看')
                    elif code in (400, 403, 404, 409) and actual is not None and str(actual.status) == '2':
                        reason = outcome.get('msg')
                        reason = reason.strip()[:180] if isinstance(reason, str) else ''
                        intent.update(status='blocked', message=reason or '启动未通过，请检查配置后重试')
                    else:
                        intent.update(status='unknown', message='启动结果尚未确认，请核实当前任务状态；本意图不会重复执行')
            except WorkflowError as error:
                self.session.rollback()
                intent.update(status='unknown' if called else 'blocked',
                              message='启动结果尚未确认，请核实当前任务状态' if called else str(error)[:180])
            except Exception:
                self.session.rollback()
                intent.update(status='unknown' if called else 'failed',
                              message='启动结果尚未确认，请核实当前任务状态' if called else '启动前校验暂不可用，任务保持原状态，请核实后重试')
            intent['updated_at'] = self.clock(); record['updated_at'] = self.clock()
            self.journal.save(record)
            return self._activation_view(intent)

    def results(self, request_id, actor):
        record = self.journal.load(_id(request_id))
        if not record or record.get('actor') != str(actor):
            raise WorkflowError('尚未找到本账号的批量执行记录', 404)
        if record.get('status') == 'running' and self.clock() - record.get('updated_at', record['created_at']) >= 30:
            with self.journal.lock('request-' + request_id, blocking=False) as acquired:
                if acquired:
                    record = self.journal.load(request_id)
                    if record.get('status') == 'running' and self.clock() - record.get('updated_at', record['created_at']) >= 30:
                        record = self._reconcile_interrupted(record)
                        self.journal.save(record)
        return self.public_job(record)

    def _reconcile_interrupted(self, record):
        # A worker may die after the legacy helper commits but before its
        # journal update. Reconcile by this request's marker; never replay a
        # create or alter an existing task from a read-only results request.
        request = record.get('selection', {})
        tag = '[batch:' + record['request_id'] + ']'
        known = {row['equipment_id'] for row in record['items']}
        configs = [row for row in self._all('Config') if tag in str(field(row, 'Algorithm_config_ps', '') or '')]
        for camera in request.get('camera_ids', []):
            if camera in known:
                continue
            matched = next((row for row in configs if int(row.Equipment_id) == camera
                            and int(row.Algorithm_library_id) == request.get('algorithm_id')), None)
            item = {'equipment_id': camera, 'status': 'failed', 'reason': '执行进程中断，未确认创建；请重新预览后操作'}
            if matched is not None:
                item.update(status='created', reason='已找到本批次创建的任务', conf_id=matched.id,
                            edit_path=edit_path(matched), stopped=str(matched.status) == '2', needs_setup=True)
            record['items'].append(item)
        record.update(status='completed', summary={name: sum(row['status'] == name for row in record['items'])
                      for name in ('created', 'skipped', 'failed')})
        record['updated_at'] = self.clock()
        return record

    def create(self, body, actor):
        try:
            if not isinstance(body, dict) or set(body) != {'plan_id', 'request_id'}:
                raise WorkflowError('创建请求参数无效')
            request_id = _id(body['request_id'])
            plan = self._verify(body['plan_id'], actor)
        except WorkflowError as error:
            error.safe_to_repreview = True
            raise
        request = plan['request']
        fingerprint = hashlib.sha256(_json(request).encode('utf-8')).hexdigest()
        with self.journal.lock('request-' + request_id):
            record = self.journal.load(request_id)
            if record:
                if record.get('actor') != str(actor) or record.get('fingerprint') != fingerprint:
                    raise WorkflowError('请求编号已用于其它操作，请重新预览', 409)
                if record.get('status') == 'running' and self.clock() - record.get('updated_at', record['created_at']) >= 30:
                    record = self._reconcile_interrupted(record)
                    self.journal.save(record)
                self._clear_system_notes(request_id, actor)
                return self.public_job(record)
            try:
                items, payloads = self._prepared(request)
            except WorkflowError as error:
                error.safe_to_repreview = True
                raise
            approved = set(plan['approved_ids'])
            for item in items:
                if item['equipment_id'] not in approved:
                    item.update(eligible=False, reason='预览时未通过校验，保留当前配置；如需新增请重新预览')
                    payloads.pop(item['equipment_id'], None)
            record = {'request_id': request_id, 'actor': str(actor), 'fingerprint': fingerprint,
                      'status': 'running', 'created_at': self.clock(), 'updated_at': self.clock(),
                      'pid': os.getpid(), 'process_ticks': _process_ticks(os.getpid()),
                      'selection': request, 'items': [], 'summary': {'created': 0, 'skipped': 0, 'failed': 0}}
            self.journal.save(record)
            def process():
                for item in items:
                    camera_id = item['equipment_id']
                    result = {'equipment_id': camera_id, 'name': item['name'], 'status': 'skipped',
                              'reason': item.get('reason', ''), 'needs_setup': item.get('needs_setup', False)}
                    if item['eligible']:
                        try:
                            with self.locker(camera_id):
                                self.session.rollback()  # fresh read after waiting for another creator
                                if self._get('Equipment', camera_id) is None:
                                    raise WorkflowError('该摄像机已删除，请重新选择', 409)
                                current = self._existing().get(camera_id, [])
                                duplicate = next((row for row in current if row.get('algorithm_id') == request['algorithm_id'] or row.get('unresolved')), None)
                                if duplicate:
                                    result.update(reason='当前算法已配置，保留原任务', conf_id=duplicate['conf_id'], edit_path=duplicate['edit_path'])
                                else:
                                    payload = payloads[camera_id]
                                    # The fresh-read rollback above releases
                                    # the batch admission transaction's model
                                    # locks. Reacquire the same library lock as
                                    # package deletion until legacy insert
                                    # commits its new reference.
                                    from service.algorithm_config_safety import lock_configuration_libraries
                                    libraries = lock_configuration_libraries(self.session, self.d['Library'], payload)
                                    library = next(row for row in libraries if row.id == request['algorithm_id'])
                                    resource = self.session.query(self.d['Resource']).filter(
                                        self.d['Resource'].id == payload['resource_id']).populate_existing().with_for_update().first()
                                    if str(library.algorithm_status) != '1':
                                        raise WorkflowError('算法包已停止，请重新预览', 409)
                                    if (resource is None or int(resource.computing_id) != int(payload['computing_id'])
                                            or not compatible(library, resource)):
                                        raise WorkflowError('算力卡或兼容关系已变化，请重新预览', 409)
                                    # A brief internal recovery tag bridges the
                                    # legacy commit/private-receipt gap. It is
                                    # removed only after the new ID is durable.
                                    payload['Algorithm_config_ps'] = '[batch:' + request_id + ']'
                                    outcome = self._create_one(payload)
                                    if not isinstance(outcome, dict) or int(outcome.get('code', 500)) != 200:
                                        result.update(status='failed', reason='创建未通过：' + str(outcome.get('msg', '请检查参数'))[:180] if isinstance(outcome, dict) else '创建未通过，请检查参数')
                                    else:
                                        self.session.expire_all()
                                        row = self.session.query(self.d['Config']).filter(
                                            self.d['Config'].Equipment_id == camera_id,
                                            self.d['Config'].Algorithm_library_id == request['algorithm_id']).order_by(self.d['Config'].id.desc()).first()
                                        if row is None or str(row.status) != '2':
                                            raise WorkflowError('创建结果待核实，请在原配置页面检查', 409)
                                        result.update(status='created', reason='已创建停用任务', conf_id=row.id,
                                                      edit_path=edit_path(row), stopped=True)
                        except WorkflowError as error:
                            self.session.rollback(); result.update(status='failed', reason=str(error))
                        except Exception:
                            self.session.rollback(); result.update(status='failed', reason='创建暂未完成，请查看原配置页面后再操作')
                    record['items'].append(result)
                    record['summary'][result['status']] += 1
                    record['updated_at'] = self.clock(); self.journal.save(record)
                    if result['status'] == 'created':
                        try:
                            self._clear_system_notes(request_id, actor, [result['conf_id']])
                        except Exception:
                            # The committed task and durable ownership remain
                            # intact. A replay/explicit write can retry cleanup.
                            result['notes_cleanup_pending'] = True
                            self.journal.save(record)
                return {'code': 200}
            outcome = self._admit(payloads, process)
            if not isinstance(outcome, dict) or int(outcome.get('code', 500)) != 200:
                for item in items:
                    if not any(row['equipment_id'] == item['equipment_id'] for row in record['items']):
                        record['items'].append({'equipment_id': item['equipment_id'], 'name': item['name'],
                                                'status': 'failed', 'reason': '资源状态变化或正在部署，请稍后重新预览'})
                        record['summary']['failed'] += 1
            record['status'] = 'completed'; record['updated_at'] = self.clock(); self.journal.save(record)
            return self.public_job(record)


def install_creation_guards(service):
    """Use the same per-camera dedupe rule for legacy normal/advanced forms."""
    if getattr(service, '__algorithm_first_guards', False):
        return
    for name in ('add_algorithm_config', 'add_algorithm_config_models', 'update_algorithm_config', 'update_algorithm_config_models'):
        original = getattr(service, name, None)
        if original is None:
            continue
        _ORIGINALS[name] = original
        def wrap(function, operation):
            @wraps(function)
            def guarded(payload):
                try:
                    dependencies = _dependencies(); db = dependencies['db']
                    camera_id = identity(payload.get('Equipment_id') or payload.get('equipment_name'), '摄像机')
                    wanted = requested_libraries(payload)
                    current_id = identity(payload.get('id'), '任务') if operation.startswith('update_') else None
                    current = (db.session.query(dependencies['Config']).filter(
                        dependencies['Config'].id == current_id).first()) if current_id else None
                    if current_id and current is None:
                        return {'code': 404, 'msg': '算法配置不存在'}
                    runtime_errors = Workflow(dependencies).runtime_issues(current, payload)
                    models = payload.get('model_data')
                    primary = models[0] if isinstance(models, list) and models and isinstance(models[0], dict) else payload
                    if str(primary.get('status', field(current, 'status', '2'))) in ('1', '运行'):
                        resource_issue = Workflow(dependencies).stream_resource_issue(current, payload)
                        if resource_issue:
                            runtime_errors.append(resource_issue)
                    if runtime_errors:
                        return {'code': 409, 'msg': '；'.join(runtime_errors)}
                    old_camera = int(current.Equipment_id) if current is not None else camera_id
                    with equipment_locks(db, (camera_id, old_camera)):
                        db.session.rollback()
                        current = (db.session.query(dependencies['Config']).filter(
                            dependencies['Config'].id == current_id).first()) if current_id else None
                        if current_id and current is None:
                            return {'code': 404, 'msg': '算法配置不存在'}
                        if current is None or int(current.Equipment_id) != camera_id:
                            equipment = dependencies['Equipment']
                            if db.session.query(equipment.id).filter(equipment.id == camera_id).first() is None:
                                return {'code': 409, 'msg': '该摄像机已删除，请重新选择'}
                        stopped_save = False
                        if current is not None:
                            workflow = Workflow(dependencies)
                            owned = workflow.batch_owned(current)
                            if owned:
                                # A start may race an editor save. Keep the
                                # stopped decision authoritative until the
                                # original save commits or rolls back.
                                current = db.session.query(dependencies['Config']).filter(
                                    dependencies['Config'].id == current_id).populate_existing().with_for_update().first()
                            models = payload.get('model_data')
                            primary = models[0] if isinstance(models, list) and models and isinstance(models[0], dict) else payload
                            requested_status = str(primary.get('status', current.status))
                            stopped_save = owned and str(current.status) == '2' and requested_status in ('2', '停止')
                            if requested_status in ('1', '运行') and owned:
                                readiness = workflow.task_setup(current, payload)
                                if not readiness['setup_complete']:
                                    db.session.rollback()
                                    return {'code': 409, 'msg': readiness['setup_message'], 'setup_required': True,
                                            'setup_missing': readiness['setup_missing']}
                            if owned and isinstance(primary.get('confidence'), bool):
                                return {'code': 400, 'msg': '置信度须为 0 至 100 的数值'}
                            if owned and 'confidence' in primary and primary.get('confidence') in (0, 0.0, '0', '0.0'):
                                payload = dict(payload)
                                if primary is not payload and isinstance(models, list):
                                    payload['model_data'] = [dict(item) for item in models]
                                    payload['model_data'][0]['confidence'] = '0'
                                else:
                                    payload['confidence'] = '0'
                        # Keep historical overlapping tasks editable. Only new
                        # algorithm memberships (or a changed camera) must pass
                        # the stronger duplicate rule introduced by this flow.
                        check = (wanted - library_ids(current) if current is not None
                                 and int(current.Equipment_id) == camera_id else wanted)
                        rows = db.session.query(dependencies['Config']).filter(dependencies['Config'].Equipment_id == camera_id).all()
                        for row in rows:
                            if current_id is not None and row.id == current_id:
                                continue
                            if check and check.intersection(library_ids(row)):
                                return {'code': 409, 'msg': '该监控点下已存在所选算法，请编辑原任务'}
                        if stopped_save:
                            raw = getattr(function, '__wrapped__', None)
                            if raw is None or getattr(raw, '__name__', '') != operation:
                                raise WorkflowError('当前保存入口无法安全复用，请刷新后重试', 409)
                            from service.resource_admission import guard
                            # Reuse every admission check and lock, omitting
                            # only a NEW warmup token for a stopped draft.
                            return guard('update', reserve_warmup=False)(raw)(payload)
                        return function(payload)
                except WorkflowError as error:
                    return {'code': error.status, 'msg': str(error)}
                except Exception:
                    return {'code': 409, 'msg': '摄像机算法配置校验暂不可用，请稍后重试'}
            return guarded
        setattr(service, name, wrap(original, name))
    for name in ('algorithm_conf_update_service', 'algorithm_conf_batch_update_service'):
        original = getattr(service, name, None)
        if original is None:
            continue
        _ORIGINALS[name] = original
        def wrap_start(function, operation):
            @wraps(function)
            def guarded(payload):
                # Stops and partial stopped saves always retain the old path.
                if str(payload.get('status')) not in ('1', '运行'):
                    return function(payload)
                try:
                    dependencies = _dependencies()
                    workflow = Workflow(dependencies)
                    ids = payload.get('ids') if operation == 'algorithm_conf_batch_update_service' else [payload.get('id')]
                    if not isinstance(ids, list) or not ids:
                        return function(payload)
                    for value in ids:
                        config = workflow._get('Config', identity(value, '任务'))
                        if config is not None:
                            runtime_errors = workflow.runtime_issues(config)
                            resource_issue = workflow.stream_resource_issue(config)
                            if resource_issue:
                                runtime_errors.append(resource_issue)
                            if runtime_errors:
                                return {'code': 409, 'msg': '；'.join(runtime_errors)}
                        if config is not None and workflow.batch_owned(config):
                            config = workflow.session.query(workflow.d['Config']).filter(
                                workflow.d['Config'].id == config.id).populate_existing().with_for_update().first()
                            readiness = workflow.task_setup(config)
                            if not readiness['setup_complete']:
                                workflow.session.rollback()
                                return {'code': 409, 'msg': '任务 {} 尚未完成配置：{}'.format(config.id, readiness['setup_message']),
                                        'setup_required': True, 'setup_missing': readiness['setup_missing']}
                    return function(payload)
                except WorkflowError as error:
                    return {'code': error.status, 'msg': str(error)}
                except Exception:
                    return {'code': 409, 'msg': '逐摄像机配置状态暂无法核实，请稍后重试'}
            return guarded
        setattr(service, name, wrap_start(original, name))
    service.__algorithm_first_guards = True


def register_routes(blueprint, auth):
    if getattr(blueprint, '__algorithm_first_routes', False):
        return
    from flask import current_app, g, jsonify, request
    from common.platform_access import has_menu_permission
    def actor(action='r'):
        user = getattr(g, 'platform_user', None)
        if user is None or not has_menu_permission(user.id, 'sfgl', action):
            raise WorkflowError('当前账号没有算法配置权限', 403)
        return str(user.id)
    def response(function, action='r'):
        @wraps(function)
        @auth
        def endpoint():
            try:
                owner = actor(action)
                if request.content_length and request.content_length > MAX_BODY:
                    raise WorkflowError('请求内容过长', 413)
                return jsonify({'code': 200, 'data': function(Workflow(), owner)})
            except WorkflowError as error:
                return jsonify({'code': error.status, 'msg': str(error),
                                'safe_to_repreview': bool(getattr(error, 'safe_to_repreview', False))}), error.status
            except Exception:
                return jsonify({'code': 409, 'msg': '算法配置暂不可用，请刷新后重试'}), 409
        return endpoint
    routes = [('/catalog', 'GET', 'catalog', lambda w, a: w.catalog(has_menu_permission(int(a), 'sfgl', 'c')), 'r'),
              ('/cameras', 'GET', 'cameras', lambda w, a: w.cameras(request.args.get('algorithm_id'),
               request.args.get('mine_id'), request.args.get('parent_id'), request.args.get('search', ''),
               request.args.get('page', 1), request.args.get('per_page', 30)), 'r'),
              ('/options', 'GET', 'options', lambda w, a: w.options(request.args.get('algorithm_id')), 'r'),
              ('/resource-default', 'GET', 'resource_default', lambda w, a: w.resource_default(
               request.args.get('equipment_id'), request.args.get('algorithm_id')), 'r'),
              ('/task-context', 'GET', 'task_context', lambda w, a: w.task_context(request.args.get('conf_id'), a), 'r'),
              ('/preview', 'POST', 'preview', lambda w, a: w.preview(request.get_json(silent=True), a), 'c'),
              ('/create', 'POST', 'create', lambda w, a: w.create(request.get_json(silent=True), a), 'c')]
    for path, method, name, handler, action in routes:
        blueprint.add_url_rule('/algorithm_first' + path, 'algorithm_first_' + name,
                               response(handler, action), methods=[method])
    @auth
    def results(request_id):
        try:
            owner = actor('r')
            return jsonify({'code': 200, 'data': Workflow().results(request_id, owner)})
        except WorkflowError as error:
            return jsonify({'code': error.status, 'msg': str(error)}), error.status
        except Exception:
            return jsonify({'code': 409, 'msg': '执行记录暂不可用，请稍后查询'}), 409
    blueprint.add_url_rule('/algorithm_first/jobs/<request_id>', 'algorithm_first_results', results, methods=['GET'])
    @auth
    def start(request_id):
        try:
            owner = actor('u' if request.method == 'POST' else 'r')
            if request.content_length and request.content_length > MAX_BODY:
                raise WorkflowError('请求内容过长', 413)
            workflow = Workflow()
            value = (workflow.activate(request_id, request.get_json(silent=True), owner) if request.method == 'POST'
                     else workflow.activation_result(request_id, request.args.get('intent_id'), owner))
            return jsonify({'code': 200, 'data': value})
        except WorkflowError as error:
            return jsonify({'code': error.status, 'msg': str(error)}), error.status
        except Exception:
            return jsonify({'code': 409, 'msg': '启动结果暂不可用，请查询原意图；不要重复提交'}), 409
    blueprint.add_url_rule('/algorithm_first/jobs/<request_id>/start', 'algorithm_first_start', start, methods=['GET', 'POST'])
    blueprint.__algorithm_first_routes = True
