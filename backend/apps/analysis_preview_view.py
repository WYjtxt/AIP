"""Authenticated, read-only browser playback of existing algorithm output."""
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from data.exts import db
from model.admin import User
from service.analysis_preview_service import get_analysis_stream, list_analysis_devices


analysis_preview_view = Blueprint('analysis_preview', __name__)


def _enabled_user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        if not isinstance(identity, str) or not identity:
            return jsonify({'code': 401, 'msg': '登录用户无效，请重新登录'}), 401
        user = db.session.query(User.id, User.user_status).filter(
            User.username == identity).first()
        if not user or user.user_status != '1':
            return jsonify({'code': 401, 'msg': '用户不存在或账号已禁用，请重新登录'}), 401
        return fn(*args, **kwargs)
    return wrapper


@analysis_preview_view.route('/devices', methods=['GET'])
@jwt_required()
@_enabled_user_required
def devices():
    return jsonify(list_analysis_devices())


@analysis_preview_view.route('/play', methods=['GET'])
@jwt_required()
@_enabled_user_required
def play():
    return jsonify(get_analysis_stream(request.args.get('em_id')))
