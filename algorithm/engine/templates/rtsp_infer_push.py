# coding:utf-8
'''
rtsp_infer_push.py —— 算能 BM1684X 统一【取流 → 推理 → 推流】引擎（一路流 / 多模型并行 / 各任务后处理分发）

**一路流多模型并行**：
同一路 RTSP 只拉一次、解一次、预处理按 img_size 去重一次，同帧扇出给该流下挂的所有模型并行推理
（BM1684X 单颗 TPU，各模型独占 sail.Engine 实例，TPU 上的执行由 bmruntime 调度），
barrier 聚合同一帧的全部结果后，**按模型把检测结果分发给各自任务的后处理回调 on_result**，最后合并画框、单条推流。

数据流：
  sail.MultiDecoder(RTSP, VPU 硬解，C++内部线程取流) → BMImage → VPP转BGR_PACKED → frame_queue(maxsize=1, 丢旧)
        │
   [decode] 只做 read + VPP 设备侧转换（约 2ms/帧）。解码线程必须恒跟上流速：
            RTSP/TCP 下消费太慢会被流媒体服务端丢弃积压 RTP 包（连接不断开），
            解码器收到残缺码流 → VPU 持续花屏（现场已实测复现），因此所有 CPU
            重活（numpy 拷贝/旋转/缩放/借帧回调）都移到 [pre] 线程，丢帧只发生
            在 frame_queue 丢旧（整帧粒度，无害）。
        │
   [pre]  BMImage→numpy + 旋转/缩放 + 借帧回调 + 预处理(按 img_size 去重，letterbox + RGB/255 → NCHW) → 扇出
        │
   [inf_post × N]  每个模型独占 bmodel 引擎并行推理 + YOLOv8 后处理 + 类别/区域过滤
        │
   [aggregator]  barrier 等齐同一 seq 的 N 个模型结果 →
        ├─ 逐模型调用 models[i]['on_result'](frame, results_i, w, h)  # 各任务后处理(报警/计数...)，不在共享帧上绘制
        ├─ 逐模型调用 models[i]['on_draw'](frame, w, h)               # 各任务推流叠加(报警区域/越线/面板…)，每帧
        └─ 合并各模型检测框，一次 draw_boxes → 投 push_q
        │
   [push]  BGR → BMImage → sail.Encoder(h264_bm/h265_bm) 硬编码推流

回调约定（每个 model_spec 的 on_result，可为 None）：
  - 仅在【该模型自己的推理帧】上（由各自 extract_count 独立判定，可不相同）、按 seq 升序、
    对该模型的结果调用一次（不丢帧；报警/计数依赖帧间时序）。非推理帧复用该模型 last_results 画框。
  - results 格式：[[cls_id:int, '%.2f'%score:str, [xmin, ymin, xmax, ymax]], ...]
                   已按该模型的 category_id / obj_thresh （及可选 regions_np）过滤。
  - frame 是该路流所有任务共享的帧；**on_result 阶段禁止在 frame 上原地绘制**——此阶段各任务
    会各自 frame.copy() 存自己的报警图，若在共享帧上画区域/面板会污染同一路流其它任务的报警图
    （表现为"某模型报警图里出现了别的模型的区域/面板"）。推流叠加请放到 on_draw。
  - 返回值被忽略（推流帧由引擎统一管理；不要在回调里替换帧对象）。
  - 注意：回调在聚合线程内同步执行，存图/上报等耗时操作请放到各自的独立线程
    （人数统计的会话上报即如此），避免拖慢热路径。

绘制约定（每个 model_spec 的 on_draw，可为 None）：
  - 仅在推流开启时调用；对**每个推流帧**（含跳帧）按 seq 调用一次，在 on_result 全部跑完之后执行，
    所以此时各任务的报警图已存好，可安全地在共享推流帧上原地叠加自己的常显覆盖层
    （报警区域、越线方向、计数面板…）。检测框随后由引擎统一合并绘制（叠在覆盖层之上）。

'''

import os
import re
import gc
import sys
import copy
import json
import time
import queue
import base64
import signal
import socket
import logging
import threading
from comm.sophon_task_health import WorkerHealth
from collections import deque
from functools import lru_cache
from urllib.parse import quote, urlparse, urlsplit, urlunsplit
from typing import Any, Dict, List, Tuple



import cv2
import numpy as np
import sophon.sail as sail
from PIL import Image, ImageDraw, ImageFont
from models import yolov8_sophon as y8
from templates import alarm_video


# ======================================================================
# 运行日志：每路流子进程把「全部输出」汇到一个 log/rtsp_infer_push_<流标识>.log
# ======================================================================
# 关键点：SAIL / bmruntime 等 C 库是【直接写 fd 1/2(stdout/stderr)】的，
# Python 的 logging 层根本拦不到。所以要把「全部日志保存到一起」，必须在进程内用 os.dup2
# 把 fd 1/2 重定向到日志文件——这样 C 库输出、print、Python logging 就全落进同一个文件。
# 同时保留原始 stderr 作为控制台回显目标，只把【格式化后的引擎日志】打到终端，方便现场观察
# （海量的 SAIL/bmruntime 原始日志只进文件、不刷屏）。每路流一个文件，多路流互不干扰。
logger = logging.getLogger('rtsp_infer_push')

# log/ 目录：与 model_start.log 同级（templates 的上一级 = 工程根目录）
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log')

# 日志等级：0=关 1=错误 2=警告 3=信息 4=常用调试 5=全量调试
_RTSP_LOG_LEVELS = {'0': logging.CRITICAL + 10, '1': logging.ERROR, '2': logging.WARNING,
                    '3': logging.INFO, '4': logging.INFO, '5': logging.DEBUG}
_logging_ready = False
_logfile = None        # 持有重定向目标文件对象，防止被 GC 关闭（fd 1/2 仍引用它）
# 日志按日轮转：归档为 <文件名>.YYYY-MM-DD[.N]，最多保留 RTSP_LOG_KEEP_DAYS 天（默认 7）
_LOG_KEEP_DAYS = max(1, int(os.environ.get('RTSP_LOG_KEEP_DAYS', '7') or 7))


def _archive_name(fpath, day):
    '''生成归档名 <fpath>.<day>；已存在则追加序号，同日多次归档不互相覆盖。'''
    dst = '%s.%s' % (fpath, day)
    i = 1
    while os.path.exists(dst):
        dst = '%s.%s.%d' % (fpath, day, i)
        i += 1
    return dst


def _purge_old_logs(fpath):
    '''删除超出保留窗口的归档（<文件名>.YYYY-MM-DD[.N]）。当前文件不动。
    保留窗口=当天 + 之前 _LOG_KEEP_DAYS-1 天，即磁盘上最多 _LOG_KEEP_DAYS 天的日志。'''
    cutoff = time.strftime('%Y-%m-%d', time.localtime(time.time() - (_LOG_KEEP_DAYS - 1) * 86400))
    log_dir = os.path.dirname(fpath)
    pat = re.compile(re.escape(os.path.basename(fpath)) + r'\.(\d{4}-\d{2}-\d{2})(?:\.\d+)?$')
    try:
        names = os.listdir(log_dir)
    except OSError:
        return
    for name in names:
        m = pat.match(name)
        if m and m.group(1) < cutoff:      # ISO 日期字符串可直接比大小
            try:
                os.remove(os.path.join(log_dir, name))
            except OSError:
                pass


def _rotate_stale_log(fpath):
    '''启动补轮转：上次运行留下的日志若最后写入不在今天（断电跨天/停用数日后再启动），
    先按其 mtime 日期归档，保证当前文件里只有当天内容。'''
    try:
        if not os.path.exists(fpath) or os.path.getsize(fpath) <= 0:
            return
        mday = time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(fpath)))
        if mday != time.strftime('%Y-%m-%d'):
            os.rename(fpath, _archive_name(fpath, mday))
    except OSError:
        pass


def _log_rotation_loop(fpath):
    '''日志轮转守护线程：跨天时把当前文件改名归档，重开新文件并把 fd 1/2 重新 dup2
    过去——C 库输出跟着 fd 走，Python logging 的 StreamHandler(sys.stderr) 也跟着 fd 走，
    所以两边都无须重建 handler。用"每分钟对比日期"而非"睡到零点"，NTP 校时/时钟跳变下依然稳。'''
    global _logfile
    opened_day = time.strftime('%Y-%m-%d')
    while True:
        time.sleep(60)
        today = time.strftime('%Y-%m-%d')
        if today == opened_day:
            continue
        try:
            dst = _archive_name(fpath, opened_day)
            os.rename(fpath, dst)      # Linux 上改名打开中的文件安全，fd 仍短暂跟着旧 inode
            new_f = open(fpath, 'a', buffering=1, encoding='utf-8')
            sys.stdout.flush(); sys.stderr.flush()
            os.dup2(new_f.fileno(), 1)
            os.dup2(new_f.fileno(), 2)
            old, _logfile = _logfile, new_f
            try:
                if old is not None:
                    old.close()
            except Exception:
                pass
            logger.info('[log] 日志已按日轮转：%s（最多保留 %d 天）',
                        os.path.basename(dst), _LOG_KEEP_DAYS)
        except Exception:
            logger.exception('[log] 日志轮转失败，继续写原文件，明天再试')
        opened_day = today
        _purge_old_logs(fpath)


def _stream_tag(cfg) -> str:
    '''由 rtsp_url 生成短标识（host_末段路径），用于区分并发的多路流日志文件。'''
    try:
        u = urlparse(str(cfg.get('rtsp_url') or ''))
        seg = (u.path or '').rstrip('/').split('/')[-1]
        raw = '%s_%s' % (u.hostname or 'stream', seg or 'live')
    except Exception:
        raw = 'stream'
    return re.sub(r'[^0-9A-Za-z_.-]', '_', raw)[:40] or 'stream'


def _setup_logging(cfg):
    '''把本进程「全部输出」汇到一起（幂等）。两种模式：

    默认(RTSP_LOG_REDIRECT!=0)：用 os.dup2 把 fd 1/2 重定向到 log/rtsp_infer_push_<流标识>.log，
      连 SAIL/bmruntime 等 C 库直接写 stdout/stderr 的内容也一并落盘；Python 引擎日志（带时间戳）
      同处该文件；并保留原始终端做回显，只显示格式化后的引擎日志（海量 C 日志只进文件、不刷屏）。
      —— 每路流一个自包含的日志文件，无需任何 shell 包装。

    RTSP_LOG_REDIRECT=0：不重定向，引擎日志照常写继承的 stdout/stderr。此时若想“系统级单文件”，
      用 shell 兜住全部进程即可：  python3 model_start.py 2>&1 | tee -a log/full.log

    等级用 RTSP_LOG_LEVEL(0~5) 调，默认 3=信息；RTSP_LOG_CONSOLE=0 可关闭终端回显。
    日志按日轮转：跨天归档为 <文件>.YYYY-MM-DD，最多保留 RTSP_LOG_KEEP_DAYS 天（默认 7）。'''
    global _logging_ready, _logfile
    if _logging_ready:
        return
    level = _RTSP_LOG_LEVELS.get(str(os.environ.get('RTSP_LOG_LEVEL', '3')), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False    # 不向上冒泡到 model_start 的 root handler，避免重复写进 model_start.log

    redirect = os.environ.get('RTSP_LOG_REDIRECT', '1') != '0'
    console = None              # 原始终端（回显用）
    if redirect:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            fpath = os.path.join(_LOG_DIR, 'rtsp_infer_push_%s.log' % _stream_tag(cfg))
            _rotate_stale_log(fpath)    # 跨天重启：把上次运行留下的旧日志先按日期归档
            _purge_old_logs(fpath)      # 顺手清理超过保留天数的归档
            _logfile = open(fpath, 'a', buffering=1, encoding='utf-8')   # 行缓冲，尽量按行落盘
            try:
                console = os.fdopen(os.dup(2), 'w', buffering=1)         # 先备份原始 stderr
            except Exception:
                console = None
            sys.stdout.flush(); sys.stderr.flush()
            os.dup2(_logfile.fileno(), 1)   # stdout → 文件（C 库 / print 都进这里）
            os.dup2(_logfile.fileno(), 2)   # stderr → 文件（SAIL/bmruntime 的 C 日志都进这里）
        except Exception as e:
            print('[log] stdout/stderr 重定向失败，退回继承的 stdout/stderr:', e)
            redirect = False

    fmt = logging.Formatter('%(asctime)s - %(levelname)s - [pid %(process)d] %(message)s')
    # ① 主输出：sys.stderr（重定向后=文件；未重定向=继承的终端/被 shell tee 兜住）
    fh = logging.StreamHandler(sys.stderr)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # ② 终端回显：仅在做了重定向时才需要（否则 ① 本身就在终端，别重复打印）
    if redirect and console is not None and os.environ.get('RTSP_LOG_CONSOLE', '1') != '0':
        ch = logging.StreamHandler(console)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    if redirect:
        # 按日轮转 + 最多保留 _LOG_KEEP_DAYS 天（RTSP_LOG_KEEP_DAYS 可调，默认 7）
        threading.Thread(target=_log_rotation_loop, args=(fpath,),
                         daemon=True, name='log-rotate').start()
    _logging_ready = True


# ======================================================================
# 0/1. 预处理 + YOLOv8 后处理（统一封装在 models/yolov8_sophon.py，此处薄转发）
# ======================================================================
def preprocess_for_yolo(image_bgr, size):
    '''BGR(任意尺寸) → letterbox(114 填充) → RGB/255 → NCHW float32。
    返回 (blob, ratio, txy) 三元组，后两者供后处理把框映射回原图（见 yolov8_sophon.preprocess）。'''
    return y8.preprocess(image_bgr, size)


# ======================================================================
# 2. 画框工具（引擎合并画框 + 各模板后处理复用）
# ======================================================================
# 系统常见 CJK 字体兜底位置（项目内 fonts/ 找不到指定字体时按序尝试）
_SYSTEM_CJK_FONTS = (
    '/data/AIGO/platform_start/runtime/fonts/truetype/wqy/wqy-microhei.ttc',
    '/data/AIGO/platform_start/runtime/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/data/AIGO/platform_start/runtime/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc',
    '/data/AIGO/platform_start/runtime/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/data/AIGO/platform_start/runtime/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/data/AIGO/platform_start/runtime/fonts/truetype/droid/DroidSansFallbackFull.ttf',
    '/data/AIGO/platform_start/runtime/fonts/truetype/arphic/uming.ttc',
)


@lru_cache(maxsize=16)
def _resolve_font_path(font_path: str) -> str:
    '''解析中文字体路径：绝对路径/当前目录/脚本同目录 → 都没有则在系统常见 CJK 字体里兜底。'''
    if os.path.isabs(font_path) and os.path.exists(font_path):
        return font_path
    if os.path.exists(font_path):
        return os.path.abspath(font_path)
    script_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), font_path)
    if os.path.exists(script_font_path):
        return script_font_path
    for p in _SYSTEM_CJK_FONTS:
        if os.path.exists(p):
            logger.warning('[font] 指定字体 %r 未找到，改用系统 CJK 字体: %s', font_path, p)
            return p
    logger.warning('[font] 警告：未找到中文字体 %r，也无系统 CJK 字体；中文标签将无法渲染。'
                   '可执行: apt-get install -y fonts-wqy-microhei', font_path)
    return font_path


