"""Present saved passage calibration without changing inference configuration."""
import json
import math
from functools import wraps
from pathlib import Path

STATE = Path('/data/AIGO/platform_start/platform_ops/state/uniqueness')
ZONES = {'entry': ('入口区', '#16a34a'), 'gate': ('闸内区', '#d69e00'),
         'exit': ('出口区', '#0891d1'), 'obstacle': ('阻挡区', '#ef4444')}


def region_polygons(cfg, equipment_id, resolution):
    if not isinstance(cfg, dict) or cfg.get('calibrated') is not True:
        return []
    if str(cfg.get('equipment_id')) != str(equipment_id):
        return []
    try:
        width, height = [int(v) for v in resolution.lower().split('x')]
        if not (0 < width <= 32768 and 0 < height <= 32768):
            return []
    except (AttributeError, TypeError, ValueError):
        return []
    if cfg.get('kind') == 'tailgating':
        names = ['entry', 'gate']
        if cfg.get('passage_confirmation', 'exit') == 'exit':
            names.append('exit')
    elif cfg.get('kind') == 'crossing':
        names = ['obstacle'] if cfg.get('crossing_confirmation', 'landing') == 'obstacle' else ['entry', 'exit', 'obstacle']
    else:
        return []
    polygons = []
    for name in names:
        points = cfg.get(name)
        if not isinstance(points, list) or not 3 <= len(points) <= 32:
            return []
        if any(not isinstance(p, list) or len(p) != 2 or
               any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in p)
               for p in points):
            return []
        label, color = ZONES[name]
        polygons.append([{'x': x * width, 'y': y * height, 'type': label, 'color': color}
                         for x, y in points])
    return polygons


def with_passage_regions(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        result = function(*args, **kwargs)
        if not isinstance(result, dict) or result.get('code') != 200:
            return result
        for row in result.get('data_list', {}).get('data', []):
            name = row.get('algorithm_name', '')
            if not any(part in name for part in ('人员尾随', '违规跨越', '唯一性尾随')):
                continue
            row['conf_area'] = '[]'
            row['analysis_region_status'] = '未标定'
            try:
                task_id = int(row['id'])
                cfg = json.loads((STATE / ('config-%d.json' % task_id)).read_text(encoding='utf-8'))
                polygons = region_polygons(cfg, row.get('Equipment_id'), row.get('img_resolution'))
                if polygons:
                    row['conf_area'] = json.dumps(polygons, ensure_ascii=False)
                    row['analysis_region_status'] = '已标定'
                    row['analysis_region_labels'] = [p[0]['type'] for p in polygons]
            except (KeyError, ValueError, TypeError, OSError):
                pass
        return result
    return wrapped
