# -*- coding: utf-8 -*-
'''
model_start.py —— 算法调度主程序（按【视频流】分组：一路流多任务 = 一路流多模型并行）

与旧版的区别：
  - 旧版「一个算法配置(conf_name) 一个进程」：同一摄像头挂多个任务会重复拉流/解码、各自抢 NPU。
  - 新版「一路 rtsp_url 一个进程」：同一路流的多个可分组任务合并到一个进程，
    经 templates/rtsp_infer_push.py 引擎做「一路流多模型并行」——只拉一次/解一次/预处理去重一次，
    同帧扇出给该流所有模型并行推理（按 RK3588 三核 NPU 智能分核），barrier 聚合后把各模型结果
    分发给各自任务的 on_result 后处理（报警/计数…），合并画框后单条推流。

兼容性：
  - 平台状态上报仍【按 conf_name 逐条上报】（update_model_status / status_send），语义不变；
    分组只改变“进程的启停单位”。
  - 可分组任务：model_algo_data == "[]" 且 模板属于
      tcid=1（基础检测 / 携带危险物品，按 algorithm_name 第二段=="携带危险物品" 区分）、
      tcid=3（人数统计）、tcid=4 且 template_name=="领导换班"。
  - 单路多模类（model_algo_data != "[]"）仍走 muban_s2m，按 conf_name 单独起进程（不分组）。
  - 其它未适配模板：本轮跳过（仅日志）。
'''
import datetime
import argparse
import multiprocessing
import time
import os
import logging
import signal
import faulthandler
from logging.handlers import TimedRotatingFileHandler

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log", "model_start.log")
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
_POLL_SEC = 5
_RESTART_MAX_SEC = 60
_RESTART_RESET_SEC = 120


def _configure_logging(worker=False):
    # spawn 会重新导入本模块；不要在导入时建 DB 池、初始化原生库或打开共享滚动日志。
    # 子进程先写 stderr；流引擎随后按流设置自己的日志，父进程独占调度日志。
    if worker:
        handler = logging.StreamHandler()
    else:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        handler = TimedRotatingFileHandler(
            LOG_FILE, when="midnight", interval=1, backupCount=30,
            encoding="utf-8", utc=False)
        handler.suffix = "%Y-%m-%d.log"
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def _enable_faulthandler():
    try:
        faulthandler.enable(all_threads=True)
    except (OSError, RuntimeError, ValueError):
        logging.exception("无法开启原生崩溃调用栈记录")


def _load_runtime(worker=False):
    from templates import alarm_directory
    # comm 导入时创建数据库连接，模板导入时加载 OpenCV/SAIL。
    # 每个进程在显式入口中初始化，避免继承父进程已初始化的原生线程/句柄。
    if worker:
        # 流进程只需要上报用的 data_send（由模板导入）；不创建调度读取用的
        # data_receive 连接池，也不加载与本路任务无关的业务模板。
        global alarm_video, rtsp_infer_push, video_quality
        from templates import alarm_video, rtsp_infer_push, video_quality
    else:
        global data_send, data_receive, status_send
        from comm import data_send, data_receive, status_send


def _worker_entry(target, worker_args):
    selected = worker_args[0]
    row = selected[0] if isinstance(selected, list) else selected
    os.environ["TPU_DEV_ID"] = str(int(row.get("dev_id") or 0))
    _configure_logging(worker=True)
    _enable_faulthandler()
    try:
        _load_runtime(worker=True)
        target(*worker_args)
    except Exception:
        logging.exception("工作进程异常退出 pid=%s", os.getpid())
        raise


def _start_worker(target, worker_args):
    # 只更改本程序创建的进程，不修改全局 multiprocessing start method。
    os.environ.setdefault("PYTHONFAULTHANDLER", "1")
    p = multiprocessing.get_context('spawn').Process(
        target=_worker_entry, args=(target, worker_args), daemon=False)
    p.start()
    logging.info("工作进程已创建 pid=%s start_method=spawn", p.pid)
    return p

# 推流地址正常由 get_data 按 upload_ip 生成；此函数仅作同规则兜底。
def _build_push_url(equipment_id):
    return data_receive._build_push_url(equipment_id)


def test_rtsp(rtsp_url):
    '''用 OpenCV 尝试打开 RTSP 地址，检测视频流是否可用（True=在线，False=离线）。'''
    import cv2
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return False
    else:
        cap.release()
        return True


