#!/usr/bin/env python3
"""Install missing 8899 service units against restored original site state.

Preparation is read-only. Application never replaces configuration, certificates
or account database bytes. Only service identities, missing units and narrowly
scoped filesystem permissions are prepared, with metadata/ACL rollback.
"""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile


SERVICES = ('config-dispatch', 'config-dispatch-gateway')
USERS = ('cfgdispatch', 'cfgdispatch-proxy')
UNIT_DIRECTORY = Path('/etc/systemd/system')


def _run(args, check=True, data=None):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True,
                            timeout=60)
    if check and result.returncode:
        # Nginx configuration and external tool output can contain secrets.
        raise RuntimeError('%s 执行失败（退出码 %s）' % (args[0], result.returncode))
    return result


def _user(name):
    import pwd
    try:
        return pwd.getpwnam(name)
    except KeyError:
        return None


def _group(name):
    import grp
    try:
        return grp.getgrnam(name)
    except KeyError:
        return None


def _under(path, root):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise RuntimeError('原派发平台路径不能包含上级目录跳转：' + str(path))
    try:
        path.relative_to(root)
    except ValueError:
        raise RuntimeError('原派发平台路径必须位于配置目录内：' + str(path)) from None
    for item in [path] + list(path.parents):
        if item.is_symlink():
            raise RuntimeError('派发平台权限适配不接受符号链接：' + str(item))
        if item == root:
            break
    return path


def _required(path, directory=False):
    if not (path.is_dir() if directory else path.is_file()):
        raise RuntimeError('缺少原派发平台%s：%s；请从原服务器备份恢复，不会生成默认配置或账号' %
                           ('目录' if directory else '文件', path))


def _can_access(user, path, rights):
    account = _user(user)
    if account is None:
        return False
    runner = shutil.which('runuser')
    if runner:
        for flag in rights:
            if _run([runner, '-u', user, '--', 'test', '-' + flag, str(path)], check=False).returncode:
                return False
        return True
    # Conservative mode-bit fallback; named ACLs can make this underestimate
    # access, in which case the adapter requests ACL tools before writing.
    info = path.stat()
    groups = os.getgrouplist(user, account.pw_gid)
    shift = 6 if info.st_uid == account.pw_uid else (3 if info.st_gid in groups else 0)
    bits = (info.st_mode >> shift) & 7
    return all(bits & {'r': 4, 'w': 2, 'x': 1}[right] for right in rights)


def _nginx():
    seen = set()
    for raw in ('/opt/nginx/sbin/nginx', shutil.which('nginx')):
        if not raw or raw in seen:
            continue
        seen.add(raw)
        path = Path(raw)
        if path.is_file() and os.access(str(path), os.X_OK):
            try:
                if _run([str(path), '-v'], check=False).returncode == 0:
                    return str(path)
            except OSError:
                continue
    raise RuntimeError('缺少可执行的本机 nginx；请先安装对应架构 nginx，原配置和账密未改动')


def _unit_templates(bundle, services, root, nginx):
    wanted = {'etc/systemd/system/' + name + '.service': name for name in services}
    result = {}
    with tarfile.open(str(bundle), 'r:*') as archive:
        for member in archive:
            name = str(PurePosixPath(member.name))
            if name not in wanted:
                continue
            service = wanted[name]
            if service in result or not member.isfile() or member.size > 65536:
                raise RuntimeError('平台包中的服务单元无效：' + service)
            text = archive.extractfile(member).read().decode('utf-8-sig')
            expected_user = USERS[0] if service == SERVICES[0] else USERS[1]
            if ('User=' + expected_user) not in text or '[Service]' not in text:
                raise RuntimeError('平台包中的服务身份与已知模板不一致：' + service)
            text = text.replace('/data/', str(root) + '/').replace('/data ', str(root) + ' ')
            text = text.replace('/opt/nginx/sbin/nginx', nginx)
            result[service] = text.encode('utf-8')
    if set(result) != set(services):
        raise RuntimeError('平台包缺少派发服务单元：' + ', '.join(sorted(set(services) - set(result))))
    return result


