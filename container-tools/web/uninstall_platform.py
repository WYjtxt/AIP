"""Uninstall this platform's software; retain drivers, media and site backups."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

UNITS = ('ai-platform-backend', 'ai-platform-web', 'ai-platform-media',
         'ai-platform-mysql', 'ai-platform-redis', 'ai-platform-kafka',
         'config-dispatch', 'config-dispatch-gateway', 'model_start', 'resource',
         'kafka_consumer', 'platform-ops', 'platform-push-worker',
         'platform-alarm-storage', 'platform-host-disks', 'platform-host-disks.timer')
DOCKER_BINARIES = ('docker', 'dockerd', 'containerd', 'containerd-shim',
                   'containerd-shim-runc-v2', 'ctr', 'runc', 'docker-proxy', 'docker-init')
BACKUP_PATHS = ('Config_files', 'mysql', 'redis', 'kafka', 'config_dispatch/state',
                'config_dispatch/tls', 'config_dispatch/security-settings.json',
                'platform_gateway/tls', 'platform_algorithm_start/config',
                'model_algorithm_package/Conf_files.py', 'model_algorithm_package/Conf_file.ini',
                'backend/config', 'backend/config.ini', 'backend/platform-security.json',
                'native-deployment.json', 'container-deployment.json', 'initial-access.json')
SHARED = ('platform_counts', 'platform_runtime_health', 'platform_storage', 'platform_alarm_media')


def run(args, check=True):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True)
    if check and result.returncode:
        raise RuntimeError('%s failed: %s' % (args[0], result.stderr[-1000:]))
    return result


def exists(path):
    return path.exists() or path.is_symlink()


def read_json(path):
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def driver_fingerprints(system):
    result = {}
    for folder in ('usr/local/Ascend/driver', 'usr/local/Ascend/firmware', 'usr/local/Ascend/develop',
                   'opt/sophon/driver-0.5.1'):
        root = system / folder
        if root.is_dir():
            tree = hashlib.sha256();files = 0
            for path in sorted(root.rglob('*')):
                relative = str(path.relative_to(root))
                if path.is_symlink():entry = 'L:'+relative+':'+os.readlink(str(path))
                elif path.is_file():entry = 'F:'+relative+':'+digest(path);files += 1
                else:continue
                tree.update(entry.encode('utf-8'));tree.update(b'\n')
            result[str(root)] = {'present': True, 'files': files, 'tree_sha256': tree.hexdigest()}
            for path in sorted(root.glob('*version*')):
                if path.is_file() and path.stat().st_size < 1024 * 1024:
                    result[str(path)] = {'sha256': digest(path)}
    return result


def compact_paths(paths):
    selected = sorted(set(Path(path) for path in paths), key=lambda path: len(path.parts))
    result = []
    for path in selected:
        if not any(parent == path or parent in path.parents for parent in result):
            result.append(path)
    return result


def plan_uninstall(root, stage=None, system_root=Path('/')):
    root, system = Path(root).absolute(), Path(system_root).absolute()
    if root.is_symlink() or root.resolve() != root or len(root.parts) < 3:
        raise ValueError('请选择实际的平台专用目录，不能使用目录链接或系统根目录')
    if root in (system, system/'data', system/'data/AIGO', system/'home', system/'root', system/'opt'):
        raise ValueError('不能卸载系统或共享父目录')
    stage = Path(stage or os.environ.get('ONECLICK_ROOT', str(system/'root/oneclick'))).absolute()
    base = root.parent
    backup_parent = base/'platform-backups'
    previous_plans = []
    for path in backup_parent.glob('uninstall-*/uninstall-plan.json'):
        previous = read_json(path)
        if previous.get('root') == str(root):previous_plans.append((path, previous))
    roots = [root]
    for name in (root.name, 'platform_start', 'ai_platform_start'):
        for candidate in [base/name] + sorted(base.glob(name+'.native-before-container-*')):
            if candidate == root or candidate.is_symlink():
                continue
            if (candidate/'native-deployment.json').is_file() or (candidate/'container-deployment.json').is_file():
                roots.append(candidate)
    roots = compact_paths(roots)
    known = any((root/name).is_file() for name in ('native-deployment.json', 'container-deployment.json', 'container/images.json'))
    known = known or bool(previous_plans)
    if not known:
        for path in backup_parent.glob('*/cleanup.json'):
            record = read_json(path)
            if record.get('root', record.get('program_root')) == str(root):
                known = True
                break
    if not known and exists(root) and any(root.iterdir()):
        raise ValueError('未找到该目录的平台部署或清洗记录，未卸载任何软件')

    units, unit_files = [], []
    unit_dir = system/'etc/systemd/system'
    roots_text = [str(path)+'/' for path in roots]
    for name in UNITS:
        name = name if name.endswith(('.service', '.timer')) else name+'.service'
        path = unit_dir/name
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        if any(value in text for value in roots_text) or name == 'platform-host-disks.timer' and 'platform-host-disks.service' in text:
            units.append(name);unit_files.append(path)

    software = list(roots)
    for prefix in ('usr/lib/jvm', 'usr/local', 'usr/java', 'opt'):
        folder = system/prefix
        for pattern in ('jdk*', 'jre*', 'java-*'):
            for path in folder.glob(pattern):
                if (path/'bin/java').is_file():software.append(path)
    for previous in backup_parent.glob('*'):
        if not previous.is_dir() or previous.is_symlink():continue
        old = read_json(previous/'cleanup.json')
        if old.get('root', old.get('program_root')) in (str(root), str(base/'ai_platform_start')):
            for relative in ('old-program-runtime/runtime', 'program/runtime', 'program/Config_files/miniconda3'):
                if exists(previous/relative):software.append(previous/relative)
    ascend = system/'usr/local/Ascend'
    for pattern in ('ascend-toolkit', 'cann', 'cann-*', 'mxVision', 'mxVision-*', 'nnal', 'atc', 'opp',
                    'add-ons', 'vendors', 'Ascend-cann-toolkit*.run'):
        software.extend(ascend.glob(pattern))
    # These are application SDKs. libsophon and driver packages also contain the
    # device libraries, bm-smi and firmware, and are deliberately retained.
    for pattern in ('sophon-ffmpeg_*', 'sophon-opencv_*'):
        software.extend((system/'opt/sophon').glob(pattern))
    for prefix in ('opt/nginx', 'opt/media', 'opt/mysql', 'usr/local/mysql',
                   'usr/local/redis', 'opt/kafka', 'usr/local/kafka', 'root/miniconda3'):
        candidate = system/prefix
        if any(str(candidate)+'/' in path.read_text(encoding='utf-8') for path in unit_files):
            software.append(candidate)

    docker = None
    for prefix in ('usr/local/bin', 'usr/bin', 'bin'):
        if (system/prefix/'docker').is_file():
            docker = system/prefix/'docker';break
    engine_files, engine_data, docker_units, packages = [], [], [], []
    containers = []
    if docker:
        listed = run([docker, 'ps', '-aq'])
        ids = listed.stdout.split()
        if ids:
            containers = json.loads(run([docker, 'inspect']+ids).stdout)
        foreign = [item['Name'] for item in containers if not
                   item.get('Config', {}).get('Labels', {}).get('com.docker.compose.project') == 'aiplatform']
        if foreign:
            raise ValueError('Docker中有其它项目容器，未停止或卸载任何软件：'+', '.join(foreign))
        info = json.loads(run([docker, 'info', '--format', '{{json .DockerRootDir}}']).stdout)
        data = Path(info)
        allowed_data = (system/'home/AIGO/container-runtime/docker', system/'var/lib/docker')
        if data not in allowed_data or data.is_symlink():
            raise ValueError('Docker数据目录不属于本项目的已知安装位置：'+str(data))
        engine_data.append(data.parent if data == system/'home/AIGO/container-runtime/docker' else data)
        engine_data += [path for path in (system/'run/docker', system/'run/containerd') if exists(path)]
        for name in DOCKER_BINARIES:
            for prefix in ('usr/local/bin', 'usr/bin'):
                candidate = system/prefix/name
                if exists(candidate):engine_files.append(candidate)
        for relative in ('usr/local/lib/docker/cli-plugins/docker-compose',
                         'usr/libexec/docker/cli-plugins/docker-compose', 'etc/docker',
                         'etc/containerd', 'run/docker.sock', 'run/docker.pid'):
            if exists(system/relative):engine_files.append(system/relative)
        for name in ('docker.service', 'docker.socket', 'containerd.service'):
            for prefix in ('etc/systemd/system', 'usr/lib/systemd/system', 'lib/systemd/system'):
                path = system/prefix/name
                if path.is_file():docker_units.append(name);engine_files.append(path)
    # Resume after the engine binaries or units were already removed, but its
    # network namespace mounts/data have not yet been cleared.
    if not docker:
        for _, previous in previous_plans:
            engine_data += [Path(value) for value in previous.get('engine_data', []) if exists(Path(value))]
            engine_files += [Path(value) for value in previous.get('engine_files', []) if exists(Path(value))]
            for name in previous.get('docker_units', []):
                if any((system/prefix/name).is_file() for prefix in ('etc/systemd/system','usr/lib/systemd/system','lib/systemd/system')):
                    docker_units.append(name)
    package_manager = None
    if (system/'usr/bin/rpm').is_file():
        package_manager = 'rpm'
        installed = run(['rpm', '-qa', '--qf', '%{NAME}\n']).stdout.splitlines()
        software_package = re.compile(r'^(?:docker(?:-ce|-ce-cli|-compose-plugin|-buildx-plugin)?|containerd(?:\.io)?|runc|'
                                      r'ffmpeg(?:-libs)?|libavdevice|java-\d+-openjdk(?:-headless|-devel)?|'
                                      r'tzdata-java|javapackages-filesystem|Ascend-cann-(?!driver|firmware)[A-Za-z0-9_.-]+)$')
        packages = sorted(set(name for name in installed if software_package.fullmatch(name)))
        if packages:run(['rpm', '-e', '--test']+packages)
    elif (system/'usr/bin/dpkg-query').is_file():
        package_manager = 'dpkg'
        installed = run(['dpkg-query', '-W', '-f=${Package} ${db:Status-Status}\n']).stdout.splitlines()
        software_package = re.compile(r'^(?:docker-ce|docker-ce-cli|docker.io|docker-compose-plugin|docker-buildx-plugin|'
                                      r'containerd(?:.io)?|runc|ffmpeg|openjdk-\d+-(?:jdk|jre)(?:-headless)?|'
                                      r'sophon-mw-sophon-(?:ffmpeg|opencv))$')
        packages = sorted({row.split()[0] for row in installed if row.endswith(' installed')
                           and software_package.fullmatch(row.split()[0])})
        if packages:run(['dpkg', '--dry-run', '--remove']+packages)
    software.extend(path for path in (system/'home/AIGO/container-build', system/'home/AIGO/container-upgrades') if exists(path))
    # Driver/firmware trees must never be included, including by an ancestor.
    protected = [system/'usr/local/Ascend/driver', system/'usr/local/Ascend/firmware', system/'usr/local/Ascend/develop']
    protected += list((system/'opt/sophon').glob('driver*'))
    protected += list((system/'opt/sophon').glob('libsophon*'))
    software = compact_paths([path for path in software if exists(path)])
    for path in software+engine_data:
        if path.is_symlink():continue
        if any(path == keep or path in keep.parents or keep in path.parents for keep in protected):
            raise ValueError('卸载目标包含硬件驱动或固件：'+str(path))
    return {'schema': 1, 'root': str(root), 'stage': str(stage), 'system_root': str(system),
            'software_roots': [str(path) for path in software], 'units': sorted(set(units)),
            'unit_files': [str(path) for path in unit_files], 'docker': str(docker) if docker else None,
            'docker_containers': [item['Id'] for item in containers],
            'docker_units': sorted(set(docker_units)), 'engine_files': [str(path) for path in engine_files],
            'engine_data': [str(path) for path in engine_data], 'software_packages': packages,
            'package_manager': package_manager,
            'preserved_drivers': driver_fingerprints(system),
            'previous_attempts': [str(path.parent) for path, _ in previous_plans],
            'retained_installation_media': str(stage/'packages'),
            'backup': str(backup_parent/('uninstall-'+time.strftime('%Y%m%d_%H%M%S')))}


def remove_path(path):
    if path.is_symlink() or path.is_file():path.unlink()
    elif path.is_dir():shutil.rmtree(str(path))


def move_backup(source, destination):
    if not exists(source):return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def clean_environment_files(plan, backup):
    system = Path(plan['system_root'])
    candidates = [system/'root/.bashrc', system/'root/.bash_profile', system/'etc/profile']
    candidates += list((system/'etc/profile.d').glob('*.sh'))
    sdk_variables = ('ASCEND_TOOLKIT_PATH', 'ASCEND_TOOLKIT_HOME', 'ASCEND_HOME_PATH',
                     'ASCEND_OPP_PATH', 'MX_SDK_HOME', 'JAVA_HOME', 'JRE_HOME')
    for path in candidates:
        if not path.is_file() or path.is_symlink():continue
        source = path.read_text(encoding='utf-8');lines = []
        for line in source.splitlines(True):
            references = any(value in line for value in plan['software_roots'])
            if 'set_env.sh' in line and re.match(r'\s*(?:source|\.)\s+', line) and (
                    references or any('$'+value in line or '${'+value+'}' in line for value in sdk_variables)):
                continue
            if references and re.match(r'\s*export\s+(?:'+ '|'.join(sdk_variables) +r')=', line):continue
            if references and re.match(r'\s*export\s+(?:PATH|LD_LIBRARY_PATH|PYTHONPATH|PKG_CONFIG_PATH)=', line):
                for value in plan['software_roots']:
                    line = re.sub(re.escape(value)+r'''[^:\s'";]*''', '', line)
                while '::' in line:line = line.replace('::', ':')
                line = line.replace('=:', '=').replace('":', '"').replace(':"', '"')
                if re.fullmatch(r'\s*export\s+\w+=[\'\"]?\s*[\'\"]?\s*', line):continue
            lines.append(line)
        updated = ''.join(lines)
        if updated != source:
            destination = backup/'system'/path.relative_to(system)
            destination.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(str(path), str(destination))
            path.write_text(updated, encoding='utf-8')


def execute_uninstall(plan):
    root, system, backup = Path(plan['root']), Path(plan['system_root']), Path(plan['backup'])
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    (backup/'uninstall-plan.json').write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
    if plan['units']:run(['systemctl', 'disable', '--now']+plan['units'])
    if plan['docker_containers']:
        run([plan['docker'], 'stop']+plan['docker_containers'])
        run([plan['docker'], 'rm']+plan['docker_containers'])
    from deploy_native import unmount_platform_storage
    unmount_platform_storage(root.parent)
    saved = []
    for index, program in enumerate(Path(value) for value in plan['software_roots'] if Path(value).parent == root.parent):
        prefix = 'program' if program == root else 'previous/'+program.name
        for relative in BACKUP_PATHS:
            if move_backup(program/relative, backup/prefix/relative):saved.append(prefix+'/'+relative)
    storage = root.parent/'platform_storage/config'
    if move_backup(storage, backup/'shared/platform_storage/config'):saved.append('shared/platform_storage/config')
    # Keep old migration credentials, issued licenses and database dumps before
    # discarding the software build workspace.
    build = system/'home/AIGO/container-build'
    if move_backup(build/'site-backups', backup/'previous-site-backups'):saved.append('previous-site-backups')
    media_preserved = [str(root.parent/'outputs')]
    if (backup/'shared/platform_storage/config/alarm-directory.json').is_file():
        registry = read_json(backup/'shared/platform_storage/config/alarm-directory.json')
        volumes = [registry.get('active', {})]+registry.get('volumes', [])
        for volume in volumes:
            value = volume.get('target')
            if not value:continue
            path = Path(value)
            if root in path.absolute().parents and exists(path):
                destination = root.parent/('outputs-before-uninstall-'+backup.name)/path.relative_to(root)
                move_backup(path, destination);media_preserved.append(str(destination))
            else:media_preserved.append(str(path))
    for name in ('outputs', 'results'):
        path = root/name
        if exists(path) and not path.is_symlink():
            destination = root.parent/('outputs-before-uninstall-'+backup.name)/name
            move_backup(path, destination);media_preserved.append(str(destination))
    if plan['docker_units']:run(['systemctl', 'disable', '--now']+plan['docker_units'])
    if plan['engine_data']:
        roots = [Path(value) for value in plan['engine_data']]
        mounts = [Path(value) for value in run(['findmnt','-rn','-o','TARGET']).stdout.splitlines()
                  if any(Path(value)==path or path in Path(value).parents for path in roots)]
        for mount in sorted(mounts,key=lambda path:len(path.parts),reverse=True):run(['umount',mount])
    if plan['software_packages']:
        if plan['package_manager'] == 'rpm':run(['rpm', '-e']+plan['software_packages'])
        else:run(['dpkg', '--purge']+plan['software_packages'])
    clean_environment_files(plan, backup)
    for value in plan['unit_files']+plan['engine_files']:
        remove_path(Path(value))
    for value in plan['software_roots']+plan['engine_data']:
        remove_path(Path(value))
        if Path(value)==root:root.mkdir(parents=True,exist_ok=True)
    for name in SHARED:
        path = root.parent/name
        if name == 'platform_alarm_media' and path.is_dir() and not path.is_symlink() and any(path.iterdir()):
            # Real files can exist here on old installs; retain them as media.
            destination = root.parent/('alarm-media-before-uninstall-'+backup.name)
            move_backup(path, destination);media_preserved.append(str(destination))
        else:remove_path(path)
    # Remove archive links into the discarded build tree; a subsequent one-click
    # upload must create a regular file rather than follow a broken cache link.
    for path in (Path(plan['stage'])/'packages').rglob('*'):
        if path.is_symlink() and build in path.resolve().parents:path.unlink()
    for folder in ('usr/local/bin', 'usr/local/sbin', 'usr/bin'):
        for path in (system/folder).glob('*'):
            if path.is_symlink() and any(str(path.resolve()).startswith(value+'/') for value in plan['software_roots']):
                path.unlink()
            elif path.is_file() and path.stat().st_size < 8192:
                text = path.read_bytes()
                if any(marker in text for marker in (b'AI_PLATFORM_CONTAINER_FORWARDER_V1', b'AI_PLATFORM_NATIVE_MEDIA_WRAPPER_V1')):remove_path(path)
    run(['systemctl', 'daemon-reload'])
    if plan['units']+plan['docker_units']:
        run(['systemctl', 'reset-failed']+plan['units']+plan['docker_units'], check=False)
    if shutil.which('ldconfig'):run(['ldconfig'], check=False)
    root.mkdir(parents=True, exist_ok=True)
    drivers_after = driver_fingerprints(system)
    remaining = [value for value in plan['software_roots'] if Path(value) != root and exists(Path(value))]
    remaining += [value for value in plan['engine_files']+plan['engine_data']+plan['unit_files'] if exists(Path(value))]
    report = {'root': str(root), 'result': 'PASS' if not remaining and drivers_after == plan['preserved_drivers'] else 'FAIL',
              'configuration_and_database_backed_up': True, 'saved': saved,
              'outputs_preserved': True, 'media_paths': sorted(set(media_preserved)),
              'software_removed': plan['software_roots'], 'driver_fingerprints_before': plan['preserved_drivers'],
              'previous_attempts': plan['previous_attempts'],
              'driver_fingerprints_after': drivers_after, 'remaining': remaining,
              'installation_media_retained': plan['retained_installation_media']}
    (backup/'cleanup.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if report['result'] != 'PASS':raise RuntimeError('软件卸载验收失败：'+', '.join(remaining))
    print('软件已卸载；驱动、固件、历史媒体及配置备份保留：'+str(backup), flush=True)
    print('CLEAN_RESULT=PASS', flush=True)
    return backup


def uninstall(root, runtime='native', stage=None, system_root=Path('/')):
    plan = plan_uninstall(root, stage, system_root)
    plan['runtime'] = runtime
    return execute_uninstall(plan)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data/AIGO/platform_start')
    parser.add_argument('--plan', action='store_true')
    args = parser.parse_args()
    if args.plan:print(json.dumps(plan_uninstall(args.root), indent=2))
    else:uninstall(args.root)
