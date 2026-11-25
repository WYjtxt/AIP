"""Validate an event archive's own evidence; never select another recording.

Legacy files remain playable but are explicitly unverified. Only new schema-1
sidecars can establish a verified association with the selected alarm row.
No URL is fetched, and no media/database file is changed by this module.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
from urllib.parse import unquote, urlsplit

from service.count_replay_scope import receipt_timeline, replay_scope

OUTPUTS = Path('/data/AIGO/outputs')
LEGACY_OUTPUTS = Path('/data/AIGO/python/bingxing_model/results')
VOLUMES = Path('/data/AIGO/platform_storage/alarm-volumes')
CONFIG = Path('/data/AIGO/platform_storage/config/alarm-directory.json')
TIME_TOLERANCE = 1.1  # Alarm database stores timestamps to a whole second.


class ArchiveProblem(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _read_registry():
    try:
        if CONFIG.stat().st_size > 1024 * 1024:
            raise ValueError('oversize storage registry')
        doc = json.loads(CONFIG.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError):
        raise ArchiveProblem(503, '报警存储配置暂不可读取，请稍后重试')
    if doc.get('schema') != 1 or doc.get('version') != 'alarm-directory-v1':
        raise ArchiveProblem(503, '报警存储配置版本不正确，请联系管理员核查')
    return doc


def _child(root, suffix):
    parts = suffix.split('/')
    if any(p in ('', '.', '..') for p in parts) or '\\' in suffix:
        raise ArchiveProblem(409, '报警视频地址无效，请查看报警图片')
    candidate = root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        raise ArchiveProblem(409, '报警视频地址超出存储目录，请查看报警图片')
    return candidate


def _local_file(url, local_host):
    parsed = urlsplit(url)
    registry = _read_registry()
    origin = registry.get('public_origin', '')
    hosts = {str(local_host).lower(), 'localhost', '127.0.0.1', '::1'}
    # Docker deployments connect to the database over loopback, while
    # stored alarm URLs use the site's configured public address.
    target = os.environ.get('TARGET_IP', '').strip().lower()
    if target:
        hosts.add(target)
    if isinstance(origin, str):
        hosts.add((urlsplit(origin).hostname or '').lower())
    if parsed.netloc and (parsed.hostname or '').lower() not in hosts:
        return None  # Preserve external historical archives as unverified.
    if parsed.scheme and parsed.scheme not in ('http', 'https'):
        raise ArchiveProblem(409, '报警视频地址格式不受支持，请查看报警图片')
    try:
        path = unquote(parsed.path, errors='strict')
    except (UnicodeError, ValueError):
        raise ArchiveProblem(409, '报警视频地址无效，请查看报警图片')
    if any(ord(c) < 32 or ord(c) == 127 for c in path) or re.search(r'%[0-9a-f]{2}', path, re.I):
        raise ArchiveProblem(409, '报警视频地址无效，请查看报警图片')
    for prefix in ('/media/alarm-storage/', '/alarm-storage/'):
        if path.startswith(prefix):
            volume_id, sep, suffix = path[len(prefix):].partition('/')
            volumes = registry.get('volumes', [])
            if not sep or not re.fullmatch(r'[a-f0-9]{20}', volume_id):
                raise ArchiveProblem(409, '报警视频存储标识不正确，请查看报警图片')
            volume = next((v for v in volumes if isinstance(v, dict) and v.get('id') == volume_id), None)
            expected = VOLUMES / volume_id
            if volume is None or volume.get('root') != str(expected):
                raise ArchiveProblem(410, '该报警视频所在存储目录已不可用，可查看报警图片')
            return _child(expected, suffix)
    routes = (('/media/alarms/', OUTPUTS), ('/alarms/', OUTPUTS),
              ('/data/AIGO/outputs/', OUTPUTS),
              ('/data/AIGO/python/bingxing_model/results/', LEGACY_OUTPUTS))
    for prefix, root in routes:
        if path.startswith(prefix):
            return _child(root, path[len(prefix):])
    return None


def _timestamp(value):
    if value is None:
        return None
    if hasattr(value, 'timestamp'):
        value = value.timestamp()
    elif isinstance(value, str):
        from datetime import datetime
        value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S').timestamp()
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('invalid timestamp')
    return float(value)


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _image_urls(result):
    images = getattr(result, 'carousel_images_list', None)
    try:
        if isinstance(images, str):
            images = ast.literal_eval(images)
        if not isinstance(images, list):
            return []
        return [u for u in images if isinstance(u, str) and u.strip()]
    except (SyntaxError, ValueError, TypeError):
        return []


def _image_stems(result):
    return {Path(unquote(urlsplit(u).path)).stem for u in _image_urls(result)}


def _count_timeline(result, path):
    if path is None:
        return None
    receipt_path = Path(str(path) + '.count-coverage.json')
    try:
        info = receipt_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 128 * 1024:
            return None
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if (not isinstance(receipt, dict) or receipt.get('schema') != 1
                or receipt.get('kind') != 'recording-coverage' or receipt.get('status') != 'ready'):
            return None
        names = [Path(unquote(urlsplit(url).path)).name for url in _image_urls(result)]
        return receipt_timeline(result, path, receipt, names)
    except (OSError, ValueError, TypeError):
        return None


def _with_count_scope(response, result, path=None, coverage=None):
    scope = replay_scope(result, path, coverage)
    if scope is not None:
        response['count_replay'] = scope
    return response


def inspect_archive(result, url, local_host):
    """Return playback state. An unavailable archive never requests re-analysis."""
    try:
        path = _local_file(url, local_host)
        if path is None:
            return _with_count_scope(
                {'code': 200, 'media_integrity': 'legacy_unverified', 'media_status': 'legacy',
                 'msg': '历史存档（未提供事件关联校验信息）'}, result)
        sidecar = Path(str(path) + '.event.json')
        if sidecar.exists():
            if sidecar.stat().st_size > 128 * 1024:
                raise ArchiveProblem(409, '报警视频关联信息异常，可查看报警图片')
            doc = json.loads(sidecar.read_text(encoding='utf-8'))
            if not isinstance(doc, dict) or doc.get('schema') != 1:
                raise ArchiveProblem(409, '报警视频关联信息版本不正确，可查看报警图片')
            status = doc.get('status')
            if status == 'pending':
                return {'code': 202, 'msg': '该报警事件视频正在保存，请稍候', 'media_status': 'pending'}
            if status == 'failed':
                raise ArchiveProblem(410, '该报警视频未完整覆盖报警时刻或保存失败，可查看报警图片')
            if status != 'ready':
                raise ArchiveProblem(409, '报警视频关联状态异常，可查看报警图片')
            requested, actual, video = doc['requested'], doc['actual'], doc['video']
            if doc.get('conf_name') != getattr(result, 'conf_name', None):
                raise ArchiveProblem(409, '该视频与所选报警任务不一致，可查看报警图片')
            end = _timestamp(requested['end'])
            start = _timestamp(requested['start'])
            evidence = _timestamp(requested['evidence_ts'])
            recorded_end = _timestamp(getattr(result, 'res_time', None))
            if recorded_end is None or abs(recorded_end - end) > TIME_TOLERANCE or start > end:
                raise ArchiveProblem(409, '该视频与所选报警时间不一致，可查看报警图片')
            if getattr(result, 'algorithm_name', None) == '人数统计':
                recorded_start = _timestamp(getattr(result, 'result_count_time', None))
                if recorded_start is not None and abs(recorded_start - start) > TIME_TOLERANCE:
                    raise ArchiveProblem(409, '该视频与所选计数事件时段不一致，可查看报警图片')
            source_start = _timestamp(actual.get('source_start', actual['start']))
            source_end = _timestamp(actual.get('source_end', actual['end']))
            fps = float(actual['fps'])
            if not math.isfinite(fps) or fps <= 0 or int(actual['frames']) < 2:
                raise ValueError('invalid frame metadata')
            frame_tolerance = max(.15, 2.0 / fps)
            if (evidence is None or source_start is None or source_end is None or
                    source_start > start + frame_tolerance or source_end < end - frame_tolerance or
                    not source_start - frame_tolerance <= evidence <= source_end + frame_tolerance):
                raise ArchiveProblem(410, '该视频未覆盖原报警画面，不能作为该报警回放，可查看报警图片')
            anchors, matches = requested.get('evidence_frames'), actual.get('evidence_frames')
            if not isinstance(anchors, list) or not anchors or not isinstance(matches, list) or len(anchors) != len(matches):
                raise ArchiveProblem(409, '报警图片与视频帧关联信息不完整，可查看报警图片')
            if getattr(result, 'algorithm_name', None) == '人数统计' and len(_image_urls(result)) != len(anchors):
                raise ArchiveProblem(409, '报警图片数量与视频帧关联信息不一致，可查看报警图片')
            if getattr(result, 'algorithm_name', None) == '人数统计':
                session_id = doc.get('event_id')
                parents = [Path(unquote(urlsplit(image).path)).parent.name for image in _image_urls(result)]
                if (not isinstance(session_id, str) or not session_id.startswith('session_') or
                        not parents or any(parent != session_id for parent in parents)):
                    raise ArchiveProblem(409, '该视频与报警图片的计数会话标识不一致，可查看报警图片')
            for anchor, match in zip(anchors, matches):
                stamp, matched = _timestamp(anchor['timestamp']), _timestamp(match['timestamp'])
                source = _timestamp(match['source_ts'])
                offset = float(match['offset_seconds'])
                error = float(match['source_error_seconds'])
                if (stamp is None or matched is None or source is None or
                        stamp != matched or anchor.get('frame_key') != match.get('frame_key') or
                        not math.isfinite(offset + error) or offset < 0 or error < 0 or
                        abs(source - stamp) > frame_tolerance or
                        abs(abs(source - stamp) - error) > .00001):
                    raise ArchiveProblem(410, '该视频缺少原报警图片对应帧，可查看报警图片')
            if getattr(result, 'algorithm_name', None) in ('人员尾随', '违规跨越'):
                event_id = doc.get('event_id')
                if not event_id or event_id not in _image_stems(result):
                    raise ArchiveProblem(409, '该视频与报警图片的事件标识不一致，可查看报警图片')
            if Path(video['path']).resolve() != path.resolve():
                raise ArchiveProblem(409, '报警视频文件与事件关联信息不一致，可查看报警图片')
            info = path.stat()
            if info.st_size <= 0 or video['size'] != info.st_size or video['sha256'] != _digest(path):
                raise ArchiveProblem(409, '报警视频文件完整性校验未通过，可查看报警图片')
            return _with_count_scope(
                {'code': 200, 'media_integrity': 'verified', 'media_status': 'ready',
                    'event_id': doc['event_id'], 'evidence_frames': matches,
                    'alarm_image_offset_seconds': matches[0]['offset_seconds'],
                    'evidence_offset_seconds': actual.get('evidence_offset_seconds'),
                 'msg': '事件存档已就绪'}, result, path, 'full')
        try:
            info = path.stat()
        except FileNotFoundError:
            raise ArchiveProblem(410, '该报警的存档视频不存在或已清理，可查看报警图片')
        if info.st_size <= 0:
            if time.time() - info.st_mtime < 30:
                return {'code': 202, 'msg': '该报警事件视频正在保存，请稍候', 'media_status': 'pending'}
            raise ArchiveProblem(410, '该报警存档视频保存未完成，可查看报警图片')
        coverage = _count_timeline(result, path)
        return _with_count_scope(
            {'code': 200, 'media_integrity': 'legacy_unverified', 'media_status': 'legacy',
             'msg': '历史存档（未提供事件关联校验信息）'}, result, path, coverage)
    except ArchiveProblem as exc:
        return {'code': exc.code, 'msg': str(exc), 'media_status': 'unavailable'}
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return {'code': 409, 'msg': '报警视频关联信息校验未通过，可查看报警图片', 'media_status': 'unavailable'}
