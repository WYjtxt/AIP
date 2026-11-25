"""Native-size annotated alarm clips with a lossless, time-bounded I420 frame buffer."""
from templates import alarm_directory
import os
import json
import re
import time
import queue
import shutil
import logging
import threading
import tempfile
import subprocess
from collections import deque

import cv2
import numpy as np

from config import common as cm

logger = logging.getLogger('alarm_video')

_OUT_DIR = os.environ.get('ALARM_VIDEO_DIR') or '/data/AIGO/outputs/videos'
_PRE_SEC = max(1.0, float(os.environ.get('ALARM_VIDEO_PRE_SEC', '5') or 5))
_POST_SEC = max(0.0, float(os.environ.get('ALARM_VIDEO_POST_SEC', '5') or 5))
_FPS = max(1.0, float(os.environ.get('ALARM_VIDEO_FPS', '25') or 25))
_PACKBITS = [cv2.IMWRITE_TIFF_COMPRESSION, 32773]
# 缓冲须盖住 [事件开始-pre, 触发时刻]：会话类报警（人数统计）片段 = 整个会话前后各
# 扩 pre/post 秒，且收尾检测在画面持续有人逗留时可滞后很久（"无活跃轨迹 3s"迟迟不
# 满足，实测 30s+）。50s 裕量 ≈ 完整覆盖 ≤40s 会话 + 收尾滞后；更长会话头部滚出缓冲，
# 照存并打 warning（视频短于应有时长）。内存 ≈随所选码流分辨率、帧率与场景变化。
_KEEP_SEC = _PRE_SEC + _POST_SEC + 50.0
_MAX_CONCURRENT_SAVES = 3
_MAX_COUNT_IMAGES = 512
_COUNT_IMAGE_NAME = re.compile(r'alarm_[0-9a-f]{32}_[0-9]{6,}\.jpg\Z')
# H.264 输出（浏览器可播）：算能 ffmpeg 的 VPU 硬编码器 h264_bm。软件帧必须显式
# -is_dma_buffer 0（默认 1 期望 DMA 物理连续缓冲，软件帧会报 Invalid pic data）。
_FFMPEG = os.environ.get('FFMPEG_BIN') or shutil.which('ffmpeg')
_H264_BITRATE = os.environ.get('ALARM_VIDEO_H264_BITRATE')
_SOFT_FFMPEG = '/data/AIGO/platform_start/runtime/bin/ffmpeg'
# 平台命名规则的前两段：20 位摄像仪编码 / 分析类型。
# 摄像仪编码 = 平台下发的 GB28181_code，进程入口调 set_camera_code() 注入；
# 分析类型 = 报警点按类型经 trigger(analysis_type=..) 传入（人数统计 01/02/0102、
# 视频质量 03、其它 00）。环境变量非空时强制覆盖（现场排查/联调用）。
_ENV_CAMERA_CODE = re.sub(r'[\\/:*?"<>|\s]+', '', os.environ.get('ALARM_VIDEO_CAMERA_CODE', '') or '')
_ENV_ANALYSIS_TYPE = re.sub(r'[\\/:*?"<>|\s]+', '', os.environ.get('ALARM_VIDEO_ANALYSIS_TYPE', '') or '')
_camera_code = ''       # set_camera_code() 注入（每进程一次）

# 滚动清理：报警视频/报警图无上限积累会占满盒上磁盘（视频 ~10MB/条；冻结/丢失类
# 持续性故障可数天无人处理，按节流间隔持续产出）。按 mtime 超龄删除，默认保留 7 天。
_KEEP_DAYS = max(0.5, float(os.environ.get('ALARM_VIDEO_KEEP_DAYS', '7') or 7))
_prune_lock = threading.Lock()
_prune_last = {}        # dir -> 上次实际扫描时刻


def prune_dir(dir_path, exts, keep_days=None, min_interval=3600.0):
    '''按 mtime 滚动清理 dir_path 下扩展名属 exts 的旧文件（报警视频与各类报警图共用）。
    每目录至多 min_interval 秒真正扫描一次，其余调用直接返回；仅在报警落盘等
    背景线程调用，不进热路径。单个文件删除失败只记日志继续。'''
    now = time.time()
    with _prune_lock:
        if now - _prune_last.get(dir_path, 0.0) < min_interval:
            return
    cutoff = now - (keep_days or _KEEP_DAYS) * 86400.0
    removed = 0
    try:
        with os.scandir(dir_path) as it:
            # 扫描成功打开才记冷却：目录尚未创建/暂不可读时不占用整小时窗口
            with _prune_lock:
                _prune_last[dir_path] = now
            for entry in it:
                try:
                    if entry.is_file() and entry.name.lower().endswith(exts) \
                            and entry.stat().st_mtime < cutoff:
                        os.remove(entry.path)
                        removed += 1
                except OSError:
                    logger.warning('[报警视频] 清理失败: %s', entry.path)
    except OSError:
        return
    if removed:
        logger.info('[报警视频] 已清理 %s 下 %d 个超过 %.1f 天的旧文件',
                    dir_path, removed, keep_days or _KEEP_DAYS)


