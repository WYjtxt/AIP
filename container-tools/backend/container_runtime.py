"""Small process entrypoint and Compose document for the offline platform images."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import time

ROOT = Path('/data/AIGO/platform_start')
SHARED = ('outputs', 'platform_alarm_media', 'platform_counts',
          'platform_runtime_health', 'platform_storage')
DIRECTORIES = (
    'Config_files', 'mysql', 'redis', 'kafka', 'logs', 'model_algorithm_package',
    'platform_gateway', 'platform_ops/state', 'backend/static',
    'config_dispatch/state', 'config_dispatch/backups', 'config_dispatch/tls',
    'config_dispatch/gateway', 'frontend/static/certificates',
    'platform_algorithm_start/config', 'platform_algorithm_start/log',
)
FILES = ('config_dispatch/security-settings.json', 'platform_ops/backend-client.json',
         'frontend/static/js/certificate-help.js')
ROLES = {'backend': 'application', 'web': 'application', 'media': 'application',
         'dispatch': 'application', 'dispatch-web': 'application',
         'mysql': 'middleware', 'redis': 'middleware', 'kafka': 'middleware',
         'algorithm-master': 'algorithm', 'resource': 'algorithm',
         'kafka-consumer': 'algorithm'}
PORTS = {'backend': 5000, 'web': 8888, 'media': 8085, 'dispatch': 18999,
         'dispatch-web': 8899, 'mysql': 3306, 'redis': 6379, 'kafka': 9092}


def persistent_paths():
    return {'directories': list(DIRECTORIES), 'files': list(FILES), 'shared': list(SHARED)}


def adapt_frontend(root):
    """Keep the existing authenticated upload UI, with accurate image semantics."""
    path = Path(root) / 'frontend/static/js/platform-upgrade.js'
    source = path.read_text(encoding='utf-8')
    marker = '/* platform-container-upgrade-ui-v1 */'
    if marker in source:
        return False
    replacements = (
        ('管理原生前后端版本，上传升级包，或一键回退到上一版本。', '管理离线镜像版本，上传升级包，或一键回退到上一版本。'),
        ('升级和回退只变更前后端代码。现场配置、数据库、账号、授权、证书、算法服务和历史媒体保留。',
         '升级和回退切换涉及服务的镜像。现场配置、数据库、账号、授权、证书和历史媒体保留。'),
        ('platform-native', 'platform-container'),
        ('声明版本、架构和前端或后端组件。代码文件按清单放入包内，可单独更新一个组件或组合更新。',
         '声明版本、架构和application、middleware、algorithm镜像。每个镜像归档由docker save导出，放入清单指定的images目录。'),
        ('每个文件声明相对组件根目录的目标路径、包内路径和 SHA256。需要核对当前文件时提供 base_sha256；新增文件使用 null 表示目标必须不存在。',
         '每个镜像声明含版本的aiplatform标签、归档相对路径archive和SHA256。使用新版本标签更新，已部署的旧版本镜像保留供回退。'),
        ('代码文件', '镜像归档'),
        ('原生前后端代码', '平台镜像'),
        ('原生前端代码', '平台镜像'),
        ('原生后端代码', '平台镜像'),
        ('系统先备份当前代码，再恢复上一版本并检查服务。回退失败时恢复操作前的代码。',
         '系统保留当前镜像，再恢复上一镜像版本并检查容器。回退失败时恢复操作前的镜像版本。'),
        ('算法服务保持运行。', '本次涉及的容器会重新启动。'),
        ('仅当前生效且备份完整、代码一致的版本可回退。', '仅当前生效且旧镜像仍在本机的版本可回退。'),
        ('备份当前代码', '记录当前镜像'),
        ('前后端代码', '平台镜像'),
        ('原生tar.gz或zip代码包', '镜像tar.gz或zip升级包'),
    )
    for before, after in replacements:
        source = source.replace(before, after)
    source = re.sub(r'var exampleLabels = \{[^;]+;',
                    "var exampleLabels = {container_images: '离线镜像更新'};", source, count=1)
    source = re.sub(r'var roles = \{[^;]+;',
                    "var roles = {application: '平台', middleware: '中间件', algorithm: '算法', frontend: '前端', backend: '后端'};", source, count=1)
    source = re.sub(r'var types = \{[^;]+;',
                    "var types = {image: '离线镜像更新', deployment: '容器部署'};", source, count=1)
    source = source.replace("h('dl', [component.base_revision",
        "h('dl', [component.image && proof(h, '镜像标签', component.image), component.image_id && proof(h, '镜像ID', component.image_id), component.base_revision", 1)
    source = source.replace('代码', '镜像').replace('原生', '容器')
    path.write_text(marker + '\n' + source, encoding='utf-8')
    return True


def build_compose(host_root, images, family='huawei', project='aiplatform', devices=None, target_ip=None):
    """Return Compose JSON; the installer seeds the listed persistent files first."""
    host = PurePosixPath(host_root)
    fixed = PurePosixPath(ROOT.as_posix())
    if not host.is_absolute() or str(host) in ('/', '/data', '/home', '/opt'):
        raise ValueError('请选择专用平台目录')
    if 'application' not in images:
        raise ValueError('缺少application镜像')
    if family not in ('huawei', 'sophon', 'none'):
        raise ValueError('未知算力驱动类型')
    volumes = [{'type': 'bind', 'source': str(host / name), 'target': str(fixed / name),
                'bind': {'create_host_path': False}} for name in DIRECTORIES + FILES]
    volumes += [{'type': 'bind', 'source': str(host.parent / name), 'target': str(fixed.parent / name),
                 'bind': {'propagation': 'rslave', 'create_host_path': False}} for name in SHARED]
    # The platform license is tied to the host machine rather than the container ID.
    volumes.append({'type': 'bind', 'source': '/etc/machine-id', 'target': '/etc/machine-id',
                    'read_only': True, 'bind': {'create_host_path': False}})
    if Path('/etc/localtime').exists():
        volumes.append({'type': 'bind', 'source': '/etc/localtime', 'target': '/etc/localtime',
                        'read_only': True, 'bind': {'create_host_path': False}})
    services = {}
    for role, image_role in ROLES.items():
        if role in ('resource', 'kafka-consumer'):
            continue  # These processes share the algorithm container's NPU namespace.
        if image_role == 'algorithm' and family == 'none':
            continue
        selected_role = image_role if image_role in images else 'application'
        service = {'image': images[selected_role], 'container_name': project + '-' + role,
                   'command': [str(fixed / 'runtime/bin/python'), '/opt/ai-platform/container_runtime.py', 'run', role],
                   'network_mode': 'host', 'init': True, 'restart': 'unless-stopped',
                   'environment': {'PLATFORM_HOST_ROOT': str(host), 'PLATFORM_NATIVE_ROOT': str(fixed),
                       'PLATFORM_ALGORITHM_FAMILY': family, 'PYTHONDONTWRITEBYTECODE': '1'},
                   'volumes': list(volumes), 'stop_grace_period': '40s',
                   'logging': {'driver': 'json-file', 'options': {'max-size': '20m', 'max-file': '3'}},
                   'labels': {'com.aiplatform.role': role, 'com.aiplatform.image-role': selected_role}}
        if role in PORTS:
            service['healthcheck'] = {'test': ['CMD', str(fixed / 'runtime/bin/python'),
                '/opt/ai-platform/container_runtime.py', 'health', role], 'interval': '15s',
                'timeout': '5s', 'retries': 12, 'start_period': '30s'}
        if role == 'backend' and target_ip:
            service['environment'].update(ZLK_PUBLIC_BASE_URL='https://' + target_ip + ':8888/media',
                                          SEAL_ALLOWED_ORIGINS='https://' + target_ip + ':8888')
        if target_ip:
            service['environment']['TARGET_IP'] = target_ip
        if image_role == 'algorithm':
            service['pid'] = 'host'
            service['shm_size'] = '1gb'
            service['devices'] = list(devices or [])
            if family == 'huawei':
                service['volumes'] += [{'type': 'bind', 'source': '/usr/local/Ascend/driver',
                    'target': '/usr/local/Ascend/driver', 'read_only': True,
                    'bind': {'create_host_path': False}}]
                if Path('/usr/local/sbin/npu-smi').exists():
                    service['volumes'].append({'type': 'bind', 'source': '/usr/local/sbin/npu-smi',
                        'target': '/usr/local/sbin/npu-smi', 'read_only': True})
        services[role] = service
    return {'name': project, 'services': services}


def aliases(host_root):
    """Resolve SSH-uploaded host paths inside a container with a fixed image root."""
    host = Path(host_root)
    pairs = [(host, ROOT)] + [(host.parent / name, ROOT.parent / name) for name in SHARED]
    for alias, target in pairs:
        if alias == target:
            continue
        if alias.is_symlink():
            if alias.resolve() != target.resolve():
                raise ValueError('容器平台目录别名不匹配')
            continue
        if alias.exists():
            raise ValueError('容器平台目录别名已被占用：' + str(alias))
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(target, target_is_directory=True)


def algorithm_environment(family):
    env = {'PATH': str(ROOT / 'runtime/miniconda3/envs/yolo/bin') + ':' + str(ROOT / 'runtime/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
           'VIDEO_NATIVE_DISPLAY': '1', 'CV2_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}
    if family == 'huawei':
        cann = ROOT / 'runtime/Ascend/cann-9.0.0'
        libraries = ':'.join(str(cann / name) for name in ('aarch64-linux/lib64', 'lib64', 'opp/lib64'))
        env.update(ASCEND_TOOLKIT_PATH=str(cann), ASCEND_OPP_PATH=str(cann / 'opp'),
            ASCEND_PROCESS_LOG_PATH=str(ROOT / 'logs/ascend'), NPU_DEVICE_IDS=os.environ.get('NPU_DEVICE_IDS', '0,1'),
            PYTHONPATH=str(cann / 'python/site-packages'),
            LD_LIBRARY_PATH=libraries + ':/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver')
    elif family == 'sophon':
        env.update(FFMPEG_BIN='/opt/sophon/sophon-ffmpeg_0.10.0/bin/ffmpeg',
            FFPROBE_BIN='/opt/sophon/sophon-ffmpeg_0.10.0/bin/ffprobe', PYTHONNOUSERSITE='1',
            PATH='/opt/sophon/sophon-ffmpeg_0.10.0/bin:' + str(ROOT / 'runtime/sophon-python/bin') + ':' + str(ROOT / 'runtime/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            LD_LIBRARY_PATH='/opt/sophon/libsophon-0.5.1/lib:/opt/sophon/sophon-ffmpeg_0.10.0/lib:/opt/sophon/sophon-opencv_0.10.0/lib')
    return env


def python_environment(environment, family=None):
    """Do not pass the entrypoint's private Python 3.7 home to another runtime."""
    result = dict(environment)
    result.pop('PYTHONHOME', None)
    result.pop('PYTHONPATH', None)
    if family:
        result.update(algorithm_environment(family))
    return result


