"""Install native maintenance, alarm-storage and push services."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

UNIT_DIR = Path('/etc/systemd/system')
SERVICES = ['platform-alarm-storage.service', 'platform-ops.service',
            'platform-push-worker.service', 'platform-host-disks.timer']

def write(path, value, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')
    path.chmod(mode)


def render(text, root, ip):
    root = Path(root)
    shared = root.parent
    shared_names = ('platform_alarm_media', 'platform_counts', 'platform_runtime_health', 'platform_storage')
    replacements = {
        '/data/sophon/ModelZoo/YOLO/python/bingxing_model': str(root / 'platform_algorithm_start'),
        '/data/AIGO/python/bingxing_model/results': str(shared / 'outputs'),
        '/home/AIGO/python/bingxing_model/results': str(shared / 'outputs'),
        '/data/AIGO/outputs': str(shared / 'outputs'),
        '/Seal_system': str(root / 'backend'),
        '/usr/share/nginx/html': str(root / 'frontend'),
        '/opt/nginx/conf/nginx.conf': str(root / 'platform_gateway/nginx.conf'),
        '/opt/Config_files/miniconda3': str(root / 'runtime/miniconda3'),
        '/data': str(root),
    }
    for name in shared_names:
        for old in ('/data/' + name, '/data/AIGO/' + name, str(root / name),
                    '/data/AIGO/ai_platform_start/' + name, '/data/AIGO/platform_start/' + name):
            replacements[old] = str(shared / name)
        replacements[str(shared / name)] = str(shared / name)
    for old in (str(root / 'results'), '/data/AIGO/ai_platform_start/results', '/data/AIGO/platform_start/results'):
        replacements[old] = str(shared / 'outputs')
    replacements[str(shared / 'outputs')] = str(shared / 'outputs')
    replacements[str(root)] = str(root)
    pattern = '|'.join(re.escape(value) + r'(?=/|[\s\x22\x27;,\)\]\}]|$)'
                       for value in sorted(replacements, key=len, reverse=True))
    return re.sub(pattern, lambda match: replacements[match.group()], text).replace('192.168.110.47', ip)


def native_storage(source):
    start = source.index('    def backend_probe(')
    end = source.index('    def media_probe(', start)
    replacement = '''    def backend_probe(self, slot, expected, config_path):
        self.run(['systemctl', 'is-active', '--quiet', 'ai-platform-backend'])
        info = os.stat(str(slot))
        if [info.st_dev, info.st_ino] != expected:
            raise StorageError(409, '目标目录发生变化，未切换写入目录')
        if not Path(config_path).parent.is_dir():
            raise StorageError(409, '报警存储配置目录不存在')

'''
    return source[:start] + replacement + source[end:]


def native_host_disks(source):
    start = source.index('def publish_to_container(')
    end = source.index("if __name__ == '__main__':", start)
    replacement = '''def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true')
    parser.parse_args()
    snapshot = build_snapshot()
    path = atomic_write_snapshot(snapshot)
    print(json.dumps({'ok': True, 'path': str(path),
                      'filesystem_count': snapshot['summary']['filesystem_count'],
                      'total_bytes': snapshot['summary']['total_bytes']}))


'''
    source = source[:start] + replacement + source[end:]
    source = source.replace("CONTAINER = 'seal_system'\n", '').replace("CONTAINER_TARGET = '/tmp/platform-host-disks.json'\n", '')
    return source


def unit_arg(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def adapt_frontend(root):
    from native_upgrade_frontend import install as install_upgrade_view
    return install_upgrade_view(root)


def native_dispatch(source):
    """Name the installed native services in configuration apply guidance."""
    for old, new in (
            ('重启平台服务（docker 容器 seal_system / seal_system_vue）',
             'systemctl restart ai-platform-backend'),
            ('docker restart zlk', 'systemctl restart ai-platform-media'),
            ('systemctl restart Huawei_resource（若独立运行）', 'systemctl restart resource')):
        source = source.replace(old, new)
    return source


def install(root, pay, env, python_launcher):
    root, pay = Path(root), Path(pay)
    shared = root.parent
    ip = env.get('TARGET_IP', '127.0.0.1')
    source = pay / 'reference-47'
    ops = root / 'platform_ops'
    ops.mkdir(parents=True, exist_ok=True)
    for path in sorted((source / 'data/platform_ops').glob('*.py')):
        if path.name.startswith('upgrade'):
            continue
        text = path.read_text(encoding='utf-8')
        if path.name == 'storage_operations.py':
            text = native_storage(text)
        write(ops / path.name, render(text, root, ip))
    write(ops / 'upgrade_operations.py', (pay / 'native_upgrade_operations.py').read_text(encoding='utf-8'))
    collector = source / 'usr/local/sbin/platform-host-disks.py'
    write(ops / 'platform-host-disks.py', render(native_host_disks(collector.read_text(encoding='utf-8')), root, ip))
    helper = source / 'data/platform_algorithm_start/templates/alarm_directory.py'
    if helper.is_file():
        write(root / 'platform_algorithm_start/templates/alarm_directory.py', render(helper.read_text(encoding='utf-8'), root, ip))
    for relative in ('platform_ops/state', 'platform_ops/backups'):
        (root / relative).mkdir(parents=True, exist_ok=True)
    for relative in ('platform_storage/config', 'platform_storage/alarm-volumes',
                     'platform_alarm_media', 'platform_counts', 'platform_runtime_health', 'outputs'):
        (shared / relative).mkdir(parents=True, exist_ok=True)
    server = ops / 'server.json'
    client = ops / 'backend-client.json'
    backend_client = root / 'backend/config/platform-ops-client.json'
    existing = next((path for path in (server, client, backend_client) if path.is_file()), None)
    key = json.loads(existing.read_text(encoding='utf-8'))['key'] if existing else secrets.token_urlsafe(48)
    for path in (server, client):
        write(path, json.dumps({'key': key}) + '\n', 0o600)
    backend_client.parent.mkdir(parents=True, exist_ok=True)
    if backend_client.is_symlink() or backend_client.exists():
        backend_client.unlink()
    backend_client.symlink_to(client)

    python = unit_arg(python_launcher)
    common = ('WorkingDirectory=' + str(ops).replace('%', '%%') + '\n'
              'Environment=' + unit_arg('PLATFORM_OPS_STATE_DIR=' + str(ops / 'state')) + '\n'
              'Environment=' + unit_arg('PLATFORM_NATIVE_ROOT=' + str(root)) + '\n' +
              'Environment=PYTHONDONTWRITEBYTECODE=1\nUser=root\n')
    write(UNIT_DIR / 'platform-ops.service',
          '[Unit]\nDescription=Native platform maintenance operations\nAfter=network.target platform-alarm-storage.service\n'
          '[Service]\nType=simple\n' + common +
          'ExecStart=' + python + ' ' + unit_arg(ops / 'platform_ops_server.py') + '\n'
          'Restart=on-failure\nRestartSec=3\nUMask=0077\n[Install]\nWantedBy=multi-user.target\n')
    write(UNIT_DIR / 'platform-push-worker.service',
          '[Unit]\nDescription=Native platform durable alarm push sender\nAfter=network-online.target\n'
          '[Service]\nType=simple\n' + common +
          'ExecStart=' + python + ' ' + unit_arg(ops / 'push_worker.py') + '\n'
          'Restart=on-failure\nRestartSec=5\nTimeoutStopSec=40\nUMask=0077\n'
          '[Install]\nWantedBy=multi-user.target\n')
    write(UNIT_DIR / 'platform-alarm-storage.service',
          '[Unit]\nDescription=Restore native platform alarm storage\nAfter=local-fs.target\nBefore=ai-platform-backend.service\n'
          '[Service]\nType=oneshot\nUser=root\nExecStart=' + python + ' ' +
          unit_arg(ops / 'storage_operations.py') + ' restore\nRemainAfterExit=yes\nTimeoutStartSec=120\n'
          '[Install]\nWantedBy=multi-user.target\n')
    write(UNIT_DIR / 'platform-host-disks.service',
          '[Unit]\nDescription=Publish native platform filesystem capacities\nAfter=local-fs.target\n'
          '[Service]\nType=oneshot\nUser=root\nExecStart=' + python + ' ' +
          unit_arg(ops / 'platform-host-disks.py') + '\nTimeoutStartSec=50\n')
    write(UNIT_DIR / 'platform-host-disks.timer',
          '[Unit]\nDescription=Refresh native platform filesystem capacities\n'
          '[Timer]\nOnBootSec=10s\nOnUnitActiveSec=60s\nUnit=platform-host-disks.service\n'
          '[Install]\nWantedBy=timers.target\n')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable'] + SERVICES, check=True, stdout=subprocess.DEVNULL)
    adapt_frontend(root)
    dispatch = root / 'config_dispatch/config_dispatch.py'
    write(dispatch, native_dispatch(dispatch.read_text(encoding='utf-8')))
    return list(SERVICES)


def complete_capabilities(root, pay, python_launcher):
    """Verify real native backend/media access before enabling directory changes."""
    root, pay = Path(root), Path(pay)
    helper = root / 'runtime/tools/complete_alarm_storage.py'
    source = (pay / 'complete_alarm_storage.py').read_text(encoding='utf-8')
    write(helper, render(source, root, '127.0.0.1'), 0o700)
    command = [str(python_launcher), str(helper), '--install', '--wait-seconds', '60']
    if not (root / 'platform_algorithm_start/model_start.py').is_file():
        command.append('--runtime-unavailable')
    subprocess.run(command, check=True, cwd=str(root))
