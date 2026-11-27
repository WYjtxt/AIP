"""Shared Redis admission state; never stops or migrates running work."""
import ast
from contextlib import ExitStack
from contextvars import ContextVar
from functools import wraps
import json
import logging
import math
from pathlib import Path
import time
import uuid

from service.resource_admission_policy import advance, percentage, policy_config, view, budget, warmup_seconds

PREFIX = 'v1:resource_admission:'
logger = logging.getLogger(__name__)
_BATCH = ContextVar('resource_admission_batch', default=None)


def batch_guard(function):
    """Share only this server-side batch's reservation; retain per-item checks."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _BATCH.set(uuid.uuid4().hex)
        try:
            return function(*args, **kwargs)
        finally:
            _BATCH.reset(token)
    return wrapped


def _pending(redis, host, rules):
    key = PREFIX + 'pending:' + str(host)
    raw = redis.get(key)
    if not raw:
        return None
    ttl = redis.ttl(key)
    if ttl == -2:
        return None
    try:
        item = json.loads(raw)
    except (ValueError, TypeError):
        item = {}
    remaining = max(1, int(ttl)) if ttl >= 0 else None
    return {'raw': raw, 'ttl': ttl, 'data': item,
            'phase': 'loading' if item.get('phase') == 'loading' else 'observing',
            'configured_seconds': int(rules['reservation_seconds']),
            'effective_seconds': warmup_seconds(rules), 'remaining_seconds': remaining,
            'reserved_cpu': max(0, float(item.get('request_cpu', 0) or 0))}


def _resume_entries(redis, host, now=None):
    now = time.time() if now is None else now
    data = _read(redis, PREFIX + 'resume_cpu:' + str(host))
    return [item for item in data.get('items', []) if item.get('expires_at', 0) > now]


def _resident_resume(current):
    try:
        from service.resource_residency import is_resident_resume
        return is_resident_resume(current) is True
    except Exception:
        # A missing/stale proof follows the normal cold-start admission path.
        return False


def _stopped_save(kind, payload, current):
    models = payload.get('model_data')
    items = models if isinstance(models, list) and models else [payload]
    if kind == 'create':
        return all(str(item.get('status')) in ('2', '停止') for item in items)
    if kind == 'update' and current is not None and str(current.status) == '2':
        return all(str(item.get('status', current.status)) in ('2', '停止') for item in items)
    return False


def _replace_reservation(redis, key, expected, replacement=None, ttl=0):
    return redis.eval("if redis.call('get',KEYS[1]) == ARGV[1] then "
                      "if tonumber(ARGV[3]) > 0 then return redis.call('setex',KEYS[1],ARGV[3],ARGV[2]) "
                      "else return redis.call('del',KEYS[1]) end end return 0",
                      1, key, expected, replacement or '', max(0, int(ttl)))


def seed_policy():
    return policy_config(json.loads((Path(__file__).resolve().parents[1] / 'config/resource-admission.json').read_text()))


def policy():
    from service.resource_admission_settings import effective_policy
    return effective_policy(seed_policy())


def client():
    from service.resource_view_service import _host_metrics_client
    return _host_metrics_client()


def _read(redis, key):
    raw = redis.get(key)
    return json.loads(raw) if raw else {}


def _runtime_identity(report):
    if not report or not report.get('generation') or not report.get('worker_pid'):
        return None
    return [report['generation'], report['worker_pid'], report.get('task_epoch')]


def _start_observation(prior, config_id, resource_ids):
    from service.algorithm_runtime_status import read_report_snapshot

    # A merged batch may include a legacy operation whose runtime is untracked.
    if prior is not None and not prior.get('start_tasks'):
        return {}
    snapshot = read_report_snapshot()
    if snapshot is None:
        return {}
    report = snapshot[1].get(str(config_id))
    identity = _runtime_identity(report)
    if report is not None and identity is None:
        return {}
    tasks = dict(prior['start_tasks']) if prior else {}
    tasks[str(config_id)] = identity
    previous_cards = prior['start_cards'] if prior else []
    return {'start_tasks': tasks, 'start_cards': sorted(set(previous_cards + resource_ids))}


def _ready_observation(host, reservation, now):
    from sqlalchemy import text
    from data.exts import db
    from service.algorithm_runtime_status import read_report_snapshot

    snapshot = read_report_snapshot(now=now)
    if snapshot is None or snapshot[0] <= reservation['completed_at']:
        return None
    epoch, reports = snapshot
    tasks = reservation['start_tasks']
    identities = {}
    for task_id, previous in tasks.items():
        report = reports.get(task_id)
        identity = _runtime_identity(report)
        if identity is None or identity == previous or report.get('healthy') is not True:
            return None
        identities[task_id] = identity + [report.get('session')]

    params = {'task'+str(i): int(task_id) for i, task_id in enumerate(tasks)}
    bindings = ','.join(':'+name for name in params)
    # The collector's ORM transaction may already have an earlier DB snapshot.
    # Use an independent committed read, without taking task locks.
    with db.engine.connect() as connection:
        rows = connection.execute(text('SELECT id FROM t_algorithm_config WHERE id IN ('+bindings+') '
            'AND computing_id=:host AND status=1 AND conf_status=1 AND model_status=1'),
            dict(params, host=host)).fetchall()
    if {str(row[0]) for row in rows} != set(tasks):
        return None
    previous = reservation.get('ready') or {}
    return previous if previous.get('identities') == identities else {'at': epoch, 'identities': identities}


def _observe_start_load(redis, host, pending, state, cpu_started_at, now, rules):
    if not pending or pending['phase'] != 'observing' or not pending['data'].get('start_tasks'):
        return
    reservation = pending['data']
    ready = _ready_observation(host, reservation, now)
    release = False
    if ready and now - reservation['completed_at'] >= rules['reservation_seconds']:
        cards = view(state, now, rules)['cards']
        aliases = state.get('card_aliases', {})
        start_cards = {aliases.get(card, card) for card in reservation['start_cards']}
        release = (state.get('cpu_at') is not None and cpu_started_at > ready['at'] and all(
            not cards.get(card, {}).get('disabled', True) and
            cards[card]['sampled_at'] > ready['at'] and state['cards'][card].get('token')
            for card in start_cards))
    if not release and reservation.get('ready') == ready:
        return
    # The collector never waits behind a start or holds task locks here. Check
    # ownership again since another accepted request can replace this reservation.
    lock = redis.lock(PREFIX + 'deploy:' + host, timeout=120, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return
    try:
        key = PREFIX + 'pending:' + host
        if release:
            _replace_reservation(redis, key, pending['raw'])
        else:
            value = json.dumps(dict(reservation, ready=ready))
            redis.eval("if redis.call('get',KEYS[1]) == ARGV[1] then "
                       "local ttl=redis.call('pttl',KEYS[1]); "
                       "if ttl > 0 then return redis.call('psetex',KEYS[1],ttl,ARGV[2]) end end return 0",
                       1, key, pending['raw'], value)
    finally:
        lock.release()


def collect():
    from data.exts import db
    from data.resource_view_data import ResourceViewData
    from model.equipment import Computing_equipment
    from service.computing_identity_service import binding_map
    from service.resource_view_service import _current_resource_slots, _sample_host_metrics, _publish_host_metrics
    redis = client()
    # All Gunicorn workers may register APScheduler; only one samples at a time.
    with redis.lock(PREFIX + 'collector', timeout=90, blocking_timeout=0.1):
        hosts = db.session.query(Computing_equipment).filter(Computing_equipment.server_type == 1).all()
        bindings = binding_map() if hosts else {}
        rules = policy()
        for host in hosts:
            host_id = str(host.id)
            binding = bindings.get(host.id)
            pending = _pending(redis, host_id, rules)
            cpu_started_at = time.time()
            metrics = _sample_host_metrics(host, binding)
            _publish_host_metrics(host, metrics, binding)
            rows = ResourceViewData.get_resource_usage_by_computing_id(host.id)
            now = time.time()
            cpu = percentage(metrics.get('cpu_usage'))
            cards = []
            aliases = {}
            for row, _, related_ids in _current_resource_slots(rows):
                age = float(row['sample_age']) if row['sample_age'] is not None else None
                cards.append({'id': row['id'], 'dev_id': row['dev_id'], 'util': row['tpu_util'],
                              'memory': row['memory_usage_rate'], 'target': row['dev_get_target'],
                              'board_temperature': row['board_temp'], 'chip_temperature': row['chip_temp'],
                              'token': str(row['sample_token']) if row['sample_token'] else None,
                              'sampled_at': now - age if age is not None and age >= 0 else None})
                aliases.update({str(rid): str(row['id']) for rid in related_ids if rid != row['id']})
            key = PREFIX + 'host:' + host_id
            sample = {'cpu': cpu, 'cpu_at': now if cpu is not None else None,
                      'cpu_token': metrics.get('host_metrics_sampled_at') if cpu is not None else None, 'cards': cards}
            state = advance(_read(redis, key), sample, now, rules)
            state['computing_id'] = host.id
            state['card_aliases'] = aliases
            redis.setex(key, 86400, json.dumps(state))
            try:
                _observe_start_load(redis, host_id, pending, state, cpu_started_at, now, rules)
            except Exception:
                logger.warning('Post-start observation evidence unavailable for host %s', host_id, exc_info=True)


def snapshot(ignore_pending_hosts=()):
    from data.exts import db
    from model.equipment import Resource_usage
    rules = policy()
    now = time.time()
    redis = client()
    resources = db.session.query(Resource_usage.id, Resource_usage.computing_id).all()
    hosts, cards, aliases = {}, {}, {}
    for resource in resources:
        host_id = str(resource.computing_id)
        if host_id not in hosts:
            state = _read(redis, PREFIX + 'host:' + host_id)
            pending = _pending(redis, host_id, rules)
            hosts[host_id] = view(state, now, rules, bool(pending) and host_id not in ignore_pending_hosts)
            aliases[host_id] = (state or {}).get('card_aliases', {})
            if pending:
                hosts[host_id]['observation'] = {key: pending[key] for key in
                    ('phase', 'configured_seconds', 'effective_seconds', 'remaining_seconds')}
            hosts[host_id]['reserved_cpu'] = ((pending['reserved_cpu'] if pending else 0) +
                sum(float(item['cost']) for item in _resume_entries(redis, host_id, now)))
        card_id = str(resource.id)
        canonical = aliases[host_id].get(card_id, card_id)
        status = hosts[host_id]['cards'].get(canonical, {'disabled': True,
            'state': 'unknown', 'reason': '正在采集资源状态，请稍后重试', 'utilization': None, 'sampled_at': None})
        cards[str(resource.id)] = dict(status, computing_id=resource.computing_id,
            canonical_resource_id=int(canonical),
            cpu=hosts[host_id]['cpu'], cpu_warning=hosts[host_id]['cpu_warning'], cpu_warning_threshold=rules['cpu_warning'])
        observation = hosts[host_id].get('observation')
        if observation:
            cards[str(resource.id)]['observation'] = observation
            if status.get('reason') == '新增部署后的负载观察中，请稍后重试':
                remaining = observation['remaining_seconds']
                message = ('新增算法正在加载，资源预留约 {} 秒后复核' if observation['phase'] == 'loading' else
                           '新增部署后的负载观察中，约 {} 秒后可重试')
                cards[str(resource.id)].update(admission_reason='load_observation',
                    retry_after_seconds=remaining,
                    reason=message.format(remaining) if remaining is not None else '新增部署正在观察，请等待资源状态复核')
    for host_id, host in hosts.items():
        host['computing_id'] = host_id
        host['physical_board_count'] = None
        host['topology_note'] = '按采集到的计算芯片调度；物理卡归属尚未上报，不按芯片数量推算卡数'
        host['warmup_seconds'] = warmup_seconds(rules)
        host['configured_warmup_seconds'] = int(rules['reservation_seconds'])
    for resource_id, status in cards.items():
        ratios = [status['cpu'] / rules['cpu_budget_limit'] if status['cpu'] is not None else 2,
                  status['utilization'] / rules['card_limit'] if status['utilization'] is not None else 2,
                  status.get('memory_utilization', 100) / rules['memory_limit'] if status.get('memory_utilization') is not None else 2]
        status['selection_score'] = round(max(ratios) * 100 + sum(ratios), 3)
        status['cpu_budget_limit'] = rules['cpu_budget_limit']
        status['cpu_task_reserve'] = rules['cpu_task_reserve']
        status['chip_count'] = hosts[str(status['computing_id'])]['chip_count']
    return {'sampled_at': now, 'policy': rules, 'cards': cards, 'hosts': hosts, 'strategy': 'host_chip_budget_v2'}


def attach(resources):
    try:
        status = snapshot()['cards']
    except Exception:
        logger.warning('Resource admission snapshot unavailable', exc_info=False)
        status = {}
    for host in resources:
        for group in host.get('grouped_resources', {}).values():
            for card in group:
                card['admission'] = status.get(str(card['id']), {'disabled': True, 'state': 'unknown',
                    'reason': '资源状态暂不可用，暂停新增部署', 'utilization': None})
    return resources


def canonical(value):
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in ('', 'none', 'null', 'undefined', 'legacy'):
            return None
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            if value.startswith(('[', '{', '(')):
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    pass
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items() if k != 'resource_id_old'}
    return value


ALIASES = {'equipment_name': 'Equipment_id', 'test_type_id': 'Algorithm_test_type_id',
           'img_resolution': 'conf_img_resolution'}
IGNORED = {'id', 'resource_id_old', 'conf_name', 'Algorithm_config_ps'}


def metadata_only(payload, current):
    # Only the two explicitly harmless fields can bypass admission. Every
    # other supplied value must agree with persisted data, not resource_id_old.
    if current is None or payload.get('model_data'):
        return False
    for name, value in payload.items():
        if name in IGNORED:
            continue
        field = ALIASES.get(name, name)
        if not hasattr(current, field):
            if canonical(value) not in (None, 0, [], {}):
                return False
            continue
        if canonical(value) != canonical(getattr(current, field)):
            return False
    return True


def _metadata_save(payload, current):
    from data.exts import db
    from model.algorithm import Algorithm_config
    from data.algorithm_model_data import insert_algorithm_config_history_from_config
    name = payload.get('conf_name', current.conf_name)
    if not name:
        return {'code': 400, 'msg': '请填写任务名称'}
    duplicate = db.session.query(Algorithm_config.id).filter(Algorithm_config.conf_name == name,
                                                           Algorithm_config.id != current.id).first()
    if duplicate:
        return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
    current.conf_name = name
    if 'Algorithm_config_ps' in payload:
        current.Algorithm_config_ps = payload['Algorithm_config_ps']
    db.session.commit()
    insert_algorithm_config_history_from_config(current, '修改')
    return {'code': 200, 'msg': '名称与备注已保存，运行配置保持不变'}


def save_metadata(payload):
    from data.exts import db
    from model.algorithm import Algorithm_config
    if not isinstance(payload, dict) or set(payload) - {'id', 'conf_name', 'Algorithm_config_ps'}:
        return {'code': 400, 'msg': '此接口仅允许修改任务名称和备注'}
    if not str(payload.get('id')).isdigit():
        return {'code': 400, 'msg': '任务ID无效'}
    current = db.session.query(Algorithm_config).filter(Algorithm_config.id == int(payload['id'])).with_for_update().first()
    if current is None:
        return {'code': 404, 'msg': '算法配置不存在'}
    return _metadata_save(payload, current)


def _resource_ids(payload, current=None):
    items = payload.get('model_data')
    if items is not None:
        if not isinstance(items, list) or not items or any(not isinstance(item, dict) for item in items):
            raise ValueError('缺少有效的算法模型参数')
        return [item.get('resource_id') for item in items]
    if current is not None and 'resource_id' not in payload:
        ids = []
        for item in canonical(current.model_algo_data_ori) or []:
            if not isinstance(item, dict) or not item.get('resource_id'):
                raise ValueError('原任务的模型资源信息不完整，请重新配置')
            ids.append(item['resource_id'])
        if not any(str(item) == str(current.resource_id) for item in ids):
            ids.append(current.resource_id)
        return ids
    return [payload.get('resource_id')]


def guard(kind, reserve_warmup=True):
    def decorate(function):
        @wraps(function)
        def wrapped(payload):
            from data.exts import db
            from model.algorithm import Algorithm_config
            from model.algorithm import Algorithm_library
            from service.algorithm_config_safety import lock_configuration_libraries, ConfigurationConflict
            from model.equipment import Resource_usage
            if not isinstance(payload, dict) and not hasattr(payload, 'get'):
                return {'code': 400, 'msg': '任务参数无效'}
            current = None
            try:
                if kind in ('update', 'start'):
                    config_id = payload.get('id')
                    if not str(config_id).isdigit():
                        return {'code': 400, 'msg': '任务ID无效'}
                    current = db.session.query(Algorithm_config).filter(Algorithm_config.id == int(config_id)).first()
                    if current is None:
                        return {'code': 404, 'msg': '算法配置不存在'}
                if kind == 'start':
                    desired = {'运行': 1, '停止': 2, '1': 1, '2': 2}.get(str(payload.get('status')))
                    if desired != 1:
                        return function(payload)  # Stops are always permitted.
                    lock_configuration_libraries(db.session, Algorithm_library, payload, current, starting=True)
                    current = db.session.query(Algorithm_config).filter(Algorithm_config.id == int(config_id)).populate_existing().with_for_update().first()
                    if current is None:
                        return {'code': 404, 'msg': '算法配置不存在'}
                    # A concurrent editor may have changed the referenced
                    # libraries before this row lock was acquired.
                    lock_configuration_libraries(db.session, Algorithm_library, payload, current, starting=True)
                    if str(current.status) == '1':
                        from model.algorithm import Algorithm_library
                        from service.algorithm_stream_selection import prepare_stream_type
                        library = db.session.query(Algorithm_library).filter(Algorithm_library.id == current.Algorithm_library_id).with_for_update().first()
                        if library is None or str(library.algorithm_status) != '1':
                            db.session.rollback()
                            return {'code': 409, 'msg': '算法包已停止或不存在，请先启用算法包；任务状态保持不变'}
                        prepare_stream_type({'stream_type': getattr(current, 'stream_type', None)}, current.Equipment_id, config_id=current.id)
                        db.session.rollback()
                        return {'code': 200, 'msg': '任务已设置运行，保持现有状态与配置处理进度'}
                if kind == 'update' and metadata_only(payload, current):
                    return _metadata_save(payload, current)
                ids = _resource_ids(payload, current if kind == 'start' else None)
                if any(isinstance(item, bool) or not str(item).isdigit() or int(item) < 1 for item in ids):
                    raise ValueError('请选择有效的算力资源卡')
                requested_ids = list(map(int, ids))  # Preserve batch/model multiplicity for CPU budgeting.
                ids = list(dict.fromkeys(requested_ids))
                resources = db.session.query(Resource_usage).filter(Resource_usage.id.in_(ids)).all()
                if len(resources) != len(ids):
                    raise ValueError('算力资源不存在，请刷新后重新选择')
                # Validate the host/card relationship rather than trusting a
                # client-supplied host id or the previous resource id.
                items = payload.get('model_data') or [payload]
                lookup = {r.id: r for r in resources}
                for item in items:
                    host = item.get('computing_id')
                    if host is not None and str(host) != str(lookup[int(item.get('resource_id', ids[0]))].computing_id):
                        raise ValueError('所选算力卡与主机不匹配，请重新选择')
                hosts = sorted(set(str(resource.computing_id) for resource in resources))
                if kind != 'start':
                    lock_configuration_libraries(db.session, Algorithm_library, payload, current)
                    if current is not None:
                        current = db.session.query(Algorithm_config).filter(Algorithm_config.id == int(current.id)).populate_existing().with_for_update().first()
                # Saving stopped configuration cannot add running load. This
                # decision uses the locked DB row, never resource_id_old or a
                # client-supplied assertion about the task's current status.
                if _stopped_save(kind, payload, current):
                    return function(payload)
                resident = kind == 'start' and _resident_resume(current)
                redis = client()
                with ExitStack() as stack:
                    for host in hosts:
                        stack.enter_context(redis.lock(PREFIX + 'deploy:' + host, timeout=120, blocking_timeout=1))
                    rules = policy()
                    pending = {host: _pending(redis, host, rules) for host in hosts}
                    own_batch = {host for host, item in pending.items() if item and _BATCH.get() and
                                 item['data'].get('batch_token') == _BATCH.get()}
                    current_snapshot = snapshot(ignore_pending_hosts=set(hosts) if resident else own_batch)
                    states = current_snapshot['cards']
                    for resource in resources:
                        state = states.get(str(resource.id), {})
                        if state.get('disabled', True):
                            return {'code': 409, 'msg': state.get('reason') or '资源状态未知，暂停新增部署', 'admission_blocked': True,
                                    'admission_reason': state.get('admission_reason'),
                                    'retry_after_seconds': state.get('retry_after_seconds'),
                                    'observation': state.get('observation')}
                    # A brief shared reservation covers model loading and new
                    # measurements. Parallel and batch requests cannot all use
                    # the same pre-deployment sample to admit more work.
                    reservations = {}
                    for host in hosts:
                        units = sum(str(lookup[item].computing_id) == host for item in requested_ids)
                        decision = budget(current_snapshot['hosts'][host]['cpu'], units, rules,
                                          reserved=current_snapshot['hosts'][host]['reserved_cpu'])
                        if not decision['allowed']:
                            return {'code': 409, 'msg': decision['reason'], 'admission_blocked': True,
                                    'cpu_budget': decision}
                        now = time.time()
                        if resident:
                            # Resident work has no model-loading window, but its
                            # resumed inference still consumes CPU. Keep a short
                            # cumulative budget until observations catch up.
                            key = PREFIX + 'resume_cpu:' + host
                            prior = redis.get(key)
                            entries = _resume_entries(redis, host, now)
                            entries.append({'token': uuid.uuid4().hex, 'cost': decision['request_cpu'],
                                            'expires_at': now + warmup_seconds(rules)})
                            value = json.dumps({'items': entries})
                            ttl = max(1, math.ceil(max(item['expires_at'] for item in entries) - now))
                        else:
                            key = PREFIX + 'pending:' + host
                            prior = pending[host]['raw'] if pending[host] else None
                            prior_cost = pending[host]['reserved_cpu'] if pending[host] else 0
                            value = json.dumps(dict(decision, request_cpu=prior_cost + decision['request_cpu'],
                                token=uuid.uuid4().hex, batch_token=_BATCH.get(), phase='loading', created_at=now))
                            ttl = max(240, warmup_seconds(rules))
                        observation = {}
                        if kind == 'start' and not resident:
                            observation = _start_observation(pending[host]['data'] if pending[host] else None,
                                current.id, [str(item) for item in ids if str(lookup[item].computing_id) == host])
                        reservations[host] = dict(key=key, raw=value, prior=prior, observation=observation,
                            prior_ttl=redis.ttl(key) if prior else 0, started=now, ttl=ttl)
                    # Reserve every host before any mutation. reserve_warmup=False
                    # remains accepted for old callers, but an active mutation
                    # cannot suppress protection by setting that argument.
                    for reservation in reservations.values():
                        redis.setex(reservation['key'], reservation['ttl'], reservation['raw'])
                    result = function(payload)
                    body = result if isinstance(result, dict) else result.get_json(silent=True) if hasattr(result, 'get_json') else None
                    for host, reservation in reservations.items():
                        # Do not overwrite a newer owner's reservation if a slow
                        # request outlived its lease. Exceptions retain protection.
                        success = not isinstance(body, dict) or str(body.get('code')) == '200'
                        if success and not resident:
                            completed = dict(json.loads(reservation['raw']), phase='observing', completed_at=time.time())
                            completed.update(reservation['observation'])
                            _replace_reservation(redis, reservation['key'], reservation['raw'],
                                                 json.dumps(completed), warmup_seconds(rules))
                        elif not success:
                            # A later failed item must not erase this batch's
                            # earlier successful reservations.
                            ttl = max(0, reservation['prior_ttl'] - math.ceil(time.time() - reservation['started']))
                            _replace_reservation(redis, reservation['key'], reservation['raw'], reservation['prior'], ttl)
                    return result
            except ConfigurationConflict as error:
                db.session.rollback()
                return {'code': 409, 'msg': str(error)}
            except ValueError as error:
                db.session.rollback()
                return {'code': 400, 'msg': str(error)}
            except Exception:
                db.session.rollback()
                logger.warning('Resource admission check unavailable', exc_info=True)
                return {'code': 409, 'msg': '资源状态校验暂不可用或有部署正在处理，请稍后重试', 'admission_blocked': True}
        return wrapped
    return decorate

# algorithm-first-stopped-admission-v1
# resource-admission-task-aware-v2
