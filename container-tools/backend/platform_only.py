#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update 8888 and 8899 using the site's original settings and credentials.

No middleware installation, reference configuration extraction, database seed,
password reset, certificate generation or firewall change belongs in this path.
Only local Docker and systemd are used; no third party Python modules are needed.
"""
import ast
import contextlib
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
import uuid

from media_manifest import inspect_image_archive, normalize_arch
from platform_profile import prepare_profile
from backend_signing import active_snapshot, canonical_snapshot, assert_preserved


SERVICES = ('config-dispatch', 'config-dispatch-gateway')
CODE_FILES = frozenset((
    'config_dispatch.py', 'login.html', 'model_ai_config.py', 'sandbox_probe.py',
    'secure_server.py', 'security-ui.css', 'security-ui.js', 'security_auth.py',
    'security_config.py',
))


def run(args, check=True, timeout=120):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=timeout)
    if check and result.returncode:
        # Tool output can include connection credentials. Keep it in neither UI
        # nor logs; the protected snapshot has the inputs needed for diagnosis.
        raise RuntimeError('%s 执行失败（退出码 %s）' % (args[0], result.returncode))
    return result


def file_digest(path):
    digest = hashlib.sha256()
    with open(str(path), 'rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def auth_fingerprint(path):
    """Check accounts, password derivations and roles, ignoring session churn."""
    with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT username,password_hash,salt,iterations,role,disabled '
                          'FROM users ORDER BY username').fetchall()
    if not rows:
        raise RuntimeError('8899 原认证库没有账号；请先准备原账号库，不能用默认密码代替')
    return hashlib.sha256(json.dumps(rows, ensure_ascii=True).encode('utf-8')).hexdigest()


def dispatch_code(bundle):
    """Read a fixed allowlist, never extract paths, links, units or settings."""
    result = {}
    with tarfile.open(str(bundle), 'r:*') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.parts and path.parts[0] == '.':
                path = PurePosixPath(*path.parts[1:])
            if (path.parent != PurePosixPath('data/config_dispatch') or
                    path.name not in CODE_FILES):
                continue
            if not member.isfile() or member.size > 4 * 1024 * 1024:
                raise RuntimeError('8899 程序包包含无效文件：' + path.name)
            if path.name in result:
                raise RuntimeError('8899 程序包包含重复文件：' + path.name)
            content = archive.extractfile(member).read()
            if path.suffix == '.py':
                ast.parse(content.decode('utf-8-sig'), filename=path.name)
            result[path.name] = content
    missing = CODE_FILES.difference(result)
    if missing:
        raise RuntimeError('8899 程序包缺少文件：' + ', '.join(sorted(missing)))
    return result


def inspect_container(name):
    result = run(['docker', 'container', 'inspect', name], check=False)
    if result.returncode:
        return None
    return json.loads(result.stdout)[0]


def select_image(archive, arch, role):
    records = inspect_image_archive(archive, arch)
    prefixes = {'seal_system': 'seal_system', 'seal_system_vue': 'seal_system_vue', 'zlk': 'zlmediakit'}
    prefix = prefixes[role]
    matching = []
    for record in records:
        name = record['tag'].rsplit('/', 1)[-1].split(':', 1)[0]
        if name.startswith(prefix) and not (role == 'seal_system' and name.startswith('seal_system_vue')):
            matching.append(record)
    if not matching or len({r['config_digest'] for r in matching}) != 1:
        raise RuntimeError('镜像包必须含唯一的对应平台镜像：' + Path(archive).name)
    return matching[0]['tag']


def container_payload(old, new_image, old_image_config=None, new_image_config=None):
    """Clone Docker configuration, including volumes, runtime and networking.

    Image defaults follow the new image unless the site explicitly overrode
    them. Explicit environment values always retain their original values.
    """
    config = copy.deepcopy(old['Config'])
    old_defaults = old_image_config or {}
    new_defaults = new_image_config or {}
    for key in ('Cmd', 'Entrypoint', 'WorkingDir', 'User', 'Healthcheck'):
        if config.get(key) == old_defaults.get(key) and key in new_defaults:
            config[key] = copy.deepcopy(new_defaults[key])
    config['Image'] = new_image
    host = copy.deepcopy(old['HostConfig'])
    # Anonymous volumes must refer to the previous volume, not a fresh empty one.
    existing_mounts = host.setdefault('Mounts', [])
    targets = {m.get('Target') for m in existing_mounts}
    targets.update(b.split(':')[1] for b in host.get('Binds') or [] if ':' in b)
    for mount in old.get('Mounts', []):
        if mount['Type'] == 'volume' and mount['Destination'] not in targets:
            existing_mounts.append({'Type': 'volume', 'Source': mount['Name'],
                                    'Target': mount['Destination'],
                                    'ReadOnly': not mount.get('RW', True)})
    payload = dict(config, HostConfig=host)
    mode = host.get('NetworkMode', 'default')
    if mode not in ('host', 'none') and not mode.startswith('container:'):
        endpoints = {}
        for name, endpoint in old.get('NetworkSettings', {}).get('Networks', {}).items():
            data = {k: copy.deepcopy(endpoint[k]) for k in ('IPAMConfig', 'DriverOpts')
                    if endpoint.get(k)}
            # Inspect includes the old container id/name as automatic aliases.
            aliases = [a for a in endpoint.get('Aliases') or []
                       if a not in (old.get('Id'), old.get('Id', '')[:12],
                                    old.get('Name', '').lstrip('/'))]
            if aliases:
                data['Aliases'] = aliases
            endpoints[name] = data
        payload['NetworkingConfig'] = {'EndpointsConfig': endpoints}
    return payload


def pin_backend_security(payload, signing_guard):
    # Docker fills omitted variables from the new image. Preserve the old
    # *effective* path even when the old image relied on the Python default.
    environment = dict(value.split('=', 1) for value in payload.get('Env', []) if '=' in value)
    environment['PLATFORM_SECURITY_CONFIG'] = signing_guard['path']
    payload['Env'] = [key + '=' + value for key, value in environment.items()]


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=120):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class Docker:
    def __init__(self):
        self.version = run(['docker', 'version', '--format', '{{.Server.APIVersion}}']).stdout.strip()
        endpoint = os.environ.get('DOCKER_HOST')
        if not endpoint:
            endpoint = run(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}']).stdout.strip()
        if not endpoint.startswith('unix://'):
            raise RuntimeError('仅部署平台需要本机 Docker Unix socket，不能向其他 Docker 主机部署')
        self.socket_path = endpoint[len('unix://'):]
        if not self.version or not Path(self.socket_path).exists():
            raise RuntimeError('需要本机正在运行的 Docker：' + self.socket_path)

    def create(self, name, payload):
        conn = UnixConnection(self.socket_path, timeout=120)
        try:
            conn.request('POST', '/v%s/containers/create?name=%s' % (self.version, name),
                         json.dumps(payload).encode('utf-8'), {'Content-Type': 'application/json'})
            response = conn.getresponse()
            result = response.read()
            if response.status != 201:
                raise RuntimeError('创建容器 %s 失败（Docker HTTP %s）' % (name, response.status))
            return json.loads(result)['Id']
        finally:
            conn.close()


def image_info(image):
    return json.loads(run(['docker', 'image', 'inspect', image]).stdout)[0]


def assert_mounts(old):
    for mount in old.get('Mounts', []):
        if mount['Type'] == 'bind' and not Path(mount['Source']).exists():
            raise RuntimeError('原容器挂载源不存在：' + mount['Source'])


def protected_files(root, containers, auth_db):
    roots = [root / 'Config_files', root / 'platform_gateway',
             root / 'config_dispatch' / 'tls', root / 'config_dispatch' / 'gateway']
    files = {root / 'config_dispatch' / 'security-settings.json'}
    for base in roots:
        if base.exists():
            for path in base.rglob('*'):
                if base.name == 'gateway' and any(part in ('logs', 'run', 'temp')
                                                  for part in path.relative_to(base).parts):
                    continue
                if path.is_file() and path.suffix.lower() not in ('.tar', '.gz', '.tgz', '.xz', '.zip'):
                    files.add(path)
    for container in containers.values():
        if container:
            for mount in container.get('Mounts', []):
                path = Path(mount['Source'])
                if mount['Type'] == 'bind' and path.is_file():
                    files.add(path)
                elif mount['Type'] == 'bind' and path.is_dir():
                    # Include external site TLS/config directories without hashing
                    # video results or log directories mounted into the backend.
                    destination = mount.get('Destination', '').lower()
                    if any(word in destination for word in ('tls', '/conf', '/cert')):
                        for child in path.rglob('*'):
                            if child.is_file() and child.suffix.lower() in (
                                    '.ini', '.conf', '.cnf', '.json', '.js', '.key', '.crt', '.cer', '.pem'):
                                files.add(child)
    # SQLite itself can change sessions on GET /auth/status. Accounts have a
    # separate fingerprint and the complete database has a protected backup.
    return {p for p in files if p.is_file() and p.resolve() != auth_db.resolve()
            and str(p) not in (str(auth_db) + '-wal', str(auth_db) + '-shm')}


def healthcheck(target, tries=30, replaced=('seal_system', 'seal_system_vue', 'zlk')):
    urls = [(8888, '/', (200,)), (8888, '/api/captcha?_=oneclick', (200,)),
            (8888, '/api/scheduler_task/show_task', (401, 403)),
            (8899, '/login', (200,)), (8899, '/api/auth/status', (200,))]
    for attempt in range(tries):
        passed = True
        for port, path, accepted in urls:
            result = run(['curl', '-sk', '--max-time', '5', '-o', '/dev/null',
                          '-w', '%{http_code}', 'https://%s:%s%s' % (target, port, path)], check=False)
            if result.returncode or result.stdout.strip() not in tuple(map(str, accepted)):
                passed = False
                break
        if passed:
            for name in ('seal_system', 'seal_system_vue', 'zlk'):
                c = inspect_container(name)
                if not c or not c['State'].get('Running') or (name in replaced and c.get('RestartCount', 0)):
                    passed = False
            for service in SERVICES:
                if run(['systemctl', 'is-active', '--quiet', service], check=False).returncode:
                    passed = False
        if passed:
            return
        if attempt + 1 < tries:
            time.sleep(2)
    raise RuntimeError('两个平台的容器、服务或 HTTPS/API 验证失败')


class PlatformUpdate:
    def __init__(self, env=None):
        self.env = os.environ if env is None else env
        raw = self.env.get('PLATFORM_DATA_ROOT', '/data')
        from data_root import resolve_selected_root
        self.root = resolve_selected_root(raw)
        if not self.root.is_absolute() or str(self.root) in ('/', '/etc', '/usr', '/var', '/root'):
            raise RuntimeError('平台原配置目录必须是专用绝对路径，例如 /data')
        self.bundle = Path(self.env.get('PLATFORM_BUNDLE', '/root/oneclick/payload/113100_bundle.tar.gz'))
        self.target = self.env.get('TARGET_IP', '127.0.0.1')
        self.original = {}
        self.images = {}
        self.old_names = {}
        self.disconnected = []
        self.stopped_containers = []
        self.created = []
        self.created_data_dirs = []
        self.code_backups = {}
        self.hashes = {}
        self.services_running = {}
        self.backup = None
        self.stopped_services = False
        self.profile = None
        self.signing_guard = None

    def preflight(self):
        arch = normalize_arch(os.uname().machine)
        release_root = Path(os.environ.get('ONECLICK_ROOT', '/root/oneclick'))
        if (release_root / 'release-lock.json').exists():
            for path in (self.root/'platform_ops/backend-client.json',self.root/'platform_ops/server.json'):
                if not path.is_file():
                    raise RuntimeError('当前环境尚未具备 V2.2 宿主机服务；请用 repair 完成服务和数据库迁移后再使用仅平台更新')
        if self.env.get('TARGET_ARCH') and normalize_arch(self.env['TARGET_ARCH']) != arch:
            raise RuntimeError('目标机架构与上传介质选择不一致')
        self.docker = Docker()
        for tool in ('curl', 'systemctl'):
            if not shutil.which(tool):
                raise RuntimeError('已有依赖缺少 %s；请选择完整部署或先安装该依赖' % tool)
        for name in ('seal_system', 'seal_system_vue', 'zlk'):
            self.original[name] = inspect_container(name)
            if self.original[name]:
                assert_mounts(self.original[name])
        required = [self.root / 'Config_files' / n for n in
                    ('config.ini', 'config.js', 'nginx.conf', 'platform-security.json')]
        required += [self.root / 'platform_gateway' / 'default.conf',
                     self.root / 'config_dispatch' / 'security-settings.json']
        for path in required:
            if not path.is_file():
                raise RuntimeError('缺少原配置文件：%s；仅部署平台不会套用参照机配置或默认账密' % path)
        self.signing_guard = (active_snapshot(self.original['seal_system'], self.root)
                              if self.original['seal_system'] else canonical_snapshot(self.root))
        settings = json.loads((self.root / 'config_dispatch' / 'security-settings.json').read_text('utf-8'))
        if Path(settings.get('data_root', '/data')).resolve() != self.root:
            raise RuntimeError('原派发配置 data_root 与所选目录不匹配；请使用配套的原配置，工具不会改写它')
        self.auth_db = Path(settings.get('auth_db', str(self.root / 'config_dispatch/state/auth.sqlite3')))
        if not self.auth_db.is_absolute():
            self.auth_db = self.root / 'config_dispatch' / self.auth_db
        if not self.auth_db.is_file():
            raise RuntimeError('缺少原 8899 认证库：' + str(self.auth_db))
        self.auth_stat = self.auth_db.stat()
        self.auth_hash = auth_fingerprint(self.auth_db)
        missing_services = []
        for service in SERVICES:
            result = run(['systemctl', 'show', '-p', 'LoadState', '--value', service])
            if result.stdout.strip() != 'loaded':
                missing_services.append(service)
                self.services_running[service] = False
            else:
                self.services_running[service] = not run(
                    ['systemctl', 'is-active', '--quiet', service], check=False).returncode
        self.code = dispatch_code(self.bundle)
        self.profile = prepare_profile(self.root, self.bundle, missing_services)
        for role, env_key in (('seal_system', 'BACKEND_IMAGE_ARCHIVE'),
                              ('seal_system_vue', 'FRONTEND_IMAGE_ARCHIVE'),
                              ('zlk', 'ZLK_IMAGE_ARCHIVE')):
            if role == 'zlk' and self.original[role]:
                if not self.original[role]['State'].get('Running'):
                    raise RuntimeError('原 zlk 未运行；请先修复原流媒体依赖，仅部署模式不会重启它')
                continue
            archive = self.env.get(env_key, '')
            if not archive or not Path(archive).is_file():
                raise RuntimeError('缺少当前架构镜像包：' + env_key)
            self.images[role] = {'archive': archive, 'tag': select_image(archive, arch, role)}
        if not self.original['zlk'] and not (self.root / 'Config_files/zlk/config.ini').is_file():
            raise RuntimeError('缺少原 ZLK 连接配置：' + str(self.root / 'Config_files/zlk/config.ini'))
        if not self.original['seal_system_vue']:
            for name in ('server.key', 'server-chain.crt'):
                if not (self.root / 'platform_gateway/tls' / name).is_file():
                    raise RuntimeError('缺少原 TLS 文件：' + str(self.root / 'platform_gateway/tls' / name))
        self.hashes = {str(path): file_digest(path)
                       for path in protected_files(self.root, self.original, self.auth_db)}
        print('[ OK ] 原配置、8899 原账号库、服务与当前架构镜像检查通过', flush=True)

    def snapshot(self):
        stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
        self.backup = Path('/root/oneclick/backups') / ('platform_' + stamp)
        self.backup.mkdir(parents=True, mode=0o700)
        os.chmod(str(self.backup.parent), 0o700)
        (self.backup / 'containers.json').write_text(json.dumps(self.original, indent=2), 'utf-8')
        (self.backup / 'preserved-sha256.json').write_text(json.dumps(self.hashes, indent=2), 'utf-8')
        for raw in self.hashes:
            source = Path(raw)
            dest = self.backup / 'original-files' / str(source).lstrip('/')
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(str(source), str(dest))
            info = source.stat()
            os.chown(str(dest), info.st_uid, info.st_gid)
        for name in self.code:
            dest = self.root / 'config_dispatch' / name
            if dest.is_symlink():
                raise RuntimeError('平台程序文件不可为符号链接：' + str(dest))
            if dest.exists():
                backup = self.backup / 'dispatch-code' / name
                backup.parent.mkdir(exist_ok=True, mode=0o700)
                shutil.copy2(str(dest), str(backup))
                info = dest.stat()
                os.chown(str(backup), info.st_uid, info.st_gid)
                self.code_backups[str(dest)] = str(backup)
            else:
                self.code_backups[str(dest)] = None
        self.stamp = stamp
        print('[ OK ] 备份目录：' + str(self.backup), flush=True)

    def load_images(self):
        for spec in self.images.values():
            run(['docker', 'load', '-i', spec['archive']], timeout=1800)
            info = image_info(spec['tag'])
            expected = 'arm64' if normalize_arch(os.uname().machine) == 'aarch64' else 'amd64'
            if info.get('Architecture') != expected:
                raise RuntimeError('导入后镜像架构不匹配')
            spec['id'] = info['Id']
            spec['config'] = info['Config']

    def validate_frontend(self):
        """Test nginx with production mounts before stopping either platform."""
        old = self.original['seal_system_vue']
        spec = self.images['seal_system_vue']
        if old:
            payload = container_payload(old, spec['id'], image_info(old['Image'])['Config'], spec['config'])
        else:
            root = str(self.root)
            payload = dict(copy.deepcopy(spec['config']), HostConfig={'Binds': [
                root + '/platform_gateway/default.conf:/etc/nginx/conf.d/default.conf',
                root + '/Config_files/config.js:/usr/share/nginx/html/static/js/config.js',
                root + '/platform_gateway/tls:/etc/platform_gateway/tls']})
            payload['Image'] = spec['id']
        payload.pop('NetworkingConfig', None)
        # nginx -t binds no listening sockets. Keep site DNS/upstream access,
        # while omitting the old endpoint's static address and aliases.
        payload['HostConfig']['NetworkMode'] = old['HostConfig'].get('NetworkMode', 'default') if old else 'host'
        payload['MacAddress'] = ''
        payload['HostConfig']['PortBindings'] = {}
        payload['HostConfig']['RestartPolicy'] = {'Name': 'no'}
        payload['Entrypoint'] = ['nginx']
        payload['Cmd'] = ['-t']
        name = 'oneclick_nginx_check_' + self.stamp
        created = False
        try:
            self.docker.create(name, payload)
            created = True
            run(['docker', 'start', name])
            status = run(['docker', 'wait', name]).stdout.strip()
            if status != '0':
                raise RuntimeError('新前端使用原配置执行 nginx -t 失败；原平台尚未停止')
        finally:
            if created:
                run(['docker', 'rm', '-f', name], check=False)
        print('[ OK ] 新前端带原配置及证书执行 nginx -t 通过', flush=True)

    def replace(self, name):
        old = self.original[name]
        spec = self.images[name]
        if old:
            if name == 'seal_system' and self.signing_guard:
                current = inspect_container(name)
                if not current or current['Id'] != old['Id']:
                    raise RuntimeError('原后台容器在预检查后发生变化，未停止后台')
                assert_preserved(self.signing_guard, active_snapshot(current, self.root))
            config = image_info(old['Image'])['Config']
            payload = container_payload(old, spec['id'], config, spec['config'])
            if name == 'seal_system' and self.signing_guard:
                pin_backend_security(payload, self.signing_guard)
            previous = name + '_oneclick_prev_' + self.stamp
            run(['docker', 'stop', '-t', '30', name])
            self.stopped_containers.append(name)
            run(['docker', 'rename', name, previous])
            self.old_names[name] = previous
            run(['docker', 'update', '--restart=no', previous])
            mode = old['HostConfig'].get('NetworkMode', 'default')
            if mode not in ('host', 'none') and not mode.startswith('container:'):
                for network in old.get('NetworkSettings', {}).get('Networks', {}):
                    run(['docker', 'network', 'disconnect', network, previous])
                    self.disconnected.append((name, network))
        else:
            config = copy.deepcopy(spec['config'])
            config['Image'] = spec['id']
            root = str(self.root)
            if name == 'seal_system':
                binds = [root + '/Config_files/config.ini:/Seal_system/config.ini',
                         root + '/Config_files/nginx.conf:/etc/nginx/nginx.conf',
                         root + '/Config_files/platform-security.json:/Seal_system/platform-security.json:ro']
                result_dir = (Path('/home/AIGO/python/bingxing_model/results')
                              if self.root == Path('/home/AIGO') else self.root / 'AIGO/python/bingxing_model/results')
                if not result_dir.is_dir():
                    absent = []
                    parent = result_dir
                    while not parent.exists():
                        absent.append(parent)
                        parent = parent.parent
                    result_dir.mkdir(parents=True, mode=0o755)
                    for path in absent:
                        os.chmod(str(path), 0o755)
                    self.created_data_dirs.extend(reversed(absent))
                binds.append(str(result_dir) + ':/data/AIGO/python/bingxing_model/results')
                environment = dict(value.split('=', 1) for value in config.get('Env', []) if '=' in value)
                environment.update({
                    'PLATFORM_SECURITY_CONFIG': '/Seal_system/platform-security.json',
                    'HOST_MACHINE_ID': Path('/etc/machine-id').read_text().strip(),
                    'ZLK_PUBLIC_BASE_URL': 'https://%s:8888/media' % self.target,
                    'SEAL_ALLOWED_ORIGINS': 'https://%s:8888' % self.target,
                })
                config['Env'] = [key + '=' + value for key, value in environment.items()]
            elif name == 'seal_system_vue':
                binds = [root + '/platform_gateway/default.conf:/etc/nginx/conf.d/default.conf',
                         root + '/Config_files/config.js:/usr/share/nginx/html/static/js/config.js',
                         root + '/platform_gateway/tls:/etc/platform_gateway/tls']
                transport = self.root / 'Config_files/secure-transport.js'
                if transport.is_file():
                    binds.append(str(transport) + ':/usr/share/nginx/html/static/js/secure-transport.js')
            else:
                binds = [root + '/Config_files/zlk/config.ini:/opt/media/conf/config.ini']
            if getattr(self, 'bulk', None):
                binds.extend(self.bulk.container_binds(name))
            payload = dict(config, HostConfig={'NetworkMode': 'host', 'Binds': binds,
                                               'RestartPolicy': {'Name': 'always'}})
            if getattr(self, 'bulk', None) and self.bulk.root:
                payload['HostConfig']['LogConfig'] = {'Type': 'json-file',
                                                     'Config': {'max-size': '20m', 'max-file': '5'}}
        self.docker.create(name, payload)
        self.created.append(name)
        run(['docker', 'start', name])

    def apply(self):
        if self.profile:
            self.profile.apply(self.backup)
        self.stopped_services = True
        run(['systemctl', 'stop', SERVICES[1], SERVICES[0]])
        with contextlib.closing(sqlite3.connect(self.auth_db.as_uri() + '?mode=ro', uri=True)) as source:
            with contextlib.closing(sqlite3.connect(str(self.backup / 'auth.sqlite3'))) as dest:
                source.backup(dest)
        os.chmod(str(self.backup / 'auth.sqlite3'), 0o600)
        for name, content in self.code.items():
            dest = self.root / 'config_dispatch' / name
            temp = dest.with_name(dest.name + '.oneclick-new')
            temp.write_bytes(content)
            if dest.exists():
                info = dest.stat()
                # Preserve named ACLs/xattrs as well as mode bits when atomic
                # replacement creates a new inode for an existing program.
                shutil.copystat(str(dest), str(temp))
                os.chown(str(temp), info.st_uid, info.st_gid)
            else:
                owner_source = self.root / 'config_dispatch/secure_server.py'
                info = (owner_source if owner_source.exists() else owner_source.parent).stat()
                os.chown(str(temp), info.st_uid, info.st_gid)
                os.chmod(str(temp), 0o644)
            os.replace(str(temp), str(dest))
        if 'zlk' in self.images:
            self.replace('zlk')
        self.replace('seal_system')
        self.replace('seal_system_vue')
        run(['systemctl', 'start', SERVICES[0], SERVICES[1]])
        healthcheck(self.target, replaced=tuple(self.created))
        self.check_preserved()

    def check_preserved(self):
        if self.signing_guard:
            assert_preserved(self.signing_guard, active_snapshot(inspect_container('seal_system'), self.root))
        for raw, digest in self.hashes.items():
            if not Path(raw).is_file() or file_digest(raw) != digest:
                raise RuntimeError('原配置内容发生变化：' + raw)
        if auth_fingerprint(self.auth_db) != self.auth_hash:
            raise RuntimeError('8899 原账号、密码或权限发生变化')

    def rollback(self):
        print('[WARN] 验证未通过，恢复原平台程序与容器 ...', flush=True)
        failures = []
        if self.stopped_services:
            run(['systemctl', 'stop', SERVICES[1], SERVICES[0]], check=False)
        for name in reversed(self.created):
            if run(['docker', 'rm', '-f', name], check=False).returncode:
                failures.append(name)
        for name, previous in self.old_names.items():
            if run(['docker', 'rename', previous, name], check=False).returncode:
                failures.append(previous)
                continue
            old = self.original[name]
            for container, network in self.disconnected:
                if container != name:
                    continue
                endpoint = old['NetworkSettings']['Networks'][network]
                args = ['docker', 'network', 'connect']
                ipam = endpoint.get('IPAMConfig') or {}
                for key, flag in (('IPv4Address', '--ip'), ('IPv6Address', '--ip6')):
                    if ipam.get(key):
                        args += [flag, ipam[key]]
                for alias in endpoint.get('Aliases') or []:
                    args += ['--alias', alias]
                if run(args + [network, name], check=False).returncode:
                    failures.append(network)
            policy = old['HostConfig'].get('RestartPolicy') or {'Name': 'no'}
            restart = policy.get('Name') or 'no'
            if restart == 'on-failure' and policy.get('MaximumRetryCount'):
                restart += ':' + str(policy['MaximumRetryCount'])
            run(['docker', 'update', '--restart=' + restart, name], check=False)
        if self.stopped_services:
            for dest, backup in self.code_backups.items():
                if backup:
                    shutil.copy2(backup, dest)
                    info = Path(backup).stat()
                    os.chown(dest, info.st_uid, info.st_gid)
                elif Path(dest).exists():
                    Path(dest).unlink()
            # Restore only files changed by a new platform during failed startup.
            for raw, digest in self.hashes.items():
                if not Path(raw).is_file() or file_digest(raw) != digest:
                    source = self.backup / 'original-files' / raw.lstrip('/')
                    shutil.copy2(str(source), raw)
                    info = source.stat()
                    os.chown(raw, info.st_uid, info.st_gid)
            try:
                auth_changed = auth_fingerprint(self.auth_db) != self.auth_hash
            except (sqlite3.Error, OSError, RuntimeError):
                auth_changed = True
            if auth_changed:
                for suffix in ('-wal', '-shm'):
                    Path(str(self.auth_db) + suffix).unlink(missing_ok=True)
                original_stat = self.auth_stat
                shutil.copy2(str(self.backup / 'auth.sqlite3'), str(self.auth_db))
                os.chown(str(self.auth_db), original_stat.st_uid, original_stat.st_gid)
        if self.profile:
            try:
                self.profile.rollback()
            except Exception:
                failures.append('8899 服务身份/单元/权限回退')
        if self.stopped_services:
            for service in SERVICES:
                if self.services_running.get(service):
                    if run(['systemctl', 'start', service], check=False).returncode:
                        failures.append(service)
        # Only start originals after their configuration and account store have
        # been restored, including the stop-succeeded/rename-failed case.
        for name in self.stopped_containers:
            if self.original[name]['State'].get('Running'):
                if run(['docker', 'start', name], check=False).returncode:
                    failures.append(name)
        for path in reversed(self.created_data_dirs):
            try:
                path.rmdir()
            except OSError:
                # Never remove results created during a failed first startup.
                pass
        if failures:
            raise RuntimeError('部分回退操作失败，请依据受保护备份恢复：' + ', '.join(failures))
        print('[ OK ] 原平台程序与容器已恢复', flush=True)

    def execute(self):
        from bulk_storage import Storage
        storage = Storage(str(self.root), self.env.get('PLATFORM_BULK_ROOT', ''), 'platform',
                          self.env.get('ONECLICK_ROOT', '/root/oneclick'))
        storage.preflight()
        storage.verify()
        self.bulk = storage
        self.preflight()
        self.snapshot()
        self.load_images()
        self.validate_frontend()
        try:
            self.apply()
        except Exception:
            self.rollback()
            raise
        (self.backup / 'result.json').write_text(json.dumps({
            'result': 'PASS', 'original_configuration_unchanged': True,
            'auth_accounts_unchanged': True, 'previous_containers': self.old_names,
            'middleware_changed': False,
            'created_platform_units': list(map(str, self.profile.created_units)) if self.profile else [],
            'created_platform_users': self.profile.created_users if self.profile else []}, indent=2), 'utf-8')
        print('[ OK ] 两个平台已更新；原配置、连接账密、证书和账号权限保留', flush=True)
        print('[ OK ] 旧容器停止并保留（自动重启已关闭），回退资料：' + str(self.backup), flush=True)


def main():
    os.umask(0o077)
    try:
        if os.geteuid() != 0:
            raise RuntimeError('请使用 root 执行')
        root = Path(os.environ.get('ONECLICK_ROOT', '/root/oneclick'))
        if (root / 'release-lock.json').exists():
            from release_media import audit
            arch = normalize_arch(os.uname().machine)
            profile = 'ubuntu20.04-x86_64-sc7' if arch == 'x86_64' else 'openeuler22.03-sp4-aarch64-ascend310p3'
            audit(root, profile, scope='platform')
        PlatformUpdate().execute()
    except Exception as exc:
        print('[FAIL] ' + str(exc), flush=True)
        print('DEPLOY_RESULT=FAIL', flush=True)
        return 1
    print('DEPLOY_RESULT=PASS', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