class Profile:
    def __init__(self, root, units, owned, access, needed_users):
        self.root, self.units = root, units
        self.owned, self.access, self.needed_users = owned, access, needed_users
        self.created_users, self.created_groups = [], []
        self.created_units, self.created_links, self.created_dirs = [], [], []
        self.metadata = {}
        self.acls = {}
        self.backup = None
        self.applied = False

    def _capture(self, path, acl=False):
        key = str(path)
        if path.exists() and key not in self.metadata:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise RuntimeError('权限适配路径变为符号链接：' + key)
            self.metadata[key] = {'uid': info.st_uid, 'gid': info.st_gid,
                                  'mode': stat.S_IMODE(info.st_mode)}
        if acl and path.exists() and key not in self.acls:
            self.acls[key] = _run(['getfacl', '--absolute-names', '--numeric', str(path)]).stdout

    def _save(self):
        if self.backup is None:
            return
        path = self.backup / 'profile-metadata.json'
        content = json.dumps({'metadata': self.metadata, 'acls': self.acls,
                              'created_users': self.created_users,
                              'created_groups': self.created_groups,
                              'created_units': list(map(str, self.created_units)),
                              'created_links': list(map(str, self.created_links)),
                              'created_dirs': list(map(str, self.created_dirs))}, indent=2)
        with open(str(path), 'w', encoding='utf-8') as stream:
            stream.write(content)
        os.chmod(str(path), 0o600)

    def _mkdir(self, path):
        if path.exists():
            if not path.is_dir() or path.is_symlink():
                raise RuntimeError('运行目录无效：' + str(path))
            return
        self._mkdir(path.parent)
        path.mkdir(mode=0o700)
        self.created_dirs.append(path)
        self._save()

    def apply(self, backup_dir):
        if not self.units:
            return
        if self.applied:
            raise RuntimeError('服务权限适配已执行')
        self.applied = True
        self.backup = Path(backup_dir)
        self.backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._save()
        for service in self.units:
            dest = UNIT_DIRECTORY / (service + '.service')
            if dest.exists() or dest.is_symlink():
                raise RuntimeError('原服务单元已出现，拒绝覆盖：' + str(dest))
        nologin = next((name for name in ('/usr/sbin/nologin', '/sbin/nologin') if Path(name).is_file()), None)
        if not nologin and self.needed_users:
            raise RuntimeError('缺少 nologin，不能创建平台服务身份')
        for name in self.needed_users:
            existing = _user(name)
            if existing:
                if existing.pw_uid == 0:
                    raise RuntimeError('平台服务身份不能使用 root UID：' + name)
                continue
            if not _group(name):
                _run(['groupadd', '--system', name])
                self.created_groups.append(name)
                self._save()
            _run(['useradd', '--system', '--gid', name, '--home-dir', '/nonexistent',
                  '--no-create-home', '--shell', nologin, '--password', '!', name])
            self.created_users.append(name)
            self._save()
        # Capture all metadata and ACLs before the first permission change.
        for path, owner, recursive in self.owned:
            if path.exists():
                children = [path] + (list(path.rglob('*')) if recursive else [])
                for child in children:
                    self._capture(child)
        for user, path, rights in self.access:
            self._capture(path, acl=True)
        self._save()
        for path, owner, recursive in self.owned:
            self._mkdir(path)
            account = _user(owner)
            children = [path] + (list(path.rglob('*')) if recursive else [])
            for child in children:
                if child.is_symlink():
                    raise RuntimeError('原平台状态包含符号链接：' + str(child))
                os.chown(str(child), account.pw_uid, account.pw_gid)
        for user, path, rights in self.access:
            _run(['setfacl', '-m', 'u:%s:%s' % (user, rights), str(path)])
        for service, content in self.units.items():
            dest = UNIT_DIRECTORY / (service + '.service')
            fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            self.created_units.append(dest)
            self._save()
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
            wants = UNIT_DIRECTORY / 'multi-user.target.wants'
            self._mkdir(wants)
            link = wants / dest.name
            if link.exists() or link.is_symlink():
                raise RuntimeError('已有服务启动链接，拒绝覆盖：' + str(link))
            link.symlink_to('../' + dest.name)
            self.created_links.append(link)
            self._save()
        _run(['systemctl', 'daemon-reload'])
        self._save()

    def rollback(self):
        if not self.applied:
            return
        failures = []
        for path in reversed(self.created_units + self.created_links):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                failures.append(str(path))
        for raw, info in reversed(list(self.metadata.items())):
            try:
                os.chown(raw, info['uid'], info['gid'])
                os.chmod(raw, info['mode'])
            except OSError:
                failures.append(raw)
        if self.acls:
            try:
                _run(['setfacl', '--restore=-'], data=''.join(self.acls.values()))
            except (OSError, RuntimeError):
                failures.append('原平台 ACL')
        for path in reversed(self.created_dirs):
            try:
                path.rmdir()
            except FileNotFoundError:
                pass
            except OSError:
                # Runtime files may have been created. Keep nonempty directories
                # rather than deleting newly written state or login sessions.
                pass
        for name in reversed(self.created_users):
            if _run(['userdel', name], check=False).returncode:
                failures.append(name)
        for name in reversed(self.created_groups):
            if _run(['groupdel', name], check=False).returncode:
                failures.append(name)
        if self.created_units and _run(['systemctl', 'daemon-reload'], check=False).returncode:
            failures.append('systemd daemon-reload')
        if failures:
            raise RuntimeError('服务权限适配部分回退失败，请查受保护备份：' + ', '.join(failures))