def configuration_links():
    """One-shot setup and service containers have different writable layers."""
    links = (
        ('Config_files/config.ini', 'backend/config.ini'),
        ('Config_files/platform-security.json', 'backend/platform-security.json'),
        ('Config_files/config.js', 'frontend/static/js/config.js'),
        ('Config_files/zlk/config.ini', 'media/conf/config.ini'),
        ('Config_files/zlk/default.pem', 'media/bin/default.pem'),
        ('platform_ops/backend-client.json', 'backend/config/platform-ops-client.json'),
        ('frontend/static/certificates/dispatch-root-ca.cer', 'config_dispatch/dispatch-root-ca.cer'),
    )
    for source, destination in links:
        path = ROOT / destination
        target = ROOT / source
        if path.is_symlink() and path.resolve() == target.resolve():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.is_file():
            path.unlink()
        path.symlink_to(target)


def render_target_ip(role, target_ip):
    """Render only this process's small application files in its own layer."""
    if not target_ip:
        return
    folders = {'backend': ('backend',), 'web': ('frontend',), 'media': ('media',),
               'dispatch': ('config_dispatch',), 'dispatch-web': ('config_dispatch',),
               'algorithm-master': ('platform_algorithm_start',),
               'resource': ('model_algorithm_package',), 'kafka-consumer': ('model_algorithm_package',)}
    suffixes = ('.py', '.ini', '.json', '.conf', '.cnf', '.js', '.html', '.sh')
    for folder in folders.get(role, ()):
        for path in (ROOT / folder).rglob('*'):
            if path.is_symlink() or not path.is_file() or path.suffix not in suffixes or path.stat().st_size > 12*1024*1024:
                continue
            try:
                source = path.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            if '__PLATFORM_TARGET_IP__' in source:
                path.write_text(source.replace('__PLATFORM_TARGET_IP__', target_ip), encoding='utf-8')


