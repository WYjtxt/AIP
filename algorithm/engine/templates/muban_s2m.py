# -*- coding: utf-8 -*-
import argparse
from comm import data_send, data_receive
import time
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import numpy as np
import cv2
from datetime import datetime
from config import common as cm
import os
import models.yolov8_sophon as Y8
from templates import rtsp_infer_push  # 复用引擎的 draw_boxes/results_to_named（中文标签渲染）
from templates import alarm_video, alarm_directory
import gc
from datetime import datetime
import queue
import threading

# upload上传地址
ip = cm.upload_ip
port = int(cm.upload_port)

# 将队列定义全局变量
global result_queue
result_queue = queue.Queue(maxsize=50) 



def parse_conf_area(conf_area, src_width, src_height, width_scale, height_scale):
    """
    解析给定的区域数据结构，提取多边形顶点列表和对应的区域命名。

    参数:
    conf_area (list): 包含区域信息的嵌套列表，格式类似 [[{'type': 'I级报警', 'data': [{'x': '274', 'y': '88'},...]}],...]

    返回:
    tuple: 包含两个元素，第一个元素是多边形顶点列表的列表（每个顶点为 (x, y) 元组），第二个元素是区域命名列表
    """
    polygons = []
    area_names = []
    null_flag = (len(conf_area)==0)
    error_flag = ("NaN" in str(conf_area))
    
    if null_flag or error_flag:  # 不划区域或者返回的值为NaN
        polygons = [[(0,0),(0,height_scale*src_height),(width_scale*src_width,height_scale*src_height),(width_scale*src_width,0)]]
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
                    x = int(int(point_dict['x'])*width_scale)
                    y = int(int(point_dict['y'])*height_scale)
                    single_polygon.append((x, y))
                polygons.append(single_polygon)
        return polygons, area_names

def is_point_in_polygon(point, polygon):
    """
    使用射线法检查点是否在多边形内。

    Parameters:
    point: (x, y) 点坐标
    polygon: 多边形顶点列表，每个顶点为 (x, y) 元组

    Returns:
    布尔值，表示点是否在多边形内
    """
    px, py = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < py <= max(p1y, p2y) and px <= max(p1x, p2x):
            if p1y!= p2y:
                xints = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or px <= xints:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_point_in_any_polygon(point, polygons):
    """
    检查点是否在任意一个多边形内。

    Parameters:
    point: (x, y) 点坐标
    polygons: 多个多边形顶点列表的列表，每个顶点为 (x, y) 元组

    Returns:
    布尔值，表示点是否在任意一个多边形内
    """
    # 检查 polygons 是否是单个多边形
    if isinstance(polygons[0], tuple):
        # print("单个安全区域")
        return is_point_in_polygon(point, polygons)
    else:
        return any(is_point_in_polygon(point, polygon) for polygon in polygons)

# 解析区域
def separate_areas(polygons,area_names):
    """按区域命名把多边形拆分为 (告警区域列表, 类型一区域列表)。"""
    alarm_areas = []
    post_process_areas = []
    for i in range(len(area_names)):
        if area_names[i] == "告警区域":
            alarm_areas.append(polygons[i])
        elif area_names[i] == "类型一":
            post_process_areas.append(polygons[i])
    return alarm_areas, post_process_areas


