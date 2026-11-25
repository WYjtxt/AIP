"""Bounded, session-confirmed first activation using the existing AK format.

The embedded Fernet key is retained for compatibility. This is not a new
issuer-signature scheme. No uploaded filename is used and no file is saved.
"""
import contextlib
from datetime import datetime
import json
import os
import re
import secrets
import stat
import time

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, jsonify, request, session
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

MAX_FILE_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 16 * 1024
NONCE_SECONDS = 600
SESSION_KEY = 'activation_bootstrap_v1'
LOCK_PATH = '/tmp/platform-activation-bootstrap.lock'
PROFILE_FIELDS = ('username', 'company', 'nation', 'mobile', 'province', 'city', 'address', 'time')


class InvalidActivation(ValueError):
    pass


def parse_activation(data, product_key, machine_id, now=None):
    """Validate in memory before any filesystem/database mutation."""
    now = now or datetime.now()
    if not data or len(data) > MAX_FILE_BYTES:
        raise InvalidActivation('激活文件为空或超过 64 KiB')
    try:
        text = data.decode('utf-8-sig')
        values = []
        for label in ('BLOCK', 'BLOCK KEY'):
            pattern = (r'^-+\s*BEGIN ' + label + r'\s*-+[ \t]*\r?\n'
                       r'([A-Za-z0-9_\-=\r\n]+)\r?\n-+\s*END ' + label + r'\s*-+[ \t]*$')
            matches = re.findall(pattern, text, flags=re.MULTILINE)
            if len(matches) != 1:
                raise ValueError('missing or repeated activation block')
            values.append(''.join(matches[0].splitlines()).strip())
        encrypted, key = values
        decoded = Fernet(key.encode('ascii')).decrypt(encrypted.encode('ascii'))
        info = json.loads(decoded.decode('utf-8'))
        if not isinstance(info, dict):
            raise ValueError('activation payload is not an object')
    except (ValueError, TypeError, UnicodeError, InvalidToken):
        raise InvalidActivation('激活文件格式或校验失败，请使用原始 .ak 文件')
    supplied_key = info.get('key')
    if not isinstance(supplied_key, str) or not isinstance(product_key, str) or not secrets.compare_digest(supplied_key.encode(), product_key.encode()):
        raise InvalidActivation('激活文件与当前产品不匹配')
    supplied_machine = info.get('machine_uuid')
    if not isinstance(machine_id, str) or not machine_id.strip():
        raise RuntimeError('target machine identifier is unavailable')
    if not isinstance(supplied_machine, str) or supplied_machine.strip().lower() != machine_id.strip().lower():
        raise InvalidActivation('激活文件与本机机器码不匹配，请重新扫码申请')
    valid_until = info.get('valid_until')
    if not isinstance(valid_until, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', valid_until):
        raise InvalidActivation('激活文件有效期格式不正确')
    try:
        expires = datetime.strptime(valid_until, '%Y-%m-%d')
    except ValueError:
        raise InvalidActivation('激活文件有效期格式不正确')
    # Match the existing verifier's midnight expiry semantics.
    if expires <= now:
        raise InvalidActivation('激活文件已过期，请重新申请')
    for field in PROFILE_FIELDS:
        value = info.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 255):
            raise InvalidActivation('激活文件中的产品信息格式不正确')
    return info, key, encrypted