def command(role):
    py = str(ROOT / 'runtime/bin/python')
    nginx = str(ROOT / 'runtime/bin/nginx')
    if role == 'backend':
        return [py, '-m', 'gunicorn', '--workers', '1', '--threads', '4', '--bind',
                '127.0.0.1:5000', '--timeout', '180', 'main:app'], ROOT / 'backend'
    if role in ('web', 'dispatch-web'):
        folder = ROOT / ('platform_gateway' if role == 'web' else 'config_dispatch/gateway')
        return [nginx, '-p', str(folder) + '/', '-c', str(folder / 'nginx.conf'), '-g', 'daemon off;'], folder
    if role == 'media':
        return [str(ROOT / 'runtime/bin/MediaServer'), '-c', str(ROOT / 'Config_files/zlk/config.ini')], ROOT / 'media/bin'
    if role == 'dispatch':
        return [os.environ.get('DISPATCH_PYTHON', '/usr/bin/python3'), str(ROOT / 'config_dispatch/secure_server.py'),
                '--settings', str(ROOT / 'config_dispatch/security-settings.json')], ROOT / 'config_dispatch'
    if role == 'mysql':
        return [str(ROOT / 'runtime/mysql/bin/mysqld'), '--defaults-file=' + str(ROOT / 'Config_files/mysql.cnf'),
                '--user=root'], ROOT / 'mysql'
    if role == 'redis':
        return [str(ROOT / 'runtime/redis/bin/redis-server'), str(ROOT / 'Config_files/redis.conf')], ROOT / 'redis'
    if role == 'kafka':
        return [str(ROOT / 'runtime/kafka/bin/kafka-server-start.sh'), str(ROOT / 'Config_files/kafka.properties')], ROOT / 'runtime/kafka'
    if role in ('algorithm-master', 'resource', 'kafka-consumer'):
        family = os.environ.get('PLATFORM_ALGORITHM_FAMILY', 'huawei')
        algorithm_py = os.environ.get('ALGORITHM_PYTHON', str(ROOT / ('runtime/sophon-python/bin/python'
                                      if family == 'sophon' else 'runtime/miniconda3/envs/yolo/bin/python')))
        if role == 'algorithm-master':
            folder, script = ROOT / 'platform_algorithm_start', 'model_start.py'
        else:
            folder = ROOT / 'model_algorithm_package'
            script = (os.environ.get('ALGORITHM_RESOURCE_SCRIPT', 'Huawei_resource.py' if family == 'huawei'
                      else 'Sophon_resource.py') if role == 'resource' else 'kafka_consumer.py')
        return [algorithm_py, str(folder / script)], folder
    raise ValueError('未知容器服务：' + role)


