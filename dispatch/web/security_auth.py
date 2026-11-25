"""Local authentication store for the configuration dispatch service (Python 3.9).

Only password derivations and SHA-256 session-token digests are persisted.
Transport security, CSRF request checks and HTTP authorization belong to the caller.
"""
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


PBKDF2_ITERATIONS = 600000
SESSION_IDLE_SECONDS = 30 * 60
SESSION_ABSOLUTE_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
USERNAME_FAILURE_LIMIT = 5
IP_FAILURE_LIMIT = 30
ROLES = frozenset(('admin', 'operator', 'viewer'))
_USERNAME = re.compile(r'^[A-Za-z0-9_.-]{3,32}$', re.ASCII)
_SECRET_KEY = re.compile(r'password|passwd|secret|token|cookie|csrf|authorization|credential|salt|hash', re.I)
_DUMMY_SALT = bytes.fromhex('ee2b1fd5b8a93140316781f7dc045b6d')
_DUMMY_HASH = None
_DUMMY_LOCK = threading.Lock()


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _password_bytes(password):
    if not isinstance(password, str) or not 15 <= len(password) <= 128:
        raise AuthError('密码长度必须为 15 至 128 个字符')
    try:
        encoded = password.encode('utf-8')
    except UnicodeEncodeError:
        raise AuthError('密码包含无效字符') from None
    if len(encoded) > 512 or not password.strip() or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise AuthError('密码不可为空白或包含控制字符')
    return encoded


def _username(username):
    if not isinstance(username, str) or not _USERNAME.fullmatch(username):
        raise AuthError('用户名须为 3 至 32 位英文字母、数字、点、下划线或短横线')
    return username.lower()


def _derive(password, salt, iterations=PBKDF2_ITERATIONS):
    return hashlib.pbkdf2_hmac('sha256', password, salt, iterations).hex()


