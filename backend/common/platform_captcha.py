"""Per-browser, single-use captcha challenges stored in the existing Redis."""
import re
import secrets

from flask import request

CAPTCHA_COOKIE = 'platform_captcha_id'
CAPTCHA_SECONDS = 180
_CLIENT_ID = re.compile(r'^[A-Za-z0-9_-]{43}$')
_CONSUME = "local v=redis.call('GET',KEYS[1]); redis.call('DEL',KEYS[1]); return v"


def _key(client_id):
    return 'platform:captcha:v1:' + client_id


def issue_captcha(redis_client, code):
    previous = request.cookies.get(CAPTCHA_COOKIE, '')
    if _CLIENT_ID.fullmatch(previous):
        redis_client.delete(_key(previous))
    client_id = secrets.token_urlsafe(32)
    redis_client.setex(_key(client_id), CAPTCHA_SECONDS, code)
    return client_id


def set_captcha_cookie(response, client_id):
    response.set_cookie(CAPTCHA_COOKIE, client_id, max_age=CAPTCHA_SECONDS,
                        secure=True, httponly=True, samesite='Strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response


def consume_captcha(redis_client, supplied):
    client_id = request.cookies.get(CAPTCHA_COOKIE, '')
    if not _CLIENT_ID.fullmatch(client_id):
        return False
    # Lua works on older Redis versions without GETDEL, and consumes even a
    # wrong answer atomically so parallel requests cannot reuse a challenge.
    expected = redis_client.eval(_CONSUME, 1, _key(client_id))
    if isinstance(expected, bytes):
        expected = expected.decode('ascii', errors='ignore')
    if (not isinstance(expected, str) or not isinstance(supplied, str)
            or not re.fullmatch(r'[A-Za-z0-9]{1,10}', supplied)):
        return False
    return secrets.compare_digest(expected.upper(), supplied.upper())
