# boarding-direction-v1
# sophon-boarding-direction-v1
# coding:utf-8
'''
人数统计 / 过线计数模板（PersonCount）—— 仅【后处理】

取流 + 推理 + 推流 模块调用templates/rtsp_infer_push.py（支持一路流多模型并行）执行。本文件只保留
人数统计相关的【后处理】：过线计数 + 多目标跟踪(Re-ID) + 会话上报 + 计数面板/越线叠加，
以及人数统计专属的配置解析（cross_line_area / 阈值 / 类别列表）与越线（判定线 + IN/OUT 箭头）绘制。

  1) build_spec(...)：把数据库参数整理成 model_spec(含 on_result) + 流参数提示；
  2) on_result：① 喂跟踪器做过线计数（依赖帧间时序，引擎已保证按 seq 顺序、不丢帧）；
                ② 在共享推流帧上叠加报警区域常显 / 越线方向 / 计数面板（检测框由引擎统一绘制）；
                ③ 会话结束（无进出超时）后把存图+上报丢给独立线程，不阻塞热路径；
  3) method(...)：单任务入口（一路流一模型 + 推流），兼容旧调用方式。

results 格式：[[cls_id:int, '%.2f'%score:str, [xmin, ymin, xmax, ymax]], ...]
（按 category_id / obj_thresh 过滤；计数模板只跟踪/绘制这些类别）。

自 People_Counting05_1 移植的后处理模块：
  - 全局永久累计进出计数 + 「井下在岗总人数」三行统计面板（会话重置不清零）；
  - 会话时间语义：记录首次和末次计数确认帧，按空闲时间及录像缓存上限结算；
  - LOST 轨迹逐帧老化（修复旧版 LOST 轨迹 lost_frames 停在 1、永不删除的问题）；
  - 短时遮挡通过 Re-ID 恢复同一轨迹；过线依据同一轨迹在线两侧的实际检测点；
  - UWB 定位卡人数核验（多卡/漏卡异常追加告警；板端无 uwbb 模块时自动跳过）。
'''

from templates import alarm_directory
import os
import ast
import json
import time
import math
import re
import queue
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from config import common as cm
port = int(cm.upload_port)
# 统一引擎：取流 + 推理 + 推流，以及围绕 model_spec 的解析/绘制工具
from templates.rtsp_infer_push import (
    make_model_spec, build_stream_cfg, run,
    _parse_conf_area, _polygons_to_np, draw_alarm_regions,
    _get_pil_text_bitmap, _paste_text_bitmap_bgr,
    _DEFAULT_MASKS, _DEFAULT_ANCHORS,
)
from templates import alarm_video
from templates.count_model_profile import FullBodyCrossing, FullBodyLineSearch, VisualCrossing, count_model_profile
from templates.count_alarm_outbox import CountAlarmOutbox, count_alarm_payload
from templates.people_count_replica import CountReplica
from templates.count_session_media import CountSessionMedia

# ---- 会话上报依赖（板端部署环境模块；缺失时仅写日志，不影响推理/推流） ----
try:
    from comm import data_send
    from config import common as cm
    _UPLOAD_IP = cm.upload_ip
    _UPLOAD_PORT = int(cm.upload_port)
except Exception as _e:
    data_send = None
    _UPLOAD_IP, _UPLOAD_PORT = '127.0.0.1', 0
    print('[counting] comm/config 模块不可用，会话结果仅写日志不上传:', _e)

# ---- UWB 定位卡核验（板端可选模块，移植自 People_Counting05_1；缺失时自动跳过） ----
try:
    from templates.uwbb import get_uwb_continuous_distance_info as _uwb_check
except Exception:
    try:
        from uwbb import get_uwb_continuous_distance_info as _uwb_check
    except Exception:
        _uwb_check = None
        print('[counting] uwbb 模块不可用，跳过 UWB 定位卡人数核验')
_UWB_DB_PATH = '/ai/web_ai/ai_flask/uwb_data.db'   # 板端 UWB 定位数据库


# ======================================================================
# 跟踪容错参数：目标被遮挡或漏检后，用 Re-ID 尽量找回同一轨迹。
# 预测位置用于匹配检测框。实际检测点确认过线时，同步记录人数和画面证据。
# 帧数型参数按 ~8fps 标定，运行期在 CountingContext 里按实际推理帧率 fps_eff 等比缩放，
# 所以下文的"≈秒数"是 8fps 口径，改跳帧策略时时间语义不会漂移。
# ======================================================================
_LOST_WINDOW_FRAMES = 45        # LOST 轨迹保留帧数(8fps 基准≈5.6s)，窗口内可被 Re-ID 找回
_REID_MAX_DIST_PX = 420         # Re-ID 允许的脚底点位移上限(像素)：长距离找回
_REID_SCORE_THRESH = 0.35       # Re-ID 得分门槛：偏低=更容易找回，偏高=更防 ID 互换
_IOU_MATCH_THRESH = 0.22        # 连续帧 IoU 匹配门槛：偏低=更容忍快速移动/框抖动
_SESSION_TIMEOUT_SEC = 8        # 8s 无活跃轨迹则会话结束
_SESSION_MAX_SEC = 40           # 为约 60s 的视频缓存预留前后文、关键帧和处理时间
_MAX_VISIBLE_EVIDENCE_TRACKS = 32
_COUNT_LOG_INITED = False
_DEFAULT_PUSH_URL = 'rtsp://127.0.0.1:8554/stream99'


_CROWD_NEAR_GAP = 1.2           # 进保守档：任两目标脚底距 < 1.2×平均框高
_CROWD_FAR_GAP = 1.8            # 回强化档：任两目标脚底距 >= 1.8×平均框高（滞回带）
_CROWD_ALWAYS = 6               # 兜底：同屏目标数达到该值直接保守（设很大等同关闭）
_CROWD_SWITCH_FRAMES = 3        # 档位切换去抖：连续 N 帧同向才真正切换
_CROWDED_SCALE = {              # 拥挤档：相对基准的倍率
    'iou_thresh': 1.10,         # 匹配略严，减少相邻目标换框（不宜太高，否则快速移动会掉轨）
    'max_lost_frames': 0.5,     # 丢失记忆减半，尽快遗忘，防旧轨迹吸附新人
    'reid_max_dist': 0.5,       # 找回半径减半，禁跨目标长跳
    'reid_score_thresh': 1.2,   # 找回门槛提高，宁可不找回也不错配
}
_SPARSE_SCALE = {               # 稀疏档：相对基准的倍率
    'iou_thresh': 0.85,         # 匹配放宽，容忍快速移动/框抖动
    'max_lost_frames': 2.0,     # 丢失记忆翻倍，遮挡后仍能等回来
    'reid_max_dist': 1.5,       # 找回半径放大
    'reid_score_thresh': 0.8,   # 找回门槛降低，尽量找回同一 ID
}

# ======================================================================
# 只有来向有实测点越过防抖带才允许计数，抵达另一侧的第一帧立即记账。
_BAND_MARGIN_RATIO = 0.05
_BAND_MARGIN_MIN_PX = 2.0

# ======================================================================
# 轨迹预测：主匹配用预测框 + 匀速卡尔曼 + 马氏门控 + 窗口速度拟合
#   _KF_ACCEL_Q / _KF_MEAS_R：CV 模型的过程噪声(加速度方差)与量测噪声(像素方差)，
#       量测噪声取 25 对应检测框约 ±5px 的抖动。
#   _MAHA_GATE：Re-ID 的门控阈值，2 自由度卡方 99.9% 分位；不确定性随时间自动放大，
#       比原来的固定像素半径更合理（丢得越久，允许的偏差越大）。
#   _PRED_MATCH_MIN_SPEED：只有速度超过该值才把"预测框 IoU"并入主匹配——慢速/静止
#       目标用当前框已经够稳，引入预测只会增加人群里的错配面。
# ======================================================================
_KF_ACCEL_Q = 20.0
_KF_MEAS_R = 20.0
_MAHA_GATE = 13.8
_PRED_MATCH_MIN_SPEED = 3.0
# Re-ID 的运动学门：人不会瞬移。允许位移 = 目标自身尺度 + 丢失期间按已知速度可能走过的
# 距离（再放宽 50%）。没有它，低阈值 + 大找回半径会把远处的新目标错认成丢失者。
_REID_JUMP_BASE_PX = 45.0
_REID_JUMP_BODY_RATIO = 1.0
_REID_JUMP_TRAVEL_RATIO = 1.5


def _safe_int(v, default=0):
    '''把 DB 字段安全转 int：兼容 None/空串/字符串/数字，失败返回 default。'''
    if v is None or v == '':
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


_LEGACY_DEFAULT_MODEL = ('/ai/AIGO/python/bingxing_model/packages/'
                         '阳光三极_人头检测_基础检测类_基础检测_基础检测_yolov5s_int8_'
                         'rockchip_rk3588_V1.0_1_1_20250904_1.rknn')


def _ensure_count_logging():
    '''按天滚动日志（仅在启用计数的进程里执行一次）。
    注意：本模块常被外层 model_start 拉起，root logger 已被 model_start/引擎挂了 handler，
    所以不能用 "if not root.handlers" 来决定是否安装本模块 handler（会被跳过导致
    计数/人脸日志“看似没有输出”）；必须无条件把本模块文件 handler 挂到 root。'''
    global _COUNT_LOG_INITED
    if _COUNT_LOG_INITED:
        return
    _COUNT_LOG_INITED = True
    try:
        stem = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), stem)
        os.makedirs(log_dir, exist_ok=True)
        handler = TimedRotatingFileHandler(
            os.path.join(log_dir, stem + '.log'),
            when='midnight', interval=1, backupCount=30, encoding='utf-8', utc=False)
        handler.suffix = '%Y-%m-%d.log'
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root = logging.getLogger()
        root.setLevel(logging.INFO)   # 确保 INFO 级日志不被外层的高级别过滤
        # 无条件挂上本模块 handler（无论 root 是否已有 model_start/引擎的 handler），
        # 否则计数/人脸日志会写不进本模块日志文件，表现为“无日志输出”。
        root.addHandler(handler)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        print('[counting] 日志初始化失败，使用控制台日志:', e)


# ======================================================================
# 人数统计：配置字段解析 + 越线（判定线 / IN·OUT 方向箭头）绘制
# ======================================================================

def _validate_boarding_polygon(points):
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if not 3 <= len(points) <= 64 or len(set(points)) != len(points):
        raise ValueError('乘车点计数区域需要 3 到 64 个不同顶点')

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return (orient(a, b, p) == 0 and
                min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
                min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

    area = sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1]))
    if not area:
        raise ValueError('乘车点计数区域不能共线或面积为零')
    edges = list(zip(points, points[1:] + points[:1]))
    for i, (a, b) in enumerate(edges):
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
            if (((o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)) or
                    on_segment(a, b, c) or on_segment(a, b, d) or
                    on_segment(c, d, a) or on_segment(c, d, b)):
                raise ValueError('乘车点计数区域不能自相交')
    return points


def _boarding_inside(point, polygon):
    # Even-odd rule used by the ARM count_geometry arrow planner. A point on
    # the boundary belongs to the region, as with cv2.pointPolygonTest >= 0.
    x, y = point
    inside = False
    for index, (ax, ay) in enumerate(polygon):
        bx, by = polygon[(index + 1) % len(polygon)]
        if ((bx - ax) * (y - ay) == (by - ay) * (x - ax) and
                min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by)):
            return True
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def _boarding_arrow_plan(points, width, height):
    # Same edge and direction geometry as the ARM count_geometry planner.
    pairs = list(zip(points, points[1:] + points[:1]))
    sign = 1 if sum(a[0] * b[1] - b[0] * a[1] for a, b in pairs) > 0 else -1
    edges = [(math.hypot(b[0] - a[0], b[1] - a[1]), i, a, b)
             for i, (a, b) in enumerate(pairs)]
    arrow_length = max(30.0, min(sum(edge[0] for edge in edges) * .05, 140.0))
    margin = min(24.0, width * .04, height * .04)
    pixels = [tuple(int(round(value)) for value in point) for point in points]
    outline = {'kind': 'polygon', 'segments': list(zip(pixels, pixels[1:] + pixels[:1]))}
    fallback = None
    for length, _, a, b in sorted(edges, key=lambda edge: (-edge[0], edge[1])):
        normal = (-(b[1] - a[1]) / length * sign, (b[0] - a[0]) / length * sign)
        middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        arrow = arrow_length
        for _ in range(10):
            inward = tuple(m + n * arrow for m, n in zip(middle, normal))
            outward = tuple(m - n * arrow for m, n in zip(middle, normal))
            if _boarding_inside(inward, points) and not _boarding_inside(outward, points):
                pixel = lambda p: tuple(int(round(value)) for value in p)
                plan = dict(outline, mid=pixel(middle), in_tip=pixel(inward), out_tip=pixel(outward),
                            in_dir=normal, out_dir=(-normal[0], -normal[1]))
                if fallback is None:
                    fallback = plan
                if all(margin <= x <= width - margin and margin <= y <= height - margin
                       for x, y in (inward, outward)):
                    return plan
            arrow /= 2
            if arrow < 2:
                break
    return fallback if fallback is not None else outline


class BoardingCountingRegion:
    """Settle once from the first and last confirmed physical positions."""

    def __init__(self, points, boarding_direction='inward', min_residence_frames=3):
        self.points = _validate_boarding_polygon(list(points))
        self.boarding_direction = boarding_direction
        self.min_residence_frames = min_residence_frames

    def observe(self, track):
        state = 'INSIDE' if _boarding_inside(track.foot, self.points) else 'OUTSIDE'
        if track.region_state == state:
            track.region_candidate = None
            track.region_candidate_frames = 0
            return
        if track.region_candidate != state:
            track.region_candidate = state
            track.region_candidate_frames = 0
        track.region_candidate_frames += 1
        if track.region_candidate_frames < self.min_residence_frames:
            return
        if track.region_origin is None:
            track.region_origin = state
        track.region_state = state
        track.region_candidate = None
        track.region_candidate_frames = 0

    def final_event(self, track):
        if track.region_finalized:
            return None
        track.region_finalized = True
        if track.region_origin == 'OUTSIDE' and track.region_state == 'INSIDE':
            return 'exit' if self.boarding_direction == 'outward' else 'enter'
        if track.region_origin == 'INSIDE' and track.region_state == 'OUTSIDE':
            return 'enter' if self.boarding_direction == 'outward' else 'exit'
        return None


