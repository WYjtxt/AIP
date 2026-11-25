# -*- coding: utf-8 -*-
"""
跨越闸机（翻越闸机）— 平台引擎模板
=====================================================================
移植自 YOLOv8_pose/python/Jump.py（姿态版），判定链路完全一致：

  conf_area       : ROI 多边形（只用于画框/参考，判定靠 L1/L2 双线）
  cross_line_area : {"area_type":"dual_line",
                     "l1":{"p1":{"x":..,"y":..},"p2":{..}},   # 闸机挡板线（触碰线）
                     "l2":{"p1":{..},"p2":{..}},              # 通道前方完成线
                     "line_touch_dist":30}                    # 可选，默认取模板参数
  template_data   : 触碰距离 / 触碰超时帧 / 连续确认帧 / 报警冷却帧 / 关键点置信度

判定（严格顺序）：
  ① 姿态 classify_posture() == crossing（人跨在闸机上，躯干倾斜+手撑+头膝折叠）；
  ② 髋部触碰 L1（到 L1 线段垂距 <= 触碰距离）→ 记录起点帧，并缓存这一帧做报警图；
  ③ 触碰超时帧内，髋部明显越过 L2 的完成侧（在 L2 远离 L1 的一侧且距线 > 触碰距离）
     → 连续 N 帧 → 报警；
  ④ 报警冷却帧内不重复报警。
L2 的“完成侧”由几何自动确定：取 L1 中点相对 L2 的侧别的反侧，所以先画 L1（挡板）、
再画 L2（人翻过去落地的一侧）即可，不需要手工填方向。
"""
import os
import json
import time
import threading

import numpy as np
import cv2

from comm import data_send
from config import common as cm
from templates import rtsp_infer_push

log = rtsp_infer_push.logger

KPT_NUM = 17
DEF_TOUCH_DIST = 30       # 髋部到 L1/L2 的容差走廊（配置坐标像素）
DEF_TOUCH_TIMEOUT = 40    # 触碰 L1 后多少检测帧内必须完成
DEF_REQUIRE_FRAMES = 2    # 连续满足才报警
DEF_COOLDOWN = 30         # 报警后冷却检测帧
DEF_MAX_LOST = 8          # 丢失多少检测帧后删除轨迹
DEF_IOU = 0.3
DEF_KPT_CONF = 0.3

SKELETON = [[16, 14], [14, 12], [17, 15], [15, 13], [12, 13], [6, 12], [7, 13], [6, 7], [6, 8],
            [7, 9], [8, 10], [9, 11], [2, 3], [1, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5, 7]]
LIMB_COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
               (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
               (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
               (255, 0, 255), (255, 0, 170), (255, 0, 85), (255, 0, 0)]
L1_COLOR = (0, 255, 255)      # 黄（BGR）
L2_COLOR = (255, 100, 0)      # 蓝
ROI_COLOR = (0, 215, 255)


# ===================== 配置解析 =====================
def _pt(raw):
    if isinstance(raw, dict) and 'x' in raw and 'y' in raw:
        return [float(raw['x']), float(raw['y'])]
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return [float(raw[0]), float(raw[1])]
    return None


def _seg(raw):
    if not isinstance(raw, dict):
        return None
    p1, p2 = _pt(raw.get('p1')), _pt(raw.get('p2'))
    if p1 is None or p2 is None:
        return None
    return {'p1': p1, 'p2': p2}


def _json(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            try:
                return json.loads(raw.replace("'", '"'))
            except Exception:
                return None
    return None


def _params(template_data):
    data = _json(template_data)
    out = {}
    if isinstance(data, dict):
        out.update(data)
    elif isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, dict):
                for k, v in item.items():
                    out[str(k).strip()] = v[0] if isinstance(v, (list, tuple)) and v else v
    return out


def _num(params, keys, default, cast=float):
    for k in keys:
        if k in params:
            try:
                return cast(params[k])
            except Exception:
                continue
    return default


def _poly(raw):
    data = _json(raw)
    if not data:
        return []
    if isinstance(data, list) and data and isinstance(data[0], list) and data[0] and isinstance(data[0][0], dict):
        data = data[0]
    if isinstance(data, list):
        pts = [_pt(p) for p in data]
        pts = [p for p in pts if p]
        if len(pts) >= 3:
            return pts
    return []


# ===================== 几何 =====================
def seg_side(p, seg):
    ax, ay = seg['p1']
    bx, by = seg['p2']
    px, py = p
    return (bx - ax) * (py - ay) - (by - ay) * (px - ax)


def side_sign(p, seg):
    s = seg_side(p, seg)
    if abs(s) < 1e-6:
        return 0
    return 1 if s > 0 else -1


def dist_point_segment(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    l2 = vx * vx + vy * vy
    if l2 == 0:
        return float(np.hypot(px - ax, py - ay))
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / l2))
    return float(np.hypot(px - (ax + t * vx), py - (ay + t * vy)))


