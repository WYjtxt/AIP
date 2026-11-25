"""Resolve platform-owned alarm media against the current HTTPS gateway."""

import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlunsplit


MARKER = '# platform-push-gateway-media-v1'
DETAIL_MARKER = '# platform-push-gateway-display-v1'
ORIGINAL = "        raw = item['payload_json']\n"
PATCH = ('        ' + MARKER + '\n'
         '        from native_alarm_push_urls import rewrite_request_json\n'
         "        raw = item['payload_json']\n"
         "        if item['kind'] == 'alarm':\n"
         '            raw = rewrite_request_json(raw, STATE_DIR, recipient_delivery=True)\n'
         "        if raw != item['payload_json']:\n"
         "            item['payload'] = json.loads(raw)\n")
DETAIL_ORIGINAL = "        return {'delivery': delivery, 'payload': json.loads(row['payload_json']),\n"
DETAIL_PATCH = ('        ' + DETAIL_MARKER + '\n'
                '        from native_alarm_push_urls import rewrite_request_json\n'
                "        raw = row['payload_json']\n"
                "        if row['kind'] == 'alarm':\n"
                '            raw = rewrite_request_json(raw, STATE_DIR)\n'
                "        return {'delivery': delivery, 'payload': json.loads(raw),\n")
LOOPBACK = frozenset(('localhost', '127.0.0.1', '::1'))
GATEWAY_PORT = 8888
MEDIA_PORT = 9002
ALARM_ROUTE = '/media/alarms/'
STORAGE_ROUTE = '/media/alarm-storage/'
LEGACY_ROOTS = ('/data/AIGO/outputs/', '/data/AIGO/python/bingxing_model/results/')
ALARM_SUFFIX = re.compile(r'\.(?:mp4|flv|jpe?g|png|webp|gif)$', re.I)
STORAGE_SUFFIX = re.compile(r'\.(?:mp4|avi|mov|mkv|jpe?g|png|webp|gif)$', re.I)
TLS_LISTEN = re.compile(r'^\s*listen\s+(?:(?:[A-Za-z0-9.*-]+|\[[^\]]+\]):)?([0-9]{1,5})\s+[^;\n]*\bssl\b[^;\n]*;', re.M)
MAX_METADATA = 1024 * 1024


def _source_block(source, name, following, original, patch, marker, patched, install):
    newline = '\r\n' if '\r\n' in source else '\n'
    original = original.replace('\n', newline)
    patch = patch.replace('\n', newline)
    start = 'def ' + name + '('
    end = 'def ' + following + '('
    if source.count(start) != 1 or source.count(end) != 1 or source.index(start) >= source.index(end):
        raise ValueError('Push outbox layout is not recognized: ' + name)
    left, right = source.index(start), source.index(end)
    block = source[left:right]
    before = original
    if patched:
        before = patch
        if name == 'claim_next' and block.count(before) == 0:
            before = patch.replace(', recipient_delivery=True)', ')')
        if source.count(marker) != 1 or block.count(before) != 1:
            raise ValueError('Push alarm URL hook is incomplete')
    elif block.count(original) != 1 or name == 'claim_next' and 'INSERT INTO delivery_attempts' not in block:
        raise ValueError('Push media URL hook anchor is not recognized: ' + name)
    after = patch if install else original
    return source if before == after else source[:left] + block.replace(before, after, 1) + source[right:]


def _source_patch(source, install):
    patched = MARKER in source or DETAIL_MARKER in source
    if not install and not patched:
        return source
    updated = _source_block(source, 'claim_next', 'prepared_request', ORIGINAL, PATCH, MARKER, patched, install)
    updated = _source_block(updated, 'delivery_details', 'snapshot', DETAIL_ORIGINAL, DETAIL_PATCH,
                            DETAIL_MARKER, patched, install)
    compile(updated, 'push_outbox.py', 'exec')
    return updated