def in_defense_time(start, end):
    '''判断当前时间是否在布防时段 [start, end] 内（"HH:MM:SS" 字符串），支持跨天时段。'''
    now = datetime.datetime.now().time()
    start = datetime.datetime.strptime(start, "%H:%M:%S").time()
    end = datetime.datetime.strptime(end, "%H:%M:%S").time()
    if start <= end:
        return start <= now <= end
    else:
        # 跨天 22:00 - 06:00
        return now >= start or now <= end


def argsparser():
    '''解析命令行参数（NMS 阈值 / 是否启用 CPU 后处理加速），返回 args 对象。'''
    parser = argparse.ArgumentParser(prog=__file__)
    parser.add_argument('--nms_thresh', type=float, default=0.4, help='nms threshold')
    parser.add_argument('--use_cpu_opt', action="store_true", default=False, help='accelerate cpu postprocess')
    args, _ = parser.parse_known_args()
    return args


# ======================================================================
# 字段提取 + 路由
# ======================================================================
def _extract_fields(row):
    '''从一条数据库配置行提取模板入参（命名与各模板 build_spec/method 一致）。'''
    return dict(
        algorithm_path=row.get('algorithm_path'),
        algorithm_name=row.get('algorithm_name') or '',
        status=int(row.get('status', 1)),
        confidence=int(row.get('confidence', 50)) / 100,
        interval_time=row.get('interval_time'),
        duration_time=row.get('duration_time'),
        Algorithm_library_id=row.get('Algorithm_library_id'),
        conf_area=row.get('conf_area'),
        sensitivity=row.get('sensitivity'),
        template_name=row.get('template_name'),
        rtsp_url=row.get('rtsp_url'),
        conf_name=row.get('conf_name'),
        conf_id=row.get('Conf_id'),
        test_type_ename=row.get('label_list'),
        algorithm_type_list=row.get('algorithm_type_list'),
        equipment_name=row.get('equipment_name'),
        equipment_ip=row.get('equipment_ip'),
        Equipment_id=row.get('Equipment_id'),
        Mine_id=row.get('Mine_id'),
        mine_code=row.get('mine_code'),
        template_config_type_id=row.get('template_config_type_id'),
        template_id=row.get('template_id'),
        template_list_area=row.get('template_list_area'),
        image_count=row.get('image_count'),
        template_data=row.get('template_data'),
        model_status=row.get('model_status'),
        conf_status=row.get('conf_status'),
        res_type=row.get('res_type'),
        template_small_name=row.get('template_small_name'),
        conf_img_resolution=row.get('conf_img_resolution'),
        defense_time_start=row.get('defense_time_start'),
        defense_time_end=row.get('defense_time_end'),
        model_algo_data=row.get('model_algo_data', '[]'),
        cross_line_area=row.get('cross_line_area'),
        all_Entering_num=row.get('all_Entering_num'),
        all_Exiting_num=row.get('all_Exiting_num'),
        # 中文类别名（与 algorithm_type_list 同序），用于推流画面标签
        test_type_cname_list=row.get('test_type_cname_list'),
    )


def is_groupable(row):
    '''该配置是否可纳入“一路流多模型并行”分组。'''
    f = _extract_fields(row)
    if str(f['model_algo_data']) != '[]':
        return False
    tcid = f['template_config_type_id']
    if tcid == 1:
        return True
    if tcid == 3:
        return True
    if tcid == 4 and f['template_name'] in ('领导换班', '闸机尾随', '跨越闸机'):  # TAILGATE_DISPATCH_V1
        return True
    return False


