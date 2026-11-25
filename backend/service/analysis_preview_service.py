"""Read existing algorithm output streams without controlling inference tasks.

The deployed analysis pipeline publishes one RTMP output per equipment under
``stream/{equipment_id}``. On 2026-10-13 the server reported these outputs as
originType=1 / rtmp_push (H264/AAC), while original camera proxies were
originType=4 / pull under openUrl. Accept native RTSP publishers as well;
missing/unknown origin metadata remains compatible with older media servers.
Multiple algorithms may share an output; their configuration and callback
ownership remain independent of browser playback.
"""
import logging

from sqlalchemy import or_
from sqlalchemy.orm import aliased

from data.exts import db
from model.algorithm import Algorithm_config, Algorithm_library
from model.equipment import Equipment
from service.preview_service import _base_url, _media_snapshot
from service.preview_urls import playback_urls


logger = logging.getLogger(__name__)
ANALYSIS_APP = 'stream'


def _equipment_query():
    parent = aliased(Equipment)
    # Source URLs and credentials are never selected or serialized.
    return db.session.query(
        Equipment.id, Equipment.equipment_name, Equipment.parent_id,
        parent.equipment_name.label('parent_name'),
    ).outerjoin(parent, Equipment.parent_id == parent.id).filter(
        or_(Equipment.user_status == '1', Equipment.user_status.is_(None)))


def _task_query():
    return db.session.query(
        Algorithm_config.id, Algorithm_config.Equipment_id,
        Algorithm_config.conf_name, Algorithm_config.status,
        Algorithm_config.model_status,
        Algorithm_library.algorithm_name,
        Algorithm_library.analysis_type, Algorithm_library.algorithm_version,
    ).outerjoin(Algorithm_library,
                Algorithm_config.Algorithm_library_id == Algorithm_library.id)


def _task_summaries(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row.Equipment_id, []).append({
            'id': row.id, 'name': row.conf_name or '算法任务 {}'.format(row.id),
            'algorithm': row.analysis_type or row.algorithm_name or '',
            'algorithm_version': row.algorithm_version or '',
            'status': row.status, 'model_status': row.model_status,
        })
    return grouped


def _matching_media(snapshot, equipment_id):
    if snapshot is None:
        return None
    # Canonical decimal IDs avoid matching another application's source stream
    # or names such as 042, 42-preview, and UUIDs.
    stream = str(equipment_id)
    return [item for item in snapshot
            if item.get('app') == ANALYSIS_APP and item.get('stream') == stream]


def _unexpected_origin(item):
    origin = item.get('originType')
    label = str(item.get('originTypeStr') or '').strip().lower()
    # 0 / none mean unknown. The current deployment's algorithm publishing
    # contract is RTMP/RTSP push; an explicitly different origin cannot prove that
    # this device's stream is analysis output, even if its name looks correct.
    return ((origin is not None and str(origin) not in ('', '0', '1', '2'))
            or label not in ('', 'unknown', 'none', 'rtmp_push', 'rtsp_push'))


def analysis_output_state(matching):
    """Only a published video track confirms analysis output for an equipment ID."""
    if matching is None:
        return 'unknown'
    if not matching or any(_unexpected_origin(item) for item in matching):
        return 'offline'
    for item in matching:
        for track in item.get('tracks') or []:
            if str(track.get('codec_type')) == '0' and track.get('ready') is not False:
                return 'online'
    return 'no_video'


def _serialize(row, tasks, base, snapshot):
    matching = _matching_media(snapshot, row.id)
    state = analysis_output_state(matching)
    tracks = next((item.get('tracks') or [] for item in matching or []
                   if item.get('tracks')), [])
    video_track = next((track for track in tracks
                        if track.get('codec_type') == 0), {})
    # The analysis encoder may differ from the camera's source encoder.
    codec = video_track.get('codec_id_name') or ''
    interval = video_track.get('gop_interval_ms')
    if (isinstance(interval, bool) or not isinstance(interval, (int, float))
            or not 0 < interval < 86400000):
        interval = None
    wrong_origin = any(_unexpected_origin(item) for item in matching or [])
    mp4_enabled = (not wrong_origin and any(
        item.get('schema') == 'fmp4' for item in matching or []))
    if matching is None:
        reason = '无法获取分析推流状态，请稍后刷新'
    elif not matching:
        reason = ('分析输出当前不在线，请检查算法任务和推流状态'
                  if tasks else '该监控点尚无分析输出，请先配置算法任务')
    elif wrong_origin:
        reason = '该流为拉流、代理或其他来源，不能作为算法分析输出'
    elif state == 'no_video':
        reason = '分析推流尚未注册可用的视频轨'
    elif not mp4_enabled:
        reason = '分析输出未启用 fMP4，暂时无法在浏览器播放'
    else:
        reason = ''
    url = (playback_urls(base, ANALYSIS_APP, str(row.id))['mp4']
           if not reason else None)
    return {
        'id': row.id, 'name': row.equipment_name or '监控点 {}'.format(row.id),
        'parent_id': row.parent_id,
        'group': row.parent_name or '独立监控点',
        'codec': codec, 'online': None if state == 'unknown' else state == 'online',
        'available': not bool(reason), 'reason': reason,
        'play_url': url, 'urls': {'mp4': url},
        'keyframe_interval_ms': interval, 'tasks': tasks,
    }


def list_analysis_devices():
    try:
        rows = _equipment_query().order_by(Equipment.parent_id, Equipment.id).all()
        tasks = _task_summaries(_task_query().order_by(Algorithm_config.id).all())
        snapshot = _media_snapshot(app=ANALYSIS_APP)
        base = _base_url()
        data = [_serialize(row, tasks.get(row.id, []), base, snapshot)
                for row in rows
                if tasks.get(row.id) or _matching_media(snapshot, row.id)]
        return {'code': 200, 'msg': '获取成功', 'data': data,
                'media_status_known': snapshot is not None}
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    except Exception:
        logger.exception('读取视频分析监控点失败')
        return {'code': 500, 'msg': '读取视频分析监控点失败，请检查后端日志'}


def _equipment_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError()
    if isinstance(value, str):
        value = value.strip()
        if not value or not value.isascii() or not value.isdigit():
            raise ValueError()
    value = int(value)
    if not 0 < value <= 2147483647:
        raise ValueError()
    return value


def get_analysis_stream(equipment_id):
    try:
        equipment_id = _equipment_id(equipment_id)
    except (TypeError, ValueError):
        return {'code': 400, 'msg': '设备ID必须为正整数'}
    try:
        row = _equipment_query().filter(Equipment.id == equipment_id).first()
        if not row:
            return {'code': 404, 'msg': '该设备不存在或已禁用'}
        tasks = _task_summaries(_task_query().filter(
            Algorithm_config.Equipment_id == equipment_id).order_by(
                Algorithm_config.id).all()).get(equipment_id, [])
        data = _serialize(row, tasks, _base_url(),
                          _media_snapshot(app=ANALYSIS_APP, stream=str(equipment_id)))
        if not data['available']:
            return {'code': 409, 'msg': data['reason'], 'data': data}
        return {'code': 200, 'msg': '获取成功', 'data': data,
                'play_url': data['play_url'], 'flv_url': data['play_url']}
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    except Exception:
        logger.exception('读取视频分析播放地址失败')
        return {'code': 500, 'msg': '读取视频分析播放地址失败，请检查后端日志'}