def prepare_profile(data_root, bundle, missing_services):
    root = Path(data_root).absolute()
    services = {re.sub(r'\.service$', '', str(name)) for name in missing_services}
    if not services.issubset(SERVICES):
        raise RuntimeError('只能恢复两个派发平台服务单元')
    if not services:
        return Profile(root, {}, [], [], [])
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(root)) or '..' in root.parts:
        raise RuntimeError('恢复服务单元需要不含空白或特殊字符的专用绝对配置路径')
    dispatch = _under(root / 'config_dispatch', root)
    _required(dispatch, directory=True)
    required = [dispatch / 'security-settings.json']
    if SERVICES[1] in services:
        required += [dispatch / 'gateway/nginx.conf', dispatch / 'gateway/proxy.conf',
                     dispatch / 'tls/server/server.crt', dispatch / 'tls/server/server.key']
    for path in required:
        _required(_under(path, root))
    settings = json.loads(required[0].read_text('utf-8'))
    if Path(settings.get('data_root', '/data')).absolute() != root:
        raise RuntimeError('原 security-settings.json 的 data_root 与所选配置目录不一致；请使用匹配的原配置')
    auth, backups, allowed = None, None, []
    if SERVICES[0] in services:
        auth = Path(settings.get('auth_db', str(dispatch / 'state/auth.sqlite3')))
        if not auth.is_absolute():
            auth = dispatch / auth
        auth = _under(auth, root)
        _required(auth)
        backups = Path(settings.get('backup_root', str(dispatch / 'backups')))
        if not backups.is_absolute():
            backups = dispatch / backups
        backups = _under(backups, root)
        if auth.parent != dispatch / 'state' or backups != dispatch / 'backups':
            raise RuntimeError('原认证库/备份目录使用了自定义位置，请恢复相配的原服务单元；不能套用标准服务模板')
        allowed = settings.get('allowed_paths')
        if not isinstance(allowed, list) or not allowed:
            raise RuntimeError('原派发平台配置缺少 allowed_paths；不能套用默认配置')
        allowed = [_under(Path(name), root) for name in allowed]
        for path in allowed:
            _required(path)
    native_nginx = _nginx() if SERVICES[1] in services else '/opt/nginx/sbin/nginx'
    if any(char.isspace() for char in native_nginx):
        raise RuntimeError('本机 nginx 路径不能包含空白')
    units = _unit_templates(bundle, services, root, native_nginx)
    for service in services:
        dest = UNIT_DIRECTORY / (service + '.service')
        link = UNIT_DIRECTORY / 'multi-user.target.wants' / dest.name
        if dest.exists() or dest.is_symlink() or link.exists() or link.is_symlink():
            raise RuntimeError('已有服务文件或启动链接，请恢复其正常状态后重试：' + service)
    required_users = [USERS[i] for i, service in enumerate(SERVICES) if service in services]
    needed_users = []
    for name in required_users:
        account = _user(name)
        if account is None:
            needed_users.append(name)
        elif account.pw_uid == 0:
            raise RuntimeError('平台服务身份不能使用 root UID：' + name)
    if needed_users:
        for tool in ('useradd', 'groupadd', 'userdel', 'groupdel'):
            if not shutil.which(tool):
                raise RuntimeError('缺少服务身份工具 %s；原配置和账号库未改动' % tool)
    owned = []
    if SERVICES[0] in services:
        owned += [(auth.parent, USERS[0], True), (backups, USERS[0], True)]
    if SERVICES[1] in services:
        owned += [(dispatch / ('gateway/' + name), USERS[1], True) for name in ('run', 'temp', 'logs')]
    access = {}
    def grant(user, path, rights):
        if not _can_access(user, path, rights):
            key = (user, path)
            access[key] = ''.join(char for char in 'rwx' if char in set(access.get(key, '') + rights))
    for user in required_users:
        parent = root.parent
        while parent != parent.parent:
            if not _can_access(user, parent, 'x') and user not in needed_users:
                raise RuntimeError('原平台服务身份无法访问配置目录的上级路径：' + str(parent))
            # New service accounts cannot gain access through a private parent
            # unless traversal for other users is already present.
            if user in needed_users and not (parent.stat().st_mode & stat.S_IXOTH):
                raise RuntimeError('新平台服务身份无法穿过私有上级目录：' + str(parent))
            parent = parent.parent
        grant(user, root, 'x')
        grant(user, dispatch, 'rx')
    if SERVICES[0] in services:
        grant(USERS[0], required[0], 'r')
        for path in allowed:
            grant(USERS[0], path, 'r')
            parent = path.parent
            grant(USERS[0], parent, 'rwx')
            while parent != root:
                parent = parent.parent
                grant(USERS[0], parent, 'x')
        for path in dispatch.iterdir():
            if path.is_file() and path.suffix in ('.py', '.html', '.css', '.js'):
                grant(USERS[0], path, 'r')
    if SERVICES[1] in services:
        for path in required[1:]:
            grant(USERS[1], path, 'r')
            parent = path.parent
            while parent != dispatch:
                grant(USERS[1], parent, 'rx')
                parent = parent.parent
    if access:
        for tool in ('getfacl', 'setfacl'):
            if not shutil.which(tool):
                raise RuntimeError('原配置恢复后需要 %s 适配服务身份权限；请先安装 acl，未修改配置和账号库' % tool)
    return Profile(root, units, owned,
                   [(user, path, rights) for (user, path), rights in access.items()], needed_users)
