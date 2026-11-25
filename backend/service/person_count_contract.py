"""Validate explicit people-count scenes without migrating legacy geometry."""
import ast
import json
import math
import re
from numbers import Real

try:
    from .count_algorithm_family import is_count_model_name
except ImportError:
    from count_algorithm_family import is_count_model_name


def _decode(raw):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(raw)
        except (ValueError, TypeError, SyntaxError):
            # Old tasks can contain other representations. They are not migrated
            # implicitly, but malformed new scene configurations must not be saved.
            if 'scene' in raw:
                raise ValueError('人数统计场景参数必须是有效的 JSON 对象')
            return None


def _point(raw, image_size=None):
    if not isinstance(raw, dict):
        raise ValueError('人数统计坐标必须包含 x、y')
    values = []
    for axis in ('x', 'y'):
        value = raw.get(axis)
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError('人数统计坐标必须是有限数值')
        if not math.isfinite(value):
            raise ValueError('人数统计坐标必须是有限数值')
        if value < 0 or value > 1000000:
            raise ValueError('人数统计坐标须在 0 至 1000000 之间')
        if image_size and value > image_size[len(values)]:
            raise ValueError('人数统计坐标不能超出原始图像分辨率，请重新绘制')
        # Inference consumes integer pixel coordinates. Validate geometry after
        # applying that same conversion so fractional vertices cannot collapse
        # only when the worker starts. Raw bounds are checked before truncation.
        values.append(int(value))
    return {'x': values[0], 'y': values[1]}


def _cross(a, b, c):
    return ((b['x'] - a['x']) * (c['y'] - a['y']) -
            (b['y'] - a['y']) * (c['x'] - a['x']))


def _on_segment(a, b, c):
    return (_cross(a, b, c) == 0 and
            min(a['x'], b['x']) <= c['x'] <= max(a['x'], b['x']) and
            min(a['y'], b['y']) <= c['y'] <= max(a['y'], b['y']))


def _intersects(a, b, c, d):
    ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
    cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
    if ((ab_c > 0 > ab_d or ab_d > 0 > ab_c) and
            (cd_a > 0 > cd_b or cd_b > 0 > cd_a)):
        return True
    return (_on_segment(a, b, c) or _on_segment(a, b, d) or
            _on_segment(c, d, a) or _on_segment(c, d, b))


def _image_size(resolution):
    if isinstance(resolution, str):
        match = re.match(r'^\s*(\d+)\s*[xX×*,]\s*(\d+)\s*$', resolution)
        if match:
            width, height = map(int, match.groups())
            if width > 0 and height > 0:
                return width, height
    elif isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        if all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in resolution):
            return tuple(resolution)
    return None