def route_build_entry(row, args, label_prefix='', region_color=None):
    '''按模板类型选择对应模板的 build_spec，返回该任务条目（含 model_spec + 流参数提示）。
    仅用于“可分组”任务；不支持的返回 None。
    region_color: 该任务报警区域的推流描边色（BGR）。多任务同流时由编排层按任务序号
    从 rtsp_infer_push.REGION_COLORS 取（与 [A]/[B] 标签前缀同序），避免多个算法的
    区域全画成同一颜色分不清归属；None = 模板各自的历史默认色（单任务流外观不变）。'''
    f = _extract_fields(row)
    tcid = f['template_config_type_id']
    names_cn = f['test_type_cname_list']     # 中文类别名（与 algorithm_type_list 同序），用于推流标签
    print('[route] conf=%s tcid=%s names_cn=%r' % (f['conf_name'], tcid, names_cn))
    common = (1, args, f['template_name'], f['algorithm_path'], f['rtsp_url'],
              f['confidence'], f['conf_area'], f['algorithm_type_list'], f['test_type_ename'],
              f['sensitivity'], f['conf_id'], f['Equipment_id'], f['template_config_type_id'],
              f['template_id'], f['conf_name'], f['equipment_name'], f['equipment_ip'],
              f['interval_time'], f['template_list_area'], f['image_count'], f['template_data'],
              f['conf_status'], f['res_type'], f['template_small_name'], f['Algorithm_library_id'],
              f['conf_img_resolution'], f['defense_time_start'], f['defense_time_end'],
              f['duration_time'])
    if tcid == 1:
        parts = f['algorithm_name'].split('_')
        if len(parts) > 1 and parts[1] == '携带危险物品':
            from templates import dangerous
            logging.info("{}执行携带危险物品模板".format(f['conf_name']))
            return dangerous.build_spec(*common, label_prefix=label_prefix, names_cn=names_cn,
                                        Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                        region_color=region_color)
        from templates import base_model
        logging.info("{}执行基础检测模板".format(f['conf_name']))
        return base_model.build_spec(*common, label_prefix=label_prefix, names_cn=names_cn,
                                     Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                     region_color=region_color)
    if tcid == 3:
        from templates import muban_PersonCount
        logging.info("{}执行人数统计模板".format(f['conf_name']))
        return muban_PersonCount.build_spec(*common, f['all_Entering_num'], f['all_Exiting_num'], f['cross_line_area'],
                                            label_prefix=label_prefix, names_cn=names_cn,
                                            Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                            region_color=region_color)
    if tcid == 4 and f['template_name'] == '领导换班':
        from templates import muban_LeadSwitch
        logging.info("{}执行领导换班模板".format(f['conf_name']))
        return muban_LeadSwitch.build_spec(*common, label_prefix=label_prefix, names_cn=names_cn,
                                           Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                           region_color=region_color)
    if tcid == 4 and f['template_name'] == '闸机尾随':  # TAILGATE_DISPATCH_V1
        from templates import tailgate
        logging.info("{}执行闸机尾随模板".format(f['conf_name']))
        return tailgate.build_spec(*common, f['cross_line_area'],
                                   label_prefix=label_prefix, names_cn=names_cn,
                                   Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                   region_color=region_color)

    if tcid == 4 and f['template_name'] == '跨越闸机':  # CROSSING_DISPATCH_V1
        from templates import crossing
        logging.info("{}执行跨越闸机模板".format(f['conf_name']))
        return crossing.build_spec(*common, f['cross_line_area'],
                                   label_prefix=label_prefix, names_cn=names_cn,
                                   Mine_id=f['Mine_id'], mine_code=f['mine_code'],
                                   region_color=region_color)

    return None


# ======================================================================
# 进程入口（子进程内执行）
# ======================================================================
def _prefix_for(i):
    '''生成第 i 个任务的标签前缀（[A]/[B]/...，超过 26 个用数字），用于多任务同流时区分检测框。'''
    return '[%s]' % (chr(ord('A') + i) if i < 26 else str(i))