@lru_cache(maxsize=8)
def _get_pil_font(font_path: str, text_size: int) -> ImageFont.FreeTypeFont:
    '''加载并缓存 PIL 字体对象（中文标签渲染用），避免每次绘制重复读字体文件。'''
    return ImageFont.truetype(_resolve_font_path(font_path), text_size, encoding="utf-8")


@lru_cache(maxsize=1024)
def _get_pil_text_bitmap(text: str, font_path: str, text_size: int,
                         text_rgb: Tuple[int, int, int]) -> Tuple[np.ndarray, np.ndarray]:
    """中文文本渲染成小位图 + alpha 掩码，缓存复用（cv2.putText 不支持中文）。"""
    font = _get_pil_font(font_path, text_size)
    if hasattr(font, 'getbbox'):
        left, top, right, bottom = font.getbbox(text)
    else:
        left, top = 0, 0
        right, bottom = font.getsize(text)
    width = max(1, right - left)
    height = max(1, bottom - top)
    rgba_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba_img)
    color = (int(text_rgb[0]), int(text_rgb[1]), int(text_rgb[2]), 255)
    draw.text((-left, -top), text, color, font=font)
    rgba = np.asarray(rgba_img, dtype=np.uint8)
    text_bgr = np.ascontiguousarray(rgba[:, :, 2::-1])
    alpha = np.ascontiguousarray(rgba[:, :, 3])
    return text_bgr, alpha


def _paste_text_bitmap_bgr(image: np.ndarray, text_bgr: np.ndarray,
                           alpha: np.ndarray, left: int, top: int) -> None:
    """把缓存文本位图按 alpha 混合贴到 BGR 图局部 ROI。"""
    left = int(left)
    top = int(top)
    img_h, img_w = image.shape[:2]
    text_h, text_w = alpha.shape[:2]
    x0 = max(0, left)
    y0 = max(0, top)
    x1 = min(img_w, left + text_w)
    y1 = min(img_h, top + text_h)
    if x0 >= x1 or y0 >= y1:
        return
    sx0 = x0 - left
    sy0 = y0 - top
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    roi = image[y0:y1, x0:x1]
    src = text_bgr[sy0:sy1, sx0:sx1]
    a = alpha[sy0:sy1, sx0:sx1]
    if not np.any(a):
        return
    a16 = a.astype(np.uint16)[:, :, None]
    roi16 = roi.astype(np.uint16)
    src16 = src.astype(np.uint16)
    roi[:] = ((src16 * a16 + roi16 * (255 - a16) + 127) // 255).astype(np.uint8)


def str_contain_chinese(s):
    '''判断字符串是否含中文字符（含则用 PIL 渲染标签，否则用 cv2.putText）。'''
    for ch in s:
        if u'一' <= ch <= u'鿿':
            return True
    return False


_LABEL_COLOR_PALETTE_BGR: Tuple[Tuple[int, int, int], ...] = (
    (60, 179, 113), (66, 66, 244), (255, 144, 30), (0, 215, 255),
    (212, 0, 148), (50, 205, 154), (180, 105, 255), (255, 191, 0),
    (0, 140, 255), (208, 224, 64), (47, 255, 173), (139, 61, 72),
    (34, 34, 178), (0, 100, 0), (130, 0, 75), (203, 192, 255),
)

_StyleT = Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]
_LABEL_STYLE_MAP: Dict[str, _StyleT] = {}
_KNOWN_LABEL_PREFIXES: List[str] = []
_LABEL_COLOR_LOCK = threading.Lock()


def _build_style(rect_bgr: Tuple[int, int, int]) -> _StyleT:
    '''按框色亮度(BT.601)预算文本颜色：亮底配黑字、暗底配白字，返回 (框色, 文本BGR, 文本RGB)。'''
    b, g, r = rect_bgr
    luma = 0.114 * b + 0.587 * g + 0.299 * r
    if luma > 160:
        text_bgr = (0, 0, 0)
        text_rgb = (0, 0, 0)
    else:
        text_bgr = (255, 255, 255)
        text_rgb = (255, 255, 255)
    return (rect_bgr, text_bgr, text_rgb)


def register_label_colors(labels, prefixes=None) -> None:
    '''拿到所有模型类别名后调用一次：基础类别名按调色板顺序固定分配颜色（跨模型同名同色）；
    多模型前缀（如 '[A]'/'[B]'）注册到全局，便于从合并 label 剥离前缀拿 base 的稳定颜色。'''
    global _KNOWN_LABEL_PREFIXES
    palette = _LABEL_COLOR_PALETTE_BGR
    with _LABEL_COLOR_LOCK:
        for name in labels:
            if not name:
                continue
            if name in _LABEL_STYLE_MAP:
                continue
            idx = len(_LABEL_STYLE_MAP) % len(palette)
            _LABEL_STYLE_MAP[name] = _build_style(palette[idx])
        if prefixes:
            seen = set(_KNOWN_LABEL_PREFIXES)
            for p in prefixes:
                if p and p not in seen:
                    _KNOWN_LABEL_PREFIXES.append(p)
                    seen.add(p)
            _KNOWN_LABEL_PREFIXES.sort(key=len, reverse=True)
        bases = list(_LABEL_STYLE_MAP.keys())
        for base in bases:
            base_style = _LABEL_STYLE_MAP[base]
            for p in _KNOWN_LABEL_PREFIXES:
                full = p + base
                if full not in _LABEL_STYLE_MAP:
                    _LABEL_STYLE_MAP[full] = base_style
        logger.info('[colors] 已注册 %d 个标签颜色(含预烘组合); 前缀: %s',
                    len(_LABEL_STYLE_MAP), _KNOWN_LABEL_PREFIXES)


def _strip_known_prefixes(label: str) -> str:
    '''从合并 label 中迭代剥离已注册前缀，例如 "[A][B]人" -> "人"。'''
    if not _KNOWN_LABEL_PREFIXES:
        return label
    s = label
    changed = True
    while changed and s:
        changed = False
        for p in _KNOWN_LABEL_PREFIXES:
            if s.startswith(p):
                s = s[len(p):]
                changed = True
                break
    return s


def _style_for_label(name: str) -> _StyleT:
    '''取标签对应的绘制样式：已注册直接查表；未命中先剥前缀找 base，再退化为名称哈希取色并写回缓存。'''
    style = _LABEL_STYLE_MAP.get(name)
    if style is not None:
        return style
    base = _strip_known_prefixes(name)
    if base != name:
        style = _LABEL_STYLE_MAP.get(base)
    if style is None:
        h = 0
        for ch in (base or name).encode('utf-8'):
            h = (h * 131 + ch) & 0xFFFFFFFF
        style = _build_style(_LABEL_COLOR_PALETTE_BGR[h % len(_LABEL_COLOR_PALETTE_BGR)])
    _LABEL_STYLE_MAP[name] = style
    return style


def draw_boxes(image, result_lst, img_width, img_height, font_path='fonts/wqy-microhei.ttc'):
    '''在 BGR 图上绘制检测框 + 标签（类别名 + 置信度），中文用 PIL 渲染，不同类别稳定不同色。
    result_lst: [[name, score_str, [xmin, ymin, xmax, ymax]], ...]（name 为字符串类别名，可含前缀）。'''
    tl = round(0.002 * (img_width + img_height) / 2) + 1
    tf = max(tl - 1, 1)
    cv2_font_scale = tl / 3
    pil_font_size = tf * 10
    cv_rect = cv2.rectangle
    cv_putText = cv2.putText
    cv_getTextSize = cv2.getTextSize
    line_aa = cv2.LINE_AA
    style_get = _style_for_label
    for result in result_lst:
        name, score, (xmin, ymin, xmax, ymax) = result
        rect_bgr, text_bgr, text_rgb = style_get(name)
        cv_rect(image, (xmin, ymin), (xmax, ymax), rect_bgr, tl, line_aa)   # 框先画，永远保留
        label = '%s %s' % (name, score)
        try:
            has_chinese = str_contain_chinese(label)
            if not has_chinese:
                tw, th = cv_getTextSize(label, 0, fontScale=cv2_font_scale, thickness=tf)[0]
                text_bgr_img = None
                text_alpha = None
            else:
                text_bgr_img, text_alpha = _get_pil_text_bitmap(label, font_path, pil_font_size, text_rgb)
                th, tw = text_alpha.shape[:2]
            text_xmin = xmin
            text_ymin = ymin - th - 3
            text_xmax = xmin + tw
            text_ymax = ymin
            if text_xmax > img_width:
                text_xmin = max(0, img_width - tw)
                text_xmax = img_width
            if text_ymin < 0:
                text_ymin = ymin
                text_ymax = ymin + th + 3
            cv_rect(image, (text_xmin, text_ymin), (text_xmax, text_ymax), rect_bgr, -1, line_aa)
            if not has_chinese:
                cv_putText(image, label, (text_xmin, text_ymax - 3), 0, cv2_font_scale, text_bgr,
                           thickness=tf, lineType=line_aa)
            else:
                _paste_text_bitmap_bgr(image, text_bgr_img, text_alpha, text_xmin, text_ymax - 3 - th)
        except Exception:
            continue   # 标签渲染失败（如缺中文字体）→ 只保留检测框，不影响其它目标
    return image


def results_to_named(results, names, prefix=''):
    '''[cls_id, score_str, box] -> [name(可含前缀), score_str, box]，给 draw_boxes 用。
    names 缺该 id 时退化为字符串 id。'''
    named = []
    n = len(names) if names else 0
    # SITE_PATCH_RESULTS_ROW_V1: pose rows carry an extra keypoints column
    for row in results:
        cid, score, box = row[0], row[1], row[2]
        try:
            cid_i = int(cid)
        except (TypeError, ValueError):
            cid_i = -1
        base = names[cid_i] if 0 <= cid_i < n else str(cid)
        label = ('%s%s' % (prefix, base)) if prefix else str(base)
        named.append([label, score, box])
    return named


