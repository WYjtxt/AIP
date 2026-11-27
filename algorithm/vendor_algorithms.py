#!/usr/bin/env python3
"""Build a single-vendor algorithm bundle or activate it on an existing AIP Compose host."""

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath


FAMILIES = {'sophon': 'x86_64', 'huawei': 'aarch64'}
NATIVE_ROOT = PurePosixPath('/data/AIGO/platform_start')
SOPHON_PCI = {('1e30', '1684'), ('1f1c', '1686')}
MANAGED = 'algorithm-vendors'
ROLE = 'algorithm-master'
MANIFEST = 'vendor-manifest.json'
BUNDLE_NAMES = {name: 'algorithm-' + name + '.tar.gz' for name in FAMILIES}
MAX_FILE = 2 * 1024 ** 3
MAX_BUNDLE = 5 * 1024 ** 3
MAX_FILES = 4000
MODEL_FILES = {'.om', '.bmodel', '.onnx'}
COLLECTORS = {'sophon': 'Sophon_resource.py', 'huawei': 'Huawei_resource.py'}
TOP_LEVEL_PROGRAMS = {'kafka_consumer.py', 'platform_host_identity.py', 'platform_telemetry.py',
                      'telemetry_identity.py', 'telemetry_resource.py', 'resource_heartbeat.py'}
EXCLUDED_PARTS = {'config', 'log', 'logs', '__pycache__', '.git', '.ssh', 'tests', 'tools'}
REQUIRED_ENGINE = ('engine/model_start.py', 'engine/templates/rtsp_infer_push.py', 'engine/comm/hik_gateway.py')


class SelectionError(ValueError):
    pass


def regular_char(path):
    try:
        return stat.S_ISCHR(path.stat().st_mode)
    except OSError:
        return False


def sysfs_value(path):
    try:
        value = path.read_text('ascii').strip().lower()
        return value[2:] if value.startswith('0x') else value
    except (OSError, UnicodeError):
        return ''


def run(*args, check=True, timeout=30):
    return subprocess.run(args, check=check, timeout=timeout, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='replace')


def detect_driver(system=Path('/'), *, probe=run, is_char=regular_char):
    """Use live vendor driver tools and device nodes. Never decide from CPU architecture."""
    sysfs = system / 'sys/bus/pci/devices'
    dev = system / 'dev'
    sophon_devices = [p for p in dev.glob('bm-sophon*') if re.fullmatch(r'bm-sophon\d+', p.name) and is_char(p)]
    huawei_devices = [p for p in dev.glob('davinci*') if re.fullmatch(r'davinci\d+', p.name) and is_char(p)]
    sophon_pci = any((sysfs_value(p / 'vendor'), sysfs_value(p / 'device')) in SOPHON_PCI
                     for p in sysfs.glob('*'))
    sophon_present = bool(sophon_devices or sophon_pci or (system / 'sys/module/bmsophon').is_dir())
    huawei_present = bool(huawei_devices or (system / 'usr/local/Ascend/driver/version.info').is_file())
    if sophon_present == huawei_present:
        raise SelectionError('同时发现算能和华为，或两者均未检出。没有安装或删除算法目录。')
    family = 'sophon' if sophon_present else 'huawei'
    devices = sophon_devices if family == 'sophon' else huawei_devices
    if not devices:
        raise SelectionError('已发现驱动标识，设备尚未就绪。没有安装或删除算法目录。')
    if family == 'sophon':
        candidates = ('/opt/sophon/libsophon-current/bin/bm-smi', '/opt/sophon/libsophon-0.5.1/bin/bm-smi',
                      '/usr/bin/bm-smi', '/usr/local/bin/bm-smi')
        executable = next((str(system / item.lstrip('/')) for item in candidates
                           if (system / item.lstrip('/')).is_file()), 'bm-smi')
        command = (executable,)
    else:
        candidates = ('/usr/local/sbin/npu-smi', '/usr/local/Ascend/driver/tools/npu-smi', '/usr/bin/npu-smi')
        executable = next((str(system / item.lstrip('/')) for item in candidates
                           if (system / item.lstrip('/')).is_file()), 'npu-smi')
        command = (executable, 'info')
    try:
        result = probe(*command, check=False, timeout=20)
    except (OSError, subprocess.SubprocessError):
        raise SelectionError('驱动诊断命令无法完成。没有安装或删除算法目录。') from None
    if (result.returncode or (family == 'huawei' and
            (not re.search(r'310P', result.stdout, re.I) or not re.search(r'\bOK\b', result.stdout, re.I)))):
        raise SelectionError('驱动未通过已交付设备兼容性检查。没有安装或删除算法目录。')
    return family