def set_camera_code(code):
    '''注入本进程的 20 位摄像仪编码（t_equipment.GB28181_code，经 get_data 下发）。
    进程入口调用一次即可（每路流/每 s2m 任务一个进程，同进程内编码唯一）；
    空值忽略并保留占位 0000；ALARM_VIDEO_CAMERA_CODE 环境变量非空时仍优先。'''
    global _camera_code
    code = re.sub(r'[\\/:*?"<>|\s]+', '', str(code or ''))
    if code:
        _camera_code = code
        logger.info('[报警视频] 摄像仪编码已注入: %s', code)


def _naming_fields(analysis_type):
    '''返回文件名前两段 (摄像仪编码, 分析类型)：环境变量 > 运行时注入/传参 > 占位。'''
    camera = _ENV_CAMERA_CODE or _camera_code or '0000'
    atype = (_ENV_ANALYSIS_TYPE
             or re.sub(r'[\\/:*?"<>|\s]+', '', str(analysis_type or ''))
             or '00')
    return camera, atype


def _reserve_path(base, ext):
    '''O_EXCL 原子占位防跨进程同名互相覆盖：撞名追加 _N 段，返回占位成功的完整路径。'''
    out_dir = alarm_directory.video_dir()
    os.makedirs(out_dir, exist_ok=True)
    i = 0
    while True:
        name = base if i == 0 else '%s_%d' % (base, i)
        path = os.path.join(out_dir, name + ext)
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL))
            return path
        except FileExistsError:
            i += 1


def _discard(path):
    '''释放占位文件（保存失败/回退换扩展名时），不留 0 字节残骸。'''
    try:
        os.remove(path)
    except OSError:
        pass


def _archive_i420(annotated, native):
    if native is not None and native.shape[:2] != annotated.shape[:2]:
        native_size = native.shape[1], native.shape[0]
        ref = cv2.resize(native, (annotated.shape[1], annotated.shape[0]), interpolation=cv2.INTER_LINEAR)
        unchanged = cv2.inRange(cv2.absdiff(ref, annotated), (0, 0, 0), (0, 0, 0))
        mask = cv2.resize(cv2.bitwise_not(unchanged), native_size, interpolation=cv2.INTER_NEAREST)
        colors = cv2.resize(annotated, native_size, interpolation=cv2.INTER_NEAREST)
        # Native belongs to this decoded frame. Preview consumers only see annotated.
        cv2.copyTo(colors, mask, native)
        annotated = native
    # H.264 4:2:0 requires even dimensions. Replicate only the final row/column as needed.
    h, w = annotated.shape[:2]
    if h % 2 or w % 2:
        annotated = cv2.copyMakeBorder(annotated, 0, h % 2, 0, w % 2, cv2.BORDER_REPLICATE)
    return cv2.cvtColor(annotated, cv2.COLOR_BGR2YUV_I420)


def _unpack(data):
    if isinstance(data, os.PathLike):
        image = cv2.imread(os.fspath(data))
        if image is None:
            raise ValueError("Unreadable persisted count frame")
        return _archive_i420(image, None)
    plane = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if plane is None:
        raise ValueError("Invalid lossless alarm buffer")
    return plane


