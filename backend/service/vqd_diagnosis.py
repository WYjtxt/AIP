# native-diagnosis-auto-reference-v1
from service.vqd_auto_reference import ensure_reference
# native-diagnosis-rating-v1
# native-diagnosis-runtime-alias-v1
"""Bounded diagnosis capture with explicit, credential-free failure reasons."""
from pathlib import Path
import json
import re
import subprocess
import uuid
import logging
import time

from service.vqd_quality import LABELS, analyze, load_reference, small


ITEMS = (
    ('视频抖动', 'jitter_detection'), ('条纹干扰', 'stripe_interference_detection'),
    ('视频丢失', 'frame_loss_detection'), ('视频遮挡', 'occlusion_detection'),
    ('视频冻结', 'freeze_detection'), ('高亮度', 'brightness_detection'),
    ('低亮度', 'brightness_detection'), ('视频噪声', 'noise_detection'),
    ('偏色', 'color_cast_detection'), ('清晰度', 'clearness_detection'),
    ('场景变化', 'scene_change_detection'), ('对比度', 'contrast_anomaly_detection'),
    ('横纹干扰', 'horizontal_waves_detection'), ('滚动条纹', 'scroll_interference_detection'),
    ('横波干扰', 'horizontal_stripes_detection'), ('花帧检测', 'glitch_detection'),
)


def stream_failure(stderr='', timed_out=False):
    """Never return raw FFmpeg output, which can contain camera credentials."""
    message = re.sub(r'(?i)[a-z][a-z0-9+.-]*://\S+', '[video-source]', str(stderr)).lower()
    if timed_out or 'timed out' in message or 'timeout' in message:
        return '取流超时：视频源未在8秒内响应'
    for marker, reason in (
        ('401', '取流认证失败（401）：请检查视频源账号、密码或通道权限'),
        ('403', '视频源拒绝访问（403）：当前账号没有通道访问权限'),
        ('404', '视频源不存在或尚未就绪（404）：请检查平台转发和通道状态'),
        ('500', '视频源返回服务器错误（500）：无法建立视频会话'),
        ('connection refused', '视频源拒绝连接：请检查服务和RTSP端口'),
        ('no route to host', '视频源网络不可达：请检查设备网络'),
        ('network is unreachable', '视频源网络不可达：请检查设备网络'),
        ('name or service not known', '视频源地址解析失败：请检查设备地址'),
        ('invalid data', '视频源数据无效：无法识别视频格式'),
    ):
        if (re.search(r'(?<!\w)' + marker + r'(?!\w)', message) if marker.isdigit() else marker in message):
            return reason
    return '取流失败：未取得有效视频流，请检查视频源连接和编码'


def probe_stream(url):
    if not url:
        return '未配置可用的视频源，请检查设备的视频转发关联'
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-rtsp_transport', 'tcp', '-show_entries',
             'stream=codec_type,codec_name,width,height', '-of', 'json', url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
    except subprocess.TimeoutExpired:
        return stream_failure(timed_out=True)
    except OSError:
        return '诊断服务缺少可用的FFmpeg取流工具'
    if result.returncode:
        return stream_failure(result.stderr.decode('utf-8', errors='replace'))
    try:
        streams = json.loads(result.stdout).get('streams', [])
        if not any(stream.get('codec_type') == 'video' for stream in streams):
            return '视频源中没有视频轨道，无法进行画质诊断'
    except (ValueError, TypeError, AttributeError):
        return '视频源信息无效，无法读取视频轨道'
    return ''


class Capture:
    def __init__(self, url):
        import cv2
        self.cv2 = cv2
        self.successful_reads = 0
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
            # SITE_PATCH_VQD_HEVC_V1
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000])

    def read(self):
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.successful_reads += 1
        return ok, frame

    def __getattr__(self, name):
        return getattr(self.cap, name)


def open_capture(url):
    return Capture(url)


