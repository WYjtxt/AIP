"""One non-secret network master and guarded projections for the platform.

Importing this module performs no I/O. Existing secrets and unrelated text are
never copied into the master, preview, receipt or exception messages.
"""
import ast
import contextlib
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import tokenize
from urllib.parse import urlsplit

MASTER = 'Config_files/platform-site.json'
STATE = 'platform_ops/state/site-config.json'
FILES = (
    'Config_files/config.ini', 'Config_files/config.js', 'Config_files/secure-transport.js',
    'Config_files/zlk/config.ini', 'Config_files/kafka.properties',
    'platform_algorithm_start/config/ApiConfig.ini', 'platform_algorithm_start/config/common.py',
    'model_algorithm_package/Conf_files.py', 'model_algorithm_package/model_ai.py',
    'model_algorithm_package/Huawei_resource.py', 'model_algorithm_package/Sophon_resource.py',
    'model_algorithm_package/kafka_consumer.py', 'platform_gateway/default.conf',
    'platform_gateway/nginx.conf', 'config_dispatch/security-settings.json',
    'config_dispatch/gateway/nginx.conf', 'config_dispatch/gateway/proxy.conf',
    'container/compose.json', 'container-deployment.json', 'native-deployment.json',
    'platform_ops/state/initial-content.json',
)
ROLES = ('mysql', 'redis', 'kafka', 'media', 'analysis', 'upload', 'push',
         'backend', 'dispatch', 'aifz', 'platform_callback')
FIELD_ROLES = {'primary_ip': 'node', 'db_host': 'mysql', 'redis_ip': 'redis',
               'kafka_ip': 'kafka', 'zlk_ip': 'media', 'box_ip': 'analysis',
               'upload_ip': 'upload', 'stream_push_ip': 'push', 'aifz_ip': 'aifz'}
PY_ROLES = {'db_host': 'mysql', 'mysql_host': 'mysql', 'linux_ip': 'mysql',
            'redis_ip': 'redis', 'redis_host': 'redis', 'box_ip': 'analysis',
            'kafka_host': 'kafka', 'kafka_ip': 'kafka', 'zlk_host': 'media',
            'zdzh_host': 'backend', 'localhost_ip': 'node', 'upload_ip': 'upload',
            'stream_push_ip': 'push'}
INI_ROLES = {
    ('database', 'db_host'): 'mysql', ('redis', 'redis_ip'): 'redis',
    ('box_ip', 'box_ip'): 'analysis', ('zlk', 'zlk_host'): 'media',
    ('aicam', 'remote_ip'): 'platform_callback', ('aicam', 'aifz_host'): 'aifz',
    ('ipconfig', 'db_host'): 'mysql', ('ipconfig', 'kafka_ip'): 'kafka',
    ('ipconfig', 'localhost_ip'): 'node', ('ipconfig', 'upload_ip'): 'upload',
    ('ipconfig', 'stream_push_ip'): 'push', ('rtc', 'externip'): 'media',
    ('rtc', 'externalip'): 'media',
}
PORT_ROLES = {3306: 'mysql', 6379: 'redis', 9092: 'kafka', 5000: 'backend',
              18999: 'dispatch', 8085: 'media_local', 8554: 'media'}


class SiteConfigError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def unique_json(raw):
    def unique(items):
        out = {}
        for key, value in items:
            if key in out:
                raise SiteConfigError('JSON 配置存在重复字段')
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError, UnicodeError):
        raise SiteConfigError('JSON 配置无效或存在重复字段') from None


def host(value):
    if not isinstance(value, str) or not value or len(value) > 253:
        raise SiteConfigError('主机地址必须是 IPv4 或主机名')
    if re.fullmatch(r'[0-9.]+', value):
        try:
            address = ipaddress.IPv4Address(value)
            if address.is_unspecified or address.is_multicast:
                raise ValueError()
            return str(address)
        except ValueError:
            raise SiteConfigError('IPv4 地址无效') from None
    if any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part)
           for part in value.split('.')):
        raise SiteConfigError('主机名无效')
    return value.lower()


