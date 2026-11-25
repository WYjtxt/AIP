# native-role-policy-v1
"""Administrator storage controls using the existing active-user and role policy."""
from flask import Blueprint, jsonify, request
from functools import wraps
from flask_jwt_extended import get_jwt_identity, jwt_required

from data.exts import db
from model.admin import Permission, UserPermission, User
from service.alarm_retention_service import cleanup_alarm_data, retention_settings

storage_retention_view = Blueprint('storage_retention', __name__)


def _can_edit_settings():
    from flask import g
    from common.platform_access import has_menu_permission
    return has_menu_permission(g.platform_user.id, 'storage', 'u')


def _enabled_user_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        identity = get_jwt_identity()
        if not isinstance(identity, str) or not identity:
            return jsonify({'code': 401, 'msg': '登录用户无效，请重新登录'}), 401
        user = db.session.query(User.id, User.user_status).filter(User.username == identity).first()
        if not user or user.user_status != '1':
            return jsonify({'code': 401, 'msg': '用户不存在或账号已禁用，请重新登录'}), 401
        return fn(*args, **kwargs)
    return wrapped


@storage_retention_view.route('/settings', methods=['GET', 'POST'])
@jwt_required()
@_enabled_user_required
def settings():
    can_edit = _can_edit_settings()
    from flask import g
    from common.platform_access import has_menu_permission
    if not can_edit and (request.method == 'POST' or not has_menu_permission(g.platform_user.id, 'storage', 'r')):
        return jsonify({'code': 403, 'msg': '当前账号没有存储设置操作权限'})
    body = request.get_json(silent=True) if request.method == 'POST' else None
    if request.method == 'POST' and (not isinstance(body, dict)
            or type(body.get('alarm_retention_days')) is not int):
        return jsonify({'code': 400, 'msg': '请提供报警保留期限天数'})
    try:
        result = retention_settings(body['alarm_retention_days'] if body else None)
        if result.get('code') == 200:
            result['data']['can_edit'] = can_edit
        return jsonify(result)
    except Exception:
        return jsonify({'code': 500, 'msg': '存储设置服务暂不可用，请稍后重试'})


@storage_retention_view.route('/cleanup', methods=['POST'])
@jwt_required()
@_enabled_user_required
def cleanup():
    if not _can_edit_settings():
        return jsonify({'code': 403, 'msg': '当前账号没有存储清理操作权限'})
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or type(body.get('dry_run')) is not bool:
        return jsonify({'code': 400, 'msg': '请明确提供dry_run布尔参数'})
    try:
        return jsonify(cleanup_alarm_data(dry_run=body['dry_run']))
    except Exception:
        return jsonify({'code': 500, 'msg': '报警清理失败，原有媒体已保留待重试'})
