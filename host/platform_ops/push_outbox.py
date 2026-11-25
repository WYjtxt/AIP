"""Durable, bounded alarm delivery queue. This module never starts a thread."""
import base64
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
from urllib.parse import quote, urlsplit, urlunsplit
import uuid
import push_token_auth as token_auth

STATE_DIR = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', '/data/AIGO/platform_start/platform_ops/state'))
DEFAULT_TARGET = os.environ.get('PLATFORM_PUSH_DEFAULT_TARGET', 'http://172.16.129.236:8080/alarmEvent/insert')
MAX_PENDING = int(os.environ.get('PLATFORM_PUSH_MAX_PENDING', '50000'))
MIN_FREE_BYTES = int(os.environ.get('PLATFORM_PUSH_MIN_FREE_BYTES', str(128 * 1024 * 1024)))
MAX_PAYLOAD_BYTES = 262144
MAX_ATTEMPTS = 12
MAX_RECEIPT_BYTES = 32768
MAX_DETAIL_ATTEMPTS = 10
SAFE_RESPONSE_HEADERS = frozenset(('content-type', 'date', 'server', 'retry-after',
    'x-request-id', 'x-correlation-id', 'x-trace-id', 'traceparent'))


class OutboxError(Exception):
    pass


class Conflict(OutboxError):
    pass


class NotFound(OutboxError):
    pass