def validate(master):
    if not isinstance(master, dict) or set(master) != {'schema', 'node', 'services'} or master['schema'] != 1:
        raise SiteConfigError('主配置字段不正确')
    if not isinstance(master['node'], dict) or set(master['node']) != {'address'}:
        raise SiteConfigError('node 只允许 address 字段')
    node = host(master['node']['address'])
    if node in ('localhost', '127.0.0.1'):
        raise SiteConfigError('平台对外地址不能是回环地址')
    if not isinstance(master['services'], dict) or set(master['services']) not in (set(ROLES), set(ROLES) - {'platform_callback'}):
        raise SiteConfigError('服务字段缺失或包含未知服务')
    result = {'node': node}
    for role, endpoint in master['services'].items():
        if not isinstance(endpoint, dict):
            raise SiteConfigError('服务地址格式不正确')
        if set(endpoint) == {'ref'} and endpoint['ref'] in ('node', 'loopback'):
            result[role] = node if endpoint['ref'] == 'node' else '127.0.0.1'
        elif set(endpoint) == {'host'}:
            result[role] = host(endpoint['host'])
        else:
            raise SiteConfigError('服务地址只允许 ref 或 host')
    result['media_local'] = ('127.0.0.1' if master['services']['media'].get('ref') in ('node', 'loopback')
                             else result['media'])
    result.setdefault('platform_callback', result['aifz'])  # Compatible with the first pilot receipt.
    result['loopback'] = '127.0.0.1'
    return result


def _hostname(value):
    """Find only the host span; URL credentials, ports and paths stay literal."""
    if not isinstance(value, str) or not value:
        return None
    try:
        if '://' in value:
            parsed = urlsplit(value)
            if not parsed.hostname:
                return None
            authority_start = value.index('://') + 3
            authority = parsed.netloc
            prefix = authority.rsplit('@', 1)[0] + '@' if '@' in authority else ''
            start = authority_start + len(prefix)
            return start, start + len(parsed.hostname), host(parsed.hostname)
        match = re.fullmatch(r'([A-Za-z0-9.-]+)(?::[0-9]{1,5})?', value)
        if match:
            return 0, len(match.group(1)), host(match.group(1))
    except (ValueError, SiteConfigError):
        return None
    return None


def _json_roles(path, document):
    """Return public managed scalar locations, excluding arbitrary JSON data."""
    result = []
    if path == 'config_dispatch/security-settings.json':
        result.append((('origin',), 'node'))
    elif path == 'container/compose.json':
        for name, service in document.get('services', {}).items():
            if name not in ('backend', 'web', 'media', 'dispatch', 'dispatch-web',
                            'mysql', 'redis', 'kafka', 'algorithm-master'):
                raise SiteConfigError('Compose 包含未登记的服务')
            if service.get('network_mode') != 'host':
                raise SiteConfigError('本机地址派发仅支持当前 host 网络部署')
            env = service.get('environment', {})
            if not isinstance(env, dict):
                raise SiteConfigError('Compose 环境变量格式不正确')
            for key in ('TARGET_IP', 'ZLK_PUBLIC_BASE_URL', 'SEAL_ALLOWED_ORIGINS'):
                if key in env:
                    result.append((('services', name, 'environment', key), 'node'))
    else:
        for key in ('target_ip', 'platform_url', 'dispatch_url', 'management_url', 'login_url'):
            if key in document:
                result.append(((key,), 'node'))
        if path == 'platform_ops/state/initial-content.json' and isinstance(document.get('device'), dict):
            result.append((('device', 'ip'), 'node'))
    return result


