# -*- coding: utf-8 -*-
"""
人员尾随（闸机尾随）— 平台引擎模板
=====================================================================
配置界面输入：
  conf_area       : 框（ROI，4 点多边形）
  cross_line_area : {"area_type":"line","points":[p1,p2],"p1":p1,"p2":p2,"direction":"down"}
  direction       : up = 由近及远（区域1=近侧） / down = 由远及近（区域1=远侧）
判定：
  区域1 连续 stable 帧 → 区域2 连续 stable 帧 = 一次通行；
  相邻两次通行间隔 < 窗口秒数 = 尾随（同一次会话内累计人数）；
  会话超过 session_timeout 秒无新尾随 → 一次上报（Exiting_num = 尾随人数）。

约束：本模板只读取自己的配置，不读写任何人数统计（count）表/文件。
"""
import os
import json
import time
import threading

import numpy as np
import cv2

from comm import data_send
from config import common as cm
from templates import alarm_video
from templates import rtsp_infer_push

log = rtsp_infer_push.logger

DEFAULT_WINDOW = 5.0
DEFAULT_STABLE = 5
DEFAULT_SESSION = 10.0
MAX_LOST_FRAMES = 30


# ===================== 几何 =====================
def _poly_area(poly):
    p = np.asarray(poly, dtype=np.float64)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _centroid(poly):
    p = np.asarray(poly, dtype=np.float64)
    a = _poly_area(p)
    if abs(a) < 1e-9:
        return p.mean(axis=0)
    x, y = p[:, 0], p[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y2 - x2 * y
    return np.array([float(np.sum((x + x2) * cross) / (6.0 * a)),
                     float(np.sum((y + y2) * cross) / (6.0 * a))])


def _clip_halfplane(poly, a, b, keep_left=True):
    p = np.asarray(poly, dtype=np.float64)
    ax, ay, bx, by = float(a[0]), float(a[1]), float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay

    def side(q):
        s = dx * (q[1] - ay) - dy * (q[0] - ax)
        return s if keep_left else -s

    out = []
    for i in range(len(p)):
        cur, nxt = p[i], p[(i + 1) % len(p)]
        sc, sn = side(cur), side(nxt)
        if sc >= 0:
            out.append(cur.copy())
        if (sc > 0 > sn) or (sc < 0 < sn):
            out.append(cur + (sc / (sc - sn)) * (nxt - cur))
    clean = []
    for q in out:
        if not clean or np.hypot(*(q - clean[-1])) > 1e-9:
            clean.append(q)
    if len(clean) > 1 and np.hypot(*(clean[0] - clean[-1])) <= 1e-9:
        clean.pop()
    return np.array(clean, dtype=np.float64) if len(clean) >= 3 else np.zeros((0, 2))


def _line_box_intersections(box, a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    d = b - a
    p = np.asarray(box, dtype=np.float64)
    hits = []
    for i in range(len(p)):
        c, e = p[i], p[(i + 1) % len(p)]
        f = e - c
        denom = d[0] * f[1] - d[1] * f[0]
        if abs(denom) < 1e-12:
            continue
        ca = c - a
        t = (ca[0] * f[1] - ca[1] * f[0]) / denom
        u = (ca[0] * d[1] - ca[1] * d[0]) / denom
        if -1e-9 <= u <= 1.0 + 1e-9:
            hits.append(a + t * d)
    uniq = []
    for q in hits:
        if all(np.hypot(*(q - u)) > 0.5 for u in uniq):
            uniq.append(q)
    if len(uniq) < 2:
        return None
    best, best_d = (0, 1), -1.0
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            dist = float(np.hypot(*(uniq[i] - uniq[j])))
            if dist > best_d:
                best, best_d = (i, j), dist
    q1, q2 = uniq[best[0]], uniq[best[1]]
    if float(np.dot(q2 - q1, d)) < 0:
        q1, q2 = q2, q1
    return q1, q2


def build_regions(box, line, direction):
    """框 + 线 + 方向 → (region1, region2, box, line, 延伸线)。"""
    box = np.asarray(box, dtype=np.float64)
    if box.shape[0] > 4:
        box = box[:4]
    if len(box) < 3 or abs(_poly_area(box)) < 1.0:
        raise ValueError('尾随 ROI 框无效（点数不足或面积过小）')
    if _poly_area(box) < 0:
        box = box[::-1]
    line = np.asarray(line, dtype=np.float64)
    if line.shape != (2, 2):
        raise ValueError('尾随警戒线需要 2 个点')
    a, b = line[0], line[1]
    if float(np.hypot(*(b - a))) < 3.0:
        raise ValueError('尾随警戒线两个端点过近')
    ext = _line_box_intersections(box, a, b)
    if ext is None:
        raise ValueError('警戒线没有穿过 ROI 框，请把线画在框内')
    pos = _clip_halfplane(box, a, b, keep_left=True)
    neg = _clip_halfplane(box, a, b, keep_left=False)
    if len(pos) < 3 or len(neg) < 3:
        raise ValueError('警戒线把 ROI 框切分失败，请把线画在框内')
    cy_pos, cy_neg = float(_centroid(pos)[1]), float(_centroid(neg)[1])
    d = str(direction or '').strip().lower()
    if d in ('up', '上', '向上', 'down', '下', '向下'):
        if abs(cy_pos - cy_neg) < 1.0:
            raise ValueError('警戒线接近竖直，无法按 up/down 判定方向')
        far_poly, near_poly = (pos, neg) if cy_pos < cy_neg else (neg, pos)
        if d in ('up', '上', '向上'):
            region1, region2 = near_poly, far_poly
        else:
            region1, region2 = far_poly, near_poly
    elif d in ('left', 'right'):
        # 兼容平台标准配置页“画线”模式的方向（与人数统计同一套约定）：
        #   direction = 进入侧，right → 线右侧（法向 n=(dy,-dx) 一侧），left → 另一侧
        dy, dx = float(b[1] - a[1]), float(b[0] - a[0])

        def _side_of(poly):
            c = _centroid(poly)
            return dy * (c[0] - a[0]) - dx * (c[1] - a[1])

        s_pos, s_neg = _side_of(pos), _side_of(neg)
        if abs(s_pos - s_neg) < 1e-6:
            raise ValueError('警戒线切出的两块区域无法区分左右侧')
        pos_is_right = s_pos > s_neg
        if d == 'right':
            region1, region2 = (pos, neg) if pos_is_right else (neg, pos)
        else:
            region1, region2 = (neg, pos) if pos_is_right else (pos, neg)
    else:
        raise ValueError('尾随方向仅支持 up / down 或 left / right（收到 %r）' % (direction,))
    return region1, region2, box, line, ext


# ===================== 配置解析 =====================
def _box_points(conf_area):
    polys = rtsp_infer_push._parse_conf_area(conf_area)
    return [[float(x), float(y)] for poly in polys for (x, y) in poly] if polys else None


def _line_and_direction(cross_line_area):
    data = cross_line_area
    if isinstance(data, str):
        try:
            data = json.loads(data.replace("'", '"'))
        except Exception:
            return None, None
    if not isinstance(data, dict):
        return None, None

    def _pt(p):
        if isinstance(p, dict) and 'x' in p and 'y' in p:
            return [float(p['x']), float(p['y'])]
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return [float(p[0]), float(p[1])]
        return None

    pts = []
    raw = data.get('points')
    if isinstance(raw, (list, tuple)):
        for p in raw:
            q = _pt(p)
            if q:
                pts.append(q)
    if len(pts) < 2:
        p1, p2 = _pt(data.get('p1')), _pt(data.get('p2'))
        if p1 and p2:
            pts = [p1, p2]
    return (pts[:2] if len(pts) >= 2 else None), data.get('direction')


def _params(template_data):
    data = template_data
    if isinstance(data, str):
        try:
            data = json.loads(data.replace("'", '"'))
        except Exception:
            return {}
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


# ===================== 跟踪 =====================
class SimpleTracker:
    def __init__(self, max_dist_px=150.0, max_lost=MAX_LOST_FRAMES):
        self.tracks = {}
        self.next_id = 1
        self.max_dist = max_dist_px
        self.max_lost = max_lost

    def update(self, dets):
        dets = sorted(dets, key=lambda d: d[0], reverse=True)
        centers = [((d[1][0] + d[1][2]) / 2.0, (d[1][1] + d[1][3]) / 2.0) for d in dets]
        active = {tid: t for tid, t in self.tracks.items() if t['lost'] < self.max_lost}
        used_t, used_d = set(), set()
        for i, det in enumerate(dets):
            best, best_d = None, self.max_dist
            for tid, t in active.items():
                if tid in used_t:
                    continue
                d = float(np.hypot(t['center'][0] - centers[i][0],
                                   t['center'][1] - centers[i][1]))
                if d < best_d:
                    best, best_d = tid, d
            if best is not None:
                self.tracks[best].update(center=centers[i], bbox=list(det[1]), lost=0)
                used_t.add(best)
                used_d.add(i)
        for tid in active:
            if tid not in used_t:
                self.tracks[tid]['lost'] += 1
        for i, det in enumerate(dets):
            if i not in used_d:
                self.tracks[self.next_id] = {'center': centers[i],
                                             'bbox': list(det[1]), 'lost': 0}
                self.next_id += 1
        for tid in [k for k, v in self.tracks.items() if v['lost'] >= self.max_lost]:
            del self.tracks[tid]
        return [(tid, t['bbox'], t['center'])
                for tid, t in sorted(self.tracks.items()) if t['lost'] == 0]


def _inside(poly_np, pt):
    return cv2.pointPolygonTest(poly_np, (float(pt[0]), float(pt[1])), False) >= 0


def _draw_arrow(img, p1, p2, direction):
    mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = float(np.hypot(dx, dy)) + 1e-6
    nx, ny = -dy / n, dx / n          # 线的左法向
    d = str(direction).lower()
    if d in ('left', 'right'):
        # left/right：沿线的法向画箭头（right = 法向 n=(dy,-dx) 一侧）
        s = -1.0 if d == 'left' else 1.0
        tip = (int(mid[0] - ny * s * 45), int(mid[1] + nx * s * 45))
        tail = (int(mid[0] + ny * s * 45), int(mid[1] - nx * s * 45))
    else:
        up = d in ('up', '上', '向上')
        sign = -1.0 if up else 1.0
        tip = (int(mid[0]), int(mid[1] + sign * 45))
        tail = (int(mid[0]), int(mid[1] - sign * 45))
    cv2.arrowedLine(img, tail, tip, (255, 0, 255), 2, tipLength=0.35)


# ===================== 平台入口 =====================
def build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence, conf_area,
               algorithm_type_list, test_type_ename, sensitivity, conf_id, Equipment_id,
               template_config_type_id, template_id, conf_name, equipment_name, equipment_ip,
               interval_time, template_list_area, image_count, template_data, conf_status,
               res_type, template_small_name, Algorithm_library_id, conf_img_resolution,
               defense_time_start, defense_time_end, duration_time, cross_line_area=None,
               label_prefix='', names_cn=None, Mine_id=None, mine_code=None, region_color=None):
    params = _params(template_data)
    window = _num(params, ('尾随时间窗', 'tailgate_window'), DEFAULT_WINDOW)
    stable = _num(params, ('稳定帧数', 'stable_frames'), DEFAULT_STABLE, int)
    session_timeout = _num(params, ('会话超时', 'session_timeout'), DEFAULT_SESSION)

    box = _box_points(conf_area)
    line, direction = _line_and_direction(cross_line_area)
    if not box:
        raise ValueError('缺少尾随 ROI 框（conf_area）')
    if not line:
        raise ValueError('缺少尾随警戒线（cross_line_area 需包含 2 个点）')
    try:
        src_w, src_h = [int(v) for v in str(conf_img_resolution or '1920x1080').lower().split('x')]
    except Exception:
        src_w, src_h = 1920, 1080

    out_dir = os.path.join('/data/AIGO/outputs/tailgate/result', str(conf_name), 'images')
    os.makedirs(out_dir, exist_ok=True)

    state = {
        'box': np.asarray(box, np.float64),
        'line': np.asarray(line, np.float64),
        'direction': direction,
        'regions': None, 'region_size': None,
        'tracker': None, 'track_state': {},
        'last_passage_time': 0.0, 'session': None,
        'region_err_logged': False,
    }

    def _regions_for(w, h):
        key = (w, h)
        if state['region_size'] == key:
            return state['regions']
        sx, sy = w / float(src_w or w), h / float(src_h or h)
        regions = build_regions(state['box'] * np.array([sx, sy]),
                                state['line'] * np.array([sx, sy]),
                                state['direction'])
        state['regions'] = regions
        state['region_size'] = key
        if state['tracker'] is None:
            state['tracker'] = SimpleTracker(max_dist_px=max(40.0, w * 0.10))
        return regions

    def _draw(img, tracked=None):
        h, w = img.shape[:2]
        region1, region2, box, line, ext = _regions_for(w, h)
        cv2.polylines(img, [np.asarray(box, np.int32).reshape(-1, 1, 2)], True, (0, 255, 255), 2)
        cv2.line(img, tuple(np.asarray(ext[0], np.int32)), tuple(np.asarray(ext[1], np.int32)),
                 (255, 0, 255), 2)
        _draw_arrow(img, ext[0], ext[1], state['direction'])
        for tid, bbox in (tracked or []):
            x1, y1, x2, y2 = [int(v) for v in bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(img, '#%s' % tid, (x1 + 2, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(img, 'Tailgating', (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (0, 0, 255), 2)

    def _report(sess):
        ts = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(sess['end']))
        folder = os.path.join(out_dir, ts)
        try:
            os.makedirs(folder, exist_ok=True)
            alarm_path = os.path.join(folder, 'alarm_%s.jpg' % ts)
            ori_path = os.path.join(folder, 'ori_%s.jpg' % ts)
            cv2.imwrite(alarm_path, sess['alarm_img'])
            cv2.imwrite(ori_path, sess['ori_img'])
        except Exception:
            log.exception('尾随告警图保存失败 conf=%s', conf_name)
            return
        host, port = cm.localhost_ip, int(cm.upload_port)
        follow = int(sess['follow_num'])
        start_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sess['start']))
        end_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sess['end']))
        log.warning('⚠ 尾随上报 conf=%s 人数=%s %s~%s', conf_name, follow, start_str, end_str)

        def _do():
            try:
                video_url = None
                try:
                    video_url = alarm_video.trigger(
                        conf_name, alarm_ts=sess['end'], start_ts=sess['start'], analysis_type='00')
                except Exception:
                    log.exception('尾随报警视频生成失败 conf=%s', conf_name)
                data_send.insert_alg_log(ip_address='None', Level='INFO',
                                         message='%s 尾随上报 人数=%s' % (conf_name, follow),
                                         alg_name=conf_name)
                data_send.upload_hwj(
                    Algorithm_conf_id=conf_id, res_type=res_type, Equipment_id=Equipment_id,
                    carousel_images_list=['http://%s:%d%s' % (host, port, alarm_path)],
                    ori_images_list=['http://%s:%d%s' % (host, port, ori_path)],
                    result_count=follow, Entering_num=0, Exiting_num=follow,
                    result_count_time=start_str, template_id=template_id,
                    template_type_id=template_config_type_id, res_time=end_str,
                    conf_name=conf_name, equipment_name=equipment_name,
                    equipment_ip=equipment_ip, Algorithm_library_id=Algorithm_library_id,
                    Mine_id=Mine_id, mine_code=mine_code,
                    warning_video=video_url)
            except Exception:
                log.exception('尾随上报失败 conf=%s', conf_name)
        threading.Thread(target=_do, daemon=True).start()

    def on_result(image_bgr, results, width, height, frame_timestamp=None, frame_continuous=True):
        try:
            now = time.time() if frame_timestamp is None else frame_timestamp
            region1, region2, box, line, ext = _regions_for(width, height)
            r1_np = np.asarray(region1, np.float32).reshape(-1, 1, 2)
            r2_np = np.asarray(region2, np.float32).reshape(-1, 1, 2)

            sess = state['session']
            if sess is not None and (now - sess['last']) >= session_timeout:
                _report(sess)
                state['session'] = None

            dets = []
            for obj in (results or []):
                try:
                    dets.append((float(obj[1]), [float(v) for v in obj[2]]))
                except Exception:
                    continue
            tracked = state['tracker'].update(dets)

            if not frame_continuous:
                for st in state['track_state'].values():
                    st['r1'] = st['r2'] = 0
            for tid, bbox, center in tracked:
                st = state['track_state'].setdefault(
                    tid, {'r1': 0, 'r2': 0, 'entered': False, 'done': False})
                in1, in2 = _inside(r1_np, center), _inside(r2_np, center)
                if not st.get('dbg'):
                    st['dbg'] = True
                    log.info('尾随模板 conf=%s Track#%s 首次出现 中心=(%d,%d) 区域=%s 区域1面积=%.0f 区域2面积=%.0f',
                             conf_name, tid, center[0], center[1],
                             '区域1' if in1 else ('区域2' if in2 else '框外'),
                             abs(cv2.contourArea(r1_np)), abs(cv2.contourArea(r2_np)))
                st['r1'] = st['r1'] + 1 if in1 and not in2 else 0
                st['r2'] = st['r2'] + 1 if in2 and not in1 else 0
                if in1 and not st['entered'] and st['r1'] >= stable:
                    st['entered'] = True
                if in2 and st['entered'] and not st['done'] and st['r2'] >= stable:
                    st['done'] = True
                    gap = (now - state['last_passage_time']) if state['last_passage_time'] else 9999.0
                    state['last_passage_time'] = now
                    log.info('尾随模板 conf=%s Track#%s 通行 间隔=%.1fs', conf_name, tid, gap)
                    if 0 <= gap < window:
                        sess = state['session']
                        if sess is None:
                            alarm = image_bgr.copy()
                            _draw(alarm, [(t, b) for t, b, _c in tracked])
                            state['session'] = {'start': now, 'end': now, 'last': now,
                                                'follow_num': 1, 'alarm_img': alarm,
                                                'ori_img': image_bgr.copy()}
                            log.warning('⚠ 尾随会话开始 conf=%s', conf_name)
                        else:
                            sess['follow_num'] += 1
                            sess['last'] = now
                            sess['end'] = now

            live = {tid for tid, _b, _c in tracked}
            for tid in list(state['track_state'].keys()):
                if tid not in state['tracker'].tracks:
                    del state['track_state'][tid]
                elif tid not in live:
                    st = state['track_state'][tid]
                    st['r1'] = st['r2'] = 0
        except Exception as e:
            # 配置类错误（如方向非法）每帧都会触发，只记一次，避免日志被刷爆
            if not state.get('region_err_logged'):
                state['region_err_logged'] = True
                log.error('尾随 on_result 异常 conf=%s: %s（同类错误后续不再打印）', conf_name, e)
                log.debug('尾随 on_result 堆栈', exc_info=True)

    def on_draw(image_bgr, width, height):
        try:
            region1, region2, box, line, ext = _regions_for(width, height)
            cv2.polylines(image_bgr, [np.asarray(box, np.int32).reshape(-1, 1, 2)],
                          True, (0, 255, 255), 2)
            cv2.line(image_bgr, tuple(np.asarray(ext[0], np.int32)),
                     tuple(np.asarray(ext[1], np.int32)), (255, 0, 255), 2)
            _draw_arrow(image_bgr, ext[0], ext[1], state['direction'])
        except Exception:
            pass

    names = names_cn if isinstance(names_cn, list) and names_cn else ['person']
    spec = rtsp_infer_push.make_model_spec(
        rknn_path=algorithm_path, names=names, on_result=on_result, on_draw=on_draw,
        category_id=None, obj_thresh=confidence, nms_thresh=0.45, img_size=640,
        extract_count=max(1, int(sensitivity or 1)), label_prefix=label_prefix,
        name=conf_name, result_frame_continuity=True)
    log.info('尾随模板 build_spec conf=%s 方向=%s 窗口=%.1fs 稳定=%d 会话=%.1fs',
             conf_name, direction, window, stable, session_timeout)
    return {'spec': spec, 'rtsp_url': rtsp_url, 'enc_type': 'h264',
            'extract_count': max(1, int(sensitivity or 1)),
            'push_url': 'rtsp://127.0.0.1:8554/stream99', 'conf_name': conf_name}


def method(*args, **kwargs):
    raise RuntimeError('人员尾随由 model_start 统一编排，请通过算法配置启动')
