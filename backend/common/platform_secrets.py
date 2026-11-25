"""Load per-installation signing keys from a private, read-only server file."""
import json
import os
import stat
from pathlib import Path


def load_platform_security(app):
    path = Path(os.environ.get('PLATFORM_SECURITY_CONFIG', '/data/AIGO/platform_start/backend/platform-security.json'))
    if not path.is_absolute():
        raise RuntimeError('PLATFORM_SECURITY_CONFIG must be an absolute path')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError('Platform security configuration must be a regular file')
    if os.name == 'posix' and stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError('Platform security configuration must have mode 0600 or stricter')
    values = json.loads(path.read_text(encoding='utf-8'))
    names = ('SESSION_SECRET_KEY', 'JWT_SECRET_KEY', 'MEDIA_SESSION_SECRET_KEY')
    if not isinstance(values, dict):
        raise RuntimeError('Invalid platform security configuration')
    keys = [values.get(name) for name in names]
    if any(not isinstance(key, str) or len(key) < 64 or len(set(key)) < 8 for key in keys):
        raise RuntimeError('Platform signing keys must be independently generated random values')
    if len(set(keys)) != len(keys):
        raise RuntimeError('Platform signing keys must be distinct')
    app.config.update(SECRET_KEY=keys[0], JWT_SECRET_KEY=keys[1], MEDIA_SESSION_SECRET_KEY=keys[2],
                      SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True, JWT_TOKEN_LOCATION=['headers'])
    # Deploy only with Gunicorn bound to loopback. The local Nginx proxy
    # replaces forwarding headers rather than accepting a client chain.
    if values.get('TRUST_LOOPBACK_PROXY') is True:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