def project(path, raw, endpoints=None, previous_node=None):
    """Return new bytes and non-secret bindings without executing config code."""
    text = raw.decode('utf-8-sig')
    bom = raw.startswith(b'\xef\xbb\xbf')
    bindings, edits = [], []

    def span(start, end, role, label):
        value = text[start:end]
        found = _hostname(value)
        if not found:
            if value.strip():
                raise SiteConfigError('受管地址不是简单主机或 URL：' + path + ':' + label)
            return
        left, right, address = found
        if (path == 'model_algorithm_package/Conf_files.py' and role == 'media'
                and label == 'zlk_host' and address in ('127.0.0.1', 'localhost')):
            role = 'media_local'
        bindings.append({'role': role, 'key': label, 'host': address})
        if endpoints and endpoints[role] != address:
            edits.append((start + left, start + right, endpoints[role]))

    if path.endswith('.json'):
        document = unique_json(raw)
        changed = False
        for keys, role in _json_roles(path, document):
            parent = document
            for key in keys[:-1]:
                parent = parent[key]
            value = parent.get(keys[-1])
            if not isinstance(value, str):
                continue
            # Allowed origins can be a comma-separated list; preserve other origins.
            candidates = value.split(',') if keys[-1] == 'SEAL_ALLOWED_ORIGINS' else [value]
            for index, item in enumerate(candidates):
                clean = item.strip()
                found = _hostname(clean)
                if not found:
                    raise SiteConfigError('受管 JSON 地址格式不正确：' + path)
                left, right, address = found
                if keys[-1] == 'SEAL_ALLOWED_ORIGINS' and address in ('127.0.0.1', 'localhost'):
                    continue
                bindings.append({'role': role, 'key': '.'.join(keys) + ':' + str(index), 'host': address})
                if endpoints and address != endpoints[role]:
                    candidates[index] = item.replace(clean, clean[:left] + endpoints[role] + clean[right:], 1)
                    changed = True
            parent[keys[-1]] = ','.join(candidates)
        return (encoded(document) if changed else raw), bindings

    if path.endswith('.ini'):
        section, offset = '', 0
        seen = set()
        for line in text.splitlines(True):
            match = re.match(r'\s*\[([^]]+)\]', line)
            if match:
                section = match.group(1).lower()
            match = re.match(r'(\s*([\w.-]+)\s*[=:]\s*)([^\r\n]*)', line)
            if match:
                key = match.group(2).lower()
                role = INI_ROLES.get((section, key))
                if role:
                    label = section + '.' + key
                    if label in seen:
                        raise SiteConfigError('受管 INI 字段重复：' + path)
                    seen.add(label)
                    value = re.split(r'\s+[;#]', match.group(3), 1)[0].strip()
                    value = value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'" else value
                    start = offset + match.start(3) + match.group(3).find(value)
                    span(start, start + len(value), role, label)
            offset += len(line)
    elif path.endswith('.py'):
        tree = ast.parse(text)
        lines = text.splitlines(True)
        offsets, count = [], 0
        for line in lines:
            offsets.append(count)
            count += len(line)
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        locations = {(t.start[0], t.start[1]): t for t in tokens if t.type == tokenize.STRING}
        assigned = {}

        def literal(node, role, label):
            if not isinstance(node, ast.Str):
                return
            column = len(lines[node.lineno - 1].encode('utf-8')[:node.col_offset].decode('utf-8'))
            token = locations.get((node.lineno, column))
            if not token or ast.literal_eval(token.string) != node.s:
                raise SiteConfigError('受管 Python 地址不是独立字面量：' + path)
            # Host literals cannot contain escaped quotes or concatenated strings.
            prefix = re.match(r'(?i)[ru]*([\"\'])', token.string)
            if not prefix or '\\' in token.string or token.string[prefix.end():].startswith(prefix.group(1) * 2):
                raise SiteConfigError('受管 Python 地址需使用简单字符串：' + path)
            if (token.start, token.end) in assigned:
                if assigned[(token.start, token.end)] != role:
                    raise SiteConfigError('Python 地址被多个服务复用，需要拆分：' + path)
                return
            assigned[(token.start, token.end)] = role
            start = offsets[token.start[0] - 1] + token.start[1] + prefix.end()
            span(start, start + len(node.s), role, label)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id.lower() for t in targets if isinstance(t, ast.Name)]
                roles = {PY_ROLES[n] for n in names if n in PY_ROLES}
                if len(roles) > 1:
                    raise SiteConfigError('Python 地址赋值存在歧义：' + path)
                if roles:
                    role = next(iter(roles))
                    if isinstance(node.value, ast.Str):
                        literal(node.value, role, names[0])
                    elif isinstance(node.value, ast.Call):
                        for keyword in node.value.keywords:
                            if keyword.arg == 'fallback':
                                literal(keyword.value, role, names[0] + '.fallback')
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
                if name in ('PooledDB', 'Redis', 'StrictRedis') or (name == 'connect' and isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name) and func.value.id in ('pymysql', 'mysql', 'redis')):
                    role = 'redis' if name in ('Redis', 'StrictRedis') or isinstance(func, ast.Attribute) and getattr(func.value, 'id', '') == 'redis' else 'mysql'
                    for keyword in node.keywords:
                        if keyword.arg == 'host':
                            literal(keyword.value, role, name + '.host')
            if isinstance(node, ast.Str) and node.s.startswith(('http://', 'https://')):
                parsed = urlsplit(node.s)
                if parsed.path in ('/ai_camera_view/model_status_callback', '/model_view/model_status_callback'):
                    literal(node, 'backend', 'status_callback')
    elif path.endswith('.js'):
        if path.endswith('/config.js'):
            for match in re.finditer(r'\blet\s+ip\s*=\s*([\"\'])([^\"\']+)\1', text):
                span(*match.span(2), 'node', 'browser.ip')
        else:
            matches = list(re.finditer(r'\bvar\s+HOSTS\s*=\s*\[([^\]]*)\]', text))
            if len(matches) != 1:
                raise SiteConfigError('媒体历史地址白名单格式不明确')
            match = matches[0]
            values = [v[1] for v in re.findall(r'([\"\'])([^\"\']+)\1', match.group(1))]
            if endpoints and endpoints['node'] not in values:
                # Historical origins remain aliases; do not rewrite stored URLs.
                edits.append((match.end(1), match.end(1), ', ' + repr(endpoints['node'])))
            bindings.append({'role': 'aliases', 'key': 'HOSTS', 'host': ','.join(sorted(set(values)))})
    elif path.endswith('.properties'):
        for match in re.finditer(r'(?m)^\s*advertised\.listeners\s*=\s*[^:\r\n]+://([^:\s,]+)', text):
            span(*match.span(1), 'kafka', 'advertised.listeners')
    elif path.endswith('.conf'):
        pattern = r'(?m)(?:^|(?<=[;{}]))\s*(listen|server_name|return|rewrite|error_page|proxy_redirect|proxy_set_header|proxy_pass)\s+([^;\n]+);'
        for match in re.finditer(pattern, text):
            directive, value = match.group(1), match.group(2)
            if directive == 'proxy_set_header' and not value.startswith('Host '):
                continue
            if directive in ('listen', 'server_name'):
                for item in re.finditer(r'[A-Za-z0-9.-]+(?::[0-9]+)?', value):
                    clean = item.group()
                    if clean in ('ssl', 'default_server', 'localhost') or clean.startswith(('127.', '0.0.0.0')) or clean.isdigit():
                        continue
                    span(match.start(2) + item.start(), match.start(2) + item.end(), 'node', 'nginx.' + directive)
            elif directive == 'proxy_set_header':
                value = value[5:].strip()
                if '$' not in value:
                    start = text.find(value, match.start(2), match.end(2))
                    found = _hostname(value)
                    role = 'node' if found and found[2] == previous_node else PORT_ROLES.get(int(value.rsplit(':', 1)[1]), 'node') if ':' in value and value.rsplit(':', 1)[1].isdigit() else 'node'
                    if found and (found[2] == previous_node or ':' in value):
                        span(start, start + len(value), role, 'nginx.Host')
            else:
                for item in re.finditer(r'https?://[^\s;$]+', value):
                    clean = item.group()
                    parsed = urlsplit(clean)
                    role = (PORT_ROLES.get(parsed.port, 'loopback' if parsed.hostname in ('127.0.0.1', 'localhost') else 'node')
                            if directive == 'proxy_pass' else 'node')
                    start = match.start(2) + item.start()
                    span(start, start + len(clean), role, 'nginx.' + directive)
    # Several AST nodes may reference the same literal; reject overlapping edits.
    distinct = sorted(set(edits), reverse=True)
    previous_start = len(text) + 1
    for start, end, replacement in distinct:
        if end > previous_start:
            raise SiteConfigError('受管配置字段重叠：' + path)
        text = text[:start] + replacement + text[end:]
        previous_start = start
    result = (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')
    if path.endswith('.py'):
        ast.parse(text)
    return result, sorted(bindings, key=lambda b: (b['key'], b['role'], b['host']))


def infer_master(address, bindings):
    address = host(address)
    master = {'schema': 1, 'node': {'address': address}, 'services': {}}
    for role in ROLES:
        candidates = [b for group in bindings.values() for b in group if b['role'] == role]
        # Parser fallbacks are used only when the authoritative INI is missing.
        # Preserve their presence in the receipt, then align them on first apply.
        effective = [b for b in candidates if not b.get('key', '').endswith('.fallback')]
        values = {b['host'] for b in (effective or candidates)}
        if not values:
            selected = '127.0.0.1' if role in ('mysql', 'redis', 'backend', 'dispatch') else address
        elif values <= {address, '127.0.0.1', 'localhost'} and role in ('mysql', 'redis', 'backend', 'dispatch'):
            selected = '127.0.0.1'
        elif len(values) == 1:
            selected = next(iter(values))
        else:
            raise SiteConfigError('同一服务存在不同地址，请核实：' + role)
        # External integration ownership is explicit even when its current IP coincides.
        master['services'][role] = ({'ref': 'loopback'} if selected == '127.0.0.1' else
                                    {'ref': 'node'} if selected == address and role != 'aifz' else {'host': selected})
    validate(master)
    return master


def atomic(path, raw, info=None, mode=0o600):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.site-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode) if info else mode) if hasattr(os, 'fchmod') else os.chmod(temporary, mode)
            if info and hasattr(os, 'fchown'):
                os.fchown(stream.fileno(), info.st_uid, info.st_gid)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
        if os.name == 'posix':
            descriptor = os.open(str(path.parent), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SiteManager:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if not self.root.is_dir() or self.root.is_symlink():
            raise SiteConfigError('平台根目录无效')

    def path(self, relative, required=True):
        if relative not in FILES + (MASTER, STATE):
            raise SiteConfigError('不支持的受管配置路径')
        path = self.root / relative
        for part in [path] + list(path.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise SiteConfigError('受管配置不能包含符号链接：' + relative)
        if required and not path.is_file():
            raise SiteConfigError('受管配置缺失：' + relative)
        if path.is_file() and path.stat().st_size > 8 * 1024 * 1024:
            raise SiteConfigError('受管配置过大')
        return path

    @contextlib.contextmanager
    def lock(self):
        self.path(STATE, required=False)
        folder = self.root / 'platform_ops/state'
        folder.mkdir(parents=True, exist_ok=True)
        if folder.is_symlink():
            raise SiteConfigError('配置状态目录不能是符号链接')
        if (folder / 'site-config.lock').is_symlink():
            raise SiteConfigError('配置锁不能是符号链接')
        with (folder / 'site-config.lock').open('a+b') as stream:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == 'posix':
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def snapshot(self, endpoints=None, previous_node=None):
        rows = []
        for relative in FILES:
            path = self.path(relative, required=False)
            if not path.exists():
                continue
            raw = path.read_bytes()
            new, bindings = project(relative, raw, endpoints, previous_node)
            rows.append({'path': relative, 'raw': raw, 'new': new, 'before': sha(raw),
                         'after': sha(new), 'bindings': bindings, 'info': path.stat()})
        return rows

    def initialize(self, address):
        with self.lock():
            if self.path(MASTER, False).exists() or self.path(STATE, False).exists():
                raise SiteConfigError('统一配置已存在，未覆盖')
            rows = self.snapshot(previous_node=address)
            bindings = {r['path']: r['bindings'] for r in rows}
            master = infer_master(address, bindings)
            state = {'schema': 1, 'generation': 0, 'applied': master, 'bindings': bindings,
                     'files': {r['path']: r['before'] for r in rows}}
            self.path(MASTER, False).parent.mkdir(exist_ok=True, parents=True)
            atomic(self.path(MASTER, False), encoded(master))
            try:
                atomic(self.path(STATE, False), encoded(state))
            except Exception:
                self.path(MASTER).unlink()
                raise
            return {'ok': True, 'generation': 0, 'files': len(rows),
                    'bindings': sum(len(r['bindings']) for r in rows), 'master': master}

    def plan(self, desired=None):
        for path in (self.root / 'platform_ops/backups').glob('site-*/manifest.json'):
            journal = unique_json(path.read_bytes())
            if journal.get('status') in ('prepared', 'rollback_failed'):
                raise SiteConfigError('存在未完成事务，请先核对并回滚：' + str(path.parent))
        state_raw = self.path(STATE).read_bytes()
        state = unique_json(state_raw)
        if 'platform_callback' not in state['applied']['services']:
            candidates = [b['host'] for group in state['bindings'].values() for b in group
                          if b['key'] == 'aicam.remote_ip']
            value = candidates[0] if candidates else state['applied']['node']['address']
            state['applied']['services']['platform_callback'] = ({'ref': 'node'} if value == state['applied']['node']['address'] else {'host': value})
            for group in state['bindings'].values():
                for binding in group:
                    if binding['key'] == 'aicam.remote_ip':
                        binding['role'] = 'platform_callback'
        master_raw = self.path(MASTER).read_bytes()
        desired = unique_json(master_raw) if desired is None else desired
        validate(desired)
        if 'platform_callback' not in desired['services']:
            desired = unique_json(encoded(desired))
            desired['services']['platform_callback'] = state['applied']['services']['platform_callback']
        endpoints = validate(desired)
        previous = state['applied']['node']['address']
        rows = self.snapshot(endpoints, previous)
        bindings = {r['path']: r['bindings'] for r in rows}
        if bindings != state['bindings']:
            raise SiteConfigError('受管地址已被其他入口修改，请先核对配置漂移')
        token = sha(encoded({'state': sha(state_raw), 'master': sha(master_raw), 'desired': desired,
                             'files': {r['path']: r['before'] for r in rows}}))
        changes = [{'path': r['path'], 'before': r['before'], 'after': r['after'],
                    'roles': sorted({b['role'] for b in r['bindings']})}
                   for r in rows if r['raw'] != r['new']]
        return {'ok': True, 'plan_id': token, 'generation': state['generation'],
                'desired': desired, 'node_changed': previous != endpoints['node'],
                'changes': changes, 'previous_node': previous, 'node': endpoints['node'],
                'master_pending': desired != state['applied']}, rows, state

    def apply(self, plan_id, desired=None, activate=None, verify=None, restore=None, prepare=None):
        with self.lock():
            public, rows, state = self.plan(desired)
            if plan_id != public['plan_id']:
                raise SiteConfigError('预览后配置发生变化，请重新预览')
            desired = public['desired']
            todo = [r for r in rows if r['raw'] != r['new']]
            if not todo and not public['master_pending']:
                return dict(public, applied=0, backup=None, no_op=True)
            if public['node_changed'] and not prepare:
                raise SiteConfigError('更换平台地址必须通过带证书及设备地址同步的控制器')
            old_state = self.path(STATE).read_bytes()
            old_master = self.path(MASTER).read_bytes()
            # Capture exact bytes, including pending manual edits and JSON
            # formatting, and bind them to the preview before preparation.
            captured = sha(encoded({'state': sha(old_state), 'master': sha(old_master), 'desired': desired,
                                    'files': {r['path']: r['before'] for r in rows}}))
            if captured != public['plan_id']:
                raise SiteConfigError('应用前统一配置发生变化，未覆盖')
            context = prepare(public) if prepare else None
            if self.path(MASTER).read_bytes() != old_master or self.path(STATE).read_bytes() != old_state:
                raise SiteConfigError('准备期间统一配置发生变化，未覆盖')
            parent = self.root / 'platform_ops/backups'
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if parent.is_symlink():
                raise SiteConfigError('备份目录不能是符号链接')
            backup = Path(tempfile.mkdtemp(prefix='site-' + time.strftime('%Y%m%d-%H%M%S-'), dir=str(parent)))
            backup.chmod(0o700)
            saved = []
            for index, row in enumerate(todo):
                destination = backup / ('%03d.bin' % index)
                atomic(destination, row['raw'])
                saved.append({'path': row['path'], 'backup': destination.name, 'before': row['before'],
                              'after': row['after'], 'mode': stat.S_IMODE(row['info'].st_mode),
                              'uid': row['info'].st_uid, 'gid': row['info'].st_gid})
            atomic(backup / 'state.json', old_state)
            atomic(backup / 'master.json', old_master)
            new_master = encoded(desired)
            core_files = [{'path': MASTER, 'backup': 'master.json', 'before': sha(old_master), 'after': sha(new_master)},
                          {'path': STATE, 'backup': 'state.json', 'before': sha(old_state), 'after': None}]
            journal = {'status': 'prepared', 'files': saved, 'generation': state['generation'],
                       'plan': public, 'context': context, 'core_files': core_files}
            atomic(backup / 'manifest.json', encoded(journal))
            written = []
            core_written = []
            try:
                for row in todo:
                    path = self.path(row['path'])
                    if sha(path.read_bytes()) != row['before']:
                        raise SiteConfigError('应用期间配置发生变化，未覆盖')
                    # Journal intent before replace: a directory fsync can fail after commit.
                    written.append(row)
                    atomic(path, row['new'], row['info'])
                if sha(self.path(MASTER).read_bytes()) != core_files[0]['before']:
                    raise SiteConfigError('应用期间主配置发生变化，未覆盖')
                core_written.append(core_files[0])
                atomic(self.path(MASTER), new_master)
                # Consumers read the applied receipt, never an uncommitted manual edit.
                new_rows = self.snapshot(previous_node=public['node'])
                new_state = {'schema': 1, 'generation': state['generation'] + 1, 'applied': desired,
                             'bindings': {r['path']: r['bindings'] for r in new_rows},
                             'files': {r['path']: r['before'] for r in new_rows}}
                new_state_raw = encoded(new_state)
                core_files[1]['after'] = sha(new_state_raw)
                # Record the exact state-write intent before replacement. A
                # committed replace may still raise during directory fsync.
                atomic(backup / 'manifest.json', encoded(journal))
                if sha(self.path(STATE).read_bytes()) != core_files[1]['before']:
                    raise SiteConfigError('应用期间配置收据发生变化，未覆盖')
                core_written.append(core_files[1])
                atomic(self.path(STATE), new_state_raw)
                if activate:
                    activate(public, context)
                checks = verify(public, context) if verify else None
                journal['status'] = 'applied'
                journal['checks'] = checks
                atomic(backup / 'manifest.json', encoded(journal))
                return dict(public, applied=len(todo), backup=str(backup), no_op=False, checks=checks,
                            generation=new_state['generation'])
            except Exception:
                failures = []
                for row in reversed(written):
                    try:
                        path = self.path(row['path'])
                        current = sha(path.read_bytes())
                        if current == row['after']:
                            atomic(path, row['raw'], row['info'])
                        elif current != row['before']:
                            raise SiteConfigError('文件已被外部修改')
                    except Exception:
                        failures.append(row['path'])
                for record in reversed(core_written):
                    try:
                        path = self.path(record['path'])
                        current = sha(path.read_bytes())
                        if current == record['after']:
                            atomic(path, old_master if record['path'] == MASTER else old_state)
                        elif current != record['before']:
                            raise SiteConfigError('统一配置已被外部修改')
                    except Exception:
                        failures.append(record['path'])
                if restore:
                    try:
                        restore(public, context)
                    except Exception:
                        failures.append('service_restore')
                journal['status'] = 'rollback_failed' if failures else 'rolled_back'
                journal['rollback_failures'] = failures
                atomic(backup / 'manifest.json', encoded(journal))
                raise SiteConfigError('应用未通过，' + ('部分回滚失败' if failures else '已回滚') + '；备份：' + str(backup)) from None

    def rollback(self, backup, restore=None):
        with self.lock():
            backup = Path(backup).absolute()
            parent = self.root / 'platform_ops/backups'
            if backup.is_symlink() or backup.parent != parent or not backup.name.startswith('site-'):
                raise SiteConfigError('回滚目录不属于当前平台')
            journal = unique_json((backup / 'manifest.json').read_bytes())
            if journal['status'] == 'rolled_back':
                return {'ok': True, 'no_op': True, 'backup': str(backup)}
            state = unique_json(self.path(STATE).read_bytes())
            if state['generation'] not in (journal['generation'], journal['generation'] + 1):
                raise SiteConfigError('已有更新代次，未回退旧事务')
            core_files = journal.get('core_files')
            if core_files is not None:
                if (not isinstance(core_files, list) or len(core_files) != 2 or
                        not all(isinstance(r, dict) and r.get('path') in (MASTER, STATE) for r in core_files) or
                        {r.get('path') for r in core_files if isinstance(r, dict)} != {MASTER, STATE}):
                    raise SiteConfigError('统一配置回滚意图无效')
                for record in core_files:
                    expected_backup = 'master.json' if record['path'] == MASTER else 'state.json'
                    if record.get('backup') != expected_backup:
                        raise SiteConfigError('统一配置回滚备份不匹配')
                    if sha(self.path(record['path']).read_bytes()) not in (record.get('before'), record.get('after')):
                        raise SiteConfigError('统一配置已被外部修改，未覆盖回滚')
                    if sha((backup / expected_backup).read_bytes()) != record.get('before'):
                        raise SiteConfigError('统一配置备份校验未通过')
            for row in journal['files']:
                path = self.path(row['path'])
                if sha(path.read_bytes()) not in (row['before'], row['after']):
                    raise SiteConfigError('配置已被外部修改，未覆盖回滚')
                if sha((backup / row['backup']).read_bytes()) != row['before']:
                    raise SiteConfigError('备份校验未通过')
            for row in reversed(journal['files']):
                path = self.path(row['path'])
                atomic(path, (backup / row['backup']).read_bytes(), path.stat())
            for relative, name in ((MASTER, 'master.json'), (STATE, 'state.json')):
                if core_files is not None:
                    record = next(r for r in core_files if r['path'] == relative)
                    if sha(self.path(relative).read_bytes()) not in (record['before'], record['after']):
                        raise SiteConfigError('回滚期间统一配置已被外部修改，未覆盖')
                atomic(self.path(relative), (backup / name).read_bytes())
            if restore:
                restore(journal['plan'], journal['context'])
            journal['status'] = 'rolled_back'
            atomic(backup / 'manifest.json', encoded(journal))
            return {'ok': True, 'no_op': False, 'backup': str(backup), 'generation': journal['generation']}


def applied_environment(root, environment):
    """Overlay existing container/unit environment from the committed master."""
    path = Path(root) / STATE
    if not path.exists():
        return dict(environment)
    endpoints = validate(unique_json(path.read_bytes())['applied'])
    result = dict(environment)
    old = result.get('TARGET_IP')
    result['TARGET_IP'] = endpoints['node']
    for key in ('ZLK_PUBLIC_BASE_URL', 'SEAL_ALLOWED_ORIGINS'):
        if key in result and old:
            values = []
            for value in result[key].split(','):
                found = _hostname(value.strip())
                if found and found[2] == old:
                    left, right, _ = found
                    clean = value.strip()
                    value = value.replace(clean, clean[:left] + endpoints['node'] + clean[right:], 1)
                values.append(value)
            result[key] = ','.join(values)
    return result


def guard_legacy_values(root, values):
    """Allow credential/port maintenance, but give network ownership one writer."""
    path = Path(root) / STATE
    if not path.exists():
        return False
    resolved = validate(unique_json(path.read_bytes())['applied'])
    for field, role in FIELD_ROLES.items():
        value = values.get(field)
        allowed = {resolved[role]}
        if field == 'aifz_ip':
            allowed.add(resolved['platform_callback'])
        if value and value not in allowed:
            raise SiteConfigError('统一网络配置已启用，请修改 Config_files/platform-site.json 并通过 platform_site_control.py 预览及应用')
    # The legacy form combines remote_ip and AIFZ_HOST into one field. Even when
    # its displayed value is current, it must not overwrite the other endpoint.
    for field in FIELD_ROLES:
        values.pop(field, None)
    return True