def clearly_over_line(hip_pt, seg, touch_dist, cross_side):
    """髋部是否明显越过 L2 的完成侧（在完成侧且距线 > 走廊宽度）。"""
    if hip_pt is None:
        return False
    d = dist_point_segment(hip_pt, seg['p1'], seg['p2'])
    s = side_sign(hip_pt, seg)
    return d > touch_dist and s != 0 and ((s > 0) == (cross_side > 0))


def point_in_polygon(point, polygon):
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        xinters = p1x
                    if y <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


# ===================== 跟踪 =====================
def box_iou(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    return inter / (area_a + area_b - inter + 1e-6)


class SimpleTracker(object):
    """IOU 跟踪器：每条轨迹带跨越判定状态（与 Jump.py 一致）。"""

    def __init__(self, iou_thresh=DEF_IOU, max_lost=DEF_MAX_LOST):
        self.tracks = []
        self.next_id = 1
        self.iou_thresh = iou_thresh
        self.max_lost = max_lost

    def update(self, boxes):
        ids = [-1] * len(boxes)
        matched = set()
        for i, box in enumerate(boxes):
            best_t, best_iou = -1, self.iou_thresh
            for ti, t in enumerate(self.tracks):
                if ti in matched:
                    continue
                iou = box_iou(box, t['box'])
                if iou > best_iou:
                    best_iou, best_t = iou, ti
            if best_t >= 0:
                matched.add(best_t)
                t = self.tracks[best_t]
                t['box'], t['lost'] = box, 0
                ids[i] = t['id']
            else:
                ids[i] = self.next_id
                self.tracks.append({
                    'id': self.next_id, 'box': box, 'lost': 0,
                    'state': {'touched_l1': False, 'touch_frame': -1, 'touch_x': None,
                              'cnt': 0, 'cooldown': 0,
                              'touch_img': None, 'touch_boxes': None},
                })
                self.next_id += 1
        matched_ids = set(ids)
        for t in self.tracks:
            if t['id'] not in matched_ids:
                t['lost'] += 1
        self.tracks = [t for t in self.tracks if t['lost'] <= self.max_lost]
        return ids

    def get_state(self, track_id):
        for t in self.tracks:
            if t['id'] == track_id:
                return t['state']
        return None


def update_crossing_state(state, touch_l1, hip_pt, hip_x, frame_idx,
                          l2_seg, l2_cross_side, touch_dist,
                          touch_timeout, require_frames, cooldown_frames, x_drift_max):
    """跨线时序状态机（严格顺序）：触碰 L1 → 明显越过 L2 完成侧 → 连续 N 帧 → 报警。"""
    if state['cooldown'] > 0:
        state['cooldown'] -= 1
        state['cnt'] = 0
        state['touched_l1'] = False
        return False

    if touch_l1 and not state['touched_l1']:
        state['touched_l1'] = True
        state['touch_frame'] = frame_idx
        state['touch_x'] = hip_x

    if state['touched_l1'] and frame_idx - state['touch_frame'] > touch_timeout:
        state['touched_l1'] = False

    candidate = False
    if state['touched_l1'] and hip_pt is not None:
        if clearly_over_line(hip_pt, l2_seg, touch_dist, l2_cross_side):
            if state['touch_x'] is None or abs(hip_x - state['touch_x']) <= x_drift_max:
                candidate = True

    state['cnt'] = state['cnt'] + 1 if candidate else 0
    if state['cnt'] >= require_frames:
        state['cnt'] = 0
        state['cooldown'] = cooldown_frames
        state['touched_l1'] = False
        return True
    return False


# ===================== 姿态 =====================
def classify_posture(keypoints, conf_thresh=DEF_KPT_CONF):
    """移植自 classify_posture.py：躯干倾斜 + 有向下支撑 + 头膝大跨度折叠 = crossing。"""
    def kpt_valid(idx):
        return keypoints[idx, 2] > conf_thresh

    info = {}
    reasons = []
    if not kpt_valid(0):
        return 'unknown', info
    head_x, head_y = keypoints[0, 0], keypoints[0, 1]

    sh_x, sh_y, hi_x, hi_y = 0.0, 0.0, 0.0, 0.0
    torso_available = False
    if kpt_valid(5) and kpt_valid(11):
        sh_x, sh_y = keypoints[5, 0], keypoints[5, 1]
        hi_x, hi_y = keypoints[11, 0], keypoints[11, 1]
        torso_available = True
    elif kpt_valid(6) and kpt_valid(12):
        sh_x, sh_y = keypoints[6, 0], keypoints[6, 1]
        hi_x, hi_y = keypoints[12, 0], keypoints[12, 1]
        torso_available = True
    if not torso_available:
        return 'unknown', info

    torso_dx = abs(hi_x - sh_x)
    torso_dy = abs(hi_y - sh_y)
    if torso_dy > torso_dx * 2.0:
        return 'unknown', info
    reasons.append('body_tilted')

    support_points = []
    for idx in [9, 10, 11, 12]:
        if kpt_valid(idx):
            support_points.append(keypoints[idx, :2])
    if not support_points:
        return 'unknown', info
    lowest_support_y = max(p[1] for p in support_points)
    if lowest_support_y < sh_y + (torso_dy * 0.5):
        return 'unknown', info
    reasons.append('supporting')

    knee_points = []
    for idx in [13, 14]:
        if kpt_valid(idx):
            knee_points.append(keypoints[idx, :2])
    if not knee_points:
        return 'unknown', info
    lowest_knee_y = max(p[1] for p in knee_points)
    head_to_knee_dist = lowest_knee_y - head_y
    torso_len = float(np.sqrt(torso_dx ** 2 + torso_dy ** 2))
    if head_to_knee_dist < torso_len * 0.8:
        return 'unknown', info
    reasons.append('head_knee_spread')
    info['crossing_reasons'] = reasons
    return 'crossing', info


def get_hip_center(keypoints, conf_thresh=DEF_KPT_CONF):
    pts = []
    if keypoints[11, 2] > conf_thresh:
        pts.append(keypoints[11, :2])
    if keypoints[12, 2] > conf_thresh:
        pts.append(keypoints[12, :2])
    if not pts:
        return None
    return float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))


