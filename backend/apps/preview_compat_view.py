"""Authenticated on-demand browser compatibility previews."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from apps.analysis_preview_view import _enabled_user_required
from data.exts import db
from model.admin import Permission, UserPermission, User
from service.preview_compat_service import (
    compatibility_settings, get_compatible_stream, start_compat_reaper, update_compat_lease,
)


preview_compat_view = Blueprint('preview_compat', __name__)


def _can_edit_settings():
    return db.session.query(User.id).join(
        UserPermission, UserPermission.user_id == User.id).join(
        Permission, Permission.id == UserPermission.permission_id).filter(
        User.username == get_jwt_identity(), User.user_status == '1',
        Permission.permission_name == '超级管理员', Permission.permission_status == '1').first() is not None


@preview_compat_view.route('/settings', methods=['GET', 'POST'])
@jwt_required()
@_enabled_user_required
def settings():
    can_edit = _can_edit_settings()
    if request.method == 'POST':
        if not can_edit:
            return jsonify({'code': 403, 'msg': '只有超级管理员可修改兼容转码上限'})
        body = request.get_json(silent=True)
        if (not isinstance(body, dict) or type(body.get('max_streams')) is not int
                or not 1 <= body['max_streams'] <= 8):
            return jsonify({'code': 400, 'msg': '兼容转码最大路数必须是 1–8 的整数'})
        result = compatibility_settings(body['max_streams'])
    else:
        result = compatibility_settings()
    if result.get('code') == 200:
        result['data']['can_edit'] = can_edit
    return jsonify(result)


@preview_compat_view.record_once
def registered(state):
    # Start without a new viewer so orphaned jobs are reclaimed after restart.
    start_compat_reaper()


@preview_compat_view.before_app_request
def ensure_reaper():
    # A prefork child may inherit a dead thread object from a preloaded parent.
    start_compat_reaper()


@preview_compat_view.route('/play', methods=['POST'])
@jwt_required()
@_enabled_user_required
def play():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'code': 400, 'msg': '请提供有效的设备ID'})
    start_compat_reaper()
    return jsonify(get_compatible_stream(body.get('em_id'), get_jwt_identity()))


@preview_compat_view.route('/keepalive', methods=['POST'])
@jwt_required()
@_enabled_user_required
def keepalive():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'code': 400, 'msg': '请提供有效的兼容预览租约'})
    return jsonify(update_compat_lease(body.get('em_id'), body.get('lease_id'),
                                     get_jwt_identity()))


@preview_compat_view.route('/release', methods=['POST'])
@jwt_required()
@_enabled_user_required
def release():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'code': 400, 'msg': '请提供有效的兼容预览租约'})
    return jsonify(update_compat_lease(body.get('em_id'), body.get('lease_id'),
                                     get_jwt_identity(), release=True))
