"""Recover one existing preview binding without replacing its public identity.

The public entry point is recover_bound_preview(equipment_id). Dependencies are
loaded lazily; isolated tests inject _services and never open DB/Redis sockets.
An existing proxy can be replaced only with cross-sweep stalled evidence and
fresh zero-reader/source/identity checks under the original recovery locks.
It never restarts ZLK. Successful creation remains pending until video advances.
"""
import contextlib
import hashlib
import json
import re
import subprocess
import time
import uuid
from urllib.parse import unquote, urlsplit

PROTOCOL_FIELDS = (
    ('enable_rtsp', 'zlk_rtsp'), ('enable_hls', 'zlk_hls'),
    ('enable_hls_fmp4', 'zlk_hls_fmp4'), ('enable_rtmp', 'zlk_rtmp'),
    ('enable_ts', 'zlk_ts'), ('enable_fmp4', 'zlk_mp4'))
URL_FIELDS = tuple(field for _, field in PROTOCOL_FIELDS) + ('zlk_flv',)
RECOVERY_LOCK = '/tmp/seal_zlk_stream_recovery.lock'


class RecoveryError(Exception):
    def __init__(self, code, message, reason='recovery_failed', status=None):
        self.code, self.message, self.reason, self.status = code, message, reason, status
        super().__init__(message)


def _identity(value):
    if isinstance(value, str):
        value = value.strip()
        if not value or not value.isascii() or not value.isdigit():
            raise RecoveryError(400, '设备ID必须为正整数')
        value = int(value)
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise RecoveryError(400, '设备ID必须为正整数')
    return value


def _canonical_source(source):
    if not isinstance(source, str) or not source or len(source) > 255 or any(ord(c) < 32 for c in source):
        raise RecoveryError(409, '绑定来源地址无效，未修改转发')
    try:
        value = urlsplit(source)
        if value.scheme not in ('rtsp', 'rtsps') or not value.hostname or value.fragment:
            raise ValueError()
        return (value.scheme, value.hostname.lower(), value.port or 554,
                unquote(value.username or ''), unquote(value.password or ''), value.path, value.query)
    except (TypeError, ValueError):
        raise RecoveryError(409, '绑定来源地址无效，未修改转发')


def _is_direct_camera(snapshot):
    equipment = snapshot['equipment']
    return equipment['type'] == '摄像头' and equipment['parent_id'] is None