def validate_target(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError('请填写完整的 HTTP 或 HTTPS 接收地址')
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError('接收地址不能包含空白或控制字符')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise ValueError('接收地址或端口格式不正确')
    if parsed.scheme.lower() not in ('http', 'https') or not host or not parsed.netloc:
        raise ValueError('接收地址必须以 http:// 或 https:// 开头')
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError('接收地址不能携带账号、密码、查询参数或片段；请使用独立鉴权设置')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('接收端口必须在 1 至 65535 之间')
    if '\\' in value or '%' in host:
        raise ValueError('接收地址主机格式不正确')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode('idna').decode('ascii').lower()
        except UnicodeError:
            raise ValueError('接收地址主机格式不正确')
        if len(host) > 253 or any(not label or len(label) > 63 or label[0] == '-' or label[-1] == '-' or
                                  any(not (ch.isalnum() or ch == '-') for ch in label)
                                  for label in host.rstrip('.').split('.')):
            raise ValueError('接收地址主机格式不正确')
    else:
        if address.is_unspecified or address.is_multicast or address.is_link_local:
            raise ValueError('不能使用未指定、多播或链路本地地址')
        host = '[' + host + ']' if address.version == 6 else host
    netloc = host + (':' + str(port) if port is not None else '')
    path = quote(parsed.path or '/', safe="/%:@!$&'()*+,;=-._~")
    return urlunsplit((parsed.scheme.lower(), netloc, path, '', ''))


def _connect():
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = STATE_DIR / 'push-outbox.sqlite3'
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS push_settings (
            id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL,
            settings_json TEXT NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL, payload_json TEXT NOT NULL, target_url TEXT NOT NULL,
            auth_json TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL, updated_at REAL NOT NULL, next_attempt_at REAL NOT NULL,
            claim_owner TEXT, lease_until REAL, last_http_status INTEGER, last_error TEXT,
            sent_at REAL, title TEXT NOT NULL, device_name TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS deliveries_due ON deliveries(state,next_attempt_at,id);
        CREATE INDEX IF NOT EXISTS deliveries_history ON deliveries(id DESC);
        CREATE TABLE IF NOT EXISTS delivery_keys (
            event_key TEXT PRIMARY KEY, delivery_id INTEGER NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS worker_status (
            id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT, pid INTEGER,
            heartbeat_at REAL, last_error TEXT
        );
        CREATE TABLE IF NOT EXISTS delivery_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL, attempt_no INTEGER NOT NULL,
            owner TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
            target_url TEXT NOT NULL, request_json TEXT NOT NULL,
            request_sha256 TEXT NOT NULL, request_headers_json TEXT NOT NULL,
            response_status INTEGER, response_headers_json TEXT NOT NULL DEFAULT '{}',
            response_body TEXT NOT NULL DEFAULT '', response_truncated INTEGER NOT NULL DEFAULT 0,
            error TEXT, outcome TEXT NOT NULL DEFAULT 'in_flight',
            UNIQUE(delivery_id, attempt_no)
        );
        CREATE INDEX IF NOT EXISTS delivery_attempts_history ON delivery_attempts(delivery_id,id DESC);
    ''')
    if 'token_refreshes' not in {row[1] for row in conn.execute('PRAGMA table_info(deliveries)')}:
        try:
            conn.execute('ALTER TABLE deliveries ADD COLUMN token_refreshes INTEGER NOT NULL DEFAULT 0')
        except sqlite3.OperationalError:
            if 'token_refreshes' not in {row[1] for row in conn.execute('PRAGMA table_info(deliveries)')}: raise
    defaults = {'enabled': True, 'target_url': validate_target(DEFAULT_TARGET), 'timeout_seconds': 5,
                'auth_mode': 'none', 'auth_username': '', 'auth_password': '', 'auth_token': ''}
    conn.execute('INSERT OR IGNORE INTO push_settings VALUES(1,1,?,?)',
                 (json.dumps(defaults), time.time()))
    try:
        os.chmod(str(STATE_DIR), 0o700)
        for suffix in ('', '-wal', '-shm'):
            candidate = Path(str(path) + suffix)
            if candidate.exists():
                os.chmod(str(candidate), 0o600)
    except OSError:
        pass
    return conn


def _settings(conn):
    row = conn.execute('SELECT revision,settings_json,updated_at FROM push_settings WHERE id=1').fetchone()
    settings = json.loads(row['settings_json'])
    settings['revision'] = row['revision']
    settings['updated_at'] = row['updated_at']
    return settings


def public_settings(settings):
    result = {key: settings[key] for key in ('revision', 'enabled', 'target_url', 'timeout_seconds',
                                           'auth_mode', 'updated_at')}
    result['auth_configured'] = bool(settings.get('auth_token') if settings['auth_mode'] == 'bearer'
                                     else settings.get('auth_username') and settings.get('auth_password')
                                     if settings['auth_mode'] == 'basic' else settings.get('auto_token', {}).get('login_url')
                                     if settings['auth_mode'] == 'auto_token' else False)
    result['auto_token'] = token_auth.public(settings.get('auto_token'))
    return result


def _auth(settings):
    result = {key: settings.get(key, '') for key in ('auth_mode', 'auth_username', 'auth_password', 'auth_token')}
    if settings['auth_mode'] == 'auto_token': result['auto_token'] = settings.get('auto_token', dict(token_auth.DEFAULTS))
    return result


def _secret(value, label):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(label + '格式不正确')
    return value


def save_settings(body):
    if not isinstance(body, dict):
        raise ValueError('请求格式不正确')
    allowed = {'revision', 'enabled', 'target_url', 'timeout_seconds', 'auth_mode',
               'auth_username', 'auth_password', 'auth_token', 'clear_auth', 'auto_token'}
    if set(body) - allowed:
        raise ValueError('包含不支持的配置项')
    if type(body.get('revision')) is not int:
        raise ValueError('缺少配置版本，请刷新后重试')
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        current = _settings(conn)
        if body['revision'] != current['revision']:
            raise Conflict('配置已被其他管理员更新，请刷新后重试')
        updated = dict(current)
        if 'enabled' in body:
            if type(body['enabled']) is not bool:
                raise ValueError('启停状态必须为布尔值')
            updated['enabled'] = body['enabled']
        if 'target_url' in body:
            updated['target_url'] = validate_target(body['target_url'])
        if 'timeout_seconds' in body:
            if type(body['timeout_seconds']) is not int or not 1 <= body['timeout_seconds'] <= 30:
                raise ValueError('请求超时必须为 1 至 30 秒的整数')
            updated['timeout_seconds'] = body['timeout_seconds']
        if 'auth_mode' in body:
            if body['auth_mode'] not in ('none', 'basic', 'bearer', 'auto_token'):
                raise ValueError('鉴权方式不正确')
            updated['auth_mode'] = body['auth_mode']
        if body.get('clear_auth') is True:
            updated.update(auth_username='', auth_password='', auth_token='')
        elif 'clear_auth' in body and type(body['clear_auth']) is not bool:
            raise ValueError('清除鉴权参数不正确')
        for field, label in (('auth_username', '账号'), ('auth_password', '密码'), ('auth_token', '令牌')):
            if field in body:
                value = _secret(body[field], label)
                if value:
                    updated[field] = value
        if 'auto_token' in body or updated['auth_mode'] == 'auto_token':
            updated['auto_token'] = token_auth.config(body.get('auto_token', {}), updated.get('auto_token'),
                validate_target, complete=updated['auth_mode'] == 'auto_token' and updated['enabled'])
        if body.get('clear_auth') is True: updated.pop('auto_token', None)
        if updated['auth_mode'] == 'none':
            updated.update(auth_username='', auth_password='', auth_token='')
        elif updated['auth_mode'] == 'basic' and not (updated['auth_username'] and updated['auth_password']):
            raise ValueError('请填写接收端账号和密码')
        elif updated['auth_mode'] == 'bearer' and not updated['auth_token']:
            raise ValueError('请填写接收端令牌')
        if updated['auth_mode'] == 'basic' and ':' in updated['auth_username']:
            raise ValueError('接收端账号不能包含冒号')
        if updated['auth_mode'] == 'bearer':
            if any(ord(ch) > 126 or ch.isspace() for ch in updated['auth_token']):
                raise ValueError('令牌只能包含可见 ASCII 字符，且不能有空白')
            updated.update(auth_username='', auth_password='')
        elif updated['auth_mode'] in ('basic', 'auto_token'):
            updated['auth_token'] = ''
        updated.pop('revision', None)
        updated.pop('updated_at', None)
        now = time.time()
        conn.execute('UPDATE push_settings SET revision=revision+1,settings_json=?,updated_at=? WHERE id=1',
                     (json.dumps(updated), now))
        result = public_settings(_settings(conn))
        conn.commit()
        return result
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def kafka_event_key(topic, partition, offset):
    raw = json.dumps([str(topic), int(partition), int(offset)], separators=(',', ':'))
    return 'kafka:' + hashlib.sha256(raw.encode()).hexdigest()


def _safe_label(value, limit=160):
    text = str(value or '')
    return ''.join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127)[:limit]


def enqueue(payload, event_key=None, kind='alarm', quarantine_reason=None):
    """Return only after FULL-synchronous SQLite commit; failures must reach Kafka."""
    if not isinstance(payload, dict) or kind not in ('alarm', 'test', 'invalid'):
        raise ValueError('推送数据格式不正确')
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if len(raw.encode('utf-8')) > MAX_PAYLOAD_BYTES:
        raise OutboxError('单条推送超过 256 KiB，Kafka 消息尚未确认')
    event_key = event_key or ('manual:' + uuid.uuid4().hex)
    if not isinstance(event_key, str) or not 1 <= len(event_key) <= 96:
        raise ValueError('消息标识格式不正确')
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        known = conn.execute('SELECT delivery_id FROM delivery_keys WHERE event_key=?', (event_key,)).fetchone()
        if known:
            conn.commit()
            return {'id': known['delivery_id'], 'duplicate': True}
        pending = conn.execute("SELECT COUNT(*) FROM deliveries WHERE state!='sent'").fetchone()[0]
        if pending >= MAX_PENDING:
            raise OutboxError('推送队列已达到上限，Kafka 消息尚未确认，请处理积压')
        if shutil.disk_usage(str(STATE_DIR)).free < MIN_FREE_BYTES:
            raise OutboxError('推送磁盘剩余空间不足 128 MiB，Kafka 消息尚未确认')
        settings = _settings(conn)
        now = time.time()
        state = 'quarantined' if kind == 'invalid' else 'pending'
        cursor = conn.execute('''INSERT INTO deliveries
            (event_key,kind,payload_json,target_url,auth_json,state,created_at,updated_at,next_attempt_at,
             last_error,title,device_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (event_key, kind, raw, settings['target_url'], json.dumps(_auth(settings)), state,
             now, now, now, quarantine_reason,
             _safe_label(payload.get('alarmTypeName') or ('格式错误的报警消息' if kind == 'invalid' else '报警数据')),
             _safe_label(payload.get('deviceName'))))
        delivery_id = cursor.lastrowid
        conn.execute('INSERT INTO delivery_keys VALUES(?,?,?)', (event_key, delivery_id, now))
        conn.commit()
        return {'id': delivery_id, 'duplicate': False}
    except sqlite3.Error as exc:
        logging.critical('Push outbox persistence failed (%s); Kafka message must not be committed', type(exc).__name__)
        raise OutboxError('推送队列无法持久化，Kafka 消息尚未确认') from exc
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def quarantine(raw, event_key, reason='消息格式不正确'):
    # Preserve a bounded diagnostic sample without pretending it is a valid alarm.
    return enqueue({'invalid_sample': str(raw)[:16000]}, event_key, 'invalid', reason)


def request_headers(item, private=False):
    """The recorded headers omit credentials; only the sender requests private values."""
    headers = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json',
        'Idempotency-Key': item['event_key'], 'X-Platform-Delivery-Id': str(item['id'])}
    auth = item.get('auth', {})
    authorization = None
    if auth.get('auth_mode') == 'bearer':
        authorization = 'Bearer ' + auth['auth_token']
    elif auth.get('auth_mode') == 'basic':
        value = (auth['auth_username'] + ':' + auth['auth_password']).encode('utf-8')
        authorization = 'Basic ' + base64.b64encode(value).decode('ascii')
    elif auth.get('auth_mode') == 'auto_token':
        cfg = dict(token_auth.DEFAULTS, **auth.get('auto_token', {}))
        token = item.get('_auto_token_value')
        if private and not token: raise OutboxError('自动 Token 尚未获取，已阻止发送')
        headers[cfg['token_header']] = cfg['token_prefix'] + token if private else '[已隐藏]'
    if authorization:
        headers['Authorization'] = authorization if private else '[已隐藏]'
    return headers


def _redact(value, auth=None, truncated=False):
    text = str(value or '')
    auth = auth or {}
    secrets = {str(auth.get(key) or '') for key in ('auth_username', 'auth_password', 'auth_token')}
    secrets.update(token_auth.secret_values(auth))
    if auth.get('auth_username') or auth.get('auth_password'):
        secrets.add(base64.b64encode((str(auth.get('auth_username') or '') + ':' +
            str(auth.get('auth_password') or '')).encode('utf-8')).decode('ascii'))
    variants = set()
    for secret in secrets - {''}:
        quoted = quote(secret, safe='')
        # Percent-escape hex digits are case insensitive; preserve the credential's own case.
        lower_escapes = re.sub(r'%[0-9A-F]{2}', lambda match: match[0].lower(), quoted)
        variants.update((secret, quoted, lower_escapes, json.dumps(secret, ensure_ascii=True)[1:-1],
                         json.dumps(secret, ensure_ascii=False)[1:-1]))
    for secret in sorted(variants, key=len, reverse=True):
        if truncated:
            # A byte limit can split an echoed credential; never expose its trailing prefix.
            for size in range(min(len(secret) - 1, len(text)), 0, -1):
                if text.endswith(secret[:size]):
                    text = text[:-size] + '[已隐藏]'
                    break
        text = text.replace(secret, '[已隐藏]')
    return text


def safe_receipt(headers=None, body=b'', auth=None, truncated=False):
    """Bound and redact receiver-controlled data before it reaches persistent storage."""
    if not isinstance(body, (bytes, str)):
        body = str(body)
    raw = body.encode('utf-8', errors='replace') if isinstance(body, str) else body
    was_truncated = bool(truncated or len(raw) > MAX_RECEIPT_BYTES)
    decoded = raw[:MAX_RECEIPT_BYTES].decode('utf-8', errors='replace')
    if was_truncated:
        # A split UTF-8 character at the boundary must not defeat credential-prefix redaction.
        decoded = decoded.rstrip('\ufffd')
    cleaned = _redact(decoded, auth, was_truncated)
    # Redaction can expand very short values. Bound the resulting text as well.
    encoded = cleaned.encode('utf-8')
    if len(encoded) > MAX_RECEIPT_BYTES:
        cleaned = encoded[:MAX_RECEIPT_BYTES].decode('utf-8', errors='ignore')
        was_truncated = True
    public_headers = {}
    header_total = 0
    for key, value in (headers.items() if hasattr(headers, 'items') else []):
        name = str(key).lower()
        if name not in SAFE_RESPONSE_HEADERS:
            continue
        value = _redact(str(value)[:4096], auth, len(str(value)) > 4096)
        value = ''.join(ch for ch in value if ord(ch) >= 32 and ord(ch) != 127)[:1024]
        if header_total + len(value.encode('utf-8')) > 8192:
            was_truncated = True
            break
        public_headers[name] = value
        header_total += len(value.encode('utf-8'))
    return {'response_headers': public_headers, 'response_body': cleaned,
            'response_truncated': was_truncated}


def delivery_details(delivery_id, before_attempt_id=None, limit=MAX_DETAIL_ATTEMPTS):
    if type(delivery_id) is not int or not 1 <= delivery_id <= 9223372036854775807:
        raise ValueError('推送记录编号必须为正整数')
    if before_attempt_id is not None and (type(before_attempt_id) is not int or not 1 <= before_attempt_id <= 9223372036854775807):
        raise ValueError('历史记录游标必须为正整数')
    if type(limit) is not int or not 1 <= limit <= MAX_DETAIL_ATTEMPTS:
        raise ValueError('每页尝试记录数量必须为 1 至 10 的整数')
    conn = _connect()
    try:
        conn.execute('BEGIN')
        row = conn.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
        if row is None:
            raise NotFound('推送记录不存在或已按保留规则清理')
        auth = json.loads(row['auth_json'])
        fields = ('id', 'event_key', 'kind', 'state', 'title', 'device_name', 'target_url', 'attempts',
                  'created_at', 'updated_at', 'next_attempt_at', 'last_http_status', 'last_error', 'sent_at')
        delivery = {key: row[key] for key in fields}
        delivery['last_error'] = _redact(delivery['last_error'], auth) or None
        key = row['event_key']
        source_type = 'kafka' if key.startswith('kafka:') else 'test' if key.startswith('test:') else \
            'manual' if key.startswith('manual:') else 'unknown'
        delivery['source'] = {'type': source_type, 'event_key': key}
        parameters = [delivery_id]
        clause = 'delivery_id=?'
        if before_attempt_id is not None:
            clause += ' AND id<?'
            parameters.append(before_attempt_id)
        attempts = []
        rows = list(conn.execute('SELECT * FROM delivery_attempts WHERE ' + clause +
            ' ORDER BY id DESC LIMIT ?', parameters + [limit + 1]))
        has_more = len(rows) > limit
        for attempt in rows[:limit]:
            result = dict(attempt)
            result.pop('owner', None)
            result.pop('delivery_id', None)
            result['request_headers'] = json.loads(result.pop('request_headers_json'))
            result['response_headers'] = json.loads(result.pop('response_headers_json'))
            result['response_truncated'] = bool(result['response_truncated'])
            result['business_success'] = None
            result['transport_accepted'] = result['outcome'] == 'http_accepted'
            attempts.append(result)
        total = conn.execute('SELECT COUNT(*) FROM delivery_attempts WHERE delivery_id=?',
                             (delivery_id,)).fetchone()[0]
        # platform-push-gateway-display-v1
        from native_alarm_push_urls import rewrite_request_json
        raw = row['payload_json']
        if row['kind'] == 'alarm':
            raw = rewrite_request_json(raw, STATE_DIR)
        return {'delivery': delivery, 'payload': json.loads(raw),
            'payload_json': row['payload_json'], 'attempts': attempts, 'attempts_total': total,
            'has_more': has_more, 'next_before_attempt_id': attempts[-1]['id'] if has_more else None,
            'history_note': '详细尝试记录从本功能上线起保存，历史尝试无法补造；每页最多 10 条，人工重试保留既有记录。成功记录与报警推送记录一起按保留规则清理，未处理失败记录保留。',
            'delivery_note': 'HTTP 2xx 只表示传输成功；业务是否入库请核对回执内容或接收端记录。Kafka 原始消息未保留，仅展示已转换并排队的报警。'}
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def snapshot():
    conn = _connect()
    try:
        conn.execute('BEGIN')
        settings = public_settings(_settings(conn))
        counts = {state: 0 for state in ('pending', 'sending', 'retry', 'failed', 'sent', 'quarantined')}
        counts.update({row['state']: row['amount'] for row in conn.execute(
            'SELECT state,COUNT(*) AS amount FROM deliveries GROUP BY state')})
        columns = '''id,kind,state,attempts,created_at,updated_at,next_attempt_at,last_http_status,
                     last_error,sent_at,title,device_name,target_url'''
        recent = [dict(row) for row in conn.execute('SELECT ' + columns + ' FROM deliveries ORDER BY id DESC LIMIT 50')]
        failures = [dict(row) for row in conn.execute('SELECT ' + columns +
            " FROM deliveries WHERE state IN ('failed','retry','quarantined') ORDER BY id DESC LIMIT 100")]
        worker = conn.execute('SELECT owner,pid,heartbeat_at,last_error FROM worker_status WHERE id=1').fetchone()
        worker = dict(worker) if worker else {'pid': None, 'heartbeat_at': None, 'last_error': None}
        worker.pop('owner', None)
        worker['healthy'] = bool(worker['heartbeat_at'] and time.time() - worker['heartbeat_at'] < 90)
        return {'settings': settings, 'counts': counts, 'recent': recent, 'failures': failures,
                'worker': worker, 'limits': {'max_pending': MAX_PENDING, 'max_attempts': MAX_ATTEMPTS,
                                           'min_free_bytes': MIN_FREE_BYTES},
                'storage': {'free_bytes': shutil.disk_usage(str(STATE_DIR)).free},
                'history_note': '成功记录保留最近 30 天及至少最近 2000 条；失败记录保留至处理。',
                'delivery_note': 'HTTP 2xx 只代表传输成功，不代表业务入库；接收端按 Idempotency-Key 去重可避免中断重试后的重复接收。'}
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def retry_failed(body):
    if not isinstance(body, dict) or set(body) - {'ids', 'all_failed'}:
        raise ValueError('重试参数不正确')
    ids = body.get('ids', [])
    all_failed = body.get('all_failed', False)
    if type(all_failed) is not bool or not isinstance(ids, list) or len(ids) > 1000 or any(type(i) is not int or i < 1 for i in ids):
        raise ValueError('请选择有效的失败记录，单次最多 1000 条')
    if bool(ids) == all_failed:
        raise ValueError('请选择记录或全部失败记录')
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        settings = _settings(conn)
        clause = "state IN ('failed','retry') AND kind IN ('alarm','test')"
        params = [time.time(), time.time(), settings['target_url'], json.dumps(_auth(settings))]
        if not all_failed:
            clause += ' AND id IN (' + ','.join('?' for _ in ids) + ')'
            params.extend(ids)
        cursor = conn.execute("UPDATE deliveries SET state='pending',attempts=0,token_refreshes=0,updated_at=?,next_attempt_at=?,"
                              'target_url=?,auth_json=?,claim_owner=NULL,lease_until=NULL WHERE ' + clause, params)
        count = cursor.rowcount
        conn.commit()
        return {'retried': count, 'target_url': settings['target_url'], 'enabled': settings['enabled']}
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def delete_failed(body):
    if not isinstance(body, dict) or set(body) != {'ids'}:
        raise ValueError('请选择要删除的推送记录')
    ids = body['ids']
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(
            type(i) is not int or not 1 <= i <= 9223372036854775807 for i in ids):
        raise ValueError('请选择有效的记录编号，单次最多 200 条')
    ids = list(dict.fromkeys(ids))
    placeholders = ','.join('?' for _ in ids)
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute('SELECT state FROM deliveries WHERE id IN (' + placeholders + ')', ids).fetchall()
        if any(row['state'] not in ('retry', 'failed') for row in existing):
            raise Conflict('只能删除等待重试或需处理的记录，请刷新后重新选择')
        # delivery_keys stays intact so Kafka replays cannot recreate a deleted delivery.
        if existing:
            conn.execute('DELETE FROM delivery_attempts WHERE delivery_id IN (' + placeholders + ')', ids)
            deleted = conn.execute("DELETE FROM deliveries WHERE state IN ('retry','failed') AND id IN (" + placeholders + ')', ids).rowcount
        else:
            deleted = 0
        conn.commit()
        return {'deleted': deleted, 'requested': len(ids), 'absent': len(ids) - deleted}
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def worker_heartbeat(owner, error=None):
    conn = _connect()
    try:
        conn.execute('INSERT OR REPLACE INTO worker_status VALUES(1,?,?,?,?)',
                     (owner, os.getpid(), time.time(), error))
    finally:
        conn.close()


def recover_abandoned(owner):
    """Called only after acquiring the process-wide OS file lock."""
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE delivery_attempts SET finished_at=?,outcome='interrupted',"
            "error='发送进程中断，接收结果未知；后续重试可能重复接收' WHERE finished_at IS NULL "
            "AND delivery_id IN (SELECT id FROM deliveries WHERE state='sending')", (time.time(),))
        conn.execute("UPDATE deliveries SET state='retry',next_attempt_at=?,updated_at=?,claim_owner=NULL,"
                     "lease_until=NULL,last_error='发送进程中断，等待重试' WHERE state='sending'",
                     (time.time(), time.time()))
        conn.commit()
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def claim_next(owner):
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        settings = _settings(conn)
        if not settings['enabled']:
            conn.commit()
            return None
        now = time.time()
        row = conn.execute("SELECT * FROM deliveries WHERE state IN ('pending','retry') AND next_attempt_at<=? "
                           'ORDER BY next_attempt_at,id LIMIT 1', (now,)).fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute("UPDATE deliveries SET state='sending',attempts=attempts+1,updated_at=?,claim_owner=?,"
                     'lease_until=? WHERE id=?', (now, owner, now + 120, row['id']))
        item = dict(row)
        item['attempts'] += 1
        item['claim_owner'] = owner
        item['timeout_seconds'] = settings['timeout_seconds']
        item['payload'] = json.loads(item['payload_json'])
        item['auth'] = json.loads(item.pop('auth_json'))
        # Persist the actual UTF-8 request representation and hash before the sender may run.
        # platform-push-gateway-media-v1
        from native_alarm_push_urls import rewrite_request_json
        raw = item['payload_json']
        if item['kind'] == 'alarm':
            raw = rewrite_request_json(raw, STATE_DIR, recipient_delivery=True)
        if raw != item['payload_json']:
            item['payload'] = json.loads(raw)
        if item['kind'] == 'alarm':
            from alarm_push_type_code import rewrite_insert_ai_type_code
            mapped = rewrite_insert_ai_type_code(raw, item['payload'], item['target_url'])
            if mapped != raw:
                raw = mapped
                item['payload'] = json.loads(raw)
        recorded_no = conn.execute('SELECT COALESCE(MAX(attempt_no),0) FROM delivery_attempts '
            'WHERE delivery_id=?', (item['id'],)).fetchone()[0]
        # Retain known legacy retry counts without inventing absent legacy attempt records.
        attempt_no = max(recorded_no, item['attempts'] - 1) + 1
        cursor = conn.execute('''INSERT INTO delivery_attempts
            (delivery_id,attempt_no,owner,started_at,target_url,request_json,request_sha256,request_headers_json)
            VALUES(?,?,?,?,?,?,?,?)''', (item['id'], attempt_no, owner, now, item['target_url'], raw,
            hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            json.dumps(request_headers(item), ensure_ascii=False)))
        item['attempt_id'] = cursor.lastrowid
        conn.commit()
        return item
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def prepared_request(item):
    """Fail closed if a sender is handed an uncommitted, stale, or modified request."""
    conn = _connect()
    try:
        attempt = conn.execute('''SELECT a.*,d.auth_json AS delivery_auth_json FROM delivery_attempts a JOIN deliveries d ON d.id=a.delivery_id
            WHERE a.id=? AND a.delivery_id=? AND a.owner=? AND a.finished_at IS NULL
            AND d.state='sending' AND d.claim_owner=a.owner''',
            (item.get('attempt_id'), item['id'], item.get('claim_owner'))).fetchone()
        if attempt is None or attempt['target_url'] != item['target_url'] or \
                json.loads(attempt['delivery_auth_json']) != item.get('auth') or \
                attempt['request_headers_json'] != json.dumps(request_headers(item), ensure_ascii=False):
            raise OutboxError('发送请求与持久化记录不一致，已阻止发送')
        raw = attempt['request_json'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest() != attempt['request_sha256']:
            raise OutboxError('持久化发送请求校验失败，已阻止发送')
        return raw
    finally:
        conn.close()


def finish_attempt(owner, item, status=None, error=None, retryable=True, receipt=None):
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        now = time.time()
        successful = status is not None and 200 <= status < 300 and not error
        state = 'sent' if successful else 'retry' if retryable and item['attempts'] < MAX_ATTEMPTS else 'failed'
        refresh_requested = bool(item.get('_token_refresh_requested'))
        delay = 0 if refresh_requested else min(3600, 5 * (2 ** min(item['attempts'] - 1, 10)))
        cursor = conn.execute('''UPDATE deliveries SET state=?,updated_at=?,next_attempt_at=?,
            last_http_status=?,last_error=?,sent_at=?,claim_owner=NULL,lease_until=NULL,token_refreshes=token_refreshes+?
            WHERE id=? AND state='sending' AND claim_owner=?''',
            (state, now, now + delay, status, None if successful else _safe_label(_redact(error or '接收端返回错误', item.get('auth'))),
             now if successful else None, int(refresh_requested), item['id'], owner))
        if cursor.rowcount != 1:
            raise OutboxError('发送结果归属已变化，未覆盖现有状态')
        receipt = receipt if receipt is not None else item.get('receipt', {})
        private_auth = dict(item.get('auth') or {}, _runtime_secrets=item.get('_runtime_secrets', []))
        safe = safe_receipt(receipt.get('response_headers', {}), receipt.get('response_body', ''),
                            private_auth, receipt.get('response_truncated', False))
        outcome = 'http_accepted' if successful else 'http_error' if status is not None else 'transport_error'
        attempt = conn.execute('''UPDATE delivery_attempts SET finished_at=?,response_status=?,
            response_headers_json=?,response_body=?,response_truncated=?,error=?,outcome=?
            WHERE id=? AND delivery_id=? AND owner=? AND finished_at IS NULL''',
            (now, status, json.dumps(safe['response_headers'], ensure_ascii=False), safe['response_body'],
             int(safe['response_truncated']), _redact(error or receipt.get('capture_error'), item.get('auth'))[:4096] or None, outcome,
             item.get('attempt_id'), item['id'], owner))
        if attempt.rowcount != 1:
            raise OutboxError('发送尝试归属已变化，未覆盖现有记录')
        conn.commit()
        return state
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def prune_sent():
    conn = _connect()
    try:
        # Permanent key tombstones retain Kafka deduplication after payload cleanup.
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("DELETE FROM delivery_attempts WHERE delivery_id IN (SELECT id FROM deliveries "
                     "WHERE state='sent' AND sent_at<? AND id NOT IN "
                     "(SELECT id FROM deliveries WHERE state='sent' ORDER BY id DESC LIMIT 2000))",
                     (time.time() - 30 * 86400,))
        conn.execute("DELETE FROM deliveries WHERE state='sent' AND sent_at<? AND id NOT IN "
                     "(SELECT id FROM deliveries WHERE state='sent' ORDER BY id DESC LIMIT 2000)",
                     (time.time() - 30 * 86400,))
        conn.commit()
        conn.execute('PRAGMA wal_checkpoint(PASSIVE)')
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()
