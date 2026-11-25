"""Configurable token login/renewal. Tokens remain in the supervised worker's memory."""
import base64
import hashlib
import json
import re
import socket
import ssl
import time
from urllib import request, error, parse

DEFAULTS = dict(login_url='', method='POST', body_format='json',
    body_json='{"username":"{{username}}","password":"{{password}}"}', headers_json='{}',
    token_path='data.access_token', expires_path='', ttl_seconds=3600, renew_before_seconds=60,
    token_header='Authorization', token_prefix='Bearer ', refresh_url='',
    refresh_body_json='{"refresh_token":"{{refresh_token}}"}', refresh_token_path='')
PRIVATE_FIELDS = ('body_json', 'headers_json', 'refresh_body_json')
HEADER = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
BLOCKED_HEADERS = {'host', 'content-length', 'connection', 'transfer-encoding', 'cookie', 'set-cookie',
                   'idempotency-key', 'x-platform-delivery-id', 'content-type', 'accept'}


class TokenError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def object_json(value, label):
    if not isinstance(value, str) or len(value.encode('utf-8')) > 16384:
        raise ValueError(label + '须为不超过 16 KiB 的 JSON 对象')
    try:
        result = json.loads(value)
    except (ValueError, TypeError):
        raise ValueError(label + '须为有效的 JSON 对象') from None
    if not isinstance(result, dict):
        raise ValueError(label + '须为 JSON 对象')
    return result


