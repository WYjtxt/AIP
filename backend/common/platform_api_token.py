"""JSON credential exchange for clients using the existing platform Bearer JWT."""
import logging
import time

from flask import jsonify, request
from flask_jwt_extended import decode_token

from service import user_view_service as login_service


logger = logging.getLogger(__name__)


def _response(body, status=200, retry_after=None):
    response = jsonify(body)
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    return response


def _limited(peer, scoped_peer, username):
    return any(not login_service._login_rate_check(address, username)[0]
               for address in (peer, scoped_peer))


def _locked():
    return _response({'code': 429, 'msg': '登录失败次数过多，请稍后重试'},
                     429, login_service.LOGIN_LOCK_SEC)


def issue_api_token():
    """POST only, with credentials in JSON; never accept role or expiry overrides.

    The legacy credential verifier remains responsible for password, enabled
    account/role checks and login auditing.  A separate IP failure bucket also
    counts unknown and disabled accounts, without clearing legacy login locks.
    """
    if request.content_length is not None and request.content_length > 16384:
        return _response({'code': 413, 'msg': '请求体过大'}, 413)
    if not request.is_json:
        return _response({'code': 415, 'msg': '请使用 application/json 请求体'}, 415)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) != {'username', 'password'}:
        return _response({'code': 400, 'msg': '请仅提交 username 和 password'}, 400)
    username, password = body['username'], body['password']
    if (not isinstance(username, str) or not isinstance(password, str)
            or not username.strip() or not password.strip()
            or len(username) > 256 or len(password) > 4096):
        return _response({'code': 400, 'msg': '账号或密码格式不正确'}, 400)
    username = username.strip()
    peer = request.remote_addr
    scoped_peer = 'api-token:' + peer if peer else None
    try:
        if _limited(peer, scoped_peer, username):
            return _locked()
        success, _message, result = login_service.UserViewService.loginfree(
            username, password, peer, request.host, request.headers.get('User-Agent'))
        if not success:
            login_service._login_rate_record_fail(scoped_peer, username)
            if _limited(peer, scoped_peer, username):
                return _locked()
            # Do not disclose whether the account exists or its role is disabled.
            return _response({'code': 401, 'msg': '账号、密码或账号权限无效'}, 401)
        token = result['access_token']
        claims = decode_token(token)
        if (claims.get('sub') != username or claims.get('type') != 'access'
                or type(claims.get('exp')) is not int):
            raise ValueError('Unexpected access token claims')
        login_service._login_rate_clear(scoped_peer)
        return _response({
            'code': 200,
            'msg': '获取Token成功',
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': max(0, claims['exp'] - int(time.time())),
            'expires_at': claims['exp'],
        })
    except Exception as error:
        # Never include credentials, JWTs, request bodies or exception text.
        logger.warning('API token exchange failed type=%s', type(error).__name__)
        return _response({'code': 503, 'msg': '鉴权服务暂时不可用，请稍后重试'}, 503)