def parse_config_resolution(raw):
    """Return the saved configuration image dimensions when available."""
    if isinstance(raw, str):
        match = re.fullmatch(r'\s*(\d+)\s*[xX×*,]\s*(\d+)\s*', raw)
        if match:
            raw = match.groups()
        else:
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return None
    if isinstance(raw, dict):
        raw = (raw.get('width', raw.get('w')), raw.get('height', raw.get('h')))
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    try:
        width, height = (int(value) for value in raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return (width, height) if min(width, height) > 0 else None


def _parse_cross_line_area(raw: Any) -> Optional[Dict[str, Any]]:
    '''解析 cross_line_area 字段为越线/方向配置。兼容三种回传格式：
       1) 两点直线：{'p1':{x,y}, 'p2':{x,y}[, 'direction':'left'|'right']}
       2) 连续多线段折线：{'points':[{x,y}, {x,y}, ...][, 'direction':...]}
       3) 裸点列表：[{x,y}, {x,y}, ...]
    统一返回 {'points':[(x,y),...], 'p1':首点, 'p2':尾点[, 'direction':...]}，
    其中 points 至少 2 个点（>=3 点即多线段折线，按净穿越代数和判定过线）；
    p1/p2 保留为首/尾点，兼容旧调用（model_start 的配置签名、未配置时的默认中线兜底）。'''
    if not raw:
        return None
    data = raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            data = json.loads(s)
        except (ValueError, TypeError) as e:
            logging.warning('[cross_line] 解析失败: %s | raw=%r', e, raw[:160])
            return None

    if isinstance(data, dict) and data.get('scene') == 'boarding':
        if data.get('area_type', 'polygon') != 'polygon':
            raise ValueError('乘车点使用闭合计数区域')
        raw_points = data.get('points')
        if not isinstance(raw_points, list) or not 3 <= len(raw_points) <= 65:
            raise ValueError('乘车点计数区域需要 3 到 64 个不同顶点')
        points = []
        for point in raw_points:
            try:
                x, y = float(point['x']), float(point['y'])
                if not (0 <= x <= 1000000 and 0 <= y <= 1000000):
                    raise ValueError('坐标超出范围')
                points.append((int(x), int(y)))
            except (KeyError, ValueError, TypeError, OverflowError) as error:
                raise ValueError('人数统计区域包含无效坐标') from error
        residence = data.get('min_residence_frames', 3)
        if type(residence) is not int or not 1 <= residence <= 120:
            raise ValueError('区域确认帧数必须为 1 到 120 的整数')
        boarding_direction = data.get('boarding_direction', 'inward')
        if boarding_direction not in ('inward', 'outward'):
            raise ValueError('无效的乘车点进出方向')
        out = {'scene': 'boarding', 'area_type': 'polygon',
               'points': _validate_boarding_polygon(points), 'min_residence_frames': residence}
        out['boarding_direction'] = boarding_direction
        return out

    def _pt(d: Any) -> Optional[Tuple[int, int]]:
        '''把 {'x':..,'y':..} 字典（或 (x,y) 元组）解析为整数坐标，非法输入返回 None。'''
        if isinstance(d, (tuple, list)) and len(d) == 2:
            d = {'x': d[0], 'y': d[1]}
        if not isinstance(d, dict):
            return None
        try:
            x, y = float(d.get('x')), float(d.get('y'))
            if not (math.isfinite(x) and math.isfinite(y)):
                return None
            return (int(x), int(y))
        except (TypeError, ValueError, OverflowError):
            return None

    direction: Any = None
    raw_points: Optional[List[Any]] = None
    if isinstance(data, list):
        raw_points = data                                   # 格式 3：裸点列表
    elif isinstance(data, dict):
        direction = data.get('direction')
        if isinstance(data.get('points'), list):
            raw_points = data.get('points')                 # 格式 2：连续多线段折线
        else:
            p1 = _pt(data.get('p1'))                        # 格式 1：两点直线（p1 -> p2）
            p2 = _pt(data.get('p2'))
            raw_points = [p1, p2] if (p1 is not None and p2 is not None) else None
    if not raw_points:
        return None

    # 逐点解析并去除相邻重复点（重复点会产生零长度子线段，线段求交会退化成点判定）
    points: List[Tuple[int, int]] = []
    for d in raw_points:
        pt = _pt(d)
        if pt is None:
            logging.warning('[cross_line] 忽略非法顶点 %r | raw=%r', d, str(raw)[:160])
            continue
        if not points or points[-1] != pt:
            points.append(pt)
    if len(points) < 2:
        return None

    out: Dict[str, Any] = {'points': points, 'p1': points[0], 'p2': points[-1]}
    if isinstance(direction, str):
        d = direction.strip().lower()
        if d in ('left', 'right'):
            out['direction'] = d
    return out


def _parse_thresh(raw: Any, default: float) -> float:
    '''解析 0~1 阈值，兼容 0~1 小数与 0~100 百分数（如 '60'->0.6）。'''
    if raw in (None, ''):
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if v > 1:
        v /= 100.0
    return v if 0.0 < v <= 1.0 else default


def _parse_label_list(raw: Any) -> List[str]:
    '''把类别列表字段解析为字符串列表：兼容 list、"['人头']" 字面量字符串与裸字符串。'''
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        try:
            data = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return [raw.strip()] if raw.strip() else []
        if isinstance(data, list):
            return [str(x) for x in data if x]
    return []


_CROSS_ARROW_DIR = 1


def precompute_cross_lines(cross_lines: List[Dict[str, Any]],
                           arrow_ratio: float = 0.05, arrow_min: int = 30,
                           arrow_max: int = 140) -> List[Dict[str, Any]]:
    '''把静态 cross_line 配置预计算成可直接绘制的基元（各子线段 + 箭头尖端/方向）。
    支持两点直线与连续多线段折线：IN/OUT 方向箭头绘制在最长子线段中点处，
    箭头长度按折线总长等比缩放（与过线判定共用同一套 direction 约定）。'''
    plans: List[Dict[str, Any]] = []
    for cl in cross_lines or []:
        if not cl or cl.get('scene') == 'boarding':
            continue
        pts = cl.get('points')
        if not pts:
            p1 = cl.get('p1')
            p2 = cl.get('p2')
            if p1 is None or p2 is None:
                continue
            pts = [p1, p2]
        pts = [(int(p[0]), int(p[1])) for p in pts]
        if len(pts) < 2:
            continue
        segments = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        plan: Dict[str, Any] = {'points': pts, 'segments': segments}
        # 选最长子线段作为 IN/OUT 方向箭头的锚放位置；箭头长度按折线总长等比缩放
        best = None
        best_len = -1.0
        total_len = 0.0
        for (a, b) in segments:
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            seglen = (dx * dx + dy * dy) ** 0.5
            total_len += seglen
            if seglen > best_len:
                best_len = seglen
                best = (a, b, dx, dy, seglen)
        if best is not None and best[4] >= 1e-6:
            a, b, dx, dy, seglen = best
            nx0 = dy / seglen
            ny0 = -dx / seglen
            base = -1 if cl.get('direction') == 'left' else 1
            sign = _CROSS_ARROW_DIR * base
            alen = max(arrow_min, min(total_len * arrow_ratio, arrow_max))
            mx = (a[0] + b[0]) * 0.5
            my = (a[1] + b[1]) * 0.5
            mid = (int(round(mx)), int(round(my)))
            ox = int(round(sign * nx0 * alen))
            oy = int(round(sign * ny0 * alen))
            plan['mid'] = mid
            plan['in_tip'] = (mid[0] + ox, mid[1] + oy)
            plan['out_tip'] = (mid[0] - ox, mid[1] - oy)
            uix = sign * nx0
            uiy = sign * ny0
            plan['in_dir'] = (uix, uiy)
            plan['out_dir'] = (-uix, -uiy)
        plans.append(plan)
    return plans


_LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
_LABEL_SCALE = 0.7
_LABEL_THICK = 2
_LABEL_GAP = 8


def _draw_arrow_label(image, text, tip, udir, color, aa, img_w, img_h):
    '''在箭头尖端外侧居中绘制标签，避开箭头头部覆盖。'''
    (tw, th), _ = cv2.getTextSize(text, _LABEL_FONT, _LABEL_SCALE, _LABEL_THICK)
    cx = tip[0] + udir[0] * (_LABEL_GAP + th)
    cy = tip[1] + udir[1] * (_LABEL_GAP + th)
    ox = int(round(cx - tw * 0.5))
    oy = int(round(cy + th * 0.5))
    ox = max(2, min(ox, img_w - tw - 2))
    oy = max(th + 2, min(oy, img_h - 2))
    cv2.putText(image, text, (ox, oy), _LABEL_FONT, _LABEL_SCALE, color, _LABEL_THICK, aa)


def draw_cross_lines(image, plans: List[Dict[str, Any]],
                     line_color=(0, 255, 255), in_color=(0, 255, 0),
                     out_color=(0, 0, 255), thickness: int = 3, point_radius: int = 6):
    '''按 precompute_cross_lines 预计算的 plan 逐帧绘制：各子线段判定线(黄) + 顶点 +
    IN(绿)/OUT(红)双箭头 + 标签。'''
    if not plans:
        return image
    aa = cv2.LINE_AA
    img_h, img_w = image.shape[:2]
    for plan in plans:
        segments = plan.get('segments')
        if not segments:
            p1 = plan.get('p1')
            p2 = plan.get('p2')
            segments = [(p1, p2)] if (p1 is not None and p2 is not None) else []
        for (a, b) in segments:
            cv2.line(image, a, b, line_color, thickness, aa)
        if plan.get('kind') != 'polygon':
            for p in plan.get('points') or []:
                cv2.circle(image, p, point_radius, line_color, -1, aa)
        mid = plan.get('mid')
        if mid is not None:
            in_tip = plan['in_tip']
            out_tip = plan['out_tip']
            cv2.arrowedLine(image, mid, in_tip, in_color, thickness, aa, tipLength=0.3)
            cv2.arrowedLine(image, mid, out_tip, out_color, thickness, aa, tipLength=0.3)
            _draw_arrow_label(image, 'IN', in_tip, plan['in_dir'], in_color, aa, img_w, img_h)
            _draw_arrow_label(image, 'OUT', out_tip, plan['out_dir'], out_color, aa, img_w, img_h)
    return image


# ======================================================================
# 过线计数 + 轨迹跟踪
# ======================================================================
class _GateSegment:
    """Signed perpendicular distance and distance along one drawn segment, in pixels."""

    def __init__(self, start, end, include_start=False, include_end=False):
        self.x, self.y = start
        dx, dy = end[0] - self.x, end[1] - self.y
        self.length = math.hypot(dx, dy)
        self.ux, self.uy = (dx / self.length, dy / self.length) if self.length else (0.0, 0.0)
        self.include_start, self.include_end = include_start, include_end

    def position(self, point):
        dx, dy = point[0] - self.x, point[1] - self.y
        return self.ux * dy - self.uy * dx, self.ux * dx + self.uy * dy

    def contains(self, along):
        # A touch at an open end can also be a path around the gate.
        start = along >= -1e-7 if self.include_start else along > 1e-7
        end = along <= self.length + 1e-7 if self.include_end else along < self.length - 1e-7
        return start and end


class _MeasuredCrossing:
    """Observe contiguous detector boxes. Emit on the first point on the opposite side."""

    def __init__(self):
        self.segments = {}
        self.contact = None
        self.first_observation = None
        self.moving = False

    def reset(self):
        self.segments.clear()
        self.contact = None
        self.first_observation = None
        self.moving = False

    @staticmethod
    def _contact_side(line, states):
        """Find the oriented side of the closest finite leg at an off-gate sample."""
        closest = float('inf')
        sides = set()
        armed = False
        for index, (distance, along, _, ready) in states.items():
            segment = line.gate_segments[index]
            beyond = max(0.0, -along, along - segment.length)
            squared = distance * distance + beyond * beyond
            if squared > closest + 1e-7:
                continue
            if squared < closest - 1e-7:
                closest = squared
                sides.clear()
                armed = False
            if abs(distance) > 1e-7:
                side = 1 if distance > 0 else -1
                sides.add(side)
                armed = armed or ready == side
        return (sides.pop(), armed) if len(sides) == 1 else (0, False)

    def observe_box(self, line, point, margin, bbox, image=None):
        """Head/shoulder and legacy models cross at the measured lower midpoint."""
        return self.observe(line, point, margin)

    def observe(self, line, point, margin):
        # A track born inside the detector's jitter band has no reliable
        # movement yet. Never emit a pending count later if its first step
        # across the line was smaller than that uncertainty.
        if self.first_observation is None:
            self.first_observation = point
        if not self.moving:
            dx = point[0] - self.first_observation[0]
            dy = point[1] - self.first_observation[1]
            self.moving = dx * dx + dy * dy > margin * margin
        crossings = 0
        armed_crossings = 0
        previous_states = self.segments
        self.segments = {}
        on_gate = at_open_end = False
        for index, segment in enumerate(line.gate_segments):
            distance, along = segment.position(point)
            side = 0 if abs(distance) <= 1e-7 else (1 if distance > 0 else -1)
            if not side and -1e-7 <= along <= segment.length + 1e-7:
                on_gate = True
                if not segment.contains(along):
                    at_open_end = True
            # The first measured box can establish the approach side even next to
            # the gate. After a crossing the margin suppresses repeated jitter.
            previous_distance, previous_along, origin, armed = previous_states.get(
                index, (distance, along, 0, side))
            if side and origin and side != origin:
                # Intersection of this measured step with the finite gate.
                # If the previous sample was exactly on the line, use that sample.
                fraction = previous_distance / (previous_distance - distance)
                intercept = previous_along + fraction * (along - previous_along)
                if segment.contains(intercept):
                    crossings += side
                    if armed == origin:
                        armed_crossings += side
                    armed = 0
                elif armed == origin:
                    # Changing sides outside the finite leg cannot consume a crossing.
                    armed = side
            if side:
                origin = side
                if abs(distance) >= margin:
                    armed = side
            elif not segment.contains(along):
                # Sliding along the line and out past an endpoint breaks the crossing.
                origin = armed = 0
            self.segments[index] = distance, along, origin, armed
        # A point sliding from one leg onto another has not left the yellow
        # line. Resolve all signed segment crossings when it first leaves it.
        if on_gate:
            if at_open_end:
                self.contact = (0, False)
            elif self.contact is None:
                self.contact = self._contact_side(line, previous_states)
            return None
        if self.contact is not None:
            origin, armed = self.contact
            self.contact = None
            destination, _ = self._contact_side(line, self.segments)
            if not armed or not destination or origin == destination:
                return None
            crossings = armed_crossings = destination
        # At a bend, a tangent that touches two segments has zero net crossings.
        if self.moving and crossings * armed_crossings > 0:
            return 'enter' if crossings * line.enter_cross_sign > 0 else 'exit'
        return None


def _set_frame_timestamp(tracker, frame_timestamp, frame_continuous):
    timestamp = time.time() if frame_timestamp is None else frame_timestamp
    if frame_continuous is None and tracker.max_observation_gap is not None and tracker.frame_timestamp is not None:
        frame_continuous = 0 < timestamp - tracker.frame_timestamp <= tracker.max_observation_gap
    if frame_continuous is False:
        for track in tracker.tracks:
            track.measured_crossing.reset()
            track.foot_history.clear()
    tracker.frame_timestamp = timestamp


def _observe_gate(tracker, track, frame_bgr=None):
    height = track.bbox[3] - track.bbox[1]
    margin = max(_BAND_MARGIN_MIN_PX, _BAND_MARGIN_RATIO * height)
    rule = track.measured_crossing
    if hasattr(rule, 'observe_sample'):
        event = rule.observe_sample(tracker.counting_line, track.foot, margin, track.bbox,
                                    frame_bgr, tracker.frame_no, tracker.frame_timestamp)
    else:
        event = rule.observe_box(tracker.counting_line, track.foot, margin, track.bbox, frame_bgr)
    if event:
        tracker._register_cross(track, event)


class CountingLine:
    """计数线：两端点定义一条直线，第三点指定"进入源侧"，仅计算已绘制线段内的穿越。"""

    def __init__(self, pt1, pt2, enter_source_pt):
        '''pt1/pt2 为判定线两端点，enter_source_pt 指定"进入源侧"的参考点。'''
        self.pt1 = np.array(pt1, dtype=float)
        self.pt2 = np.array(pt2, dtype=float)
        ref_side = self._cross_val(enter_source_pt)
        self.enter_source_sign = 1 if ref_side >= 0 else -1
        self.enter_cross_sign = -self.enter_source_sign
        self.gate_segments = [_GateSegment(pt1, pt2)]

    def _cross_val(self, pt):
        '''计算 (pt2-pt1) × (pt-pt1) 的叉积值，符号表示 pt 在直线哪一侧。'''
        d = self.pt2 - self.pt1
        v = np.array(pt, dtype=float) - self.pt1
        return float(d[0] * v[1] - d[1] * v[0])

    def side(self, pt):
        '''返回 +1 或 -1，表示点 pt 在判定线的哪一侧。'''
        return 1 if self._cross_val(pt) >= 0 else -1

    def distance(self, pt):
        '''点到判定线的垂距（像素），供判断是否离开线宽死区。'''
        d = self.pt2 - self.pt1
        line_len = math.sqrt(float(d[0]) ** 2 + float(d[1]) ** 2)
        if line_len <= 1e-6:
            return float('inf')
        return abs(self._cross_val(pt)) / line_len

    def segment_crosses(self, p, q):
        segment = self.gate_segments[0]
        first, x1 = segment.position(p)
        last, x2 = segment.position(q)
        return first * last < 0 and segment.contains(x1 + first / (first - last) * (x2 - x1))

    def crossing_event(self, prev_side, curr_side):
        '''由侧面变化判定过线事件：从进入源侧穿到另一侧返回 'enter'，反向返回 'exit'，无变化返回 None。'''
        if prev_side == curr_side:
            return None
        return 'enter' if prev_side == self.enter_source_sign else 'exit'


class Track:
    """单个目标的轨迹状态：ACTIVE -> LOST -> 删除；过线后继续跟踪，支持反复计数。"""
    STATE_ACTIVE = 'ACTIVE'
    STATE_LOST = 'LOST'
    STATE_DEAD = 'DEAD'
    _next_id = 0

    def __init__(self, bbox, cls, conf, frame_no):
        '''以首次检测框初始化轨迹：分配自增 track_id，记录脚底点/速度/时间戳等状态。'''
        self.track_id = Track._next_id
        Track._next_id += 1
        self.cls = cls
        self.conf = conf
        self.bbox = bbox
        self.foot = self._bbox2foot(bbox)
        self.measured_crossing = _MeasuredCrossing()
        self.foot_history = deque([self.foot], maxlen=150)
        self.velocity = (0.0, 0.0)
        self.state = Track.STATE_ACTIVE
        self.lost_frames = 0
        self.last_frame = frame_no
        self.region_origin = self.region_state = self.region_candidate = None
        self.region_candidate_frames = 0
        self.region_finalized = False
        self.prev_foot = self.foot
        self.start_foot = self.foot
        self.first_appear_ts = time.time()
        self.last_active_ts = self.first_appear_ts
        self.track_end_ts = None

    @staticmethod
    def _bbox2foot(bbox):
        '''取检测框底边中点作为"脚底点"（过线判定用）。'''
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, y2)

    def update(self, bbox, cls, conf, frame_no):
        '''用新检测框更新轨迹：EMA 平滑速度、追加脚底点历史、恢复 ACTIVE 状态。'''
        self.prev_foot = self.foot
        self.bbox = bbox
        self.cls = cls
        self.conf = conf
        new_foot = self._bbox2foot(bbox)
        # 用 EMA 平滑速度，减少检测框抖动对 Re-ID 预测点的影响。
        alpha = 0.45
        dx = new_foot[0] - self.foot[0]
        dy = new_foot[1] - self.foot[1]
        self.velocity = (alpha * dx + (1 - alpha) * self.velocity[0],
                         alpha * dy + (1 - alpha) * self.velocity[1])
        self.foot = new_foot
        self.foot_history.append(new_foot)
        self.state = Track.STATE_ACTIVE
        self.lost_frames = 0
        self.last_frame = frame_no
        self.last_active_ts = time.time()

    def mark_lost(self):
        '''本帧未匹配到检测：标记为 LOST 并记录临时结束时间。'''
        self.lost_frames += 1
        self.state = Track.STATE_LOST
        self.measured_crossing.reset()
        self.track_end_ts = time.time()

    def predict_foot(self, frame_gap):
        '''按当前速度外推 frame_gap 帧后的脚底点位置（Re-ID 匹配用）。'''
        fx, fy = self.foot
        vx, vy = self.velocity
        return (fx + vx * frame_gap, fy + vy * frame_gap)

    def reidentify(self, bbox, cls, conf, frame_no):
        '''Re-ID 成功：保留原 track_id 恢复 ACTIVE，并清空结束时间。'''
        self.foot_history.clear()
        self.update(bbox, cls, conf, frame_no)
        self.track_end_ts = None


