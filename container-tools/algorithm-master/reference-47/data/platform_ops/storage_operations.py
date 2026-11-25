"""Root host alarm-storage operations. No work runs on import.

The caller provides authentication. API: GET /storage, POST /storage/preview,
POST /storage/apply. No historical file is migrated or removed by this module.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import urllib.request
import uuid

DEFAULT_ROOT = '/data/AIGO/python/bingxing_model/results'
CONFIG = '/data/platform_storage/config/alarm-directory.json'
VOLUMES = '/data/platform_storage/alarm-volumes'
PUBLIC_MEDIA = '/data/platform_alarm_media'
STATE = '/data/platform_ops/state'
VERSION = 'alarm-directory-v1'
PUBLIC_ORIGIN = 'https://192.168.110.47:8888'
WRITER_HELPER = '/data/sophon/ModelZoo/YOLO/python/bingxing_model/templates/alarm_directory.py'


class StorageError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def atomic_json(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory = os.open(str(path.parent), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path, fallback=None):
    try:
        with open(path, encoding='utf-8') as handle:
            result = json.load(handle)
        if not isinstance(result, dict):
            raise ValueError('not an object')
        return result
    except FileNotFoundError:
        return fallback
    except (OSError, ValueError) as exc:
        raise StorageError(409, '存储配置无法安全读取：' + type(exc).__name__)


def identity(path):
    info = os.stat(str(path), follow_symlinks=False)
    return [info.st_dev, info.st_ino]


def process_start(pid):
    try:
        # comm can contain spaces and parentheses; starttime is field 22.
        return Path('/proc/%d/stat' % int(pid)).read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, ValueError, IndexError):
        return None


class LinuxDriver:
    def runtime_processes(self):
        matches = {}
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                argv = (entry / 'cmdline').read_bytes().split(b'\0')
                if not argv or not os.path.basename(os.fsdecode(argv[0])).startswith('python'):
                    continue
                if not any(os.fsdecode(arg).endswith('/model_start.py') or arg == b'model_start.py' for arg in argv[1:]):
                    continue
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                matches[int(entry.name)] = {'pid': int(entry.name), 'ppid': int(fields[1]), 'start': fields[19]}
            except (OSError, ValueError, IndexError):
                continue
        return matches

    def census(self):
        matches = self.runtime_processes()
        return [item for item in matches.values() if item['ppid'] in matches]

    def supervisors(self):
        matches = self.runtime_processes()
        return [item for item in matches.values() if item['ppid'] not in matches]

    def run(self, args):
        namespace = os.environ.get('PLATFORM_OPS_HOST_MOUNT_NAMESPACE')
        if namespace and args[0] in ('mount', 'umount', 'findmnt'):
            if namespace != '/proc/1/ns/mnt':
                raise StorageError(409, '宿主机挂载命名空间配置无效')
            # PrivateTmp gives the service a slave mount namespace: new mounts
            # made there cannot propagate upstream to Docker. Mount on the
            # host, then let the existing slave trees receive that change.
            args = ['/usr/bin/nsenter', '--mount=' + namespace, '--root=/proc/1/root', '--wd=/proc/1/root', '--'] + args
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=25)
        return result.stdout.strip()

    def shared(self, path):
        try:
            lines = self.run(['findmnt', '-n', '-M', str(path), '-o', 'PROPAGATION']).splitlines()
            return bool(lines) and all('shared' in line.split(',') for line in lines)
        except (subprocess.SubprocessError, OSError):
            return False

    def mounted(self, path):
        try:
            # findmnt reports the physical target for a validated /data alias.
            # This is only mount-state comparison; path security checks remain
            # in validate_path/restore and continue to reject unsafe symlinks.
            expected = Path(path).resolve()
            return any(Path(target).resolve() == expected for target in
                       self.run(['findmnt', '-n', '-M', str(path), '-o', 'TARGET']).splitlines())
        except (subprocess.SubprocessError, OSError):
            return False

    def mount(self, source, slot):
        self.run(['mount', '--bind', '--', str(source), str(slot)])

    def mirror(self, source, destination):
        self.run(['mount', '--rbind', '--', str(source), str(destination)])
        self.run(['mount', '--make-rslave', str(destination)])

    def unmount(self, slot):
        self.run(['umount', '--', str(slot)])

    def backend_probe(self, slot, expected, config_path):
        info = json.loads(self.run(['docker', 'inspect', 'seal_system']))[0]
        mounts = info.get('Mounts', [])
        volume = next((m for m in mounts if m.get('Source') == VOLUMES and m.get('Destination') == VOLUMES), None)
        config = next((m for m in mounts if m.get('Source') == str(Path(config_path).parent) and m.get('Destination') == str(Path(config_path).parent)), None)
        if not volume or not volume.get('RW') or volume.get('Propagation') not in ('rslave', 'rshared'):
            raise StorageError(409, '后端尚未加载报警存储共享挂载，需要先完成受控安装')
        if not config or config.get('RW'):
            raise StorageError(409, '后端尚未加载只读存储配置目录')
        code = 'import os,json; p=' + repr(str(slot)) + '; s=os.stat(p); print(json.dumps([s.st_dev,s.st_ino]))'
        seen = json.loads(self.run(['docker', 'exec', 'seal_system', 'python', '-B', '-c', code]))
        if seen != expected:
            raise StorageError(409, '目标挂载尚未同步到后端，未切换写入目录')

    def media_probe(self, volume_id, name, expected):
        url = 'http://127.0.0.1:9002/alarm-storage/' + volume_id + '/' + name
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200 or response.read(512) != expected:
                    raise ValueError()
        except Exception:
            raise StorageError(409, '报警媒体访问路由尚未就绪，未切换写入目录')


class StorageManager:
    def __init__(self, config=CONFIG, volumes=VOLUMES, state=STATE, default_root=DEFAULT_ROOT, driver=None, writer_helper=WRITER_HELPER, public_media=PUBLIC_MEDIA):
        self.config, self.volumes, self.state = Path(config), Path(volumes), Path(state)
        self.default_root = str(default_root)
        self.writer_helper = Path(writer_helper)
        self.public_media = Path(public_media)
        self.driver = driver or LinuxDriver()

    def document(self):
        doc = load_json(self.config)
        if doc is None:
            return {'schema': 1, 'version': VERSION, 'public_origin': PUBLIC_ORIGIN, 'active': {'id': 'legacy', 'target': self.default_root, 'root': self.default_root, 'url_path': self.default_root.rstrip('/') + '/'}, 'volumes': [], 'generation': 0}
        if doc.get('schema') != 1 or doc.get('version') != VERSION or not isinstance(doc.get('active'), dict) or not isinstance(doc.get('volumes'), list):
            raise StorageError(409, '报警目录配置格式不受支持')
        return doc

    @staticmethod
    def revision(doc):
        return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def validate_path(self, value, doc, allow_missing=False):
        if not isinstance(value, str) or len(value) > 1024 or not value.startswith('/') or value.startswith('//') or '\\' in value or any(ord(c) < 32 for c in value):
            raise StorageError(400, '请输入安全的 Linux 绝对目录')
        p = Path(value)
        if '..' in p.parts or len(p.parts) < 3 or str(p) != value.rstrip('/'):
            raise StorageError(400, '目录包含非法层级或非规范路径')
        protected = ['/etc', '/bin', '/sbin', '/usr', '/boot', '/proc', '/sys', '/dev', '/run', '/var/log', '/root', '/var/lib/docker', '/var/lib/mysql', '/opt/mysql', '/data/Config_files', '/data/platform_gateway', '/data/sophon', '/data/model_algorithm_package', str(self.volumes), str(self.public_media), str(self.config.parent), str(self.state), '/data/platform_ops']
        for entry in protected:
            protected_path = Path(entry)
            if p == protected_path or protected_path in p.parents or p in protected_path.parents:
                raise StorageError(400, '该目录属于系统或平台运行目录，不能用作报警存储')
        for part in (p, *p.parents):
            if part.is_symlink():
                raise StorageError(400, '报警目录及父目录不能包含软链接')
        registered_targets = [self.default_root, doc['active']['target']] + [v['target'] for v in doc['volumes']]
        for registered in registered_targets:
            old = Path(registered)
            if old != p and (old in p.parents or p in old.parents):
                raise StorageError(409, '目标不能与已登记的报警目录相互嵌套')
        for part in reversed((p, *p.parents)):
            if part.exists() and not part.is_dir():
                raise StorageError(400, '目标目录或父目录已被文件占用')
        if not p.is_dir():
            if not allow_missing:
                raise StorageError(400, '目标目录不存在，请检查目录或磁盘挂载')
            registered = [doc['active']['target']] + [v['target'] for v in doc['volumes']]
            if str(p) in registered:
                raise StorageError(409, '已使用的报警目录缺失，请先检查原磁盘挂载')
        elif p.resolve() != p:
            raise StorageError(400, '目标目录必须为真实目录')
        return p

    @staticmethod
    def rollback_created(created):
        # Remove only our still-empty directories, never recursively remove data.
        for path, expected in reversed(created):
            try:
                if identity(path) == expected:
                    Path(path).rmdir()
            except OSError:
                pass

    def create_target(self, target, doc):
        self.validate_path(str(target), doc, allow_missing=True)
        created = []
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open('/', flags)
        walked = Path('/')
        try:
            for name in Path(target).parts[1:]:
                walked = walked / name
                new = False
                try:
                    child = os.open(name, flags, dir_fd=fd)
                except FileNotFoundError:
                    try:
                        os.mkdir(name, 0o755, dir_fd=fd)
                        new = True
                    except FileExistsError:
                        pass
                    child = os.open(name, flags, dir_fd=fd)
                os.close(fd)
                fd = child
                if new:
                    info = os.fstat(fd)
                    created.append((str(walked), [info.st_dev, info.st_ino]))
                    os.fchmod(fd, 0o755)
                    os.fsync(fd)
            self.validate_path(str(target), doc)
            info = os.fstat(fd)
            if identity(target) != [info.st_dev, info.st_ino]:
                raise StorageError(409, '目标目录在创建期间发生变化')
            return created
        except Exception as exc:
            self.rollback_created(created)
            if isinstance(exc, StorageError):
                raise
            raise StorageError(400, '无法自动创建目标目录：' + type(exc).__name__)
        finally:
            os.close(fd)

    @staticmethod
    def write_probe(directory):
        name = '.platform-alarm-probe-' + uuid.uuid4().hex + '.jpg'
        data = ('alarm-storage-probe:' + uuid.uuid4().hex).encode()
        path = Path(directory) / name
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o644)
            with os.fdopen(fd, 'wb') as handle:
                os.fchmod(handle.fileno(), 0o644)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            return path, data
        except OSError as exc:
            raise StorageError(400, '目标目录不可写：' + type(exc).__name__)

    def preflight(self, body):
        doc = self.document()
        p = self.validate_path(body.get('path'), doc, allow_missing=True)
        missing = []
        ancestor = p
        while not ancestor.exists():
            missing.append(str(ancestor))
            ancestor = ancestor.parent
        before = None if missing else identity(p)
        ancestor_before = identity(ancestor)
        probe, _ = self.write_probe(ancestor)
        probe.unlink()
        self.validate_path(str(p), doc, allow_missing=True)
        if identity(ancestor) != ancestor_before or (not missing and identity(p) != before):
            raise StorageError(409, '目标目录在检查期间发生变化，请重新预检')
        usage = os.statvfs(str(ancestor))
        free = usage.f_bavail * usage.f_frsize
        if free < 256 * 1024 * 1024:
            raise StorageError(400, '目标可用空间不足 256 MiB')
        return {'path': str(p), 'revision': self.revision(doc), 'target_identity': before, 'will_create': bool(missing), 'missing_directories': list(reversed(missing)), 'available_bytes': free, 'same_as_current': str(p) == doc['active']['target'], 'history_policy': '保留所有历史目录与既有文件，不自动迁移或删除', 'shared_mount_ready': self.driver.shared(self.volumes)}

    def runtime_inventory(self):
        """Require every live algorithm process to acknowledge the installed helper."""
        masters = sorted(self.driver.supervisors(), key=lambda item: int(item['pid']))
        workers = sorted(self.driver.census(), key=lambda item: int(item['pid']))
        if not masters:
            raise StorageError(409, '算法运行服务尚未加载统一目录配置')
        try:
            expected_code = hashlib.sha256(self.writer_helper.read_bytes()).hexdigest()
        except OSError:
            raise StorageError(409, '统一目录组件尚未安装')
        missing = []
        for item in masters + workers:
            pid = int(item['pid'])
            current = process_start(pid)
            if current is None:
                continue
            receipt = load_json(self.state / 'writer-receipts' / ('%d.json' % pid), {})
            if (str(item.get('start')) != current or receipt.get('start') != current or receipt.get('version') != VERSION
                    or receipt.get('code_sha256') != expected_code):
                missing.append(pid)
        if missing:
            raise StorageError(409, '仍有运行任务未加载统一目录配置，需受控轮换任务：' + ','.join(map(str, missing)))
        return {'runtime_pids': workers, 'supervisor_pids': masters, 'writer_code_sha256': expected_code}

    def readiness(self):
        ready = load_json(self.state / 'storage-readiness.json', {})
        if ready.get('algorithm_runtime') == 'not_available':
            raise StorageError(409, 'SC7 算法运行包尚未提供，报警目录切换不可用；平台与基础环境可正常使用')
        required = ('inventory_complete', 'media_route_ready', 'shared_mount_ready',
                    'new_child_backend_probe', 'new_child_http_probe')
        if ready.get('schema') != 2 or not all(ready.get(key) is True for key in required):
            raise StorageError(409, '需先完成运行任务清单、媒体路由和共享挂载的受控安装')
        if not self.driver.shared(self.volumes):
            raise StorageError(409, '报警共享挂载未就绪，目录切换不可用')
        inventory = self.runtime_inventory()
        if ready.get('writer_code_sha256') != inventory['writer_code_sha256']:
            raise StorageError(409, '统一目录组件已更新，需要重新完成存储能力验收')
        try:
            media_hash = hashlib.sha256(Path('/opt/nginx/conf/nginx.conf').read_bytes()).hexdigest()
        except OSError:
            raise StorageError(409, '报警媒体路由配置不可读')
        if ready.get('media_config_sha256') != media_hash:
            raise StorageError(409, '媒体路由配置已变化，需要重新完成存储能力验收')
        return dict(ready, **inventory)

    def status(self):
        doc = self.document()
        try:
            readiness = self.readiness()
            ready, reason = True, ''
        except StorageError as exc:
            readiness, ready, reason = {}, False, exc.message
        return {'active': doc['active'], 'history': doc['volumes'], 'revision': self.revision(doc), 'generation': doc['generation'], 'draft': load_json(self.state / 'storage-draft.json', {}).get('path', ''), 'ready': ready, 'readiness_reason': reason, 'readiness': readiness, 'shared_mount_ready': self.driver.shared(self.volumes), 'history_policy': '历史文件保留，原地址继续可读，不自动迁移或删除'}

    @contextlib.contextmanager
    def lock(self):
        import fcntl
        self.state.mkdir(parents=True, exist_ok=True)
        with open(self.state / 'storage.lock', 'a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StorageError(409, '另一项存储操作正在执行，请稍后重试')
            yield

    def apply(self, body):
        with self.lock():
            doc = self.document()
            if body.get('revision') != self.revision(doc):
                raise StorageError(409, '存储配置已经更新，请刷新并重新预检')
            flight = self.preflight(body)
            if flight['same_as_current']:
                return dict(self.status(), changed=False)
            self.readiness()
            if not self.driver.shared(self.volumes):
                raise StorageError(409, '报警共享挂载未就绪，未切换写入目录')
            target = flight['path']
            existing = next((v for v in doc['volumes'] if v['target'] == target), None)
            volume_id = hashlib.sha256(target.encode()).hexdigest()[:20]
            slot = Path(existing['root']) if existing else self.volumes / volume_id
            new_mount = False
            committed = False
            probe = None
            created = []
            updated = None
            try:
                if flight['will_create']:
                    created = self.create_target(target, doc)
                    flight = self.preflight(body)
                volume = existing or {'id': volume_id, 'target': target, 'root': str(slot), 'url_path': '/media/alarm-storage/' + volume_id + '/', 'target_identity': flight['target_identity']}
                slot.mkdir(parents=True, exist_ok=True)
                if slot.is_symlink():
                    raise StorageError(409, '报警挂载目录异常')
                if not self.driver.mounted(slot):
                    if any(slot.iterdir()):
                        raise StorageError(409, '报警挂载目录包含未管理文件，拒绝覆盖')
                    self.driver.mount(target, slot)
                    new_mount = True
                if identity(slot) != flight['target_identity'] or identity(target) != flight['target_identity']:
                    raise StorageError(409, '目标目录或挂载来源发生变化，未切换')
                self.driver.backend_probe(slot, flight['target_identity'], self.config)
                probe, data = self.write_probe(slot)
                self.driver.media_probe(volume['id'], probe.name, data)
                probe.unlink()
                probe = None
                updated = json.loads(json.dumps(doc))
                if not existing:
                    updated['volumes'].append(volume)
                updated['active'] = volume
                updated['generation'] += 1
                updated['applied_at'] = int(time.time())
                atomic_json(self.state / 'storage-before-apply.json', doc, 0o600)
                # Config is the commit point: writers, media URL and retention read one atomic document.
                atomic_json(self.config, updated)
                committed = True
                return dict(self.status(), changed=True, created_directories=[p for p, _ in created])
            except Exception:
                if not committed and updated is not None:
                    # replace() can commit before its directory fsync raises.
                    # Preserve the destination whenever config points to it.
                    try:
                        committed = self.revision(self.document()) == self.revision(updated)
                    except Exception:
                        committed = True  # Unknown commit state: preserve mounts and data.
                if probe is not None:
                    try:
                        probe.unlink()
                    except OSError:
                        pass
                if new_mount and not committed:
                    self.driver.unmount(slot)
                    slot.rmdir()
                if not committed:
                    self.rollback_created(created)
                raise

    def restore(self):
        """Boot-only restore. Caller runs before backend/tasks; never switches config."""
        doc = self.document()
        self.volumes.mkdir(parents=True, exist_ok=True)
        if not self.driver.mounted(self.volumes):
            self.driver.mount(self.volumes, self.volumes)
        if not self.driver.shared(self.volumes):
            self.driver.run(['mount', '--make-rshared', str(self.volumes)])
        # Nginx must traverse a dedicated public tree: platform_storage is intentionally private.
        public = self.public_media
        if (not public.is_absolute() or public == self.volumes or public in self.volumes.parents
                or self.volumes in public.parents or len(public.parts) < 3):
            raise StorageError(409, '公共媒体映射目录配置无效')
        for parent in (public, *public.parents):
            if parent.is_symlink():
                raise StorageError(409, '公共媒体映射目录不能包含软链接')
        public.mkdir(parents=True, exist_ok=True)
        if not self.driver.mounted(public):
            if any(public.iterdir()):
                raise StorageError(409, '公共媒体映射目录包含未管理文件')
            try:
                self.driver.mirror(self.volumes, public)
            except Exception:
                # A partial rbind must not leave a peer that can propagate changes upstream.
                if self.driver.mounted(public):
                    self.driver.unmount(public)
                raise
        else:
            if identity(public) != identity(self.volumes):
                raise StorageError(409, '公共媒体映射来源不一致')
            self.driver.run(['mount', '--make-rslave', str(public)])
        os.chmod(str(public), 0o755)
        for volume in doc['volumes']:
            target = self.validate_path(volume['target'], doc)
            if identity(target) != volume.get('target_identity'):
                raise StorageError(409, '历史报警目标已更换或其磁盘未挂载')
            slot = Path(volume['root'])
            if slot.parent != self.volumes or slot.name != volume['id']:
                raise StorageError(409, '历史挂载清单无效')
            slot.mkdir(exist_ok=True)
            if not self.driver.mounted(slot):
                if any(slot.iterdir()):
                    raise StorageError(409, '历史挂载目录存在未管理文件')
                self.driver.mount(target, slot)
            if identity(slot) != identity(target):
                raise StorageError(409, '历史报警挂载来源不一致')
        return {'restored': len(doc['volumes']), 'active': doc['active'], 'public_media_root': str(public)}

    def dispatch(self, method, path, body=None):
        body = body or {}
        try:
            if method == 'GET' and path.rstrip('/') == '/storage':
                data = self.status()
            elif method == 'POST' and path == '/storage/preview':
                data = self.preflight(body)
            elif method == 'POST' and path == '/storage/draft':
                self.preflight(body)
                atomic_json(self.state / 'storage-draft.json', {'path': body['path']}, 0o600)
                data = self.status()
            elif method == 'POST' and path == '/storage/apply':
                data = self.apply(body)
            else:
                raise StorageError(404, '存储操作不存在')
            return 200, {'code': 200, 'msg': '操作成功', 'data': data}
        except StorageError as exc:
            return exc.code, {'code': exc.code, 'msg': exc.message}
        except Exception as exc:
            return 500, {'code': 500, 'msg': '存储操作未完成：' + type(exc).__name__}


def dispatch(method, path, body=None):
    return StorageManager().dispatch(method, path, body)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['restore']:
        raise SystemExit('usage: storage_operations.py restore')
    print(json.dumps(StorageManager().restore(), ensure_ascii=False))
