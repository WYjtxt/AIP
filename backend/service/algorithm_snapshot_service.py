"""Still-image fallback for a verified recorder channel, without changing inputs."""
from service.algorithm_stream_source import infer_stream_type, normalize_stream_type, select_stream_url


def _verified_direct_url(equipment_id, choice):
    from data.exts import db
    from model.equipment import Equipment
    from model.extra import Zlk_data
    from service.preview_source_service import _registered_direct_source

    selected = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
    if (selected is None or selected.equipment_type != '录像机' or not selected.parent_id
            or selected.user_status not in ('1', None)):
        return None
    parent = db.session.query(Equipment).filter(Equipment.id == selected.parent_id).first()
    if parent is None or parent.user_status not in ('1', None):
        return None
    # Legacy snapshots must retain the profile of the actual saved source.
    # A relay URL alone never identifies whether it contains main or sub video.
    if choice is None:
        binding = (db.session.query(Zlk_data).filter(Zlk_data.id == selected.zlk_dat_id).first()
                   if selected.zlk_dat_id else None)
        if binding:
            if str(binding.equipment_id) != str(selected.id):
                return None
            choice = infer_stream_type(binding.cameras_rtsp)
            if choice is None:
                return None
    direct = _registered_direct_source(selected, parent, timeout=(0.8, 1.5))
    return select_stream_url(direct, choice) if choice else direct


def capture_snapshot_with_recorder_fallback(equipment_id, stream_type, rtsp, mp4,
                                            snapshot_key, img_type, img_resolution, capture):
    choice = normalize_stream_type(stream_type)
    if rtsp or mp4:
        try:
            result = capture(rtsp, mp4, snapshot_key, img_type, img_resolution)
        except Exception:
            result = {'code': 400, 'msg': '无法获取到图像，请检查视频来源和连接状态'}
    else:
        result = {'code': 400, 'msg': '所选摄像机通道无法获取视频流，请检查设备在线状态和码流配置'}
    if not isinstance(result, dict) or result.get('code') == 200:
        return result
    try:
        direct = _verified_direct_url(equipment_id, choice)
        if not direct or direct == rtsp:
            return result
        # The same requested main/sub profile is retained. Never substitute a
        # lower-resolution profile or a still image from another camera/cache.
        fallback = capture(direct, None, snapshot_key, 1, img_resolution)
        if isinstance(fallback, dict) and fallback.get('code') == 200:
            fallback['snapshot_source_mode'] = 'camera-direct'
            return fallback
    except Exception:
        # HTTP/device errors can contain authenticated source URIs. Preserve the
        # safe original response and never return or print those diagnostics.
        pass
    return result
