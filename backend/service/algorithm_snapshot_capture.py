"""Capture a configuration still with one bounded decoder per registered source."""

import logging
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.parse import urlsplit

import cv2

from common.camera_snapshots import SnapshotWriteError, persist_snapshot


_LOG = logging.getLogger(__name__)
_RUNTIME = Path('/data/AIGO/platform_start/runtime/bin/ffmpeg')
_IDENTITY = re.compile(r'\d+(?:_(?:main|sub))?')
_RESOLUTION = re.compile(r'(\d{1,4})x(\d{1,4})')
_CAPTURE_TIMEOUT = 5.0
_FRAME_LIMIT = 24 * 1024 * 1024


def _dimensions(value):
    if value in ('', None):
        return None
    match = _RESOLUTION.fullmatch(str(value))
    if not match:
        raise ValueError('截图分辨率无效')
    size = tuple(map(int, match.groups()))
    if not all(0 < side <= 8192 for side in size) or size[0] * size[1] > 33554432:
        raise ValueError('截图分辨率超出支持范围')
    return size


def _read_image(path):
    try:
        if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= _FRAME_LIMIT:
            return None
        frame = cv2.imread(str(path))
        return frame if frame is not None and frame.size else None
    except (OSError, cv2.error):
        return None


def _command(ffmpeg, source, output):
    # Use only expected video protocols. Source URLs are resolved server-side.
    try:
        uri = urlsplit(source)
        scheme = uri.scheme
        if not uri.hostname or scheme not in ('rtsp', 'rtsps', 'http', 'https'):
            return None
    except (TypeError, ValueError):
        return None
    command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-threads', '1', '-analyzeduration', '1500000', '-probesize', '1000000']
    if scheme in ('rtsp', 'rtsps'):
        command += ['-rtsp_transport', 'tcp']
    return command + ['-i', source, '-map', '0:v:0', '-frames:v', '1', '-an', '-sn', '-dn',
                      '-c:v', 'mjpeg', '-q:v', '3', '-threads', '1', '-f', 'image2', str(output)]


def _first_frame(sources, timeout=_CAPTURE_TIMEOUT):
    ffmpeg = _RUNTIME if _RUNTIME.is_file() else shutil.which('ffmpeg')
    if not ffmpeg:
        return None
    deadline = monotonic() + timeout
    with TemporaryDirectory(prefix='aiplatform-snapshot-') as directory:
        pending = {}
        try:
            for index, source in enumerate(dict.fromkeys(filter(None, sources))):
                output = Path(directory) / (str(index) + '.jpg')
                command = _command(ffmpeg, source, output)
                if command:
                    try:
                        pending[subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                 stderr=subprocess.DEVNULL)] = output
                    except OSError:
                        _LOG.warning('Configuration snapshot decoder could not start')
            while pending:
                for process, output in tuple(pending.items()):
                    result = process.poll()
                    if result is None:
                        continue
                    del pending[process]
                    if result == 0:
                        frame = _read_image(output)
                        if frame is not None:
                            return frame
                remaining = deadline - monotonic()
                if not pending or remaining <= 0:
                    return None
                sleep(min(0.04, remaining))
        finally:
            for process in pending:
                if process.poll() is None:
                    process.kill()
            for process in pending:
                process.wait()


def _cache_snapshot(identity, path, resolution):
    # Keep the legacy Redis keys available to other pages. The atomically written
    # JPEG remains usable when the cache is briefly unavailable.
    import redis
    from config import configs

    try:
        client = redis.Redis(host=configs.Redis_ip, port=configs.Redis_port, password=configs.Redis_password,
                             socket_connect_timeout=0.5, socket_timeout=0.5)
        try:
            client.mset({'em_' + identity: path, 'img_resolution_' + identity: resolution})
        finally:
            client.connection_pool.disconnect()
    except (redis.RedisError, OSError):
        _LOG.warning('Configuration snapshot cache unavailable')


def capture_config_snapshot(rtsp, mp4, snapshot_key, img_type, img_resolution):
    from config.configs import FILE_SAVE_PATH

    identity = str(snapshot_key)
    if not _IDENTITY.fullmatch(identity):
        return {'code': 400, 'msg': '截图设备标识无效'}
    try:
        size = _dimensions(img_resolution)
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    filename = 'em_' + identity + '.jpg'
    cached = _read_image(Path(FILE_SAVE_PATH) / filename) if img_type != 1 else None
    if cached is not None and (not size or size == (cached.shape[1], cached.shape[0])):
        return {'code': 200, 'msg': '/static/' + filename,
                'img_resolution': '{}x{}'.format(cached.shape[1], cached.shape[0])}
    frame = _first_frame((rtsp, mp4))
    if frame is None:
        return {'code': 400, 'msg': '未能及时获取设备画面，请检查所选码流和视频连接后重试'}
    try:
        if size and size != (frame.shape[1], frame.shape[0]):
            frame = cv2.resize(frame, size)
        path = persist_snapshot(frame, snapshot_key, FILE_SAVE_PATH)
    except (SnapshotWriteError, cv2.error):
        return {'code': 500, 'msg': '截图保存失败，请检查平台截图目录权限和可用空间后重试'}
    resolution = '{}x{}'.format(frame.shape[1], frame.shape[0])
    _cache_snapshot(identity, path, resolution)
    return {'code': 200, 'msg': '/static/' + filename, 'img_resolution': resolution}