def compute_iou(b1, b2):
    """[x1,y1,x2,y2] 格式 IoU。"""
    ix1 = max(b1[0], b2[0])
    iy1 = max(b1[1], b2[1])
    ix2 = min(b1[2], b2[2])
    iy2 = min(b1[3], b2[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0


def compute_reid_score(track, new_foot, new_bbox, frame_gap, max_dist=200, min_vel=1.0):
    """丢失轨迹与新检测目标的 Re-ID 得分 [0,1]（距离 + IOU + 方向 + 大小）。"""
    pred_x, pred_y = track.predict_foot(frame_gap)
    nx, ny = new_foot
    dist = math.sqrt((nx - pred_x) ** 2 + (ny - pred_y) ** 2)
    if dist > max_dist * 1.2:
        return 0.0
    dist_score = max(0.0, 1.0 - dist / max_dist)
    tb = track.bbox
    t_w = tb[2] - tb[0]
    t_h = tb[3] - tb[1]
    pred_bbox = [pred_x - t_w / 2, pred_y - t_h / 2, pred_x + t_w / 2, pred_y + t_h / 2]
    # 长距离找回时位置外推本身就不精确：固定 IoU 门限会把远距离恢复全部挡死
    # （旧框尺寸还在变，人走近/走远时预测框与当前框几乎不重叠）。因此门限随位移
    # 线性放宽——近处仍保留 0.05 的强约束防错配，超过 0.6*max_dist 后完全交给
    # 距离/方向/大小三项打分（距离分本身在 max_dist 处已衰减到 0）。
    iou_need = 0.05 * max(0.0, 1.0 - dist / max(1e-6, max_dist * 0.6))
    if compute_iou(pred_bbox, new_bbox) < iou_need:
        return 0.0
    fx, fy = track.foot
    actual_vec = (nx - fx, ny - fy)
    vx, vy = track.velocity
    vel_norm = math.sqrt(vx ** 2 + vy ** 2)
    if vel_norm < min_vel:
        dir_score = 0.5
    else:
        pred_vec = (vx * frame_gap, vy * frame_gap)
        dot = actual_vec[0] * pred_vec[0] + actual_vec[1] * pred_vec[1]
        mag_a = math.sqrt(actual_vec[0] ** 2 + actual_vec[1] ** 2) + 1e-6
        mag_p = math.sqrt(pred_vec[0] ** 2 + pred_vec[1] ** 2) + 1e-6
        dir_score = max(0.0, dot / (mag_a * mag_p))
    nb = new_bbox
    t_area = max(1, (tb[2] - tb[0]) * (tb[3] - tb[1]))
    n_area = max(1, (nb[2] - nb[0]) * (nb[3] - nb[1]))
    area_ratio = min(t_area, n_area) / max(t_area, n_area)
    t_ar = (tb[3] - tb[1]) / max(1, tb[2] - tb[0])
    n_ar = (nb[3] - nb[1]) / max(1, nb[2] - nb[0])
    ar_score = 1.0 - min(1.0, abs(t_ar - n_ar) / max(t_ar, n_ar, 1e-6))
    size_score = 0.5 * area_ratio + 0.5 * ar_score
    return 0.5 * dist_score + 0.3 * dir_score + 0.2 * size_score


class Tracker:
    """多目标跟踪器，支持 Re-ID 及过线计数。"""

    def __init__(self, iou_thresh=0.30, max_lost_frames=30, reid_max_dist=120,
                 reid_score_thresh=0.45, counting_line=None, cross_cooldown_frames=15,
                 init_enter_all=0, init_exit_all=0):
        self.iou_thresh = iou_thresh
        self.max_lost_frames = max_lost_frames
        self.reid_max_dist = reid_max_dist
        self.reid_score_thresh = reid_score_thresh
        self.counting_line = counting_line
        # 会话临时计数（每次会话结束归零）
        self.enter_count = 0
        self.exit_count = 0
        # 全局永久累计（进程运行全程保留，不随会话重置）：在场人数 = 累计进入 - 累计离开
        # 重启时由外层传入上次回传的累计值作为初始值，不写本地文件
        self.total_enter_all = _safe_int(init_enter_all)
        self.total_exit_all = _safe_int(init_exit_all)
        if self.total_enter_all or self.total_exit_all:
            logging.info('[counting] 使用外部传入初始累计：进入=%d 离开=%d',
                         self.total_enter_all, self.total_exit_all)
        self.tracks = []
        self.frame_no = 0
        self.frame_timestamp = None
        self.max_observation_gap = None
        self.first_cross_ts = None            # 第一张计数确认帧时间（会话开始）
        self.last_cross_ts = None             # 最后一张计数确认帧时间（会话结束）
        self.no_active_since = None           # 画面无活跃轨迹的起始时间
        self.cross_events = []                # 本帧过线事件缓存 [(track_id, bbox, event_type), ...]

    @property
    def active_tracks(self):
        '''当前处于 ACTIVE 状态的轨迹列表。'''
        return [t for t in self.tracks if t.state == Track.STATE_ACTIVE]

    def _register_cross(self, trk, event, tag='过线'):
        '''记录一次过线事件，并使用录像共用的帧时间标注计数时段。'''
        now_ts = time.time() if self.frame_timestamp is None else self.frame_timestamp
        self.last_cross_ts = now_ts
        if self.first_cross_ts is None:
            self.first_cross_ts = now_ts   # 视频预录独立保留过线前画面
        if event == 'enter':
            self.enter_count += 1
            self.total_enter_all += 1                   # 全局累计不随会话重置
        elif event == 'exit':
            self.exit_count += 1
            self.total_exit_all += 1
        logging.info('[%s] 轨迹 #%d %s，会话进入=%d 离开=%d | 全局累计进入=%d 离开=%d' % (
            tag, trk.track_id, '进入' if event == 'enter' else '离开',
            self.enter_count, self.exit_count, self.total_enter_all, self.total_exit_all))
        # 缓存本次过线事件及目标框，供 on_result 保存画面。
        self.cross_events.append((trk.track_id,
                                  [int(v) for v in trk.bbox], event))

    def _check_crossing(self, trk):
        '''检测轨迹本帧是否穿过计数线（含冷却帧防抖），更新会话/全局进出计数。'''
        if self.counting_line is None:
            return
        if isinstance(self.counting_line, BoardingCountingRegion):
            self.counting_line.observe(trk)
            return
        _observe_gate(self, trk)

    def update(self, detections, frame_timestamp=None, frame_continuous=None):
        '''跟踪器主更新入口：IoU 匹配 → 过线检测 → 丢失轨迹 Re-ID → 新建轨迹 → 清理超龄轨迹。
        detections 为 (bbox, cls, conf) 列表，返回 ACTIVE 轨迹列表。'''
        _set_frame_timestamp(self, frame_timestamp, frame_continuous)
        self.frame_no += 1
        n_det = len(detections)
        active = [t for t in self.tracks if t.state == Track.STATE_ACTIVE]
        matched_det = set()
        matched_trk = set()
        if active and n_det > 0:
            iou_mat = np.zeros((len(active), n_det))
            for ti, trk in enumerate(active):
                for di, (bbox, _, _) in enumerate(detections):
                    iou_mat[ti, di] = compute_iou(trk.bbox, bbox)
            while True:
                if iou_mat.max() < self.iou_thresh:
                    break
                ti, di = np.unravel_index(iou_mat.argmax(), iou_mat.shape)
                bbox, cls, conf = detections[di]
                active[ti].update(bbox, cls, conf, self.frame_no)
                matched_det.add(di)
                matched_trk.add(active[ti].track_id)
                iou_mat[ti, :] = -1
                iou_mat[:, di] = -1
        if self.counting_line:
            for trk in active:
                if trk.track_id in matched_trk:
                    self._check_crossing(trk)
        newly_lost_ids = set()
        for trk in active:
            if trk.track_id not in matched_trk:
                trk.mark_lost()
                newly_lost_ids.add(trk.track_id)
        lost = [t for t in self.tracks if t.state == Track.STATE_LOST]
        unmatched_dets = [i for i in range(n_det) if i not in matched_det]
        if lost and unmatched_dets:
            for di in list(unmatched_dets):
                bbox, cls, conf = detections[di]
                new_foot = Track._bbox2foot(bbox)
                best_score = self.reid_score_thresh
                best_trk = None
                for trk in lost:
                    if trk.track_id in matched_trk:
                        continue
                    frame_gap = self.frame_no - trk.last_frame
                    px, py = trk.predict_foot(frame_gap)
                    if math.sqrt((new_foot[0] - px) ** 2 + (new_foot[1] - py) ** 2) > self.reid_max_dist * 2:
                        continue
                    score = compute_reid_score(trk, new_foot, bbox, frame_gap, max_dist=self.reid_max_dist)
                    if score > best_score:
                        best_score = score
                        best_trk = trk
                if best_trk is not None:
                    best_trk.reidentify(bbox, cls, conf, self.frame_no)
                    matched_det.add(di)
                    matched_trk.add(best_trk.track_id)
                    unmatched_dets.remove(di)
                    if self.counting_line:
                        self._check_crossing(best_trk)
        # LOST 轨迹逐帧老化（05_1 移植）：本帧未被 Re-ID 回、也不是刚转 LOST 的轨迹 lost_frames+1，
        # 否则旧 LOST 轨迹的 lost_frames 永远停在 1、达不到删除阈值（轨迹越积越多且易误 Re-ID）
        for trk in self.tracks:
            if (trk.state == Track.STATE_LOST
                    and trk.track_id not in matched_trk
                    and trk.track_id not in newly_lost_ids):
                trk.lost_frames += 1
        for di in unmatched_dets:
            bbox, cls, conf = detections[di]
            new_trk = Track(bbox, cls, conf, self.frame_no)
            self.tracks.append(new_trk)
            if isinstance(self.counting_line, BoardingCountingRegion):
                self.counting_line.observe(new_trk)
            elif self.counting_line:
                _observe_gate(self, new_trk)
        survivors = []
        for t in self.tracks:
            if t.state == Track.STATE_LOST and t.lost_frames > self.max_lost_frames:
                if isinstance(self.counting_line, BoardingCountingRegion):
                    event = self.counting_line.final_event(t)
                    if event is not None:
                        self._register_cross(t, event, tag='乘车点区域结算')
                if t.track_end_ts is None:
                    t.track_end_ts = time.time()
            else:
                survivors.append(t)
        self.tracks = survivors
        # 维护「画面无活跃轨迹」的起始时间（会话结束判定用）
        if len(self.active_tracks) == 0:
            if self.no_active_since is None:
                self.no_active_since = time.time()
        else:
            self.no_active_since = None
        return self.active_tracks

    def pop_cross_events(self):
        '''取出并清空本帧累积的过线事件，返回 [(track_id, [x1,y1,x2,y2], event_type), ...]。'''
        events = self.cross_events
        self.cross_events = []
        return events

    def check_activity_timeout(self, timeout=5):
        """Settle idle sessions and cap busy sessions while their footage is retained."""
        if self.first_cross_ts is None or self.last_cross_ts is None:
            return None
        now_ts = time.time()
        no_active_gap = None if self.no_active_since is None else now_ts - self.no_active_since
        media_now = now_ts if self.frame_timestamp is None else self.frame_timestamp
        total_life = media_now - self.first_cross_ts
        if total_life >= _SESSION_MAX_SEC or (no_active_gap is not None and no_active_gap >= timeout):
            session_info = {
                'start_time': datetime.fromtimestamp(self.first_cross_ts),
                'end_time': datetime.fromtimestamp(self.last_cross_ts),
                'enter_count': self.enter_count,
                'exit_count': self.exit_count,
            }
            self._reset_session()
            return session_info
        return None

    def _reset_session(self):
        '''会话结算后重置：仅清空会话临时计数与时间标记，全局永久累计保留不清零。'''
        self.enter_count = 0
        self.exit_count = 0
        self.first_cross_ts = None
        self.last_cross_ts = None
        self.no_active_since = None


def _segments_intersect(p1, p2, p3, p4):
    '''判定线段 p1p2 与线段 p3p4 是否相交（叉积方向法）。
    归侧口径与 CountingLine.side 对齐：叉积 d==0（端点恰在线上）归入正侧——
    使"脚底点恰落线上"的触线/跨帧过线行为与两点直线分支一致，且折线共享顶点
    恰在弦上时相邻两段只登记一次（另一段因顶点与邻端点同归正侧而不判相交）。
    完全共线重叠视为不相交。'''
    def _ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    d1 = _ccw(p3, p4, p1)
    d2 = _ccw(p3, p4, p2)
    d3 = _ccw(p1, p2, p3)
    d4 = _ccw(p1, p2, p4)
    return ((d1 >= 0) != (d2 >= 0)) and ((d3 >= 0) != (d4 >= 0))


def _point_seg_distance(pt, a, b):
    '''点 pt 到线段 ab 的最短距离（退化为点时取端点距离）。'''
    px, py = float(pt[0]), float(pt[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _point_polyline_distance(pt, segments):
    '''点到折线（子线段列表）的最短距离；空折线返回 0.0。'''
    if not segments:
        return 0.0
    return min(_point_seg_distance(pt, a, b) for (a, b) in segments)


class PolylineCountingLine:
    """连续多线段（折线）计数线：按弦与全部子线段的净穿越代数和判定过线；
    进/出方向由子线段法向 + direction 决定（与 IN 箭头绘制约定一致）。"""

    def __init__(self, points, direction='right'):
        '''points 为按顺序的折线顶点列表（>=2 点），direction 指定"进入"侧（与 IN 箭头方向一致）。'''
        self.points = [(float(p[0]), float(p[1])) for p in points]
        self.segments = []
        for i in range(len(self.points) - 1):
            a = self.points[i]
            b = self.points[i + 1]
            if a != b:
                self.segments.append((a, b))
        self.gate_segments = [
            _GateSegment(a, b, index > 0, index + 1 < len(self.segments))
            for index, (a, b) in enumerate(self.segments)
        ]
        # 与 precompute_cross_lines/绘制的 IN 箭头保持一致：
        #   IN 法向 = sign*(dy,-dx)/len，sign = _CROSS_ARROW_DIR*base，base=('left'->-1,'right'->1)
        #   运动 m 跨越子线段时，若与 IN 法向同向则为 enter；
        #   推导得 enter 对应 sign(segdir×m) == -sign，记为 enter_cross_sign。
        base = -1 if str(direction).lower() == 'left' else 1
        self.enter_cross_sign = -(_CROSS_ARROW_DIR * base)
        # side() 兼容属性（仅用于初始化 trk.line_side 占位）：用首尾连线作为整体参考方向
        first, last = self.points[0], self.points[-1]
        enter_src = get_arrow_side_point(first, last, direction, distance=30)
        self._ref = CountingLine(first, last, enter_src)

    def side(self, pt):
        '''返回 +1/-1：按首尾连线的整体侧面（仅供 trk.line_side 初始化与非空判断）。'''
        return self._ref.side(pt)

    def distance(self, pt):
        '''点到折线各子线段的最短距离（像素），供判断是否离开线宽死区。'''
        return _point_polyline_distance(pt, self.segments)

    def detect_event(self, prev, curr):
        '''按【净穿越代数和】判定 prev->curr 位移是否过线：累加弦与全部子线段
        穿越的方向符号（±1），和为 0 = 起终点在折线同一拓扑侧（擦过凸顶点、
        拐角单帧双穿越、往返未过线）返回 None；否则按和的符号判 enter/exit。
        代数和口径与穿越次序无关，天然处理发卡/蛇形折线的多次穿越
        （如符号序列 (+,+,-) 净 +1 → 单次事件，方向取净方向而非末次方向），
        杜绝拐点附近的虚假计数与在岗净值漂移。'''
        mdx = curr[0] - prev[0]
        mdy = curr[1] - prev[1]
        total = 0
        for (a, b) in self.segments:
            if not _segments_intersect(prev, curr, a, b):
                continue
            cross = (b[0] - a[0]) * mdy - (b[1] - a[1]) * mdx
            if cross > 0:
                total += 1
            elif cross < 0:
                total -= 1
        if total == 0:
            return None                        # 净未过线
        s = 1 if total > 0 else -1
        return 'enter' if s == self.enter_cross_sign else 'exit'


def _pairwise_iou(boxes_a, boxes_b):
    """Evaluate the same IoU formula for every pair of finite xyxy boxes."""
    boxes_a = np.asarray(boxes_a, dtype=np.float64)
    boxes_b = np.asarray(boxes_b, dtype=np.float64)
    corner_min = np.maximum(boxes_a[:, None, :2], boxes_b[None, :, :2])
    corner_max = np.minimum(boxes_a[:, None, 2:], boxes_b[None, :, 2:])
    extent = np.maximum(0, corner_max - corner_min)
    inter = extent[:, :, 0] * extent[:, :, 1]
    size_a = boxes_a[:, 2:] - boxes_a[:, :2]
    size_b = boxes_b[:, 2:] - boxes_b[:, :2]
    union = (size_a[:, 0] * size_a[:, 1])[:, None] + (size_b[:, 0] * size_b[:, 1])[None, :] - inter
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


class _KalmanFoot:
    '''脚底点匀速（CV）卡尔曼：状态 [x, y, vx, vy]，只对位置做量测更新。
    相比"当前点 + 速度外推"，它额外维护协方差 P——P 随丢失时间自然放大，
    正好用来做 Re-ID 的马氏门控（丢得越久，允许的偏差越大）。'''

    _F = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
    _H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
    _I = np.eye(4)

    def __init__(self, x, y, accel_q=_KF_ACCEL_Q, meas_r=_KF_MEAS_R):
        self.x = np.array([float(x), float(y), 0.0, 0.0])
        # 初始速度方差给大：新轨迹第一帧不知道速度，门控必须放得开，
        # 否则快速起步的目标第二帧就会被自己"门"掉。
        self.P = np.diag([meas_r, meas_r, 400.0, 400.0])
        self.q = float(accel_q)
        self.r = float(meas_r)
        # 连续白噪声加速度模型的离散化 Q（dt=1）
        self.Q = self.q * np.array([[0.25, 0, 0.5, 0],
                                    [0, 0.25, 0, 0.5],
                                    [0.5, 0, 1.0, 0],
                                    [0, 0.5, 0, 1.0]], dtype=float)
        self.R = self.r * np.eye(2)
        self._prediction = None
        self._inverse_innovation = None

    def predict(self):
        '''状态一步预测（不含量测）。'''
        self.x = self._F @ self.x
        self.P = self._F @ self.P @ self._F.T + self.Q
        self._prediction = None
        return self.x

    def correct(self, zx, zy):
        '''用量测位置修正状态，返回修正后的状态向量。'''
        y = np.array([float(zx), float(zy)]) - self._H @ self.x
        S = self._H @ self.P @ self._H.T + self.R
        K = self.P @ self._H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (self._I - K @ self._H) @ self.P
        self._prediction = None
        return self.x

    def propagated(self, gap):
        '''不改状态，纯外推 gap 帧，返回 (位置, 位置协方差 2x2)。
        用闭式解而不是逐帧递推：Re-ID 每帧要对"丢失轨迹×候选检测"成对调用，
        而稀疏档的 LOST 窗口可达上百帧，逐帧推会变成热路径负担。'''
        n = float(max(0, int(gap)))
        # Lost tracks are compared with multiple detections at the same gap.
        if self._prediction is not None and self._prediction[0] == n:
            return self._prediction[1], self._prediction[2]
        Fn = np.array([[1.0, 0.0, n, 0.0],
                       [0.0, 1.0, 0.0, n],
                       [0.0, 0.0, 1.0, 0.0],
                       [0.0, 0.0, 0.0, 1.0]])
        q = self.q
        Qn = q * np.array([[n ** 3 / 3.0 - n / 12.0, 0.0, n ** 2 / 2.0, 0.0],
                           [0.0, n ** 3 / 3.0 - n / 12.0, 0.0, n ** 2 / 2.0],
                           [n ** 2 / 2.0, 0.0, n, 0.0],
                           [0.0, n ** 2 / 2.0, 0.0, n]])
        x = Fn @ self.x
        P = Fn @ self.P @ Fn.T + Qn
        pos, cov = x[:2], P[:2, :2]
        self._prediction = n, pos, cov
        self._inverse_innovation = None
        return pos, cov

    def mahalanobis2(self, pt, gap=0):
        '''新息的马氏距离平方（2 自由度）：偏差按预测不确定性归一化。'''
        pos, P = self.propagated(gap)
        d = np.array([float(pt[0]), float(pt[1])]) - pos
        if self._inverse_innovation is None:
            self._inverse_innovation = np.linalg.inv(P + self.R)
        return float(d @ self._inverse_innovation @ d)


class _LineTrack:
    """单个目标的轨迹状态：ACTIVE -> LOST -> 删除；过线后继续跟踪，支持反复计数。"""
    STATE_ACTIVE = 'ACTIVE'
    STATE_LOST = 'LOST'
    STATE_DEAD = 'DEAD'
    _next_id = 0
    _sample_centers = np.arange(3, 15, 2)

    def __init__(self, bbox, cls, conf, frame_no):
        '''以首次检测框初始化轨迹：分配自增 track_id，记录脚底点/速度/时间戳等状态。'''
        self.track_id = _LineTrack._next_id
        _LineTrack._next_id += 1
        self.cls = cls
        self.conf = conf
        self.bbox = bbox
        self.foot = self._bbox2foot(bbox)
        self.appearance = None
        self.measured_crossing = _MeasuredCrossing()
        self.foot_history = deque([self.foot], maxlen=150)
        self.kf = _KalmanFoot(self.foot[0], self.foot[1],     # 位置/速度/协方差的唯一来源
                                accel_q=_KF_ACCEL_Q, meas_r=_KF_MEAS_R)
        self.velocity = (0.0, 0.0)
        self.state = _LineTrack.STATE_ACTIVE
        self.lost_frames = 0
        self.last_frame = frame_no
        self.prev_foot = self.foot
        self.start_foot = self.foot
        self.first_appear_ts = time.time()
        self.last_active_ts = self.first_appear_ts
        self.track_end_ts = None

    @staticmethod
    def _bbox2foot(bbox):
        '''取检测框底边中点作为"脚底点"（过线判定用）。'''
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, y2)

    def update(self, bbox, cls, conf, frame_no):
        '''用新检测框更新轨迹：EMA 平滑速度、追加脚底点历史、恢复 ACTIVE 状态。'''
        self.prev_foot = self.foot
        self.bbox = bbox
        self.cls = cls
        self.conf = conf
        new_foot = self._bbox2foot(bbox)
        dx = new_foot[0] - self.foot[0]
        dy = new_foot[1] - self.foot[1]
        # 速度 EMA 系数：偏小(0.45)让速度更平滑，作为历史不足 3 帧时的兜底
        alpha = 0.45
        ema = (alpha * dx + (1 - alpha) * self.velocity[0],
               alpha * dy + (1 - alpha) * self.velocity[1])
        self.foot = new_foot
        self.foot_history.append(new_foot)
        # 卡尔曼：先把状态推到本帧，再用当前量测修正（位置/速度/协方差一起更新）
        self.kf.predict()
        self.kf.correct(new_foot[0], new_foot[1])
        # 速度：历史够长时用窗口最小二乘斜率——对匀速运动无滞后、对检测抖动更稳；
        # 历史不足 3 帧时退回 EMA（此时拟合等价于单步差分，噪声更大）。
        self.velocity = self._fit_velocity() if len(self.foot_history) >= 3 else ema
        self.state = _LineTrack.STATE_ACTIVE
        self.lost_frames = 0
        self.last_frame = frame_no
        self.last_active_ts = time.time()

    def mark_lost(self):
        '''本帧未匹配到检测：标记为 LOST 并记录临时结束时间。'''
        self.lost_frames += 1
        self.state = _LineTrack.STATE_LOST
        rule = self.measured_crossing
        getattr(rule, 'mark_missing', rule.reset)()
        self.track_end_ts = time.time()

    def _fit_velocity(self, k=5):
        '''最近 k 个脚底点上的最小二乘斜率（像素/帧）。点太少时没有意义，退回当前速度。'''
        pts = list(self.foot_history)[-k:]
        n = len(pts)
        if n < 3:
            return self.velocity
        mt = (n - 1) / 2.0
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        den = sum((t - mt) ** 2 for t in range(n)) or 1.0
        vx = sum((t - mt) * (pts[t][0] - mx) for t in range(n)) / den
        vy = sum((t - mt) * (pts[t][1] - my) for t in range(n)) / den
        return (vx, vy)

    def predict_foot(self, frame_gap):
        '''预测 frame_gap 帧后的脚底点，供主匹配和 Re-ID 使用。'''
        pos, _ = self.kf.propagated(frame_gap)
        return (float(pos[0]), float(pos[1]))

    def predict_bbox(self, frame_gap=1):
        '''由预测脚底点还原同尺寸框（主匹配用：快速移动时当前框 IoU 会掉到阈值以下）。'''
        px, py = self.predict_foot(frame_gap)
        x1, y1, x2, y2 = self.bbox
        half = (x2 - x1) / 2.0
        h = y2 - y1
        return [px - half, py - h, px + half, py]

    @staticmethod
    def sample_appearance(image, bbox):
        """A transient 6x6 sample from inside the box for association only."""
        if image is None:
            return None
        h, w = image.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, x2 = max(0, int(x1)), min(w, int(x2))
        y1, y2 = max(0, int(y1)), min(h, int(y2))
        if min(x2 - x1, y2 - y1) < 6:
            return None
        # Interior cell centers avoid the background along detection edges.
        xs = x1 + (x2 - x1) * _LineTrack._sample_centers // 16
        ys = y1 + (y2 - y1) * _LineTrack._sample_centers // 16
        return image[ys[:, None], xs].astype(np.float32)

    def accepts_continuous_match(self, bbox, appearance):
        """Reject abrupt identity changes even when boxes still overlap."""
        foot = self._bbox2foot(bbox)
        scale = max(1.0, min(self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1]))
        jump = math.hypot(foot[0] - self.foot[0], foot[1] - self.foot[1])
        if jump <= max(2.0, scale * 0.10):
            return True
        # Strongly different colors on a sizable displacement are evidence
        # of a different detection; retain no line history across that jump.
        comparable = self.appearance is not None and appearance is not None
        if comparable:
            color_shift = self.appearance.mean(axis=(0, 1)) - appearance.mean(axis=(0, 1))
            if np.max(np.abs(color_shift)) > 64:
                return False
        if jump <= max(3.0, scale * 0.20) or len(self.foot_history) < 3:
            return True
        still_radius = max(1.0, 0.06 * scale)
        if any(math.hypot(self.foot_history[-k][0] - self.foot[0],
                          self.foot_history[-k][1] - self.foot[1]) > still_radius for k in (2, 3)):
            return True
        # A stationary person can start moving, but overlapping box geometry
        # alone also fits a second person becoming visible. Only keep the
        # identity on that step when a textured patch independently agrees.
        if not comparable or self.appearance.std(axis=(0, 1)).max() < 15:
            return False
        return float(np.abs(self.appearance - appearance).mean()) < 16

    def reidentify(self, bbox, cls, conf, frame_no):
        '''Re-ID 成功：保留原 track_id 恢复 ACTIVE，并清空结束时间。'''
        self.foot_history.clear()
        self.update(bbox, cls, conf, frame_no)
        self.track_end_ts = None


def _line_reid_score(track, new_foot, new_bbox, frame_gap, max_dist=200, min_vel=1.0):
    """丢失轨迹与新检测目标的 Re-ID 得分 [0,1]（距离 + IOU + 方向 + 大小）。"""
    pred_x, pred_y = track.predict_foot(frame_gap)
    nx, ny = new_foot
    dist = math.sqrt((nx - pred_x) ** 2 + (ny - pred_y) ** 2)
    if dist > max_dist * 1.2:
        return 0.0
    # 马氏门控：偏差按卡尔曼协方差归一化，丢得越久门越宽；固定像素半径做不到这一点
    if track.kf.mahalanobis2(new_foot, frame_gap) > _MAHA_GATE:
        return 0.0
    # 运动学门：人不会瞬移。允许的位移 = 目标自身尺度 + 丢失期间按已知速度可能走过的距离。
    # 没有这道门时，稀疏档（找回半径放大 1.5 倍）+ 动态放宽的 IoU 门会让"原地丢失的人"
    # 被几百像素外的新目标顶替，表现就是轨迹突然跳到很远的位置。
    body = max(_REID_JUMP_BASE_PX, _REID_JUMP_BODY_RATIO * float(track.bbox[3] - track.bbox[1]))
    speed = math.hypot(track.velocity[0], track.velocity[1])
    travel = math.hypot(nx - track.foot[0], ny - track.foot[1])
    if travel > body + speed * frame_gap * _REID_JUMP_TRAVEL_RATIO:
        return 0.0
    dist_score = max(0.0, 1.0 - dist / max_dist)
    tb = track.bbox
    pred_bbox = track.predict_bbox(frame_gap)
    # 长距离找回时位置外推本身就不精确：固定 IoU 门限会把远距离恢复全部挡死
    # （旧框尺寸还在变，人走近/走远时预测框与当前框几乎不重叠）。因此门限随位移
    # 线性放宽——近处仍保留 0.05 的强约束防错配，超过 0.6*max_dist 后完全交给
    # 距离/方向/大小三项打分（距离分本身在 max_dist 处已衰减到 0）。
    iou_need = 0.05 * max(0.0, 1.0 - dist / max(1e-6, max_dist * 0.6))
    if compute_iou(pred_bbox, new_bbox) < iou_need:
        return 0.0
    fx, fy = track.foot
    actual_vec = (nx - fx, ny - fy)
    vx, vy = track.velocity
    vel_norm = math.sqrt(vx ** 2 + vy ** 2)
    if vel_norm < min_vel:
        dir_score = 0.5
    else:
        pred_vec = (vx * frame_gap, vy * frame_gap)
        dot = actual_vec[0] * pred_vec[0] + actual_vec[1] * pred_vec[1]
        mag_a = math.sqrt(actual_vec[0] ** 2 + actual_vec[1] ** 2) + 1e-6
        mag_p = math.sqrt(pred_vec[0] ** 2 + pred_vec[1] ** 2) + 1e-6
        dir_score = max(0.0, dot / (mag_a * mag_p))
    nb = new_bbox
    t_area = max(1, (tb[2] - tb[0]) * (tb[3] - tb[1]))
    n_area = max(1, (nb[2] - nb[0]) * (nb[3] - nb[1]))
    area_ratio = min(t_area, n_area) / max(t_area, n_area)
    t_ar = (tb[3] - tb[1]) / max(1, tb[2] - tb[0])
    n_ar = (nb[3] - nb[1]) / max(1, nb[2] - nb[0])
    ar_score = 1.0 - min(1.0, abs(t_ar - n_ar) / max(t_ar, n_ar, 1e-6))
    size_score = 0.5 * area_ratio + 0.5 * ar_score
    return 0.5 * dist_score + 0.3 * dir_score + 0.2 * size_score


def _clamp_param(name, value):
    '''档位倍率计算后的边界保护：阈值限定在合理开区间，帧数/像素/速度保底，
    避免倍率叠加后出现 0 帧窗口、负阈值之类不可用参数。'''
    if name in ('iou_thresh', 'reid_score_thresh'):
        return min(0.9, max(0.05, value))
    if name == 'max_lost_frames':
        return max(3, int(value))
    if name == 'reid_max_dist':
        return max(20.0, value)
    return value


class _LineTracker:
    @staticmethod
    def _associations(scores, minimum):
        """Yield the greedy IoU matches in the original row-major tie order."""
        rows, cols = scores.shape
        if rows == cols == 1:
            if scores[0, 0] >= minimum:
                yield 0, 0, False
            return
        track, detection = np.nonzero(scores >= minimum)
        if not len(track):
            return
        score = scores[track, detection]
        order = np.argsort(-score, kind='mergesort')
        if (np.bincount(track).max() == 1 and np.bincount(detection).max() == 1):
            for i in order:
                yield int(track[i]), int(detection[i]), False
            return
        # In the unmodified score matrix a near tie is exactly a runner-up
        # reaching the chosen match's threshold in its row or column.
        row_second = np.partition(scores, -2, axis=1)[:, -2] if cols > 1 else np.full(rows, -1.0)
        col_second = np.partition(scores, -2, axis=0)[-2] if rows > 1 else np.full(cols, -1.0)
        tied = np.maximum(row_second[track], col_second[detection]) >= np.maximum(minimum, 0.95 * score)
        used_tracks, used_detections = set(), set()
        for i in order:
            ti, di = int(track[i]), int(detection[i])
            if ti in used_tracks or di in used_detections:
                continue
            used_tracks.add(ti)
            used_detections.add(di)
            yield ti, di, bool(tied[i])
            if len(used_tracks) == min(rows, cols):
                break

    """多目标跟踪器，支持 Re-ID 及过线计数。"""

    def __init__(self, iou_thresh=0.30, max_lost_frames=30, reid_max_dist=120,
                 reid_score_thresh=0.45, counting_line=None, cross_cooldown_frames=15,
                 init_enter_all=0, init_exit_all=0, max_lost_cap=None, full_body=False, model_profile=None):
        self.model_profile = model_profile
        self.full_body = full_body
        self.iou_thresh = iou_thresh
        self.max_lost_frames = max_lost_frames
        self.reid_max_dist = reid_max_dist
        self.reid_score_thresh = reid_score_thresh
        self.counting_line = counting_line
        # 场景自适应：记下基准参数（已按 fps 缩放），档位切换时按倍率重算，
        # 基准本身不被覆盖，因此可在稀疏/拥挤之间反复切换而不漂移。
        # max_lost_cap 按空闲结算时间限制稀疏档的轨迹找回窗口。
        self._base_params = {name: getattr(self, name) for name in _CROWDED_SCALE}
        self.max_lost_cap = int(max_lost_cap) if max_lost_cap else None
        self.crowded = None          # None=尚未定档，首帧按可见目标数直接定档
        self._crowd_streak = 0
        # 会话临时计数（每次会话结束归零）
        self.enter_count = 0
        self.exit_count = 0
        # 全局永久累计（进程运行全程保留，不随会话重置）：在场人数 = 累计进入 - 累计离开
        # 重启时由外层传入上次回传的累计值作为初始值，不写本地文件
        self.total_enter_all = _safe_int(init_enter_all)
        self.total_exit_all = _safe_int(init_exit_all)
        if self.total_enter_all or self.total_exit_all:
            logging.info('[counting] 使用外部传入初始累计：进入=%d 离开=%d',
                         self.total_enter_all, self.total_exit_all)
        self.tracks = []
        self.frame_no = 0
        # 会话时间语义（05_1 移植）：首次过线为会话开始，最后过线轨迹消失为会话结束
        self.frame_timestamp = None
        self.max_observation_gap = None
        self.first_cross_ts = None            # 第一张计数确认帧时间（会话开始）
        self.last_cross_ts = None             # 最后一张计数确认帧时间（会话结束）
        self.no_active_since = None           # 画面无活跃轨迹的起始时间
        self.cross_events = []                # 本帧过线事件缓存 [(track_id, bbox, event_type), ...]

    @property
    def active_tracks(self):
        '''当前处于 ACTIVE 状态的轨迹列表。'''
        return [t for t in self.tracks if t.state == _LineTrack.STATE_ACTIVE]

    def _scene_risk(self, detections):
        '''本帧的误匹配风险度量：返回 (目标数, 最近两目标的归一化间距)。
        间距 = 两目标脚底点距离 / 两者平均框高，与分辨率、远近无关；
        两框有重叠（遮挡/交错）时直接记 0——那正是 Re-ID 最容易串 ID 的时刻。'''
        n = len(detections)
        if n < 2:
            return n, float('inf')
        boxes = [d[0] for d in detections]
        min_gap = float('inf')
        for i in range(len(boxes)):
            b1 = boxes[i]
            f1x, f1y = (b1[0] + b1[2]) * 0.5, float(b1[3])
            h1 = max(1.0, float(b1[3] - b1[1]))
            for j in range(i + 1, len(boxes)):
                b2 = boxes[j]
                f2x, f2y = (b2[0] + b2[2]) * 0.5, float(b2[3])
                h2 = max(1.0, float(b2[3] - b2[1]))
                gap = math.hypot(f2x - f1x, f2y - f1y) / (0.5 * (h1 + h2))
                if compute_iou(b1, b2) > 0.02:
                    return n, 0.0
                if gap < min_gap:
                    min_gap = gap
        return n, min_gap

    def _adapt_profile(self, detections):
        '''按"目标间最近间距"切换跟踪档位（滞回 + 连续帧去抖）。
        有 >=2 个目标且最近间距 <= _CROWD_NEAR_GAP → 保守档（记忆短、找回半径小、
        匹配严）；只有一个目标或任两目标间距 >= _CROWD_FAR_GAP → 强化档
        （记忆长、找回半径大、匹配较宽）；_CROWD_ALWAYS 只作人多时的兜底。
        基准参数保持不变，档位只在其上做倍率，可反复切换。'''
        if self.crowded and len(detections) >= _CROWD_ALWAYS:
            self._crowd_streak = 0
            return
        n_visible, min_gap = self._scene_risk(detections)
        if self.crowded:
            risky = ((n_visible >= 2 and min_gap < _CROWD_FAR_GAP)
                     or n_visible >= _CROWD_ALWAYS)
        else:
            risky = ((n_visible >= 2 and min_gap <= _CROWD_NEAR_GAP)
                     or n_visible >= _CROWD_ALWAYS)
        if risky == self.crowded:
            self._crowd_streak = 0
            return
        if self.crowded is not None:            # 首帧直接定档，不做去抖
            self._crowd_streak += 1
            if self._crowd_streak < _CROWD_SWITCH_FRAMES:
                return
        self._crowd_streak = 0
        self.crowded = risky
        scales = _CROWDED_SCALE if risky else _SPARSE_SCALE
        for name, factor in scales.items():
            base = self._base_params[name]
            value = int(round(base * factor)) if isinstance(base, int) else base * factor
            if name == 'max_lost_frames' and self.max_lost_cap:
                value = min(value, max(self.max_lost_cap, base))
            setattr(self, name, _clamp_param(name, value))
        gap_txt = ('%.2f倍框高' % min_gap) if min_gap != float('inf') else '单目标'
        logging.info('[tracking] 切换%s档位：可见目标=%d 最近间距=%s iou阈=%.2f LOST窗口=%d帧 '
                     'ReID=%dpx/阈值%.2f',
                     '拥挤(保守)' if risky else '稀疏(强化)', n_visible, gap_txt,
                     self.iou_thresh, self.max_lost_frames, self.reid_max_dist,
                     self.reid_score_thresh)

    def _register_cross(self, trk, event, tag='过线'):
        '''记录一次过线事件，并使用录像共用的帧时间标注计数时段。'''
        now_ts = time.time() if self.frame_timestamp is None else self.frame_timestamp
        self.last_cross_ts = now_ts
        if self.first_cross_ts is None:
            self.first_cross_ts = now_ts   # 视频预录独立保留过线前画面
        if event == 'enter':
            self.enter_count += 1
            self.total_enter_all += 1                   # 全局累计不随会话重置
        elif event == 'exit':
            self.exit_count += 1
            self.total_exit_all += 1
        logging.info('[%s] 轨迹 #%d %s，会话进入=%d 离开=%d | 全局累计进入=%d 离开=%d' % (
            tag, trk.track_id, '进入' if event == 'enter' else '离开',
            self.enter_count, self.exit_count, self.total_enter_all, self.total_exit_all))
        # 缓存本次过线事件（含目标框 [x1,y1,x2,y2]），供 on_result 取过线画面并存图
        self.cross_events.append((trk.track_id,
                                  [int(v) for v in trk.bbox], event))

    def _check_crossing(self, trk, frame_bgr):
        _observe_gate(self, trk, frame_bgr)

    def update(self, detections, frame_timestamp=None, frame_continuous=None, frame_bgr=None):
        '''跟踪器主更新入口：IoU 匹配 → 过线检测 → 丢失轨迹 Re-ID → 新建轨迹 → 清理超龄轨迹。
        detections 为 (bbox, cls, conf) 列表，返回 ACTIVE 轨迹列表。'''
        self._adapt_profile(detections)     # 先按本帧目标间距定档位（滞回+去抖）
        _set_frame_timestamp(self, frame_timestamp, frame_continuous)
        self.frame_no += 1
        n_det = len(detections)
        active = [t for t in self.tracks if t.state == _LineTrack.STATE_ACTIVE]
        appearance = [_LineTrack.sample_appearance(frame_bgr, box) for box, _, _ in detections]
        matched_det = set()
        matched_trk = set()
        if active and n_det > 0:
            boxes = [bbox for bbox, _, _ in detections]
            iou_mat = _pairwise_iou([trk.bbox for trk in active], boxes)
            predicted_rows = []
            predicted_boxes = []
            for ti, trk in enumerate(active):
                # 快速移动时保留预测框参与匹配；慢速目标只比较当前框。
                vx, vy = trk.velocity
                if (vx * vx + vy * vy) ** 0.5 >= _PRED_MATCH_MIN_SPEED:
                    predicted_rows.append(ti)
                    predicted_boxes.append(trk.predict_bbox(1))
            if predicted_rows:
                iou_mat[predicted_rows] = np.maximum(
                    iou_mat[predicted_rows], _pairwise_iou(predicted_boxes, boxes))
            # Near-tied associations can join two different people across a gate.
            # Start fresh with the next unambiguous observation on either side.
            ambiguous = set()
            for ti, di, near_tie in self._associations(iou_mat, self.iou_thresh):
                bbox, cls, conf = detections[di]
                if cls != active[ti].cls or not active[ti].accepts_continuous_match(bbox, appearance[di]):
                    continue
                if near_tie:
                    active[ti].measured_crossing.reset()
                    active[ti].foot_history.clear()
                    ambiguous.add(active[ti].track_id)
                active[ti].update(bbox, cls, conf, self.frame_no)
                active[ti].appearance = appearance[di]
                matched_det.add(di)
                matched_trk.add(active[ti].track_id)
            if self.counting_line:
                for trk in active:
                    if trk.track_id in matched_trk and trk.track_id not in ambiguous:
                        self._check_crossing(trk, frame_bgr)
        # Finish both association passes on the same sample before declaring
        # a missed observation. A quick, uniquely matched adjacent detection
        # is still a real step even when primary IoU was below its threshold.
        remaining = [t for t in self.tracks if t.track_id not in matched_trk]
        unmatched_dets = [i for i in range(n_det) if i not in matched_det]
        if remaining and unmatched_dets:
            scores = np.zeros((len(remaining), len(unmatched_dets)), dtype=float)
            for ti, trk in enumerate(remaining):
                frame_gap = self.frame_no - trk.last_frame
                for ci, di in enumerate(unmatched_dets):
                    bbox, cls, _ = detections[di]
                    if cls != trk.cls:
                        continue
                    if trk.state == _LineTrack.STATE_ACTIVE and not trk.accepts_continuous_match(bbox, appearance[di]):
                        continue
                    scores[ti, ci] = _line_reid_score(
                        trk, _LineTrack._bbox2foot(bbox), bbox, frame_gap, max_dist=self.reid_max_dist)
            viable = scores >= self.reid_score_thresh
            row_candidates = viable.sum(axis=1)
            col_candidates = viable.sum(axis=0)
            for ti, ci, near_tie in self._associations(scores, self.reid_score_thresh):
                trk, di = remaining[ti], unmatched_dets[ci]
                bbox, cls, conf = detections[di]
                rivals = col_candidates[ci]
                # A stale projection alone cannot invalidate a clear, short-gap return.
                gap = self.frame_no - trk.last_frame
                if (self.model_profile == 'full_body' and rivals > 1 and gap <= 9 and not near_tie
                        and trk.accepts_continuous_match(bbox, appearance[di])):
                    overlap = compute_iou(trk.bbox, bbox)
                    if overlap > 0 and max(overlap, compute_iou(trk.predict_bbox(gap), bbox)) >= .5:
                        rivals = sum(1 for k in np.flatnonzero(viable[:, ci])
                                     if self.frame_no - remaining[k].last_frame <= 9
                                     or compute_iou(remaining[k].bbox, bbox) > 0)
                uncertain = near_tie or row_candidates[ti] != 1 or rivals != 1
                if uncertain:
                    trk.measured_crossing.reset()
                    trk.foot_history.clear()
                if trk.state == _LineTrack.STATE_LOST:
                    trk.reidentify(bbox, cls, conf, self.frame_no)
                else:
                    trk.update(bbox, cls, conf, self.frame_no)
                trk.appearance = appearance[di]
                matched_det.add(di)
                matched_trk.add(trk.track_id)
                if self.counting_line and not uncertain:
                    self._check_crossing(trk, frame_bgr)
        newly_lost_ids = set()
        for trk in active:
            if trk.track_id not in matched_trk:
                trk.mark_lost()
                newly_lost_ids.add(trk.track_id)
        # LOST 轨迹逐帧老化（05_1 移植）：本帧未被 Re-ID 回、也不是刚转 LOST 的轨迹 lost_frames+1，
        # 否则旧 LOST 轨迹的 lost_frames 永远停在 1、达不到删除阈值（轨迹越积越多且易误 Re-ID）
        for trk in self.tracks:
            if (trk.state == _LineTrack.STATE_LOST
                    and trk.track_id not in matched_trk
                    and trk.track_id not in newly_lost_ids):
                trk.lost_frames += 1
        for di in range(n_det):
            if di in matched_det:
                continue
            bbox, cls, conf = detections[di]
            new_trk = _LineTrack(bbox, cls, conf, self.frame_no)
            if self.model_profile in ('head_shoulder', 'full_body'):
                new_trk.measured_crossing = VisualCrossing(new_trk.measured_crossing, self.model_profile)
            elif self.full_body:
                new_trk.measured_crossing = FullBodyCrossing(new_trk.measured_crossing)
            new_trk.appearance = appearance[di]
            self.tracks.append(new_trk)
            if self.counting_line:
                self._check_crossing(new_trk, frame_bgr)
        survivors = []
        for t in self.tracks:
            if t.state == _LineTrack.STATE_LOST and t.lost_frames > self.max_lost_frames:
                if t.track_end_ts is None:
                    t.track_end_ts = time.time()
            else:
                survivors.append(t)
        self.tracks = survivors
        # 维护「画面无活跃轨迹」的起始时间（会话结束判定用）
        if len(self.active_tracks) == 0:
            if self.no_active_since is None:
                self.no_active_since = time.time()
        else:
            self.no_active_since = None
        return self.active_tracks

    def pop_cross_events(self):
        '''取出并清空本帧累积的过线事件，返回 [(track_id, [x1,y1,x2,y2], event_type), ...]。'''
        events = self.cross_events
        self.cross_events = []
        return events

    def check_activity_timeout(self, timeout=5):
        """Settle idle sessions and cap busy sessions while their footage is retained."""
        if self.first_cross_ts is None or self.last_cross_ts is None:
            return None
        now_ts = time.time()
        no_active_gap = None if self.no_active_since is None else now_ts - self.no_active_since
        media_now = now_ts if self.frame_timestamp is None else self.frame_timestamp
        total_life = media_now - self.first_cross_ts
        if total_life >= _SESSION_MAX_SEC or (no_active_gap is not None and no_active_gap >= timeout):
            session_info = {
                'start_time': datetime.fromtimestamp(self.first_cross_ts),
                'end_time': datetime.fromtimestamp(self.last_cross_ts),
                'enter_count': self.enter_count,
                'exit_count': self.exit_count,
            }
            self._reset_session()
            return session_info
        return None

    def _reset_session(self):
        '''会话结算后重置：仅清空会话临时计数与时间标记，全局永久累计保留不清零。'''
        self.enter_count = 0
        self.exit_count = 0
        self.first_cross_ts = None
        self.last_cross_ts = None
        self.no_active_since = None


def get_arrow_side_point(start, end, direction, distance=10):
    """根据箭头起点/终点/方向，生成箭头左侧或右侧的坐标点。"""
    s = np.array(start, dtype=np.float32)
    e = np.array(end, dtype=np.float32)
    dir_vec = e - s
    norm = np.linalg.norm(dir_vec)
    if norm < 1e-6:
        return start
    u = dir_vec / norm
    perp_left = np.array([-u[1], u[0]])
    mid = (s + e) / 2.0
    if str(direction).lower() == "left":
        side_point = mid - perp_left * distance
    else:
        side_point = mid + perp_left * distance
    return (int(side_point[0]), int(side_point[1]))


def snapshot_tracker(tracker):
    '''在回调线程内生成轻量绘制快照，避免 draw/upload 与跟踪器并发访问。'''
    track_list = []
    for t in tracker.active_tracks:
        track_list.append({
            'track_id': t.track_id,
            'bbox': tuple(int(v) for v in t.bbox),
            'foot_history': list(t.foot_history),
            'start_ts': t.first_appear_ts,
            'last_active_ts': t.last_active_ts,
            'end_ts': t.track_end_ts,
        })
    return {'enter': tracker.enter_count, 'exit': tracker.exit_count,
            'total_enter_all': tracker.total_enter_all, 'total_exit_all': tracker.total_exit_all,
            'tracks': track_list}


_COUNT_FONT_FALLBACK = False

def draw_count_overlay(image, snap, font_path='fonts/wqy-microhei.ttc'):
    '''绘制活跃轨迹、脚底点和右上角累计进出统计面板。'''
    global _COUNT_FONT_FALLBACK

    # 轨迹绘制增加异常捕获，防止单条轨迹报错阻断面板渲染
    try:
        for track_dict in snap.get('tracks', []):
            tid = track_dict.get('track_id', -1)
            bbox = track_dict.get('bbox', [0,0,0,0])  # 修复：track_dict['bbox']
            foots = track_dict.get('foot_history', [])

            # 绘制轨迹连线，增加长度判断防越界
            if len(foots) >= 2:
                for i in range(1, len(foots)):
                    pt_prev = foots[i - 1]
                    pt_curr = foots[i]
                    # 过滤非法坐标
                    if len(pt_prev) <2 or len(pt_curr) <2:
                        continue
                    alpha = int(200 * i / len(foots))
                    cv2.line(
                        image,
                        (int(pt_prev[0]), int(pt_prev[1])),
                        (int(pt_curr[0]), int(pt_curr[1])),
                        (0, alpha, 255 - alpha),
                        2
                    )
            # 绘制当前脚底圆点
            if foots and len(foots[-1]) >=2:
                last_pt = foots[-1]
                cv2.circle(
                    image,
                    (int(last_pt[0]), int(last_pt[1])),
                    4, (0, 255, 0), -1
                )
            # 绘制目标ID文字
            x_b, y_b = int(bbox[0]), int(bbox[1]) - 5
            cv2.putText(
                image, f'#{tid}',
                (x_b, y_b),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (0, 255, 0), 2
            )
    except Exception as track_err:
        # 轨迹绘制报错仅打印，不阻断右上角统计面板
        print(f"[track draw warn] 轨迹渲染异常，忽略轨迹不影响计数面板: {track_err}")

    all_enter = snap.get('total_enter_all', 0)
    all_exit = snap.get('total_exit_all', 0)
    diff = all_enter - all_exit
    if diff > 0:
        title_cn, title_en = '净进入', 'Net Enter'
    elif diff < 0:
        title_cn, title_en = '净离开', 'Net Exit'
    else:
        title_cn, title_en = '净进出', 'Net'
    colors = ((0, 220, 0), (0, 60, 220), (0, 220, 255))
    image_h, image_w = image.shape[:2]
    size = max(14, min(40, round(image_h * 26 / 1080)))
    gap = max(6, round(size * 0.3))
    x1, y0 = image_w - gap, gap
    y1 = min(image_h, y0 + 3 * (size + gap) + gap)

    if not _COUNT_FONT_FALLBACK:
        try:
            labels = (f'累计进入：{all_enter}', f'累计离开：{all_exit}', f'{title_cn}：{abs(diff)}')
            bitmaps = [_get_pil_text_bitmap(label, font_path, size, tuple(reversed(color)))
                       for label, color in zip(labels, colors)]
            width = max(alpha.shape[1] for _, alpha in bitmaps) + 2 * gap
            x0 = max(0, x1 - width)
            image[y0:y1, x0:x1] = (24, 29, 36)
            for index, (bmp, alpha) in enumerate(bitmaps):
                top = y0 + gap + index * (size + gap)
                _paste_text_bitmap_bgr(image, bmp, alpha, x0 + gap, top)
            return
        except Exception as e:
            _COUNT_FONT_FALLBACK = True
            print('[counting] 中文字体加载失败(%s)，计数面板退回英文: %s' % (font_path, e))

    labels = (f'Total Enter: {all_enter}', f'Total Exit: {all_exit}', f'{title_en}: {abs(diff)}')
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = size / 30
    width = max(cv2.getTextSize(label, font, scale, 1)[0][0] for label in labels) + 2 * gap
    x0 = max(0, x1 - width)
    image[y0:y1, x0:x1] = (24, 29, 36)
    for index, (label, color) in enumerate(zip(labels, colors)):
        baseline = y0 + gap + index * (size + gap) + size
        cv2.putText(image, label, (x0 + gap, baseline), font, scale, color, 1, cv2.LINE_AA)

def _extract_upload_meta(item):
    '''提取会话上报（upload_hwj）所需字段。'''
    g = item.get
    return {
        'conf_id': g('conf_id') or g('config_id'),
        'res_type': g('res_type'),
        'Equipment_id': g('Equipment_id') or g('equipment_id'),
        'Mine_id': g('Mine_id') or g('mine_id'),
        'mine_code': g('mine_code'),
        'template_config_type_id': g('template_config_type_id') or g('template_type_id'),
        'template_id': g('template_id'),
        'conf_name': g('conf_name') or g('name'),
        'equipment_name': g('equipment_name'),
        'equipment_ip': g('equipment_ip'),
        'Algorithm_library_id': g('Algorithm_library_id') or g('algorithm_library_id'),
    }


class CountingContext:
    '''一路"人数统计"算法的运行态：计数线 + 跟踪器 + 会话上传元数据。
    帧数型阈值按 ~8fps 标定，这里按实际推理帧率 fps_eff 等比放大，保持时间语义不变。'''

    def __init__(self, model_cfg, fps_eff, init_enter_all=0, init_exit_all=0, managed_counts=False):
        cl = model_cfg.get('cross_line') or {}
        self.boarding = cl if cl.get('scene') == 'boarding' else None
        self.config_cross_line = cl
        self.config_resolution = parse_config_resolution(model_cfg.get('conf_img_resolution'))
        self.geometry_size = None
        self.cross_lines_plans = []
        self.line = None
        scale = max(1.0, fps_eff / 8.0)
        tracker_type = Tracker if self.boarding else _LineTracker
        tracker_options = {} if self.boarding else {
            'model_profile': model_cfg.get('count_model_profile'),
            'max_lost_cap': int(fps_eff * max(1.0, _SESSION_TIMEOUT_SEC - 1.0)),
        }
        self.tracker = tracker_type(
            iou_thresh=_IOU_MATCH_THRESH,
            max_lost_frames=int(_LOST_WINDOW_FRAMES * scale),
            reid_max_dist=_REID_MAX_DIST_PX,
            reid_score_thresh=_REID_SCORE_THRESH,
            counting_line=self.line,
            init_enter_all=init_enter_all, init_exit_all=init_exit_all,
            **tracker_options)
        logging.info('[counting] 跟踪容错: LOST窗口=%d帧(≈%.1fs) ReID距离=%dpx 阈值=%.2f',
                     self.tracker.max_lost_frames, _LOST_WINDOW_FRAMES / 8.0,
                     self.tracker.reid_max_dist, self.tracker.reid_score_thresh)
        if not self.boarding:
            # Disconnected/paused streams can jump in time between callback invocations.
            self.tracker.max_observation_gap = max(0.5, 2.5 / max(0.1, fps_eff))
        self.upload_meta = model_cfg.get('upload_meta') or {}
        self.count_replica = (CountReplica(self.upload_meta['conf_id'], init_enter_all, init_exit_all)
                              if managed_counts else None)
        # 绘制的警戒区域多边形（conf_area）：非空时对跟踪输入做前置过滤，
        # 只有脚底点落在任一区域内的检测框才参与跟踪/计数（空=不过滤，全图计数）
        self.config_regions_np = model_cfg.get('display_regions_np') or []
        self.display_regions_np = self.config_regions_np
        self.last_snap = None
        self.last_visible = {}
        conf_name = (self.upload_meta.get('conf_name') or model_cfg.get('name') or 'People_Counting')
        stem = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
        out_dir = alarm_directory.relocate(os.path.join('/data/AIGO/outputs', stem, 'result', str(conf_name), 'images'))
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'count_results', str(conf_name))
            os.makedirs(out_dir, exist_ok=True)
        self.output_img_dir = out_dir

    def ensure_line(self, w, h):
        '''在当前帧坐标系中构建计数和绘制共用的几何。'''
        if self.geometry_size == (w, h) or min(w, h) <= 0:
            return
        source_w, source_h = self.config_resolution or (w, h)
        sx, sy = w / source_w, h / source_h
        cl = self.config_cross_line
        if self.boarding:
            points = [(x * sx, y * sy) for x, y in cl['points']]
            direction = cl['boarding_direction']
            line = BoardingCountingRegion(points, direction, cl['min_residence_frames'])
            plan = _boarding_arrow_plan(points, w, h)
            if direction == 'outward' and 'mid' in plan:
                plan = dict(plan, in_tip=plan['out_tip'], out_tip=plan['in_tip'],
                            in_dir=plan['out_dir'], out_dir=plan['in_dir'])
            plans = [plan]
        else:
            if cl:
                points = [(round(x * sx), round(y * sy)) for x, y in cl['points']]
                direction = cl.get('direction', 'right')
            else:
                points = [(0, h // 2), (w, h // 2)]
                direction = 'left'
            line = PolylineCountingLine(points, direction)
            plans = precompute_cross_lines([{'points': points, 'direction': direction}])
            self.display_regions_np = [np.rint(poly * (sx, sy)).astype(np.int32)
                                       for poly in self.config_regions_np]
            line.count_regions = self.display_regions_np
        if self.geometry_size is not None:
            # 丢弃不同坐标系下的轨迹与绘制快照，保留累计进出人数。
            if self.count_replica is not None:
                self.count_replica.close_discontinuity(self.tracker)
                self.tracker._reset_session()
            self.tracker.tracks.clear()
            self.tracker.cross_events.clear()
            self.last_snap = None
            self.last_visible.clear()
        self.line = self.tracker.counting_line = line
        self.cross_lines_plans = plans
        self.geometry_size = (w, h)
        logging.info('[geometry] 配置图=%dx%d 当前帧=%dx%d 警戒线=%s',
                     source_w, source_h, w, h, points)

    def update(self, result_lst, w, h, frame_timestamp=None, frame_continuous=None, frame_bgr=None):
        '''把本帧检测结果喂给跟踪器做过线计数，返回会话结束信息 dict（未结束返回 None）。'''
        self.ensure_line(w, h)
        dets = []
        for it in result_lst:
            box = it[2]
            try:
                conf = float(it[1])
            except (TypeError, ValueError):
                conf = 0.0
            dets.append(([int(box[0]), int(box[1]), int(box[2]), int(box[3])], it[0], conf))
        # 区域、轨迹和警戒线都使用实际检测框底边中点。
        if not self.boarding and self.display_regions_np:
            points = (_LineTrack._bbox2foot(d[0]) for d in dets)
            dets = [d for d, point in zip(dets, points)
                    if any(cv2.pointPolygonTest(poly, point, False) >= 0 for poly in self.display_regions_np)]
        if self.count_replica is not None:
            previous = self.count_replica.before_frame(self.tracker)
        if self.boarding:
            self.tracker.update(dets, frame_timestamp, frame_continuous)
        else:
            self.tracker.update(dets, frame_timestamp, frame_continuous, frame_bgr=frame_bgr)
        if self.count_replica is not None:
            self.count_replica.after_frame(self.tracker, previous)
        ended = self.tracker.check_activity_timeout(timeout=_SESSION_TIMEOUT_SEC)
        if ended is not None and self.count_replica is not None:
            return self.count_replica.seal(self.tracker, ended['end_time'].timestamp())
        return ended


def _uwb_verify_and_alarm(session_info, meta, carousel_url, ori_url, conf_name):
    '''UWB 定位卡人数核验（移植自 People_Counting05_1）：把会话进出人数与 UWB 定位卡数据比对，
    result=1 疑似有人携带多张定位卡、result=-1 疑似有人未携带定位卡，异常时追加一条带
    result_alarm/result_card_id 的告警上报（起止时间各外扩 3s）；核验失败仅写日志，不影响常规上报。'''
    try:
        start_str = (session_info['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                     if session_info.get('start_time') else '')
        end_str = (session_info['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                   if session_info.get('end_time') else '')
        result, card_id = _uwb_check(_UWB_DB_PATH, start_str, end_str,
                                     session_info['enter_count'], session_info['exit_count'],
                                     max_distance=None)
        if result == 1:
            logging.info('疑似有人携带多张定位卡 card_id=%s', card_id)
        elif result == -1:
            logging.info('疑似有人未携带定位卡 card_id=%s', card_id)
        else:
            return
        data_send.upload_hwj(
            Algorithm_conf_id=meta.get('conf_id'), res_type=meta.get('res_type'),
            Equipment_id=meta.get('Equipment_id'), carousel_images_list=carousel_url, ori_images_list=ori_url,
            result_count=0, result_card_id=card_id, result_alarm=result,
            Entering_num=session_info['enter_count'], Exiting_num=session_info['exit_count'],
            # 平台读 result_count_time 作报警开始时间：与下方 start_time 同为外扩 3s 的起点
            # （旧版传上报时刻 now()，与外扩窗口口径不一致）
            result_count_time=str((session_info['start_time'] - timedelta(seconds=3)).strftime('%Y-%m-%d %H:%M:%S')
                                  if session_info.get('start_time') else ''),
            template_type_id=meta.get('template_config_type_id'), template_id=meta.get('template_id'),
            start_time=str((session_info['start_time'] - timedelta(seconds=3)).strftime('%Y-%m-%d %H:%M:%S')
                           if session_info.get('start_time') else ''),
            res_time=str((session_info['end_time'] + timedelta(seconds=3)).strftime('%Y-%m-%d %H:%M:%S')
                         if session_info.get('end_time') else ''),
            conf_name=conf_name, equipment_name=meta.get('equipment_name'),
            equipment_ip=meta.get('equipment_ip'), Algorithm_library_id=meta.get('Algorithm_library_id'),
            Mine_id=meta.get('Mine_id'), mine_code=meta.get('mine_code'),
            # UWB 告警是同一会话的衍生告警，复用该会话的报警视频
            warning_video=session_info.get('warning_video'),
            count_state_managed=meta.get('count_state_managed') is True)
    except Exception:
        logging.exception('[uwb] 定位卡核验/上报失败（不影响常规会话上报）')


def _counting_restart_seed(outbox, entered, exited, defense_time_start):
    '''Kafka 积压时按本布防周期的最后一条结算继续累计。'''
    incoming = _safe_int(entered), _safe_int(exited)
    try:
        defense_start = datetime.strptime(defense_time_start, '%H:%M:%S').time()
    except (TypeError, ValueError):
        return incoming
    now = datetime.now()
    boundary = datetime.combine(now.date(), defense_start)
    if now < boundary:
        boundary -= timedelta(days=1)
    # 保留调度器在布防开始 5 秒窗口内传入的显式清零。
    if incoming == (0, 0) and now - boundary <= timedelta(seconds=5):
        return incoming
    snapshot = outbox.last_staged()
    if snapshot is None:
        return incoming
    try:
        settled = datetime.strptime(snapshot['res_time'], '%Y-%m-%d %H:%M:%S')
        recovered = snapshot['all_Entering_num'], snapshot['all_Exiting_num']
    except (KeyError, TypeError, ValueError):
        return incoming
    if (boundary <= settled <= now and all(type(value) is int and value >= seed
                                            for value, seed in zip(recovered, incoming))):
        return recovered
    return incoming


def _uwb_after_count_delivery(payload):
    """普通会话确认送达后，再执行可选定位卡核验。"""
    session_info = {
        'start_time': datetime.fromisoformat(payload['start_time']),
        'end_time': datetime.fromisoformat(payload['res_time']),
        'enter_count': payload['Entering_num'],
        'exit_count': payload['Exiting_num'],
        'warning_video': payload.get('warning_video'),
    }
    meta = dict(payload, conf_id=payload['Algorithm_conf_id'],
                template_config_type_id=payload['template_type_id'])
    _uwb_verify_and_alarm(session_info, meta, payload['carousel_images_list'],
                          payload['ori_images_list'], payload['conf_name'])


def _draw_capture_time(image, snap):
    stamp = snap.get('capture_timestamp')
    if stamp is None:
        return
    clock = datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S')
    kind = snap.get('evidence_kind')
    height, width = image.shape[:2]
    size = max(12, min(30, round(height * 22 / 1080)))
    gap = max(4, round(size * 0.3))
    white = (255, 255, 255)
    bottom = height - gap
    try:
        label = {'last_visible': '末次可见画面 · 平台时间',
                 'inferred_crossing': '推断过线 · 重新检出时间'}.get(kind, '平台抓拍时间')
        bitmap, alpha = _get_pil_text_bitmap(f'{label} {clock}', snap['font_path'], size, white)
        top = max(0, bottom - alpha.shape[0] - 2 * gap)
        image[top:bottom, gap:min(width, alpha.shape[1] + 3 * gap)] = (24, 29, 36)
        _paste_text_bitmap_bgr(image, bitmap, alpha, 2 * gap, top + gap)
    except Exception:
        label = {'last_visible': 'Platform last visible',
                 'inferred_crossing': 'Inferred crossing - reacquired'}.get(kind, 'Platform capture')
        label = f'{label} {clock}'
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = size / 32
        (text_width, text_height), baseline = cv2.getTextSize(label, font, scale, 1)
        top = max(0, bottom - text_height - baseline - 2 * gap)
        image[top:bottom, gap:min(width, text_width + 3 * gap)] = (24, 29, 36)
        cv2.putText(image, label, (2 * gap, bottom - gap - baseline), font, scale,
                    white, 1, cv2.LINE_AA)


def _render_count_alarm(frame, snap, bbox, direction):
    """在独立副本上画过线人体框、检测区域、计数线及本次累计人数。"""
    image = frame.copy()
    draw_alarm_regions(image, snap['regions'], color_bgr=snap['region_color'], fill_alpha=0.0)
    draw_cross_lines(image, snap['lines'])
    x1, y1, x2, y2 = bbox
    color = (0, 255, 0) if direction == 'enter' else (0, 80, 255)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3, cv2.LINE_AA)
    draw_count_overlay(image, dict(snap, tracks=[]), snap['font_path'])
    _draw_capture_time(image, snap)
    return image


def _render_count_scene(frame, snap):
    image = frame.copy()
    draw_alarm_regions(image, snap['regions'], color_bgr=snap['region_color'], fill_alpha=0.0)
    draw_cross_lines(image, snap['lines'])
    for track in snap['tracks']:
        x1, y1, x2, y2 = track['bbox']
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 200, 0), 2)
    draw_count_overlay(image, snap, snap['font_path'])
    return image


def _save_count_capture(media, stem, frame, snap, bbox, direction, out_dir):
    for kind, field in (('original', 'ori_images_list'), ('alarm', 'carousel_images_list')):
        path = os.path.join(out_dir, '%s_%s.jpg' % (kind, stem))
        try:
            path = alarm_directory.relocate(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            image = frame if kind == 'original' else _render_count_alarm(frame, snap, bbox, direction)
            if not cv2.imwrite(path, image):
                raise OSError('cv2.imwrite returned False')
            media[field].append(alarm_directory.media_url(path, cm.localhost_ip, port))
            if kind == 'alarm' and snap.get('capture_timestamp') is not None:
                media.setdefault('evidence_frames', []).append((
                    os.path.basename(path), snap['capture_timestamp'], snap['evidence_kind']))
        except Exception:
            logging.exception('[counting] 过线图片保存失败: %s', path)


def counting_upload_worker(upload_q, stop_event, outbox, capture_slots):
    """先按入队顺序保存各次越线图片，再完成对应会话的持久化上报。"""
    while not stop_event.is_set() or not upload_q.empty():
        try:
            kind, entry = upload_q.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            if kind == 'capture':
                _save_count_capture(*entry)
            else:
                event_id, payload, session_info, media = entry
                evidence_frames = media.pop('evidence_frames', ())
                entered, exited = payload['Entering_num'], payload['Exiting_num']
                analysis = '0102' if entered and exited else '02' if exited else '01'
                try:
                    media['warning_video'] = alarm_video.trigger(
                        payload['conf_name'], alarm_ts=session_info['end_time'].timestamp(),
                        start_ts=session_info['start_time'].timestamp(), analysis_type=analysis,
                        **({'images': evidence_frames} if evidence_frames else {}))
                except Exception:
                    logging.exception('[counting] 会话录像准备失败')
                outbox.complete(event_id, **media)
                logging.info('[会话报警] 进入=%d 离开=%d 报警图=%d 原图=%d ID=%s',
                             entered, exited,
                             len(media['carousel_images_list']), len(media['ori_images_list']), event_id)
        except Exception:
            logging.exception('[counting] 人数统计媒体任务失败: %s', kind)
        finally:
            if kind == 'capture':
                capture_slots.release()
            upload_q.task_done()
            del entry


def build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence,
               conf_area, algorithm_type_list, test_type_ename, sensitivity,
               conf_id, Equipment_id, template_config_type_id, template_id, conf_name,
               equipment_name, equipment_ip, interval_time, template_list_area, image_count,
               template_data, conf_status, res_type, template_small_name, Algorithm_library_id,
               conf_img_resolution, defense_time_start, defense_time_end, duration_time,all_Entering_num,all_Exiting_num,
               cross_line_area, label_prefix='', names_cn=None, Mine_id=None, mine_code=None,
               region_color=None, managed_counts=False, analysis_type=None):
    '''整理为任务条目：{'spec': model_spec(含计数 on_result), + 流参数提示}。
    推理间隔取任务配置的间隔帧数，缺省为 2；
    conf_area 报警区域：推流画面常显，且非空时作为跟踪输入的前置过滤
    （脚底点在区域内的检测框才参与计数，见 CountingContext.update）。
    region_color: 报警区域推流描边色（多任务同流时按任务区分，None=默认红色）。'''
#    all_Entering_num,all_Exiting_num = 0, 0
    if not algorithm_path:
        algorithm_path = _LEGACY_DEFAULT_MODEL
        print('[method] DB 未给出 algorithm_path，回退默认模型: %s' % algorithm_path)

    names_en = _parse_label_list(algorithm_type_list) or ['目标']
    allow_names = set(_parse_label_list(test_type_ename))
    category_id = [i for i, nm in enumerate(names_en) if nm in allow_names] if allow_names else []
    # 推流画面标签：优先用中文类名（需与 algorithm_type_list 同序、等长），否则回退英文
    disp_names = names_cn if (isinstance(names_cn, list) and len(names_cn) == len(names_en)) else names_en
    obj_thresh = _parse_thresh(confidence, 0.5)
    # 平台 sensitivity 是检测间隔帧数；同类框的去重阈值独立于采样频率。
    nms_thresh = 0.45

    display_regions_np = _polygons_to_np(_parse_conf_area(conf_area))
    cross_line = _parse_cross_line_area(cross_line_area)

    fps = 25
    extract_count = _safe_int(sensitivity, 2)
    if extract_count < 1:
        extract_count = 2
    fps_eff = float(fps) / max(1, extract_count)
    upload_meta = _extract_upload_meta({
        'conf_id': conf_id, 'res_type': res_type, 'Equipment_id': Equipment_id,
        'template_config_type_id': template_config_type_id, 'template_id': template_id,
        'conf_name': conf_name, 'equipment_name': equipment_name, 'equipment_ip': equipment_ip,
        'Algorithm_library_id': Algorithm_library_id, 'Mine_id': Mine_id, 'mine_code': mine_code})
    outbox = CountAlarmOutbox(conf_id)
    all_Entering_num, all_Exiting_num = _counting_restart_seed(
        outbox, all_Entering_num, all_Exiting_num, defense_time_start)
    profile = count_model_profile(analysis_type, algorithm_path)
    counting_ctx = CountingContext({'name': conf_name, 'cross_line': cross_line, 'upload_meta': upload_meta,
                                    'count_model_profile': profile,
                                    'display_regions_np': display_regions_np,
                                    'conf_img_resolution': conf_img_resolution},
                                   fps_eff,
                                   init_enter_all=all_Entering_num, init_exit_all=all_Exiting_num,
                                   managed_counts=managed_counts)

    _ensure_count_logging()
    logging.info('[counting] 任务=%s 过线策略=%s', conf_id, 'boarding' if counting_ctx.boarding else profile)
    logging.info('[counting] 检测间隔=%d帧 名义推理帧率=%.1ffps 置信度=%.3f NMS IoU=%.3f',
                 extract_count, fps_eff, obj_thresh, nms_thresh)

    # 只限制持有图像的抓拍任务，轻量的会话结算不能因存图慢而阻塞推理。
    upload_q = queue.Queue()
    capture_slots = threading.BoundedSemaphore(8)
    upload_stop = threading.Event()
    if counting_ctx.count_replica is None:
        threading.Thread(target=counting_upload_worker, args=(upload_q, upload_stop, outbox, capture_slots),
                         daemon=True, name='count_media_%s' % conf_name).start()

    threading.Thread(target=outbox.run,
                     args=(upload_stop, data_send.upload_hwj if data_send is not None else None,
                           _uwb_after_count_delivery if _uwb_check is not None else None),
                     daemon=True, name='count_up_%s' % conf_name).start()

#    if data_send is not None:
#        try:
#            data_send.insert_alg_log(
#                ip_address="None", Level="INFO", message="%s 开始运行" % conf_name,
#                alg_name=conf_name, response_data=None, error_code=None, hostname=None)
#        except Exception as e:
#            print('[counting] insert_alg_log 失败:', e)

    font_path = 'fonts/wqy-microhei.ttc'
    alarm_id = None
    capture_index = 0
    media = {'carousel_images_list': [], 'ori_images_list': []}
    color = region_color or (0, 0, 255)

    def snapshot():
        snap = snapshot_tracker(counting_ctx.tracker)
        snap.update(regions=counting_ctx.display_regions_np, lines=counting_ctx.cross_lines_plans,
                    region_color=color, font_path=font_path)
        return snap

    managed_media = None
    if counting_ctx.count_replica is not None:
        managed_media = CountSessionMedia(counting_ctx, outbox, upload_stop, _render_count_alarm,
                                          _render_count_scene, snapshot)
        threading.Thread(target=managed_media.run, daemon=True, name='count_media_%s' % conf_name).start()

    def on_result(image_bgr, results, width, height, frame_timestamp=None, frame_continuous=None):
        """过线时保留独立整帧，JPEG 写入和报警标注由媒体线程执行。"""
        nonlocal alarm_id, capture_index, media
        tracker = counting_ctx.tracker
        stamp = time.time() if frame_timestamp is None else frame_timestamp
        if managed_media is not None:
            managed_media.current = image_bgr
        session_info = counting_ctx.update(results, width, height, stamp, frame_continuous, frame_bgr=image_bgr)
        if managed_media is not None:
            crossed = bool(tracker.pop_cross_events())
            managed_media.observed(stamp, bool(results), crossed)
            managed_media.current = None
            return
        snap = snapshot()
        counting_ctx.last_snap = snap
        cross_events = tracker.pop_cross_events()
        active = tracker.active_tracks
        evidence_kinds = {t.track_id: getattr(t.measured_crossing, 'evidence_kind', 'observed')
                          for t in active}
        # 乘车点按已观测到的分区轨迹在结算时统计，缓存其最后可见画面。
        cache_ids = []
        if counting_ctx.boarding:
            cache_ids = [t.track_id for t in active
                         if t.region_origin and t.region_state and t.region_origin != t.region_state]
        frame = None
        if cache_ids or any(tid in evidence_kinds for tid, _, _ in cross_events):
            try:
                frame = image_bgr.copy()
            except Exception:
                logging.exception('[counting] 无法复制过线画面')
        last_visible = counting_ctx.last_visible
        current_evidence = (frame, snap, stamp) if frame is not None else None
        if frame is not None:
            for tid in cache_ids:
                last_visible.pop(tid, None)
                last_visible[tid] = current_evidence
        if cross_events and alarm_id is None:
            alarm_id = uuid.uuid4().hex
        for tid, bbox, direction in cross_events:
            observed = tid in evidence_kinds and current_evidence is not None
            evidence = current_evidence if observed else last_visible.get(tid)
            capture_index += 1
            if evidence is None:
                logging.warning('[counting] 过线轨迹 #%d 缺少可见画面，人数仍正常上报', tid)
                continue
            original, visible_snap, capture_ts = evidence
            alarm_snap = dict(visible_snap, total_enter_all=snap['total_enter_all'],
                              total_exit_all=snap['total_exit_all'], capture_timestamp=capture_ts,
                              evidence_kind=evidence_kinds[tid] if observed else 'last_visible')
            stem = '%s_%06d' % (alarm_id, capture_index)
            capture_slots.acquire()
            upload_q.put_nowait(('capture', (media, stem, original, alarm_snap, bbox, direction,
                                            counting_ctx.output_img_dir)))
        live_ids = {track.track_id for track in tracker.tracks}
        for tid in last_visible.keys() - live_ids:
            del last_visible[tid]
        while len(last_visible) > _MAX_VISIBLE_EVIDENCE_TRACKS:
            del last_visible[next(iter(last_visible))]
        if session_info is not None:
            # 把全局累计注入会话信息，供上传 worker 携带总人数
            session_info['total_enter_all'] = tracker.total_enter_all
            session_info['total_exit_all'] = tracker.total_exit_all
            # Persist counts before the media worker reserves the clip and finalizes the record.
            payload = count_alarm_payload(counting_ctx.upload_meta, session_info,
                                          managed=counting_ctx.count_replica is not None)
            event_id = outbox.stage(payload, event_id=alarm_id)
            upload_q.put_nowait(('finish', (event_id, payload, session_info, media)))
            alarm_id = None
            capture_index = 0
            media = {'carousel_images_list': [], 'ori_images_list': []}

    def on_draw(image_bgr, width, height):
        '''推流帧常显叠加（报警区域/越线方向/计数面板；检测框由引擎统一绘制）。
        在所有 on_result 之后、每个推流帧调用一次，只动共享推流帧，不影响各任务报警存图。'''
        try:
            counting_ctx.ensure_line(width, height)
            if counting_ctx.display_regions_np:
                draw_alarm_regions(image_bgr, counting_ctx.display_regions_np, color_bgr=color, fill_alpha=0.0)
            draw_cross_lines(image_bgr, counting_ctx.cross_lines_plans)
            snap = counting_ctx.last_snap
            if snap is not None:
                draw_count_overlay(image_bgr, snap, font_path)
        except Exception as e:
            print('绘制异常（推原始帧继续）:', e)

    spec = make_model_spec(
        rknn_path=algorithm_path, names=disp_names, on_result=on_result, on_draw=on_draw,
        category_id=category_id, obj_thresh=obj_thresh, nms_thresh=nms_thresh, img_size=640,
        masks=_DEFAULT_MASKS, anchors=_DEFAULT_ANCHORS, label_prefix=label_prefix,
        extract_count=extract_count,
        draw_det_boxes=True, name=conf_name, result_frame_timestamp=True,
        result_frame_continuity=not counting_ctx.boarding)
    if profile == 'full_body' and cross_line and not counting_ctx.boarding:
        spec['full_body_line_search'] = FullBodyLineSearch(cross_line['points'], counting_ctx.config_resolution)

    return {
        'spec': spec,
        'rtsp_url': rtsp_url,
        'enc_type': 'h264',
        'extract_count': extract_count,
        'fps': fps,
        'push_url': _DEFAULT_PUSH_URL,
        'conf_name': conf_name,
        'upload_stop': upload_stop,
    }


def method(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence,
           conf_area, algorithm_type_list, test_type_ename, sensitivity,
           conf_id, Equipment_id, template_config_type_id, template_id, conf_name,
           equipment_name, equipment_ip, interval_time, template_list_area, image_count,
           template_data, conf_status, res_type, template_small_name, Algorithm_library_id,
           conf_img_resolution, defense_time_start, defense_time_end, duration_time,
           all_Entering_num, all_Exiting_num,
           cross_line_area=None, label_prefix='', names_cn=None, Mine_id=None, mine_code=None,
           analysis_type=None):
    '''单任务入口（一路流一模型 + 推流）：兼容旧调用方式。'''
    if not rtsp_status:
        return
    # 兼容 DB 字段可能为字符串/None 的情况
    all_enter_db = _safe_int(all_Entering_num)
    all_exit_db = _safe_int(all_Exiting_num)
    entry = build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence,
                       conf_area, algorithm_type_list, test_type_ename, sensitivity,
                       conf_id, Equipment_id, template_config_type_id, template_id, conf_name,
                       equipment_name, equipment_ip, interval_time, template_list_area, image_count,
                       template_data, conf_status, res_type, template_small_name, Algorithm_library_id,
                       conf_img_resolution, defense_time_start, defense_time_end, duration_time,
                       all_enter_db, all_exit_db,
                       cross_line_area, label_prefix=label_prefix, names_cn=names_cn,
                       Mine_id=Mine_id, mine_code=mine_code, analysis_type=analysis_type)
    cfg = build_stream_cfg(
        [entry['spec']], rtsp_url=entry['rtsp_url'], enc_type=entry['enc_type'],
        extract_count=entry['extract_count'], fps=entry['fps'], push_url=entry['push_url'])
    try:
        run(cfg)
    finally:
        entry['upload_stop'].set()


def main():
    '''板端调试入口。'''
    method(
        rtsp_status=1, args=None, template_name='人数统计类', algorithm_path=_LEGACY_DEFAULT_MODEL,
        rtsp_url='rtsp://127.0.0.1:8554/stream11', confidence='50', conf_area='',
        algorithm_type_list="['人头']", test_type_ename="['人头']", sensitivity='45',
        conf_id=0, Equipment_id=0, template_config_type_id=3, template_id=1, conf_name='people_count_debug',
        equipment_name='debug', equipment_ip='127.0.0.1', interval_time=1, template_list_area=[],
        image_count='5', template_data='[]', conf_status=1, res_type='1', template_small_name='人数统计',
        Algorithm_library_id=0, conf_img_resolution='1920x1080', defense_time_start='00:00:00',
        defense_time_end='23:59:59', duration_time=1, cross_line_area=None)


if __name__ == '__main__':
    main()