@contextlib.contextmanager
def activation_lock(path=LOCK_PATH):
    """Serialize check-and-insert across workers of the local backend."""
    import fcntl
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise RuntimeError('unsafe activation lock')
        os.fchmod(fd, 0o600)
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('activation is busy')
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class ActivationRepository:
    """Use the current schema, propagate database failures to the caller."""
    def __init__(self, database, model):
        self.database = database
        self.model = model

    def has_active(self, now=None):
        now = now or datetime.now()
        records = self.database.session.query(self.model).filter(self.model.activate_status == '1').all()
        for record in records:
            # Malformed stored state is an error, not permission to bootstrap.
            expiry = datetime.strptime(record.activate_valid_until, '%Y-%m-%d')
            if expiry > now:
                return True
        return False

    def duplicate(self, key, encrypted):
        return self.database.session.query(self.model).filter(
            self.model.activate_key == key,
            self.model.activate_encrypted_data == encrypted).first() is not None

    def insert(self, info, key, encrypted):
        values = {'activate_' + name: info.get(name) for name in PROFILE_FIELDS}
        values.update(activate_key=key, activate_encrypted_data=encrypted,
                      activate_status='1', activate_valid_until=info['valid_until'])
        self.database.session.add(self.model(**values))
        self.database.session.commit()

    def rollback(self):
        self.database.session.rollback()


def _response(code, message, **extra):
    body = dict(code=code, msg=message)
    body.update(extra)
    response = jsonify(body)
    response.status_code = code
    response.headers['Cache-Control'] = 'no-store'
    return response


def _origin_allowed(origins, require=False):
    origin = request.headers.get('Origin')
    return (not require and origin is None) or origin in origins


def _rollback_safely(repository):
    try:
        repository.rollback()
    except Exception:
        # Database failure never converts into permission to bootstrap.
        pass


def issue_challenge(repository, origins):
    if not _origin_allowed(origins):
        return _response(403, '请从当前平台页面申请激活')
    try:
        if repository.has_active():
            session.pop(SESSION_KEY, None)
            return _response(409, '系统已激活，请登录后管理授权')
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = {'token': token, 'issued': time.time()}
        return _response(200, '请选择本机激活文件', csrf_token=token, expires_in=NONCE_SECONDS)
    except Exception:
        _rollback_safely(repository)
        return _response(503, '暂时无法确认激活状态，请稍后重试')


def import_first_activation(repository, origins, product_key, machine_id):
    if not _origin_allowed(origins, require=True):
        return _response(403, '请从当前平台页面导入激活文件')
    challenge = session.get(SESSION_KEY)
    supplied = request.headers.get('X-Activation-CSRF', '')
    if (not isinstance(challenge, dict) or not isinstance(challenge.get('token'), str)
            or not isinstance(challenge.get('issued'), (int, float))
            or not 0 <= time.time() - challenge['issued'] <= NONCE_SECONDS
            or not re.fullmatch(r'[A-Za-z0-9_-]{43}', supplied)
            or not secrets.compare_digest(challenge['token'], supplied)):
        return _response(403, '激活页面已过期，请刷新页面后重新选择文件')
    if request.content_length is None or request.content_length > MAX_REQUEST_BYTES:
        return _response(413, '激活文件上传请求超过大小限制（文件限 64 KiB）')
    try:
        files = request.files.getlist('files')
        if len(files) != 1:
            return _response(400, '请选择一个原始 .ak 激活文件')
        content = files[0].stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            return _response(413, '激活文件不能超过 64 KiB')
        with activation_lock(current_app.config.get('ACTIVATION_BOOTSTRAP_LOCK', LOCK_PATH)):
            # Reset any prior read snapshot before checking under the lock.
            repository.rollback()
            if repository.has_active():
                session.pop(SESSION_KEY, None)
                return _response(409, '系统已激活，请登录后管理授权')
            info, key, encrypted = parse_activation(content, product_key, machine_id)
            if repository.duplicate(key, encrypted):
                return _response(409, '该激活文件已使用，请勿重复导入')
            repository.insert(info, key, encrypted)
            session.pop(SESSION_KEY, None)
        return _response(200, '系统激活成功！')
    except InvalidActivation as error:
        return _response(400, str(error))
    except RequestEntityTooLarge:
        return _response(413, '激活文件不能超过 64 KiB')
    except BadRequest:
        return _response(400, '激活文件上传格式不正确，请重新选择原始文件')
    except Exception:
        _rollback_safely(repository)
        return _response(503, '激活操作暂未完成，请稍后重试；请勿修改激活文件')
