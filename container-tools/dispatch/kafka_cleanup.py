"""Preserve the exact platform Kafka installation before removing its real tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import uuid

INSTALL = Path('/usr/local/kafka_2.12-3.6.2')
ALIAS = Path('/usr/local/kafka')
BULK_STATE = Path('/etc/oneclick/bulk-storage.json')
UNIT = Path('/etc/systemd/system/kafka.service')
FINGERPRINTS = {
    'bin/kafka-server-start.sh': '634c886ff0995e1d0ffd300b9a9be9d67e28b6aac8919808f4ac10b404395708',
    'bin/kafka-run-class.sh': '91aac9f521eaff0e9d931f59e031ca83c7b6d4853dced592b14e56eb53355575',
    'libs/kafka_2.12-3.6.2.jar': 'd864e706cd3faa6299b41c6edca600b770d6de5faab65cd98deb58bd538c660d',
    'libs/kafka-clients-3.6.2.jar': '03a06da18a391f480910e590aa580f9ddc392e3eacca0d28553adc0968bb351f',
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def mounts():
    return {Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), line.split()[4]))
            for line in Path('/proc/self/mountinfo').read_text().splitlines()}


def regular_chain(path):
    for part in reversed((path,) + tuple(path.parents)):
        if part.is_symlink():
            raise ValueError('Kafka 路径含符号链接，未归档或清理：' + str(part))


def service_owned(install, alias):
    # Check installed unit/drop-ins before clean stops or removes the service.
    paths = [UNIT] + sorted(UNIT.with_name(UNIT.name + '.d').glob('*.conf'))
    allowed_commands = {str(root / 'bin/kafka-server-start.sh') for root in (install, alias)}
    allowed_configs = {str(root / 'config/kraft/server.properties') for root in (install, alias)}
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        regular_chain(path)
        for line in path.read_text().splitlines():
            if line.strip().startswith('ExecStart='):
                value = line.strip().split('=', 1)[1].strip()
                if not value:
                    continue
                args = shlex.split(value)
                if len(args) != 2 or args[0] not in allowed_commands or args[1] not in allowed_configs:
                    raise ValueError('kafka.service 启动配置属于其他实例，未停止或清洗')


def preflight(data_root, install=INSTALL, alias=ALIAS, allow_bulk_logs=False):
    install, alias = Path(install), Path(alias)
    regular_chain(install)
    service_owned(install, alias)
    if alias.is_symlink():
        if alias.resolve() != install:
            raise ValueError('Kafka 别名指向其他实例，未清洗：' + str(alias))
    elif alias.exists():
        raise ValueError('Kafka 别名是实际目录，归属不明确，未清洗：' + str(alias))
    if not install.exists():
        return False
    if not install.is_dir():
        raise ValueError('Kafka 版本路径不是目录')
    managed_logs = False
    for mount in mounts():
        if mount == install or install in mount.parents:
            permitted = False
            if allow_bulk_logs and mount == install / 'logs':
                state = BULK_STATE
                if state.is_file() and not state.is_symlink():
                    for item in json.loads(state.read_text()).get('mappings', []):
                        source = Path(item.get('source', '/nonexistent'))
                        if item.get('target') == str(mount) and source.is_dir() and source.samefile(mount):
                            permitted = True
                            managed_logs = True
            if not permitted:
                raise ValueError('Kafka 目录存在未解除的挂载，停止清洗：' + str(mount))
    # bulk prepare creates only this empty mountpoint before Kafka is unpacked.
    # Permit cleanup of that incomplete installation, but never adopt unknown files.
    children = list(install.iterdir())
    if not children or (len(children) == 1 and children[0].name == 'logs'
                        and children[0].is_dir() and not children[0].is_symlink()
                        and (managed_logs or not any(children[0].iterdir()))):
        return True
    for relative, expected in FINGERPRINTS.items():
        path = install / relative
        regular_chain(path)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Kafka 文件不匹配当前发布版本，未接管：' + str(path))
    config = install / 'config/kraft/server.properties'
    regular_chain(config)
    values = re.findall(r'^\s*log\.dirs\s*=\s*(.*?)\s*$', config.read_text(), re.M)
    expected = Path(data_root).resolve() / 'kafka/kraft-combined-logs'
    if len(values) != 1 or Path(values[0]).resolve() != expected.resolve():
        raise ValueError('Kafka KRaft 数据目录不属于所选平台，未清洗')
    return True


def assert_idle(install):
    """No stop/kill action: refuse live Kafka or open handles in this exact tree."""
    if shutil.which('systemctl'):
        result = subprocess.run(['systemctl', 'is-active', 'kafka'], capture_output=True, text=True)
        if result.stdout.strip() in ('active', 'activating', 'deactivating', 'reloading'):
            raise ValueError('Kafka 服务仍在运行，未归档或删除')
    own = os.getpid()
    prefix = str(install) + '/'
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == own:
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            if any(arg == b'kafka.Kafka' or arg.endswith(b'/kafka-server-start.sh') for arg in argv):
                raise ValueError('检测到 Kafka 进程，未归档或删除')
            handles = [proc / 'cwd', proc / 'exe'] + list((proc / 'fd').iterdir())
            for handle in handles:
                try:
                    target = os.readlink(str(handle))
                    if target.endswith(' (deleted)'):
                        target = target[:-10]
                except FileNotFoundError:
                    continue
                if target == str(install) or target.startswith(prefix):
                    raise ValueError('Kafka 目录仍被进程占用，未归档或删除')
        except (FileNotFoundError, ProcessLookupError):
            continue


def inventory(root):
    result = {}
    for path in sorted([root] + list(root.rglob('*'))):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('Kafka 树内存在链接或特殊文件，未清理：' + str(path))
        result[path.relative_to(root).as_posix()] = {
            'kind': 'dir' if path.is_dir() else 'file', 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'size': info.st_size if path.is_file() else 0,
            'mtime_ns': info.st_mtime_ns,
            'sha256': digest(path) if path.is_file() else '',
        }
    return result


def verify_archive(path, expected, top):
    found = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            if member.name == top:
                relative = '.'
            elif member.name.startswith(top + '/'):
                relative = member.name[len(top) + 1:]
            else:
                raise ValueError('Kafka 归档条目越界')
            if relative not in expected or relative in found:
                raise ValueError('Kafka 归档条目不匹配')
            record = expected[relative]
            if member.mode != record['mode'] or member.uid != record['uid'] or member.gid != record['gid']:
                raise ValueError('Kafka 归档权限/归属校验失败')
            if record['kind'] == 'dir':
                if not member.isdir():
                    raise ValueError('Kafka 归档目录类型校验失败')
            else:
                if not (member.isfile() or member.islnk()):
                    raise ValueError('Kafka 归档文件类型校验失败')
                h = hashlib.sha256()
                length = 0
                with archive.extractfile(member) as source:
                    for block in iter(lambda: source.read(1048576), b''):
                        h.update(block)
                        length += len(block)
                if h.hexdigest() != record['sha256'] or length != record['size']:
                    raise ValueError('Kafka 归档文件内容校验失败')
            found[relative] = True
    if set(found) != set(expected):
        raise ValueError('Kafka 归档缺少条目')


def remove_verified(root, records):
    # Do not use rmtree: every removed file must still match the verified snapshot.
    for relative, record in records.items():
        if record['kind'] != 'file':
            continue
        path = root / relative
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_size != record['size'] or
                info.st_mtime_ns != record['mtime_ns'] or digest(path) != record['sha256']):
            raise ValueError('Kafka 文件在归档后变化，停止清理：' + str(path))
        path.unlink()
    for relative in sorted((r for r, v in records.items() if v['kind'] == 'dir'),
                           key=lambda value: len(Path(value).parts), reverse=True):
        (root / relative).rmdir()  # An unexpected new entry stops removal.


def restore_missing(archive_path, root, records, top):
    """Undo partial removal; preserve changed/new files instead of overwriting them."""
    with tarfile.open(archive_path, 'r:gz') as archive:
        for relative, record in records.items():
            path = root / relative
            if record['kind'] == 'dir':
                path.mkdir(parents=True, exist_ok=True)
            elif not path.exists() and not path.is_symlink():
                path.parent.mkdir(parents=True, exist_ok=True)
                member = archive.getmember(top + '/' + relative)
                with archive.extractfile(member) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                os.chmod(path, record['mode'])
                if hasattr(os, 'chown'):
                    os.chown(path, record['uid'], record['gid'])
                os.utime(path, ns=(record['mtime_ns'], record['mtime_ns']))
        for relative, record in records.items():
            if record['kind'] == 'dir':
                path = root / relative
                os.chmod(path, record['mode'])
                if hasattr(os, 'chown'):
                    os.chown(path, record['uid'], record['gid'])


def archive_installation(data_root, backup_dir, install=INSTALL, alias=ALIAS):
    install, alias, backup = Path(install), Path(alias), Path(backup_dir)
    if not preflight(data_root, install, alias):
        return {'result': 'ABSENT'}
    regular_chain(backup)
    backup = backup.resolve()
    if backup == install or install in backup.parents:
        raise ValueError('Kafka 备份目录不能放在其安装目录内')
    assert_idle(install)
    before = inventory(install)
    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime('%Y%m%d_%H%M%S') + '-' + uuid.uuid4().hex[:8]
    destination = backup / (install.name + '-' + stamp + '.tar.gz')
    quarantine = install.with_name('.oneclick-kafka-preserve-' + stamp)
    install.rename(quarantine)  # Same-parent atomic isolation, even if backup is another disk.
    verified = False
    try:
        assert_idle(quarantine)
        with destination.open('xb') as output:
            os.chmod(destination, 0o600)
            with tarfile.open(fileobj=output, mode='w:gz', format=tarfile.PAX_FORMAT) as archive:
                archive.add(quarantine, arcname=install.name, recursive=True)
            output.flush()
            os.fsync(output.fileno())
        verify_archive(destination, before, install.name)
        verified = True
        if inventory(quarantine) != before:
            raise ValueError('Kafka 内容在备份期间变化，保留原目录并停止')
        assert_idle(quarantine)
        remove_verified(quarantine, before)
    except Exception:
        if verified:
            restore_missing(destination, quarantine, before, install.name)
        if quarantine.exists() and not install.exists():
            quarantine.rename(install)
        raise
    report = {'result': 'PASS', 'archive': str(destination), 'sha256': digest(destination),
              'files': sum(v['kind'] == 'file' for v in before.values()),
              'bytes': sum(v['size'] for v in before.values()), 'original_removed': not install.exists()}
    destination.with_suffix(destination.suffix + '.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'archive', 'verify'))
    parser.add_argument('--data-root', default=os.environ.get('PLATFORM_DATA_ROOT', '/data'))
    parser.add_argument('--backup-dir')
    parser.add_argument('--allow-bulk-logs', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'preflight':
            present = preflight(args.data_root, allow_bulk_logs=args.allow_bulk_logs)
            print('KAFKA_CLEAN_PREFLIGHT=PASS ' + ('PRESENT' if present else 'ABSENT'))
        elif args.action == 'archive':
            if not args.backup_dir:
                parser.error('archive requires --backup-dir')
            print(json.dumps(archive_installation(args.data_root, args.backup_dir), ensure_ascii=False))
        else:
            if INSTALL.exists() or INSTALL.is_symlink():
                raise ValueError('Kafka 真实版本目录仍存在：' + str(INSTALL))
            print('KAFKA_REAL_DIRECTORY_CLEAN=PASS')
        return 0
    except Exception as exc:
        print('Kafka 保全清理失败：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
