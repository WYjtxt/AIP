"""File-specific access for alarm media delivered to external recipients."""
import functools
import hashlib
import hmac
import ipaddress
import json
import re
from pathlib import Path
from urllib import parse


LEGACY = '/data/AIGO/outputs/'
NATIVE = '/media/alarms/'
SHARE = '/media/push/'
KEY_FILE = 'recipient-media.key'
LEGACY_FILE = 'recipient-media-legacy.json'
EXTENSIONS = frozenset(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.flv'))
MAX_LEGACY_BYTES = 2 * 1024 * 1024
_FORBIDDEN_ESCAPE = re.compile(r'%(?:2f|5c|(?![0-9a-f]{2}))', re.I)
_HEX_SIGNATURE = re.compile(r'[a-f0-9]{64}\Z')


def _clean(value):
    return (isinstance(value, str) and 0 < len(value) <= 4096
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _relative(path, prefix):
    if not _clean(path) or not path.startswith(prefix) or _FORBIDDEN_ESCAPE.search(path):
        return None
    try:
        relative = parse.unquote(path[len(prefix):], encoding='utf-8', errors='strict')
    except UnicodeError:
        return None
    if (not _clean(relative) or any(c in relative for c in '%\\?#')
            or any(not part or part.startswith('.') or ':' in part for part in relative.split('/'))
            or Path(relative).suffix.lower() not in EXTENSIONS):
        return None
    return relative


def _origin(value):
    if not _clean(value):
        return None
    try:
        link = parse.urlsplit(value)
        if (link.scheme == 'https' and link.hostname and link.username is None and link.password is None
                and link.path in ('', '/') and not link.query and not link.fragment and (link.port is None or link.port > 0)):
            return link
    except ValueError:
        return None


def reference_path(value, expected_host=None, origin=None):
    """Return the exact relative path for a local, recognized alarm-media URL."""
    if not _clean(value) or value.startswith('//'):
        return None
    authority = _origin(origin)
    if authority is None:
        return None
    hosts = {authority.hostname.lower()}
    if isinstance(expected_host, str):
        hosts.add(expected_host.lower())
    elif expected_host is not None:
        hosts.update(host.lower() for host in expected_host if isinstance(host, str))
    try:
        link = parse.urlsplit(value)
        if link.fragment or link.username is not None or link.password is not None:
            return None
        if link.netloc or link.scheme:
            if (link.scheme not in ('http','https') or link.hostname not in hosts
                    or link.port not in {8888, 9002, authority.port, None}):
                return None
        for prefix in (LEGACY, NATIVE):
            result = _relative(link.path, prefix)
            if result is not None:
                return result
    except ValueError:
        return None


def _key(state_dir):
    path = Path(state_dir) / KEY_FILE
    try:
        if path.is_symlink():
            return None
        with path.open('rb') as stream:
            raw = stream.read(33)
        return raw if len(raw) == 32 else None
    except OSError:
        return None


def _signature(key, relative):
    return hmac.new(key, b'platform-recipient-media-v1\0' + relative.encode('utf-8'), hashlib.sha256).hexdigest()


def rewrite_reference(value, state_dir, expected_host=None, origin=None):
    """Build a reusable HTTPS capability for one pushed media file."""
    relative = reference_path(value, expected_host, origin)
    if relative is None:
        return value
    key = _key(state_dir)
    if key is None:
        return value
    authority = _origin(origin)
    route = SHARE + parse.quote(relative, safe='/')
    return parse.urlunsplit(('https', authority.netloc, route, 'sig=' + _signature(key, relative), ''))


def _client(value):
    try:
        address = ipaddress.ip_address(value)
        return str((address.ipv4_mapped or address) if address.version == 6 else address)
    except ValueError:
        return None


@functools.lru_cache(maxsize=4)
def _legacy_index(path, inode, timestamp, size):
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_LEGACY_BYTES + 1)
        if len(raw) > MAX_LEGACY_BYTES:
            return frozenset(), frozenset()
        document = json.loads(raw)
        if (not isinstance(document, dict) or document.get('version') != 1
                or not isinstance(document.get('clients'), list) or not isinstance(document.get('paths'), list)):
            return frozenset(), frozenset()
        clients = frozenset(_client(item) for item in document['clients'] if isinstance(item, str))
        return clients - {None}, frozenset(item for item in document['paths'] if isinstance(item, str))
    except (OSError, ValueError, UnicodeError):
        return frozenset(), frozenset()


def authorize(uri, client, state_dir):
    if not _clean(uri) or not uri.startswith('/') or uri.startswith('//'):
        return False
    try:
        link = parse.urlsplit(uri)
        if link.scheme or link.netloc or link.fragment:
            return False
    except ValueError:
        return False
    relative = _relative(link.path, SHARE)
    if relative is not None:
        if not link.query.startswith('sig=') or not _HEX_SIGNATURE.fullmatch(link.query[4:]):
            return False
        key = _key(state_dir)
        return key is not None and hmac.compare_digest(link.query[4:], _signature(key, relative))
    relative = _relative(link.path, LEGACY)
    if relative is None or link.query:
        return False
    path = Path(state_dir) / LEGACY_FILE
    try:
        if path.is_symlink():
            return False
        metadata = path.stat()
        if not path.is_file() or metadata.st_size > MAX_LEGACY_BYTES:
            return False
    except OSError:
        return False
    clients, paths = _legacy_index(path, metadata.st_ino, metadata.st_mtime_ns, metadata.st_size)
    return _client(client) in clients and relative in paths
