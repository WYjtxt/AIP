# -*- coding: utf-8 -*-
'''
携带危险物品模板（dangerous）—— 仅【后处理】

取流 + 推理 + 推流 已统一抽到 templates/rtsp_infer_push.py（支持一路流多模型并行）。本文件只：
  1) build_spec(...)：把数据库参数整理成 model_spec(含 on_result) + 流参数提示；
  2) on_result：人/危险品分类 → 区域判断 → 人与危险品 IOU 关联 → 持续时长 → 报警间隔 → 存图/上报；
  3) method(...)：单任务入口（一路流一模型），兼容旧调用方式。

results 格式：[[cls_id:int, '%.2f'%score:str, [xmin, ymin, xmax, ymax]], ...]（约定 0=人，1=危险品）。
'''
import os
import time
import logging
import threading
from logging.handlers import TimedRotatingFileHandler
import numpy as np
import cv2
from datetime import datetime

from comm import data_send
from config import common as cm
from templates import rtsp_infer_push
from templates import alarm_video

ip = cm.upload_ip
port = int(cm.upload_port)


def parse_conf_area(conf_area, src_width, src_height, width_scale, height_scale):
    """解析区域数据结构，返回 (多边形顶点列表, 区域命名列表)。"""
    polygons = []
    area_names = []
    null_flag = (len(conf_area) == 0)
    error_flag = ("NaN" in str(conf_area))
    if null_flag or error_flag:
        polygons = [[(0, 0), (0, height_scale * src_height), (width_scale * src_width, height_scale * src_height), (width_scale * src_width, 0)]]
        area_names = ["告警区域"]
        return polygons, area_names
    else:
        for outer_list in conf_area:
            for inner_dict in outer_list:
                area_name = inner_dict['type']
                area_names.append(area_name)
                data_list = inner_dict['data']
                single_polygon = []
                for point_dict in data_list:
                    x = int(int(point_dict['x']) * width_scale)
                    y = int(int(point_dict['y']) * height_scale)
                    single_polygon.append((x, y))
                polygons.append(single_polygon)
        return polygons, area_names


def is_point_in_polygon(point, polygon):
    """射线法判断点是否在多边形内。"""
    px, py = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < py <= max(p1y, p2y) and px <= max(p1x, p2x):
            if p1y != p2y:
                xints = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or px <= xints:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def is_point_in_any_polygon(point, polygons):
    """检查点是否在任意一个多边形内。"""
    if isinstance(polygons[0], tuple):
        return is_point_in_polygon(point, polygons)
    else:
        return any(is_point_in_polygon(point, polygon) for polygon in polygons)


def separate_areas(polygons, area_names):
    """按区域命名拆分出告警区域 / 类型一区域。"""
    alarm_areas = []
    post_process_areas = []
    for i in range(len(area_names)):
        if area_names[i] == "告警区域":
            alarm_areas.append(polygons[i])
        elif area_names[i] == "类型一":
            post_process_areas.append(polygons[i])
    return alarm_areas, post_process_areas


def handle_alert(output_img_dir, current_frame, det, alarm_areas, equipment_ip=None, names=None):
    """画框(中文标签) + 画区域 → 存报警图与原图，返回 (报警图URL列表, 原图URL列表)。
    URL 主机用算力盒本机 IP（cm.localhost_ip，因报警图存在盒子上），端口用 upload_port。
    names 为类别显示名（优先中文、与类别 id 同序）；标签复用引擎 draw_boxes 渲染（支持中文，cv2.putText 不支持）。"""
    logging.info("触发报警...")
    host = cm.localhost_ip   # 报警图存在算力盒本机，URL 主机用盒子 IP，非设备 equipment_ip
    model_dir = output_img_dir
    frame_np = current_frame.copy()
    frame_np_ori = current_frame.copy()
    h_img, w_img = frame_np.shape[:2]
    named = rtsp_infer_push.results_to_named(det, names or [])
    rtsp_infer_push.draw_boxes(frame_np, named, w_img, h_img)
    if alarm_areas is not None:
        for alarm_area in alarm_areas:
            if len(alarm_area) > 1:
                pts = np.array(alarm_area, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame_np, [pts], isClosed=True, color=(0, 255, 255), thickness=2)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    alarm_filename = f'alarm_{timestamp}.jpg'
    alarm_path = os.path.join(model_dir, alarm_filename)
    cv2.imwrite(alarm_path, frame_np)
    image_paths = [f"http://{host}:{port}{alarm_path}"]
    logging.info(f"报警图像保存: {alarm_path}")
    ori_filename = f'ori_{timestamp}.jpg'
    ori_path = os.path.join(model_dir, ori_filename)
    cv2.imwrite(ori_path, frame_np_ori)
    ori_image_paths = [f"http://{host}:{port}{ori_path}"]
    return image_paths, ori_image_paths


def duration_flag(duration_list, duration_frame, frame_ratio):
    """持续时长窗口内报警帧占比是否达到 frame_ratio。"""
    frame_count = duration_list.count(1)
    if (int(frame_count) / int(duration_frame)) >= frame_ratio:
        return True
    else:
        return False