def snapshot(frame):
    import cv2
    # Reuse the existing persistent results mount and authenticated media gateway.
    root = Path('/data/AIGO/outputs/vqd')
    if root.is_symlink():
        raise OSError('Invalid snapshot directory')
    root.mkdir(mode=0o755, parents=True, exist_ok=True)
    root.chmod(0o755)
    filename = 'vqd_' + uuid.uuid4().hex + '.jpg'
    target = root / filename
    if not cv2.imwrite(str(target), frame, [cv2.IMWRITE_JPEG_QUALITY, 85]):
        raise OSError('Snapshot write failed')
    target.chmod(0o644)
    return '/media/alarms/vqd/' + filename


def _row(source, statuses, image, reason, failed=False):
    checked = [value for value in statuses if value != '未检测']
    if failed or '检测失败' in checked:
        overall = '失败'
    elif '报警' in checked:
        overall = '很差'
    elif '预警' in checked:
        overall = '一般'
    elif checked and all(value == '正常' for value in checked):
        overall = '达标'
    else:
        overall = '未检测'
    return [str(source['id']), source.get('ip', ''), source.get('name', ''),
            source.get('parent_ip', ''), overall] + statuses + [image, source.get('parent_name', ''), reason[:512]]


def sample_window(cap, duration=6.0, sample_fps=8):
    frames, times, last = [], [], None
    started = time.monotonic()
    next_sample = started
    failures = consecutive = 0
    while time.monotonic() - started < duration:
        ok, frame = cap.read()
        now = time.monotonic()
        if not ok or frame is None or frame.size == 0:
            failures += 1
            consecutive += 1
            if consecutive >= 2:
                break
            continue
        consecutive = 0
        last = frame
        if now >= next_sample:
            frames.append(small(frame))
            times.append(now - started)
            next_sample = now + 1.0 / sample_fps
    return frames, times, last, failures


def diagnose_one(owner, source, thresholds):
    url = source.get('rtsp') or ''
    reason = probe_stream(url)
    if reason:
        return _row(source, ['未检测'] * len(ITEMS), '', reason, failed=True)
    image = ''
    cap = None
    try:
        cap = open_capture(url)
        if not cap.isOpened():
            return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但解码连接建立失败', failed=True)
        frames, times, last, failures = sample_window(cap)
        if last is None:
            return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但没有收到可解码的有效画面', failed=True)
        image = snapshot(last)
        reference = load_reference(source['id'], url)
        reference_note = ''
        if reference is None and any(label in thresholds for label in ('视频遮挡', '偏色', '清晰度', '场景变化', '对比度')):
            reference, reference_note = ensure_reference(
                source['id'], url, frames, times, failures, reference=reference)
        results, details = analyze(frames, times, thresholds, reference=reference, read_errors=failures)
        notes = details['reason']
        if reference_note:
            notes = (notes + '；' if notes else '') + reference_note
        if failures:
            notes = (notes + '；' if notes else '') + '采样期间读取失败' + str(failures) + '次，建议检查视频连接'
        logging.getLogger(__name__).info('VQD measurement %s', json.dumps(
            {'equipment_id': source['id'], 'samples': details.get('samples'),
             'duration_seconds': details.get('duration_seconds'), 'reference_available': reference is not None,
             'checks': details.get('checks', {})}, ensure_ascii=False))
        return _row(source, [results[label] for label in LABELS], image, notes, failed=details.get('failed', False))
    except Exception as error:
        return _row(source, ['检测失败'] * len(ITEMS), image, '画质分析未完成（' + type(error).__name__ + '）')
    finally:
        if cap is not None:
            cap.release()

def diagnose(owner):
    thresholds = {('滚动条纹' if row['name'] == '滚动干扰' else row['name']):
                  (int(row['prewarn_threshold']), int(row['warn_threshold'])) for row in owner.data2}
    # Keep the original sequential scheduling and never change camera/proxy/task state.
    return [diagnose_one(owner, source, thresholds) for source in owner.data1]
