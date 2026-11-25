# aiplatform-hik-connection-test-v1
"""Shared client for Hikvision's Artemis catalog and RTSP APIs."""

import base64
import hashlib
import hmac
import json
import re
import socket
import ssl
import threading
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import (HTTPRedirectHandler, HTTPSHandler, ProxyHandler,
                            Request, build_opener)


_HTTP_TIMEOUT = 5
_MAX_RESPONSE = 8 * 1024 * 1024
_MAX_PAGES = 1000
_CACHE_TTL = 180
_CACHE_LIMIT = 1024
_ROUTE_CODES = {'403', '404', '405', '501'}
_ARTEMIS_ROUTE_CODES = _ROUTE_CODES | {'0x02401008', '0x0240103a'}
_CATALOG_UNAVAILABLE = '海康安防平台接口不可用，请检查组件和接口授权'
_VNSC_PREVIEW = '/api/vnsc/mls/v1/preview/openApi/getPreviewParam'
_ARTEMIS_PREVIEW = '/api/video/v1/cameras/previewURLs'
_ARTEMIS_V2_PREVIEW = '/api/video/v2/cameras/previewURLs'
_CACHE = {}
_PENDING = {}
_LOCK = threading.Lock()


class HikGatewayError(ValueError):
    """An error safe to display or log without request or response contents."""

    def __init__(self, message, reason='gateway'):
        super().__init__(message)
        self.reason = reason


class _RouteUnavailable(HikGatewayError):
    pass


def _connection_error(error):
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, ConnectionRefusedError):
        return HikGatewayError('海康安防平台拒绝连接，请核对协议和端口', 'connection_refused')
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return HikGatewayError('海康安防平台连接或响应超时，请检查网络和网关状态', 'timeout')
    if isinstance(reason, socket.gaierror):
        return HikGatewayError('无法解析海康安防平台地址，请检查域名和 DNS', 'dns')
    if isinstance(reason, ssl.SSLError):
        return HikGatewayError('海康安防平台 TLS 握手失败，请核对 HTTPS 端口和证书配置', 'tls')
    return HikGatewayError('海康安防平台连接失败，请检查配置地址和网络', 'connection')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _field(config, *names):
    for name in names:
        value = config.get(name) if isinstance(config, dict) else getattr(config, name, None)
        if value is not None and value != '':
            return value
    return None


def _stream_number(value):
    stream = {'0': 0, '1': 0, '2': 1, 'main': 0, 'sub': 1}.get(str(value))
    if stream is None:
        raise HikGatewayError('安防平台码流类型必须为主码流或子码流')
    return stream