def safe_relative(name):
    result = PurePosixPath(name)
    if (not result.parts or result.as_posix() != name or result.is_absolute() or '..' in result.parts
            or '\\' in name or ':' in name or any(ord(ch) < 32 for ch in name)):
        raise SelectionError('算法包内存在无效路径')
    return result


def is_program(relative, family):
    p = safe_relative(relative)
    if len(p.parts) < 2 or any(part.lower() in EXCLUDED_PARTS for part in p.parts[1:]):
        return False
    if p.name.endswith('.dpapi') or p.name == 'Conf_files.py':
        return False
    extension = p.suffix.lower()
    if family == 'huawei' and (extension == '.bmodel' or 'runtime_acceleration' in p.parts
                               or 'sophon' in p.name.lower()):
        return False
    if family == 'sophon' and (extension == '.om' or re.search(r'ascend|huawei', p.name, re.I)):
        return False
    if p.parts[0] == 'engine':
        return True
    if p.parts[0] == 'overrides':
        return family == 'huawei' and p.parts[1] in ('algorithm-runtime', 'personcount-huawei', 'pose',
                                                       'native_hik_gateway.py')
    if p.parts[0] == 'packages':
        return (p.parts[1] == '_platform_push' or p.name == COLLECTORS[family] or p.name in TOP_LEVEL_PROGRAMS
                or extension in MODEL_FILES or p.name.lower().endswith('.om.input.json'))
    return False


def check_contents(family, records):
    needed = {*REQUIRED_ENGINE, 'packages/' + COLLECTORS[family], 'packages/kafka_consumer.py'}
    if not needed <= records.keys():
        raise SelectionError('算法包不完整，缺少调度、取流、采集或消息处理程序')
    if family == 'sophon' and 'packages/_platform_push/push_outbox.py' not in records:
        raise SelectionError('算能算法包缺少报警推送队列模块')


def reject_unrendered_site_tokens(path):
    if path.suffix.lower() in ('.py', '.ini', '.json', '.conf', '.sh', '.js') and path.stat().st_size <= 12 * 1024 ** 2:
        if b'__PLATFORM_TARGET_IP__' in path.read_bytes():
            raise SelectionError('算法文件包含启动时需改写的站点占位符，不能只读挂载')


def digest(source):
    value = hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def add_file(tar, name, source):
    info = tarfile.TarInfo(name)
    info.size = source.stat().st_size
    info.mode = 0o644
    with source.open('rb') as stream:
        tar.addfile(info, stream)


def build(project_code, family, destination, portable=None):
    algorithm = project_code / 'algorithm'
    branch = algorithm / family
    if family == 'sophon' and not (branch / 'engine').is_dir():
        branch = algorithm  # Working snapshots still keep Sophon's historical engine/packages paths.
    paths = {}
    for top in ('engine', 'packages', 'overrides'):
        for file in (branch / top).rglob('*'):
            name = file.relative_to(branch).as_posix()
            if file.is_file() and is_program(name, family):
                if file.is_symlink() or not beneath(file.resolve(), branch.resolve()):
                    raise SelectionError('算法源码含无法打包的符号链接')
                paths[name] = file
    if family == 'sophon' and portable is not None:
        paths.update({'engine/comm/recorder_recovery.py': portable / 'recorder_recovery.py',
                      'packages/kafka_consumer.py': portable / 'kafka_consumer.py'})
    check_contents(family, paths)
    if any(not p.is_file() or p.is_symlink() for p in paths.values()):
        raise SelectionError('安全的算法源码覆盖文件缺失或不可用')
    for path in paths.values():
        reject_unrendered_site_tokens(path)
    files = {name: {'sha256': digest(path), 'size': path.stat().st_size} for name, path in paths.items()}
    payload = encoded({'schema': 1, 'family': family, 'architecture': FAMILIES[family], 'files': files})
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    read_manifest(payload, family)
    with tempfile.TemporaryDirectory(prefix='.algorithm-build-', dir=destination.parent) as temporary:
        package = Path(temporary) / 'bundle.tar.gz'
        with tarfile.open(package, 'x:gz', format=tarfile.PAX_FORMAT) as tar:
            metadata = tarfile.TarInfo(MANIFEST)
            metadata.size = len(payload)
            metadata.mode = 0o644
            tar.addfile(metadata, io.BytesIO(payload))
            for name, path in sorted(paths.items()):
                add_file(tar, family + '/' + name, path)
        if os.name == 'nt':
            os.rename(package, destination)  # Windows rename refuses an existing destination.
        else:
            os.link(package, destination)
    return len(files)