def _validate(snapshot, recheck_recorder=False):
    equipment, binding, parent = snapshot['equipment'], snapshot['binding'], snapshot['parent']
    if equipment['enabled'] not in ('1', None):
        raise RecoveryError(409, '监控点已禁用，未恢复转发')
    require_online = not recheck_recorder or _is_direct_camera(snapshot)
    if require_online and equipment['online'] not in (1, '1'):
        raise RecoveryError(409, '监控点在线状态未确认，未恢复转发')
    if _is_direct_camera(snapshot):
        if parent is not None or snapshot.get('vcr') is not None or equipment.get('vcr_id') is not None:
            raise RecoveryError(409, '直连摄像头归属不符，未恢复转发')
        if (not binding or _canonical_source(binding['source']) !=
                _canonical_source(snapshot.get('registered_camera_source'))):
            raise RecoveryError(409, '原绑定与登记的摄像头直连来源不一致，未修改转发',
                                'registered_source_mismatch')
        key = binding.get('key')
        if (not isinstance(key, str) or len(key) > 512 or any(c.isspace() or ord(c) < 32 for c in key)
                or len(key.rsplit('/', 2)) != 3 or not key.rsplit('/', 2)[0]
                or key.rsplit('/', 2)[-2:] != [binding['app'], binding['live']]):
            raise RecoveryError(409, '原直连转发身份不完整，未修改转发', 'proxy_identity_changed')
    elif (not parent or equipment['parent_id'] != parent['id']
            or equipment['type'] not in ('录像机', '特殊摄像头', '视频中心存储')
            or parent['enabled'] not in ('1', None) or (require_online and parent['online'] not in (1, '1'))):
        raise RecoveryError(409, '录像机归属或启用状态不符，未恢复转发')
    if (not binding or equipment['binding_id'] != binding['id']
            or str(binding['owner']) != str(equipment['id'])):
        raise RecoveryError(409, '设备与流媒体绑定归属不一致，未修改转发')
    if (binding['app'] != 'openUrl' or not isinstance(binding['live'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', binding['live'])):
        raise RecoveryError(409, '绑定app或stream不受支持，未修改转发')
    _canonical_source(binding['source'])
    if not any(bool(binding['urls'].get(field)) for _, field in PROTOCOL_FIELDS):
        raise RecoveryError(409, '原绑定未启用输出协议，未更改协议配置')


def _signature(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _probe_source(source):
    """Return structured evidence only; source/ffprobe stderr never escape."""
    try:
        result = subprocess.run(['/data/AIGO/platform_start/runtime/bin/ffprobe', '-v', 'error', '-rtsp_transport', 'tcp',
            '-analyzeduration', '2000000', '-probesize', '1000000',
            '-show_entries', 'stream=codec_type,codec_name,width,height', '-of', 'json', source],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12, check=False)
        if result.returncode == 0:
            body = json.loads(result.stdout.decode('utf-8'))
            video = any(item.get('codec_type') == 'video'
                        and type(item.get('width')) is int and item['width'] > 0
                        and type(item.get('height')) is int and item['height'] > 0
                        for item in body.get('streams', []) if isinstance(item, dict))
            return {'video': video, 'status': None}
        diagnostic = result.stderr.decode('utf-8', 'replace')
        status = re.search(r'(?:method\s+(?:DESCRIBE|SETUP|PLAY)\s+failed:\s*|'
                           r'server\s+returned\s+|RTSP/\d\.\d\s+)([45][0-9]{2})\b', diagnostic, re.I)
        return {'video': False, 'status': int(status.group(1)) if status else None}
    except subprocess.TimeoutExpired:
        return {'video': False, 'status': None, 'timeout': True}
    except Exception:
        return {'video': False, 'status': None, 'probe_error': True}


def _has_video(rows, app, live):
    return any(item.get('app') == app and item.get('stream') == live
               and any(str(track.get('codec_type')) == '0' and track.get('ready') is not False
                       and ('frames' not in track or (type(track['frames']) is int and track['frames'] > 0))
                       for track in item.get('tracks') or []
                       if isinstance(track, dict)) for item in rows if isinstance(item, dict))


def _proxy_entries(data):
    if data is None:
        return []
    if isinstance(data, dict):
        if any(not isinstance(value, dict) for value in data.values()):
            raise RecoveryError(503, '无法确认代理身份', 'proxy_evidence_missing')
        return [dict(value, key=key) for key, value in data.items()]
    if not isinstance(data, list) or any(not isinstance(value, dict) for value in data):
        raise RecoveryError(503, '无法确认代理身份', 'proxy_evidence_missing')
    return data


def _proxy_identity(item):
    source = item.get('src') if isinstance(item.get('src'), dict) else {}
    key = item.get('key')
    parts = key.rsplit('/', 2) if isinstance(key, str) else []
    app = source.get('app') or item.get('app') or (parts[-2] if len(parts) == 3 else None)
    live = source.get('stream') or item.get('stream') or (parts[-1] if len(parts) == 3 else None)
    return app, live


def _index_proxies(data):
    grouped = {}
    for item in _proxy_entries(data):
        app, live = _proxy_identity(item)
        if isinstance(app, str) and isinstance(live, str):
            grouped.setdefault((app, live), []).append(item)
    return grouped


def _detail_for_proxy_matches(matches, relevant):
    if not matches:
        return None
    if len(matches) != 1:
        return {'ambiguous': True}
    item = matches[0]
    source = item.get('src') if isinstance(item.get('src'), dict) else {}
    detail = {'key': item.get('key'), 'source': source.get('url') or item.get('url')}
    counts = []
    incomplete = False
    # A proxy's aggregate count is preferred. If absent, every actual media
    # protocol must explicitly report its readers. Absence is not evidence 0.
    dst = item.get('dst') if isinstance(item.get('dst'), dict) else {}
    holders = [holder for holder in (item, dst)
               if 'totalReaderCount' in holder or 'readerCount' in holder]
    holders += relevant
    for holder in holders:
        values = [holder[name] for name in ('totalReaderCount', 'readerCount') if name in holder]
        if not values or any(type(value) is not int or value < 0 for value in values):
            incomplete = True
        else:
            counts.extend(values)
    detail['readers'] = max(counts) if counts and not incomplete else None
    return detail


def _proxy_detail(data, media, app, live):
    """Private evidence only; no raw source is returned by the public APIs."""
    matches = [item for item in _proxy_entries(data) if _proxy_identity(item) == (app, live)]
    if len(matches) != 1:
        return _detail_for_proxy_matches(matches, ())
    relevant = [row for row in media if isinstance(row, dict)
                and (row.get('app'), row.get('stream')) == (app, live)]
    return _detail_for_proxy_matches(matches, relevant)


def _proxy_token(detail):
    if not detail or detail.get('ambiguous'):
        return None
    key, source = detail.get('key'), detail.get('source')
    if (not isinstance(key, str) or not key or len(key) > 512
            or any(ord(char) < 32 for char in key)):
        return None
    try:
        return hashlib.sha256(repr((key, _canonical_source(source))).encode('utf-8')).hexdigest()
    except RecoveryError:
        return None


def _verify_stalled(binding, state, observation):
    detail = state.get('proxy_detail')
    token = _proxy_token(detail)
    if not token or not observation or token != observation.get('proxy_token'):
        raise RecoveryError(409, '代理身份或来源证据不足，保持现状', 'proxy_evidence_missing')
    if (detail['key'] != binding['key']
            or detail['key'].rsplit('/', 2)[-2:] != [binding['app'], binding['live']]
            or _canonical_source(detail['source']) != _canonical_source(binding['source'])):
        raise RecoveryError(409, '代理与当前绑定不一致，保持现状', 'proxy_identity_changed')
    first = observation.get('first_seen_at')
    if (type(first) not in (int, float) or not 0 <= first <= time.time() - 120
            or type(observation.get('observations')) is not int or observation['observations'] < 2):
        raise RecoveryError(409, '代理仍在有界观察期间', 'proxy_observing')
    if type(detail.get('readers')) is not int or detail['readers'] != 0:
        reason = 'proxy_has_readers' if type(detail.get('readers')) is int else 'reader_evidence_missing'
        raise RecoveryError(409, '代理有使用者或读者证据不足，保持现状', reason)
    return detail


def _result(code, message, snapshot=None, **extra):
    result = {'code': code, 'msg': message}
    if snapshot:
        binding, equipment = snapshot['binding'], snapshot['equipment']
        result['data'] = dict(id=equipment['id'], binding_id=binding['id'],
                              app=binding['app'], stream=binding['live'], **extra)
    if code == 202:
        result['retry_after_ms'] = 1000
    return result


def recover_bound_preview(equipment_id, _services=None, _stalled=None, recheck_recorder=False):
    """Recover one enabled saved recorder or independent-camera binding."""
    created = False
    removed = False
    uncertain_mutation = False
    snapshot = None
    services = None
    try:
        equipment_id = _identity(equipment_id)
        services = _services or _Runtime()
        with services.locks(equipment_id):
            snapshot = services.snapshot(equipment_id)
            _validate(snapshot, recheck_recorder=recheck_recorder)
            binding = snapshot['binding']
            state = services.state(binding)
            if state['video']:
                result = _result(200, '该绑定已有视频转发，保持现状', snapshot, changed=False)
                result['reason'] = 'video_present'
                return result
            replacing = bool(state['proxy'])
            if replacing and not _stalled:
                result = _result(202, '已有代理正在连接，未重置或更换来源', snapshot, changed=False)
                result['reason'] = 'proxy_connecting'
                return result
            if replacing:
                _verify_stalled(binding, state, _stalled)

            candidate = binding['source']
            direct_camera = _is_direct_camera(snapshot)
            mode = 'camera' if direct_camera else 'recorder'
            evidence = services.probe(candidate)
            if replacing and evidence.get('video'):
                raise RecoveryError(409, '当前来源已有视频，保留代理等待恢复', 'source_video_present')
            if not evidence.get('video'):
                status = evidence.get('status')
                if status in (401, 403):
                    raise RecoveryError(409, '来源认证失败，请维护设备账号', 'source_auth_failed', status)
                if direct_camera or type(status) is not int or not 500 <= status <= 599:
                    raise RecoveryError(409, '当前来源未提供可验证视频，未自动更换来源', 'source_unavailable', status)
                if _canonical_source(candidate) != _canonical_source(snapshot['registered_nvr_source']):
                    raise RecoveryError(409, '旧来源与登记录像机通道不一致，未自动切换来源', 'registered_source_mismatch')
                candidate = services.direct_source(snapshot)
                _canonical_source(candidate)
                direct = services.probe(candidate)
                if not direct.get('video'):
                    if direct.get('status') in (401, 403):
                        raise RecoveryError(409, '摄像头直连认证失败，请维护设备账号', 'source_auth_failed', direct['status'])
                    raise RecoveryError(409, '已核对摄像头映射，但直连未提供视频，原绑定保持不变', 'direct_source_unavailable', direct.get('status'))
                mode = 'camera-direct'
            # Do not hold SQL row locks during network I/O. Recheck both saved
            # intent and runtime immediately before asking for a missing proxy.
            if _signature(services.snapshot(equipment_id)) != _signature(snapshot):
                raise RecoveryError(409, '设备或绑定已变化，请刷新后重试', 'configuration_changed')
            state = services.state(binding)
            if state['video']:
                return _result(200, '该绑定已恢复视频，保持现状', snapshot, changed=False)
            if state['proxy']:
                if not replacing:
                    result = _result(202, '其他操作已建立代理，未重置或更换来源', snapshot, changed=False)
                    result['reason'] = 'proxy_connecting'
                    return result
                old = _verify_stalled(binding, state, _stalled)
                uncertain_mutation = True
                deleted = services.remove(old['key'])
                if (not isinstance(deleted, dict) or deleted.get('code') != 0
                        or (deleted.get('data') or {}).get('flag') is not True):
                    raise RecoveryError(503, '定点重建未确认旧代理已移除，原配置保留', 'proxy_remove_unconfirmed')
                removed = True
                uncertain_mutation = False
                # A concurrent client may have created a proxy after removal.
                # Never replace that object or submit a DB update for it.
                state = services.state(binding)
                if state['video'] or state['proxy']:
                    raise RecoveryError(409, '其他操作已恢复代理，原配置保留待核对', 'proxy_changed_after_remove')
            elif replacing:
                raise RecoveryError(409, '旧代理身份已变化，取消定点重建', 'proxy_identity_changed')
            flags = {name: int(bool(binding['urls'].get(field))) for name, field in PROTOCOL_FIELDS}
            uncertain_mutation = True
            response = services.add(binding, candidate, flags)
            if not isinstance(response, dict) or response.get('code') != 0:
                if isinstance(response, dict) and type(response.get('code')) is int:
                    uncertain_mutation = False
                raise RecoveryError(409, '流媒体未确认转发恢复成功，原绑定保持不变', 'proxy_add_failed')
            created = True
            uncertain_mutation = False
            key = (response.get('data') or {}).get('key')
            if (not isinstance(key, str) or len(key) > 512 or any(ord(c) < 32 for c in key)
                    or len(key.rsplit('/', 2)) != 3
                    or key.rsplit('/', 2)[-2:] != [binding['app'], binding['live']]
                    or (direct_camera and key != binding['key'])):
                raise RecoveryError(503, '转发已创建但返回身份未确认，请检查流媒体状态')
            services.cas_update(snapshot, candidate, key)
            result = _result(202, '原绑定转发已恢复，正在等待视频', snapshot,
                             changed=True, source_mode=mode, pending_video=True)
            result['reason'] = 'waiting_video'
            return result
    except RecoveryError as exc:
        result = _result(exc.code, exc.message)
        result['reason'] = exc.reason
        if type(exc.status) is int and 400 <= exc.status <= 599:
            result['source_status'] = exc.status
    except Exception:
        result = _result(503, '绑定转发恢复未完成，请检查服务状态后重试')
        result['reason'] = 'service_unavailable'
    if created or removed or uncertain_mutation:
        # Never delete an existing/healthy proxy to compensate for a DB race.
        result['data'] = {'proxy_created': created, 'proxy_removed': removed, 'database_changed': False,
                          'mutation_unconfirmed': uncertain_mutation, 'requires_reconciliation': True}
    return result


class _Runtime:
    def __init__(self):
        from data.exts import db
        from model.equipment import Equipment, VCR_data
        from model.extra import Zlk_data
        from service import preview_source_service as source
        from config.zlk_conf import ZLK_HOST, stream_proxy_identities
        self.db, self.Equipment, self.Binding, self.VCR = db, Equipment, Zlk_data, VCR_data
        self.source, self.vhost, self.identities = source, str(ZLK_HOST), stream_proxy_identities

    @contextlib.contextmanager
    def global_lock(self):
        import fcntl
        with open(RECOVERY_LOCK, 'a+') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RecoveryError(202, '流媒体巡检或恢复正在执行，请稍后重试', 'lock_busy')
            yield

    @contextlib.contextmanager
    def locks(self, equipment_id):
        client = self.source._redis()
        token, key = uuid.uuid4().hex, self.source.PREFIX + 'lock:' + str(equipment_id)
        if not client.set(key, token, nx=True, ex=240):
            raise RecoveryError(202, '该设备正在建立转发，请稍后重试', 'lock_busy')
        try:
            with self.global_lock():
                yield
        finally:
            try:
                client.eval(self.source._RELEASE_LOCK, 1, key, token)
            except Exception:
                pass

    def _records(self, equipment_id, locked=False):
        session = self.db.session
        def row(model, identity):
            query = session.query(model).filter(model.id == identity)
            return (query.with_for_update() if locked else query).first()
        equipment = row(self.Equipment, equipment_id)
        if equipment is None:
            raise RecoveryError(404, '监控点不存在')
        binding = row(self.Binding, equipment.zlk_dat_id) if equipment.zlk_dat_id else None
        if binding is None:
            raise RecoveryError(409, '该设备没有可恢复的已有流媒体绑定')
        parent = row(self.Equipment, equipment.parent_id) if equipment.parent_id else None
        direct_camera = (equipment.equipment_type == '摄像头' and equipment.parent_id is None
                         and equipment.VCR_data_id is None)
        if parent is None and not direct_camera:
            raise RecoveryError(409, '该设备没有有效的录像机归属')
        vcr = row(self.VCR, parent.VCR_data_id) if parent and parent.VCR_data_id else None
        return equipment, binding, parent, vcr

    def _snapshot(self, records):
        equipment, binding, parent, vcr = records
        def values(row, fields):
            return {name: getattr(row, field, None) for name, field in fields}
        direct_camera = equipment.equipment_type == '摄像头' and equipment.parent_id is None
        snapshot = {
            'equipment': values(equipment, [('id', 'id'), ('enabled', 'user_status'), ('online', 'online'),
                ('type', 'equipment_type'), ('binding_id', 'zlk_dat_id'), ('parent_id', 'parent_id'),
                ('channel', 'equipment_aisles'), ('code', 'code'), ('ip', 'equipment_ip'),
                ('port', 'equipment_port'), ('username', 'equipment_uname'), ('password', 'equipment_password'),
                ('onvif', 'Onvif_rtsp_url')]),
            'binding': {'id': binding.id, 'owner': binding.equipment_id, 'app': binding.zlk_app,
                'live': binding.zlk_live, 'source': binding.cameras_rtsp, 'key': binding.zlk_key,
                'urls': {field: getattr(binding, field, None) for field in URL_FIELDS}},
            'parent': values(parent, [('id', 'id'), ('enabled', 'user_status'), ('online', 'online'),
                ('vendor', 'manufacturer_type'), ('ip', 'equipment_ip'), ('username', 'equipment_uname'),
                ('password', 'equipment_password'), ('vcr_id', 'VCR_data_id')]) if parent else None,
            'vcr': values(vcr, [('id', 'id'), ('ip', 'vcr_ip'), ('port', 'vcr_port'),
                ('username', 'vcr_username'), ('password', 'vcr_password')]) if vcr else None,
            'registered_nvr_source': None if direct_camera else self.source._registered_source(equipment, parent)}
        if direct_camera:
            # Use the same vendor-specific URL construction as normal camera
            # registration, including its credential escaping. No network I/O.
            from service.equipment_model_service import _get_rtsp_url_by_equipment_type
            snapshot['equipment'].update(vendor=equipment.manufacturer_type,
                                         vcr_id=equipment.VCR_data_id)
            snapshot['registered_camera_source'] = _get_rtsp_url_by_equipment_type(equipment)
        return snapshot

    def snapshot(self, equipment_id):
        self.db.session.rollback()
        try:
            return self._snapshot(self._records(equipment_id))
        finally:
            self.db.session.rollback()

    def state(self, binding):
        media = self.source._proxy_api('getMediaList', app=binding['app'], stream=binding['live'])
        if media.get('code') != 0 or not isinstance(media.get('data') or [], list):
            raise RecoveryError(503, '无法确认当前媒体状态，未修改转发')
        if _has_video(media.get('data') or [], binding['app'], binding['live']):
            return {'video': True, 'proxy': True}
        proxies = self.source._proxy_api('listStreamProxy')
        if proxies.get('code') != 0:
            raise RecoveryError(503, '无法确认当前代理状态，未修改转发')
        detail = _proxy_detail(proxies.get('data'), media.get('data') or [], binding['app'], binding['live'])
        return {'video': False, 'proxy': detail is not None, 'proxy_detail': detail}

    probe = staticmethod(_probe_source)

    def direct_source(self, expected):
        self.db.session.rollback()
        try:
            records = self._records(expected['equipment']['id'])
            if _signature(self._snapshot(records)) != _signature(expected):
                raise RecoveryError(409, '设备接入信息已变化，未自动切换来源')
            try:
                return self.source._registered_direct_source(records[0], records[2])
            except self.source.CompatError as exc:
                status = getattr(exc, 'source_status', None)
                if status in (401, 403):
                    raise RecoveryError(409, '设备认证失败，请维护设备账号', 'source_auth_failed', status)
                raise RecoveryError(409, '无法核对录像机与摄像头映射，原绑定保持不变', 'mapping_unconfirmed')
        finally:
            self.db.session.rollback()

    def add(self, binding, source, flags):
        return self.source._proxy_api('addStreamProxy', vhost=self.vhost,
            app=binding['app'], stream=binding['live'], url=source,
            rtp_type=0, timeout_sec=8, retry_count=3, **flags)

    def remove(self, key):
        return self.source._proxy_api('delStreamProxy', key=key)

    def cas_update(self, expected, source, key):
        from sqlalchemy import text
        session = self.db.session
        session.rollback()
        try:
            records = self._records(expected['equipment']['id'], locked=True)
            current = self._snapshot(records)
            # The caller validated the initial snapshot under its online policy.
            # The signature below checks any intervening status or identity change.
            _validate(current, recheck_recorder=True)
            if _signature(current) != _signature(expected):
                raise RecoveryError(409, '设备或绑定已变化；新代理保留待核对，旧配置未覆盖')
            if _is_direct_camera(current):
                # Independent-camera recovery restores runtime only. It cannot
                # adopt a changed source/key or write saved device metadata.
                if source != current['binding']['source'] or key != current['binding']['key']:
                    raise RecoveryError(409, '直连来源或转发身份已变化，原配置保持不变',
                                        'configuration_changed')
                session.rollback()
                return
            # Explicit SQL changes only these two fields; ORM onupdate values,
            # ownership, protocol flags and all playback URLs remain untouched.
            result = session.execute(text('UPDATE t_zlk_data SET cameras_rtsp=:source, zlk_key=:key WHERE id=:id'),
                {'source': source, 'key': key, 'id': expected['binding']['id']})
            if result.rowcount not in (0, 1):
                raise RecoveryError(409, '绑定更新数量异常，未提交更改')
            session.commit()
        except Exception:
            session.rollback()
            raise