def _code(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise HikGatewayError('安防平台资源编号无效')
    return value.strip()


def _number(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and len(value) <= 9 and re.fullmatch(r'[0-9]+', value):
        return int(value)
    raise HikGatewayError('安防平台返回的分页信息无效')


def _valid_rtsp(url):
    if (not isinstance(url, str) or not url or len(url) > 65536 or
            url != url.strip() or any(ord(char) < 32 or ord(char) == 127 for char in url)):
        raise HikGatewayError('海康安防平台未返回有效 RTSP 视频地址')
    try:
        parsed = urlsplit(url)
        port = parsed.port
        if (parsed.scheme not in ('rtsp', 'rtsps') or not parsed.hostname or
                (port is not None and not 0 < port <= 65535)):
            raise ValueError()
    except ValueError:
        raise HikGatewayError('海康安防平台未返回有效 RTSP 视频地址') from None
    return url


def _empty_catalog(result):
    data = result.get('data')
    if not isinstance(data, dict):
        return False
    if 'total' in data:
        return _number(data['total']) == 0 and data.get('list', []) == []
    return data.get('list') == []


def _preview_url(result):
    data = result.get('data')
    return data.get('url') if isinstance(data, dict) else None


def _missing_preview(result):
    try:
        _valid_rtsp(_preview_url(result))
    except HikGatewayError:
        return True
    return False


class HikGateway:
    def __init__(self, config):
        try:
            raw_host = str(_field(config, 'hik_host', 'host') or '').strip()
            configured_scheme = str(_field(config, 'hik_scheme', 'scheme') or '').lower()
            parsed = urlsplit(raw_host if '://' in raw_host else '//' + raw_host)
            if (not parsed.hostname or parsed.username is not None or parsed.password is not None or
                    parsed.path not in ('', '/') or parsed.query or parsed.fragment or
                    re.search(r'[\s\\]', parsed.hostname)):
                raise ValueError()
            raw_port = _field(config, 'hik_port', 'port')
            port = _number(raw_port) if raw_port is not None else parsed.port
            if parsed.port is not None and port != parsed.port:
                raise ValueError()
            if configured_scheme and parsed.scheme and configured_scheme != parsed.scheme:
                raise ValueError()
            scheme = parsed.scheme or configured_scheme or {80: 'http', 443: 'https', None: 'https'}.get(port)
            if scheme is None and 0 < port <= 65535:
                raise HikGatewayError('使用非标准端口时，请选择 HTTP 或 HTTPS', 'scheme_required')
            if scheme not in ('http', 'https') or (port is not None and not 0 < port <= 65535):
                raise ValueError()
            port = port if port is not None else (80 if scheme == 'http' else 443)
            prefix = str(_field(config, 'hik_artemis', 'artemis') or 'artemis').strip('/')
            if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', prefix):
                raise ValueError()
            self.app_key = _field(config, 'hik_appKey', 'app_key')
            self.app_secret = _field(config, 'hik_appSecret', 'app_secret')
            if (not isinstance(self.app_key, str) or not re.fullmatch(r'[!-~]{1,512}', self.app_key) or
                    not isinstance(self.app_secret, str) or not 1 <= len(self.app_secret) <= 1024):
                raise ValueError()
        except HikGatewayError as error:
            if error.reason == 'scheme_required':
                raise
            raise HikGatewayError('海康安防平台端口无效，请填写 1 到 65535 的整数', 'invalid_config') from None
        except ValueError:
            raise HikGatewayError('海康安防平台地址、端口或授权配置无效', 'invalid_config') from None

        authority = '[{}]'.format(parsed.hostname) if ':' in parsed.hostname else parsed.hostname
        self.host = '{}://{}'.format(scheme, authority)
        if len(self.host) > 50:
            raise HikGatewayError('海康安防平台地址过长，请使用 IP 或较短的域名', 'invalid_config')
        self.port = port
        self.origin = '{}:{}'.format(self.host, self.port)
        self.prefix = '/' + prefix
        self._fingerprint = hashlib.sha256(
            json.dumps([self.origin, self.prefix, self.app_key, self.app_secret]).encode()).digest()

    def post(self, api, payload):
        if not re.fullmatch(r'/api(?:/[A-Za-z0-9_-]+)+', api):
            raise HikGatewayError('海康安防平台接口路径无效')
        path = self.prefix + api
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        message = ('POST\n*/*\napplication/json\nx-ca-key:{}\nx-ca-nonce:{}\n'
                   'x-ca-timestamp:{}\n{}').format(self.app_key, nonce, timestamp, path)
        signature = base64.b64encode(hmac.new(self.app_secret.encode(), message.encode(),
                                               hashlib.sha256).digest()).decode('ascii')
        request = Request(self.origin + path, data=json.dumps(payload).encode(), method='POST', headers={
            'Accept': '*/*', 'Content-Type': 'application/json', 'X-Ca-Key': self.app_key,
            'X-Ca-Nonce': nonce, 'X-Ca-Timestamp': timestamp, 'X-Ca-Signature': signature,
            'X-Ca-Signature-Headers': 'x-ca-key,x-ca-nonce,x-ca-timestamp',
        })
        # Keep compatibility with existing installations using a self-signed gateway certificate.
        context = ssl._create_unverified_context()
        opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=context))
        try:
            with opener.open(request, timeout=_HTTP_TIMEOUT) as response:
                if response.status != 200:
                    raise HikGatewayError('海康安防平台请求失败，请检查服务和授权')
                body = response.read(_MAX_RESPONSE + 1)
        except HTTPError as error:
            status = str(error.code)
            error.close()
            if status in ('301', '302', '303', '307', '308'):
                raise HikGatewayError(
                    '海康安防平台返回跳转（HTTP {}），请填写实际网关的协议和端口'.format(status),
                    'redirect') from None
            if status == '401':
                raise HikGatewayError('海康安防平台拒绝认证（HTTP 401），请核对应用凭据和授权',
                                      'authentication') from None
            if status in _ROUTE_CODES:
                reason = 'permission' if status == '403' else 'route'
                raise _RouteUnavailable(_CATALOG_UNAVAILABLE, reason) from None
            raise HikGatewayError('海康安防平台请求失败（HTTP {}）'.format(status), 'http') from None
        except OSError as error:
            raise _connection_error(error) from None
        try:
            result = json.loads(body.decode('utf-8-sig')) if len(body) <= _MAX_RESPONSE else None
        except (ValueError, UnicodeError):
            result = None
        if not isinstance(result, dict) or type(result.get('code')) not in (str, int):
            raise HikGatewayError('海康安防平台返回数据格式无效')
        code = str(result['code']).lower()
        if code == '0x02401003':
            raise HikGatewayError('海康安防平台签名校验失败，请核对 AppKey、AppSecret 和两端时间', 'invalid_signature')
        if code in _ARTEMIS_ROUTE_CODES:
            reason = 'permission' if code == '403' else 'route'
            raise _RouteUnavailable(_CATALOG_UNAVAILABLE, reason)
        if code != '0':
            raise HikGatewayError('海康安防平台业务请求失败，请检查接口权限和参数')
        return result

    def _compatible(self, candidates, try_next):
        fallback = None
        permission_denied = False
        for api, payload in candidates:
            try:
                response = self.post(api, payload)
            except _RouteUnavailable as error:
                permission_denied = permission_denied or error.reason == 'permission'
                continue
            selected = (api, payload, response)
            if not try_next(response):
                return selected
            if fallback is None:
                fallback = selected
        if fallback is not None:
            return fallback
        if permission_denied:
            raise HikGatewayError('海康安防平台拒绝访问，请核对应用的接口授权', 'permission')
        raise HikGatewayError(_CATALOG_UNAVAILABLE, 'route')

    def _catalog(self, candidates, kind):
        api, payload, response = self._compatible(candidates, _empty_catalog)
        page = payload['pageNo']
        rows = []
        seen = set()
        expected_total = None
        for _ in range(_MAX_PAGES):
            data = response.get('data')
            if not isinstance(data, dict):
                raise HikGatewayError('海康安防平台返回的资源清单无效')
            if 'pageNo' in data and _number(data['pageNo']) != page:
                raise HikGatewayError('海康安防平台返回了错误的资源页码')
            if 'total' in data:
                total = _number(data['total'])
                if expected_total is not None and expected_total != total:
                    raise HikGatewayError('海康安防平台资源数量在分页期间发生变化')
                expected_total = total
            items = data.get('list', [] if expected_total == 0 else None)
            if not isinstance(items, list):
                raise HikGatewayError('海康安防平台返回的资源清单无效')
            for item in items:
                if not isinstance(item, dict):
                    raise HikGatewayError('海康安防平台返回的资源清单无效')
                code = _code(item.get('indexCode') or item.get(kind + 'IndexCode'))
                name = item.get('name') or item.get(kind + 'Name')
                if code in seen or not isinstance(name, str) or not name.strip():
                    raise HikGatewayError('海康安防平台资源编号重复或名称无效')
                seen.add(code)
                rows.append(dict(item, indexCode=code, name=name.strip()))
            if expected_total is not None and payload['pageNo'] == 1:
                if len(rows) == expected_total:
                    return rows
                if len(rows) > expected_total or not items:
                    raise HikGatewayError('海康安防平台资源清单不完整')
            elif not items or (data.get('pageSize') and len(items) < _number(data['pageSize'])):
                return rows
            page += 1
            response = self.post(api, dict(payload, pageNo=page))
        raise HikGatewayError('海康安防平台资源分页超过上限')

    @staticmethod
    def _region_candidates(pagination, resource_type):
        return (('/api/irds/v2/region/nodesByParams', dict(pagination, resourceType=resource_type)),
                ('/api/resource/v1/regions', pagination))

    @staticmethod
    def _camera_candidates(pagination, region):
        shared = dict(pagination, authCodes=['view'])
        return (('/api/irds/v2/resource/subResources',
                 dict(shared, regionIndexCode=region, cascadeFlag=0, resourceType='camera')),
                ('/api/resource/v2/camera/search',
                 dict(shared, regionIndexCodes=[region], isSubRegion=False)))

    def regions(self, page_no=1, page_size=1000, resource_type='region'):
        candidates = self._region_candidates(self._pagination(page_no, page_size), resource_type)
        return self._catalog(candidates, 'region')

    def cameras(self, region_code, page_no=1, page_size=1000):
        candidates = self._camera_candidates(self._pagination(page_no, page_size), _code(region_code))
        return self._catalog(candidates, 'camera')

    def _probe_catalog(self, candidates):
        _, _, response = self._compatible(candidates, _empty_catalog)
        data = response.get('data')
        if not isinstance(data, dict):
            raise HikGatewayError('海康安防平台返回的资源清单无效', 'catalog')
        total = _number(data['total']) if 'total' in data else None
        items = data.get('list', [] if total == 0 else None)
        if (not isinstance(items, list) or (total == 0 and items)
                or (total is not None and total > 0 and not items)):
            raise HikGatewayError('海康安防平台返回的资源清单无效', 'catalog')
        return total, items

    def test_connection(self):
        """Check signed catalog access, looking at at most one page per route."""
        pagination = self._pagination(1, 1)
        count, regions = self._probe_catalog(self._region_candidates(pagination, 'region'))
        camera_count = None
        if regions:
            region = regions[0]
            if not isinstance(region, dict):
                raise HikGatewayError('海康安防平台返回的区域信息无效', 'catalog')
            code = _code(region.get('indexCode') or region.get('regionIndexCode'))
            camera_count, _ = self._probe_catalog(self._camera_candidates(pagination, code))
        return {'origin': self.origin, 'region_count': count, 'camera_count': camera_count}

    @staticmethod
    def _pagination(page_no, page_size):
        page_no, page_size = _number(page_no), _number(page_size)
        if page_no < 1 or not 1 <= page_size <= 1000:
            raise HikGatewayError('安防平台资源分页参数无效')
        return {'pageNo': page_no, 'pageSize': page_size}

    def _preview_source(self, result, authenticated=False):
        url = _valid_rtsp(_preview_url(result))
        parsed = urlsplit(url)
        if parsed.port != 8604 or parsed.username is not None:
            return url
        # Application credentials belong to the configured Hikvision gateway.
        # Authorize the observed proprietary port without redistributing the
        # application's secret to a different host returned by the gateway.
        if not authenticated or parsed.hostname != urlsplit(self.origin).hostname:
            raise HikGatewayError('海康安防平台返回未经确认的 8604 视频地址', 'media_authority')
        scheme, sep, location = url.partition('://')
        user = quote(self.app_key, safe='')
        secret = quote(self.app_secret, safe='')
        # Keep the gateway's signed path and the original query octets intact.
        return scheme + sep + user + ':' + secret + '@' + location

    def _preview(self, index, stream):
        shared = {'transmode': 1, 'streamType': stream, 'protocol': 'rtsp'}
        rtp = dict(shared, cameraIndexCode=index, expand='streamform=rtp')
        preferred = (
            (_ARTEMIS_V2_PREVIEW, {'transmode': 1, 'streamType': stream,
                                   'cameraIndexCode': index, 'expand': 'expireTime=-1&transcode=0',
                                   'streamform': 'ps'}, True),
            (_ARTEMIS_V2_PREVIEW, rtp, False),
        )
        legacy = (
            (_VNSC_PREVIEW, dict(shared, indexCode=index, expireTime=-1, expand='streamform=rtp'), False),
            (_ARTEMIS_PREVIEW, rtp, False),
        )
        unavailable = set()
        last_error = None
        for attempt in range(3):
            candidates = preferred + legacy if attempt == 0 else legacy
            for api, payload, use_digest in candidates:
                if api in unavailable:
                    continue
                try:
                    return self._preview_source(self.post(api, payload), authenticated=use_digest)
                except _RouteUnavailable:
                    unavailable.add(api)
                except HikGatewayError as error:
                    if error.reason in ('authentication', 'invalid_signature'):
                        raise
                    last_error = error
            if all(api in unavailable for api, _, _ in legacy):
                return self._preview_source(self.post(_ARTEMIS_PREVIEW,
                    dict(shared, cameraIndexCode=index, expand='streamform=ps')))
            if attempt < 2:
                time.sleep(0.2)
        raise last_error or HikGatewayError('海康安防平台未提供可用视频')

    def preview(self, index_code, stream_type='1', force_refresh=False):
        index = _code(index_code)
        stream = _stream_number(stream_type)
        key = (self._fingerprint, index, stream)
        with _LOCK:
            now = time.monotonic()
            cached = _CACHE.get(key)
            if not force_refresh and cached and cached[0] > now:
                return cached[1]
            pending = _PENDING.get(key)
            if pending is None:
                for expired in [item for item, value in _CACHE.items() if value[0] <= now]:
                    _CACHE.pop(expired)
                if key not in _CACHE and len(_CACHE) + len(_PENDING) >= _CACHE_LIMIT:
                    raise HikGatewayError('海康安防平台取流缓存已达容量，请稍后重试')
                pending = _PENDING[key] = {'event': threading.Event(), 'url': None, 'error': None}
                owner = True
            else:
                owner = False
        if not owner:
            if not pending['event'].wait(9 * _HTTP_TIMEOUT + 2):
                raise HikGatewayError('海康安防平台取流超时，请稍后重试')
            if pending['error'] is not None:
                raise HikGatewayError(pending['error'])
            return pending['url']
        try:
            url = self._preview(index, stream)
            with _LOCK:
                _CACHE[key] = (time.monotonic() + _CACHE_TTL, url)
                pending['url'] = url
            return url
        except HikGatewayError as error:
            pending['error'] = str(error)
            raise
        except Exception:
            pending['error'] = '海康安防平台取流失败，请检查平台配置'
            raise HikGatewayError(pending['error']) from None
        finally:
            with _LOCK:
                _PENDING.pop(key)
                pending['event'].set()