def _write_count_coverage(path, conf_name, start_ts, alarm_ts, frames, fps, images=()):
    """Store only timing evidence for a finalized count recording."""
    file_info = os.stat(path)
    stamps = [item[0] for item in frames]
    gaps = (current - previous for previous, current in zip(stamps, stamps[1:])
            if previous < alarm_ts and current > start_ts)
    state = {
        'schema': 1, 'kind': 'recording-coverage', 'status': 'ready',
        'conf_name': conf_name, 'start': start_ts, 'end': alarm_ts,
        'first_frame': stamps[0], 'last_frame': stamps[-1],
        'largest_gap': max(gaps, default=0.0),
        'frame_tolerance': min(1.0, max(.15, 2.0 / fps)),
        'video_size': file_info.st_size, 'video_mtime_ns': file_info.st_mtime_ns,
    }
    if images:
        frame_times = set(stamps)
        evidence = []
        for name, stamp, kind in images[:_MAX_COUNT_IMAGES]:
            if not _COUNT_IMAGE_NAME.fullmatch(name) or kind not in ('observed', 'last_visible', 'inferred_crossing'):
                continue
            capture = {'name': name, 'platform_ts': stamp, 'evidence_kind': kind}
            if stamp in frame_times:
                capture.update(source_ts=stamp, offset_seconds=round((stamp - stamps[0]) * 1000) / 1000.0)
            evidence.append(capture)
        if evidence:
            state['images'] = evidence
    scratch = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False,
                                         prefix='.archive-coverage-', dir=os.path.dirname(path)) as out:
            scratch = out.name
            json.dump(state, out, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        os.replace(scratch, path + '.count-coverage.json')
    finally:
        if scratch and os.path.exists(scratch):
            os.remove(scratch)


class _Recorder:
    '''进程内单例：时间采样 → 独立线程 无损缓冲 → 时间环形缓冲 → 报警时异步写片段。'''

    def __init__(self):
        self.pid = os.getpid()
        self._interval = 1.0 / _FPS
        self._last_feed = 0.0
        self._in_q = queue.Queue(maxsize=12)
        self._queue_drops = 0
        self._source_epoch = None
        self._source_anchor = 0
        self._source_start = 0.0
        self._source_last_time = 0.0
        self._buf = deque()                  # (frame timestamp, packed I420)
        self._buf_lock = threading.Lock()
        self._saving = 0
        self._saving_lock = threading.Lock()
        threading.Thread(target=self._encode_loop, name='alarm_video_buf', daemon=True).start()

    def frame_timestamp(self, arrival=None, frame_no=None, rate=0, epoch=None):
        """Resolve the frame clock once for analysis and archive sampling."""
        now = time.time() if arrival is None else arrival
        stamp = now
        if rate and frame_no is not None:
            if self._source_epoch is not epoch:
                self._source_epoch = epoch
                self._source_start, self._source_anchor = now, frame_no
            stamp = self._source_start + (frame_no - self._source_anchor) / rate
            # A reconnect or a sustained cadence change invalidates the estimate.
            # Short arrival bursts are normal on RTSP/TCP and retain their order.
            if abs(now - stamp) > 2:
                self._source_start, self._source_anchor = now, frame_no
                stamp = now
        stamp = max(stamp, self._source_last_time + 0.001)
        self._source_last_time = stamp
        return stamp

    # ---- 喂帧（聚合线程/解码回调热路径：只做采样判断 + 非阻塞入队） ----
    def feed(self, frame_bgr, arrival=None, frame_no=None, rate=0, epoch=None, native=None,
             timestamp=None):
        stamp = self.frame_timestamp(arrival, frame_no, rate, epoch) if timestamp is None else timestamp
        if stamp - self._last_feed < self._interval - 0.0005:
            return
        try:
            self._in_q.put_nowait((stamp, frame_bgr, native))
        except queue.Full:
            self._queue_drops += 1
            if self._queue_drops == 1 or self._queue_drops % 100 == 0:
                logger.warning("Alarm archive queue full: %d dropped frames", self._queue_drops)
            return
        self._last_feed = max(self._last_feed + self._interval, stamp - self._interval)

    def _encode_loop(self):
        while True:
            ts, frame, native = self._in_q.get()
            try:
                yuv = _archive_i420(frame, native)
                ok, enc = cv2.imencode('.tiff', yuv, _PACKBITS)
            except Exception:
                logger.exception('[报警视频] 帧压缩异常')
                continue
            if not ok:
                continue
            data = enc.tobytes()
            with self._buf_lock:
                self._buf.append((ts, data))
                cutoff = ts - _KEEP_SEC
                while self._buf and self._buf[0][0] < cutoff:
                    self._buf.popleft()

    # ---- 触发（报警点调用，立即返回；返回视频 URL 供 warning_video 上报） ----
    def trigger(self, conf_name, alarm_ts=None, start_ts=None, analysis_type=None, images=()):
        alarm_ts = float(alarm_ts) if alarm_ts else time.time()
        start_ts = float(start_ts) if start_ts else alarm_ts   # 始末暂同值口径
        start_ts = min(start_ts, alarm_ts)                     # 防倒置：起点不得晚于终点
        if str(analysis_type) == '03':
            with self._buf_lock:
                count = sum(start_ts - _PRE_SEC <= stamp <= alarm_ts + _POST_SEC for stamp, _ in self._buf)
            if count < 2:
                logger.info('[报警视频] 视频丢失期间没有可用画面: %s', conf_name)
                return None
        with self._saving_lock:
            if self._saving >= _MAX_CONCURRENT_SAVES:
                logger.warning('[报警视频] %s 并发保存已达 %d 路，本次跳过',
                               conf_name, _MAX_CONCURRENT_SAVES)
                return None
            self._saving += 1
        # 文件名在触发时即取定并 O_EXCL 占位：返回的 URL 与最终落盘文件严格一致，
        # 供调用方立刻放进上报消息的 warning_video（视频本体延后 post 秒才写完）。
        # 平台命名规则：摄像仪编码_分析类型_报警开始时间_报警结束时间（yyyyMMddHHmmss）
        try:
            camera, atype = _naming_fields(analysis_type)
            base = '%s_%s_%s_%s' % (camera, atype,
                                    time.strftime('%Y%m%d%H%M%S', time.localtime(start_ts)),
                                    time.strftime('%Y%m%d%H%M%S', time.localtime(alarm_ts)))
            os.makedirs(_OUT_DIR, exist_ok=True)
            path = _reserve_path(base, '.mp4')
        except Exception:
            with self._saving_lock:
                self._saving -= 1
            logger.exception('[报警视频] %s 文件名占位失败，本次无视频', conf_name)
            return None
        count_clip = str(analysis_type) in ('01', '02', '0102')
        threading.Thread(target=self._save_clip, args=(conf_name, alarm_ts, start_ts, path, count_clip, tuple(images)),
                         name='alarm_video_save', daemon=True).start()
        # URL 口径同报警图：主机 = 算力盒本机 IP（文件存在盒子上），端口 = upload_port
        return alarm_directory.media_url(path, cm.localhost_ip, cm.upload_port)

    def _encode_h264(self, conf_name, frames, fps, w, h, path):
        # Keep each actual frame once, on its own timestamp. The vendor encoder
        # writes fixed-rate DTS; Matroska carries the actual PTS and the final
        # stream copy derives matching MP4 sample durations without re-encoding.
        first_ts = frames[0][0]
        stamps = [round((ts - first_ts) * 1000) for ts, _ in frames]
        def timestamp_expression(lo, hi):
            if hi - lo == 1:
                return str(stamps[lo])
            mid = (lo + hi) // 2
            return 'if(lt(N,%d),%s,%s)' % (mid, timestamp_expression(lo, mid), timestamp_expression(mid, hi))
        try:
            with tempfile.TemporaryDirectory(prefix='.alarm-', dir=os.path.dirname(path)) as work:
                graph = os.path.join(work, 'timestamps.txt')
                intermediate = os.path.join(work, 'video.mkv')
                output = os.path.join(work, 'complete.mp4')
                with open(graph, 'w', encoding='ascii') as stream:
                    stream.write("scale=%d:%d,settb=1/1000,setpts='%s'" %
                                 (w, h, timestamp_expression(0, len(frames))))
                # Stream each losslessly buffered YUV frame directly to the encoder.
                # The MP4 remux below only copies packets.
                rate_control = ['-b:v', _H264_BITRATE] if _H264_BITRATE else ['-qp', '20']
                options = [(_FFMPEG, ['-c:v', 'h264_bm', '-gop_preset', '2',
                                      '-is_dma_buffer', '0'] + rate_control)]
                if os.path.isfile(_SOFT_FFMPEG):
                    options.append((_SOFT_FFMPEG, ['-c:v', 'libx264', '-preset', 'veryfast',
                                                   '-crf', '18', '-bf', '0', '-threads', '2']))
                for binary, encoder in options:
                    if not binary:
                        continue
                    cmd = [binary, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-video_size', '%dx%d' % (w, h),
                           '-framerate', str(_FPS), '-i', 'pipe:0', '-filter_threads', '1',
                           '-filter_script:v', graph] + encoder + [
                           '-vsync', 'vfr', '-enc_time_base', '1:1000', '-r', str(_FPS), intermediate]
                    try:
                        with tempfile.TemporaryFile() as err, subprocess.Popen(
                                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err) as proc:
                            timer = threading.Timer(180, proc.kill)
                            timer.start()
                            try:
                                with proc.stdin as sink:
                                    for _, data in frames:
                                        plane = _unpack(data)
                                        if plane.shape != (h * 3 // 2, w):
                                            bgr = cv2.cvtColor(plane, cv2.COLOR_YUV2BGR_I420)
                                            plane = cv2.cvtColor(cv2.resize(bgr, (w, h)), cv2.COLOR_BGR2YUV_I420)
                                        sink.write(memoryview(plane))
                                if proc.wait():
                                    raise RuntimeError("encoder exited")
                            finally:
                                timer.cancel()
                        break
                    except (OSError, RuntimeError) as exc:
                        logger.warning("Alarm encoder %s failed: %s", encoder[1], type(exc).__name__)
                else:
                    return False
                subprocess.run([binary, '-nostdin', '-loglevel', 'error', '-i', intermediate,
                                '-map', '0:v:0', '-c', 'copy', '-movflags', '+faststart', output],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=60)
                os.replace(output, path)
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning('[报警视频] %s H.264编码或封装失败: %s', conf_name, type(exc).__name__)
            return False

    def _save_clip(self, conf_name, alarm_ts, start_ts, path, count_clip, images=()):
        try:
            # 顺带滚动清理旧报警视频（已在后台保存线程，非热路径；内部每小时至多一次）
            prune_dir(os.path.dirname(path), ('.mp4', '.avi', '.mp4.count-coverage.json'))
            # 等事件结束后 post 秒的帧全部进缓冲（多等 1.5s：采样间隔 + 压缩队列消化）
            wait = alarm_ts + _POST_SEC + 1.5 - time.time()
            if wait > 0:
                time.sleep(wait)
            # 片段窗口 = [事件开始-pre, 事件结束+post]；瞬时报警始末同值即 pre+post 秒
            lo, hi = start_ts - _PRE_SEC, alarm_ts + _POST_SEC
            want = hi - lo
            with self._buf_lock:
                buf = list(self._buf)
            frames = [item for item in buf if lo <= item[0] <= hi]
            # 会话过长/收尾检测滞后过久时，事件窗口可能已部分/完全滚出环形缓冲——
            # 完全滚出则退而保存缓冲里最近 want 秒（会话收尾场景），仍优于无视频/404；
            # 部分滚出照存（视频短于应有时长），都打 warning 便于现场归因。
            if frames and buf[0][0] > lo:
                logger.warning('[报警视频] %s 时间窗头部已超出缓冲，保存可用时段', conf_name)
            if len(frames) < 2:
                logger.warning('[报警视频] %s 时间窗内缓冲帧不足(%d 帧)，放弃保存'
                               '（进程刚启动或报警时刻距今超出缓冲窗口）；'
                               '已上报的 warning_video 将无对应文件: %s', conf_name, len(frames), path)
                _discard(path)
                return
            span = frames[-1][0] - frames[0][0]
            fps = max(1.0, (len(frames) - 1) / span) if span > 0 else _FPS
            plane = _unpack(frames[0][1])
            h, w = plane.shape[0] * 2 // 3, plane.shape[1]
            if self._encode_h264(conf_name, frames, fps, w, h, path):
                if count_clip:
                    try:
                        _write_count_coverage(path, conf_name, start_ts, alarm_ts, frames, fps, images)
                    except (OSError, ValueError):
                        logger.warning('[报警视频] %s 保存统计录像时段信息失败', conf_name, exc_info=True)
                logger.info('[报警视频] %s 已保存(H.264): %s（%d 帧 / %.1f 秒 / %.1ffps）',
                            conf_name, path, len(frames), span, fps)
                return
            logger.error("No encoder could save the timestamped alarm clip: %s", path)
            _discard(path)
        except Exception:
            _discard(path)
            logger.exception('[报警视频] %s 保存异常', conf_name)
        finally:
            with self._saving_lock:
                self._saving -= 1


_recorder = None
_recorder_lock = threading.Lock()


def save_count_recording(session_id, conf_name, start_ts, end_ts, analysis_type, images, backup):
    """Encode native frames and durably retained observations before publishing the URL."""
    recorder = _get()
    camera, atype = _naming_fields(analysis_type)
    base = '%s_%s_%s_%s_%d.mp4' % (camera, atype,
            time.strftime('%Y%m%d%H%M%S', time.localtime(start_ts)),
            time.strftime('%Y%m%d%H%M%S', time.localtime(end_ts)), int(session_id, 16))
    directory = alarm_directory.video_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, base)
    url = alarm_directory.media_url(path, cm.localhost_ip, cm.upload_port)
    try:
        with open(path + '.count-coverage.json', encoding='utf8') as f:
            previous = json.load(f)
        stat = os.stat(path)
        if (previous.get('start') == start_ts and previous.get('end') == end_ts
                and previous.get('video_size') == stat.st_size > 0
                and previous.get('video_mtime_ns') == stat.st_mtime_ns):
            return url
    except (OSError, ValueError):
        pass
    wait = min(_POST_SEC + 1.5, end_ts + _POST_SEC + 1.5 - time.time())
    if wait > 0:
        time.sleep(wait)
    lo, hi = start_ts - _PRE_SEC, end_ts + _POST_SEC
    with recorder._buf_lock:
        native = {ts:data for ts,data in recorder._buf if lo <= ts <= hi}
    # Match exact native timestamps where possible. Keep real capture timestamps
    # at millisecond resolution even when the sampling ring skipped that frame.
    frames_by_ms = {round(ts*1000):(ts,data) for ts,data in backup.items() if lo <= ts <= hi}
    frames_by_ms.update({round(ts*1000):(ts,data) for ts,data in native.items()})
    for _, stamp, _ in images:
        if stamp in backup:
            frames_by_ms[round(stamp*1000)] = stamp, native.get(stamp, backup[stamp])
    frames = sorted(frames_by_ms.values())
    if len(frames) < 2 or not images:
        raise ValueError('Insufficient real frames for count replay')
    span = frames[-1][0] - frames[0][0]
    fps = max(1.0, (len(frames)-1) / span)
    plane = _unpack(next(iter(native.values())) if native else frames[0][1])
    h, w = plane.shape[0]*2//3, plane.shape[1]
    if not recorder._encode_h264(conf_name, frames, fps, w, h, path):
        raise OSError('Count replay encoding failed')
    _write_count_coverage(path, conf_name, start_ts, end_ts, frames, fps, images)
    prune_dir(directory, ('.mp4', '.avi', '.mp4.count-coverage.json'))
    return url


def _get():
    global _recorder
    rec = _recorder
    if rec is None or rec.pid != os.getpid():     # fork 后旧线程不存在，按进程重建
        with _recorder_lock:
            rec = _recorder
            if rec is None or rec.pid != os.getpid():
                rec = _Recorder()
                _recorder = rec
    return rec


def frame_timestamp(arrival=None, frame_no=None, rate=0, epoch=None):
    """Clock shared by opt-in inference callbacks and their recorded frames."""
    try:
        return _get().frame_timestamp(arrival, frame_no, rate, epoch)
    except Exception:
        # Recorder initialization must not interrupt inference.
        return time.time() if arrival is None else arrival


def feed(frame_bgr, arrival=None, frame_no=None, rate=0, epoch=None, native=None, timestamp=None):
    '''每帧喂入显示帧（引擎聚合线程 / s2m 解码回调调用）。内部时间采样 + 异步压缩，热路径安全。'''
    try:
        _get().feed(frame_bgr, arrival, frame_no, rate, epoch, native, timestamp)
    except Exception:
        pass          # 缓冲失败绝不影响推理/推流主链路


def trigger(conf_name, alarm_ts=None, start_ts=None, analysis_type=None, images=()):
    '''报警触发：后台保存 [事件开始-5s, 事件结束+5s] 视频片段到 results/videos/，立即返回。
    返回本次视频的 URL（http://盒IP:upload_port<绝对路径>，供上报 warning_video 字段），
    跳过/失败返回 None（调用方按无视频上报即可）。
    alarm_ts 为报警事件结束时刻（片段终点=结束+post），缺省当前时刻；会话类报警可传
    真实事件时刻（滞后不能超出缓冲窗口）。start_ts 为报警事件开始时刻（片段起点=
    开始-pre，并进文件名），缺省 = alarm_ts（始末暂同值口径，片段即 pre+post 秒）；
    会话类报警传真实会话起点，片段随会话时长变长。
    analysis_type 为平台命名规则的分析类型段：人数统计 仅进=01 / 仅出=02 / 有进有出=0102，
    视频质量(遮挡)=03；缺省 00（其它类型暂定）。'''
    try:
        return _get().trigger(conf_name, alarm_ts, start_ts, analysis_type, images)
    except Exception:
        logger.exception('[报警视频] trigger 异常')
        return None
