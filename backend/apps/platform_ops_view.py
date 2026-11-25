# native-role-policy-v1
"""Administrative maintenance bridge; privileged host key never leaves backend."""
import http.client
import json
import re
from pathlib import Path
from urllib.parse import quote, urlencode
from flask import Blueprint, g, jsonify, request
from sqlalchemy import LargeBinary, cast
from common.platform_auth import platform_jwt_required
from data.exts import db
from model.admin import Permission, UserPermission

platform_ops_view = Blueprint('platform_ops', __name__)
CLIENT_CONFIG = '/data/AIGO/platform_start/backend/config/platform-ops-client.json'
ROUTES = {
    ('GET', 'health'), ('GET', 'push/status'), ('POST', 'push/settings'),
    ('POST', 'push/test'), ('POST', 'push/retry'), ('POST', 'push/delete'), ('GET', 'storage'),
    ('GET', 'storage/status'), ('POST', 'storage/preview'), ('POST', 'storage/draft'),
    ('POST', 'storage/apply'), ('GET', 'upgrade/status'), ('POST', 'upgrade/uploads'),
    ('POST', 'upgrade/plan'), ('POST', 'upgrade/apply'), ('POST', 'upgrade/rollback'),
    ('GET', 'upgrade/examples'), ('GET', 'ntp'), ('PUT', 'ntp'), ('POST', 'ntp/sync'),
}


def _can_delete_push():
    from common.platform_access import has_menu_permission
    return has_menu_permission(g.platform_user.id, 'data-push', 'd')


def _admin(operation):
    if operation == 'push/delete':
        return _can_delete_push()
    from service.platform_role_policy import maintenance_allowed
    return maintenance_allowed(operation)


@platform_ops_view.route('/<path:operation>', methods=['GET', 'POST', 'PUT'])
@platform_jwt_required
def maintenance(operation):
    if not _admin(operation):
        return jsonify({'code': 403, 'msg': '当前账号没有此维护操作的权限'}), 403
    upload = re.fullmatch(r'upgrade/uploads/([a-f0-9]{32})/(chunk|finish)', operation)
    upload_status = request.method == 'GET' and re.fullmatch(r'upgrade/uploads/[a-f0-9]{32}', operation)
    detail = request.method == 'GET' and re.fullmatch(r'push/deliveries/[1-9][0-9]{0,18}', operation)
    job_detail = request.method == 'GET' and re.fullmatch(r'upgrade/jobs/[a-f0-9]{32}', operation)
    if (request.method, operation) not in ROUTES and not (upload and request.method == 'POST') and not upload_status and not detail and not job_detail:
        return jsonify({'code': 404, 'msg': '维护操作不存在'}), 404
    query = {}
    if request.args:
        if not detail or set(request.args) - {'before_attempt_id', 'limit'}:
            return jsonify({'code': 400, 'msg': '不支持的查询参数'}), 400
        for key in request.args:
            values = request.args.getlist(key)
            if len(values) != 1 or not re.fullmatch(r'[1-9][0-9]{0,18}', values[0]):
                return jsonify({'code': 400, 'msg': '回执分页参数无效'}), 400
            value = int(values[0])
            if (key == 'limit' and value > 10) or value > 9223372036854775807:
                return jsonify({'code': 400, 'msg': '回执分页参数超出范围'}), 400
            query[key] = value
    if request.content_length is not None and request.content_length > 5 * 1024 * 1024:
        return jsonify({'code': 413, 'msg': '单次上传分片不能超过4MiB'}), 413
    raw = request.get_data(cache=False)
    if not upload or upload.group(2) != 'chunk':
        try:
            body = json.loads(raw.decode('utf-8')) if raw else {}
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            return jsonify({'code': 400, 'msg': '请提供JSON对象'}), 400
    connection = None
    try:
        settings = json.loads(Path(CLIENT_CONFIG).read_text())
        headers = {'Content-Type': request.content_type or 'application/json',
                   'X-Platform-Ops-Key': settings['key'], 'X-Platform-Actor': quote(str(g.platform_user.username), safe='')}
        if upload and upload.group(2) == 'chunk':
            headers['X-Upload-Offset'] = request.headers.get('X-Upload-Offset', '')
        connection = http.client.HTTPConnection('127.0.0.1', 9011, timeout=40)
        destination = '/' + operation + ('?' + urlencode(query) if query else '')
        method = request.method
        if operation == 'ntp':
            destination = '/ntp/status' if method == 'GET' else '/ntp/config'
            method = 'GET' if method == 'GET' else 'POST'
        connection.request(method, destination, body=raw, headers=headers)
        response = connection.getresponse()
        response_limit = (8 if detail or job_detail else 2) * 1024 * 1024
        received = response.read(response_limit + 1)
        if len(received) > response_limit:
            return jsonify({'code': 502, 'msg': '维护响应超出显示限制，请减少回执分页条数'}), 502
        result = json.loads(received.decode('utf-8'))
        if not isinstance(result, dict):
            raise ValueError()
        if operation in ('ntp', 'ntp/sync') and response.status == 200 and isinstance(result.get('data'), dict):
            result['data']['can_edit'] = True
        if operation == 'push/status' and response.status == 200 and isinstance(result.get('data'), dict):
            result['data']['can_delete'] = _can_delete_push()
        return jsonify(result), response.status
    except Exception:
        return jsonify({'code': 503, 'msg': '平台维护服务暂不可用，请稍后刷新'}), 503
    finally:
        if connection is not None:
            connection.close()