# ======================================================================
# 2.5 报警区域（model_spec 的 regions_np 字段）解析 / 过滤 / 绘制
#     过滤发生在引擎推理阶段（_box_in_polygons）；解析/绘制供各模板整理 spec、on_draw 叠加复用
# ======================================================================
def _parse_conf_area(raw: Any) -> List[List[Tuple[int, int]]]:
    '''解析 conf_area 字段为多边形列表 [[(x,y),...], ...]。'''
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            data = json.loads(s)
        except (ValueError, TypeError) as e:
            logger.warning('[regions] conf_area JSON 解析失败: %s | raw=%r', e, raw[:120])
            return []
    if not isinstance(data, list):
        return []
    polygons: List[List[Tuple[int, int]]] = []
    for poly in data:
        if not isinstance(poly, list):
            continue
        if len(poly) == 1 and isinstance(poly[0], dict) and isinstance(poly[0].get('data'), list):
            poly = poly[0]['data']
        pts: List[Tuple[int, int]] = []
        for p in poly:
            if isinstance(p, dict) and isinstance(p.get('data'), list):
                for child in p['data']:
                    if not isinstance(child, dict):
                        continue
                    try:
                        x = int(float(child.get('x')))
                        y = int(float(child.get('y')))
                    except (TypeError, ValueError):
                        continue
                    pts.append((x, y))
                continue
            if not isinstance(p, dict):
                continue
            try:
                x = int(float(p.get('x')))
                y = int(float(p.get('y')))
            except (TypeError, ValueError):
                continue
            pts.append((x, y))
        if len(pts) >= 3:
            polygons.append(pts)
    return polygons


def _polygons_to_np(polygons: List[List[Tuple[int, int]]]) -> List[np.ndarray]:
    '''多边形点列表 → cv2 使用的 int32 点阵。'''
    out: List[np.ndarray] = []
    for poly in polygons:
        if len(poly) >= 3:
            out.append(np.asarray(poly, dtype=np.int32).reshape(-1, 1, 2))
    return out


def _box_in_polygons(box, polygons_np: List[np.ndarray]) -> bool:
    '''检测框中心点是否落在任一多边形内（未配置区域则视为全图命中）。'''
    if not polygons_np:
        return True
    xmin, ymin, xmax, ymax = box
    cx = (xmin + xmax) * 0.5
    cy = (ymin + ymax) * 0.5
    for poly_np in polygons_np:
        if cv2.pointPolygonTest(poly_np, (cx, cy), False) >= 0:
            return True
    return False


# 多任务同流时各任务报警区域的区分色（BGR），与检测框 [A]/[B]… 标签前缀同序：
# 任务 A=黄 B=绿 C=品红 D=青 E=橙 F=蓝 G=粉 H=红，超过 8 个循环取用。
# 索引 0 保持历史黄色 —— 单任务流不传色时各模板仍用自己原有的默认色，外观不变。
REGION_COLORS = [(0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 255, 0),
                 (0, 165, 255), (255, 144, 30), (203, 192, 255), (0, 0, 255)]


def region_color_for(i):
    '''第 i 个任务的报警区域颜色（一路流多任务时按任务序号区分，同 [A]/[B] 前缀次序）。'''
    return REGION_COLORS[i % len(REGION_COLORS)]


def draw_alarm_regions(image, polygons_np: List[np.ndarray], color_bgr=(0, 0, 255),
                       thickness: int = 3, fill_alpha: float = 0.0):
    '''在图上绘制报警区域多边形（描边 + 可选半透明填充）。'''
    if not polygons_np:
        return image
    if fill_alpha > 0:
        overlay = image.copy()
        cv2.fillPoly(overlay, polygons_np, color_bgr)
        cv2.addWeighted(overlay, fill_alpha, image, 1.0 - fill_alpha, 0, dst=image)
    cv2.polylines(image, polygons_np, isClosed=True, color=color_bgr,
                  thickness=thickness, lineType=cv2.LINE_AA)
    return image


# ======================================================================
# 3. SAIL 硬件编解码与图像转换
# ======================================================================
def _rtsp_url_with_credentials(rtsp_url, user_id=None, user_pw=None):
    '''SAIL Decoder 不提供独立 user-id/user-pw 参数；URL 未带鉴权信息时将配置注入 URL。'''
    if not user_id:
        return rtsp_url
    try:
        parts = urlsplit(rtsp_url)
        if parts.username is not None or '@' in parts.netloc:
            return rtsp_url
        host = parts.hostname or ''
        if ':' in host and not host.startswith('['):
            host = '[%s]' % host
        port = ':%d' % parts.port if parts.port else ''
        auth = '%s:%s@' % (quote(str(user_id), safe=''), quote(str(user_pw or ''), safe=''))
        return urlunsplit((parts.scheme, auth + host + port, parts.path, parts.query, parts.fragment))
    except Exception:
        logger.warning('[SAIL Decoder] RTSP 鉴权信息注入失败，使用原始 URL')
        return rtsp_url


def _bmimage_to_packed(image, handle, bmcv):
    '''SAIL Decoder 输出 BMImage → BGR_PACKED BMImage（VPP 设备侧转换，实测约 1.5ms/帧）。

    解码线程只做这一步：转换结果占独立设备内存，不再引用解码器的 VPU 帧缓冲，
    numpy 拷贝等 CPU 重活全部移交 [pre] 线程。解码线程必须恒跟上流速——RTSP/TCP
    下消费太慢会触发流媒体服务端(mediamtx)丢弃积压 RTP 包，解码器收到残缺码流而
    持续花屏（现场实测：旧路径单帧 68ms 使消费降到 9.7fps < 流 20fps，VPU 报
    VPU_DecGetOutputInfo reason 0x00400000 并输出彩虹宏块）。'''
    h, w = int(image.height()), int(image.width())
    if h <= 0 or w <= 0:
        raise ValueError('解码帧尺寸无效: %dx%d' % (w, h))
    packed = sail.BMImage(
        handle, h, w, sail.Format.FORMAT_BGR_PACKED, sail.DATA_TYPE_EXT_1N_BYTE)
    # RTSP 解码帧通常是 YUV。优先走 VPP 做色彩/布局转换；旧版 SAIL
    # 没有 vpp_convert_format 时再退回 convert_format。
    convert = getattr(bmcv, 'vpp_convert_format', None)
    if not callable(convert):
        convert = bmcv.convert_format
    ret = convert(image, packed)
    if ret not in (0, None):
        raise RuntimeError('BMImage 转 BGR_PACKED 失败，返回码=%s' % ret)
    return packed


_PACKED_VIA_TENSOR = True   # packed→tensor 路径首次失败后永久改走 asmat（只告警一次）


def _packed_to_numpy(packed, bmcv):
    '''返回独立 BGR uint8 HWC 数组，不让下游依赖 SDK 临时对象的内存所有权。'''
    global _PACKED_VIA_TENSOR
    h, w = int(packed.height()), int(packed.width())
    if _PACKED_VIA_TENSOR and bmcv is not None:
        try:
            tensor = bmcv.bm_image_to_tensor(packed)
            arr = tensor.asnumpy()
            if arr.dtype != np.uint8 or arr.size != h * w * 3:
                raise ValueError('packed tensor 尺寸异常: %s' % (arr.shape,))
            # ascontiguousarray 对已连续内存可能不复制；保留 tensor 到 copy 完成。
            return np.array(arr.reshape(h, w, 3), dtype=np.uint8, order='C', copy=True)
        except Exception:
            _PACKED_VIA_TENSOR = False
            logger.exception('[pre] packed→tensor 路径不可用，永久改用 BMImage.asmat')
    arr = packed.asmat()
    if arr.dtype != np.uint8 or arr.shape != (h, w, 3):
        raise ValueError('packed asmat 格式异常: %s %s' % (arr.shape, arr.dtype))
    return np.array(arr, dtype=np.uint8, order='C', copy=True)


def _bgr_to_bmimage(image_bgr, handle, bmcv, pix_fmt='I420', upload_mode='tensor'):
    '''BGR ndarray → Encoder 所需的独立 I420/NV12 BMImage。

    默认经显式 Tensor 上传，避开 OpenCV Mat 的原生桥接；mat 模式仅用于兼容对比。
    返回 backing 保留设备对象；调用方在 Encoder.release 返回前保留队列中的引用。
    '''
    image_bgr = np.asarray(image_bgr)
    if image_bgr.dtype != np.uint8:
        raise ValueError('Encoder 输入 dtype 必须为 uint8，当前=%s' % image_bgr.dtype)
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError('Encoder 输入必须是 HxWx3 BGR 图像，当前=%s' % (image_bgr.shape,))
    h, w = image_bgr.shape[:2]
    pix_fmt = str(pix_fmt or 'I420').upper()
    if pix_fmt not in ('I420', 'NV12'):
        raise ValueError('Encoder 像素格式仅支持 I420/NV12，当前=%s' % pix_fmt)
    if h <= 0 or w <= 0 or (w & 1) or (h & 1):
        raise ValueError('%s 编码要求宽高为偶数，当前=%dx%d' % (pix_fmt, w, h))

    upload_mode = str(upload_mode).lower()
    backing = []
    if upload_mode == 'mat':
        mat_to_bm_image = getattr(bmcv, 'mat_to_bm_image', None)
        if not callable(mat_to_bm_image):
            raise RuntimeError('当前 SDK 不支持 mat_to_bm_image，请使用 tensor 上传')
        image_bgr = np.array(image_bgr, dtype=np.uint8, order='C', copy=True)
        backing.append(image_bgr)
        bgr_bm = sail.BMImage()
        try:
            ret = mat_to_bm_image(image_bgr, bgr_bm)
            if ret not in (0, None):
                raise RuntimeError('mat_to_bm_image 失败，返回码=%s' % ret)
        except TypeError:
            bgr_bm = mat_to_bm_image(image_bgr)
    elif upload_mode == 'tensor':
        chw = np.ascontiguousarray(
            np.transpose(image_bgr, (2, 0, 1))[None, ...], dtype=np.uint8)
        # 设备内存由 Tensor 持有；无 host 内存时 update_data 直接同步上传设备。
        # 不再把 numpy 数组作为 Tensor 的隐式后备存储。
        tensor = sail.Tensor(handle, list(chw.shape), sail.Dtype.BM_UINT8, False, True)
        tensor.update_data(chw)
        bgr_bm = bmcv.tensor_to_bm_image(tensor)
        backing.append(tensor)
    else:
        raise ValueError('SAIL 图像上传仅支持 tensor/mat，当前=%s' % upload_mode)
    backing.append(bgr_bm)

    target_format = (sail.Format.FORMAT_YUV420P if pix_fmt == 'I420'
                     else sail.Format.FORMAT_NV12)
    encoder_bm = sail.BMImage(
        handle, h, w, target_format, sail.DATA_TYPE_EXT_1N_BYTE)
    convert = getattr(bmcv, 'vpp_convert_format', None)
    if not callable(convert):
        convert = bmcv.convert_format
    ret = convert(bgr_bm, encoder_bm)
    if ret not in (0, None):
        raise RuntimeError('BGR 转 %s 失败，返回码=%s' % (pix_fmt, ret))
    backing.append(encoder_bm)
    return encoder_bm, tuple(backing)


def _rotate_decoded_frame(image_bgr, rotation):
    '''保持原管道语义：先旋转，再缩放到配置分辨率。'''
    if rotation == 90:
        image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == 180:
        image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_180)
    elif rotation == 270:
        image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image_bgr


