# hik-preview-status-v307
def _hik_online_by_area(rows):
    """Resolve each configured platform once; never expose credentials to clients."""
    from model.equipment import Hik_security_platform_info, Hik_security_platform_up_area
    from tool.hik_gateway import hik_online_states
    ids = {row.hik_area for row in rows if getattr(row, 'equipment_type', None) == '安防平台'
           and getattr(row, 'parent_vendor', None) == '海康' and getattr(row, 'hik_area', None)}
    if not ids:
        return {}
    areas = db.session.query(Hik_security_platform_up_area).filter(Hik_security_platform_up_area.id.in_(ids)).all()
    platform_ids = {area.hik_info_id for area in areas if area.hik_info_id}
    platforms = db.session.query(Hik_security_platform_info).filter(Hik_security_platform_info.id.in_(platform_ids)).all() if platform_ids else []
    states = {}
    for platform in platforms:
        config = {key: getattr(platform, key, None) for key in ('hik_host', 'hik_port', 'hik_appKey', 'hik_appSecret', 'hik_artemis')}
        try:
            states[platform.id] = hik_online_states(config)
        except ValueError:
            states[platform.id] = None
    return {area.id: states.get(area.hik_info_id) for area in areas}


# native-hik-platform-preview-v1
# native-onvif-bound-preview-v1
"""List enabled camera channels independently of their media bindings.

Listing is read only; recorder channels may be prepared explicitly on playback.
"""
import logging
import os

import requests
from flask import request
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from config.zlk_conf import ZLK_HOST, ZLK_PORT, ZLK_SECRET
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from service.media_stream_index import index_media_streams, media_stream_rows
from service.preview_urls import media_base_url, playback_urls

logger = logging.getLogger(__name__)


def _base_url():
    return media_base_url(ZLK_HOST, ZLK_PORT, request.host,
                          os.environ.get('ZLK_PUBLIC_BASE_URL'))


def _media_snapshot(app=None, stream=None):
    params = {'secret': ZLK_SECRET}
    if app:
        params['app'] = app
    if stream:
        params['stream'] = stream
    try:
        internal_base = media_base_url(ZLK_HOST, ZLK_PORT)
        response = requests.get(internal_base + '/index/api/getMediaList',
                                params=params, timeout=(2, 4))
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 0:
            return None
        return result.get('data') or []
    except (requests.RequestException, ValueError):
        # Do not log URLs with the server API secret.
        logger.warning('视频预览无法获取流媒体状态')
        return None


def _serialize(row, base, matching, online_by_area=None):
    name = row.equipment_name or '监控点 {}'.format(row.id)
    app = row.zlk_app or 'openUrl'
    # MP4 can register with audio before the source's first video keyframe.
    # An online audio-only muxer is not a browser-ready camera picture.
    mp4_rows = [item for item in matching or [] if item.get('schema') == 'fmp4']
    tracks = [track for item in mp4_rows for track in item.get('tracks') or []]
    if not tracks:
        tracks = next((item.get('tracks') or [] for item in matching or []
                       if item.get('tracks')), [])
    video_track = next((track for track in tracks if track.get('codec_type') == 0), {})
    video_ready = None
    if any(item.get('tracks') for item in mp4_rows):
        video_ready = any(track.get('codec_type') == 0 and track.get('ready') is not False
                          for item in mp4_rows for track in item.get('tracks') or [])
    codec = video_track.get('codec_id_name') or row.equipment_codetype or ''
    keyframe_interval = video_track.get('gop_interval_ms')
    if (isinstance(keyframe_interval, bool)
            or not isinstance(keyframe_interval, (int, float))
            or not 0 < keyframe_interval < 86400000):
        keyframe_interval = None
    urls = playback_urls(base, app, row.zlk_live) if row.zlk_live else {}
    mp4_enabled = bool(row.zlk_mp4) or any(
        item.get('schema') == 'fmp4' for item in matching or [])
    reason = ''
    recorder = bool(getattr(row, 'parent_id', None)
                       and getattr(row, 'equipment_type', '') in ('录像机', '特殊摄像头', '视频中心存储')
                       and getattr(row, 'parent_vendor', '') in ('海康', '宇视', '大华'))
    recorder_enabled = getattr(row, 'parent_enabled', None) in (None, '1')
    can_prepare = bool(recorder and recorder_enabled
                       and (getattr(row, 'equipment_aisles', None) or (
                           getattr(row, 'parent_vendor', '') == '大华'
                           and getattr(row, 'source_onvif_url', None)
                           and str(getattr(row, 'binding_owner', None)) == str(row.id))))
    hik_platform = bool(getattr(row, 'equipment_type', None) == '安防平台'
                        and getattr(row, 'parent_vendor', None) == '海康'
                        and getattr(row, 'parent_id', None) and getattr(row, 'hik_area', None)
                        and getattr(row, 'hik_index', None)
                        and (not getattr(row, 'source_binding_id', None) or (
                            str(getattr(row, 'binding_owner', None)) == str(row.id)
                            and app == 'openUrl' and row.zlk_live == 'preview_hik_' + str(row.id))))
    source_online = ((online_by_area or {}).get(getattr(row, 'hik_area', None)) or {}).get(getattr(row, 'hik_index', None)) if hik_platform else None
    if recorder:
        reported = getattr(row, 'source_online', None)
        source_online = str(reported) == '1' if str(reported) in ('0', '1') else None
        if matching and row.zlk_mp4 and not mp4_rows:
            video_ready = False
    can_prepare = can_prepare or (hik_platform and source_online is not False)
    needs_prepare = can_prepare and (not row.zlk_live
                                     or (matching is not None and not matching))
    if not row.zlk_live:
        reason = '点击播放时建立通道转发' if needs_prepare else '该设备尚未配置流媒体转发'
    elif matching is not None and not matching:
        reason = '点击播放时恢复该通道转发' if needs_prepare else '转发流当前不在线，请检查流媒体管理'
    elif not mp4_enabled:
        reason = '该转发流未启用 MP4 输出，请在流媒体管理中开启'
    if hik_platform and source_online is False:
        reason = '设备离线，请检查摄像机供电与网络'
    if recorder and not recorder_enabled:
        reason = '录像机已禁用'
    return {
        'id': row.id, 'name': name, 'parent_id': row.parent_id,
        'group': row.parent_name or '独立监控点',
        'channel': getattr(row, 'equipment_aisles', None),
        'source_mode': 'hik-platform' if hik_platform else 'camera-direct' if str(row.zlk_live or '').startswith('preview_ipc_') else 'recorder' if row.parent_id else 'camera',
        'codec': codec, 'online': source_online if hik_platform or recorder else None if matching is None else bool(matching),
        'source_online': source_online, 'media_live': None if matching is None else bool(matching),
        'video_ready': video_ready,
        'keyframe_interval_ms': keyframe_interval,
        'available': needs_prepare or not bool(reason), 'reason': reason,
        'needs_prepare': needs_prepare,
        'play_url': urls.get('mp4') if mp4_enabled else None,
        'urls': {'mp4': urls.get('mp4') if mp4_enabled else None},
    }