def patch_outbox(source):
    return _source_patch(source, install=True)


def unpatch_outbox(source):
    return _source_patch(source, install=False)


def _read(path):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open('rb') as stream:
            raw = stream.read(MAX_METADATA + 1)
        return raw if len(raw) <= MAX_METADATA else None
    except OSError:
        return None


def _document(path):
    raw = _read(path)
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _host(value):
    if not isinstance(value, str) or not value or len(value) > 253 or '%' in value:
        return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        hostname = value.rstrip('.').lower()
        if (not re.fullmatch(r'[a-z0-9.-]+', hostname) or re.fullmatch(r'[0-9.]+', hostname)
                or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', item)
                       for item in hostname.split('.'))):
            return None
        return hostname
    if address.is_loopback:
        return str(address) if str(address) in LOOPBACK else None
    return str(address) if not (address.is_unspecified or address.is_multicast or address.is_link_local) else None


def _origin(value):
    if not isinstance(value, str):
        return None, None
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.username is not None or url.password is not None
                or url.path not in ('', '/') or url.query or url.fragment):
            return None, None
        return _host(url.hostname), url.port if url.port is not None else 443
    except ValueError:
        return None, None


def _context(state):
    state = Path(state)
    environment_root = os.environ.get('PLATFORM_NATIVE_ROOT')
    if environment_root:
        root = Path(environment_root)
    elif state.name == 'state' and state.parent.name == 'platform_ops':
        root = state.parent.parent
    else:
        return None
    documents = []
    for name, runtime in (('container-deployment.json', 'container'), ('container/images.json', 'container'),
                          ('native-deployment.json', 'native')):
        document = _document(root / name)
        if document.get('runtime') == runtime and document.get('root', str(root)) == str(root):
            documents.append(document)
    targets = [_host(doc.get('target_ip')) for doc in documents]
    receipt = state / 'site-config.json'
    committed = _document(receipt)
    if receipt.exists() or receipt.is_symlink():
        applied = committed.get('applied')
        node = applied.get('node') if isinstance(applied, dict) else None
        canonical = (_host(node.get('address')) if committed.get('schema') == 1 and isinstance(node, dict) else None)
    else:
        canonical = next((host for host in targets if host and host not in LOOPBACK), None)
    if not canonical or canonical in LOOPBACK:
        return None
    aliases = {canonical, *LOOPBACK, *(host for host in targets if host)}
    recorded_ports = set()
    for document in documents:
        host, port = _origin(document.get('platform_url'))
        if host in aliases and 1 <= port <= 65535:
            recorded_ports.add(port)
    gateway = _read(root / 'platform_gateway/default.conf')
    listeners = {int(value) for value in TLS_LISTEN.findall(gateway.decode('utf-8', 'replace') if gateway else '')
                 if 1 <= int(value) <= 65535}
    if len(listeners) == 1:
        port = next(iter(listeners))
    elif len(listeners & recorded_ports) == 1:
        port = next(iter(listeners & recorded_ports))
    elif not listeners and len(recorded_ports) <= 1:
        port = next(iter(recorded_ports), GATEWAY_PORT)
    else:
        return None
    authority = '[' + canonical + ']' if ':' in canonical else canonical
    if port != 443:
        authority += ':' + str(port)
    legacy = tuple(dict.fromkeys((*LEGACY_ROOTS, (root.parent / 'outputs').as_posix().rstrip('/') + '/')))
    return root, authority, aliases, {GATEWAY_PORT, port, *recorded_ports}, legacy


def _historical_hosts(root):
    try:
        candidates = sorted((root / 'platform_ops/backups').glob('site-*/manifest.json'), reverse=True)[:32]
    except OSError:
        return set()
    hosts = set()
    for path in candidates:
        if path.parent.is_symlink():
            continue
        record = _document(path)
        plan = record.get('plan')
        status = record.get('status')
        if status not in ('applied', 'rolled_back') or not isinstance(plan, dict) or plan.get('node_changed') is not True:
            continue
        hosts.add(_host(plan.get('previous_node')))
        if status == 'applied' or record.get('checks'):
            hosts.add(_host(plan.get('node')))
    hosts.discard(None)
    return hosts


