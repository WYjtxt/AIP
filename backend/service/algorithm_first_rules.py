"""Data-only rules for the algorithm-first camera selection workflow."""
import ast
from decimal import Decimal, InvalidOperation
import json
import math
import os
import re

try:
    from .count_algorithm_family import (FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME,
                                         is_count_model_name, algorithm_display_name)
except ImportError:
    from count_algorithm_family import (FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME,
                                         is_count_model_name, algorithm_display_name)


class WorkflowError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status
        self.safe_to_repreview = False


def field(row, name, default=None):
    return row.get(name, default) if isinstance(row, dict) else getattr(row, name, default)


def identity(value, title='编号'):
    if isinstance(value, bool) or not str(value).isdigit() or not 0 < int(value) < 2147483648:
        raise WorkflowError(title + '无效')
    return int(value)


def literal(value):
    if value in (None, '', 'None', 'null'):
        return None
    if not isinstance(value, str):
        return value
    if len(value) > 1048576:
        raise WorkflowError('已有算法配置参数过长，请先检查原任务')
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            raise WorkflowError('已有高级算法配置无法解析，请先检查原任务')


def default_detection_type(library_id, tests):
    """Match the legacy new-form defaults, excluding other packages' labels."""
    library_id = identity(library_id, '算法')
    matches = [row for row in tests if str(field(row, 'Algorithm_library_id')) == str(library_id)
               and isinstance(field(row, 'test_type_ename'), str) and field(row, 'test_type_ename').strip()]
    matches.sort(key=lambda row: identity(field(row, 'id'), '检测类型'))
    if not matches:
        raise WorkflowError('算法包缺少有效检测类型，请先完善算法包', 409)
    first = matches[0]
    return {'test_type_id': identity(field(first, 'id'), '检测类型'),
            'label_list': list(dict.fromkeys(field(row, 'test_type_ename') for row in matches))}


def detection_setup(config, tests):
    try:
        library_id = identity(field(config, 'Algorithm_library_id'), '算法')
        matching = [row for row in tests if str(field(row, 'Algorithm_library_id')) == str(library_id)]
        ids = {identity(field(row, 'id'), '检测类型') for row in matching}
        names = {field(row, 'test_type_ename') for row in matching
                 if isinstance(field(row, 'test_type_ename'), str) and field(row, 'test_type_ename').strip()}
        selected = identity(field(config, 'Algorithm_test_type_id', field(config, 'test_type_id')), '检测类型')
        labels = literal(field(config, 'label_list'))
        if selected not in ids or not isinstance(labels, list) or not labels or any(
                not isinstance(label, str) or label not in names for label in labels):
            raise WorkflowError('请选择有效检测类型')
        return []
    except (WorkflowError, ValueError, TypeError):
        return ['与算法匹配的检测类型']


def library_ids(config):
    result = set()
    primary = field(config, 'Algorithm_library_id')
    if primary not in (None, ''):
        result.add(identity(primary, '算法'))
    for name in ('model_algo_data_ori', 'model_algo_data'):
        data = literal(field(config, name))
        if data is None:
            continue
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise WorkflowError('已有高级算法配置结构异常，请先检查原任务')
        for item in data:
            value = item.get('Algorithm_library_id')
            if value not in (None, ''):
                result.add(identity(value, '算法'))
    extra = field(config, 'model_two_type')
    if extra not in (None, '', 0, '0', 'None', 'null'):
        result.add(identity(extra, '级联算法'))
    return result


def requested_libraries(payload):
    items = payload.get('model_data')
    if items is None:
        items = [payload]
    if not isinstance(items, list) or not items or any(not isinstance(item, dict) for item in items):
        raise WorkflowError('请选择有效算法')
    ids = [identity(item.get('Algorithm_library_id'), '算法') for item in items]
    if len(ids) != len(set(ids)):
        raise WorkflowError('同一摄像机不能重复添加相同算法')
    for item in items:
        cascade = item.get('model_two_type')
        if cascade not in (None, '', 0, '0', 'None', 'null'):
            child = identity(cascade, '级联算法')
            if child in ids:
                raise WorkflowError('同一摄像机不能重复添加相同算法')
            ids.append(child)
    return set(ids)