def _query():
    parent = aliased(Equipment)
    # Select only display/playback fields; camera credentials and RTSP URLs stay server-side.
    return db.session.query(
        Equipment.id, Equipment.equipment_name, Equipment.parent_id,
        Equipment.equipment_type, Equipment.equipment_aisles,
        Equipment.Hik_id.label('hik_area'), Equipment.Hik_indexCode.label('hik_index'),
        Equipment.zlk_dat_id.label('source_binding_id'),
        Equipment.online.label('source_online'), parent.manufacturer_type.label('parent_vendor'),
        parent.user_status.label('parent_enabled'),
        Equipment.Onvif_rtsp_url.label('source_onvif_url'), Zlk_data.equipment_id.label('binding_owner'),
        Equipment.equipment_codetype, parent.equipment_name.label('parent_name'),
        Zlk_data.zlk_app, Zlk_data.zlk_live, Zlk_data.zlk_mp4,
    ).outerjoin(Zlk_data, Equipment.zlk_dat_id == Zlk_data.id).outerjoin(
        parent, Equipment.parent_id == parent.id
    ).filter(or_(Equipment.user_status == '1', Equipment.user_status.is_(None)),
             or_(Equipment.parent_id.isnot(None),
                 Equipment.equipment_type.in_(['摄像头', '特殊摄像头', '浙江双视热成像']),
                 Equipment.zlk_dat_id.isnot(None)))


def list_preview_devices():
    try:
        rows = _query().order_by(Equipment.parent_id, Equipment.equipment_aisles, Equipment.id).all()
        media = index_media_streams(_media_snapshot())
        online_by_area = _hik_online_by_area(rows)
        base = _base_url()
        return {'code': 200, 'msg': '获取成功',
                'data': [_serialize(row, base, media_stream_rows(media, row.zlk_app or 'openUrl', row.zlk_live),
                                    online_by_area) for row in rows],
                'media_status_known': media is not None}
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    except Exception:
        logger.exception('读取视频预览监控点失败')
        return {'code': 500, 'msg': '读取监控点失败，请检查后端日志'}


def get_preview_stream(equipment_id):
    try:
        if isinstance(equipment_id, bool):
            raise ValueError()
        equipment_id = int(equipment_id)
        if equipment_id < 1:
            raise ValueError()
    except (TypeError, ValueError):
        return {'code': 400, 'msg': '设备ID必须为正整数'}
    try:
        row = _query().filter(Equipment.id == equipment_id).first()
        if not row:
            return {'code': 404, 'msg': '该设备不存在、已禁用或未关联流媒体转发'}
        snapshot = _media_snapshot(row.zlk_app, row.zlk_live) if row.zlk_live else []
        matching = media_stream_rows(index_media_streams(snapshot), row.zlk_app or 'openUrl', row.zlk_live)
        data = _serialize(row, _base_url(), matching, _hik_online_by_area([row]))
        if data['needs_prepare']:
            message = ('请先建立该安防平台监控点的转发' if data['source_mode'] == 'hik-platform'
                       else '请先建立该录像机通道的转发')
            return {'code': 409, 'msg': message, 'data': data}
        if not data['available']:
            return {'code': 409, 'msg': data['reason'], 'data': data}
        if data['video_ready'] is False:
            return {'code': 202, 'msg': '转发流尚未提供视频轨，正在等待关键帧',
                    'retry_after_ms': 2000, 'data': data}
        # Keep the legacy flv_url field: the existing interface used it for fMP4.
        return {'code': 200, 'msg': '获取成功', 'data': data,
                'play_url': data['play_url'], 'flv_url': data['play_url']}
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    except Exception:
        logger.exception('读取视频预览播放地址失败')
        return {'code': 500, 'msg': '读取播放地址失败，请检查后端日志'}