def stream_worker(rows, args, push_url=None):
    '''一路流子进程：把该流下所有可分组任务组装成多模型 cfg 并跑引擎（多模型并行 + 分发 + 单推流）。
    push_url 由编排层按配置的 upload_ip 构造，覆盖各模板内置默认值。'''
    # 在 build_spec/模型加载之前接通该路日志；run() 中再次调用是幂等的。
    # root handler 和 faulthandler 均写 fd 2，随引擎重定向及跨天轮转落盘。
    rtsp_infer_push._setup_logging({'rtsp_url': rows[0].get('rtsp_url') if rows else ''})
    # 报警视频文件名的 20 位摄像仪编码：同一路流各任务同设备，取第一条的 GB28181_code
    alarm_video.set_camera_code(rows[0].get('GB28181_code') if rows else None)
    entries = []
    multi = len(rows) > 1     # 单任务流不加 [A] 前缀，标签更干净；多任务才用 [A][B]… 区分
    for i, row in enumerate(rows):
        try:
            # 多任务同流：报警区域按任务序号取区分色（与 [A]/[B] 前缀同序），
            # 否则多个算法的区域全画成同一颜色分不清归属；单任务保持各模板默认色
            entry = route_build_entry(
                row, args, _prefix_for(i) if multi else '',
                region_color=rtsp_infer_push.region_color_for(i) if multi else None)
        except Exception:
            logging.exception("build_spec 失败 conf=%s" % row.get('conf_name'))
            entry = None
        if entry is not None:
            entries.append(entry)
    if not entries:
        logging.warning("该路流无可用任务，进程退出: %s" % (rows[0].get('rtsp_url') if rows else ''))
        return
    cfg = rtsp_infer_push.assemble_stream_cfg(entries, push_url=push_url)
    cfg['dev_id'] = int(rows[0].get('dev_id') or 0)
    # 视频质量监测（遮挡+挪动/过暗/过曝/模糊/冻结/丢失/抖动/分辨率）：周期借帧检测
    # （不另拉流、不占推理热路径），异常时存报警图并经 data_send 上报；
    # 报警身份复用该流第一个任务的配置
    cfg['occlusion'] = video_quality.quality_cfg_from_row(rows[0])
    logging.info("启动一路流: %s 推流=%s 任务=%s" % (rows[0].get('rtsp_url'), push_url,
                                            [r.get('conf_name') for r in rows]))
    rtsp_infer_push.run(cfg)





# ======================================================================
# 进程池管理
# ======================================================================
# stream_pool: rtsp_url -> {'proc': Process, 'sig': tuple}   （一路流多模型并行）
# s2m_pool:    conf_name -> Process                          （单路多模，不分组）
stream_pool = {}
s2m_pool = {}
_stream_retry = {}


def _exit_signal(exitcode):
    if exitcode is None or exitcode >= 0:
        return '-'
    try:
        return signal.Signals(-exitcode).name
    except ValueError:
        return str(-exitcode)


def _reap_process(p, label, stop=False):
    '''回收进程并记录真实退出码；未能终止时保留池条目，避免重复启动同一路流。'''
    if stop and p.is_alive():
        p.terminate()
        p.join(timeout=3)
        if p.is_alive():
            logging.warning("进程未响应 terminate，发送 kill [%s] pid=%s", label, p.pid)
            p.kill()
            p.join(timeout=3)
    else:
        p.join(timeout=0)
    if p.is_alive():
        logging.error("进程尚未退出，保留管理条目 [%s] pid=%s", label, p.pid)
        return False
    logging.warning("进程已回收 [%s] pid=%s exitcode=%s signal=%s",
                    label, p.pid, p.exitcode, _exit_signal(p.exitcode))
    return True


def _stream_ready(url, new_sig):
    retry = _stream_retry.get(url)
    if retry is None:
        return True
    if retry['sig'] != new_sig:
        # 人工配置变更立即生效，不受旧配置的故障退避约束。
        _stream_retry.pop(url, None)
        return True
    return time.monotonic() >= retry['next_at']


def _record_stream_exit(url, cur):
    p = cur['proc']
    if p.exitcode == 0:
        _stream_retry.pop(url, None)
        return
    now = time.monotonic()
    previous = _stream_retry.get(url, {})
    failures = previous.get('failures', 0)
    if previous.get('sig') != cur['sig'] or now - cur['started_at'] >= _RESTART_RESET_SEC:
        failures = 0
    failures = min(failures + 1, 5)
    delay = min(_RESTART_MAX_SEC, _POLL_SEC * (2 ** (failures - 1)))
    _stream_retry[url] = {'sig': cur['sig'], 'failures': failures, 'next_at': now + delay}
    logging.warning("流进程异常退出，%s 秒后允许重试（连续失败=%s）: %s", delay, failures, url)


def _kill_conf(conf_name, reason=""):
    '''终止并回收单路多模进程。'''
    p = s2m_pool.get(conf_name)
    if p is None:
        return
    logging.info(f"关闭进程[{conf_name}]，原因：{reason}")
    if _reap_process(p, conf_name, stop=True):
        s2m_pool.pop(conf_name, None)
        p.close()


def _kill_stream(url, reason=""):
    '''终止并回收一路流进程。'''
    _stream_retry.pop(url, None)
    cur = stream_pool.get(url)
    if cur is None:
        return True
    logging.info(f"关闭流进程[{url}]，原因：{reason}")
    p = cur['proc']
    if not _reap_process(p, url, stop=True):
        return False
    stream_pool.pop(url, None)
    p.close()
    return True