def edit_path(config):
    if str(field(config, 'multimodels_type', 0)) == '1':
        return '/sfgl'
    return '/sfgl_child?conf_id=' + str(identity(field(config, 'id'), '任务'))


def geometry_requirement(library, template):
    type_id = int(field(template, 'model_template_config_type_id', 0) or 0)
    name = str(field(template, 'model_name', '') or field(library, 'model_name', ''))
    people = type_id == 3 and is_count_model_name(name)
    specialized = {'人员尾随': 'tailgating', '唯一性尾随': 'tailgating',
                   '违规跨越': 'crossing', '唯一性违规跨越': 'crossing'}.get(name.strip()) if type_id == 4 else None
    # A camera's geometry is deliberately never copied to another camera.
    return {'requires_geometry': type_id != 1,
            'geometry_kind': specialized or ('count_scene' if people else 'per_camera' if type_id != 1 else 'optional_roi'),
            'should_confirm_geometry': people or type_id != 1,
            'message': ('请逐摄像机标定入口区、闸内区；可选择出口确认模式' if specialized == 'tailgating' else
                        '请逐摄像机标定实际阻挡物，选择越障动作或异侧落地确认模式' if specialized == 'crossing' else
                        '请逐摄像机确认人数统计场景、计数线或乘车点区域及进出方向' if people else
                        '请逐摄像机确认检测区域及场景参数' if type_id != 1 else
                        '默认全画面检测，可在继续配置中调整区域')}


def default_name(camera, library):
    suffix = '-' + str(identity(field(camera, 'id'), '摄像机'))
    camera_name = str(field(camera, 'equipment_name', '') or '摄像机').strip()
    algorithm_name = display_name(library)
    if algorithm_name in (FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME):
        suffix = '-' + algorithm_name + suffix
        return camera_name[:32 - len(suffix)] + suffix
    return '{}-{}'.format(camera_name, algorithm_name)[:32 - len(suffix)] + suffix


def display_name(library):
    return algorithm_display_name(field(library, 'algorithm_name'), field(library, 'model_name'),
                                  '算法 #' + str(field(library, 'id', '')), field(library, 'analysis_type'))