def read_manifest(raw, family):
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('schema') != 1 or data.get('family') != family
            or data.get('architecture') != FAMILIES[family] or not isinstance(data.get('files'), dict)):
        raise SelectionError('算法包与已检测驱动不一致，或包格式不受支持')
    records = data['files']
    if not records or len(records) > MAX_FILES:
        raise SelectionError('算法包文件数量越界')
    total = 0
    for name, entry in records.items():
        if (not is_program(name, family) or not isinstance(entry, dict) or set(entry) != {'sha256', 'size'}
                or not isinstance(entry['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])
                or type(entry['size']) is not int or not 0 <= entry['size'] <= MAX_FILE):
            raise SelectionError('算法包清单存在异厂商或无效文件')
        total += entry['size']
    if total > MAX_BUNDLE:
        raise SelectionError('算法包总大小越界')
    check_contents(family, records)
    return records


def unpack(archive, family, staging):
    with tarfile.open(archive, 'r|gz') as tar:
        item = tar.next()
        if not item or item.name != MANIFEST or not item.isfile() or item.size > 2 * 1024 * 1024:
            raise SelectionError('算法包缺少首条清单')
        raw = tar.extractfile(item).read()
        records = read_manifest(raw, family)
        remaining = set(records)
        while True:
            item = tar.next()
            if item is None:
                break
            name = safe_relative(item.name)
            if name.parts[0] != family or len(name.parts) < 2:
                raise SelectionError('算法包混入其他厂商目录')
            relative = PurePosixPath(*name.parts[1:]).as_posix()
            if relative not in remaining or not item.isfile() or item.size != records[relative]['size']:
                raise SelectionError('算法包与清单不一致或含不安全文件类型')
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                shutil.copyfileobj(tar.extractfile(item), stream)
            if digest(target) != records[relative]['sha256']:
                raise SelectionError('算法文件 SHA-256 校验失败')
            reject_unrendered_site_tokens(target)
            remaining.remove(relative)
        if remaining:
            raise SelectionError('算法包缺少清单中声明的文件')
    (staging / MANIFEST).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), records


def checked_dir(path, *, create=False):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise SelectionError('算法安装路径中存在符号链接或非目录')
    if create:
        path.mkdir(exist_ok=True)
    return path


def beneath(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def mounted_inside(path):
    mountinfo = Path('/proc/self/mountinfo').read_text('utf-8')
    for entry in mountinfo.splitlines():
        mount = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), entry.split()[4])
        if beneath(Path(mount), path):
            return True
    return False


def installed_manifest(directory, family):
    checked_dir(directory)
    receipt = directory / MANIFEST
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 2 * 1024 * 1024:
        raise SelectionError('已有算法目录缺少安全的受管清单')
    raw = receipt.read_bytes()
    if hashlib.sha256(raw).hexdigest() != directory.name:
        raise SelectionError('已有算法目录的清单标识不匹配')
    records = read_manifest(raw, family)
    seen = set()
    for path in directory.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise SelectionError('已有算法目录含符号链接或特殊文件')
        if path.is_file() and path != receipt:
            name = path.relative_to(directory).as_posix()
            if name not in records or digest(path) != records[name]['sha256']:
                raise SelectionError('已有算法目录含现场修改，保留以供核对')
            seen.add(name)
    if seen != records.keys():
        raise SelectionError('已有算法目录中的文件缺失')
    return records


def verify_opposite(directory, family):
    checked_dir(directory)
    if not directory.exists():
        return
    if mounted_inside(directory):
        raise SelectionError('异厂商算法目录中有活动挂载，未删除')
    revisions = list(directory.iterdir())
    if not revisions:
        raise SelectionError('无法确认空的异厂商算法目录为本工具创建，未删除')
    for revision in revisions:
        if not re.fullmatch('[0-9a-f]{64}', revision.name):
            raise SelectionError('另一厂商目录中有非受管文件，未删除')
        installed_manifest(revision, family)


def runtime_path(name):
    p = safe_relative(name)
    group = p.parts[0]
    tail = PurePosixPath(*p.parts[1:])
    if group == 'engine':
        return NATIVE_ROOT / 'platform_algorithm_start' / tail
    if group == 'packages':
        return NATIVE_ROOT / 'model_algorithm_package' / tail
    if tail.parts[0] == 'pose':
        return PurePosixPath('/opt/ai-platform/release-defaults') / tail
    if tail.parts[0] == 'native_hik_gateway.py':
        return PurePosixPath('/opt/ai-platform/release-defaults/code') / tail
    return NATIVE_ROOT / 'Config_files' / tail