def _heartbeat():
    '''清理已退出的进程（两个池）。'''
    for conf_name in list(s2m_pool.keys()):
        p = s2m_pool[conf_name]
        if not p.is_alive() and _reap_process(p, conf_name):
            s2m_pool.pop(conf_name, None)
            p.close()
    for url in list(stream_pool.keys()):
        cur = stream_pool[url]
        p = cur['proc']
        if not p.is_alive() and _reap_process(p, url):
            _record_stream_exit(url, cur)
            stream_pool.pop(url, None)
            p.close()


def _group_signature(rows, push_url=None):
    '''一路流的签名：分配到的 push_url + 成员 conf_name + 各任务关键参数/几何；任一变化则热重启该流。'''
    from templates import rtsp_infer_push, muban_PersonCount
    sig = []
    for r in sorted(rows, key=lambda x: str(x.get('conf_name'))):
        polygons = rtsp_infer_push._parse_conf_area(r.get('conf_area'))
        region_sig = tuple(tuple(poly) for poly in polygons)
        cl = muban_PersonCount._parse_cross_line_area(r.get('cross_line_area'))
        cross_sig = None if not cl else (cl.get('p1'), cl.get('p2'), cl.get('direction'))
        sig.append((r.get('conf_name'), r.get('algorithm_path'), r.get('confidence'),
                    r.get('sensitivity'), r.get('template_config_type_id'),
                    r.get('template_name'), region_sig, cross_sig))
    return (push_url, tuple(sig))