def normalize_cross_line_area(raw, image_resolution=None):
    """Return a storage-safe JSON string for explicit scenes; preserve old input.

    There is deliberately no conf_area fallback: boarding requires its own
    validated polygon. Counts are runtime outputs and are never changed here.
    """
    config = _decode(raw)
    if not isinstance(config, dict) or 'scene' not in config:
        return json.dumps(raw, ensure_ascii=False) if isinstance(raw, (dict, list)) else raw

    scene = config.get('scene')
    if scene not in ('uniqueness', 'boarding'):
        raise ValueError('人数统计场景仅支持唯一性检测装置或乘车点')
    expected = 'polygon' if scene == 'boarding' else 'line'
    area_type = config.get('area_type', expected)
    if area_type != expected:
        raise ValueError('乘车点须使用多边形区域，唯一性检测装置须使用计数线')
    direction = config.get('direction', 'left')
    if direction not in ('left', 'right'):
        raise ValueError('人数统计进入方向仅支持 left 或 right')
    frames = config.get('min_residence_frames', 3)
    if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= 120:
        raise ValueError('最少连续检测帧数须为 1 至 120 的整数')

    raw_points = config.get('points')
    if raw_points is None and scene == 'uniqueness':
        raw_points = [config.get('p1'), config.get('p2')]
    if not isinstance(raw_points, (list, tuple)):
        raise ValueError('请绘制人数统计计数线或乘车点区域')
    if len(raw_points) > (65 if area_type == 'polygon' else 64):
        raise ValueError('人数统计区域最多支持 64 个顶点')
    size = _image_size(image_resolution)
    points = [_point(point, size) for point in raw_points]
    if area_type == 'polygon' and len(points) > 1 and points[0] == points[-1]:
        points.pop()
    minimum = 3 if area_type == 'polygon' else 2
    if not minimum <= len(points) <= 64:
        raise ValueError('人数统计计数线需 2 至 64 个点，乘车点区域需 3 至 64 个点')
    if len({(point['x'], point['y']) for point in points}) != len(points):
        raise ValueError('人数统计区域不能包含重复顶点')

    if area_type == 'polygon':
        twice_area = sum(point['x'] * points[(index + 1) % len(points)]['y'] -
                         points[(index + 1) % len(points)]['x'] * point['y']
                         for index, point in enumerate(points))
        if not math.isfinite(twice_area) or twice_area == 0:
            raise ValueError('乘车点区域不能共线或面积为零')
        for index, a in enumerate(points):
            b = points[(index + 1) % len(points)]
            # Adjacent backtracking edges overlap and do not form a polygon.
            c = points[(index + 2) % len(points)]
            if _cross(a, b, c) == 0 and (_on_segment(a, b, c) or _on_segment(b, c, a)):
                raise ValueError('乘车点区域的边不能重叠')
            for other in range(index + 1, len(points)):
                if other == index + 1 or (index == 0 and other == len(points) - 1):
                    continue
                if _intersects(a, b, points[other], points[(other + 1) % len(points)]):
                    raise ValueError('乘车点区域不能自相交')

    result = dict(config)
    result.update(scene=scene, area_type=area_type, direction=direction,
                  min_residence_frames=frames, points=points)
    # Keep the existing two-point consumer shape as well as the full polyline.
    result['p1'], result['p2'] = points[0], points[-1]
    return json.dumps(result, ensure_ascii=False, allow_nan=False)


def _normalize_count_model(model, template, default_resolution=None):
    item = dict(model)
    area = _decode(item.get('cross_line_area'))
    template_type = getattr(template, 'model_template_config_type_id', None)
    people_template = (not isinstance(template_type, bool) and str(template_type) == '3' and
                       is_count_model_name(getattr(template, 'model_name', '')))
    if isinstance(area, dict) and 'scene' in area and not people_template:
        raise ValueError('人数统计场景仅可用于人数统计模板')
    if 'cross_line_area' in item:
        resolution = item.get('img_resolution') or item.get('conf_img_resolution') or default_resolution
        item['cross_line_area'] = normalize_cross_line_area(item['cross_line_area'], resolution)
    # This value comes from the same server template row used by the inference
    # loader for the primary model. Never trust a submitted template type.
    item['template_config_type_id'] = template_type
    item['template_id'] = getattr(template, 'id', None)
    item['template_name'] = getattr(template, 'model_name', '')
    return item


def normalize_count_config(payload, template_lookup):
    """Validate a single-model save only when it opts into a new scene."""
    item = dict(payload)
    area = _decode(item.get('cross_line_area'))
    if isinstance(area, dict) and 'scene' in area:
        return _normalize_count_model(item, template_lookup(item.get('model_template_config_id')))
    if 'cross_line_area' in item:
        item['cross_line_area'] = normalize_cross_line_area(item['cross_line_area'])
    return item


def normalize_count_models(models, template_lookup):
    """Copy and validate every advanced model before any database operation."""
    if not isinstance(models, list) or not models or any(not isinstance(item, dict) for item in models):
        raise ValueError('缺少有效的算法模型参数')
    normalized = []
    count_models = 0
    default_resolution = models[0].get('img_resolution') or models[0].get('conf_img_resolution')
    for model in models:
        item = _normalize_count_model(model, template_lookup(model.get('model_template_config_id')), default_resolution)
        if (not isinstance(item['template_config_type_id'], bool) and str(item['template_config_type_id']) == '3' and
                is_count_model_name(item['template_name'])):
            count_models += 1
        if count_models > 1:
            raise ValueError('同一高级配置最多支持一个人数统计算法，请分别创建任务')
        normalized.append(item)
    return normalized