def _route(path, port, gateway_ports, legacy):
    if port == MEDIA_PORT:
        if path.startswith('/alarm-storage/'):
            path = '/media' + path
        else:
            prefix = next((prefix for prefix in legacy if path.startswith(prefix)), None)
            if prefix is None:
                return None
            path = ALARM_ROUTE + path[len(prefix):]
    elif port is not None and port not in gateway_ports:
        return None
    if not path.startswith((ALARM_ROUTE, STORAGE_ROUTE)) or re.search(r'%(?:2f|5c|(?![0-9a-f]{2}))', path, re.I):
        return None
    try:
        decoded = unquote(path, errors='strict')
    except UnicodeError:
        return None
    storage = path.startswith(STORAGE_ROUTE)
    suffix = STORAGE_SUFFIX if storage else ALARM_SUFFIX
    if (not suffix.search(decoded) or any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded)
            or '\\' in decoded or re.search(r'%[0-9a-f]{2}', decoded, re.I)
            or any(segment in ('', '.', '..') for segment in decoded[1:].split('/'))):
        return None
    if storage and not re.match(r'^/media/alarm-storage/[a-f0-9]{20}/.+', decoded, re.I):
        return None
    return path


def rewrite_request_json(raw, state_dir, recipient_delivery=False):
    """Use native media URLs in the UI and signed media URLs for outgoing alarms."""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError, UnicodeError):
        return raw
    fields = ('httpUrl', 'httpUrlList', 'warning_video') if recipient_delivery else ('httpUrl', 'httpUrlList')
    if not isinstance(payload, dict) or not any(key in payload for key in fields):
        return raw
    try:
        context = _context(state_dir)
    except OSError:
        context = None
    if not context and not recipient_delivery:
        return raw
    if context:
        root, authority, aliases, ports, legacy = context
        origin = 'https://' + authority
    else:
        origin, aliases = None, None
    historical = None
    if recipient_delivery:
        from recipient_media import rewrite_reference

    def rewrite_native(value):
        nonlocal historical
        if not context or not isinstance(value, str) or not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            return value
        try:
            url = urlsplit(value)
            if url.scheme in ('http', 'https') and url.netloc and url.username is None and url.password is None:
                host = _host(url.hostname)
                port = url.port if url.port is not None else (443 if url.scheme == 'https' else 80)
            elif value.startswith('/') and not value.startswith('//') and not url.netloc and not url.scheme:
                host, port = None, None
            else:
                return value
        except ValueError:
            return value
        path = _route(url.path, port, ports, legacy)
        if path is None or url.netloc and host is None:
            return value
        if host is not None and host not in aliases:
            if historical is None:
                historical = _historical_hosts(root)
            if host not in historical:
                return value
        return urlunsplit(('https', authority, path, url.query, url.fragment))

    def rewrite(value, native_fallback):
        if not isinstance(value, str):
            return value
        native = rewrite_native(value)
        if recipient_delivery:
            expected = aliases | historical if aliases and historical else aliases
            signed = rewrite_reference(native, state_dir, expected_host=expected, origin=origin)
            if signed != native:
                return signed
        return native if native_fallback else value

    changed = False
    for key in fields:
        if key not in payload:
            continue
        previous = payload[key]
        use_native = key != 'warning_video'
        if isinstance(previous, list) and (recipient_delivery or key == 'httpUrlList'):
            value = [rewrite(item, use_native) for item in previous]
        else:
            value = rewrite(previous, use_native)
        if value != previous:
            payload[key] = value
            changed = True
    if not changed:
        return raw
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except ValueError:
        return raw
