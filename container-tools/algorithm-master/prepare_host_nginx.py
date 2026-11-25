"""Prepare nginx runtime directories without rewriting existing site configuration.

The Ubuntu binary keeps absolute compiled defaults under /var even with -p.
Fresh releases explicitly use /opt/nginx, whose output paths support bulk storage.
Older/manual configs may still use compiled defaults, so create those empty
directories too. Existing directory ownership, mode and contents are retained.
"""
from pathlib import Path
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import time

PREFIX = Path('/opt/nginx')
NGINX = str(PREFIX / 'sbin/nginx')
LEGACY_TEMPLATE_SHA256 = '99d2a7e9a33c24c64f4c5c21ac9e163c2511f4eca8f7ce6856f74a5d662b5b5a'
DEFAULTS = {
    '--error-log-path': ('logs/error.log', False),
    '--http-log-path': ('logs/access.log', False),
    '--pid-path': ('logs/nginx.pid', False),
    '--lock-path': ('logs/nginx.lock', False),
    '--http-client-body-temp-path': ('client_body_temp', True),
    '--http-proxy-temp-path': ('proxy_temp', True),
    '--http-fastcgi-temp-path': ('fastcgi_temp', True),
    '--http-uwsgi-temp-path': ('uwsgi_temp', True),
    '--http-scgi-temp-path': ('scgi_temp', True),
}


def runtime_directories(output, prefix=PREFIX):
    settings = {}
    for line in output.splitlines():
        if line.startswith('configure arguments:'):
            for value in shlex.split(line.partition(':')[2]):
                key, _, setting = value.partition('=')
                settings[key] = setting
    directories = {prefix / 'logs'}
    directories.update(prefix / name for name in
                       ('client_body_temp', 'proxy_temp', 'fastcgi_temp', 'uwsgi_temp', 'scgi_temp'))
    for flag, (fallback, directory) in DEFAULTS.items():
        value = settings.get(flag, fallback)
        if value in ('stderr', '/dev/stderr', '/dev/stdout'):
            continue
        path = Path(value)
        if not path.is_absolute():
            path = prefix / path
        directories.add(path if directory else path.parent)
    return sorted(directories)


def config_structure(text):
    # Preserve character offsets while ignoring comments, including ones that
    # mention an example location. Quoted # and braces are configuration data.
    uncommented = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|#[^\n]*',
                         lambda match: ' ' * len(match.group()) if match.group().startswith('#') else match.group(), text)
    token_pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};]|(?:\$\{[^}]*\}|[^\s{};])+'
    root = {'children': [], 'directives': []}
    stack, header = [root], []
    for match in re.finditer(token_pattern, uncommented):
        token = match.group()
        if token == '{':
            if not header:
                raise ValueError('无法解析已有 nginx 配置块；原配置保持不变')
            block = {'name': header[0][0], 'args': [item[0] for item in header[1:]],
                     'start': header[0][1], 'children': [], 'directives': []}
            stack[-1]['children'].append(block)
            stack.append(block)
            header = []
        elif token == ';':
            stack[-1]['directives'].append([item[0] for item in header])
            header = []
        elif token == '}':
            if len(stack) == 1 or header:
                raise ValueError('无法解析已有 nginx 配置；原配置保持不变')
            stack.pop()
        else:
            header.append((token.strip('\"\''), match.start()))
    if len(stack) != 1 or header:
        raise ValueError('nginx 配置块不完整；原配置保持不变')
    return root, uncommented


def ensure_media_route(config, backup_root):
    text = config.read_text(encoding='utf-8')
    structure, uncommented = config_structure(text)
    def blocks(node):
        for child in node['children']:
            yield child
            yield from blocks(child)
    servers = [node for node in blocks(structure) if node['name'] == 'server' and any(
        len(item) >= 2 and item[0] == 'listen' and re.search(r'(?:^|:)9002$', item[1])
        for item in node['directives'])]
    if servers and all(any(child['name'] == 'location' and child['args'] in
                           (['/alarm-storage/'], ['^~', '/alarm-storage/'])
                           for child in server['children']) for server in servers):
        return False
    normalized = re.sub(r'(server_name\s+)\d+(?:\.\d+){3}', r'\1__TARGET_IP__', uncommented)
    normalized = re.sub(r'\s+', '', normalized)
    if hashlib.sha256(normalized.encode()).hexdigest() != LEGACY_TEMPLATE_SHA256:
        raise ValueError('现有手工 nginx 配置缺少 /alarm-storage/ 必需媒体路由；配置保持原样，请在 9002 server 中配置指向 /data/platform_alarm_media/ 的路由后重试')
    insertion = [child['start'] for server in servers for child in server['children']
                 if child['name'] == 'location' and child['args'] == ['/data/']]
    if len(servers) != 1 or len(insertion) != 1:
        raise ValueError('已知 nginx 模板中的媒体 server 无法定位，原配置保持不变')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = backup_root / ('nginx.conf.before-alarm-route-' + str(time.time_ns()))
    shutil.copy2(str(config), str(backup))
    os.chmod(str(backup), 0o600)
    addition = 'location /alarm-storage/ { alias /data/platform_alarm_media/; autoindex off; }\n        '
    updated = text[:insertion[0]] + addition + text[insertion[0]:]
    temporary = config.with_name(config.name + '.media-route-new')
    temporary.write_text(updated, encoding='utf-8')
    shutil.copymode(str(config), str(temporary))
    os.replace(str(temporary), str(config))
    print('HOST_NGINX_LEGACY_MEDIA_ROUTE=ADDED; backup=' + str(backup))
    return True


def main():
    result = subprocess.run([NGINX, '-V'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, check=True)
    for path in runtime_directories(result.stdout):
        path.mkdir(parents=True, exist_ok=True, mode=0o755)
    backup = Path(os.environ.get('ONECLICK_BACKUP_ROOT',
                                os.environ.get('ONECLICK_ROOT', '/root/oneclick') + '/backups')) / 'nginx-host'
    ensure_media_route(PREFIX / 'conf/nginx.conf', backup)
    print('HOST_NGINX_RUNTIME_DIRECTORIES=READY; existing configuration preserved')


if __name__ == '__main__':
    main()