# ===================== 绘制 =====================
def _draw_skeleton(img, kpts, conf_thresh):
    for i, (a, b) in enumerate(SKELETON):
        if a >= len(kpts) or b >= len(kpts):
            continue
        if kpts[a, 2] > conf_thresh and kpts[b, 2] > conf_thresh:
            cv2.line(img, (int(kpts[a, 0]), int(kpts[a, 1])),
                     (int(kpts[b, 0]), int(kpts[b, 1])), LIMB_COLORS[i % len(LIMB_COLORS)], 2)
    for i in range(len(kpts)):
        if kpts[i, 2] > conf_thresh:
            cv2.circle(img, (int(kpts[i, 0]), int(kpts[i, 1])), 3, (0, 0, 255), -1)


def _draw_marks(img, roi, l1, l2):
    if roi:
        cv2.polylines(img, [np.asarray(roi, np.int32).reshape(-1, 1, 2)], True, ROI_COLOR, 2)
    cv2.line(img, (int(l1['p1'][0]), int(l1['p1'][1])), (int(l1['p2'][0]), int(l1['p2'][1])), L1_COLOR, 3)
    cv2.line(img, (int(l2['p1'][0]), int(l2['p1'][1])), (int(l2['p2'][0]), int(l2['p2'][1])), L2_COLOR, 3)
    cv2.putText(img, 'L1', (int(l1['p1'][0]), int(l1['p1'][1]) - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, L1_COLOR, 2)
    cv2.putText(img, 'L2', (int(l2['p1'][0]), int(l2['p1'][1]) - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, L2_COLOR, 2)


# ===================== 平台入口 =====================
def build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence, conf_area,
               algorithm_type_list, test_type_ename, sensitivity, conf_id, Equipment_id,
               template_config_type_id, template_id, conf_name, equipment_name, equipment_ip,
               interval_time, template_list_area, image_count, template_data, conf_status,
               res_type, template_small_name, Algorithm_library_id, conf_img_resolution,
               defense_time_start, defense_time_end, duration_time, cross_line_area=None,
               label_prefix='', names_cn=None, Mine_id=None, mine_code=None, region_color=None):
    params = _params(template_data)
    touch_dist = _num(params, ('触碰距离', 'line_touch_dist'), DEF_TOUCH_DIST)
    touch_timeout = _num(params, ('触碰超时帧', 'touch_timeout_frames'), DEF_TOUCH_TIMEOUT, int)
    require_frames = _num(params, ('连续确认帧', 'require_frames'), DEF_REQUIRE_FRAMES, int)
    cooldown_frames = _num(params, ('报警冷却帧', 'cooldown_frames'), DEF_COOLDOWN, int)
    kpt_conf = _num(params, ('关键点置信度', 'kpt_conf'), DEF_KPT_CONF)

    data = _json(cross_line_area)
    if not isinstance(data, dict):
        raise ValueError('跨越闸机缺少双线配置（cross_line_area 应为 {"l1":..,"l2":..}）')
    l1 = _seg(data.get('l1') or data.get('gate_l1'))
    l2 = _seg(data.get('l2') or data.get('gate_l2'))
    if l1 is None or l2 is None:
        raise ValueError('跨越闸机需要 L1、L2 两条线（各含 p1/p2）')
    if 'line_touch_dist' in data:
        try:
            touch_dist = float(data['line_touch_dist'])
        except Exception:
            pass
    roi = _poly(conf_area)
    try:
        src_w, src_h = [int(v) for v in str(conf_img_resolution or '1920x1080').lower().split('x')]
    except Exception:
        src_w, src_h = 1920, 1080
    if src_w <= 0 or src_h <= 0:
        src_w, src_h = 1920, 1080

    out_dir = os.path.join('/data/AIGO/outputs/crossing/result', str(conf_name), 'images')
    os.makedirs(out_dir, exist_ok=True)

    state = {
        'src': (src_w, src_h),
        'roi': roi, 'l1': l1, 'l2': l2,
        'scaled': None, 'size': None,
        'tracker': SimpleTracker(),
        'frame_idx': 0,
        'err_logged': False,
        'stat': {'frames': 0, 'dets': 0, 'crossing': 0, 'touch': 0, 'alarms': 0},
    }

    def _geometry(w, h):
        if state['size'] == (w, h):
            return state['scaled']
        sx, sy = w / float(src_w), h / float(src_h)
        s = (sx + sy) / 2.0
        l1s = {'p1': [l1['p1'][0] * sx, l1['p1'][1] * sy],
               'p2': [l1['p2'][0] * sx, l1['p2'][1] * sy]}
        l2s = {'p1': [l2['p1'][0] * sx, l2['p1'][1] * sy],
               'p2': [l2['p2'][0] * sx, l2['p2'][1] * sy]}
        rois = [[p[0] * sx, p[1] * sy] for p in roi] if roi else []
        # L2 完成侧 = 远离 L1 的一侧
        mid_l1 = ((l1s['p1'][0] + l1s['p2'][0]) / 2.0, (l1s['p1'][1] + l1s['p2'][1]) / 2.0)
        side = side_sign(mid_l1, l2s)
        cross_side = -1 if side > 0 else 1
        state['scaled'] = {
            'l1': l1s, 'l2': l2s, 'roi': rois,
            'touch_dist': max(2.0, touch_dist * s),
            'touch_l1_dist': max(2.0, touch_dist * 1.3 * s),
            'x_drift': max(20.0, 200.0 * sx),
            'cross_side': cross_side,
        }
        state['size'] = (w, h)
        return state['scaled']

    def _report(image_bgr, st, g):
        ts = time.strftime('%Y-%m-%d_%H-%M-%S')
        day = time.strftime('%Y-%m-%d')
        folder = os.path.join(out_dir, day)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        alarm_path = os.path.join(folder, 'alarm_crossing_%s.jpg' % ts)
        ori_path = os.path.join(folder, 'ori_crossing_%s.jpg' % ts)
        try:
            frame = st.get('touch_img')
            if frame is None:
                frame = image_bgr.copy()
            canvas = frame.copy()
            _draw_marks(canvas, g['roi'], g['l1'], g['l2'])
            for box, kpts in (st.get('touch_boxes') or []):
                x1, y1, x2, y2 = [int(v) for v in box]
                cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 2)
                if kpts is not None:
                    _draw_skeleton(canvas, kpts, kpt_conf)
            cv2.putText(canvas, 'CROSSING', (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
            cv2.imwrite(alarm_path, canvas)
            cv2.imwrite(ori_path, frame)
        except Exception:
            log.exception('跨越报警图保存失败 conf=%s', conf_name)
            return
        host, port = cm.localhost_ip, int(cm.upload_port)
        alarm_str = time.strftime('%Y-%m-%d %H:%M:%S')
        log.warning('⚠ 跨越闸机报警 conf=%s %s', conf_name, alarm_str)

        def _do():
            try:
                data_send.insert_alg_log(ip_address='None', Level='INFO',
                                         message='%s 跨越闸机报警' % conf_name, alg_name=conf_name)
                data_send.upload_hwj(
                    Algorithm_conf_id=conf_id, res_type=res_type, Equipment_id=Equipment_id,
                    carousel_images_list=['http://%s:%d%s' % (host, port, alarm_path)],
                    ori_images_list=['http://%s:%d%s' % (host, port, ori_path)],
                    result_count=1, Entering_num=0, Exiting_num=0,
                    result_count_time=alarm_str, template_id=template_id,
                    template_type_id=template_config_type_id, res_time=alarm_str,
                    conf_name=conf_name, equipment_name=equipment_name,
                    equipment_ip=equipment_ip, Algorithm_library_id=Algorithm_library_id,
                    Mine_id=Mine_id, mine_code=mine_code, warning_message='跨越闸机')
            except Exception:
                log.exception('跨越闸机报警上报失败 conf=%s', conf_name)
        threading.Thread(target=_do, daemon=True).start()

    def on_result(image_bgr, results, width, height):
        try:
            state['frame_idx'] += 1
            idx = state['frame_idx']
            g = _geometry(width, height)
            dets = []
            for obj in (results or []):
                if len(obj) < 4:
                    continue
                try:
                    box = [float(v) for v in obj[2]]
                    kpts = np.asarray(obj[3], dtype=np.float32).reshape(KPT_NUM, 3)
                    score = float(obj[1])
                except Exception:
                    continue
                dets.append((score, box, kpts))
            ids = state['tracker'].update([d[1] for d in dets])
            stat = state['stat']
            stat['frames'] += 1
            stat['dets'] += len(dets)
            for n, (score, box, kpts) in enumerate(dets):
                hip = get_hip_center(kpts, kpt_conf)
                posture, _info = classify_posture(kpts, kpt_conf)
                if posture == 'crossing':
                    stat['crossing'] += 1
                touch_l1 = False
                hip_x = 0.0
                hip_pt = None
                if hip is not None:
                    hip_x, hip_y = hip
                    hip_pt = (hip_x, hip_y)
                    d_l1 = dist_point_segment(hip_pt, g['l1']['p1'], g['l1']['p2'])
                    touch_l1 = (posture == 'crossing' and d_l1 <= g['touch_l1_dist'])
                st = state['tracker'].get_state(ids[n])
                if st is None:
                    continue
                if touch_l1 and not st['touched_l1']:
                    st['touch_img'] = image_bgr.copy()
                    st['touch_boxes'] = [(d[1], d[2]) for d in dets]
                    stat['touch'] += 1
                alarm = update_crossing_state(
                    st, touch_l1, hip_pt, hip_x, idx, g['l2'], g['cross_side'],
                    g['touch_dist'], touch_timeout, require_frames, cooldown_frames, g['x_drift'])
                if alarm:
                    stat['alarms'] += 1
                    _report(image_bgr, st, g)
            if stat['frames'] % 300 == 0:
                log.info('跨越闸机统计 conf=%s 检测帧=%d 累计目标=%d crossing姿态=%d 触碰L1=%d 报警=%d',
                         conf_name, stat['frames'], stat['dets'], stat['crossing'],
                         stat['touch'], stat['alarms'])
        except Exception as e:
            if not state.get('err_logged'):
                state['err_logged'] = True
                log.error('跨越 on_result 异常 conf=%s: %s', conf_name, e)

    def on_draw(image_bgr, width, height):
        try:
            g = _geometry(width, height)
            _draw_marks(image_bgr, g['roi'], g['l1'], g['l2'])
        except Exception:
            pass

    names = names_cn if isinstance(names_cn, list) and names_cn else ['person']
    spec = rtsp_infer_push.make_model_spec(
        rknn_path=algorithm_path, names=names, on_result=on_result, on_draw=on_draw,
        category_id=None, obj_thresh=float(confidence or 0.25), nms_thresh=0.45, img_size=640,
        extract_count=max(1, int(sensitivity or 1)), label_prefix=label_prefix,
        name=conf_name, pose=True, kpt_num=KPT_NUM)
    log.info('跨越闸机模板 build_spec conf=%s 触碰距离=%.1f 触碰超时=%d帧 连续=%d帧 冷却=%d帧',
             conf_name, touch_dist, touch_timeout, require_frames, cooldown_frames)
    return {'spec': spec, 'rtsp_url': rtsp_url, 'enc_type': 'h264',
            'extract_count': max(1, int(sensitivity or 1)),
            'push_url': 'rtsp://127.0.0.1:8554/stream99', 'conf_name': conf_name}


def method(*args, **kwargs):
    raise RuntimeError('跨越闸机由 model_start 统一编排，请通过算法配置启动')
