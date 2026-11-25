"""JWT-authenticated superadmin bridge for unified host network configuration."""
import http.client
import json
from pathlib import Path
import re
from urllib.parse import quote

from flask import Blueprint, g, jsonify, request
from common.platform_auth import platform_jwt_required

platform_site_view = Blueprint('platform_site', __name__)
CLIENT_CONFIG = Path(__file__).resolve().parents[1] / 'config/platform-ops-client.json'
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 2 * 1024 * 1024


def install_network_confirmation_access():
    from common.platform_access import PUBLIC_ROUTES
    PUBLIC_ROUTES['/platform_site/network/confirm'] = frozenset(('POST',))


def _superadmin():
    from service.platform_role_policy import is_superadmin
    return bool(is_superadmin(g.platform_user.id))


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate request field')
        result[key] = value
    return result


@platform_site_view.route('/<path:operation>', methods=['GET', 'POST'])
@platform_jwt_required
def unified_network(operation):
    if not _superadmin():
        return jsonify({'code': 403, 'msg': '只有超级管理员可管理统一网络配置'}), 403
    routes = {('GET', 'config'), ('POST', 'preview'), ('POST', 'apply'), ('POST', 'rollback')}
    routes.update({('GET', 'network/config'), ('POST', 'network/preview'), ('POST', 'network/apply')})
    if (request.method, operation) not in routes and not (
            request.method == 'GET' and re.fullmatch(r'(?:network/)?jobs/[a-f0-9]{32}', operation)) and not (
            request.method == 'POST' and re.fullmatch(r'network/jobs/[a-f0-9]{32}/(?:cancel|rollback)', operation)):
        return jsonify({'code': 404, 'msg': '统一配置操作不存在'}), 404
    if request.args:
        return jsonify({'code': 400, 'msg': '不支持的查询参数'}), 400
    if request.content_length is not None and request.content_length > MAX_REQUEST:
        return jsonify({'code': 413, 'msg': '配置请求过大'}), 413
    raw = request.get_data(cache=False)
    if len(raw) > MAX_REQUEST:
        return jsonify({'code': 413, 'msg': '配置请求过大'}), 413
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object) if raw else {}
        if not isinstance(body, dict):
            raise ValueError()
        expected = {'preview': {'config'}, 'apply': {'plan_id'}, 'rollback': {'backup'},
                    'network/preview': {'revision', 'config'}, 'network/apply': {'plan_id', 'request_id'}}
        if operation in expected and set(body) != expected[operation]:
            raise ValueError()
        if operation.startswith('network/jobs/') and request.method == 'POST' and body:
            raise ValueError()
        if request.method == 'GET' and body:
            raise ValueError()
    except (ValueError, UnicodeError):
        return jsonify({'code': 400, 'msg': '配置请求字段不正确'}), 400
    actor = str(g.platform_user.id) + ':' + str(g.platform_user.username)
    return _proxy(operation, body, actor)


def _proxy(operation, body, actor):
    connection = None
    try:
        settings = json.loads(CLIENT_CONFIG.read_text(encoding='utf-8'))
        key = settings['key']
        if not isinstance(key, str) or len(key) < 48:
            raise ValueError()
        headers = {'Content-Type': 'application/json', 'X-Platform-Ops-Key': key,
                   'X-Platform-Actor': quote(actor, safe='')}
        connection = http.client.HTTPConnection('127.0.0.1', 9011, timeout=20)
        connection.request(request.method, '/site-config/' + operation, body=json.dumps(body).encode(), headers=headers)
        response = connection.getresponse()
        received = response.read(MAX_RESPONSE + 1)
        if len(received) > MAX_RESPONSE:
            return jsonify({'code': 502, 'msg': '维护响应超出显示限制'}), 502
        result = json.loads(received.decode('utf-8'))
        if not isinstance(result, dict):
            raise ValueError()
        return jsonify(result), response.status
    except Exception:
        return jsonify({'code': 503, 'msg': '统一配置维护服务暂不可用，请稍后刷新'}), 503
    finally:
        if connection is not None:
            connection.close()


@platform_site_view.route('/network/confirm', methods=['POST'])
def confirm_network():
    # NetworkManager and this gateway use host networking. Direct backend or
    # old-origin calls cannot certify delivery through the selected new IP.
    if request.remote_addr not in ('127.0.0.1', '::1') or request.args:
        return jsonify({'code': 403, 'msg': '请从指定的平台确认入口访问'}), 403
    if request.content_length is not None and request.content_length > MAX_REQUEST:
        return jsonify({'code': 413, 'msg': '确认请求过大'}), 413
    raw = request.get_data(cache=False)
    try:
        if len(raw) > MAX_REQUEST:
            raise ValueError()
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(body, dict) or set(body) != {'job_id', 'token', 'phase'}:
            raise ValueError()
    except (ValueError, UnicodeError):
        return jsonify({'code': 400, 'msg': '确认请求无效'}), 400
    body.update(destination=request.headers.get('X-Platform-Network-Destination', ''),
                peer=request.headers.get('X-Real-IP', ''), origin=request.headers.get('Origin', ''))
    return _proxy('network/confirm', body, 'network-confirmation')
