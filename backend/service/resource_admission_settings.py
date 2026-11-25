"""Validated, revision-checked settings shared by the UI and admission checks."""
from datetime import datetime, timezone
import json
import threading

from flask import has_app_context
from sqlalchemy.exc import IntegrityError, OperationalError

from data.exts import db
from model.resource_admission_settings import ResourceAdmissionSettings
from service.resource_admission_policy import policy_config

EDITABLE = ('cpu_warning', 'cpu_warning_recovery', 'cpu_limit', 'cpu_recovery',
            'card_limit', 'card_recovery', 'memory_limit', 'memory_recovery',
            'cpu_budget_limit', 'cpu_task_reserve',
            'trigger_seconds', 'recovery_seconds', 'reservation_seconds')
_LOCK = threading.Lock()
_ENGINES = set()


class SettingsConflict(ValueError):
    pass


def validate_changes(changes, seed):
    if not isinstance(changes, dict) or set(changes) != set(EDITABLE):
        raise ValueError('调度配置已更新，请刷新页面后完整填写阈值和时间设置')
    if any(type(changes[key]) is not int for key in EDITABLE):
        raise ValueError('阈值和时间均须填写整数')
    for key in EDITABLE[:8]:
        if not 0 <= changes[key] <= 100:
            raise ValueError('利用率阈值必须在 0–100% 之间')
        if key.endswith('_recovery') and changes[key] == 0:
            raise ValueError('恢复阈值须大于 0%，以便资源在低负载时解除保护')
    labels = [('cpu_warning_recovery', 'cpu_warning', 'CPU 提醒'),
              ('cpu_recovery', 'cpu_limit', 'CPU 暂停部署'),
              ('card_recovery', 'card_limit', '计算芯片保护'),
              ('memory_recovery', 'memory_limit', '芯片内存保护')]
    for recovery, limit, label in labels:
        if changes[recovery] >= changes[limit]:
            raise ValueError(label + '的恢复阈值须低于触发阈值')
    if changes['cpu_warning'] >= changes['cpu_limit']:
        raise ValueError('CPU 提醒阈值须低于暂停部署阈值')
    if not 1 <= changes['cpu_task_reserve'] <= changes['cpu_budget_limit'] <= changes['cpu_limit']:
        raise ValueError('单任务 CPU 预留须大于 0，且不高于预算上限；预算上限不得高于 CPU 暂停阈值')
    for key, minimum, maximum, label in (
        ('trigger_seconds', 10, 300, '超限持续时间'),
        ('recovery_seconds', 10, 600, '恢复持续时间'),
        ('reservation_seconds', 5, 120, '部署观察时间')):
        if not minimum <= changes[key] <= maximum:
            raise ValueError('{}须在 {}–{} 秒之间'.format(label, minimum, maximum))
    return policy_config(dict(seed, **changes))


def ensure_table():
    engine = db.engine
    if engine not in _ENGINES:
        with _LOCK:
            if engine not in _ENGINES:
                try:
                    ResourceAdmissionSettings.__table__.create(engine, checkfirst=True)
                except Exception:
                    from sqlalchemy import inspect
                    if not inspect(engine).has_table(ResourceAdmissionSettings.__tablename__):
                        raise
                _ENGINES.add(engine)


def _row(connection, locked=False):
    query = ResourceAdmissionSettings.__table__.select().where(ResourceAdmissionSettings.id == 1)
    if locked:
        query = query.with_for_update()
    result = connection.execute(query).first()
    if result is None:
        return None
    return dict(result._mapping) if hasattr(result, '_mapping') else dict(result)


def _result(row, seed):
    return {'policy': policy_config(json.loads(row['policy_json'])) if row else dict(seed),
            'defaults': dict(seed), 'revision': row['revision'] if row else 0,
            'updated_at': row['updated_at'].isoformat() + 'Z' if row else None,
            'updated_by': row['updated_by'] if row else None,
            'editable_fields': list(EDITABLE), 'strategy': 'host_chip_budget_v2'}


def read_settings(seed):
    ensure_table()
    with db.engine.connect() as connection:
        return _result(_row(connection), seed)


def effective_policy(seed):
    # The scheduler registration phase has no application context. Its fixed
    # sampling cadence remains in the seed; runtime decisions read shared DB.
    return read_settings(seed)['policy'] if has_app_context() else seed


def save_settings(changes, expected_revision, actor, seed):
    candidate = validate_changes(changes, seed)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('配置版本无效，请重新读取当前配置')
    ensure_table()
    table = ResourceAdmissionSettings.__table__
    try:
        with db.engine.begin() as connection:
            row = _row(connection, locked=True)
            if expected_revision != (row['revision'] if row else 0):
                raise SettingsConflict('配置已被其他管理员更新，请重新读取后再保存')
            if row and policy_config(json.loads(row['policy_json'])) == candidate:
                return _result(row, seed)
            values = {'policy_json': json.dumps(candidate, sort_keys=True),
                      'revision': expected_revision + 1, 'updated_at': datetime.now(timezone.utc).replace(tzinfo=None), 'updated_by': actor}
            if row:
                result = connection.execute(table.update().where(table.c.id == 1).where(table.c.revision == expected_revision).values(**values))
                if result.rowcount != 1:
                    raise SettingsConflict('配置已更新，请重新读取后再保存')
            else:
                connection.execute(table.insert().values(id=1, **values))
            saved = dict(values, id=1)
        return _result(saved, seed)
    except (IntegrityError, OperationalError):
        raise SettingsConflict('配置正在更新，请重新读取后再保存')