def handle_alert(output_img_dir, current_frame, det, alarm_areas, model_name, equipment_ip=None, names=None):
    """
    Parameters:
        output_img_dir: 总输出目录
        current_frame: 当前帧 BMImage
        det: 模型检测结果
        alarm_areas: 区域
        equipment_ip: 设备实际 IP，仅用于上报数据；报警图 URL 主机改用算力盒 cm.localhost_ip
        names: 类别显示名（优先中文、与类别 id 同序）；标签复用引擎 draw_boxes 渲染（支持中文，cv2.putText 不支持）
    """

    logging.info("触发报警...")
    host = cm.localhost_ip   # 报警图存在算力盒本机，URL 主机用盒子 IP，非设备 equipment_ip

    # -----------------------------
    # ① 创建模型独立目录
    # -----------------------------
    model_dir = alarm_directory.relocate(os.path.join(output_img_dir, str(model_name)))
    os.makedirs(model_dir, exist_ok=True)

    # -----------------------------
    # ① 图像备份 (直接在 BGR 原图上操作)
    # -----------------------------
    # 备份原始的 BGR 图像，后续画图、保存原图都基于它
    frame_np = current_frame.copy()
    frame_np_ori = current_frame.copy()

    # -----------------------------
    # ③ 绘制检测框 + 中文标签（类别名 + 置信度），复用引擎 draw_boxes
    # -----------------------------
    h_img, w_img = frame_np.shape[:2]
    named = rtsp_infer_push.results_to_named(det, names or [])
    rtsp_infer_push.draw_boxes(frame_np, named, w_img, h_img)

    # -----------------------------
    # ④ 绘制区域
    # -----------------------------
    if alarm_areas is not None:
        for alarm_area in alarm_areas:
            if len(alarm_area) > 1:
                pts = np.array(alarm_area, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame_np, [pts], isClosed=True, color=(0, 255, 255), thickness=2)

    # -----------------------------
    # ⑤ 保存报警图
    # -----------------------------
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

    alarm_filename = f'alarm_{timestamp}.jpg'
    alarm_path = os.path.join(model_dir, alarm_filename)
    cv2.imwrite(alarm_path, frame_np)

    # 构造 URL
    image_paths = [alarm_directory.media_url(alarm_path, host, port)]
    logging.info(f"报警图像保存: {alarm_path}")

    # -----------------------------
    # ⑥ 保存原图
    # -----------------------------
    ori_filename = f'ori_{timestamp}.jpg'
    ori_path = os.path.join(model_dir, ori_filename)
    cv2.imwrite(ori_path, frame_np_ori)

    # 构造 URL
    ori_image_paths = [alarm_directory.media_url(ori_path, host, port)]

    return image_paths, ori_image_paths

# 判断出现的概率
def duration_flag(duration_list, duration_frame, frame_ratio):
    """判断持续时长窗口内报警帧占比是否达到 frame_ratio（达到返回 True）。"""
    # duration_list：列表
    # #duration_frame：帧数
    # #frame_ratio：比率
    # logging.info("fduration_list的长度为{}".format(len(duration_list)))
    frame_count = duration_list.count(1)
    # logging.info("frame_count为{}, duration_list为{}".format(frame_count, duration_list))
    # logging.info("ratio为{}, frame_ratio为{}".format((int(frame_count)/int(duration_frame)),frame_ratio))
    # print(f"frame_count:{int(frame_count)}")
    # print(f"duration_frame:{int(duration_frame)}")
    if (int(frame_count)/int(duration_frame)) >= frame_ratio:
        return True
    else:
        return False
    
def _s2m_frames(rtsp_url, pull_seconds=5):
    """Read BGR frames with the bundled OpenCV FFmpeg decoder and reconnect."""
    os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS',
                          'rtsp_transport;tcp|analyzeduration;1000000|probesize;1048576')
    # native_hik_stream integration
    from comm.algorithm_platform_source import HikCaptureSource
    hik_capture = HikCaptureSource(rtsp_url)
    if hik_capture.reference is not None:
        os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
    while True:
        source_url = rtsp_url
        if hik_capture.reference is not None:
            try:
                source_url = hik_capture.open_url()
            except ValueError:
                print('海康安防平台取流地址获取失败，稍后重试')
                time.sleep(pull_seconds)
                continue
        cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 6000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000])
        try:
            if cap.isOpened():
                while True:
                    ok, frame = cap.read()
                    if not ok or frame is None or frame.size == 0:
                        break
                    yield frame
        finally:
            cap.release()
        time.sleep(pull_seconds)


def init_rknn_auto(model_path, platform):
    """
    初始化算能 bmodel 模型（sophon-sail Engine，SYSIO）。
    函数名沿用旧签名以减少调用点改动；platform 参数已不使用。
    """
    print('正在加载模型...')
    try:
        model = Y8.YOLOv8Model(model_path)
    except Exception as e:
        print('加载 bmodel 失败: %s' % e)
        logging.exception('加载 bmodel 失败: %s' % model_path)
        return None
    print('加载 bmodel 成功: 输入=%dx%d' % (model.net_w, model.net_h))
    print('-' * 50)
    return model

