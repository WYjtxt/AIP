"""Short-lived, media-only browser sessions for Nginx auth_request."""
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, make_response, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from common.platform_auth import enabled_platform_user, platform_jwt_required
from common.recipient_media import authorize as authorize_recipient_media
from flask_jwt_extended import get_jwt_identity


MEDIA_COOKIE = 'platform_media_session'
MEDIA_SECONDS = 600
MEDIA_COOKIE_PATH = '/media/'
_MEDIA_SALT = 'platform-media-session-v1'
platform_security = Blueprint('platform_security', __name__)
RECIPIENT_STATE = Path('/data/AIGO/platform_start/platform_ops/state')


def _serializer():
    key = current_app.config.get('MEDIA_SESSION_SECRET_KEY') or current_app.config.get('JWT_SECRET_KEY')
    if not isinstance(key, (str, bytes)) or len(key) < 32:
        raise RuntimeError('A strong media session signing secret is required')
    return URLSafeTimedSerializer(key, salt=_MEDIA_SALT)


@platform_security.route('/media-session', methods=['POST', 'DELETE'])
def media_session():
    if request.method == 'DELETE':
        # Clearing this browser's cookie grants no access and also works when
        # its API JWT has expired.  It cannot revoke another browser's cookie.
        response = jsonify({'code': 200, 'expires_in': 0})
        response.delete_cookie(MEDIA_COOKIE, path=MEDIA_COOKIE_PATH,
                               secure=True, httponly=True, samesite='Strict')
        response.headers['Cache-Control'] = 'no-store'
        return response
    return _issue_media_session()


@platform_jwt_required
def _issue_media_session():
    response = jsonify({'code': 200, 'expires_in': MEDIA_SECONDS})
    token = _serializer().dumps({'purpose': 'browser-media', 'sub': get_jwt_identity(),
                                 'nonce': secrets.token_urlsafe(16)})
    response.set_cookie(MEDIA_COOKIE, token, max_age=MEDIA_SECONDS, path=MEDIA_COOKIE_PATH,
                        secure=True, httponly=True, samesite='Strict')
    response.headers['Cache-Control'] = 'no-store'
    return response


@platform_security.route('/media-access', methods=['GET'])
def media_access():
    """Called through an internal Nginx subrequest, never an API JWT login."""
    cookie = request.cookies.get(MEDIA_COOKIE, '')
    allowed = False
    if cookie:
        try:
            data = _serializer().loads(cookie, max_age=MEDIA_SECONDS)
            if isinstance(data, dict) and data.get('purpose') == 'browser-media':
                user, _ = enabled_platform_user(data.get('sub'))
                allowed = user is not None
        except (BadSignature, SignatureExpired):
            pass
    # Checking access does not issue or extend the cookie's fixed lifetime.
    response = make_response('', 204 if allowed else 401)
    response.headers['Cache-Control'] = 'no-store'
    return response


@platform_security.route('/recipient-media-access', methods=['GET'])
def recipient_media_access():
    """Authorize the original file request from the site's internal gateway."""
    allowed = request.remote_addr in ('127.0.0.1', '::1') and authorize_recipient_media(
        request.headers.get('X-Platform-Media-Request'),
        request.headers.get('X-Platform-Media-Client'), RECIPIENT_STATE)
    response = make_response('', 204 if allowed else 403)
    response.headers['Cache-Control'] = 'no-store'
    return response


def install_platform_media(app):
    app.register_blueprint(platform_security, url_prefix='/security')
