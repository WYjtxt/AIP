"""Explicitly confirmed per-device references, guarded by existing menu grants."""
from flask import g, jsonify, request

from common.platform_access import has_menu_permission
from data.exts import db
from data.vqd_source_data import _source
from model.equipment import Equipment
from model.extra import Zlk_data
from service.vqd_diagnosis import open_capture
from service.vqd_quality import save_reference


def can_set_reference():
    user = getattr(g, 'platform_user', None)
    return bool(user and has_menu_permission(user.id, 'spzlzd', 'u'))


def set_reference():
    if not can_set_reference():
        return jsonify({'code': 403, 'msg': '当前账号没有诊断配置修改权限'}), 403
    payload = request.get_json(silent=True)
    if (not isinstance(payload, dict) or type(payload.get('equipment_id')) is not int
            or payload.get('confirmed_normal') is not True):
        return jsonify({'code': 400, 'msg': '请确认当前监控画面正常后设置基准'}), 400
    pair = db.session.query(Equipment, Zlk_data).outerjoin(
        Zlk_data, Zlk_data.id == Equipment.zlk_dat_id).filter(Equipment.id == payload['equipment_id']).first()
    if pair is None:
        return jsonify({'code': 404, 'msg': '监控点不存在'}), 404
    url = _source(*pair)
    if not url:
        return jsonify({'code': 400, 'msg': '监控点没有可用视频源'}), 400
    cap = None
    try:
        # Capture only the registered current source. Never accept a client URL or image path.
        cap = open_capture(url)
        if not cap.isOpened():
            raise RuntimeError('CaptureUnavailable')
        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            raise RuntimeError('NoVideoFrame')
        save_reference(pair[0].id, url, frame)
        return jsonify({'code': 200, 'msg': '正常画面基准已更新，下次诊断生效'})
    except Exception:
        return jsonify({'code': 400, 'msg': '获取正常画面失败，原基准已保留，请检查当前视频'}), 400
    finally:
        if cap is not None:
            cap.release()
