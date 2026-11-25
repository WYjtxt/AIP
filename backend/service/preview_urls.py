"""Build browser playback URLs from the currently configured media server."""
import ipaddress
from urllib.parse import quote, urlencode, urlsplit, urlunsplit


def is_loopback(host):
    if host.lower() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def media_base_url(host, port, request_host=None, public_base=None):
    if public_base:
        parsed = urlsplit(public_base.strip())
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('ZLK_PUBLIC_BASE_URL 必须是有效的 HTTP/HTTPS 地址')
        if parsed.query or parsed.fragment:
            raise ValueError('ZLK_PUBLIC_BASE_URL 不应包含查询参数或片段')
        return public_base.strip().rstrip('/')
    host = str(host).strip().strip('[]')
    # A remote browser's 127.0.0.1 refers to its own machine, not the platform.
    if is_loopback(host) and request_host:
        candidate = urlsplit('http://' + request_host).hostname
        if candidate and not is_loopback(candidate):
            host = candidate
    authority = '[{}]'.format(host) if ':' in host else host
    return 'http://{}:{}'.format(authority, int(port))


def playback_urls(base, app, stream):
    path = '{}/{}'.format(quote(app or 'openUrl', safe=''), quote(str(stream), safe=''))
    return {
        'mp4': '{}/{}.live.mp4'.format(base, path),
        'flv': '{}/{}.live.flv'.format(base, path),
        'hls': '{}/{}/hls.m3u8'.format(base, path),
        'webrtc': '{}/index/api/webrtc?{}'.format(base, urlencode({
            'app': app or 'openUrl', 'stream': stream, 'type': 'play',
        })),
    }