def supervise_loop():
    '''主监管循环：每 5s 拉配置 → 逐条上报状态/判定合格 → 按 rtsp_url 分组启停流进程。'''
    _load_runtime()
    args = argsparser()
    while True:
        # 0) 心跳
        _heartbeat()

        original_list = data_receive.get_data()
        # None = 数据库读取失败：保留现有进程、下轮重试（避免 DB 抖动导致全量停起）。
        # [] = 配置确已全部删除：不能 continue，需继续往下走，由步骤 3/4 回收所有残留进程。
        if original_list is None:
            time.sleep(_POLL_SEC)
            continue

        db_conf_names = set(item["conf_name"] for item in original_list)
        eligible_group_rows = []     # 本轮应运行的“可分组”任务行

        # 1) 逐条：平台状态上报（按 conf）+ 判定是否应运行
        for row in original_list:
            conf_name = row["conf_name"]
            conf_id = row["Conf_id"]
            equipment_ip = row["equipment_ip"]
            rtsp_url = row["rtsp_url"]
            status = int(row["status"])
            model_status = row["model_status"]
            conf_status = row["conf_status"]
            defense_time_start = row["defense_time_start"]
            defense_time_end = row["defense_time_end"]
            rtsp_status = 1  # 与旧版一致：摄像头实际在线交由引擎重连判定，这里恒为 1


            # ================= 新增逻辑开始 =================
            # 在布防开始的前 5 秒内，针对“人员计数”模板重置进出人数（带防重复触发机制）
            try:
                now = datetime.datetime.now()
                current_time_str = now.strftime("%H:%M:%S")
                
                # 解析开始时间
                start_dt = datetime.datetime.strptime(defense_time_start, "%H:%M:%S")
                
                # 构造一个 5 秒的容错窗口：从开始时间，到开始时间 + 5秒
                # 例如：如果开始时间是 08:00:00，那么 08:00:00 ~ 08:00:05 都会触发
                end_window = (start_dt + datetime.timedelta(seconds=5)).strftime("%H:%M:%S")
                
                # 判断当前时间是否在这个 5 秒窗口内，且模板是“人员计数”，且还没重置过
                if (defense_time_start <= current_time_str <= end_window 
                        and row.get("template_name") == "人员计数" 
                        and not row.get("is_count_reset")):
                    
                    row["all_Exiting_num"] = 0
                    row["all_Entering_num"] = 0
                    logging.info(f"{conf_name} 命中布防开始5秒窗口，重置人员计数（进出人数归零）")
                    
            except Exception as e:
                logging.warning(f"{conf_name} 检查布防开始时间重置计数时发生异常: {e}")
            # ================= 新增逻辑结束 =================


            # RTSP 优先级最高
            if not rtsp_status or rtsp_url is None:
                logging.info(f"{conf_name} 推流失败: {rtsp_url}")
                data_send.update_model_status(3, conf_name)
                status_send.sync_model_status_to_main_system(conf_id, conf_name, 3, equipment_ip)
                _kill_conf(conf_name, "RTSP 不在线")
                continue
            if model_status == 3:
                logging.info(f"{conf_name} RTSP恢复")
                data_send.update_model_status(1, conf_name)
                status_send.sync_model_status_to_main_system(conf_id, conf_name, 1, equipment_ip)

            # 停止运行
            if status == 2:
                logging.info(f"停止中的模板：{conf_name}")
                data_send.update_model_status(4, conf_name)
                status_send.sync_model_status_to_main_system(conf_id, conf_name, 4, equipment_ip)
                _kill_conf(conf_name, "停止运行")
                continue
            # 配置更新：本轮排除该任务（下一轮 conf_status 置 1 后重新纳入并重启所属流）
            elif status == 1 and conf_status == 0:
                logging.info(f"更新模板：{conf_name}")
                data_send.update_conf_status(1, conf_name)
                data_send.update_model_status(1, conf_name)
                status_send.sync_model_status_to_main_system(conf_id, conf_name, 1, equipment_ip)
                _kill_conf(conf_name, "配置更新")
                continue

            # 布防时间
            if not in_defense_time(defense_time_start, defense_time_end):
                _kill_conf(conf_name, "超出布防时间")
                continue

            # 合格运行条件
            if not (status == 1 and model_status == 1 and conf_status == 1):
                continue

            if is_groupable(row):
                eligible_group_rows.append(row)               # 交“按流分组”统一调度
            elif str(row.get('model_algo_data', '[]')) != '[]':
                if conf_name not in s2m_pool:                  # 单路多模：按 conf 单独起进程
                    logging.info(f"启动单路多模模板：{conf_name}")
                    p = _start_worker(s2m_worker, (row, args))
                    s2m_pool[conf_name] = p
            else:
                logging.info(f"{conf_name} 模板未适配/不分组，跳过")

        # 2) 按 rtsp_url 分组；拉流主机可为 NVR，推流主机始终取 upload_ip
        groups = {}
        for row in eligible_group_rows:
            groups.setdefault((row["rtsp_url"], int(row.get("dev_id") or 0)), []).append(row)

        for url, grp in groups.items():
            # 推流地址优先用 get_data 组装值；缺失时仍按 upload_ip + Equipment_id 生成
            push_url = grp[0].get('push_url') or _build_push_url(grp[0].get('Equipment_id'))
            new_sig = _group_signature(grp, push_url)
            cur = stream_pool.get(url)
            if cur is None:
                if not _stream_ready(url, new_sig):
                    continue
                logging.info(f"启动流进程：{url} → 推流 {push_url}")
                p = _start_worker(stream_worker, (grp, args, push_url))
                stream_pool[url] = {'proc': p, 'sig': new_sig, 'started_at': time.monotonic()}
            elif new_sig != cur['sig']:
                logging.info(f"流配置/推流地址变化，热重启该路流: {url} → 推流 {push_url}")
                if _kill_stream(url, "配置变化"):
                    p = _start_worker(stream_worker, (grp, args, push_url))
                    stream_pool[url] = {'proc': p, 'sig': new_sig, 'started_at': time.monotonic()}

        # 3) 回收：本轮不再需要的流（无合格任务 / rtsp_url 消失）
        for url in list(stream_pool.keys()):
            if url not in groups:
                _kill_stream(url, "无合格任务/流下线")
        for url in list(_stream_retry):
            if url not in groups:
                _stream_retry.pop(url, None)

        # 4) 回收：数据库已删除的单路多模配置
        for conf_name in list(s2m_pool.keys()):
            if conf_name not in db_conf_names:
                _kill_conf(conf_name, "配置删除")

        # 5) 运行态打印
        running = [r.get('conf_name') for url, grp in groups.items()
                   if url in stream_pool and stream_pool[url]['proc'].is_alive()
                   for r in grp] + list(s2m_pool.keys())
        if running:
            logging.info(f"【当前运行中的任务】: {running}")
            print(f"【当前运行中的任务】: {running}")
        else:
            print("【当前没有运行中的任务】")

        time.sleep(_POLL_SEC)


if __name__ == '__main__':
    _configure_logging()
    _enable_faulthandler()
    supervise_loop()