def method(rtsp_status, args,template_name,algorithm_path, rtsp_url,confidence, conf_area,algorithm_type_list, test_type_ename, sensitivity,
                                                    conf_id, Equipment_id, template_config_type_id,template_id, conf_name, equipment_name, equipment_ip,interval_time, template_list_area,image_count,template_data,conf_status,res_type,template_small_name,Algorithm_library_id,conf_img_resolution, defense_time_start, defense_time_end,duration_time, model_algo_data, names_cn=None, Mine_id=None, mine_code=None):
    '''单路多模模板主入口：一路 RTSP 流 + N 个模型（第一个来自主配置，其余来自 model_algo_data）。
    使用 OpenCV FFmpeg 取帧，对每帧依次跑各模型的 SAIL 推理，
    并按各模型独立的 区域/持续时长/报警间隔 做后处理与报警上报（不推流）。'''
    # algorithm_path = '/ai/AIGO/python/bingxing_model/packages/阳光三极_未戴安全帽_基础检测类_基础检测_基础检测_yolov5s_int8_rockchip_rk3588_V1.2_1_1_20260507_1.rknn'

    if rtsp_status:
        """
        主函数，进行视频处理、相似度计算、运行状态检测和目标检测。

        参数:
        - args: 包含输入视频路径、模型路径、设备ID等参数的命令行参数。
        """
        # 创建结果保存路径
        output_dir = "/data/AIGO/outputs/s2m/result"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 建立日志
        # 1. 先拼接好目标目录的路径
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s2m")
        # 2. 检查并创建目录（exist_ok=True 表示如果目录已存在也不会报错）
        os.makedirs(log_dir, exist_ok=True)
        LOG_FILE = os.path.join(log_dir, "s2m.log")
        # 设置日志格式
        LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

        # 创建按日分割的日志处理器，并最多保留30天的日志
        log_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=30, encoding="utf-8", utc=False)
        log_handler.suffix = "%Y-%m-%d.log"  # 让日志文件按日期命名
        log_handler.setFormatter(logging.Formatter(LOG_FORMAT))

        # 配置日志
        logging.basicConfig(level=logging.INFO, handlers=[log_handler], force=True)


        output_algo_dir = os.path.join(output_dir, conf_name)
        if not os.path.exists(output_algo_dir):
            os.mkdir(output_algo_dir)
            logging.info("{}路径创建成功{}".format(conf_name, output_algo_dir))
        output_img_dir = os.path.join(output_algo_dir, 'images')
        if not os.path.exists(output_img_dir):
            os.mkdir(output_img_dir)


        # 基础参数（YOLOv8 bmodel 为 anchor-free，输入尺寸以 bmodel 为准，无需 img_size/masks/anchors）
        platform = 'bm1684x'
        enc_type = 'h264'
        pull_seconds = 5
        nms_thresh = 0.45
        

        # -------------------------
        # (1) 解析第一个模型
        # 这些变量 method 已经有
        # -------------------------
        first_class_list = eval(algorithm_type_list)
        # 报警图标签显示名：第一个模型优先用中文类名（test_type_cname_list，需与类别同序、等长），否则回退英文
        first_disp_names = names_cn if (isinstance(names_cn, list) and len(names_cn) == len(first_class_list)) else first_class_list
        first_model_config = {
            "model_path": algorithm_path,
            "confidence": confidence,
            "class_list": first_class_list,
            "target_labels": eval(test_type_ename),
            "Algorithm_library_id": Algorithm_library_id,
            "interval_time": interval_time,
            "duration_time": duration_time,
            "conf_area": conf_area,
            "res_type": res_type,
            "disp_names": first_disp_names,
        }
        models_config = [first_model_config]   # 先放第一个模型

        # -------------------------
        # (2) 解析后面 N 个模型（model_algo_data）
        # -------------------------
        model_algo_data = eval(model_algo_data) #文本转python格式
        for m in model_algo_data:
            models_config.append({
                "model_path": m["algorithm_path"],
                "confidence": float(m["confidence"]) / 100,
                # "confidence": 0.01,
                "class_list": m["algorithm_type_list"],
                "target_labels": m["label_list"],
                "Algorithm_library_id": m["Algorithm_library_id"],
                "interval_time": m["interval_time"],
                "duration_time": m["duration_time"],
                "conf_area": m["conf_area"],
                "res_type": m["res_type"],
                # 子模型 model_algo_data 不含中文类名，标签回退用其类别列表
                "disp_names": m["algorithm_type_list"],
            })
        # print(f"models_config:{models_config}")
        logging.info(f"models_config:{models_config}")


        # 配置初始分辨率,如果为空，用默认值
        if conf_img_resolution == "":
            conf_img_resolution = "1920x1080"
        original_resolution = conf_img_resolution

        frame_ratio = 0.7  # 可根据需求调整持续时长列表中报警出现的频率

        # ------------------------------
        # 按传入的模型参数自动初始化 N 个模型
        # ------------------------------
        rknn_pool = []         # 存储模型对象
        model_configs = []

        for m in models_config:
            model_path = m["model_path"]
            conf = float(m["confidence"])

            # 创建并初始化模型对象
            rknn_instance = init_rknn_auto(model_path,platform)
            if rknn_instance:
                rknn_pool.append(rknn_instance)

            # 计算类别 index
            cls_list = m["class_list"]
            target_labels = m["target_labels"]
            class_ids = [i for i, c in enumerate(cls_list) if c in target_labels]

            #根据模型路径分割获取解析类型
            model_name = os.path.basename(model_path).split('_')[1]

            # 保存该模型的独立配置
            model_configs.append({
                "conf":conf,
                "model_name":model_name,
                "Algorithm_library_id": m["Algorithm_library_id"],
                "interval_time": int(m["interval_time"]),
                "duration_time": int(m["duration_time"]),
                "conf_area": m["conf_area"],
                "res_type": m["res_type"],       # ← 新增：写入报警等级
                "class_ids":class_ids,
                "disp_names": m.get("disp_names") or cls_list,   # 报警图标签显示名（优先中文）
            })

        # print(f"class_ids:{class_ids}")
        logging.info(f"成功初始化 {len(rknn_pool)} 个模型")
        print(f"成功初始化 {len(rknn_pool)} 个模型")

        # 为每个模型维护独立报警时间
        if 'last_alarm_times' not in globals():
            last_alarm_times = [0] * len(rknn_pool)

        # 为每个模型维护持续帧列表
        if 'duration_lists' not in globals():
            duration_lists = [[] for _ in rknn_pool]  # 每个模型一个列表

        data_send.insert_alg_log(ip_address="None", Level="INFO",
                                 message=f"{conf_name}开始运行", alg_name=conf_name,
                                 response_data=None, error_code=None, hostname=None)

        def _process_frame(image_bgr):
            t1 = datetime.now()
            height, width = image_bgr.shape[:2]
            alarm_video.feed(image_bgr)



            for idx, rknn_instance in enumerate(rknn_pool):

                    cfg = model_configs[idx]
                    conf = cfg["conf"]
                    model_name = cfg['model_name']
                    interval_time = cfg["interval_time"]
                    duration_time = cfg["duration_time"]
                    algo_lib_id = cfg["Algorithm_library_id"]
                    model_area = cfg["conf_area"]
                    res_type = cfg["res_type"]
                    class_ids = cfg["class_ids"]
                    disp_names = cfg["disp_names"]


                    # 执行推理
                    # 注意：这里直接使用从caps获取的width和height
                    # print(f"width:{width},height:{height}")
                    results = Y8.infer(image_bgr, rknn_instance, conf, nms_thresh, class_ids)
                    # results = [[0, '0.45', [829, 298, 1083, 443]], [1, '0.52', [792, 304, 1116, 627]]]
                    t2 = datetime.now()
                    print(f'[模型{idx}]infer time: %.3fms' % ((t2 - t1).microseconds / 1000))
                    print('-' * 50)
                    # 在这里可以对置信度和类别id筛选完的results进行进一步处理，例如打印或发送
                    # results = [[0, '0.52', [792, 304, 1116, 627]], [0, '0.45', [829, 298, 1083, 443]]]
                    print(f"[模型{idx}]检测结果:", results)

                    if len(results) == 0:
                        print(f"[模型{idx}]没有检测到目标")
                        continue
                    # [
                    #     [0, "0.95", [120, 50, 280, 300]], 
                    #     [2, "0.88", [400, 100, 550, 400]]
                    # ]
                    #这里直接对结果进行判断存图

                    # ----------------------------
                    # 图像尺寸处理
                    # ----------------------------
                    src_width, src_height = original_resolution.split('x')
                    width_scale  = width / int(src_width)
                    height_scale = height / int(src_height)
                    # print(f"width_scale:{width_scale}")
                    # ----------------------
                    # ① 区域解析（独立）
                    # ----------------------
                    polygons, area_names = parse_conf_area(
                        model_area,
                        int(src_width),
                        int(src_height),
                        width_scale,
                        height_scale
                    )

                    alarm_areas, post_process_areas = separate_areas(polygons, area_names)
                    if alarm_areas == []:
                        alarm_areas = [[(0,0),(0,height),(width,height),(width,0)]]

                    # ----------------------
                    # ③ 区域判断
                    # ----------------------
                    valid_targets = []

                    for obj in results:
                        # obj 的格式是: [类别ID, "置信度", [xmin, ymin, xmax, ymax]]
                        bbox = obj[2]
                        xmin, ymin, xmax, ymax = bbox[0], bbox[1], bbox[2], bbox[3]

                        # 计算中心点坐标
                        center = ((xmin + xmax) / 2, (ymin + ymax) / 2)

                        # 判断中心点是否在报警区域内
                        if is_point_in_any_polygon(center, alarm_areas):
                            valid_targets.append(obj)

                    if len(valid_targets) == 0:
                        print("没有在区域内的目标")
                        continue



                    # ----------------------
                    # ★★★ 持续帧更新逻辑（必须每帧执行）★★★
                    # ----------------------
                    if len(valid_targets) > 0:
                        duration_lists[idx].append(1)
                    else:
                        duration_lists[idx].append(0)

                    # 限制窗口长度
                    duration_frame = int(duration_time)*25 // int(sensitivity)
                    # duration_frame = int(duration_time) * 25 // 25  # 等价于持续时间秒数 * 1FPS
                    if len(duration_lists[idx]) > duration_frame:
                        duration_lists[idx].pop(0)

                    # 如果当前帧没有有效目标，持续判断依然需要做，但后面无需报警
                    #（注意：不能直接 continue，否则持续时长永远无法被统计）
                    # 所以这里不 continue，而是让“持续时长判断”来决定是否继续执行报警流程

                    # ----------------------
                    # ④ 持续时长判断
                    # ----------------------
                    duration_alarm = duration_flag(duration_lists[idx], duration_frame, frame_ratio)
                    if not duration_alarm:
                        logging.info(f"[模型{idx}]不满足持续时长条件")
                        continue


                    # ----------------------
                    # ⑤ 报警间隔判断（独立）
                    # ----------------------
                    current_time = time.time()
                    if (current_time - last_alarm_times[idx]) < int(interval_time):
                        logging.info(f"[模型{idx}]不满足报警间隔")
                        continue


                    # ----------------------
                    # ⑥ 满足条件：执行报警
                    # ----------------------
                    logging.info(f"[模型{idx}]触发报警")
                    # 报警时刻一次取定（current_time）：报警视频文件名与上报的始末时间
                    # 共用同一时刻，保证平台记录与视频文件名逐秒一致（瞬时报警始末同值）。
                    # 返回的视频 URL 随上报进 warning_video（分析类型缺省 00=其它）。
                    video_url = alarm_video.trigger(conf_name, alarm_ts=current_time)
                    alarm_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))

                    image_paths, ori_image_paths = handle_alert(
                        output_img_dir, image_bgr, valid_targets, alarm_areas, model_name, equipment_ip, disp_names
                    )

                    # --------------- 日志写入 + 上传数据（独立） ---------------
                    # 放到后台线程并捕获异常：本回调在 GStreamer 流线程内同步执行，
                    # kafka/DB 卡顿会拖住整条取流管道；且原来裸调 upload_hwj，
                    # 一旦抛异常 → 图片已存、kafka 消息永久丢失。
                    # 用默认参数把循环变量（idx/res_type/algo_lib_id/图片列表）绑定进闭包。
                    def _report(idx=idx, res_type=res_type, algo_lib_id=algo_lib_id,
                                image_paths=image_paths, ori_image_paths=ori_image_paths,
                                alarm_str=alarm_str, video_url=video_url):
                        try:
                            data_send.insert_alg_log(
                                ip_address="None",
                                Level="INFO",
                                message=f"[模型{idx}]触发报警",
                                alg_name=conf_name
                            )
                            data_send.upload_hwj(
                                Algorithm_conf_id=conf_id,
                                res_type=res_type,
                                Mine_id=Mine_id,
                                Equipment_id=Equipment_id,
                                # Equipment_parent_id=parent_id,
                                carousel_images_list=image_paths,
                                ori_images_list=ori_image_paths,
                                result_count=None,
                                Entering_num=None,
                                Exiting_num=None,
                                result_count_time=alarm_str,
                                template_type_id=template_config_type_id,
                                template_id=template_id,
                                res_time=alarm_str,
                                conf_name=conf_name,
                                equipment_name=equipment_name,
                                equipment_ip=equipment_ip,
                                Algorithm_library_id=algo_lib_id,   # <- 各自不同
                                mine_code=mine_code,
                                warning_video=video_url,
                                # Hik_indexCode=Hik_indexCode
                            )
                        except Exception:
                            logging.exception(f"[模型{idx}]{conf_name}报警上报失败")
                    threading.Thread(target=_report, daemon=True).start()

                    last_alarm_times[idx] = current_time

        frame_count = 0
        for image_bgr in _s2m_frames(rtsp_url, pull_seconds):
            frame_count += 1
            if frame_count % sensitivity != 0:
                continue
            _process_frame(image_bgr)
