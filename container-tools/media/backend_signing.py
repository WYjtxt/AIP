"""Preserve effective backend signing keys without logging or exporting secrets.

Full repair migrates only the two documented persistent layouts to the site's
canonical file. Platform-only updates retain their existing volume and env.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import uuid

CANONICAL = '/Seal_system/platform-security.json'
LEGACY = '/var/lib/seal-system/platform-security.json'
NAMES = ('SESSION_SECRET_KEY', 'JWT_SECRET_KEY', 'MEDIA_SESSION_SECRET_KEY')
MAX_BYTES = 65536


class SigningError(RuntimeError):
    pass


def _run(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def _no_prior_docker_state(default_root=Path('/var/lib/docker'), config=Path('/etc/docker/daemon.json'), work=None):
    """Only a demonstrably uninstalled runtime may continue partial installation."""
    roots = [Path(default_root)]
    config = Path(config)
    if config.exists() or config.is_symlink():
        if config.is_symlink() or not config.is_file():
            return False
        try:
            settings = json.loads(config.read_text(encoding='utf-8'))
            configured = settings.get('data-root')
        except (ValueError, AttributeError, OSError):
            return False
        if configured is not None:
            if not isinstance(configured, str) or not Path(configured).is_absolute():
                return False
            roots.append(Path(configured))
    for root in roots:
        if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
            return False
    state = Path(work or os.environ.get('ONECLICK_ROOT', '/root/oneclick')) / 'container-transaction.json'
    if state.exists() or state.is_symlink():
        try:
            if state.is_symlink() or json.loads(state.read_text(encoding='utf-8')).get('containers'):
                return False
        except (ValueError, AttributeError, OSError):
            return False
    return True


def inspect_backend():
    if not shutil.which('docker'):
        if _no_prior_docker_state():
            return None
        raise SigningError('无法核对原后台签名配置：Docker 不可用；未生成替代密钥')
    endpoint = os.environ.get('DOCKER_HOST', '')
    if not endpoint:
        result = _run(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'])
        if result.returncode:
            raise SigningError('无法核对本机 Docker 端点')
        endpoint = result.stdout.decode('utf-8').strip()
    if not endpoint.startswith('unix://'):
        raise SigningError('签名配置保留只允许本机 Docker Unix socket')
    result = _run(['docker', 'inspect', 'seal_system'])
    if result.returncode == 0:
        return json.loads(result.stdout)[0]
    # A missing container is different from an unreachable Docker daemon.
    probe = _run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    if probe.returncode:
        raise SigningError('无法核对原后台容器；未生成替代密钥')
    listed = _run(['docker', 'ps', '-a', '--filter', 'name=^/seal_system$', '--format', '{{.ID}}'])
    if listed.returncode or listed.stdout.strip():
        raise SigningError('原后台容器存在但无法核对其签名配置')
    return None


def canonical_path(root):
    base = Path(root).resolve()
    directory = base / 'Config_files'
    if directory.is_symlink() or not directory.is_dir():
        raise SigningError('签名配置目录不存在或含未授权符号链接')
    path = directory / 'platform-security.json'
    if path.is_symlink():
        raise SigningError('签名配置文件不可为符号链接')
    return path


def _file_bytes(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_BYTES):
        raise SigningError('签名配置必须是 root 所有的单链接普通文件，权限不宽于 0600')
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise SigningError('读取时签名配置发生变化')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SigningError('签名配置超过大小限制')
    return data


def fingerprint(data):
    try:
        values = json.loads(data.decode('utf-8'))
        keys = [values.get(name) for name in NAMES]
        valid = (isinstance(values, dict) and
                 all(isinstance(key, str) and len(key) >= 64 and len(set(key)) >= 8 for key in keys) and
                 len(set(keys)) == len(keys))
    except (ValueError, TypeError, AttributeError, UnicodeError):
        valid = False
    if not valid:
        raise SigningError('原后台签名配置无效；拒绝静默生成新密钥')
    # Private comparison state only. Never print this digest or include it in a release artifact.
    return hashlib.sha256(json.dumps(keys, separators=(',', ':')).encode('utf-8')).hexdigest()


def _container_bytes(info, path):
    result = _run(['docker', 'cp', info['Id'] + ':' + path, '-'])
    if result.returncode or len(result.stdout) > MAX_BYTES + 32768:
        raise SigningError('无法安全读取原后台生效签名文件')
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:*') as archive:
            members = archive.getmembers()
            if len(members) != 1:
                raise SigningError('后台签名文件归档结构异常')
            member = members[0]
            if (not member.isfile() or member.name.rstrip('/').split('/')[-1] != 'platform-security.json' or
                    member.uid != 0 or member.mode & 0o077 or member.size > MAX_BYTES):
                raise SigningError('后台生效签名文件类型或权限不合法')
            return archive.extractfile(member).read()
    except (tarfile.TarError, OSError):
        raise SigningError('后台签名文件归档不可读')


def active_snapshot(info, root, include_content=False):
    """Accept exact documented mounts, not arbitrary paths/implicit new keys."""
    environment = dict(item.split('=', 1) for item in info['Config'].get('Env', []) if '=' in item)
    path = environment.get('PLATFORM_SECURITY_CONFIG', CANONICAL)
    if path not in (CANONICAL, LEGACY):
        raise SigningError('原后台使用未知签名路径，停止以保留原有效密钥')
    mounts = info.get('Mounts', [])
    if path == CANONICAL:
        matches = [m for m in mounts if m.get('Destination') == CANONICAL and m.get('Type') == 'bind']
        if len(matches) != 1:
            raise SigningError('原后台签名配置缺少明确持久化挂载')
        mount = matches[0]
        host = canonical_path(root)
        if Path(mount['Source']).resolve() != host:
            raise SigningError('原后台签名挂载不属于所选平台根目录')
    else:
        matches = [m for m in mounts if m.get('Destination') == '/var/lib/seal-system' and m.get('Type') == 'volume']
        if len(matches) != 1 or not matches[0].get('Name'):
            raise SigningError('旧版签名路径缺少合法持久 Docker 卷')
        mount = matches[0]
        result = _run(['docker', 'volume', 'inspect', mount['Name']])
        if result.returncode:
            raise SigningError('原签名卷不存在')
        volume = json.loads(result.stdout)[0]
        base = Path(volume['Mountpoint'])
        if (volume.get('Driver') != 'local' or volume.get('Options') or
                str(base) != mount.get('Source') or base.is_symlink() or not base.is_dir()):
            raise SigningError('原签名卷不是已验证的本机持久卷')
        host = base / 'platform-security.json'
    data = _file_bytes(host)
    # Detect stale bind inodes or a file changed while being inspected.
    if _container_bytes(info, path) != data or _file_bytes(host) != data:
        raise SigningError('后台生效签名文件与持久化源不一致，停止以保留现场')
    record = {'path': path, 'fingerprint': fingerprint(data), 'container_id': info['Id'],
              'mount_type': mount['Type'], 'mount_source': mount.get('Name') or mount['Source']}
    if include_content:
        record['content'] = data
    return record


def canonical_snapshot(root):
    return {'path': CANONICAL, 'fingerprint': fingerprint(_file_bytes(canonical_path(root)))}


def assert_preserved(expected, observed, require_same_path=True):
    if expected['fingerprint'] != observed['fingerprint'] or (require_same_path and expected['path'] != observed['path']):
        raise SigningError('后台有效签名密钥发生变化，拒绝提交更新')


def _atomic_private(path, data):
    path = Path(path)
    if path.is_symlink():
        raise SigningError('拒绝写入符号链接安全状态')
    fd, raw = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    temp = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def preserve(root, work, mode):
    canonical = canonical_path(root)
    info = inspect_backend()
    state = {'version': 1, 'root': str(Path(root).resolve()), 'expected': None, 'migrated': False,
             'original_container_id': info['Id'] if info else None}
    if info:
        if mode == 'fresh':
            raise SigningError('fresh 检测到原后台，拒绝覆盖现有安全配置')
        active = active_snapshot(info, root, include_content=True)
        data = active.pop('content')
        state['expected'] = active
        # No replacement is needed for the already-correct canonical layout.
        if active['path'] != CANONICAL:
            previous = _file_bytes(canonical) if canonical.exists() else None
            backup_parent = Path(work) / 'backups'
            backup_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            backup = backup_parent / ('backend-signing-' + time.strftime('%Y%m%d_%H%M%S') + '-' + uuid.uuid4().hex[:8])
            backup.mkdir(mode=0o700)
            _atomic_private(backup / 'active-security.json', data)
            if previous is not None:
                _atomic_private(backup / 'canonical-before.json', previous)
            # Recheck both inputs immediately before the only configuration mutation.
            current = active_snapshot(info, root, include_content=True)
            if current.pop('content') != data or (_file_bytes(canonical) if canonical.exists() else None) != previous:
                raise SigningError('备份后签名配置发生变化，未迁移')
            _atomic_private(canonical, data)
            assert_preserved(active, canonical_snapshot(root), require_same_path=False)
            state.update(migrated=True, backup=str(backup))
    _atomic_private(Path(work)/'backend-signing-state.json', json.dumps(state).encode('utf-8'))
    print('BACKEND_SIGNING_PRESERVE=PASS; ACTIVE_KEYS_LOGGED=NO')


def load_state(root, work):
    state = json.loads(_file_bytes(Path(work)/'backend-signing-state.json'))
    if state.get('version') != 1 or state.get('root') != str(Path(root).resolve()):
        raise SigningError('签名保留状态与所选平台根目录不一致')
    return state


def capture(root, work):
    state = load_state(root, work)
    observed = canonical_snapshot(root)
    if state['expected']:
        assert_preserved(state['expected'], observed, require_same_path=False)
    state['expected'] = observed
    _atomic_private(Path(work)/'backend-signing-state.json', json.dumps(state).encode('utf-8'))
    print('BACKEND_SIGNING_CAPTURE=PASS')


def verify(root, work):
    state = load_state(root, work)
    info = inspect_backend()
    if not info or not state.get('expected'):
        raise SigningError('缺少待验证后台或签名保留基线')
    observed = active_snapshot(info, root)
    if observed['path'] != CANONICAL:
        raise SigningError('新后台未使用统一的持久化签名配置')
    mount = next(m for m in info['Mounts'] if m.get('Destination') == CANONICAL)
    if mount.get('RW'):
        raise SigningError('新后台签名配置必须只读挂载')
    assert_preserved(state['expected'], observed)
    print('BACKEND_SIGNING_VERIFY=PASS; EFFECTIVE_KEYS_PRESERVED=YES')


def guard(root, work):
    """Read-only final check immediately before the old containers are stopped."""
    state = load_state(root, work)
    if not state.get('expected') or 'original_container_id' not in state:
        raise SigningError('缺少签名基线；不能在停服务前重新创建基线')
    assert_preserved(state['expected'], canonical_snapshot(root))
    info = inspect_backend()
    current_id = info['Id'] if info else None
    if current_id != state['original_container_id']:
        raise SigningError('准备期间原后台容器发生变化，未停止服务')
    if info:
        assert_preserved(state['expected'], active_snapshot(info, root), require_same_path=False)
    print('BACKEND_SIGNING_PRESTOP_GUARD=PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preserve', 'capture', 'guard', 'verify'))
    parser.add_argument('--mode', choices=('fresh', 'repair'), default=os.environ.get('MODE', 'repair'))
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() != 0:
        raise SigningError('签名配置保留需要 root')
    root = os.environ.get('PLATFORM_DATA_ROOT', '/data')
    work = os.environ.get('ONECLICK_ROOT', '/root/oneclick')
    if args.action == 'preserve':
        preserve(root, work, args.mode)
    else:
        {'capture': capture, 'guard': guard, 'verify': verify}[args.action](root, work)


if __name__ == '__main__':
    try:
        main()
    except (SigningError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        # Never include subprocess output, JSON content or secret values in logs.
        print('BACKEND_SIGNING=FAIL; 有效签名配置校验或保留失败，未提交容器更新')
        raise SystemExit(1)