def compute_iou(box1, box2):
    """[x1,y1,x2,y2] 格式 IOU。"""
    x1, y1, x2, y2 = box1
    x1g, y1g, x2g, y2g = box2
    xi1 = max(x1, x1g)
    yi1 = max(y1, y1g)
    xi2 = min(x2, x2g)
    yi2 = min(y2, y2g)
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = (x2 - x1) * (y2 - y1)
    box2_area = (x2g - x1g) * (y2g - y1g)
    union = box1_area + box2_area - inter_area
    return inter_area / union if union > 0 else 0


def _ensure_logging(log_dir, log_name):
    """进程内首个任务负责配置 root 日志。"""
    os.makedirs(log_dir, exist_ok=True)
    if logging.getLogger().handlers:
        return
    LOG_FILE = os.path.join(log_dir, log_name)
    handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=30, encoding="utf-8", utc=False)
    handler.suffix = "%Y-%m-%d.log"
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence, conf_area, algorithm_type_list, test_type_ename, sensitivity,
               conf_id, Equipment_id, template_config_type_id, template_id, conf_name, equipment_name, equipment_ip, interval_time, template_list_area, image_count, template_data, conf_status, res_type, template_small_name, Algorithm_library_id, conf_img_resolution, defense_time_start, defense_time_end, duration_time, label_prefix='', names_cn=None, Mine_id=None, mine_code=None, region_color=None):
    '''整理为任务条目：{'spec': model_spec(含 on_result), + 流参数提示}。
    region_color: 报警区域推流描边色（多任务同流时按任务区分，None=默认黄色）。'''
    output_dir = "/data/AIGO/outputs/dangerous/result"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    _ensure_logging(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dangerous"), "dangerous.log")
    output_algo_dir = os.path.join(output_dir, conf_name)
    if not os.path.exists(output_algo_dir):
        os.mkdir(output_algo_dir)
        logging.info("{}路径创建成功{}".format(conf_name, output_algo_dir))
    output_img_dir = os.path.join(output_algo_dir, 'images')
    if not os.path.exists(output_img_dir):
        os.mkdir(output_img_dir)

    classes_list = eval(algorithm_type_list)
    test_type_ename_list = eval(test_type_ename)
    category_id = [index for index, category in enumerate(classes_list) if any(category == item for item in test_type_ename_list)]
    # 推流画面标签：优先用中文类名（需与 algorithm_type_list 同序、等长），否则回退英文
    disp_names = names_cn if (isinstance(names_cn, list) and len(names_cn) == len(classes_list)) else classes_list

    if conf_img_resolution == "":
        conf_img_resolution = "1920x1080"
    original_resolution = conf_img_resolution

    duration_list = []
    frame_ratio = 0.7
    state = {'last_alarm_time': 0.0}
    region_cache = {}

    def on_draw(image_bgr, width, height):
        '''推流帧上常显报警区域（每帧调用，含跳帧）：按帧尺寸缓存缩放后的多边形。'''
        polys_np = region_cache.get((width, height))
        if polys_np is None:
            src_width, src_height = original_resolution.split('x')
            width_scale = width / int(src_width)
            height_scale = height / int(src_height)
            if conf_area and "NaN" not in str(conf_area):
                polygons, area_names = parse_conf_area(conf_area, int(src_width), int(src_height), width_scale, height_scale)
                alarm_areas, _ = separate_areas(polygons, area_names)
            else:
                alarm_areas = []
            polys_np = rtsp_infer_push._polygons_to_np(alarm_areas)
            region_cache[(width, height)] = polys_np
        if polys_np:
            rtsp_infer_push.draw_alarm_regions(image_bgr, polys_np,
                                               color_bgr=region_color or (0, 255, 255), thickness=2)

    def on_result(image_bgr, results, width, height):
        '''人/危险品分类 → 区域判断 → IOU 关联 → 持续时长 → 报警间隔 → 存图上报。'''
        if len(results) == 0:
            return
        person_boxes = []
        danger_boxes = []
        for item in results:
            cid, score, box = item
            if cid == 0:
                person_boxes.append(box)
            elif cid in [1]:
                danger_boxes.append(box)
        src_width, src_height = original_resolution.split('x')
        width_scale = width / int(src_width)
        height_scale = height / int(src_height)
        polygons, area_names = parse_conf_area(conf_area, int(src_width), int(src_height), width_scale, height_scale)
        alarm_areas, _ = separate_areas(polygons, area_names)
        if alarm_areas == []:
            alarm_areas = [[(0, 0), (0, height), (width, height), (width, 0)]]
        valid_targets = []
        for box in danger_boxes:
            xmin, ymin, xmax, ymax = box[0], box[1], box[2], box[3]
            center = ((xmin + xmax) / 2, (ymin + ymax) / 2)
            if is_point_in_any_polygon(center, alarm_areas):
                valid_targets.append(box)
        if len(valid_targets) == 0:
            danger_with_person = False
        else:
            danger_with_person = False
            for d_box in valid_targets:
                for p_box in person_boxes:
                    if compute_iou(d_box, p_box) > 0.06:
                        danger_with_person = True
                        break
                if danger_with_person:
                    break
        if danger_with_person:
            duration_list.append(1)
        else:
            duration_list.append(0)
        duration_frame = int(duration_time) * 25 // int(sensitivity)
        if len(duration_list) > duration_frame:
            duration_list.pop(0)
        if not duration_flag(duration_list, duration_frame, frame_ratio):
            logging.info(f"{conf_name}不满足持续时长条件")
            return
        current_time = time.time()
        if (current_time - state['last_alarm_time']) < int(interval_time):
            logging.info(f"{conf_name}不满足报警间隔")
            return
        logging.info(f"{conf_name}触发报警")
        # 报警时刻一次取定（current_time）：报警视频文件名与上报的始末时间共用同一时刻，
        # 保证平台报警记录与视频文件名逐秒一致（瞬时报警始末同值）。
        # 返回的视频 URL 随上报进 warning_video（分析类型缺省 00=其它）。
        video_url = alarm_video.trigger(conf_name, alarm_ts=current_time)
        alarm_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
        # 存图必须同步：handle_alert 会立刻 copy 当前共享帧，延后到线程里帧可能已被后续绘制改写。
        image_paths, ori_image_paths = handle_alert(output_img_dir, image_bgr, results, alarm_areas, equipment_ip, disp_names)

        # 上报走网络，放到后台线程并捕获异常（与 base_model 一致）：
        #  ① 回调在聚合线程内同步执行，kafka/DB 卡顿会拖住整条推流管道；
        #  ② 原来裸调 upload_hwj，一旦抛异常被引擎吞掉 → 图片存了、kafka 消息永久丢失。
        def _report():
            try:
                data_send.insert_alg_log(ip_address="None", Level="INFO", message=f"{conf_name}触发报警", alg_name=conf_name)
                data_send.upload_hwj(
                    Algorithm_conf_id=conf_id, res_type=res_type, Equipment_id=Equipment_id,
                    carousel_images_list=image_paths, ori_images_list=ori_image_paths,
                    result_count=None, Entering_num=None, Exiting_num=None, result_count_time=alarm_str,
                    template_type_id=template_config_type_id, template_id=template_id,
                    res_time=alarm_str, conf_name=conf_name, equipment_name=equipment_name,
                    equipment_ip=equipment_ip, Algorithm_library_id=Algorithm_library_id,
                    Mine_id=Mine_id, mine_code=mine_code, warning_video=video_url)
            except Exception:
                logging.exception(f"{conf_name}报警上报失败")
        threading.Thread(target=_report, daemon=True).start()
        state['last_alarm_time'] = current_time

    spec = rtsp_infer_push.make_model_spec(
        rknn_path=algorithm_path, names=disp_names, on_result=on_result, on_draw=on_draw,
        category_id=category_id, obj_thresh=confidence, nms_thresh=0.45, img_size=640,
        extract_count=max(1, int(sensitivity)),   # 按任务配置的帧间隔推理（模型级，同流其它任务不受影响）
        label_prefix=label_prefix, name=conf_name)

    return {
        'spec': spec,
        'rtsp_url': rtsp_url,
        'enc_type': 'h264',
        'extract_count': max(1, int(sensitivity)),
        # 带标注结果流的推流地址（缺此键 → assemble_stream_cfg 取不到 push_url → 引擎只取流推理不推流）。
        # 与 muban_PersonCount 的 _DEFAULT_PUSH_URL 保持一致；按实际媒体服务器路径调整。
        'push_url': 'rtsp://127.0.0.1:8554/stream99',
        'conf_name': conf_name,
    }


def method(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence, conf_area, algorithm_type_list, test_type_ename, sensitivity,
           conf_id, Equipment_id, template_config_type_id, template_id, conf_name, equipment_name, equipment_ip, interval_time, template_list_area, image_count, template_data, conf_status, res_type, template_small_name, Algorithm_library_id, conf_img_resolution, defense_time_start, defense_time_end, duration_time, Mine_id=None, mine_code=None):
    '''单任务入口（一路流一模型）：兼容旧调用方式。'''
    if not rtsp_status:
        return
    entry = build_spec(rtsp_status, args, template_name, algorithm_path, rtsp_url, confidence, conf_area, algorithm_type_list, test_type_ename, sensitivity,
                       conf_id, Equipment_id, template_config_type_id, template_id, conf_name, equipment_name, equipment_ip, interval_time, template_list_area, image_count, template_data, conf_status, res_type, template_small_name, Algorithm_library_id, conf_img_resolution, defense_time_start, defense_time_end, duration_time,
                       Mine_id=Mine_id, mine_code=mine_code)
    cfg = rtsp_infer_push.build_stream_cfg(
        [entry['spec']], rtsp_url=entry['rtsp_url'], enc_type=entry['enc_type'],
        extract_count=entry['extract_count'], push_url=None)
    data_send.insert_alg_log(
        ip_address="None", Level="INFO", message=f"{conf_name}开始运行",
        alg_name=conf_name, response_data=None, error_code=None, hostname=None)
    rtsp_infer_push.run(cfg)
