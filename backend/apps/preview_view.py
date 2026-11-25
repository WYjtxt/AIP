"""Authenticated media preview and explicit recorder-channel preparation."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from service.preview_service import get_preview_stream, list_preview_devices
from apps.analysis_preview_view import _enabled_user_required

preview_view = Blueprint('preview', __name__)


@preview_view.route('/devices', methods=['GET'])
@jwt_required()
def devices():
    return jsonify(list_preview_devices())


@preview_view.route('/play', methods=['GET'])
@jwt_required()
def play():
    return jsonify(get_preview_stream(request.args.get('em_id')))


@preview_view.route('/prepare', methods=['POST'])
@jwt_required()
@_enabled_user_required
def prepare():
    from service.preview_source_service import prepare_recorder_channel
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'code': 400, 'msg': '请提供有效的设备ID'})
    return jsonify(prepare_recorder_channel(body.get('em_id')))