def resolve_hik_platform_url(config, stream_type='1', force_refresh=False):
    """Resolve and cache an RTSP URL for one platform, camera and profile."""
    index_code = _field(config, 'hik_index_code', 'Hik_indexCode', 'hik_indexCode', 'index_code', 'indexCode')
    return HikGateway(config).preview(index_code, stream_type, force_refresh)


# Appended to the shared gateway source by build_hik_patch.py.
_STATUS_CACHE = {}
_STATUS_PENDING = set()
_STATUS_LOCK = threading.Lock()


def _read_online_states(gateway):
    states, total, deadline = {}, None, time.monotonic() + 8
    for page in range(1, 21):
        if time.monotonic() >= deadline:
            raise HikGatewayError('安防平台在线状态查询超时')
        response = gateway.post('/api/nms/v1/online/camera/get', {'pageNo': page, 'pageSize': 1000})
        data = response.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('list'), list):
            raise HikGatewayError('安防平台在线状态格式无效')
        if 'pageNo' in data and _number(data['pageNo']) != page:
            raise HikGatewayError('安防平台在线状态页码不匹配')
        current_total = _number(data['total']) if 'total' in data else None
        if total is not None and current_total != total:
            raise HikGatewayError('安防平台在线状态分页发生变化')
        total = current_total
        items = data['list']
        for item in items:
            if not isinstance(item, dict):
                raise HikGatewayError('安防平台在线状态格式无效')
            code = _code(item.get('indexCode') or item.get('cameraIndexCode'))
            if code in states:
                raise HikGatewayError('安防平台在线状态分页重复')
            value = item.get('online')
            states[code] = True if value in (1, '1', True) else False if value in (0, '0', False) else None
        if total is not None:
            if len(states) == total:
                return states
            if len(states) > total or not items:
                raise HikGatewayError('安防平台在线状态清单不完整')
        elif len(items) < 1000:
            return states
    raise HikGatewayError('安防平台在线状态清单超出查询范围')


def hik_online_states(config):
    """Per-platform cache; unknown/failed status must never mean offline."""
    gateway = HikGateway(config)
    key = gateway._fingerprint
    with _STATUS_LOCK:
        now = time.monotonic()
        cached = _STATUS_CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]
        if key in _STATUS_PENDING:
            return None
        for expired in [k for k, value in _STATUS_CACHE.items() if value[0] <= now]:
            _STATUS_CACHE.pop(expired, None)
        if len(_STATUS_CACHE) + len(_STATUS_PENDING) >= 128:
            return None
        _STATUS_PENDING.add(key)
    try:
        states = _read_online_states(gateway)
    except Exception:
        states = None
    finally:
        with _STATUS_LOCK:
            _STATUS_PENDING.discard(key)
    with _STATUS_LOCK:
        _STATUS_CACHE[key] = (time.monotonic() + (60 if states is not None else 10), states)
    return states