def _analysis_frame(image_bgr, target_w, target_h):
    if (image_bgr.shape[1], image_bgr.shape[0]) != (target_w, target_h):
        image_bgr = cv2.resize(image_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(image_bgr)


def _configure_sail_decoder(cfg):
    '''Decoder 构造前设置 RTSP 可靠传输与帧缓存参数。

    算能官方 FAQ 指出：部分旧版 SAIL 在 RTSP 下把 extra_frame_buffer_num 设为20，
    叠加码流自身参考帧后可能超过单实例32帧上限，出现 FFmpeg 软解正常而
    sail.Decoder 异常/花屏。这里显式限制为官方默认建议值5（允许配置0~10）。
    '''
    setter = getattr(sail, 'set_decoder_env', None)
    if not callable(setter):
        logger.warning('[SAIL Decoder] 当前 SAIL 无 set_decoder_env，无法强制 RTSP/TCP')
        return
    timeout_us = max(1000000, int(float(cfg.get('pull_seconds', 5) or 5) * 1000000))
    options = {
        'rtsp_transport': str(cfg.get('rtsp_transport', 'tcp') or 'tcp'),
        'stimeout': str(timeout_us),
        'buffer_size': str(max(262144, int(cfg.get('decoder_buffer_size', 2097152) or 2097152))),
        'extra_frame_buffer_num': str(max(
            0, min(10, int(cfg.get('decoder_extra_frame_buffer_num', 5))))),
    }
    for name, value in options.items():
        try:
            setter(name, value)
        except Exception:
            logger.exception('[SAIL Decoder] 设置 %s=%s 失败', name, value)
    logger.info('[SAIL Decoder] transport=%s timeout=%sus buffer=%sB extra_frames=%s',
                options['rtsp_transport'], options['stimeout'], options['buffer_size'],
                options['extra_frame_buffer_num'])


def _encoder_push_url(cfg):
    '''编码器实际使用的推流地址（默认把 RTSP 地址重写为同路径 RTMP）。

    现场实测（2026-07-22，SDK v23.09 SP4 / SAIL 3.8.0 + mediamtx）：sail.Encoder 走
    RTSP 推流时握手成功但 RTP 一个包都发不出去——TCP 连接上只有控制报文、系统级
    UDP 发包计数为零、VPU 编码核在转但复用器无输出，且 enc_params 不支持
    rtsp_transport=tcp（构造即报 stoi）。改推 RTMP（mediamtx 对同一路径自动互通，
    下游读者仍用原 RTSP 地址）后立刻恢复正常。如现场需要规避该 SDK 问题，可配置
    push_transport='rtmp' 将 rtsp://host:8554/path 重写为 rtmp://host:<rtmp_port>/path；
    本项目默认使用 RTMP 发布。'''
    push_url = str(cfg.get('push_url') or '')
    transport = str(cfg.get('push_transport', 'rtmp') or 'rtmp').lower()
    enc_type = str(cfg.get('enc_type', 'h264')).lower()
    if transport != 'rtmp' or not push_url.startswith('rtsp://'):
        return push_url
    if enc_type != 'h264':
        logger.warning('[SAIL Encoder] %s 不适用 RTMP(FLV) 容器，保持原推流地址 %s',
                       enc_type, push_url)
        return push_url
    try:
        parts = urlsplit(push_url)
        host = parts.hostname or ''
        if ':' in host and not host.startswith('['):
            host = '[%s]' % host
        rtmp_port = int(cfg.get('rtmp_port', 1935) or 1935)
        target = 'rtmp://%s:%d%s' % (host, rtmp_port, parts.path or '')
        logger.info('[SAIL Encoder] 推流地址重写: %s -> %s（读者仍用原 RTSP 地址；'
                    'push_transport=rtsp 可禁用重写）', push_url, target)
        return target
    except Exception:
        logger.exception('[SAIL Encoder] RTMP 地址重写失败，使用原始 push_url')
        return push_url


def _create_sail_encoder(cfg, push_w, push_h):
    '''创建 SAIL 硬件编码器；I420 比 NV12 更稳健，输出地址见 _encoder_push_url。'''
    enc_type = str(cfg.get('enc_type', 'h264')).lower()
    enc_fmt = 'h264_bm' if enc_type == 'h264' else 'h265_bm'
    pix_fmt = str(cfg.get('encoder_pix_fmt', 'I420') or 'I420').upper()
    if pix_fmt not in ('I420', 'NV12'):
        raise ValueError('encoder_pix_fmt 仅支持 I420/NV12，当前=%s' % pix_fmt)
    fps = max(1, int(cfg.get('fps', 25) or 25))
    bitrate = max(1, int(cfg.get('bitrate', 2500) or 2500))
    gop = max(1, int(cfg.get('gop', fps) or fps))
    enc_params = (
        'width=%d:height=%d:bitrate=%d:gop=%d:gop_preset=2:framerate=%d'
        % (push_w, push_h, bitrate, gop, fps)
    )
    cache_length = max(1, int(cfg.get('encoder_cache', 10) or 10))
    push_target = _encoder_push_url(cfg)
    args = (push_target, int(cfg.get('dev_id', 0)), enc_fmt,
            pix_fmt, enc_params, cache_length)
    try:
        # 队列满时丢最旧帧，避免实时流越积越慢；旧版 SAIL 不支持该参数时回退默认策略。
        encoder = sail.Encoder(*args, 1)
    except TypeError:
        encoder = sail.Encoder(*args)
    if not encoder.is_opened():
        try:
            encoder.release()
        except Exception:
            pass
        raise RuntimeError('SAIL Encoder 打开失败: %s' % push_target)
    logger.info('[SAIL Encoder] %s %s %dx%d fps=%d bitrate=%dkbps gop=%d cache=%d',
                enc_fmt, pix_fmt, push_w, push_h, fps, bitrate, gop, cache_length)
    return encoder


def _finish_native_call(action, tag, timeout=10.0, check_result=False):
    '''原生释放失败/卡住时不再销毁依赖对象；结束进程，交由调度器恢复。'''
    done = threading.Event()
    errors = []

    def release():
        try:
            result = action()
            if check_result and result != 0:
                raise RuntimeError('%s 返回错误码 %s' % (tag, result))
        except BaseException as exc:
            errors.append(exc)
            logger.exception('[%s] 清理异常', tag)
        finally:
            done.set()

    threading.Thread(target=release, daemon=True, name='media-release').start()
    if not done.wait(timeout) or errors:
        logger.error('[%s] 清理失败或超过 %.1fs；保留在用对象并退出进程，等待调度器重启',
                     tag, timeout)
        os._exit(3)


def _release_media(obj, tag):
    '''确认释放完成后才能回收该对象的依赖内存。'''
    if obj is None:
        return
    _finish_native_call(obj.release, tag)


# ======================================================================
# 4. 共享状态与解码帧投递
# ======================================================================
class SharedState:
    '''SAIL 解码主循环与推理/推流 worker 线程之间的共享状态。'''
    def __init__(self):
        self.frame_queue = queue.Queue(maxsize=4)
        self.sample_intervals = ()
        self.last_results = []          # 每模型最近一次推理结果（非推理帧复用以保持画面连续）
        self.result_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.encoder = None
        self.encoder_bmcv = None
        self.encoder_keepalive = None  # push 退出后仍存活，直到 Encoder.release 成功
        self.media_handle = None
        self.media_error = None
        self.frame_count = 0
        self.archive_epoch = object()
        self.archive_native_drops = 0
        self.pre_evictions = 0
        self.pre_sample_drops = 0
        self.infer_evictions = 0
        self.archive_source_fps = 0.0
        self.stage_threads = []         # worker_loop 启动的阶段线程，run() 停机时统一 join

    def decoded_sample(self, frame):
        return not self.sample_intervals or any(frame[1] % n == 0 for n in self.sample_intervals)


def _run_stage(state, name, target, args=(), launcher=False):
    '''阶段异常必须通知主循环，避免线程已死但进程仍活着且永远没有输出。'''
    try:
        target(*args)
        if not launcher and not state.stop_event.is_set():
            raise RuntimeError('阶段线程意外提前结束')
    except Exception as exc:
        logger.exception('[%s] 阶段异常，停止本次流会话', name)
        state.media_error = '%s 阶段异常: %s' % (name, exc)
        state.stop_event.set()


def _close_session(state, worker, decoder, encoder, use_md, md_channel):
    '''先停止所有使用方，再释放媒体对象，最后解除图像保活。'''
    state.stop_event.set()
    try:
        while True:
            state.frame_queue.get_nowait()
    except queue.Empty:
        pass
    if worker is not None:
        worker.join(timeout=6)
    deadline = time.monotonic() + 8.0
    for t in state.stage_threads:
        # worker 启动中异常时，列表可能包含尚未 start 的线程。
        if t.ident is not None:
            t.join(timeout=max(0.0, deadline - time.monotonic()))
    stale = [t.name for t in state.stage_threads if t.is_alive()]
    if worker is not None and worker.is_alive():
        stale.append(worker.name)
    if stale:
        logger.error('[run] 阶段线程未在超时内退出: %s；立即退出进程，等待调度器重启', stale)
        # 不能返回 run 的外层 finally：线程可能仍在 infer_raw/video_write 中。
        os._exit(3)
    if use_md and decoder is not None:
        if md_channel is not None and md_channel >= 0:
            _finish_native_call(lambda: decoder.del_channel(md_channel),
                                'SAIL MultiDecoder', check_result=True)
    else:
        _release_media(decoder, 'SAIL Decoder')
    _release_media(encoder, 'SAIL Encoder')
    state.encoder = None
    state.encoder_bmcv = None
    if state.encoder_keepalive is not None:
        state.encoder_keepalive.clear()
    state.encoder_keepalive = None
    state.media_handle = None


def _put_latest(q, item):
    '''Append in order and evict only the oldest item if the bounded queue is full.'''
    try:
        q.put_nowait(item)
        return False
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass
        return True


def _put_sample_first(q, item, is_sample, wait_for_sample=False):
    """Return the dropped frame's kind, or None. Retained frames stay in FIFO order."""
    with q.not_full:
        dropped = None
        if len(q.queue) >= q.maxsize:
            display_index = next((i for i, old in enumerate(q.queue) if not is_sample(old)), None)
            if display_index is not None:
                del q.queue[display_index]
                dropped = 'display'
            elif not is_sample(item):
                return 'display'
            elif wait_for_sample:
                raise queue.Full
            else:
                # The decoder must keep draining the camera. All slots contain samples.
                q.queue.popleft()
                dropped = 'sample'
            q.unfinished_tasks -= 1
        q.queue.append(item)
        q.unfinished_tasks += 1
        q.not_empty.notify()
        return dropped


def _offer_decoded_frame(state, cfg, image_packed):
    '''把解码线程转好的 BGR_PACKED 帧投给推理队列（满则丢旧）。
    丢帧只允许发生在这里（整帧粒度、无害）；绝不能靠解码线程变慢来限流，
    否则 TCP 背压会让流媒体服务端丢 RTP 包导致花屏。借帧回调(frame_tap)
    需要 numpy 帧，已随 CPU 转换一起移到 [pre] 线程。'''
    state.frame_count += 1
    archive_no = state.frame_count + state.archive_native_drops
    dropped = _put_sample_first(state.frame_queue, (image_packed, state.frame_count, archive_no, time.monotonic()),
                                state.decoded_sample)
    if dropped:
        state.pre_evictions += 1
        if dropped == 'sample':
            state.pre_sample_drops += 1

# ----------------------------------------------------------------------
# 多模型 TPU 实例创建（BM1684X 单颗 TPU，无需分核）
# ----------------------------------------------------------------------
def build_model_runtimes(model_cfgs, dev_id=None):
    '''为每个模型加载 bmodel（sail.Engine SYSIO）。BM1684X 单颗 TPU：各模型独占一个
    Engine 实例并行提交，TPU 上的实际执行由 bmruntime 串行调度，无需手工分核。
    在原 model_spec 上追加 'net'（YOLOv8Model 实例）并返回；img_size 以 bmodel 实际输入为准。'''
    n = len(model_cfgs)
    if n == 0:
        raise ValueError('cfg["models"] 不能为空')

    runtimes = []
    for i, mc in enumerate(model_cfgs):
        path = mc.get('bmodel_path') or mc.get('rknn_path') or mc.get('algorithm_path')
        if not path:
            raise ValueError('第 %d 个模型缺少 bmodel_path/algorithm_path' % i)
        try:
            net = y8.YOLOv8Model(path, dev_id=dev_id)
        except Exception:
            for it in runtimes:
                try:
                    it['net'].release()
                except Exception:
                    pass
            raise
        item = dict(mc)
        item['net'] = net
        if int(item.get('img_size') or 0) != net.net_w:
            logger.info('[模型 %d] img_size 配置=%s 与 bmodel 输入=%d 不一致，以 bmodel 为准',
                        i, item.get('img_size'), net.net_w)
        item['img_size'] = net.net_w
        runtimes.append(item)
        logger.info('[模型 %d] %s 类别名(画框用)=%s 输入=%dx%d dev=%d 加载成功',
                    i, mc.get('name', path), mc.get('names'), net.net_w, net.net_h, net.dev_id)

    all_labels, all_prefixes = [], []
    for mc in model_cfgs:
        for nm in (mc.get('names') or []):
            if nm:
                all_labels.append(str(nm))
        p = mc.get('label_prefix', '')
        if p:
            all_prefixes.append(str(p))
    register_label_colors(all_labels, all_prefixes)
    return runtimes


def _consecutive_sample(previous, seq, arrival, interval, source_fps):
    if previous is None:
        return False
    last_seq, last_arrival = previous
    max_gap = max(0.5, 2.5 * interval / max(0.1, source_fps))
    return seq - last_seq == interval and 0 < arrival - last_arrival <= max_gap


def worker_loop(state, cfg, models):
    '''多模型并行推理 worker（流水线 + 同帧扇出 + barrier 聚合 + 各任务后处理分发）：

      [pre]        ──1 线程──→ BMImage→numpy+旋转/缩放+借帧 → 预处理(按 img_size 去重，仅一次 letterbox/cvt)，扇出到 N 个模型队列
      [inf_post_i] ──N 线程──→ 各模型独占 bmodel 引擎，推理 + 后处理 + 类别/区域过滤
      [aggregator] ──1 线程──→ barrier 等齐同一 seq 的 N 个结果 → 逐模型调 on_result → 合并画框
      [push]       ──1 线程──→ BGR 转 BMImage + sail.Encoder.video_write

    models 形如 [{'net':YOLOv8Model, 'img_size':640, 'obj_thresh':.., 'nms_thresh':..,
                  'names':[..], 'category_id':[..],
                  'label_prefix':'[A]'(可选), 'regions_np':[..](可选),
                  'extract_count':N(可选，该模型推理间隔：每 N 个解码帧推理一次),
                  'on_result':callable|None, 'draw_det_boxes':True}, ...]
    '''
    n = len(models)
    stop = state.stop_event
    font_path = cfg.get('font_path', 'fonts/wqy-microhei.ttc')
    push_enabled = bool(cfg.get('push_url'))
    task_health = WorkerHealth(cfg.get('platform_generation'), models, push_required=push_enabled)

    if not state.last_results or len(state.last_results) != n:
        state.last_results = [[] for _ in range(n)]

    inf_qs = [queue.Queue(maxsize=4) for _ in range(n)]
    agg_in_q = queue.Queue(maxsize=max(4, 2 * n))
    push_q = queue.Queue(maxsize=1)

    # 各模型独立推理间隔（单位：解码帧）：优先取 model_spec 自带的 extract_count，
    # 缺省回退流级 extract_count——计数任务隔帧跑、检测任务按 sensitivity 跑，互不拖累。
    intervals = tuple(max(1, int(m.get('extract_count') or cfg.get('extract_count') or 1))
                      for m in models)
    state.sample_intervals = intervals
    logger.info('[worker] 各模型推理间隔(解码帧)=%s', intervals)

    def _put_wait(q, item):
        '''阻塞入队(FIFO 不丢帧)，仅在收到停止信号时放弃。
        用于：① 多模型扇出——让各模型严格按同一 seq 顺序推理，保证聚合 barrier 每帧都能对齐；
              ② 推理→聚合投递——聚合线程慢时以背压回压上游(前端 frame_queue 丢旧)，而不是丢弃
                 单个模型的结果导致该 seq 永远凑不齐、on_result 被整帧跳过。'''
        while not stop.is_set():
            try:
                q.put(item, timeout=0.5)
                return True
            except queue.Full:
                continue
        return False

    # ---- 阶段 1：BMImage→numpy + 旋转/缩放 + 借帧 + 预处理（按 img_size 去重）+ 扇出 ----
    def pre_stage():
        '''阶段1线程：从 frame_queue 取最新 BGR_PACKED BMImage → numpy 拷贝 + 旋转/缩放 +
        借帧回调（这些 CPU 重活从解码线程移来，保证解码恒跟上流速）→ 按各模型 extract_count
        独立判定本帧哪些模型要推理 → 只对「本帧确有模型要推理」的 img_size 做一次预处理 →
        带 seq 与各自推理标志扇出到各模型队列。'''
        size_groups = {}
        for i, m in enumerate(models):
            size_groups.setdefault(int(m['img_size']), []).append(i)
        worker_bmcv = sail.Bmcv(state.media_handle) if state.media_handle is not None else None
        rotation = int(cfg.get('rotation', 0) or 0)
        dec_w, dec_h = cfg.get('_decode_size') or (0, 0)
        tap = cfg.get('frame_tap')
        size_tap = cfg.get('raw_size_tap')      # 视频质量监测：解码原始尺寸（缩放前）
        last_raw_size = None
        while not stop.is_set():
            try:
                image_packed, frame_no, archive_no, arrival = state.frame_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            t_in = time.time()
            try:
                image_bgr = _packed_to_numpy(image_packed, worker_bmcv)
            except Exception:
                logger.exception('[pre] BMImage 转 numpy 失败，跳过该帧')
                continue
            finally:
                image_packed = None     # 尽早释放 BGR_PACKED 的设备内存
            # 分辨率异常检测需要缩放前的真实流分辨率（tap 帧已被统一缩放到配置尺寸），
            # 仅在尺寸变化时上报一次，热路径开销为两个整数比较
            if size_tap is not None:
                rh, rw = image_bgr.shape[:2]
                if (rw, rh) != last_raw_size:
                    last_raw_size = (rw, rh)
                    try:
                        size_tap(rw, rh)
                    except Exception:
                        pass
            native = _rotate_decoded_frame(image_bgr, rotation)
            image_bgr = _analysis_frame(native, dec_w or native.shape[1], dec_h or native.shape[0])
            h, w = image_bgr.shape[:2]
            if tap is not None:
                try:
                    tap(image_bgr)
                except Exception:
                    pass
            tp0 = time.time()
            # 按模型独立节奏：frame_no 是解码帧号，各模型只在自己的间隔帧上推理
            infer_flags = [frame_no % intervals[mi] == 0 for mi in range(n)]
            preps = {}
            for size, idxs in size_groups.items():
                if any(infer_flags[mi] for mi in idxs):
                    preps[size] = preprocess_for_yolo(image_bgr, size)
            pre_ms = (time.time() - tp0) * 1000
            for size, idxs in size_groups.items():
                for mi in idxs:
                    m_infer = infer_flags[mi]
                    item = (archive_no, image_bgr, m_infer, w, h,
                            preps.get(size) if m_infer else None, pre_ms, t_in, native, arrival)
                    if n == 1:
                        try:
                            if _put_sample_first(inf_qs[mi], item, lambda frame: frame[2], wait_for_sample=True):
                                state.infer_evictions += 1
                        except queue.Full:
                            if not _put_wait(inf_qs[mi], item):
                                return
                    else:
                        # 多模型：阻塞入队(不丢帧)，各模型锁步在同一 seq 上，聚合每帧对齐、按序分发
                        if not _put_wait(inf_qs[mi], item):
                            return

    # ---- 阶段 2：模型推理 + 后处理 ----
    def inf_post_stage(mi):
        '''
        阶段2线程（每模型一个）：独占第 mi 个 bmodel 引擎，推理 + YOLOv8 后处理 + 类别/区域过滤，结果投给聚合队列。
        mi: 模型索引，0..n-1。
        '''
        m = models[mi]
        net = m['net']
        obj_th = float(m['obj_thresh'])
        nms_th = float(m['nms_thresh'])
        cat = set(int(c) for c in (m.get('category_id') or []))  # 空=不过滤
        regions_np = m.get('regions_np') or []
        has_regions = bool(regions_np)
        line_search = m.get('full_body_line_search')

        def infer_region(region):
            size = region.shape[0]
            crop_blob, ratio, padding = y8.preprocess(region, net.net_w, net.net_h)
            predicted = net.infer_raw(crop_blob)
            boxes, classes, scores = y8.postprocess(predicted, size, size, ratio, padding, obj_th, nms_th)
            if boxes is None:
                return []
            return [[int(label), float(score), list(map(int, box))]
                    for box, label, score in zip(boxes, classes, scores)
                    if score >= obj_th and (not cat or int(label) in cat)]

        while not stop.is_set():
            try:
                seq, image_bgr, need_infer, w, h, inp, pre_ms, t_in, native, arrival = inf_qs[mi].get(timeout=1.0)
            except queue.Empty:
                continue
            inf_ms = 0.0
            post_ms = 0.0
            results = []
            processed = False
            if need_infer and inp is not None:
                blob, ratio, txy = inp
                ti0 = time.time()
                try:
                    pred = net.infer_raw(blob)
                except Exception:
                    logger.exception('推理异常 (model=%d)', mi)
                    pred = None
                inf_ms = (time.time() - ti0) * 1000
                if pred is not None:
                    tpp0 = time.time()
                    try:
                        if m.get('pose'):
                            # SITE_PATCH_CROSSING_POSE_V1: YOLOv8-pose keypoints
                            boxes, classes, scores, keypoints = y8.postprocess_pose(
                                pred, w, h, ratio, txy, obj_th, nms_th,
                                kpt_num=int(m.get('kpt_num', 17)))
                        else:
                            boxes, classes, scores = y8.postprocess(
                                pred, w, h, ratio, txy, obj_th, nms_th)
                            keypoints = None
                        if boxes is not None:
                            for bi, (box, score, cl) in enumerate(zip(boxes, scores, classes)):
                                if score < obj_th:
                                    continue
                                cl_int = int(cl)
                                if cat and cl_int not in cat:
                                    continue
                                xmin, ymin, xmax, ymax = box
                                if has_regions and not _box_in_polygons(
                                        (xmin, ymin, xmax, ymax), regions_np):
                                    continue
                                if keypoints is not None:
                                    results.append([cl_int, '%.2f' % score,
                                                    [int(xmin), int(ymin), int(xmax), int(ymax)],
                                                    keypoints[bi].tolist()])
                                else:
                                    results.append([cl_int, '%.2f' % score,
                                                    [int(xmin), int(ymin), int(xmax), int(ymax)]])
                        processed = True
                    except Exception:
                        logger.exception('后处理异常 (model=%d)', mi)
                    if processed and line_search is not None:
                        try:
                            observed = line_search.detect(image_bgr, results, arrival, infer_region)
                            results = [row for row in observed if not has_regions or _box_in_polygons(row[2], regions_np)]
                        except Exception:
                            logger.exception('全身计数线局部检测异常 (model=%d)', mi)
                    post_ms = (time.time() - tpp0) * 1000
            # 背压式投递：聚合慢时回压(前端丢旧帧)，绝不丢弃单模型结果——否则该 seq 永远凑不齐，
            # barrier 会把这一整推理帧的 on_result 跳过（多模型报警丢失的根因）。
            _put_wait(agg_in_q, (mi, seq, image_bgr, need_infer, w, h, results,
                                 pre_ms, inf_ms, post_ms, t_in, processed, native, arrival))

    # ---- 阶段 3：barrier 聚合 + 各任务后处理分发 + 合并画框 ----
    # slot[mi] 统一存 9 元组：(image_bgr, m_infer, w, h, results, pre_ms, inf_ms, post_ms, t_in)
    # 其中 m_infer 为【该模型】本帧是否推理（各模型 extract_count 独立，可不相同）
    last_archive_seq = None
    # A new worker starts a fresh decoder session; inference intervals differ by model.
    previous_sample = [None] * n
    source_fps = state.archive_source_fps or float(cfg.get('fps') or 25)
    next_gap_log = 0.0

    def _process_seq(seq, slot):
        '''
        处理已凑齐 N 个模型结果的一帧：逐模型（仅各自推理帧）调 on_result → on_draw 叠加 → 合并画框 → 投推流队列。
        seq: 帧号；slot: {mi:(image_bgr, m_infer, w, h, results, pre_ms, inf_ms, post_ms, t_in), ...}
        '''
        nonlocal last_archive_seq, next_gap_log
        if last_archive_seq is not None and seq > last_archive_seq + 1 and time.monotonic() >= next_gap_log:
            logger.warning("Archive sequence gap=%d native_drops=%d pre_evictions=%d pre_sample_drops=%d infer_evictions=%d",
                           seq-last_archive_seq-1, state.archive_native_drops, state.pre_evictions,
                           state.pre_sample_drops, state.infer_evictions)
            next_gap_log = time.monotonic() + 10
        last_archive_seq = seq
        any_item = next(iter(slot.values()))
        image_bgr, w, h = any_item[0], any_item[2], any_item[3]
        pre_ms = any_item[5]
        t_in = any_item[8]
        archive_timestamp = alarm_video.frame_timestamp(t_in, seq, state.archive_source_fps, state.archive_epoch)
        any_infer = False            # 本帧是否有模型真正推理（耗时统计用）
        inf_ms_max = 0.0
        post_ms_sum = 0.0
        for it in slot.values():
            any_infer = any_infer or bool(it[1])
            inf_ms_max = max(inf_ms_max, it[6])
            post_ms_sum += it[7]

        td0 = time.time()
        # ① 逐模型：仅在该模型自己的推理帧上更新缓存结果 + 调后处理回调；
        #    非推理帧复用 last_results（画框推流连续），on_result 不重复触发
        for mi in range(n):
            it = slot.get(mi)
            if it is None or not it[1]:
                continue
            res = it[4]
            state.last_results[mi] = res
            cb = models[mi].get('on_result')
            if cb is not None:
                try:
                    if models[mi].get('result_frame_continuity'):
                        arrival = it[11]
                        contiguous = it[9] and _consecutive_sample(
                            previous_sample[mi], seq, arrival, intervals[mi], source_fps)
                        previous_sample[mi] = None
                        cb(image_bgr, res if it[9] else [], w, h, frame_timestamp=archive_timestamp,
                           frame_continuous=contiguous)
                        if it[9]:
                            previous_sample[mi] = seq, arrival
                    elif models[mi].get('result_frame_timestamp'):
                        cb(image_bgr, res, w, h, frame_timestamp=archive_timestamp)
                    else:
                        cb(image_bgr, res, w, h)
                except Exception:
                    logger.exception('on_result 回调异常 (model=%d)', mi)
                    continue
            if it[9]:
                task_health.processed(mi, t_in)
        # ② 合并各模型检测框，一次画框（叠在各任务覆盖层之上）
        # ①.5 逐模型常显叠加（如报警区域），每帧都画（含跳帧），叠在检测框之下
        for mi in range(n):
            od = models[mi].get('on_draw')
            if od is not None:
                try:
                    od(image_bgr, w, h)
                except Exception:
                    logger.exception('on_draw 回调异常 (model=%d)', mi)
        merged = []
        for mi in range(n):
            m = models[mi]
            if not m.get('draw_det_boxes', True):
                continue
            res = state.last_results[mi]
            if res:
                merged.extend(results_to_named(res, m.get('names') or [],
                                               m.get('label_prefix', '')))
        if merged:
            try:
                draw_boxes(image_bgr, merged, w, h, font_path)
            except Exception:
                logger.exception('合并画框异常（推原始帧继续）')
        if not image_bgr.flags['C_CONTIGUOUS']:
            image_bgr = np.ascontiguousarray(image_bgr)
        if push_enabled:
            draw_ms = (time.time() - td0) * 1000
            _put_latest(push_q, (seq, image_bgr, any_infer, pre_ms, inf_ms_max,
                                 post_ms_sum, draw_ms, t_in))
        # Capture the selected stream before preview resizing. The recorder applies only
        # pixels changed by the overlays, leaving native scene detail intact.
        alarm_video.feed(image_bgr, native=any_item[10], timestamp=archive_timestamp)

    def aggregator():
        '''阶段3线程：barrier 聚合——按 seq 收集 N 个模型的结果，凑齐才处理该帧；积压超限时丢弃最老的残缺帧。'''
        pending = {}
        while not stop.is_set():
            try:
                mi, seq, image_bgr, need_infer, w, h, results, pre_ms, inf_ms, post_ms, t_in, processed, native, arrival = \
                    agg_in_q.get(timeout=1.0)
            except queue.Empty:
                continue
            slot = pending.setdefault(seq, {})
            slot[mi] = (image_bgr, need_infer, w, h, results, pre_ms, inf_ms, post_ms, t_in, processed, native, arrival)
            if len(slot) == n:
                _process_seq(seq, slot)
                pending.pop(seq, None)
            if len(pending) > 8:
                for s in sorted(pending.keys())[: len(pending) - 8]:
                    pending.pop(s, None)

    # ---- 阶段 4：BGR → BMImage + SAIL 硬编码推流 + 耗时统计 ----
    def push_stage():
        '''阶段4线程：帧转 BMImage → sail.Encoder.video_write，并按秒汇总各阶段耗时。'''
        stats = {'start': time.time(), 'frames': 0, 'infer_frames': 0,
                 'pre_sum': 0.0, 'inf_sum': 0.0, 'post_sum': 0.0, 'draw_sum': 0.0,
                 'cvt_sum': 0.0, 'push_sum': 0.0, 'e2e_sum': 0.0, 'e2e_max': 0.0, 'seq': -1}
        queue_full_count = 0
        encoder_pix_fmt = str(cfg.get('encoder_pix_fmt', 'I420') or 'I420').upper()
        upload_mode = os.environ.get('SAIL_IMAGE_UPLOAD') or cfg.get('image_upload', 'tensor')
        if str(upload_mode).lower() not in ('tensor', 'mat'):
            raise ValueError('SAIL_IMAGE_UPLOAD/image_upload 仅支持 tensor/mat')
        logger.info('[push] 图像上传路径=%s，等待首帧提交编码器', upload_mode)
        first_submitted = False
        # 此有界队列是额外保活，并非编码消费完成协议；停止时由 state 保留至 release 返回。
        cache_length = max(1, int(cfg.get('encoder_cache', 10) or 10))
        keepalive = deque(maxlen=max(16, cache_length * 3 + 8))
        state.encoder_keepalive = keepalive

        # 可选诊断：设置 cfg['debug_preencode_path'] 或环境变量 RTSP_DEBUG_PREENCODE，
        # 定时覆盖保存编码前 BGR 帧。该图正常而 RTSP 花屏时，问题就在 Encoder/RTP/播放器链路。
        debug_path = cfg.get('debug_preencode_path') or os.environ.get('RTSP_DEBUG_PREENCODE')
        debug_interval = max(1.0, float(cfg.get('debug_preencode_interval', 5.0) or 5.0))
        last_debug = 0.0
        if debug_path:
            debug_path = os.path.abspath(str(debug_path))
            if os.path.splitext(debug_path)[1].lower() not in ('.jpg', '.jpeg', '.png'):
                os.makedirs(debug_path, exist_ok=True)
                debug_path = os.path.join(
                    debug_path, 'preencode_%s.jpg' % _stream_tag(cfg))
            else:
                parent = os.path.dirname(debug_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
            logger.warning('[诊断] 已启用编码前截图（每 %.1fs 覆盖）：%s',
                           debug_interval, debug_path)

        def _print_stats(force=False):
            '''每 ≥1 秒输出一次各阶段平均耗时，随后清零窗口。'''
            now = time.time()
            elapsed = now - stats['start']
            if not force and elapsed < 1.0:
                return
            frames = stats['frames']
            if frames <= 0:
                stats['start'] = now
                return
            inf_f = max(1, stats['infer_frames'])
            logger.debug('耗时汇总[%.1fs seq=%d frames=%d infer=%d]: pre=%.1f inf=%.1f post=%.1f '
                         'draw=%.1f bmimage=%.1f push=%.1f e2e_avg=%.1f e2e_max=%.1f',
                         elapsed, stats['seq'], frames, stats['infer_frames'],
                         stats['pre_sum'] / inf_f, stats['inf_sum'] / inf_f, stats['post_sum'] / inf_f,
                         stats['draw_sum'] / frames, stats['cvt_sum'] / frames,
                         stats['push_sum'] / frames, stats['e2e_sum'] / frames, stats['e2e_max'])
            stats.update({'start': now, 'frames': 0, 'infer_frames': 0, 'pre_sum': 0.0,
                          'inf_sum': 0.0, 'post_sum': 0.0, 'draw_sum': 0.0, 'cvt_sum': 0.0,
                          'push_sum': 0.0, 'e2e_sum': 0.0, 'e2e_max': 0.0})

        # 恒速起搏写入：SAIL Encoder 按 enc_params 的 framerate 内部起搏，实测喂帧速率
        # 明显低于 framerate 时（推理管道慢，如 ~4fps），其 RTMP/RTSP 复用器会在数十秒
        # 内饥饿失败（video_write 返回 -3，隔离复现：25fps 恒速喂 90s 稳定，~3fps 喂
        # ~40s 必挂）。因此无论上游多慢，这里都按 fps 节拍写入：有新帧写新帧，没有就
        # 重复写上一帧。输出流因此帧率恒定、时间戳规整。
        fps = max(1, int(cfg.get('fps', 25) or 25))
        tick = 1.0 / fps
        # Retain short scheduler variations between the inference and encoder clocks.
        pending = deque(maxlen=3)
        fresh_frames = repeated_frames = repeat_run = longest_repeat = 0
        period_start = time.monotonic()
        last_frame = None         # 最近一次写入的 (bm_image, backing)，无新帧时按节拍重复
        repeat_writes = 0
        next_due = time.monotonic() + tick
        while not stop.is_set():
            wait = next_due - time.monotonic()
            item = None
            try:
                if wait > 0:
                    item = push_q.get(timeout=wait)
                else:
                    item = push_q.get_nowait()
            except queue.Empty:
                pass
            if item is not None:
                seq, image_bgr, need_infer, pre_ms, inf_ms, post_ms, draw_ms, t_in = item
                try:
                    tc0 = time.time()
                    psize = cfg.get('_push_size')
                    if psize and (image_bgr.shape[1], image_bgr.shape[0]) != psize:
                        image_bgr = cv2.resize(image_bgr, psize, interpolation=cv2.INTER_AREA)
                    image_bgr = np.ascontiguousarray(image_bgr, dtype=np.uint8)
                    if debug_path and time.monotonic() - last_debug >= debug_interval:
                        if cv2.imwrite(debug_path, image_bgr):
                            last_debug = time.monotonic()
                        else:
                            logger.error('[诊断] 编码前截图写入失败，停止截图：%s', debug_path)
                            debug_path = None
                    if state.encoder_bmcv is None or state.encoder is None:
                        raise RuntimeError('SAIL Encoder 尚未初始化')
                    bm_image, backing = _bgr_to_bmimage(
                        image_bgr, state.media_handle, state.encoder_bmcv,
                        encoder_pix_fmt, upload_mode)
                    cvt_ms = (time.time() - tc0) * 1000
                    pending.append((bm_image, backing,
                                    (seq, need_infer, pre_ms, inf_ms, post_ms, draw_ms, t_in, cvt_ms)))
                except Exception as exc:
                    logger.exception('SAIL 硬编码推流异常')
                    state.media_error = 'SAIL 硬编码推流异常: %s' % exc
                    stop.set()
                    break
            if time.monotonic() < next_due:
                continue
            # 到达节拍：优先写 pending 的新帧，没有则重复上一帧维持恒定帧率
            if pending:
                bm_image, backing, meta = pending.popleft()
            elif last_frame is not None:
                bm_image, backing = last_frame
                meta = None
            else:
                next_due = time.monotonic() + tick   # 尚无任何帧可写
                _print_stats(force=True)
                continue
            push_ms = 0.0
            ret = None
            try:
                tp0 = time.time()
                # 调用失败也保留本帧至 release，不能假设原生层完全未接收。
                keepalive.append((bm_image, backing))
                ret = state.encoder.video_write(bm_image)
                push_ms = (time.time() - tp0) * 1000
                if ret in (0, None):
                    last_frame = (bm_image, backing)
                    if not first_submitted:
                        logger.info('[SAIL Encoder] 首帧已提交编码器队列；远端播放仍需验证')
                        first_submitted = True
                    if meta is None:
                        repeat_writes += 1
                        if repeat_writes % (fps * 60) == 0:
                            logger.debug('[push] 上游慢于推流帧率，已按节拍重复补帧 %d 次', repeat_writes)
                if ret == -1:
                    queue_full_count += 1
                    if queue_full_count == 1 or queue_full_count % 100 == 0:
                        logger.warning('[SAIL Encoder] 内部队列已满，丢弃当前帧（累计 %d）', queue_full_count)
                elif ret not in (0, None):
                    state.media_error = 'SAIL Encoder video_write 失败，返回码=%s' % ret
                    logger.error(state.media_error)
                    stop.set()
            except Exception as exc:
                logger.exception('SAIL 硬编码推流异常')
                state.media_error = 'SAIL 硬编码推流异常: %s' % exc
                stop.set()
            if meta is not None and ret in (0, None):
                seq, need_infer, pre_ms, inf_ms, post_ms, draw_ms, t_in, cvt_ms = meta
                task_health.output(t_in)
                e2e_ms = (time.time() - t_in) * 1000
                stats['seq'] = seq
                stats['frames'] += 1
                stats['draw_sum'] += draw_ms
                stats['cvt_sum'] += cvt_ms
                stats['push_sum'] += push_ms
                stats['e2e_sum'] += e2e_ms
                stats['e2e_max'] = max(stats['e2e_max'], e2e_ms)
                if need_infer:
                    stats['infer_frames'] += 1
                    stats['pre_sum'] += pre_ms
                    stats['inf_sum'] += inf_ms
                    stats['post_sum'] += post_ms
            if ret in (0, None):
                if meta is None:
                    repeated_frames += 1
                    repeat_run += 1
                    longest_repeat = max(longest_repeat, repeat_run)
                else:
                    fresh_frames += 1
                    repeat_run = 0
            measured = time.monotonic() - period_start
            if measured >= 30:
                logger.info('[push] %.1fs fresh_fps=%.2f repeats=%d longest_repeat=%d',
                            measured, fresh_frames / measured, repeated_frames, longest_repeat)
                fresh_frames = repeated_frames = 0
                longest_repeat = repeat_run
                period_start = time.monotonic()
            next_due += tick
            if next_due < time.monotonic() - 1.0:
                next_due = time.monotonic() + tick   # 长时间停滞后重新对齐节拍
            _print_stats()
    threads = [threading.Thread(target=_run_stage, args=(state, 'pre', pre_stage),
                                daemon=True, name='pre')]
    for i in range(n):
        threads.append(threading.Thread(target=_run_stage,
                                        args=(state, 'inf%d' % i, inf_post_stage, (i,)),
                                        daemon=True, name='inf%d' % i))
    threads.append(threading.Thread(target=_run_stage, args=(state, 'agg', aggregator),
                                    daemon=True, name='agg'))
    if push_enabled:
        threads.append(threading.Thread(target=_run_stage, args=(state, 'push', push_stage),
                                        daemon=True, name='push'))
    state.stage_threads = threads
    for t in threads:
        t.start()
    # 阶段线程由 run() 在停机/重连时统一 join（见 run() 的 finally 分支）。
    # 早先版本在这里等 5s 并打"子线程未在超时内退出"告警——阶段线程本来就与流会话同生命周期，
    # 该告警每次启动必现（误报），且 run() 重连时不等阶段线程退出就释放 Decoder/Encoder、
    # 复用共享推理引擎，存在"上代线程还在 video_write/infer_raw、下代已开始"的竞态。


# ======================================================================
# 7. 主流程
# ======================================================================
def _probe_pull_source(rtsp_url, timeout=2.0):
    '''裸 socket 发一次 RTSP DESCRIBE，轻量探测拉流源是否已发布。

    返回 (ready, code)：404/连接失败/超时 → 未就绪；200/401 等其余应答 → 可尝试
    （401 只说明要走 digest 等鉴权，交给 rtspsrc 处理）。单次探测毫秒级，
    比反复创建 Decoder 再等待打开失败更轻量。'''
    try:
        u = urlparse(rtsp_url)
        host, port = u.hostname, u.port or 554
        if not host:
            return True, None    # URL 异常时不拦路，让管道自己去报错
    except Exception:
        return True, None
    path = u.path or '/'
    if u.query:
        path += '?' + u.query
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            req = ('DESCRIBE rtsp://%s:%d%s RTSP/1.0\r\n'
                   'CSeq: 1\r\n'
                   'Accept: application/sdp\r\n' % (host, port, path))
            if u.username:
                token = base64.b64encode(
                    ('%s:%s' % (u.username, u.password or '')).encode('utf-8')).decode('ascii')
                req += 'Authorization: Basic %s\r\n' % token
            req += 'User-Agent: rtsp-probe\r\n\r\n'
            sock.sendall(req.encode('utf-8'))
            data = sock.recv(4096).decode('utf-8', 'replace')
    except Exception:
        return False, None
    parts = data.split('\r\n', 1)[0].split()
    if len(parts) < 2 or not parts[1].isdigit():
        return (bool(data), None)    # 空应答=未就绪；应答格式怪异则放行给管道
    code = int(parts[1])
    return code != 404, code


def _wait_pull_source_ready(rtsp_url, stop_event, exit_flag, probe_interval=1.0):
    '''以 probe_interval 间隔探测拉流源直到就绪。返回 True=就绪，False=被要求退出。
    开机竞态下拉流源（如流媒体服务上的 stream11）晚于本程序就绪，等待粒度缩到 1s，加快开机后出流。'''
    n = 0
    t0 = time.monotonic()
    while not exit_flag['requested']:
        ok, code = _probe_pull_source(rtsp_url)
        if ok:
            if n:
                logger.info('[源探测] 拉流源已就绪（等待 %.1fs，共探测 %d 次）',
                            time.monotonic() - t0, n + 1)
            return True
        n += 1
        if n == 1 or n % 30 == 0:
            logger.warning('[源探测] 拉流源未就绪（%s），%.0fs 间隔继续探测（第 %d 次）',
                           ('RTSP %d' % code) if code else '无法连接', probe_interval, n)
        if stop_event.wait(probe_interval):
            break
    return False


# 单路流默认参数（不含 models）
DEFAULT_STREAM_CFG: Dict[str, Any] = {
    'platform': 'bm1684x',
    'dev_id': y8.DEFAULT_DEV_ID,     # TPU 设备号（单卡盒子为 0，可用环境变量 TPU_DEV_ID 覆盖）
    'enc_type': 'h264',
    'img_width': 1280,
    'img_height': 720,
    'rotation': 0,
    'user_id': 'admin',
    'user_pw': os.environ.get("AIP_CAMERA_PASSWORD", ""),
    'rtsp_url': 'rtsp://127.0.0.1:8554/stream11',
    'push_url': None,            # 为空=不推流（只取流+推理+回调）
    'pull_seconds': 5,
    'rtsp_transport': 'tcp',     # TCP 避免 RTP/UDP 丢包导致 P 帧连续花屏
    'decoder_compressed': False, # 可靠性优先；True 的压缩 NV12 面在部分 SDK/码流上会花屏
    'decoder_buffer_size': 2097152,
    'decoder_extra_frame_buffer_num': 5, # 官方建议5；旧版RTSP默认20可能超过VPU单实例32帧上限
    'use_multidecoder': True,    # True: MultiDecoder（C++ 内部线程取流，Python 读帧不持 GIL，
                                 # 实测 GIL 可用率 97% vs sail.Decoder 的 7%）；False 回退旧 Decoder
    'multidecoder_queue': 40,     # MultiDecoder 内部帧队列长度（满时丢旧，慢消费安全）
    'debug_decode_dir': None,    # Decoder 原始帧诊断落盘目录（每秒1张≈21GB/天，勿常开）；
                                 # 排查花屏时设 RTSP_DEBUG_DECODE_DIR=debug_decoded 临时开启
    'debug_decode_interval': 1.0,         # 原始解码帧保存间隔（秒）
    'extract_count': 1,          # 流级缺省推理间隔；model_spec 自带 extract_count 时按模型独立节奏
    'fps': 25,
    'bitrate': 2500,           # SAIL Encoder 目标码率(kbps)
    'gop': 25,                 # 短 GOP：异常时最多约 1 秒恢复
    'encoder_cache': 10,       # Encoder 内部异步缓存队列长度
    'encoder_pix_fmt': 'I420', # 官方推荐格式；如板端验证需要可改回 NV12
    'image_upload': 'tensor',  # 显式设备 Tensor 上传；SAIL_IMAGE_UPLOAD=mat 可兼容对比
    'push_transport': 'rtmp',  # RTSP push_url 自动重写为 rtmp://host:1935/同路径
    'rtmp_port': 1935,         # 流媒体服务 RTMP 端口（mediamtx 默认 1935）
    'debug_preencode_path': None,     # 诊断花屏：非空时定时覆盖保存编码前图像
    'debug_preencode_interval': 5.0, # 编码前诊断截图间隔（秒）
    'font_path': 'fonts/wqy-microhei.ttc',
}

# 旧 YOLOv5(RKNN) 遗留参数：YOLOv8 bmodel 为 anchor-free 单输出，masks/anchors 已不参与推理，
# 仅为兼容旧模板调用签名保留（muban_PersonCount 等仍会传入，引擎直接忽略）
_DEFAULT_MASKS = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
_DEFAULT_ANCHORS = [[10, 13], [16, 30], [33, 23], [30, 61], [62, 45],
                    [59, 119], [116, 90], [156, 198], [373, 326]]


def make_model_spec(rknn_path, names, on_result=None, category_id=None, obj_thresh=0.5,
                    nms_thresh=0.45, img_size=640, masks=None, anchors=None,
                    label_prefix='', regions_np=None, draw_det_boxes=True, name=None,
                    on_draw=None, extract_count=None, **extra) -> Dict[str, Any]:
    '''构造一个模型规格（一路流下的一个任务）。rknn_path 参数名沿用旧签名，现指向 .bmodel 文件；
    masks/anchors 为 YOLOv5 遗留参数，YOLOv8 下忽略。on_result 为该任务后处理回调（见模块顶部约定）；
    on_draw(image_bgr, w, h) 为每帧常显叠加回调（如报警区域），推流时每帧都会调用（含跳帧），可为 None；
    extract_count 为该模型的推理间隔（每 N 个解码帧推理一次），None=跟随流级 extract_count。
    img_size 仅作提示：引擎加载 bmodel 后以模型实际输入尺寸为准。'''
    spec = {
        'name': name or os.path.splitext(os.path.basename(str(rknn_path)))[0],
        'rknn_path': rknn_path,
        'img_size': int(img_size),
        'obj_thresh': float(obj_thresh),
        'nms_thresh': float(nms_thresh),
        'names': list(names or []),
        'category_id': list(category_id or []),
        'label_prefix': label_prefix or '',
        'regions_np': regions_np or [],
        'on_result': on_result,
        'on_draw': on_draw,
        'draw_det_boxes': bool(draw_det_boxes),
        # 该模型的推理间隔（解码帧数）；None 时引擎回退流级 extract_count
        'extract_count': max(1, int(extract_count)) if extract_count else None,
    }
    spec.update(extra)  # 支持额外自定义字段，供 on_result 回调使用
    return spec


def build_stream_cfg(models, **overrides) -> Dict[str, Any]:
    '''基于默认流参数生成 cfg；models 为该路流下挂的模型规格列表（一个或多个任务）。'''
    cfg = copy.deepcopy(DEFAULT_STREAM_CFG)
    cfg['models'] = models if isinstance(models, list) else [models]
    cfg.update({k: v for k, v in overrides.items() if v is not None})   # None 不覆盖
    return cfg


def assemble_stream_cfg(entries, **overrides) -> Dict[str, Any]:
    '''把同一路流（同 rtsp_url）的多个任务条目（各模板 build_spec 的返回）组装成一份多模型 cfg。

    entries: [{'spec':model_spec, 'rtsp_url':.., 'enc_type':.., 'extract_count':..,
               'fps':..(可选), 'push_url':..(可选)}, ...]
    约定：
      - 流级参数取第一个 entry 的提示（同一路流应一致）；
      - 流级 extract_count 取所有任务的最小值（仅作缺省回退/日志展示）；实际推理节奏
        由各 model_spec 自带的 extract_count 在引擎内按模型独立判定，互不拖累；
      - push_url 取首个非空者（一路流只推一条带全部任务叠加的画面）。
    '''
    if not entries:
        raise ValueError('entries 为空')
    first = entries[0]
    models = [e['spec'] for e in entries]
    extract_counts = [int(e.get('extract_count', 1) or 1) for e in entries]
    push_url = overrides.get('push_url')
    if not push_url:
        for e in entries:
            if e.get('push_url'):
                push_url = e['push_url']
                break
    cfg = build_stream_cfg(
        models,
        rtsp_url=first.get('rtsp_url'),
        enc_type=first.get('enc_type', 'h264'),
        extract_count=max(1, min(extract_counts)),
        fps=first.get('fps', 25),
        push_url=push_url,
    )
    for k, v in overrides.items():
        if v is not None:
            cfg[k] = v
    return cfg


def _opencv_worker_threads(environment):
    # Preserve the explicit per-worker override; container_runtime sets CV2_NUM_THREADS.
    configured = environment.get('OPENCV_FOR_THREADS_NUM') or environment.get('CV2_NUM_THREADS')
    try:
        return max(1, int(configured or '1'))
    except (ValueError, TypeError):
        return 1


def _decoder_idle_delay(empty_for):
    # Keep the 5 ms polling interval until the FIFO has stayed empty for 250 ms.
    if empty_for < 0.25:
        return 0.005
    return min(0.020, 0.004 + empty_for * 0.004)


def run(cfg):
    '''主流程：加载多模型 → SAIL Decoder 硬解拉流 → 推理/绘制 → SAIL Encoder 硬编推流。

    cfg['models']: 模型规格列表（每个含自己的 on_result）；其余为流级参数，见 DEFAULT_STREAM_CFG。
    解码或编码异常时释放当前 Decoder/Encoder，随后进入外层重连循环。
    '''
    if not cfg.get('models'):
        raise ValueError('cfg 缺少 models')

    _setup_logging(cfg)
    # Each camera worker owns an OpenCV pool. Keep CPU headroom for sibling cameras.
    cv2.setNumThreads(_opencv_worker_threads(os.environ))
    logger.info("OpenCV worker threads=%d", cv2.getNumThreads())
    # native_hik_stream integration
    from comm.algorithm_platform_source import HikCaptureSource
    from comm.recorder_recovery import open_camera_decoder
    hik_capture = HikCaptureSource(cfg.get('rtsp_url'))
    recorder_channel = cfg.get('recorder_channel')
    next_camera_url = None
    next_mapping_check = 0.0
    cfg['_hik_dynamic_source'] = hik_capture.reference is not None
    if cfg['_hik_dynamic_source']:
        os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
    logger.info('=' * 50)
    logger.info('启动引擎 拉流=%s 推流=%s 编码=%s 尺寸=%dx%d fps=%s 跳帧=%s',
                cfg.get('rtsp_url'), cfg.get('push_url') or '(不推流)', cfg.get('enc_type'),
                cfg.get('img_width'), cfg.get('img_height'), cfg.get('fps'),
                cfg.get('extract_count'))
    logger.info('挂载模型(%d个): %s 各模型推理间隔=%s', len(cfg['models']),
                [m.get('name') for m in cfg['models']],
                [m.get('extract_count') or cfg.get('extract_count') or 1 for m in cfg['models']])

    models = build_model_runtimes(cfg['models'], dev_id=cfg.get('dev_id'))

    # 视频质量监测（遮挡 + 挪动/过暗/过曝/模糊/冻结/丢失/抖动/分辨率）按需启动，
    # 借帧回调跨 Decoder 重连循环存活；video_quality 异常时回退纯遮挡监测。
    occl_monitor = None
    if os.path.isfile('/data/AIGO/platform_start/Config_files/pause-stream-video-quality'):
        logger.info('[视频质量] 已暂停随流诊断')
    elif cfg.get('occlusion'):
        try:
            from templates import video_quality
            occl_monitor = video_quality.VideoQualityMonitor(cfg['occlusion'])
            cfg['raw_size_tap'] = occl_monitor.offer_raw_size
        except Exception:
            logger.exception('[视频质量] 启动失败，回退纯遮挡监测')
            try:
                from templates import camera_occlusion
                occl_monitor = camera_occlusion.OcclusionMonitor(cfg['occlusion'])
            except Exception:
                occl_monitor = None
                logger.exception('[遮挡检测] 启动失败（不影响取流/推理/推流主流程）')
        if occl_monitor is not None:
            cfg['frame_tap'] = occl_monitor.offer_frame
            occl_monitor.start()

    img_width = int(cfg['img_width'])
    img_height = int(cfg['img_height'])
    if img_width > 1920 or img_height > 1080:
        img_width, img_height = 1920, 1080
    if cfg.get('rotation') in (90, 270):
        img_width, img_height = img_height, img_width

    
    push_enabled = bool(cfg.get('push_url'))
    push_w, push_h = img_width, img_height
    try:
        push_max_w = int(os.environ.get('PUSH_MAX_WIDTH', '1920') or 0)
    except ValueError:
        push_max_w = 1920
    if push_enabled and push_max_w > 0 and img_width > push_max_w:
        push_w = push_max_w
        push_h = max(2, int(round(img_height * push_max_w / img_width / 2)) * 2)
        logger.info('[push] 推流分辨率降载: %dx%d → %dx%d（PUSH_MAX_WIDTH=%d，报警图仍为原分辨率）',
                    img_width, img_height, push_w, push_h, push_max_w)
    cfg['_push_size'] = (push_w, push_h)
    cfg['_decode_size'] = (img_width, img_height)   # [pre] 线程旋转/缩放的目标尺寸

    dev_id = int(cfg.get('dev_id', 0))
    _configure_sail_decoder(cfg)
    media_handle = sail.Handle(dev_id)
    decode_bmcv = sail.Bmcv(media_handle)

    # Decoder 原始帧诊断：紧跟 decoder.read()、位于 BGR 转换/推理/绘制之前。
    # 默认写入项目根目录 debug_decoded；RTSP_DEBUG_DECODE_DIR=0 可关闭，
    # 也可把该环境变量设置为其它目录。诊断结束后应关闭，避免持续占用磁盘。
    decode_debug_dir = cfg.get('debug_decode_dir')
    env_decode_dir = os.environ.get('RTSP_DEBUG_DECODE_DIR')
    if env_decode_dir is not None:
        decode_debug_dir = (None if env_decode_dir.strip().lower() in ('', '0', 'off', 'false')
                            else env_decode_dir.strip())
    try:
        decode_debug_interval = max(
            0.1, float(os.environ.get(
                'RTSP_DEBUG_DECODE_INTERVAL', cfg.get('debug_decode_interval', 1.0)) or 1.0))
    except (TypeError, ValueError):
        decode_debug_interval = 1.0
    if decode_debug_dir:
        if not os.path.isabs(str(decode_debug_dir)):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            decode_debug_dir = os.path.join(project_root, str(decode_debug_dir))
        decode_debug_dir = os.path.abspath(str(decode_debug_dir))
        os.makedirs(decode_debug_dir, exist_ok=True)
        logger.warning('[诊断] Decoder 原始帧每 %.1fs 保存一张：%s',
                       decode_debug_interval, decode_debug_dir)
    decode_debug_last = 0.0
    decode_debug_seq = 0
    exit_flag = {'requested': False}
    state = None

    def _request_stop(_signum, _frame):
        # 只记录退出请求。由主循环进入 _close_session 停止当前 state，
        # 避免信号打断 Event.wait 时，在信号处理器内重入同一把锁。
        exit_flag['requested'] = True

    try:
        old_sigint = signal.signal(signal.SIGINT, _request_stop)
        old_sigterm = signal.signal(signal.SIGTERM, _request_stop)
    except ValueError:
        old_sigint = old_sigterm = None
        logger.info('[run] 非主线程调用，跳过信号处理器安装（退出由调度框架接管）')

    try:
        while not exit_flag['requested']:
            state = SharedState()
            state.media_handle = media_handle
            decoder = None
            encoder = None
            worker = None
            reconnect_reason = None
            opening_decoder = False
            camera_url, next_camera_url = next_camera_url, None
            if hik_capture.reference is None:
                source_url = camera_url or _rtsp_url_with_credentials(
                    cfg['rtsp_url'], cfg.get('user_id'), cfg.get('user_pw'))
                if not camera_url and not _wait_pull_source_ready(source_url, state.stop_event, exit_flag):
                    break
            if exit_flag['requested']:
                break

            md_channel = None
            source_interval = 0.0
            next_source_frame = 0.0
            use_md = bool(cfg.get('use_multidecoder', True)) and hasattr(sail, 'MultiDecoder')
            try:
                if hik_capture.reference is not None:
                    source_url = hik_capture.open_url()
                    if exit_flag['requested']:
                        break
                opening_decoder = True
                if use_md:
                    # MultiDecoder：取流+解码在 C++ 内部线程完成，Python 侧非阻塞取帧。
                    # 关键动机：sail.Decoder.read 在阻塞等帧的整个期间持有 GIL（py-spy 实测
                    # 解码线程占 GIL 93%），把 pre/inf/agg/push 全部拖慢 10~50 倍（管道仅
                    # ~4fps、端到端延迟 5~8s）。换 MultiDecoder 后 GIL 可用率实测 97%。
                    # 内部帧队列满时丢旧（discard_mode=1），慢消费天然安全，不会背压到
                    # 流媒体服务端（昨日花帧根因），且自带断流重连能力。
                    md_queue = max(2, int(cfg.get('multidecoder_queue', 40) or 40))
                    decoder = sail.MultiDecoder(md_queue, dev_id, 1)
                    try:
                        decoder.set_read_timeout(1)
                    except Exception:
                        pass
                    md_channel = (open_camera_decoder(decoder.add_channel, source_url, 0) if camera_url
                                  else decoder.add_channel(source_url, 0))
                    if md_channel is None or md_channel < 0:
                        raise RuntimeError('SAIL MultiDecoder add_channel 失败')
                    logger.info('[SAIL MultiDecoder] RTSP 硬解通道已建立 ch=%d queue=%d 丢旧模式',
                                md_channel, md_queue)
                else:
                    # 部分 SDK/摄像头在压缩 NV12 面上会出现块状花屏，默认关闭压缩以可靠性优先。
                    decoder_compressed = bool(cfg.get('decoder_compressed', False))
                    decoder = (open_camera_decoder(sail.Decoder, source_url, decoder_compressed, dev_id) if camera_url
                               else sail.Decoder(source_url, decoder_compressed, dev_id))
                    if not decoder.is_opened():
                        raise RuntimeError('SAIL Decoder 无法打开拉流地址')
                    logger.info('[SAIL Decoder] RTSP 硬解拉流已打开 compressed=%s', decoder_compressed)

                if exit_flag['requested']:
                    break
                opening_decoder = False
                try:
                    reported_fps = decoder.get_channel_fps(md_channel) if use_md else decoder.get_fps()
                    if 1 <= float(reported_fps) <= 120:
                        state.archive_source_fps = float(reported_fps)
                except (AttributeError, TypeError, ValueError, RuntimeError):
                    pass
                if push_enabled:
                    encoder = _create_sail_encoder(cfg, push_w, push_h)
                    state.encoder = encoder
                    state.encoder_bmcv = sail.Bmcv(media_handle)
                if exit_flag['requested']:
                    break

                if use_md and state.archive_source_fps:
                    source_interval = 1.0 / state.archive_source_fps
                    logger.info('解码通道源帧率 %.2f，缓存上限 %d 帧', state.archive_source_fps, md_queue)
                worker = threading.Thread(
                    target=_run_stage,
                    args=(state, 'infer-worker', worker_loop, (state, cfg, models), True),
                    daemon=True, name='infer-worker')
                worker.start()
                logger.info('SAIL 硬解%s初始化完成，等待处理首帧', '+硬编' if push_enabled else '')

                # 断流判定：MultiDecoder 空读不算错误，超过 stall_timeout 无帧才重连
                stall_timeout = max(5.0, float(cfg.get('pull_seconds', 5) or 5) * 2)
                last_frame_ok = time.monotonic()
                while not exit_flag['requested'] and not state.stop_event.is_set():
                    frame = sail.BMImage()
                    if use_md:
                        # Smooth TCP bursts in the decoder's bounded native FIFO. Deliver
                        # the first frame immediately and reset the clock after a source gap.
                        delay = next_source_frame - time.monotonic()
                        if delay > 0 and state.stop_event.wait(delay):
                            break
                        ret = decoder.read(md_channel, frame, 0)
                        if ret != 0 or frame.width() <= 0:
                            empty_for = time.monotonic() - last_frame_ok
                            if empty_for > stall_timeout:
                                reconnect_reason = ('SAIL MultiDecoder %.0fs 未收到帧，判定断流'
                                                    % stall_timeout)
                                break
                            state.stop_event.wait(_decoder_idle_delay(empty_for))
                            continue
                        if state.archive_source_fps and hasattr(decoder, 'get_drop_num'):
                            try:
                                dropped = int(decoder.get_drop_num(md_channel))
                                state.archive_native_drops = max(state.archive_native_drops, dropped)
                            except (AttributeError, TypeError, ValueError, RuntimeError):
                                pass
                        last_frame_ok = time.monotonic()
                        # A small amount of headroom drains residual backlog after a burst.
                        next_source_frame = max(next_source_frame + source_interval * 0.98,
                                                last_frame_ok + source_interval * 0.95)
                    else:
                        ret = decoder.read(media_handle, frame)
                        if ret != 0:
                            reconnect_reason = 'SAIL Decoder.read 失败，返回码=%s' % ret
                            break
                    if exit_flag['requested'] or state.stop_event.is_set():
                        break

                    # 直接保存 Decoder 输出的 BMImage，不经过本程序的 BGR 转换、推理或绘制。
                    # 如果这里的图片也花屏，可确定问题发生在源流/硬件解码阶段。
                    now_mono = time.monotonic()
                    if (decode_debug_dir and
                            now_mono - decode_debug_last >= decode_debug_interval):
                        decode_debug_last = now_mono
                        decode_debug_seq += 1
                        stamp = time.strftime('%Y%m%d_%H%M%S')
                        debug_file = os.path.join(
                            decode_debug_dir,
                            'decoded_raw_%s_%s_%06d.jpg' % (
                                _stream_tag(cfg), stamp, decode_debug_seq))
                        try:
                            write_ret = decode_bmcv.imwrite(debug_file, frame)
                            if write_ret not in (0, None):
                                logger.error('[诊断] Decoder 原始帧保存失败 ret=%s path=%s',
                                             write_ret, debug_file)
                        except Exception:
                            logger.exception('[诊断] Decoder 原始帧保存异常：%s', debug_file)

                    # 解码线程热路径到此为止：VPP 设备侧转 BGR_PACKED（~2ms）后立即入队，
                    # numpy 拷贝/旋转/缩放/借帧回调全部在 [pre] 线程完成。这里不做任何
                    # CPU 重活、也不做周期性 gc.collect()——任何停顿都会通过 TCP 背压
                    # 变成流媒体服务端丢包，直接导致花屏。
                    _offer_decoded_frame(
                        state, cfg, _bmimage_to_packed(frame, media_handle, decode_bmcv))

                if state.media_error:
                    reconnect_reason = state.media_error
                if reconnect_reason:
                    logger.warning('%s；释放 SAIL 编解码器后重连', reconnect_reason)
            except KeyboardInterrupt:
                logger.info('用户中断')
                exit_flag['requested'] = True
            except Exception as exc:
                if hik_capture.reference is not None:
                    reconnect_reason = '海康取流/推流会话异常'
                    logger.warning('%s；释放后重连', reconnect_reason)
                else:
                    reconnect_reason = str(exc)
                    logger.exception('SAIL 取流/推流会话异常；释放后重连')
                    if opening_decoder and recorder_channel and not camera_url and time.monotonic() >= next_mapping_check:
                        next_mapping_check = time.monotonic() + 30
                        next_camera_url = recorder_channel.verified_camera_after_failure(source_url)
                        if next_camera_url:
                            logger.info('录像机 SETUP 失败，已核对摄像机通道及码流，下一次使用摄像机直连')
            finally:
                _close_session(state, worker, decoder, encoder, use_md, md_channel)
                state = None
                decoder = None
                encoder = None
                gc.collect()

            if not exit_flag['requested']:
                delay = max(0.2, float(cfg.get('pull_seconds', 5) or 5))
                logger.info('[重连] %.1fs 后重建 SAIL Decoder/Encoder', delay)
                deadline = time.monotonic() + delay
                while not exit_flag['requested']:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.2, remaining))
    finally:
        try:
            if occl_monitor is not None:
                try:
                    occl_monitor.stop()
                    occl_monitor.join(timeout=2)
                except Exception:
                    pass
            for m in models:
                try:
                    m['net'].release()
                except Exception:
                    pass
            if exit_flag['requested']:
                logger.info('[run] 已退出流会话并完成编解码清理')
        finally:
            if old_sigint is not None:
                signal.signal(signal.SIGINT, old_sigint)
            if old_sigterm is not None:
                signal.signal(signal.SIGTERM, old_sigterm)
