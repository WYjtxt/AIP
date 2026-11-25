"""Install host services required by current 47 platform images; keep per-site secrets."""
import configparser
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from data_root import adapt_service_unit

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'reference-47'
UNITS = ('platform-ops.service', 'platform-push-worker.service', 'platform-alarm-storage.service',
         'platform-host-disks.service', 'platform-host-disks.timer')


def render_host_paths(data, name, selected):
    # selected is the validated, resolved root; child paths remain unresolved
    # so the service's own symlink protections still apply.
    if name == 'storage_operations.py':
        marker = b"PUBLIC_MEDIA = '/data/platform_alarm_media'"
        value = 'PUBLIC_MEDIA = ' + repr(str(selected / 'platform_alarm_media'))
    elif name == 'platform-host-disks.py':
        marker = b"OUTPUT_DIRECTORY = Path('/data/platform_storage')"
        value = 'OUTPUT_DIRECTORY = Path(' + repr(str(selected / 'platform_storage')) + ')'
    elif name == 'alarm_directory.py':
        marker = b"HOST_VOLUMES = Path('/data/platform_storage/alarm-volumes')"
        value = 'HOST_VOLUMES = Path(' + repr(str(selected / 'platform_storage/alarm-volumes')) + ')'
    else:
        return data
    if data.count(marker) != 1:
        raise ValueError('Unexpected host directory source template: ' + name)
    return data.replace(marker, value.encode('utf-8'))


def render_site_origin(data, name, target_ip):
    if name != 'storage_operations.py': return data
    address = ipaddress.ip_address(target_ip)
    authority = '[' + str(address) + ']' if address.version == 6 else str(address)
    marker = b"PUBLIC_ORIGIN = 'https://192.168.110.47:8888'"
    if data.count(marker) != 1: raise ValueError('Unexpected storage origin template')
    return data.replace(marker, ('PUBLIC_ORIGIN = ' + repr('https://' + authority + ':8888')).encode())


def write(path, data, mode=0o600):
    path=Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.oneclick-new')
    fd=os.open(str(temp), os.O_CREAT|os.O_TRUNC|os.O_WRONLY, mode)
    with os.fdopen(fd,'wb') as stream: stream.write(data)
    os.chmod(str(temp),mode)
    os.replace(str(temp),str(path))


def main():
    ip=os.environ['TARGET_IP']
    backup=Path(os.environ.get('ONECLICK_ROOT','/root/oneclick'))/'backups'/('host-features-'+time.strftime('%Y%m%d_%H%M%S'))
    files=list((SOURCE/'data/platform_ops').glob('*.py'))
    if not files: raise ValueError('Missing verified current platform host service source')
    files += [SOURCE/'etc/systemd/system'/name for name in UNITS]
    files += [SOURCE/'usr/local/sbin/platform-host-disks.py', SOURCE/'data/platform_gateway/default.conf', SOURCE/'data/Config_files/nginx.conf']
    # Both runtime bundles carry this shared directory helper; installing it
    # does not install or start an accelerator-specific algorithm program.
    files.append(SOURCE/'data/platform_algorithm_start/templates/alarm_directory.py')
    for source in files:
        relative=source.relative_to(SOURCE)
        target=Path('/')/relative
        if target.exists():
            destination=backup/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(target),str(destination))
        data=source.read_bytes()
        data = render_site_origin(data, source.name, ip)
        if source.name in ('storage_operations.py', 'platform-host-disks.py', 'alarm_directory.py'):
            # /data may be the validated compatibility alias for /home/AIGO.
            # Resolve only the selected root; restore must still reject an
            # unexpected symlink at the public-media child or its parents.
            selected = Path(os.environ.get('PLATFORM_DATA_ROOT', '/data')).resolve()
            child = 'platform_alarm_media' if source.name == 'storage_operations.py' else 'platform_storage'
            if (Path('/data') / child).resolve() != selected / child:
                raise ValueError('Host directory does not match the validated platform root: ' + child)
            data = render_host_paths(data, source.name, selected)
        if source.suffix == '.service' and source.name == 'platform-push-worker.service':
            data = adapt_service_unit(data.decode('utf-8'), os.environ.get('PLATFORM_DATA_ROOT', '/data')).encode('utf-8')
        data=data.replace(b'/data/sophon/ModelZoo/YOLO/python/bingxing_model', b'/data/platform_algorithm_start')
        if os.environ.get('HAS_SOPHGO')=='1' and source.suffix=='.service':
            data=data.replace(b'/usr/bin/python3', b'/opt/Config_files/platform-python/bin/python3')
        if source.suffix=='.conf': data=data.replace(b'192.168.110.47',ip.encode())
        write(target,data,0o644 if source.suffix in ('.service','.timer','.conf') else 0o700)
    ops=Path('/data/platform_ops')
    server=ops/'server.json'; client=ops/'backend-client.json'
    if server.exists():
        key=json.loads(server.read_text())['key']
        if len(key)<48: raise ValueError('Existing operations key is invalid')
    elif client.exists():
        key=json.loads(client.read_text())['key']
        if len(key)<48: raise ValueError('Existing operations client key is invalid')
    else:
        key=secrets.token_urlsafe(48)
    for path in (server,client):
        if path.exists():
            if json.loads(path.read_text())['key']!=key: raise ValueError('Existing operations keys disagree; no rotation performed')
        else: write(path,(json.dumps({'key':key})+'\n').encode())
    for folder in ('state','backups'):
        (ops/folder).mkdir(mode=0o700,exist_ok=True)
    for folder in ('/data/platform_storage/config','/data/platform_storage/alarm-volumes','/data/platform_alarm_media'):
        Path(folder).mkdir(parents=True,exist_ok=True)
    write('/etc/systemd/system/platform-ops.service.d/oneclick.conf',
          b'[Service]\nEnvironment=PLATFORM_OPS_HOST_MOUNT_NAMESPACE=/proc/1/ns/mnt\nEnvironment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n',0o644)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','platform-alarm-storage.service','platform-ops.service','platform-push-worker.service','platform-host-disks.timer'],check=True)
    # enable --now does not reload code/configuration of an already active service.
    subprocess.run(['systemctl','restart','platform-ops.service'],check=True)
    print('REFERENCE_HOST_FEATURES=PASS')


if __name__=='__main__': main()