def _token_hash(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        return None
    try:
        return hashlib.sha256(token.encode('ascii')).hexdigest()
    except UnicodeEncodeError:
        return None


def _safe_detail(value, depth=0):
    """Defence in depth; callers must still supply summaries rather than secrets."""
    if depth > 5:
        return '[omitted]'
    if isinstance(value, dict):
        return {str(k)[:100]: '[redacted]' if _SECRET_KEY.search(str(k)) else _safe_detail(v, depth + 1)
                for k, v in list(value.items())[:50]}
    if isinstance(value, (list, tuple)):
        return [_safe_detail(v, depth + 1) for v in value[:50]]
    if isinstance(value, str):
        return value[:1000]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return '[omitted]'


class AuthStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise AuthError('认证存储不可使用符号链接', 500)
        os.chmod(str(self.path.parent), 0o700)
        # Precreate privately so SQLite never briefly creates a world-readable DB.
        try:
            descriptor = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if not self.path.is_file():
                raise AuthError('认证存储路径无效', 500) from None
        else:
            os.close(descriptor)
        os.chmod(str(self.path), 0o600)
        with self._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    iterations INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                    csrf TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_username ON sessions(username);
                CREATE TABLE IF NOT EXISTS login_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    identity TEXT NOT NULL,
                    happened_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS login_failure_lookup
                    ON login_failures(scope, identity, happened_at);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    happened_at REAL NOT NULL,
                    username TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
            ''')
        global _DUMMY_HASH
        with _DUMMY_LOCK:
            if _DUMMY_HASH is None:
                _DUMMY_HASH = _derive(b'no-real-account-password', _DUMMY_SALT)

    @contextlib.contextmanager
    def _connection(self):
        with self._lock:
            db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=10000')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                if db.in_transaction:
                    db.commit()
            except Exception:
                if db.in_transaction:
                    db.rollback()
                raise
            finally:
                db.close()

    @staticmethod
    def _audit(db, actor, ip, action, detail):
        if isinstance(actor, dict):
            actor = actor.get('username', '')
        db.execute('INSERT INTO audit(happened_at, username, ip, action, detail) VALUES(?,?,?,?,?)',
                   (time.time(), str(actor or '')[:128], str(ip or '')[:128], str(action)[:100],
                    json.dumps(_safe_detail(detail), ensure_ascii=False)))

    @staticmethod
    def _public_user(row):
        return {key: bool(row[key]) if key == 'disabled' else row[key]
                for key in ('username', 'role', 'disabled', 'created_at', 'updated_at')}

    @staticmethod
    def _session(db, token_hash, now, touch=False):
        if not token_hash:
            return None
        row = db.execute('''SELECT s.*, u.role, u.disabled FROM sessions s
                          JOIN users u ON u.username=s.username WHERE s.token_hash=?''',
                         (token_hash,)).fetchone()
        if not row:
            return None
        if row['disabled'] or now >= row['expires_at'] or now - row['last_seen'] >= SESSION_IDLE_SECONDS:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))
            return None
        last_seen = now if touch else row['last_seen']
        if touch:
            db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?', (now, token_hash))
        return {'id': token_hash, 'username': row['username'], 'role': row['role'],
                'csrf': row['csrf'], 'created_at': row['created_at'], 'last_seen': last_seen,
                'expires_at': row['expires_at'],
                'idle_expires_at': min(last_seen + SESSION_IDLE_SECONDS, row['expires_at'])}

    def _actor(self, db, actor, admin=False):
        session_id = actor.get('id') if isinstance(actor, dict) else None
        session = self._session(db, session_id, time.time())
        if session is None:
            raise AuthError('请重新登录', 401)
        if admin and session['role'] != 'admin':
            raise AuthError('需要管理员权限', 403)
        return session

    def status(self):
        with self._connection() as db:
            return bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    def bootstrap(self, token, username, password):
        username = _username(username)
        password_bytes = _password_bytes(password)
        token_path = self.path.parent / 'bootstrap.token'
        with self._connection() as db:
            if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise AuthError('系统已经初始化', 403)
            try:
                info = token_path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise OSError('not a regular file')
                expected = token_path.read_text(encoding='utf-8').strip()
            except (OSError, UnicodeError):
                raise AuthError('初始化令牌不可用，请联系管理员', 403) from None
            supplied = token.encode('utf-8') if isinstance(token, str) else b''
            if not 32 <= len(expected) <= 256 or not hmac.compare_digest(supplied, expected.encode('utf-8')):
                raise AuthError('初始化令牌无效', 403)
            now, salt = time.time(), secrets.token_bytes(16)
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)',
                       (username, _derive(password_bytes, salt), salt.hex(), PBKDF2_ITERATIONS,
                        'admin', 0, now, now))
            self._audit(db, username, '', 'bootstrap', {'role': 'admin'})
            # Deletion happens while the transaction and bootstrap lock are held.
            try:
                token_path.unlink()
            except OSError:
                raise AuthError('初始化令牌无法清理，请联系管理员', 500) from None
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            return self._public_user(row)

    def login(self, username, password, ip):
        valid_username = isinstance(username, str) and bool(_USERNAME.fullmatch(username))
        normalized = username.lower() if valid_username else '<invalid>'
        ip = str(ip or '')[:128]
        now = time.time()
        # Return authentication errors after committing counters and audit events.
        error = None
        result = None
        with self._connection() as db:
            db.execute('DELETE FROM login_failures WHERE happened_at<=?', (now - LOGIN_WINDOW_SECONDS,))
            ip_count = db.execute("SELECT COUNT(*) FROM login_failures WHERE scope='ip' AND identity=?", (ip,)).fetchone()[0]
            name_count = db.execute("SELECT COUNT(*) FROM login_failures WHERE scope='username' AND identity=?", (normalized,)).fetchone()[0]
            if ip_count >= IP_FAILURE_LIMIT or name_count >= USERNAME_FAILURE_LIMIT:
                self._audit(db, normalized, ip, 'login_limited', {})
                error = AuthError('登录尝试过多，请在 15 分钟后重试', 429)
            else:
                user = db.execute('SELECT * FROM users WHERE username=?', (normalized,)).fetchone()
                try:
                    encoded = password.encode('utf-8') if isinstance(password, str) and len(password) <= 128 else b''
                except UnicodeEncodeError:
                    encoded = b''
                salt = bytes.fromhex(user['salt']) if user else _DUMMY_SALT
                expected = user['password_hash'] if user else _DUMMY_HASH
                actual = _derive(encoded, salt, user['iterations'] if user else PBKDF2_ITERATIONS)
                verified = hmac.compare_digest(actual, expected)
                if not user or user['disabled'] or not valid_username or not verified:
                    db.executemany('INSERT INTO login_failures(scope,identity,happened_at) VALUES(?,?,?)',
                                   [('ip', ip, now), ('username', normalized, now)])
                    self._audit(db, normalized, ip, 'login_failed', {})
                    error = AuthError('用户名或密码错误', 401)
                else:
                    raw_token = secrets.token_urlsafe(32)
                    token_hash = _token_hash(raw_token)
                    csrf = secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires_at<=? OR last_seen<=?',
                               (now, now - SESSION_IDLE_SECONDS))
                    db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',
                               (token_hash, user['username'], csrf, now, now, now + SESSION_ABSOLUTE_SECONDS))
                    db.execute("DELETE FROM login_failures WHERE scope='username' AND identity=?", (normalized,))
                    session = self._session(db, token_hash, now)
                    public = {k: v for k, v in session.items() if k != 'id'}
                    self._audit(db, normalized, ip, 'login', {})
                    result = (raw_token, public)
        if error:
            raise error
        return result

    def get_session(self, raw_token):
        token_hash = _token_hash(raw_token)
        if not token_hash:
            return None
        with self._connection() as db:
            return self._session(db, token_hash, time.time(), touch=True)

    def logout(self, raw_token):
        token_hash = _token_hash(raw_token)
        if not token_hash:
            return
        with self._connection() as db:
            row = db.execute('SELECT username FROM sessions WHERE token_hash=?', (token_hash,)).fetchone()
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))
            if row:
                self._audit(db, row['username'], '', 'logout', {})

    def change_password(self, session, old, new):
        encoded = _password_bytes(new)
        with self._connection() as db:
            current = self._actor(db, session)
            user = db.execute('SELECT * FROM users WHERE username=?', (current['username'],)).fetchone()
            try:
                old_encoded = old.encode('utf-8') if isinstance(old, str) and len(old) <= 128 else b''
            except UnicodeEncodeError:
                old_encoded = b''
            actual = _derive(old_encoded, bytes.fromhex(user['salt']), user['iterations'])
            if not hmac.compare_digest(actual, user['password_hash']):
                raise AuthError('当前密码错误', 401)
            salt = secrets.token_bytes(16)
            db.execute('UPDATE users SET password_hash=?,salt=?,iterations=?,updated_at=? WHERE username=?',
                       (_derive(encoded, salt), salt.hex(), PBKDF2_ITERATIONS, time.time(), current['username']))
            db.execute('DELETE FROM sessions WHERE username=?', (current['username'],))
            self._audit(db, current, '', 'password_changed', {})
        return {'ok': True}

    def list_users(self):
        with self._connection() as db:
            return [self._public_user(row) for row in db.execute('SELECT * FROM users ORDER BY username')]

    def save_user(self, actor, username, role, password=None, disabled=False):
        username = _username(username)
        if role not in ROLES:
            raise AuthError('无效的用户角色')
        if not isinstance(disabled, bool):
            raise AuthError('用户禁用状态必须为布尔值')
        encoded = _password_bytes(password) if password is not None else None
        with self._connection() as db:
            current = self._actor(db, actor, admin=True)
            existing = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            if existing and existing['role'] == 'admin' and not existing['disabled'] and (role != 'admin' or disabled):
                admins = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0]
                if admins <= 1:
                    raise AuthError('必须保留至少一名可用管理员', 409)
            now = time.time()
            if existing:
                db.execute('UPDATE users SET role=?,disabled=?,updated_at=? WHERE username=?',
                           (role, int(disabled), now, username))
                if encoded is not None:
                    salt = secrets.token_bytes(16)
                    db.execute('UPDATE users SET password_hash=?,salt=?,iterations=? WHERE username=?',
                               (_derive(encoded, salt), salt.hex(), PBKDF2_ITERATIONS, username))
            else:
                if encoded is None:
                    raise AuthError('创建用户时必须设置密码')
                salt = secrets.token_bytes(16)
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)',
                           (username, _derive(encoded, salt), salt.hex(), PBKDF2_ITERATIONS,
                            role, int(disabled), now, now))
            if disabled or encoded is not None:
                db.execute('DELETE FROM sessions WHERE username=?', (username,))
            self._audit(db, current, '', 'user_saved',
                        {'target': username, 'role': role, 'disabled': disabled,
                         'password_changed': encoded is not None})
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            return self._public_user(row)

    def audit(self, actor, ip, action, detail):
        with self._connection() as db:
            self._audit(db, actor, ip, action, detail)

    def recent_audit(self, limit=100):
        try:
            limit = min(max(int(limit), 1), 1000)
        except (TypeError, ValueError):
            raise AuthError('审计条数无效') from None
        with self._connection() as db:
            rows = db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
            return [{'id': row['id'], 'timestamp': row['happened_at'],
                     'time': datetime.fromtimestamp(row['happened_at'], timezone.utc).isoformat(),
                     'username': row['username'], 'ip': row['ip'], 'action': row['action'],
                     'detail': json.loads(row['detail'])} for row in rows]
