"""Resolve Hikvision monitor codes using the shared gateway."""
# native_hik_stream integration
from comm.hik_gateway import resolve_hik_platform_url as _gateway_resolve

import hashlib
import json
from urllib.parse import parse_qsl, unquote, urlsplit


_FIELDS = ('hik_host', 'hik_port', 'hik_appKey', 'hik_appSecret', 'hik_artemis')
_RTSP_QUERY_KEYS = {'channel', 'subtype', 'streamtype', 'profile', 'transportmode'}


def _configuration(platform, index_code):
    def field(name):
        return platform.get(name) if isinstance(platform, dict) else getattr(platform, name, None)

    values = {name: field(name) for name in _FIELDS}
    values['index_code'] = str(index_code or '').strip()
    return values


def _complete(config):
    return all(config[name] for name in ('hik_host', 'hik_appKey', 'hik_appSecret', 'index_code'))


def _profile(stream_type):
    choice = str(stream_type or '').strip().lower()
    if choice in ('', 'legacy', 'main', '0', '1'):
        return 'main'
    if choice in ('sub', '2'):
        return 'sub'
    raise ValueError('安防平台码流类型无效')


def stable_hik_fallback(url):
    if not isinstance(url, str) or any(char.isspace() for char in url):
        return None
    try:
        parsed = urlsplit(url)
        path = unquote(parsed.path).lower()
        if (parsed.scheme != 'rtsp' or not parsed.hostname or parsed.fragment
                or 'openurl' in path or 'nsig' in path):
            return None
        parsed.port  # Validate a stored explicit port before passing it to a decoder.
        if any(key.lower() not in _RTSP_QUERY_KEYS
               for key, _ in parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)):
            return None
    except ValueError:
        return None
    return url


def resolve_hik_platform_url(platform, index_code, stream_type='main', force_refresh=False):
    config = _configuration(platform, index_code)
    if not _complete(config):
        raise ValueError('安防平台接入信息不完整，请同步监控点并检查平台授权')
    return _gateway_resolve(config, _profile(stream_type), force_refresh=force_refresh)


class HikSnapshotUrl(str):
    """Mark a URL whose decoder errors must not be printed or returned."""

    def __repr__(self):
        return '<HikSnapshotUrl>'


class HikStreamReference(str):
    """Stable string key for the supervisor; credentials and URLs stay out of its logs."""

    def __new__(cls, platform, index_code, stream_type=None, fallback=None):
        config = _configuration(platform, index_code)
        profile = _profile(stream_type)
        if str(stream_type or '').strip().lower() in ('', 'legacy'):
            fallback = stable_hik_fallback(fallback)
        else:
            fallback = None
        if not _complete(config) and not fallback:
            raise ValueError('安防平台接入信息不完整，请同步监控点并检查平台授权')
        identity = hashlib.sha256(json.dumps([config, profile, fallback], sort_keys=True)
                                  .encode('utf-8')).hexdigest()
        source = str.__new__(cls, 'rtsp://hik-platform.invalid/' + identity)
        source._config = config
        source._stream_type = stream_type
        source._profile = profile
        source._fallback = fallback
        return source

    def __reduce__(self):
        return (type(self), (self._config, self._config['index_code'],
                             self._stream_type, self._fallback))

    def resolve(self, force_refresh=False):
        if _complete(self._config):
            try:
                return _gateway_resolve(self._config, self._profile, force_refresh=force_refresh)
            except ValueError:
                if not self._fallback:
                    raise
        return self._fallback


class HikCaptureSource:
    """Use the gateway cache on the first open and refresh for each reopen."""

    def __init__(self, source):
        self.reference = source if isinstance(source, HikStreamReference) else None
        self.attempted = False

    def open_url(self):
        refresh = self.attempted
        self.attempted = True
        return self.reference.resolve(force_refresh=refresh)