def in_managed_source(source, managed):
    return isinstance(source, str) and Path(source).is_absolute() and beneath(Path(source), managed)


def configure_service(document, family, installed, files, managed):
    services = document.get('services')
    if not isinstance(services, dict) or ROLE not in services:
        raise SelectionError('当前 Compose 安装未配置算法服务，请先安装同厂商基础镜像')
    role = services[ROLE]
    environment = role.get('environment')
    if not isinstance(environment, dict) or environment.get('PLATFORM_ALGORITHM_FAMILY') != family:
        raise SelectionError('现有 Compose 算法基础镜像与已检测驱动不一致')
    volumes = role.get('volumes', [])
    if not isinstance(volumes, list) or any(not isinstance(v, dict) for v in volumes):
        raise SelectionError('Compose 挂载不符合 AIP 格式')
    for name, service in services.items():
        if name == ROLE:
            continue
        for volume in service.get('volumes', []):
            if isinstance(volume, dict) and in_managed_source(volume.get('source'), managed):
                raise SelectionError('非算法服务仍引用受管算法目录，不能清理另一厂商')
    kept = [v for v in volumes if not in_managed_source(v.get('source'), managed)]
    reserved = {v.get('target') for v in kept}
    additions = []
    for name in sorted(files):
        target = str(runtime_path(name))
        if target in reserved:
            raise SelectionError('算法文件与已有 Compose 挂载冲突')
        additions.append({'type': 'bind', 'source': str(installed / name), 'target': target,
                          'read_only': True, 'bind': {'create_host_path': False}})
    role['volumes'] = kept + additions
    return role


