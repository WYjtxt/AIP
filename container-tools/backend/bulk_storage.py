"""Optional bulk storage for platform logs, media, backups and temporary files.

Configuration paths remain stable through bind mounts. Never migrate populated
directories online, move databases/Docker storage, or delete bulk files on clean.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys

STATE = Path('/etc/oneclick/bulk-storage.json')
LIBRARY = Path('/usr/local/lib/oneclick/bulk_storage.py')
UNIT_DIR = Path('/etc/systemd/system')
SERVICE = 'oneclick-bulk-storage.service'
SERVICES = ('mysqld', 'redis', 'kafka', 'nginx', 'config-dispatch',
            'config-dispatch-gateway', 'platform-ops', 'platform-push-worker',
            'platform-alarm-storage', 'platform-host-disks', 'kafka_consumer',
            'model_start', 'resource')


def normalize_bulk_root(value):
    if not value:
        return ''
    if not isinstance(value, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value):
        raise ValueError('大型文件目录须为 Linux 绝对路径，只使用字母、数字、下划线、横线和 /，例如 /home/logs')
    if '..' in PurePosixPath(value).parts:
        raise ValueError('大型文件目录不能包含上级目录跳转')
    value = str(PurePosixPath(value))
    if value in ('/', '/home', '/data', '/srv', '/mnt', '/media', '/opt', '/var') or any(
            value == p or value.startswith(p + '/') for p in
            ('/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot', '/proc',
             '/sys', '/dev', '/run', '/tmp', '/root', '/var/lib', '/var/log')):
        raise ValueError('请选择专用的大容量目录，例如 /home/logs，不能使用系统目录：' + value)
    return value


def overlap(a, b):
    a, b = PurePosixPath(a), PurePosixPath(b)
    return a == b or a in b.parents or b in a.parents


def validate_selection(data_root, storage_root):
    storage_root = normalize_bulk_root(storage_root)
    if storage_root and overlap(data_root, storage_root):
        raise ValueError('大型文件目录与平台配置根目录须分别设置，不能相同或相互包含')
    return storage_root


def no_links(path):
    path = Path(path)
    for part in reversed((path,) + tuple(path.parents)):
        if part.is_symlink():
            raise ValueError('大型文件目录链中不能包含符号链接：' + str(part))
        if part.exists() and not part.is_dir():
            raise ValueError('预期为目录：' + str(part))


def run(argv, check=True):
    return subprocess.run(list(map(str, argv)), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=check)


def filesystem(path):
    path = Path(path)
    while not path.exists():
        path = path.parent
    result = run(['findmnt', '-J', '-T', path, '-o', 'TARGET,SOURCE,FSTYPE,UUID,OPTIONS'])
    entry = json.loads(result.stdout)['filesystems'][0]
    if 'ro' in entry['options'].split(','):
        raise ValueError('大型文件所在文件系统是只读的')
    return {key: entry.get(key) or '' for key in ('target', 'source', 'fstype', 'uuid')}


def mounted_targets():
    # os.path.ismount cannot detect bind mounts on the same filesystem.
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), value)
    return {unescape(line.split()[4]) for line in Path('/proc/self/mountinfo').read_text().splitlines()}


def is_mounted(path):
    return str(Path(path).absolute()) in mounted_targets()


def same_filesystem(current, saved):
    keys = ('target', 'fstype', 'uuid') if saved.get('uuid') else ('target', 'fstype', 'source')
    return all(current.get(key) == saved.get(key) for key in keys)


def make_plan(data_root, storage_root, oneclick_root):
    data, base = PurePosixPath(data_root), PurePosixPath(storage_root) / 'ai-platform'
    pairs = [
        (data / 'config_dispatch/backups', 'backups/dispatch'),
        (data / 'config_dispatch/security-backups', 'backups/dispatch-security'),
        (data / 'config_dispatch/gateway/logs', 'logs/dispatch-gateway'),
        (data / 'config_dispatch/gateway/temp', 'tmp/dispatch-gateway'),
        (data / 'config_dispatch/temp', 'tmp/dispatch'),
        (data / 'platform_ops/backups', 'backups/platform-upgrades'),
        (data / 'platform_ops/tmp', 'tmp/platform-ops'),
        (data / 'platform_algorithm_start/log', 'logs/algorithm'),
        (data / 'platform_algorithm_start/logs', 'logs/algorithm-extra'),
        (data / 'model_algorithm_package/log', 'logs/algorithm-packages'),
        (data / 'platform_algorithm_start/tmp', 'tmp/algorithm'),
        (data / 'model_algorithm_package/tmp', 'tmp/algorithm-packages'),
        (PurePosixPath('/home/AIGO/python/bingxing_model/results'), 'media/results'),
        (PurePosixPath('/opt/nginx/logs'), 'logs/nginx-host'),
        (PurePosixPath('/usr/local/kafka_2.12-3.6.2/logs'), 'logs/kafka'),
        (PurePosixPath(oneclick_root) / 'backups', 'backups/deployment'),
    ]
    pairs += [(PurePosixPath('/opt/nginx') / (name + '_temp'), 'tmp/nginx-host/' + name)
              for name in ('client_body', 'proxy', 'fastcgi', 'uwsgi', 'scgi')]
    # Algorithm upgrades clone and atomically exchange their code directory.
    # Links survive that exchange; nested bind mounts would move with the old
    # tree and make cp -al fail across filesystems. Configuration/backup paths
    # retain real directories because 8899 deliberately rejects symlinks.
    return [{'source': str(base / relative), 'target': str(target),
             'kind': 'link' if any(p in target.parents for p in
                                  (data / 'platform_algorithm_start', data / 'model_algorithm_package')) else 'bind'}
            for target, relative in pairs]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.new')
    with temporary.open('w', encoding='utf-8') as output:
        os.chmod(str(temporary), 0o600)
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def public_directory(path):
    """Create traversable parents without changing existing shared directories."""
    path = Path(path)
    if not path.exists():
        public_directory(path.parent)
        path.mkdir(mode=0o755)
        os.chmod(str(path), 0o755)


def unit_token(value):
    return str(value).replace('%', '%%').replace('\\', '\\x5c').replace(' ', '\\x20').replace('"', '\\x22').replace("'", '\\x27')


def load_state():
    if not STATE.exists():
        return None
    if STATE.is_symlink():
        raise ValueError('大型文件状态不能是符号链接')
    state = json.loads(STATE.read_text(encoding='utf-8'))
    validate_selection(state['data_root'], state['storage_root'])
    if state.get('schema') != 1 or state['mappings'] != make_plan(
            state['data_root'], state['storage_root'], state['oneclick_root']):
        raise ValueError('大型文件目录状态不完整，停止操作')
    return state


class Storage:
    def __init__(self, data_root, requested='', mode='repair', oneclick_root='/root/oneclick'):
        self.data_root = str(Path(data_root).resolve())
        self.oneclick_root = str(Path(oneclick_root).resolve())
        self.mode = mode
        self.state = load_state()
        self.root = validate_selection(self.data_root, requested or (
            self.state['storage_root'] if self.state else ''))
        self.base = Path(self.root) / 'ai-platform' if self.root else None
        if self.state and (self.state['data_root'] != self.data_root or
                           self.state['oneclick_root'] != self.oneclick_root or
                           self.root != self.state['storage_root']):
            raise ValueError('服务器已登记大型文件目录 ' + self.state['storage_root'] +
                             '；请保持原设置。更换磁盘需单独停机迁移，未移动或删除数据')
        self.items = make_plan(self.data_root, self.root, self.oneclick_root) if self.root else []

    def preflight(self):
        if not self.root:
            return
        no_links(self.root)
        no_links(self.base)
        for path in [Path(self.root)] + list(Path(self.root).parents):
            if path.exists() and not path.stat().st_mode & 0o001:
                raise ValueError('服务用户无法穿过大型文件目录父级，请选择可访问的专用目录：' + str(path))
        for item in self.items:
            if overlap(item['source'], item['target']):
                raise ValueError('大型文件与原路径不能相互嵌套')
        fs = filesystem(self.root)
        if self.state:
            if not same_filesystem(fs, self.state['filesystem']):
                raise ValueError('大型文件磁盘挂载与登记信息不一致；停止以免写入系统盘')
            self.check_marker()
        else:
            if self.mode not in ('fresh', 'repair'):
                raise ValueError('该服务器尚未配置大型文件目录，请在 fresh/repair 安装时设置')
            if self.base.exists() and any(self.base.iterdir()):
                raise ValueError('指定目录已有 ai-platform 数据，未覆盖或接管：' + str(self.base))
            # Preflight every source before creating any mount. Existing data
            # needs a separately planned offline migration, never a hidden copy.
            for item in self.items:
                target = Path(item['target'])
                no_links(target)
                if target.exists() and any(target.iterdir()):
                    raise ValueError('原目录已有文件，未迁移或覆盖：' + str(target) +
                                     '；请保留原存放设置，现有数据需单独停机迁移')
                if is_mounted(target):
                    raise ValueError('原目录已挂载其他存储：' + str(target))
            if shutil.disk_usage(next(p for p in [Path(self.root)] + list(Path(self.root).parents)
                                      if p.exists())).free < 1024 ** 3:
                raise ValueError('大型文件所在分区可用空间不足 1 GiB')

    def check_marker(self):
        path = self.base / '.oneclick-owner.json'
        if path.is_symlink() or not path.is_file():
            raise ValueError('大型文件目录标记丢失，拒绝写入或清理')
        owner = json.loads(path.read_text(encoding='utf-8'))
        if owner != {'data_root': self.data_root, 'storage_root': self.root}:
            raise ValueError('大型文件目录属于其他平台，未操作')

    def env(self):
        if not self.root:
            return {}
        return {'PLATFORM_BULK_ROOT': self.root, 'PLATFORM_BULK_BASE': str(self.base),
                'ONECLICK_LOG_ROOT': str(self.base / 'logs/deployment'),
                'ONECLICK_BACKUP_ROOT': str(self.base / 'backups/deployment')}

    def container_binds(self, name):
        if not self.root:
            return []
        layouts = {
            'seal_system': [('logs/backend', '/Seal_system/logs'), ('logs/backend-nginx', '/var/log/nginx'), ('tmp/backend', '/tmp')],
            'seal_system_vue': [('logs/frontend', '/var/log/nginx'), ('tmp/frontend', '/tmp')],
            'zlk': [('logs/zlk', '/opt/media/bin/log'), ('tmp/zlk', '/tmp')],
        }
        return [str(self.base / folder) + ':' + destination for folder, destination in layouts[name]]

    def prepare(self):
        self.preflight()
        if not self.root:
            return
        if not self.state:
            for service in SERVICES:
                if run(['systemctl', 'is-active', '--quiet', service], check=False).returncode == 0:
                    raise ValueError('平台服务正在运行，不能首次切换大型文件目录：' + service)
            # Platform containers may run even with missing systemd units.
            if shutil.which('docker'):
                for name in ('seal_system', 'seal_system_vue', 'zlk'):
                    result = run(['docker', 'inspect', '-f', '{{.State.Running}}', name], check=False)
                    if result.returncode == 0 and result.stdout.strip() == 'true':
                        raise ValueError('平台容器正在运行，不能切换大型文件目录：' + name)
            public_directory(self.base)
            # The supplied parent can already contain unrelated logs. Only this
            # owned namespace is managed; never chmod or clean the parent tree.
            os.chmod(str(self.base), 0o755)
            write_json(self.base / '.oneclick-owner.json',
                       {'data_root': self.data_root, 'storage_root': self.root})
            self.state = {'schema': 1, 'data_root': self.data_root, 'storage_root': self.root,
                          'oneclick_root': self.oneclick_root, 'filesystem': filesystem(self.root),
                          'mappings': self.items, 'active': True}
            write_json(STATE, self.state)  # Recovery intent is durable before mounts.
        for relative in ('logs/deployment', 'logs/services', 'logs/mysql', 'logs/backend',
                         'logs/backend-nginx', 'logs/frontend', 'logs/zlk',
                         'backups/clean', 'tmp/backend', 'tmp/frontend', 'tmp/zlk'):
            path = self.base / relative
            no_links(path)
            public_directory(path)
            if relative.startswith('tmp/'):
                os.chmod(str(path), 0o1777)
        self.restore()
        self.install_service()

    def restore(self):
        self.preflight()
        if not self.root:
            return
        mounted = []
        try:
            for item in self.items:
                source, target = Path(item['source']), Path(item['target'])
                no_links(source)
                no_links(target.parent if item.get('kind') == 'link' else target)
                public_directory(source)
                if item.get('kind') == 'link':
                    if target.is_symlink():
                        if target.resolve() != source:
                            raise ValueError('算法输出链接指向其他目录：' + str(target))
                        continue
                    if target.exists():
                        if not target.is_dir() or any(target.iterdir()):
                            raise ValueError('算法输出目录已有文件，未替换：' + str(target))
                        target.rmdir()
                    public_directory(target.parent)
                    target.symlink_to(source, target_is_directory=True)
                    continue
                public_directory(target)
                if is_mounted(target):
                    if not source.samefile(target):
                        raise ValueError('目录已被其他存储占用：' + str(target))
                    continue
                if any(target.iterdir()):
                    raise ValueError('原目录出现未迁移文件，停止挂载：' + str(target))
                run(['mount', '--bind', source, target])
                mounted.append(target)
                if not source.samefile(target):
                    raise ValueError('大型文件目录映射验证失败：' + str(target))
        except Exception:
            for target in reversed(mounted):
                run(['umount', target], check=False)
            raise
        self.state['active'] = True
        write_json(STATE, self.state)

    def verify(self):
        self.preflight()
        if not self.root:
            return
        for item in self.items:
            source, target = Path(item['source']), Path(item['target'])
            no_links(source)
            if item.get('kind') == 'link':
                no_links(target.parent)
                if not target.is_symlink() or target.resolve() != source or not source.is_dir():
                    raise ValueError('算法输出目录链接失效：' + str(target))
                continue
            no_links(target)
            if not is_mounted(target) or not source.exists() or not source.samefile(target):
                raise ValueError('大型文件目录未正确挂载：' + str(target))

    def detach(self):
        self.preflight()
        if not self.root:
            return
        # Inspect all mounts first; an unexpected one is never unmounted.
        for item in self.items:
            target, source = Path(item['target']), Path(item['source'])
            no_links(source)
            if item.get('kind') == 'link':
                no_links(target.parent)
                if target.is_symlink() and target.resolve() != source:
                    raise ValueError('算法输出链接不匹配，停止清洗：' + str(target))
                if target.exists() and not target.is_symlink() and (not target.is_dir() or any(target.iterdir())):
                    raise ValueError('算法输出目录出现原地数据，停止清洗：' + str(target))
                continue
            no_links(target)
            if any(target in Path(mount).parents for mount in mounted_targets()):
                raise ValueError('目录内部存在额外挂载，停止清洗：' + str(target))
            if is_mounted(target) and (not source.exists() or not source.samefile(target)):
                raise ValueError('清洗前发现不同的挂载，停止：' + str(target))
        for item in reversed(self.items):
            target = Path(item['target'])
            if item.get('kind') == 'link':
                if target.is_symlink():
                    target.unlink()
                continue
            if is_mounted(target):
                run(['umount', target])  # No lazy/forced unmount; busy data must stop clean.
        run(['systemctl', 'disable', '--now', SERVICE], check=False)
        for name in SERVICES + ('docker',):
            path = UNIT_DIR / (name + '.service.d/oneclick-bulk.conf')
            if path.exists():
                path.unlink()
        (UNIT_DIR / SERVICE).unlink(missing_ok=True)
        self.state['active'] = False
        write_json(STATE, self.state)
        run(['systemctl', 'daemon-reload'])
        print('大型文件、历史媒体和备份已保留：' + str(self.base))

    def install_service(self):
        LIBRARY.parent.mkdir(parents=True, exist_ok=True)
        if Path(__file__).resolve() != LIBRARY.resolve():
            shutil.copyfile(__file__, LIBRARY)
        os.chmod(str(LIBRARY), 0o644)
        unit = ('[Unit]\nDescription=Restore platform bulk storage\nAfter=local-fs.target\n'
                'Before=docker.service\nRequiresMountsFor=' + self.root + '\n'
                '[Service]\nType=oneshot\nExecStart=/usr/bin/python3 ' + str(LIBRARY) +
                ' restore\nRemainAfterExit=yes\n[Install]\nWantedBy=multi-user.target\n')
        (UNIT_DIR / SERVICE).write_text(unit, encoding='utf-8')
        for name in SERVICES + ('docker',):
            text = '[Unit]\nRequires=' + SERVICE + '\nAfter=' + SERVICE + '\n'
            if name != 'docker':
                text += '[Service]\nStandardOutput=append:' + str(self.base / ('logs/services/' + name + '.log'))
                text += '\nStandardError=inherit\n'
            temp_folders = {'config-dispatch': 'config_dispatch/temp', 'platform-ops': 'platform_ops/tmp',
                            'model_start': 'platform_algorithm_start/tmp',
                            'kafka_consumer': 'model_algorithm_package/tmp', 'resource': 'model_algorithm_package/tmp'}
            if name in temp_folders:
                folder = temp_folders[name]
                temp = str(Path(self.data_root) / folder)
                text += 'Environment=TMPDIR=' + unit_token(temp) + '\nReadWritePaths=' + unit_token(temp) + '\n'
            path = UNIT_DIR / (name + '.service.d/oneclick-bulk.conf')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'enable', SERVICE])
        # Mark the already established mounts active before dependencies start.
        run(['systemctl', 'start', SERVICE])

    def configure(self):
        if not self.root:
            return
        self.verify()
        import pwd
        for folder, user in (('logs/mysql', 'mysql'), ('backups/dispatch', 'cfgdispatch'),
                             ('backups/dispatch-security', 'cfgdispatch'), ('tmp/dispatch', 'cfgdispatch'),
                             ('tmp/dispatch-gateway', 'cfgdispatch-proxy')):
            account = pwd.getpwnam(user)
            path = self.base / folder
            os.chown(str(path), account.pw_uid, account.pw_gid)
            os.chmod(str(path), 0o700 if folder != 'logs/mysql' else 0o750)
        config = Path('/etc/my.cnf')
        text = config.read_text(encoding='utf-8')
        line = 'log-error=' + str(self.base / 'logs/mysql/error.log')
        if re.search(r'^\s*log-error\s*=', text, re.M):
            text = re.sub(r'^\s*log-error\s*=.*$', lambda match: line, text, flags=re.M)
        else:
            text += '\n[mysqld]\n' + line + '\n'
        config.write_text(text, encoding='utf-8')
        # Existing timer invokes logrotate. Application/Docker limits remain
        # independently enabled; media and backups are never log-rotated.
        Path('/etc/logrotate.d').mkdir(exist_ok=True)
        Path('/etc/logrotate.d/oneclick-bulk').write_text(
            str(self.base / 'logs/*/*.log') + ' {\n daily\n maxsize 20M\n rotate 5\n'
            ' compress\n delaycompress\n missingok\n notifempty\n copytruncate\n su root root\n}\n',
            encoding='utf-8')


def from_env(mode=None):
    return Storage(os.environ.get('PLATFORM_DATA_ROOT', '/data'),
                   os.environ.get('PLATFORM_BULK_ROOT', ''), mode or os.environ.get('MODE', 'repair'),
                   os.environ.get('ONECLICK_ROOT', '/root/oneclick'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'prepare', 'restore', 'verify', 'detach', 'configure'))
    parser.add_argument('--shell-env', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'restore':
            state = load_state()
            if not state:
                raise ValueError('大型文件目录登记丢失，拒绝在系统盘创建替代数据')
            storage = Storage(state['data_root'], state['storage_root'], oneclick_root=state['oneclick_root'])
        else:
            storage = from_env()
        getattr(storage, args.action)()
        if args.action == 'preflight' and storage.mode in ('platform', 'clean', 'verify') and storage.state and storage.state['active']:
            storage.verify()
        if args.shell_env:
            for key, value in storage.env().items():
                print('export ' + key + '=' + shlex.quote(value))
        elif storage.root:
            print('BULK_STORAGE_' + args.action.upper() + '=PASS ' + str(storage.base))
        else:
            print('BULK_STORAGE=UNCHANGED')
    except Exception as exc:
        print('大型文件目录：' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
