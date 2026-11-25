"""Data-only config parsing and transactional algorithm-library references."""
import ast
import json
import math


class ConfigurationConflict(ValueError):
    pass


def literal_data(value):
    """Accept JSON and historic Python literals, never executable expressions."""
    if not isinstance(value, str):
        return value
    if len(value) > 1048576:
        raise ValueError('算法参数过长')
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            raise ValueError('算法参数必须是有效的 JSON 或数据字面量')


def alarm_interval(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('告警间隔须为 1 至 3600 秒的整数')
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            raise ValueError('告警间隔须为 1 至 3600 秒的整数')
        value = int(value)
    if not 1 <= value <= 3600:
        raise ValueError('告警间隔须为 1 至 3600 秒的整数')
    return value


def model_roi(value):
    """Validate the existing nested drawing shape without changing coordinates."""
    value = literal_data(value)
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError('算法区域必须是坐标分组数组')
    count = 0
    for group in value:
        if not isinstance(group, list):
            raise ValueError('算法区域必须是坐标分组数组')
        count += len(group)
        if count > 10000:
            raise ValueError('算法区域坐标数量过多')
        if group and (not isinstance(group[0], dict) or 'type' not in group[0]):
            raise ValueError('算法区域缺少类型')
        for point in group:
            if not isinstance(point, dict):
                raise ValueError('算法区域坐标必须是对象')
            for axis in ('x', 'y'):
                raw = point.get(axis)
                if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                    raise ValueError('算法区域坐标必须是有限数值')
                try:
                    number = float(raw)
                except (TypeError, ValueError, OverflowError):
                    raise ValueError('算法区域坐标必须是有限数值')
                if not math.isfinite(number) or not 0 <= number <= 1000000:
                    raise ValueError('算法区域坐标必须在有效范围内')
    return value


def _field(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _identity(value, required=False):
    if value in (None, '', 'None', 'null', 0, '0') and not isinstance(value, bool) and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        raise ValueError('算法包引用无效')
    number = int(value)
    if not 1 <= number <= 2147483647:
        raise ValueError('算法包引用无效')
    return number


def library_references(config):
    """Read direct, cascade and both historic advanced representations."""
    ids, paths = set(), set()
    for field in ('Algorithm_library_id', 'model_two_type'):
        value = _identity(_field(config, field))
        if value is not None:
            ids.add(value)
    for field in ('model_algo_data_ori', 'model_algo_data'):
        raw = _field(config, field)
        if raw in (None, ''):
            continue
        models = literal_data(raw)
        if models is None:
            continue  # Historical unset JSON null / Python None.
        if not isinstance(models, list) or any(not isinstance(item, dict) for item in models):
            raise ValueError('高级算法配置无法解析，请先修复配置再删除算法包')
        for model in models:
            value = _identity(model.get('Algorithm_library_id'))
            if value is not None:
                ids.add(value)
            path = model.get('algorithm_path') or model.get('model_path')
            if path:
                if not isinstance(path, str):
                    raise ValueError('高级算法模型路径无效')
                paths.add(path)
    raw = _field(config, 'model_two_data')
    if raw not in (None, ''):
        cascade = literal_data(raw)
        # Both a dict and list[dict] have been persisted by the platform.
        # Non-cascade tasks may hold an empty-path record, [] or null/None.
        cascades = [] if cascade is None else [cascade] if isinstance(cascade, dict) else cascade
        if not isinstance(cascades, list) or any(not isinstance(item, dict) for item in cascades):
            raise ValueError('级联算法配置无法解析，请先修复配置再删除算法包')
        for model in cascades:
            value = _identity(model.get('Algorithm_library_id'))
            if value is not None:
                ids.add(value)
            path = model.get('model_path') or model.get('algorithm_path')
            if path and path != '模型路径':
                if not isinstance(path, str):
                    raise ValueError('级联算法模型路径无效')
                paths.add(path)
    return ids, paths


def lock_configuration_libraries(session, library_model, payload, current=None, starting=False):
    """Use the same row locks as deletion, before a config can gain references."""
    if starting:
        ids, _paths = library_references(current)
    else:
        models = payload.get('model_data')
        if models is not None:
            if not isinstance(models, list) or not models or any(not isinstance(model, dict) for model in models):
                raise ValueError('缺少有效的算法模型参数')
        else:
            models = [payload]
        ids = set()
        for model in models:
            primary = model.get('Algorithm_library_id', _field(current, 'Algorithm_library_id'))
            ids.add(_identity(primary, required=True))
            cascade = _identity(model.get('model_two_type'))
            if cascade is not None:
                ids.add(cascade)
    if not ids:
        raise ValueError('请选择有效的算法包')
    rows = session.query(library_model).filter(library_model.id.in_(sorted(ids))).order_by(
        library_model.id).populate_existing().with_for_update().all()
    if {row.id for row in rows} != ids:
        raise ValueError('算法包不存在或已删除，请刷新后重新选择')
    if starting and any(str(row.algorithm_status) != '1' for row in rows):
        raise ConfigurationConflict('任务引用的算法包已停止，请先启用算法包')
    return rows


def delete_library_records(session, library_model, config_model, queue_model, requested):
    """Commit the complete parent/child set once; return only safe file paths."""
    if not isinstance(requested, list) or not requested or len(requested) > 100:
        raise ValueError('请选择 1 至 100 个算法包')
    ids = set(_identity(value, required=True) for value in requested)
    try:
        # A current read locks model rows in one stable order. Configuration
        # creates/updates lock their model rows before persisting references.
        libraries = session.query(library_model).order_by(library_model.id).populate_existing().with_for_update().all()
        chosen = [row for row in libraries if row.id in ids]
        if len(chosen) != len(ids):
            raise ConfigurationConflict('部分算法包已不存在，请刷新后重试')
        parent_types = {row.analysis_type for row in chosen
                        if row.analysis_type and str(row.algorithm_child) != '2'}
        ids.update(row.id for row in libraries if str(row.algorithm_child) == '2' and row.analysis_type in parent_types)
        removed = [row for row in libraries if row.id in ids]
        paths = {row.algorithm_path for row in removed if row.algorithm_path}
        configs = session.query(config_model).order_by(config_model.id).populate_existing().with_for_update().all()
        direct = []
        for config in configs:
            referenced_ids, referenced_paths = library_references(config)
            if not (ids.intersection(referenced_ids) or paths.intersection(referenced_paths)):
                continue
            if config.Algorithm_library_id not in ids:
                raise ConfigurationConflict('算法包被高级组合或级联任务引用，请先修改或删除引用任务')
            if str(config.status) != '2' or str(config.model_status) != '4':
                raise ConfigurationConflict('请先停止引用算法包的任务，并等待停止确认后再删除')
            direct.append(config.id)
        if direct:
            session.query(config_model).filter(config_model.id.in_(direct)).delete(synchronize_session=False)
        existing = {row.algorithm_id for row in session.query(queue_model).filter(queue_model.algorithm_id.in_(sorted(ids))).all()}
        for identity in sorted(ids - existing):
            session.add(queue_model(algorithm_id=identity))
        session.query(library_model).filter(library_model.id.in_(sorted(ids))).delete(synchronize_session=False)
        # Never remove a model file still shared by another library/config.
        shared = {row.algorithm_path for row in libraries if row.id not in ids and row.algorithm_path}
        for config in configs:
            if config.id not in direct:
                shared.update(library_references(config)[1])
        session.commit()
        return {'deleted_library_ids': sorted(ids), 'deleted_config_ids': sorted(direct),
                'file_paths': sorted(paths - shared)}
    except Exception:
        session.rollback()
        raise