def config(value, previous, validate_url, complete=True):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('自动 Token 配置项不正确')
    result = dict(DEFAULTS, **(previous or {}))
    for key, val in value.items():
        if key in PRIVATE_FIELDS and val == '': continue  # blank preserves a saved secret
        result[key] = val
    for key in ('login_url', 'refresh_url'):
        if result[key]: result[key] = validate_url(result[key])
        elif not isinstance(result[key], str): raise ValueError('登录/刷新地址格式不正确')
    if complete and not result['login_url']:
        raise ValueError('请填写 Token 登录接口地址；接口尚未确认时可暂停推送后保存草稿')
    if result['method'] not in ('POST', 'GET') or result['body_format'] not in ('json', 'form'):
        raise ValueError('登录方法或参数格式不正确')
    for key in ('token_path', 'expires_path', 'refresh_token_path'):
        path = result[key]
        if not isinstance(path, str) or len(path) > 256 or (path and not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', path)):
            raise ValueError('返回字段请填写以点分隔的字段路径，例如 data.access_token')
    if not result['token_path']: raise ValueError('请填写 Token 返回字段')
    for key, low, high in [('ttl_seconds', 1, 604800), ('renew_before_seconds', 0, 3600)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError('Token 有效期须为 1 至 604800 秒，提前更新时间须为 0 至 3600 秒')
    name, prefix = result['token_header'], result['token_prefix']
    if not isinstance(name, str) or not HEADER.fullmatch(name) or name.lower() in BLOCKED_HEADERS:
        raise ValueError('Token 请求头名称不正确或与报警请求的保留字段冲突')
    if not isinstance(prefix, str) or len(prefix) > 128 or any(ord(c) < 32 or ord(c) > 126 for c in prefix):
        raise ValueError('Token 前缀只能包含可见 ASCII 字符和空格')
    for key in PRIVATE_FIELDS:
        values = object_json(result[key], '登录/刷新参数或请求头')
        if key == 'headers_json':
            for name, val in values.items():
                if not HEADER.fullmatch(name) or name.lower() in BLOCKED_HEADERS or not isinstance(val, str) or len(val) > 4096 or any(ord(c) < 32 or ord(c) > 126 for c in val):
                    raise ValueError('登录请求头名称或值不正确')
        def check(val):
            if isinstance(val, dict):
                for child in val.values(): check(child)
            elif isinstance(val, list):
                for child in val: check(child)
            elif isinstance(val, str):
                for placeholder in re.findall(r'\{\{([^{}]+)\}\}', val):
                    if placeholder not in ('username', 'password', 'refresh_token'):
                        raise ValueError('仅支持 {{username}}、{{password}}、{{refresh_token}} 占位符')
        check(values)
    if result['body_format'] == 'form' or result['method'] == 'GET':
        for key in ('body_json', 'refresh_body_json'):
            if any(isinstance(v, (dict, list)) for v in object_json(result[key], '表单参数').values()):
                raise ValueError('表单和 GET 参数仅支持一层字段')
    return result


def public(value):
    original = value or {}
    value = dict(DEFAULTS, **original)
    return dict({key: val for key, val in value.items() if key not in PRIVATE_FIELDS},
                **{key + '_configured': bool(original.get(key)) for key in PRIVATE_FIELDS})


def secret_values(auth):
    result = set()
    cfg = auth.get('auto_token') or {}
    def visit(val):
        if isinstance(val, dict):
            for child in val.values(): visit(child)
        elif isinstance(val, list):
            for child in val: visit(child)
        elif isinstance(val, str) and val and '{{' not in val:
            result.add(val)
    for key in PRIVATE_FIELDS:
        try: visit(json.loads(cfg.get(key, '{}')))
        except (ValueError, TypeError): pass
    result.update(auth.get('_runtime_secrets') or [])
    return result


def field(body, path):
    for key in path.split('.'):
        if isinstance(body, dict): body = body.get(key)
        elif isinstance(body, list) and key.isdigit() and int(key) < len(body): body = body[int(key)]
        else: return None
    return body


def expand(val, credentials):
    if isinstance(val, dict): return {k: expand(v, credentials) for k, v in val.items()}
    if isinstance(val, list): return [expand(v, credentials) for v in val]
    if isinstance(val, str):
        return re.sub(r'\{\{(username|password|refresh_token)\}\}', lambda m: credentials.get(m[1], ''), val)
    return val


class TokenManager:
    def __init__(self):
        self.cache = {}
        self.failures = {}

    def key(self, auth):
        return hashlib.sha256(json.dumps(auth, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    def invalidate(self, auth, token):
        entry = self.cache.get(self.key(auth))
        if entry and entry['token'] == token: entry['deadline'] = 0

    def get(self, auth, timeout=5):
        key, now = self.key(auth), time.monotonic()
        entry = self.cache.get(key)
        if entry and entry['deadline'] > now: return entry['token']
        failure = self.failures.get(key)
        if failure and failure[0] > now: raise TokenError(*failure[1:])
        cfg = dict(DEFAULTS, **auth.get('auto_token', {}))
        if not cfg['login_url']: raise TokenError('自动 Token 登录接口尚未配置，请完善配置后重试')
        try:
            if entry and entry.get('refresh') and cfg['refresh_url']:
                try: fresh = self.fetch(auth, cfg, timeout, entry['refresh'])
                except TokenError as exc:
                    if exc.retryable: raise
                    fresh = self.fetch(auth, cfg, timeout)
            else: fresh = self.fetch(auth, cfg, timeout)
        except TokenError as exc:
            self.failures[key] = (now + 30, str(exc), exc.retryable)
            raise
        if len(self.cache) > 32: self.cache.clear()
        if len(self.failures) > 32: self.failures.clear()
        self.cache[key] = fresh
        self.failures.pop(key, None)
        return fresh['token']

    def secrets(self, auth):
        entry = self.cache.get(self.key(auth)) or {}
        return [v for v in (entry.get('token'), entry.get('refresh')) if v]

    def fetch(self, auth, cfg, timeout, refresh=None):
        credentials = dict(username=auth.get('auth_username', ''), password=auth.get('auth_password', ''), refresh_token=refresh or '')
        data = expand(object_json(cfg['refresh_body_json'] if refresh else cfg['body_json'], '登录参数'), credentials)
        headers = expand(object_json(cfg['headers_json'], '登录请求头'), credentials)
        url = cfg['refresh_url'] if refresh else cfg['login_url']
        method = 'POST' if refresh else cfg['method']
        if method == 'GET':
            url += '?' + parse.urlencode(data); raw = None
        elif cfg['body_format'] == 'form':
            raw = parse.urlencode(data).encode(); headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode(); headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        started = time.monotonic()
        try:
            with opener.open(request.Request(url, data=raw, headers=headers, method=method), timeout=timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536: raise TokenError('Token 接口返回内容超过 64 KiB，请核对接口')
                body = json.loads(raw.decode('utf-8'))
        except error.HTTPError as exc:
            status = exc.code; exc.close()
            raise TokenError('Token 接口返回 HTTP ' + str(status) + '，请检查登录参数和权限', status in (408, 425, 429) or status >= 500) from None
        except (ssl.SSLError, error.URLError, OSError, ValueError) as exc:
            retryable = isinstance(exc, (OSError, error.URLError)) and not isinstance(getattr(exc, 'reason', exc), ssl.SSLError)
            raise TokenError('Token 接口连接、证书或返回 JSON 异常，请核对登录接口配置', retryable) from None
        if isinstance(body, dict) and str(body.get('code')) in ('401', '403'):
            raise TokenError('Token 接口拒绝登录，请检查账号密码和登录参数')
        token = field(body, cfg['token_path'])
        if not isinstance(token, str) or not token or len(token) > 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise TokenError('Token 返回字段不存在或内容不正确，请核对字段路径')
        ttl = cfg['ttl_seconds']
        if cfg['expires_path']:
            value = field(body, cfg['expires_path'])
            try: ttl = float(value)
            except (TypeError, ValueError): raise TokenError('Token 有效期返回字段不是秒数，请核对字段路径') from None
            if not 0 < ttl <= 604800: raise TokenError('Token 返回的有效期超出范围（1 至 604800 秒）')
        # JWT exp is an upper bound only; the receiver remains responsible for verification.
        try:
            part = token.split('.')[1]; claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
            exp = float(claims['exp']) - time.time()
            ttl = min(ttl, exp)
        except (IndexError, ValueError, TypeError, KeyError): pass
        if ttl <= 0: raise TokenError('Token 接口返回的令牌已过期')
        margin = min(cfg['renew_before_seconds'], ttl * 0.2)
        refreshed = field(body, cfg['refresh_token_path']) if cfg['refresh_token_path'] else None
        return dict(token=token, refresh=refreshed if isinstance(refreshed, str) else refresh,
                    deadline=started + ttl - margin)
