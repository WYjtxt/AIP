#!/usr/bin/env python3
"""Install platform code and native services in one configurable directory."""
import configparser
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

DEFAULT_ROOT = '/data/AIGO/platform_start'
SHARED_DIRS = ('platform_alarm_media', 'platform_counts', 'platform_runtime_health', 'platform_storage')
SERVICES = ('ai-platform-backend', 'ai-platform-media', 'ai-platform-web',
            'config-dispatch', 'config-dispatch-gateway')
MEDIA_ENVIRONMENT = {}


def run(args, **kwargs):
    print('+ ' + ' '.join(str(a) for a in args[:3]), flush=True)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def write(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    path.chmod(mode)


def selected_root(value):
    value = value or DEFAULT_ROOT
    path = Path(value)
    if not path.is_absolute() or str(path) in ('/', '/data', '/usr', '/etc', '/root', '/opt', '/home'):
        raise ValueError('请选择专用安装目录，例如 ' + DEFAULT_ROOT)
    if any(c in value for c in '\n\r\x00'):
        raise ValueError('安装目录包含无效字符')
    return path.resolve()


def render(text, root, ip):
    # One pass matters because the selected directory may itself start with /data.
    shared = root.parent
    mapping = {
        '/data/sophon/ModelZoo/YOLO/python/bingxing_model': str(root / 'platform_algorithm_start'),
        '/data/AIGO/python/bingxing_model/results': str(shared / 'outputs'),
        '/home/AIGO/python/bingxing_model/results': str(shared / 'outputs'),
        '/Seal_system': str(root / 'backend'),
        '/usr/share/nginx/html': str(root / 'frontend'),
        '/usr/share/fonts': str(root / 'runtime/fonts'),
        '/etc/platform_gateway': str(root / 'platform_gateway'),
        '/opt/Config_files/miniconda3': str(root / 'runtime/miniconda3'),
        '/opt/nginx': str(root / 'runtime/nginx'),
        '/opt/media': str(root / 'media'),
        '/usr/bin/ffmpeg': str(root / 'runtime/bin/ffmpeg'),
        '/usr/bin/ffprobe': str(root / 'runtime/bin/ffprobe'),
        '/tmp/platform-host-disks.json': str(shared / 'platform_storage/host-disks.json'),
        '/data': str(root),
    }
    for name in SHARED_DIRS:
        mapping['/data/' + name] = str(shared / name)
        mapping['/data/AIGO/' + name] = str(shared / name)
        mapping[str(root / name)] = str(shared / name)
        mapping['/data/AIGO/ai_platform_start/' + name] = str(shared / name)
        mapping[str(shared / name)] = str(shared / name)
    mapping['/data/AIGO/outputs'] = str(shared / 'outputs')
    mapping[str(shared / 'outputs')] = str(shared / 'outputs')
    mapping[str(root / 'results')] = str(shared / 'outputs')
    mapping['/data/AIGO/ai_platform_start/results'] = str(shared / 'outputs')
    mapping['/data/AIGO/ai_platform_start'] = str(root)
    mapping[str(root)] = str(root)
    pattern = '|'.join(re.escape(k) + r'(?=/|[\s\x22\x27;,:\)\]\}]|$)' for k in sorted(mapping, key=len, reverse=True))
    text = re.sub(pattern, lambda m: mapping[m.group()], text)
    return text.replace('192.168.113.100', ip).replace('192.168.110.47', ip)


def unpack(archive, root, template=False, preserve=False, keep_site=False):
    hardlinks = []
    with tarfile.open(str(archive)) as source:
        for member in source:
            name = member.name.lstrip('./')
            if template:
                if not name.startswith('data/'):
                    continue
                name = name[5:]
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('压缩包包含无效路径：' + name)
            target = root / relative
            if keep_site and target.exists() and (name.startswith('backend/config/') and target.suffix != '.py' or
                    name in ('backend/config.ini', 'backend/platform-security.json')):
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                if preserve and target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink():
                    target.unlink()
                with source.extractfile(member) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(member.mode & 0o777)
            elif member.issym():
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() and not target.is_symlink():
                    target.symlink_to(member.linkname)
            elif member.islnk():
                linked = root / member.linkname.lstrip('./')
                hardlinks.append((target, linked))
    # Tar archives may list a hardlink before the file data or another alias.
    while hardlinks:
        pending = []
        for target, linked in hardlinks:
            if linked.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and os.path.samefile(str(target), str(linked)):
                    continue
                if target.exists() or target.is_symlink():
                    target.unlink()
                os.link(str(linked), str(target))
            else:
                pending.append((target, linked))
        if len(pending) == len(hardlinks):
            raise ValueError('压缩包硬链接目标缺失：' + str(pending[0][1]))
        hardlinks = pending


def link(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() == source.resolve():
            return
        destination.unlink()
    elif destination.exists():
        destination.unlink()
    destination.symlink_to(source)


def unit(name, command, cwd, environment=None, after='network.target'):
    environment = dict(MEDIA_ENVIRONMENT, **(environment or {}))
    settings = ''.join('Environment=' + shlex.quote(str(k) + '=' + str(v)) + '\n'
                       for k, v in (environment or {}).items())
    text = ('[Unit]\nDescription=AI platform ' + name + '\nAfter=' + after + '\n'
            '[Service]\nType=simple\nWorkingDirectory=' + str(cwd) + '\n' + settings +
            'ExecStart=' + ' '.join(shlex.quote(str(a)) for a in command) + '\n'
            'Restart=on-failure\nRestartSec=5\nUMask=0022\nLimitNOFILE=65535\n'
            '[Install]\nWantedBy=multi-user.target\n')
    write('/etc/systemd/system/' + name + '.service', text)


def start(names):
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable'] + list(names), stdout=subprocess.DEVNULL)
    run(['systemctl', 'restart'] + list(names))


def stop_owned_services(root, include_algorithms=True):
    names = ['platform-host-disks.timer'] + list(SERVICES) + ['platform-ops', 'platform-push-worker', 'platform-alarm-storage',
             'platform-host-disks']
    if include_algorithms:
        names += ['model_start', 'resource', 'kafka_consumer']
    owned = []
    for name in names:
        filename = name if name.endswith('.timer') else name + '.service'
        path = Path('/etc/systemd/system') / filename
        owner = path.with_suffix('.service') if name.endswith('.timer') else path
        if owner.is_file() and str(root) in owner.read_text(encoding='utf-8'):
            active = subprocess.run(['systemctl', 'is-active', '--quiet', name])
            if active.returncode == 0:
                owned.append(name)
    if owned:
        run(['systemctl', 'stop'] + owned)


def rewrite_sources(root, ip, directories):
    for folder in directories:
        for path in (root / folder).rglob('*'):
            if path.is_symlink() or path.suffix not in ('.py', '.ini', '.conf', '.json', '.cnf', '.ext', '.js', '.sh'):
                continue
            if not path.is_file() or path.stat().st_size > 12 * 1024 * 1024:
                continue
            try:
                original = path.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            # Already-rendered files should not acquire a repeated root on repair.
            token = '__NATIVE_INSTALL_ROOT__'
            text = render(original.replace(str(root), token), root, ip).replace(token, str(root))
            if text != original:
                path.write_text(text, encoding='utf-8')


def configure_api_transport(root):
    config = root / 'Config_files/config.js'
    text = config.read_text(encoding='utf-8')
    updated = re.sub(r'(?m)^(\s*url_5000\s*:)[^,\r\n]+',
                     r"\1 window.location.origin + '/api'", text)
    if updated != text:
        write(config, updated)
    transport = root / 'frontend/static/js/secure-transport.js'
    index = root / 'frontend/index.html'
    version = 'native-api-' + hashlib.sha256(transport.read_bytes()).hexdigest()[:10]
    text = index.read_text(encoding='utf-8')
    config_version = 'native-config-' + hashlib.sha256(config.read_bytes()).hexdigest()[:10]
    text = re.sub(r'(?<=static/js/)config\.js(?:\?[^\s\x22\x27<>]*)?',
                  'config.js?v=' + config_version, text)
    updated = re.sub(r'secure-transport\.js(?:\?[^\s\x22\x27<>]*)?',
                     'secure-transport.js?v=' + version, text)
    if updated != text:
        write(index, updated)


def configure(root, ip, env, new_site):
    config = root / 'Config_files'
    if new_site:
        for folder in ('Config_files', 'config_dispatch', 'model_algorithm_package', 'platform_algorithm_start'):
            for path in (root / folder).rglob('*'):
                if path.is_file() and path.suffix in ('.ini', '.py', '.json'):
                    try:
                        text = path.read_text(encoding='utf-8')
                    except UnicodeError:
                        continue
                    for key, value in (('__ONECLICK_DB_PASSWORD__', env.get('MYSQL_ROOT_PASS', '')),
                                       ('__ONECLICK_BOX_PASSWORD__', env.get('BOX_PASS', ''))):
                        if path.suffix == '.py':
                            text = text.replace(repr(key), repr(value)).replace('"' + key + '"', repr(value))
                        else:
                            text = text.replace(key, value)
                    path.write_text(text, encoding='utf-8')
    signing = config / 'platform-security.json'
    settings = json.loads(signing.read_text()) if signing.exists() else {}
    for key in ('SESSION_SECRET_KEY', 'JWT_SECRET_KEY', 'MEDIA_SESSION_SECRET_KEY'):
        if not settings.get(key) or settings[key] in ('GENERATE_ON_TARGET', '__GENERATE_ON_TARGET__'):
            settings[key] = secrets.token_hex(48)
    write(signing, json.dumps(settings), 0o600)
    media_settings = configparser.ConfigParser(interpolation=None, strict=False)
    media_settings.read(str(config / 'zlk/config.ini'), encoding='utf-8')
    secret = media_settings.get('api', 'secret', fallback='')
    if not secret or secret == '__ONECLICK_ZLK_SECRET__':
        secret = secrets.token_hex(24)
    for path in (config / 'config.ini', config / 'zlk/config.ini'):
        text = path.read_text(encoding='utf-8').replace('__ONECLICK_ZLK_SECRET__', secret)
        write(path, text)
    model_config = root / 'model_algorithm_package/Conf_files.py'
    if model_config.is_file():
        source = model_config.read_text(encoding='utf-8')
        source = re.sub(r'(?m)^ZLK_SECRET\s*=.*$', lambda _: 'ZLK_SECRET = ' + repr(secret), source)
        write(model_config, source.replace('__ONECLICK_ZLK_SECRET__', secret))
    if new_site:
        path = config / 'config.ini'
        text = re.sub(r'(?m)^(Redis_ip\s*=).*$', r'\1 127.0.0.1', path.read_text(encoding='utf-8'))
        write(path, text)
        conf = root / 'model_algorithm_package/Conf_files.py'
        if conf.exists():
            text = re.sub(r"(?m)^(Redis_ip\s*=).*", r"\1 '127.0.0.1'", conf.read_text(encoding='utf-8'))
            write(conf, text)
    for folder in ('backend', 'frontend', 'media', 'platform_gateway', 'config_dispatch',
                   'model_algorithm_package', 'platform_algorithm_start', 'logs',
                   'backups',
                   'platform_ops/state', 'config_dispatch/state', 'config_dispatch/backups',
                   'config_dispatch/gateway/run', 'config_dispatch/gateway/temp'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for name in SHARED_DIRS + ('outputs', 'platform_storage/config', 'platform_storage/alarm-volumes'):
        (root.parent / name).mkdir(parents=True, exist_ok=True)
    dispatch_settings = root / 'config_dispatch/security-settings.json'
    data = json.loads(dispatch_settings.read_text(encoding='utf-8'))
    data['data_root'] = str(root)
    data['allowed_paths'] = [p for p in data['allowed_paths'] if Path(p).is_file()]
    write(dispatch_settings, json.dumps(data, ensure_ascii=False, indent=2), 0o644)
    for source, destination in ((config / 'config.ini', root / 'backend/config.ini'),
                                (signing, root / 'backend/platform-security.json'),
                                (config / 'config.js', root / 'frontend/static/js/config.js'),
                                (config / 'zlk/config.ini', root / 'media/conf/config.ini')):
        link(source, destination)
    configure_api_transport(root)
    # Dispatch validates regular files and rejects group/other writable configs.
    for folder in ('Config_files', 'config_dispatch', 'model_algorithm_package', 'platform_algorithm_start'):
        for path in (root / folder).rglob('*'):
            if not path.is_symlink():
                path.chmod((path.stat().st_mode & 0o777) & ~0o022)


def certificates(root, ip):
    import tempfile

    ca = root / 'config_dispatch/tls/ca'
    ca.mkdir(parents=True, exist_ok=True)
    ca.chmod(0o700)
    config = ca / 'minimal-openssl.cnf'
    write(config, '[req]\nprompt = no\ndistinguished_name = req_dn\n'
          '[req_dn]\nO = AI Platform\nCN = AI Platform\n'
          '[v3_ca]\nbasicConstraints = critical, CA:TRUE\n'
          'keyUsage = critical, keyCertSign, cRLSign\nsubjectKeyIdentifier = hash\n')
    executable = '/usr/bin/openssl' if Path('/usr/bin/openssl').is_file() else (shutil.which('openssl') or 'openssl')
    environment = dict(os.environ)
    for name in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'OPENSSL_CONF', 'OPENSSL_MODULES', 'PYTHONHOME', 'PYTHONPATH'):
        environment.pop(name, None)
    environment['OPENSSL_CONF'] = str(config)

    def openssl(arguments):
        print('+ openssl ' + arguments[0], flush=True)
        result = subprocess.run([executable] + [str(value) for value in arguments],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=environment)
        if result.returncode:
            error = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',
                           '[private key omitted]', result.stderr or '', flags=re.S)
            error = '\n'.join(line for line in error.splitlines() if not re.fullmatch(r'[.+*\s]+', line)).strip()
            raise RuntimeError('OpenSSL ' + arguments[0] + ' failed (rc=' + str(result.returncode)
                               + '): ' + (error[-2000:] or 'no stderr returned'))
        return result.stdout

    def present(path):
        return path.is_file() and path.stat().st_size > 0

    ca_key, ca_cert = ca / 'root.key', ca / 'root.crt'
    if present(ca_cert) and not present(ca_key):
        raise ValueError('现有 CA 证书缺少私钥，证书已保留，请恢复对应 root.key 后使用 repair。')
    if not present(ca_cert):
        with tempfile.TemporaryDirectory(prefix='.openssl-ca-', dir=str(ca)) as temporary:
            temporary = Path(temporary)
            key = ca_key if present(ca_key) else temporary / 'root.key'
            arguments = ['req', '-x509', '-config', config, '-extensions', 'v3_ca']
            arguments += ['-key', key] if present(ca_key) else ['-newkey', 'rsa:3072', '-nodes', '-keyout', key]
            openssl(arguments + ['-out', temporary / 'root.crt', '-days', '3650', '-sha256',
                                  '-subj', '/O=AI Platform/CN=AI Platform Root CA'])
            if key != ca_key:
                key.chmod(0o600)
                os.replace(str(key), str(ca_key))
            os.replace(str(temporary / 'root.crt'), str(ca_cert))
    ca_key.chmod(0o600)
    for folder in (root / 'platform_gateway/tls', root / 'config_dispatch/tls/server'):
        folder.mkdir(parents=True, exist_ok=True)
        key, certificate = folder / 'server.key', folder / 'server.crt'
        if present(certificate) and not present(key):
            raise ValueError('现有服务器证书缺少私钥，证书已保留，请恢复对应 server.key 后使用 repair：' + str(folder))
        if not present(certificate):
            ext = folder / 'native.ext'
            write(ext, 'subjectAltName=IP:' + ip + ',DNS:localhost\nextendedKeyUsage=serverAuth\n')
            with tempfile.TemporaryDirectory(prefix='.openssl-leaf-', dir=str(folder)) as temporary:
                temporary = Path(temporary)
                signing_key = key if present(key) else temporary / 'server.key'
                arguments = ['req', '-new', '-config', config]
                arguments += ['-key', signing_key] if present(key) else ['-newkey', 'rsa:2048', '-nodes', '-keyout', signing_key]
                openssl(arguments + ['-out', temporary / 'server.csr', '-subj', '/CN=' + ip])
                openssl(['x509', '-req', '-in', temporary / 'server.csr', '-CA', ca_cert,
                         '-CAkey', ca_key, '-CAcreateserial', '-out', temporary / 'server.crt',
                         '-days', '1825', '-sha256', '-extfile', ext])
                if signing_key != key:
                    signing_key.chmod(0o600)
                    os.replace(str(signing_key), str(key))
                os.replace(str(temporary / 'server.csr'), str(folder / 'server.csr'))
                os.replace(str(temporary / 'server.crt'), str(certificate))
        key.chmod(0o600)
        write(folder / 'server-chain.crt', (folder / 'server.crt').read_text() + (ca / 'root.crt').read_text())
    pem = root / 'Config_files/zlk/default.pem'
    write(pem, (root / 'platform_gateway/tls/server.key').read_text() +
          (root / 'platform_gateway/tls/server-chain.crt').read_text(), 0o600)
    link(pem, root / 'media/bin/default.pem')
    target = root / 'frontend/static/certificates'
    target.mkdir(parents=True, exist_ok=True)
    openssl(['x509', '-in', ca_cert, '-outform', 'DER', '-out', target / 'dispatch-root-ca.cer'])
    shutil.copy2(str(target / 'dispatch-root-ca.cer'), str(root / 'config_dispatch/dispatch-root-ca.cer'))
    details = openssl(['x509', '-in', ca_cert, '-noout', '-subject', '-startdate', '-enddate',
                       '-nameopt', 'RFC2253,sep_comma_plus_space'])
    fields = dict(line.split('=', 1) for line in details.strip().splitlines())
    subject = fields['subject']
    metadata = {'subject': subject,
                'commonName': re.search(r'(?:^|, )CN=([^,]+)', subject).group(1),
                'sha256': hashlib.sha256((target / 'dispatch-root-ca.cer').read_bytes()).hexdigest().upper()}
    for field, label in (('notBeforeUtc', 'notBefore'), ('notAfterUtc', 'notAfter')):
        metadata[field] = time.strftime('%Y-%m-%dT%H:%M:%SZ',
            time.gmtime(ssl.cert_time_to_seconds(fields[label])))
    from native_frontend_fixes import refresh_certificate_help
    refresh_certificate_help(root, metadata)
    with zipfile.ZipFile(str(target / 'dispatch-certificate-windows.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('dispatch-root-ca.cer', 'install-dispatch-certificate.ps1', 'README.txt'):
            if (target / name).is_file():
                archive.write(str(target / name), name)


def gateways(root, nginx):
    gateway = root / 'platform_gateway'
    default = gateway / 'default.conf'
    text = default.read_text(encoding='utf-8')
    text = '\n'.join(line for line in text.splitlines() if 'container' not in line.lower()) + '\n'
    text = text.replace('/var/log/nginx/platform-access.log', str(root / 'logs/web-access.log'))
    text = text.replace('/var/log/nginx/platform-error.log', str(root / 'logs/web-error.log'))
    write(default, text)
    # Use the packaged gateway rules unchanged inside a standalone host nginx.
    write(gateway / 'nginx.conf', 'user root;\nworker_processes auto;\npid ' + str(gateway / 'nginx.pid') +
          ';\nerror_log stderr warn;\nevents { worker_connections 1024; }\nhttp {\n'
          'access_log off;\n'
          'include ' + str(root / 'runtime/nginx/conf/mime.types') + ';\n'
          'client_body_temp_path ' + str(gateway / 'temp/client') + ';\n'
          'proxy_temp_path ' + str(gateway / 'temp/proxy') + ';\n'
          'fastcgi_temp_path ' + str(gateway / 'temp/fastcgi') + ';\n'
          'uwsgi_temp_path ' + str(gateway / 'temp/uwsgi') + ';\n'
          'scgi_temp_path ' + str(gateway / 'temp/scgi') + ';\n'
          'include ' + str(default) + ';\n'
          'server { listen 127.0.0.1:9002;\n'
          'location /alarm-storage/ { alias ' + str(root.parent / 'platform_alarm_media') + '/; }\n'
          'location ' + str(root.parent / 'outputs') + '/ { alias ' + str(root.parent / 'outputs') + '/; }\n'
          '}\n}\n')
    (gateway / 'temp').mkdir(parents=True, exist_ok=True)
    dispatch = root / 'config_dispatch/gateway'
    dispatch_conf = dispatch / 'nginx.conf'
    dispatch_text = dispatch_conf.read_text(encoding='utf-8')
    if not re.search(r'(?m)^\s*user\s+', dispatch_text):
        write(dispatch_conf, 'user root;\n' + dispatch_text)
    for folder in ('client', 'proxy', 'fastcgi', 'uwsgi', 'scgi'):
        (dispatch / 'temp' / folder).mkdir(parents=True, exist_ok=True)
        (gateway / 'temp' / folder).mkdir(parents=True, exist_ok=True)
    for name, folder in (('ai-platform-web', gateway), ('config-dispatch-gateway', dispatch)):
        run([nginx, '-t', '-p', str(folder) + '/', '-c', folder / 'nginx.conf'])
        unit(name, [nginx, '-p', str(folder) + '/', '-c', folder / 'nginx.conf', '-g', 'daemon off;'], folder)


def backend_database(root, pay, env):
    python = root / 'runtime/bin/python'
    working = root / 'backend'
    helpers = root / 'runtime/tools'
    helpers.mkdir(parents=True, exist_ok=True)
    for name in ('sync_reference_database.py', 'bootstrap_platform_admin.py', 'migrate_admin_menu_permissions.py'):
        source = (pay / name).read_text(encoding='utf-8')
        source = source.replace('/Seal_system', str(working)).replace('/tmp/oneclick-reference.json', str(pay / 'reference-47/database.json'))
        source = source.replace('/tmp/oneclick-initial-admin.json', str(root / 'initial-access.json'))
        write(helpers / name, source, 0o700)
        run([python, helpers / name], cwd=str(working), env=dict(os.environ, **env))


def initialize_site_content(root, pay, env, phase):
    """Fill missing install defaults while preserving existing site choices."""
    helpers = root / 'runtime/tools'
    for name in ('native_initial_content.py', 'native_initial_device.py', 'native_initial_model.py'):
        write(helpers / name, (pay / name).read_text(encoding='utf-8'), 0o700)
    run([root / 'runtime/bin/python', '-B', helpers / 'native_initial_content.py',
         '--root', root, '--models-root', pay / 'preinstalled_models', '--phase', phase],
        cwd=str(root / 'backend'), env=dict(os.environ, **env))


def algorithm_runtime(root, packages, arch, env):
    if arch != 'aarch64':
        from native_sophon_runtime import install as install_sophon
        return install_sophon(root, packages, env, run, unit)
    media = packages / arch / 'python'
    if not media.is_dir():
        media = packages / 'python'
    conda = root / 'runtime/miniconda3'
    if not (conda / 'bin/python').exists():
        installer = next(media.glob('Miniconda3-*.sh'))
        run(['bash', installer, '-b', '-p', conda])
    yolo = conda / 'envs/yolo'
    if not (yolo / 'bin/python').exists():
        yolo.mkdir(parents=True, exist_ok=True)
        unpack(media / 'yolo-env.tar.gz', yolo)
        run([yolo / 'bin/python', yolo / 'bin/conda-unpack'])
    cann = next((p for p in (root / 'runtime/Ascend/cann-9.0.0',
                  Path('/usr/local/Ascend/cann-9.0.0-full/cann-9.0.0'),
                  Path('/usr/local/Ascend/cann-9.0.0'), Path('/usr/local/Ascend/cann'),
                  Path('/usr/local/Ascend/ascend-toolkit/latest')) if any(
                  (p / suffix).exists() for suffix in ('lib64/libacl_dvpp.so', arch + '-linux/lib64/libacl_dvpp.so'))), None)
    if cann is None:
        asc = packages / arch / 'AscendConfig'
        if not asc.is_dir():
            asc = packages / 'AscendConfig'
        for installer in asc.glob('*.run'):
            installer.chmod(0o755)
        if not Path('/usr/local/Ascend/driver/version.info').exists():
            run(['bash', next(asc.glob('*npu-driver*.run')), '--full', '--quiet'])
        install_root = root / 'runtime/Ascend'
        install_root.mkdir(parents=True, exist_ok=True)
        run(['bash', next(asc.glob('*toolkit*.run')), '--install', '--quiet', '--install-for-all',
             '--install-path=' + str(install_root)])
        ops = next(asc.glob('*ops*.run'), None)
        if ops:
            run(['bash', ops, '--install', '--quiet', '--install-for-all',
                 '--install-path=' + str(install_root)])
        cann = install_root / 'cann-9.0.0'
    if not any((cann / path).is_file() for path in
               ('lib64/libacl_dvpp.so', arch + '-linux/lib64/libacl_dvpp.so')):
        raise RuntimeError('CANN 安装后缺少 310P DVPP 库：' + str(cann))
    cannlibs = str(cann / (arch + '-linux/lib64')) + ':' + str(cann / 'lib64') + ':' + str(cann / 'opp/lib64')
    settings = {'ASCEND_TOOLKIT_PATH': str(cann),
                'ASCEND_OPP_PATH': str(cann / 'opp'),
                'ASCEND_PROCESS_LOG_PATH': str(root / 'logs/ascend'),
                'LD_LIBRARY_PATH': cannlibs + ':/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver',
                'PYTHONPATH': str(cann / 'python/site-packages'), 'NPU_DEVICE_IDS': '0,1',
                'VIDEO_NATIVE_DISPLAY': '1', 'CV2_NUM_THREADS': '1',
                'PATH': str(yolo / 'bin') + ':' + str(root / 'runtime/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}
    (root / 'logs/ascend').mkdir(parents=True, exist_ok=True)
    names = []
    for name, folder, script in (('model_start', 'platform_algorithm_start', 'model_start.py'),
                                  ('resource', 'model_algorithm_package', 'Huawei_resource.py'),
                                  ('kafka_consumer', 'model_algorithm_package', 'kafka_consumer.py')):
        unit(name, [yolo / 'bin/python', root / folder / script], root / folder, settings)
        names.append(name)
    return names


def http_json(url, data=None, opener=None, headers=None):
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                    headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    response = (opener.open(request, timeout=15) if opener else
                urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=15))
    with response:
        return json.load(response)


def bootstrap_dispatch(ip, root, env):
    base = 'https://' + ip + ':8899'
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    for attempt in range(30):
        try:
            status = http_json(base + '/api/auth/status', opener=opener)
            break
        except (OSError, ValueError):
            if attempt == 29:
                raise
            time.sleep(2)
    if status.get('initialized'):
        print('8899 已有账号，保留原口令。')
        return
    username = env.get('ADMIN_8899_USER') or 'admin'
    password = env.get('ADMIN_8899_PASS', '')
    if username != 'admin' or not 15 <= len(password) <= 128:
        raise ValueError('8899 尚未初始化：请提供 admin 用户及 15 至 128 位管理员口令后重试')
    token = root / 'config_dispatch/state/bootstrap.token'
    try:
        result = http_json(base + '/api/auth/bootstrap', {
            'username': username, 'password': password,
            'token': token.read_text().strip()}, opener,
            {'Origin': base, 'X-CSRF-Token': status['csrf']})
    except urllib.error.HTTPError as error:
        try:
            reason = str(json.loads(error.read()).get('error', ''))[:250]
        except (ValueError, AttributeError):
            reason = ''
        reason = reason.replace(password, '[redacted]')
        raise RuntimeError('8899 管理员初始化失败（HTTP ' + str(error.code) + '）' +
                           ('：' + reason if reason else '')) from None
    if not result.get('ok'):
        raise RuntimeError('8899 管理员初始化失败')


def verify(root):
    state = json.loads((root / 'native-deployment.json').read_text(encoding='utf-8'))
    for name in state['services']:
        run(['systemctl', 'is-active', '--quiet', name])
    context = ssl._create_unverified_context()
    for port, path in ((8888, '/'), (8888, '/api/activate/activate_verify'), (8899, '/login')):
        url = 'https://' + state['target_ip'] + ':' + str(port) + path
        for attempt in range(30):
            try:
                with urllib.request.urlopen(url, context=context, timeout=5) as response:
                    if response.status != 200:
                        raise RuntimeError(url)
                print('HTTP=200 ' + url, flush=True)
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(2)
    print('VERIFY_RESULT=PASS', flush=True)


def unmount_platform_storage(base):
    prefixes = (base / 'platform_alarm_media', base / 'platform_storage/alarm-volumes')
    result = subprocess.run(['findmnt', '-rn', '-o', 'TARGET'], stdout=subprocess.PIPE,
                            universal_newlines=True, check=True)
    mounts = [Path(value) for value in result.stdout.splitlines()
              if any(value == str(p) or value.startswith(str(p) + '/') for p in prefixes)]
    for mount in sorted(mounts, key=lambda p: len(p.parts), reverse=True):
        current = subprocess.run(['findmnt', '-rn', '-M', str(mount)], stdout=subprocess.DEVNULL)
        if current.returncode == 0:
            run(['umount', mount])


def clean_configuration(root):
    from uninstall_platform import uninstall
    return uninstall(root, runtime='native')


def deploy(env):
    root = selected_root(env.get('PLATFORM_DATA_ROOT'))
    if any((root / marker).exists() for marker in ('container-deployment.json', 'container/images.json')):
        raise ValueError('该目录为容器部署，请选择 --runtime container，不能使用原生模式操作。')
    mode = env.get('MODE', 'repair')
    if mode == 'verify':
        verify(root)
        return
    if mode == 'clean':
        clean_configuration(root)
        return
    stage = Path(env.get('ONECLICK_ROOT', '/root/oneclick'))
    pay, packages = stage / 'payload', stage / 'packages'
    arch = env.get('TARGET_ARCH') or os.uname().machine
    manifest = json.loads((pay / 'native-release.json').read_text())
    files = manifest['architectures'][arch]['files']
    application = [f for f in files if f.get('scope') != 'full' and '/native/' in f['path']]
    if not {'backend-runtime.tar.gz', 'frontend-runtime.tar.gz', 'media-runtime.tar.gz'} <= {
            Path(f['path']).name for f in application}:
        raise ValueError('原生发布清单应包含前端、后端和媒体代码包')
    for entry in application:
        source = stage / entry['path']
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != entry['sha256']:
            raise ValueError('代码包校验失败：' + entry['path'])
    new_site = not (root / 'Config_files/config.ini').exists()
    if mode == 'fresh' and not new_site:
        raise ValueError('该目录已有平台，请选择 repair 续装或 platform 更新。')
    if mode == 'platform' and not (root / 'native-deployment.json').exists():
        raise ValueError('该目录尚未完成原生部署，请使用 repair。')
    if not new_site:
        settings = configparser.ConfigParser(interpolation=None)
        settings.read(str(root / 'Config_files/config.ini'))
        env['MYSQL_ROOT_PASS'] = settings['database']['DB_PASSWORD']
    root.mkdir(parents=True, exist_ok=True)
    print('原生部署目录：' + str(root), flush=True)
    # Back up site configuration before a repair or code update.
    if not new_site:
        backup = root / 'backups' / ('native-' + time.strftime('%Y%m%d_%H%M%S'))
        for folder in ('Config_files', 'config_dispatch/state', 'backend/config'):
            if (root / folder).is_dir():
                shutil.copytree(str(root / folder), str(backup / folder), symlinks=True)
        print('配置备份：' + str(backup))
    if mode != 'platform':
        from install_native_dependencies import install
        deps = install(root, packages, arch, env)
    else:
        deps = json.loads((root / 'native-deployment.json').read_text())['dependencies']
        run(['systemctl', 'start'] + deps['services'])
    stop_owned_services(root, include_algorithms=mode != 'platform')
    for entry in application:
        print('解压代码包：' + entry['path'], flush=True)
        unpack(stage / entry['path'], root, keep_site=not new_site)
    bundle = packages / arch / 'runtime_bundle.tar.gz'
    if mode != 'platform':
        unpack(bundle, root, template=True, preserve=True)
    unpack(pay / 'platform_code.tar.gz', root, template=True)
    ip = env['TARGET_IP']
    # Latest gateway/auth rules accompany the code, site certificates remain.
    ref_gateway = pay / 'reference-47/data/platform_gateway/default.conf'
    if ref_gateway.exists():
        shutil.copy2(str(ref_gateway), str(root / 'platform_gateway/default.conf'))
    rewrite_sources(root, ip, ('backend', 'frontend', 'Config_files', 'config_dispatch',
                             'platform_gateway', 'model_algorithm_package', 'platform_algorithm_start'))
    from native_ffmpeg import install as install_ffmpeg, media_environment
    install_ffmpeg(root)
    MEDIA_ENVIRONMENT.update(media_environment(root))
    from native_backend_fixes import (patch_recorder_bindings, patch_camera_ip_endpoint,
                                      patch_model_input_contracts, patch_native_version,
                                      patch_native_preview_recovery, patch_native_alarm_details,
                                      patch_native_model_bootstrap, patch_native_diagnosis_configuration,
                                      patch_native_diagnosis_runtime, patch_native_diagnosis_rating,
                                      patch_native_diagnosis_auto_reference, patch_native_user_capabilities,
                                      patch_native_role_management)
    patch_recorder_bindings(root)
    patch_camera_ip_endpoint(root)
    patch_model_input_contracts(root)
    patch_native_version(root)
    patch_native_preview_recovery(root)
    patch_native_alarm_details(root)
    patch_native_model_bootstrap(root)
    patch_native_diagnosis_configuration(root)
    patch_native_diagnosis_runtime(root)
    patch_native_diagnosis_rating(root)
    patch_native_diagnosis_auto_reference(root)
    patch_native_user_capabilities(root)
    patch_native_role_management(root)
    from native_role_policy import patch_native_role_policy
    patch_native_role_policy(root)
    configure(root, ip, env, new_site)
    certificates(root, ip)
    if (root / 'runtime/bin/nginx').exists():
        deps['nginx'] = str(root / 'runtime/bin/nginx')
    gateways(root, deps['nginx'])
    backend_database(root, pay, env)
    python = root / 'runtime/bin/python'
    backend_env = {'PLATFORM_SECURITY_CONFIG': str(root / 'Config_files/platform-security.json'),
                   'HOST_MACHINE_ID': Path('/etc/machine-id').read_text().strip(),
                   'ZLK_PUBLIC_BASE_URL': 'https://' + ip + ':8888/media',
                   'SEAL_ALLOWED_ORIGINS': 'https://' + ip + ':8888',
                   'PATH': str(root / 'runtime/bin') + ':/usr/local/bin:/usr/bin:/bin'}
    unit('ai-platform-backend', [python, '-m', 'gunicorn', '--workers', '1', '--threads', '4',
         '--bind', '127.0.0.1:5000', '--timeout', '180', 'main:app'], root / 'backend', backend_env,
         'network.target ai-platform-mysql.service ai-platform-redis.service')
    unit('ai-platform-media', [root / 'runtime/bin/MediaServer', '-c', root / 'Config_files/zlk/config.ini'], root / 'media/bin')
    token = root / 'config_dispatch/state/bootstrap.token'
    if not (root / 'config_dispatch/state/auth.sqlite3').exists() and not token.exists():
        write(token, secrets.token_hex(32), 0o600)
    unit('config-dispatch', ['/usr/bin/python3', root / 'config_dispatch/secure_server.py',
         '--settings', root / 'config_dispatch/security-settings.json'], root / 'config_dispatch',
         {'CFGP_ROOTS': ' '.join(str(root / p) for p in ('Config_files', 'model_algorithm_package', 'platform_algorithm_start'))})
    algorithms = algorithm_runtime(root, packages, arch, env) if mode != 'platform' else []
    features = []
    from native_host_features import install as install_features
    features = install_features(root, pay, env, python)
    from native_frontend_fixes import (patch_menu_loading, patch_camera_sync_label,
                                       patch_native_recorder_dialog,
                                       patch_native_model_upload_layout, patch_native_template_administrator,
                                       patch_native_storage_notice, patch_native_alarm_statistics,
                                       patch_native_alarm_details as patch_alarm_details_frontend,
                                       patch_native_diagnosis_configuration as patch_diagnosis_frontend,
                                       patch_native_diagnosis_rating as patch_diagnosis_rating_frontend,
                                       patch_native_diagnosis_auto_reference as patch_diagnosis_auto_frontend,
                                       refresh_asset_versions)
    patch_menu_loading(root)
    patch_camera_sync_label(root)
    patch_native_recorder_dialog(root)
    patch_native_model_upload_layout(root)
    patch_native_template_administrator(root)
    patch_native_storage_notice(root)
    patch_native_alarm_statistics(root)
    patch_alarm_details_frontend(root)
    patch_diagnosis_frontend(root)
    patch_diagnosis_rating_frontend(root)
    patch_diagnosis_auto_frontend(root)
    from native_account_frontend import install as install_account_frontend
    install_account_frontend(root)
    from native_role_frontend import patch_native_role_frontend
    patch_native_role_frontend(root)
    from native_playback_recovery import append_to_config as install_playback_recovery
    install_playback_recovery(root)
    refresh_asset_versions(root)
    services = list(SERVICES) + ['ai-platform-mysql', 'ai-platform-redis', 'ai-platform-kafka'] + algorithms + features
    if mode == 'platform':
        previous = json.loads((root / 'native-deployment.json').read_text())
        services = list(dict.fromkeys(services + previous['services']))
    initialize_site_content(root, pay, env, 'device')
    start(list(SERVICES) + algorithms + features)
    if mode == 'platform':
        initial = json.loads((root / 'platform_ops/state/initial-content.json').read_text(encoding='utf-8'))
        if initial.get('collector_updated'):
            run(['systemctl', 'try-restart', 'resource'])
    initialize_site_content(root, pay, env, 'model')
    state = {'runtime': 'native', 'root': str(root), 'shared_root': str(root.parent),
             'release': manifest.get('release', 'native'),
             'outputs': str(root.parent / 'outputs'), 'target_ip': ip,
             'arch': arch, 'services': list(dict.fromkeys(services)),
             'dependencies': deps,
             'installed_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    write(root / 'native-deployment.json', json.dumps(state, ensure_ascii=False, indent=2), 0o600)
    bootstrap_dispatch(ip, root, env)
    from native_host_features import complete_capabilities
    complete_capabilities(root, pay, python)
    if shutil.which('firewall-cmd') and subprocess.call(['firewall-cmd', '--state'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        for port in ('8888/tcp', '8899/tcp'):
            run(['firewall-cmd', '--permanent', '--add-port=' + port])
        run(['firewall-cmd', '--reload'])
    verify(root)
    # A full deploy establishes the baseline for later web code upgrades.
    run([python, '-B', root / 'platform_ops/upgrade_operations.py',
         'baseline', manifest.get('release', 'native')],
        env=dict(os.environ, PLATFORM_NATIVE_ROOT=str(root),
                 PLATFORM_OPS_STATE_DIR=str(root / 'platform_ops/state')))
    print('DEPLOY_RESULT=PASS', flush=True)


if __name__ == '__main__':
    try:
        deploy(dict(os.environ))
    except Exception as exc:
        print('[FAIL] ' + str(exc), flush=True)
        print('DEPLOY_RESULT=FAIL', flush=True)
        raise