def atomic_replace(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        name = Path(temporary.name)
        temporary.write(raw)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        name.chmod(stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600)
        os.replace(name, path)
    finally:
        if name.exists():
            name.unlink()


def compose(base, path, *args, **kwargs):
    return run('docker', 'compose', '--project-directory', str(base), '-f', str(path), *args, **kwargs)


def smoke(base, config, family):
    names = ['model_start.py', COLLECTORS[family], 'kafka_consumer.py']
    check = '''import glob, pathlib, sys
root = '/data/AIGO/platform_start/'
expected = {root + 'platform_algorithm_start/' + sys.argv[1],
            root + 'model_algorithm_package/' + sys.argv[2],
            root + 'model_algorithm_package/' + sys.argv[3]}
own_cgroup = pathlib.Path('/proc/self/cgroup').read_bytes()
seen = set()
for name in glob.glob('/proc/[0-9]*/cmdline'):
    try:
        cmdline = pathlib.Path(name)
        argv = cmdline.read_bytes().decode('utf-8', 'replace').split(chr(0))
        if len(argv) <= 1 or argv[1] not in expected:
            continue
        if cmdline.with_name('cgroup').read_bytes() != own_cgroup:
            continue
    except OSError:
        continue
    seen.add(argv[1])
raise SystemExit(expected != seen)
'''
    for _ in range(24):
        answer = compose(base, config, 'exec', '-T', ROLE, str(NATIVE_ROOT / 'runtime/bin/python'),
                         '-c', check, *names, check=False, timeout=12)
        if not answer.returncode:
            time.sleep(3)
            answer = compose(base, config, 'exec', '-T', ROLE, str(NATIVE_ROOT / 'runtime/bin/python'),
                             '-c', check, *names, check=False, timeout=12)
            if not answer.returncode:
                return
        time.sleep(2)
    raise SelectionError('算法调度、资源采集或消息服务未通过启动检查')


def check_container_references(directory):
    running = run('docker', 'ps', '-q').stdout.split()
    if not running:
        return
    for container in json.loads(run('docker', 'inspect', *running).stdout):
        for attachment in container.get('Mounts', ()):
            source = attachment.get('Source')
            if attachment.get('Type') == 'bind' and isinstance(source, str):
                resolved = Path(source).resolve()
                if beneath(resolved, directory) or beneath(directory, resolved):
                    raise SelectionError('正在运行的容器仍挂载另一厂商算法，未删除')


def apply_locked(root, config, archive, family):
    managed = checked_dir(root / MANAGED, create=True)
    if mounted_inside(managed):
        raise SelectionError('算法目录中存在挂载点，无法保证可靠切换')
    extra = next(name for name in FAMILIES if name != family)
    opposite = managed / extra
    verify_opposite(opposite, extra)
    previous = config.read_bytes()
    document = json.loads(previous)
    with tempfile.TemporaryDirectory(prefix='.verify-', dir=managed) as stage:
        scratch = Path(stage)
        revision, files = unpack(archive, family, scratch)
        active = checked_dir(managed / family, create=True)
        installed = active / revision
        role = configure_service(document, family, installed, files, managed)
        result = run('docker', 'image', 'inspect', '--format', '{{.Architecture}}', role['image'])
        known = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(result.stdout.strip(), result.stdout.strip())
        if known != FAMILIES[family]:
            raise SelectionError('已安装算法镜像的架构与本地算法包不一致')
        if installed.exists() or installed.is_symlink():
            installed_manifest(installed, family)
        else:
            os.rename(scratch, installed)
    atomic_replace(config, encoded(document))
    try:
        compose(config.parent, config, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                ROLE, timeout=240)
        smoke(config.parent, config, family)
    except (SelectionError, OSError, subprocess.SubprocessError) as error:
        atomic_replace(config, previous)
        try:
            compose(config.parent, config, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                    ROLE, timeout=240)
        except (OSError, subprocess.SubprocessError):
            raise SelectionError('切换失败，旧 Compose 已恢复，旧算法服务重启亦失败') from None
        raise SelectionError('切换失败，已恢复上一版算法服务') from error
    if opposite.exists():
        verify_opposite(opposite, extra)
        check_container_references(opposite)
        if not shutil.rmtree.avoids_symlink_attacks:
            raise SelectionError('本机删除函数无法安全清理另一厂商目录')
        shutil.rmtree(opposite)
    return revision


def apply(root, archive, *, choose=False):
    import fcntl

    family = detect_driver()
    if choose:
        if archive.is_symlink() or not archive.is_dir():
            raise SelectionError('请选择实际的算法包目录')
        archive = archive / BUNDLE_NAMES[family]
    real_arch = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine(), platform.machine())
    if real_arch != FAMILIES[family]:
        raise SelectionError('当前驱动已确认，本次发布未提供该 CPU 架构的算法文件')
    if not root.is_absolute() or root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise SelectionError('请指定实际平台目录，路径不得包含符号链接')
    config = checked_dir(root / 'container') / 'compose.json'
    if config.is_symlink() or not config.is_file() or archive.is_symlink() or not archive.is_file():
        raise SelectionError('未找到 AIP Compose 配置或单厂商算法包')
    with os.fdopen(os.open(config.parent / '.algorithm-vendor.lock',
                           os.O_NOFOLLOW | os.O_CREAT | os.O_RDWR, 0o600), 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return family, apply_locked(root, config, archive, family)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('probe', help='check live hardware without changes')
    package = sub.add_parser('build', help='build only the requested family on the source machine')
    package.add_argument('family', choices=[*FAMILIES, 'auto'])
    package.add_argument('archive', type=Path)
    package.add_argument('--code', type=Path, default=Path(__file__).resolve().parents[1])
    package.add_argument('--portable-sophon', type=Path)
    install = sub.add_parser('apply', help='activate the selected bundle and restart the AIP algorithm service')
    install.add_argument('root', type=Path)
    install.add_argument('archive', type=Path)
    automatic = sub.add_parser('apply-auto', help='select the matching bundle from an offline directory')
    automatic.add_argument('root', type=Path)
    automatic.add_argument('directory', type=Path)
    audit = sub.add_parser('verify', help='check one archive without contacting Docker')
    audit.add_argument('family', choices=FAMILIES)
    audit.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'probe':
            family = detect_driver()
            print(json.dumps({'family': family, 'package_architecture': FAMILIES[family]}))
        elif args.action == 'build':
            family = detect_driver() if args.family == 'auto' else args.family
            portable = args.portable_sophon
            if family == 'sophon' and portable is None:
                candidates = (args.code / 'algorithm/sophon/release-overrides',
                              args.code.parent / 'tools/portable/sophon')
                portable = next((path for path in candidates if path.is_dir()), None)
            print(json.dumps({'family': family,
                              'files': build(args.code, family, args.archive, portable)}))
        elif args.action == 'verify':
            with tempfile.TemporaryDirectory(prefix='v-', dir=args.archive.resolve().parent) as temp:
                revision, files = unpack(args.archive, args.family, Path(temp))
            print(json.dumps({'family': args.family, 'files': len(files), 'revision': revision}))
        else:
            choose = args.action == 'apply-auto'
            family, revision = apply(args.root, args.directory if choose else args.archive, choose=choose)
            print(json.dumps({'active_family': family, 'revision': revision}))
    except (ValueError, OSError, subprocess.SubprocessError) as problem:
        parser.exit(1, '%s\n' % problem)


if __name__ == '__main__':
    main()