def default_count_parameters(library, template, small=None):
    """Use the existing scalar template value; never copy per-camera geometry.

    300 is the deployed count editor's compatibility value. It is not a claim
    that the current inference engine consumes this legacy parameter.
    """
    if geometry_requirement(library, template)['geometry_kind'] != 'count_scene':
        return None
    for definition in (field(small, 'list_data'), field(template, 'model_conf_list')):
        try:
            values = literal(definition)
        except WorkflowError:
            continue
        rows = values if isinstance(values, list) else [values] if isinstance(values, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get('value') if row.get('key') == '上报时长' else row.get('上报时长')
            if isinstance(value, list):
                value = value[0] if value else None
            try:
                if isinstance(value, bool):
                    continue
                number = float(value)
                if math.isfinite(number) and number > 0:
                    return [{'上报时长': format(number, '.10g')}]
            except (ValueError, TypeError):
                continue
    return [{'上报时长': '300'}]


def setup_status(config, template, scene_validator=None, roi_validator=None, calibration_validator=None):
    """Derive setup from saved parameters; task run/stop status is irrelevant."""
    missing = []
    for name, label in (('Equipment_id', '摄像机'), ('Mine_id', '所属单位'),
                        ('Algorithm_library_id', '算法'), ('resource_id', '算力卡'),
                        ('computing_id', '分析服务器'), ('model_template_config_id', '算法模板')):
        try:
            identity(field(config, name), label)
        except WorkflowError:
            missing.append(label)
    try:
        if isinstance(field(config, 'confidence'), bool):
            raise ValueError()
        confidence = float(field(config, 'confidence'))
        if not math.isfinite(confidence) or not 0 <= confidence <= 100:
            raise ValueError()
    except (ValueError, TypeError):
        missing.append('置信度')
    for name, label, maximum in (('interval_time', '告警间隔', 3600), ('sensitivity', '间隔帧', 300)):
        value = field(config, name)
        if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= maximum:
            missing.append(label)
    match = re.fullmatch(r'\s*(\d+)\s*[xX×*,]\s*(\d+)\s*', str(field(config, 'conf_img_resolution', '') or ''))
    size = tuple(map(int, match.groups())) if match else None
    if not size or min(size) <= 0:
        missing.append('原始图像分辨率')
        size = None
    if template is None:
        missing.append('算法模板')
    requirement = geometry_requirement({}, template)
    try:
        region = literal(field(config, 'conf_area')) or []
        if roi_validator is not None:
            region = roi_validator(region)
        if not isinstance(region, list):
            raise ValueError()
        for group in region:
            if not isinstance(group, list):
                raise ValueError()
            for point in group:
                if not isinstance(point, dict):
                    raise ValueError()
                x, y = float(point.get('x')), float(point.get('y'))
                if (not math.isfinite(x) or not math.isfinite(y) or min(x, y) < 0
                        or size and (x > size[0] or y > size[1])):
                    raise ValueError()
    except (WorkflowError, ValueError, TypeError):
        region = []
        missing.append('有效检测区域')
    if requirement['geometry_kind'] == 'count_scene':
        try:
            scene = literal(field(config, 'cross_line_area'))
            if not isinstance(scene, dict) or scene.get('scene') not in ('uniqueness', 'boarding'):
                raise ValueError()
            if scene['scene'] == 'uniqueness' and scene.get('direction') not in ('left', 'right'):
                raise ValueError()
            if scene['scene'] == 'boarding' and scene.get('boarding_direction') not in ('inward', 'outward'):
                raise ValueError()
            points = scene.get('points') or ([scene.get('p1'), scene.get('p2')] if scene['scene'] == 'uniqueness' else None)
            if not isinstance(points, list) or len(points) < (3 if scene['scene'] == 'boarding' else 2):
                raise ValueError()
            if scene_validator is not None:
                scene_validator(scene, field(config, 'conf_img_resolution'))
            else:
                coordinates = [(float(point['x']), float(point['y'])) for point in points]
                if len(set(coordinates)) != len(coordinates) or any(not math.isfinite(v) for point in coordinates for v in point):
                    raise ValueError()
        except (WorkflowError, ValueError, TypeError, KeyError):
            missing.append('人数统计场景、计数线或乘车点区域及进出方向')
    elif requirement['geometry_kind'] in ('tailgating', 'crossing'):
        try:
            if calibration_validator is None:
                raise ValueError(requirement['message'])
            calibration_validator(config)
        except (ValueError, TypeError, OSError) as error:
            missing.append(str(error)[:180] or requirement['message'])
    elif requirement['requires_geometry'] and not region:
        missing.append('逐摄像机检测区域')
    try:
        values = literal(field(config, 'template_data'))
        parameters = {}
        if isinstance(values, dict):
            parameters.update(values)
        elif isinstance(values, list):
            for value in values:
                if isinstance(value, dict):
                    parameters.update(value)
        elif values is not None:
            raise ValueError()
        if requirement['geometry_kind'] == 'count_scene':
            report_seconds = float(parameters.get('上报时长'))
            if not math.isfinite(report_seconds) or report_seconds <= 0:
                missing.append('上报时长')
        configured = literal(field(template, 'model_conf_list'))
        for entry in configured if isinstance(configured, list) else []:
            if isinstance(entry, dict) and entry.get('required') is True:
                key = entry.get('key') or entry.get('name')
                if key and parameters.get(key) in (None, ''):
                    missing.append(str(key))
    except (WorkflowError, ValueError, TypeError):
        missing.append('逐摄像机场景参数')
    missing = list(dict.fromkeys(missing))
    return {'setup_complete': not missing, 'needs_setup': bool(missing), 'setup_missing': missing,
            'setup_message': '已完成逐摄像机配置' if not missing else '请先完成：' + '、'.join(missing)}


def compatible(library, resource):
    target = re.sub(r'[^a-z0-9]', '', str(field(resource, 'dev_get_target', '') or '').lower())
    path = str(field(library, 'algorithm_path', '') or '').lower()
    extension = os.path.splitext(path)[1]
    if extension == '.om':
        family = 'ascend'
    elif extension == '.bmodel':
        family = 'sophon'
    elif extension == '.rknn':
        family = 'rockchip'
    else:
        family = {'1': 'cambricon', '2': 'sophon', '3': 'ascend'}.get(str(field(library, 'algorithm_trade_type', '')))
    actual = ('ascend' if 'ascend' in target or 'huawei' in target else
              'sophon' if 'bm168' in target or 'sophon' in target else
              'rockchip' if 'rk35' in target or 'rockchip' in target else
              'cambricon' if 'mlu' in target or 'cambricon' in target else None)
    if not family or actual != family:
        return False
    # Same-family chip variants are not interchangeable when explicitly named.
    pattern = {'ascend': r'ascend\d+[a-z0-9]*', 'sophon': r'bm\d+[a-z0-9]*',
               'rockchip': r'rk\d+[a-z0-9]*', 'cambricon': r'mlu\d+[a-z0-9]*'}[family]
    chips = re.findall(pattern, os.path.basename(path))
    return not chips or any(chip in target for chip in chips)


def scalar_options(options):
    allowed = {'template_id', 'resource_id', 'confidence', 'interval_time', 'interval_frames', 'stream_type'}
    if not isinstance(options, dict) or set(options) - allowed:
        raise WorkflowError('参数包含不支持的字段，请重新预览')
    result = dict(options)
    for key in ('template_id', 'resource_id'):
        if result.get(key) not in (None, ''):
            result[key] = identity(result[key], key)
    confidence = result.get('confidence', 0.6)
    if isinstance(confidence, bool):
        raise WorkflowError('置信度须为 0 至 1')
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        raise WorkflowError('置信度须为 0 至 1')
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise WorkflowError('置信度须为 0 至 1')
    try:
        precise = Decimal(str(result.get('confidence', 0.6)))
        if precise != precise.quantize(Decimal('0.01')):
            raise WorkflowError('置信度最多保留两位小数')
    except InvalidOperation:
        raise WorkflowError('置信度须为 0 至 1')
    result['confidence'] = confidence
    interval = result.get('interval_time', 2)
    if isinstance(interval, bool) or not str(interval).isdigit() or not 1 <= int(interval) <= 3600:
        raise WorkflowError('告警间隔须为 1 至 3600 秒的整数')
    result['interval_time'] = int(interval)
    frames = result.get('interval_frames', 2)
    if isinstance(frames, bool) or not str(frames).isdigit() or not 1 <= int(frames) <= 300:
        raise WorkflowError('间隔帧须为 1 至 300 的整数')
    result['interval_frames'] = int(frames)
    choice = result.get('stream_type', 'legacy')
    if choice in (None, ''):
        choice = 'legacy'
    if choice not in ('legacy', 'main', 'sub'):
        raise WorkflowError('码流仅支持沿用原地址、主码流或子码流')
    result['stream_type'] = choice
    return result


def selection(body):
    if not isinstance(body, dict) or set(body) - {'algorithm_id', 'camera_ids', 'options', 'overrides'}:
        raise WorkflowError('请求参数无效')
    algorithm_id = identity(body.get('algorithm_id'), '算法')
    cameras = body.get('camera_ids')
    if not isinstance(cameras, list) or not 1 <= len(cameras) <= 50:
        raise WorkflowError('每次请选择 1 至 50 个摄像机通道')
    cameras = [identity(value, '摄像机') for value in cameras]
    if len(cameras) != len(set(cameras)):
        raise WorkflowError('摄像机选择重复')
    overrides = body.get('overrides', [])
    if not isinstance(overrides, list) or len(overrides) > len(cameras):
        raise WorkflowError('逐摄像机参数无效')
    seen, prepared = set(), []
    for item in overrides:
        if not isinstance(item, dict) or set(item) - {'equipment_id', 'conf_name', 'resource_id', 'template_id', 'confidence', 'interval_time', 'interval_frames', 'stream_type'}:
            raise WorkflowError('逐摄像机参数包含不支持的字段')
        camera_id = identity(item.get('equipment_id'), '摄像机')
        if camera_id not in cameras or camera_id in seen:
            raise WorkflowError('逐摄像机参数与当前选择不一致')
        seen.add(camera_id)
        entry = dict(item)
        if 'conf_name' in entry:
            name = entry['conf_name']
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 32 or any(ord(c) < 32 for c in name):
                raise WorkflowError('任务名称须为 1 至 32 个字符')
            entry['conf_name'] = name.strip()
        prepared.append(entry)
    return {'algorithm_id': algorithm_id, 'camera_ids': cameras,
            'options': scalar_options(body.get('options', {})), 'overrides': prepared}