def supervise_algorithm(environment, grace_seconds=30):
    """Keep scheduler and collectors in one device-owning mount namespace."""
    children = []
    stopping = [False]
    previous = {}

    def forward(signum):
        for child in children:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(child.pid, signum)
                elif child.poll() is None:
                    child.send_signal(signum)
            except ProcessLookupError:
                pass

    def stop(signum, _frame):
        stopping[0] = True
        forward(signum)

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, stop)
        for role in ('algorithm-master', 'resource', 'kafka-consumer'):
            if stopping[0]:
                return 0
            args, cwd = command(role)
            children.append(subprocess.Popen(args, cwd=str(cwd), env=environment,
                                             start_new_session=True))
        while not stopping[0]:
            for child in children:
                code = child.poll()
                if code is not None:
                    # All three are long-running services. Any unexpected exit
                    # stops the group so Docker can restart a complete runtime.
                    return code if code > 0 else (128 - code if code < 0 else 1)
            time.sleep(0.2)
        return 0
    finally:
        forward(signal.SIGTERM)
        deadline = time.monotonic() + grace_seconds
        while any(child.poll() is None for child in children) and time.monotonic() < deadline:
            time.sleep(0.1)
        for child in children:
            if child.poll() is None:
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(child.pid, getattr(signal, 'SIGKILL', 9))
                    else:
                        child.kill()
                except ProcessLookupError:
                    pass
            child.wait()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run(role):
    aliases(os.environ.get('PLATFORM_HOST_ROOT', str(ROOT)))
    configuration_links()
    render_target_ip(role, os.environ.get('TARGET_IP'))
    env = dict(os.environ)
    env.update(PATH=str(ROOT / 'runtime/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               PLATFORM_SECURITY_CONFIG=str(ROOT / 'Config_files/platform-security.json'),
               HOST_MACHINE_ID=Path('/etc/machine-id').read_text().strip(),
               CFGP_ROOTS=' '.join(str(ROOT / p) for p in ('Config_files', 'model_algorithm_package', 'platform_algorithm_start')))
    if role in ('algorithm-master', 'resource', 'kafka-consumer'):
        env = python_environment(env, env.get('PLATFORM_ALGORITHM_FAMILY', 'huawei'))
    elif role == 'dispatch':
        env = python_environment(env)
    if role == 'algorithm-master':
        render_target_ip('resource', os.environ.get('TARGET_IP'))
        render_target_ip('kafka-consumer', os.environ.get('TARGET_IP'))
        raise SystemExit(supervise_algorithm(env))
    if role == 'kafka':
        env.update(JAVA_HOME=str(ROOT / 'runtime/jdk11'), LOG_DIR=str(ROOT / 'logs/kafka'),
                   KAFKA_HEAP_OPTS=env.get('KAFKA_HEAP_OPTS', '-Xms256m -Xmx512m'))
        data = ROOT / 'kafka/kraft-combined-logs'
        if not (data / 'meta.properties').is_file():
            script = str(ROOT / 'runtime/kafka/bin/kafka-storage.sh')
            cluster = subprocess.check_output([script, 'random-uuid'], env=env, universal_newlines=True).strip()
            subprocess.run([script, 'format', '-t', cluster, '-c', str(ROOT / 'Config_files/kafka.properties')],
                           env=env, check=True)
    args, cwd = command(role)
    if role == 'mysql' and not (ROOT / 'mysql/mysql').is_dir():
        subprocess.run(args + ['--initialize-insecure'], cwd=str(cwd), env=env, check=True)
    os.chdir(str(cwd))
    os.execvpe(args[0], args, env)


def health(role):
    import socket
    host = os.environ.get('TARGET_IP', '127.0.0.1') if role == 'dispatch-web' else '127.0.0.1'
    with socket.create_connection((host, PORTS[role]), timeout=3):
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'health', 'compose', 'paths'))
    parser.add_argument('role', nargs='?')
    parser.add_argument('--host-root', default=str(ROOT))
    parser.add_argument('--images', help='JSON mapping application/middleware/algorithm to image tags')
    parser.add_argument('--family', choices=('huawei', 'sophon', 'none'), default='huawei')
    args = parser.parse_args()
    if args.action == 'run':
        run(args.role)
    elif args.action == 'health':
        raise SystemExit(health(args.role))
    elif args.action == 'paths':
        print(json.dumps(persistent_paths()))
    else:
        print(json.dumps(build_compose(args.host_root, json.loads(args.images), args.family), indent=2))


if __name__ == '__main__':
    main()
