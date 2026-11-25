"""Validate the selected data directory before touching a single-install host.

Legacy services keep /data paths. A full install can create a compatibility
symlink to a dedicated directory, but must never hide or move existing data.
Check/clean modes never create that link.
"""
import argparse
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess

MANAGED_DIRS = ('mysql', 'redis', 'kafka', 'Config_files', 'platform_gateway',
                'config_dispatch', 'platform_algorithm_start', 'model_algorithm_package',
                'platform_storage', 'platform_ops', 'platform_alarm_media')


def normalize_data_root(value):
    if not isinstance(value, str) or not value.startswith('/') or '\\' in value or ':' in value or any(
            ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('服务器配置根目录必须是 Linux 绝对路径，例如 /data 或 /srv/platform')
    value = '/' + posixpath.normpath(value).lstrip('/')
    exact = ('/', '/var', '/root', '/home', '/opt', '/srv', '/mnt', '/media')
    trees = ('/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot', '/dev',
             '/proc', '/sys', '/run', '/tmp', '/root/oneclick', '/root/stage',
             '/root/miniconda3', '/var/lib/docker', '/var/run', '/opt/mysql',
             '/opt/nginx', '/opt/Config_files', '/home/mysql')
    if value in exact or any(value == tree or value.startswith(tree + '/') for tree in trees):
        raise ValueError('请选择专用的平台数据目录，不能使用系统或安装介质目录：' + value)
    return value


def same_path(left, right):
    left, right = Path(left), Path(right)
    return left.resolve() == right.resolve() or (left.exists() and right.exists() and left.samefile(right))


def resolve_selected_root(value, canonical=Path('/data')):
    selected = Path(value).resolve()
    if selected == canonical and canonical.is_dir() and not canonical.is_symlink():
        candidates = {(canonical / name).resolve().parent for name in MANAGED_DIRS
                      if (canonical / name).is_symlink() and (canonical / name).resolve().name == name}
        if len(candidates) == 1:
            candidate = next(iter(candidates))
            if all(not (canonical / name).exists() and not (canonical / name).is_symlink()
                   or same_path(canonical / name, candidate / name) for name in MANAGED_DIRS):
                return candidate
    return selected


def validate_root(selected, mode, prepare=False, canonical=Path('/data'), layout='root'):
    """Filesystem-only part, also exercised against isolated temporary trees."""
    selected, canonical = Path(selected), Path(canonical)
    target = selected.resolve()
    current = canonical.resolve()
    same = same_path(target, canonical)
    if selected.exists() and not selected.is_dir():
        raise ValueError('配置根目录不是目录：' + str(selected))
    if mode == 'fresh':
        for relative in ('mysql/mysql', 'config_dispatch/state/auth.sqlite3', 'Config_files/config.ini'):
            if (target / relative).exists():
                raise ValueError('fresh 仅用于空环境；已有配置或数据库，请使用 repair 或 platform：' + str(target / relative))
    if mode in ('clean', 'verify') and not target.is_dir():
        raise ValueError('所选原配置目录不存在，未操作平台：' + str(selected))
    if layout == 'children' and not same:
        if current in target.parents or target in current.parents:
            raise ValueError('配置根目录不能与 /data 相互嵌套')
        if canonical.is_symlink() or (canonical.exists() and not canonical.is_dir()):
            raise ValueError('所选目录与现有 /data 冲突')
        for name in MANAGED_DIRS:
            alias = canonical / name
            if (alias.exists() or alias.is_symlink()) and not same_path(alias, target / name):
                raise ValueError('平台子目录冲突，未覆盖原数据：' + str(alias))
        if prepare:
            if mode not in ('fresh', 'repair'):
                raise ValueError('仅 fresh/repair 可准备数据目录')
            target.mkdir(parents=True, exist_ok=True)
            canonical.mkdir(parents=True, exist_ok=True)
            for name in MANAGED_DIRS:
                (target / name).mkdir(exist_ok=True)
                alias = canonical / name
                if not alias.exists() and not alias.is_symlink():
                    alias.symlink_to(target / name, target_is_directory=True)
        return target
    if not same:
        if current in target.parents or target in current.parents:
            raise ValueError('配置根目录不能与 /data 相互嵌套')
        if os.path.ismount(str(canonical)) or canonical.is_symlink() or (canonical.exists() and (
                not canonical.is_dir() or any(canonical.iterdir()))):
            raise ValueError('所选目录与现有 /data 冲突；不会覆盖、迁移或清洗另一目录，请填写当前平台根目录')
    if prepare:
        if mode not in ('fresh', 'repair'):
            raise ValueError('仅 fresh/repair 可准备数据目录')
        target.mkdir(parents=True, exist_ok=True)
        if not same:
            removed_empty = canonical.exists()
            if removed_empty:
                canonical.rmdir()  # Fails safely for nonempty directories and mounted filesystems.
            try:
                canonical.symlink_to(target, target_is_directory=True)
            except OSError:
                if removed_empty and not canonical.exists() and not canonical.is_symlink():
                    canonical.mkdir()
                raise
    return target


def configure_dispatch_root(settings_path, selected, canonical=Path('/data')):
    selected, canonical = Path(selected).resolve(), Path(canonical)
    path = Path(settings_path)
    settings = json.loads(path.read_text(encoding='utf-8'))
    old_root = Path(settings.get('data_root', str(canonical)))
    if old_root not in (canonical, selected) and old_root.resolve() != selected:
        raise ValueError('原派发配置根目录不匹配，未改写配置')

    def mapped(value):
        if not isinstance(value, str):
            return value
        original = Path(value)
        try:
            relative = original.relative_to(canonical)
        except ValueError:
            return value
        if not relative.parts or relative.parts[0] not in MANAGED_DIRS:
            raise ValueError('派发配置包含非平台路径：' + value)
        if not same_path(canonical / relative.parts[0], selected / relative.parts[0]):
            raise ValueError('派发配置目录映射不匹配，未改写配置：' + value)
        return str(selected / relative)

    updated = dict(settings)
    updated['data_root'] = str(selected)
    updated['allowed_paths'] = [mapped(value) for value in settings.get('allowed_paths', [])]
    for key in ('auth_db', 'backup_root'):
        if key in settings:
            updated[key] = mapped(settings[key])
    if updated != settings:
        backup = path.with_name(path.name + '.before-root-update')
        if not backup.exists():
            import shutil
            shutil.copy2(str(path), str(backup))
            os.chmod(str(backup), 0o600)
        temp = path.with_name(path.name + '.root-new')
        descriptor = os.open(str(temp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
        os.replace(str(temp), str(path))
    return updated


def adapt_service_unit(text, selected):
    root = Path(selected).resolve()
    # systemd unescapes these path tokens after splitting list-valued directives.
    escaped = str(root).replace('%', '%%').replace('\\', '\\x5c').replace(' ', '\\x20').replace('"', '\\x22').replace("'", '\\x27')
    text = text.replace('/data/', escaped + '/')
    # Legacy discovery splits CFGP_ROOTS on whitespace. Scan the nearest
    # whitespace-free ancestor; SecurityConfig still admits only its exact whitelist.
    search_root = root
    while any(char.isspace() for char in str(search_root)):
        search_root = search_root.parent
    search_token = str(search_root).replace('%', '%%').replace('"', '\\x22').replace("'", '\\x27')
    text = re.sub(r'^Environment="CFGP_ROOTS=.*"$',
                  lambda match: 'Environment="CFGP_ROOTS=' + search_token + '"', text, flags=re.M)
    if Path('/home') in root.parents and 'ProtectHome=true' in text:
        text = text.replace('ProtectHome=true', 'ProtectHome=tmpfs\nBindReadOnlyPaths=' + escaped)
    return text


def configure_services(root, unit_dir=Path('/etc/systemd/system')):
    root = Path(root).resolve()
    configure_dispatch_root(root / 'config_dispatch/security-settings.json', root)
    for name in ('config-dispatch.service', 'config-dispatch-gateway.service'):
        path = unit_dir / name
        text = path.read_text(encoding='utf-8')
        updated = adapt_service_unit(text, root)
        if updated != text:
            path.write_text(updated, encoding='utf-8')


def check_service_roots(root, my_cnf=Path('/etc/my.cnf'), inspect_container=True,
                        allow_pending_link=False):
    """Do not clean or update global services belonging to a different root."""
    if my_cnf.is_file():
        text = my_cnf.read_text(encoding='utf-8', errors='replace')
        match = re.search(r'^\s*datadir\s*=\s*(.*?)\s*$', text, re.M)
        if match:
            actual = Path(match.group(1).strip('"\'')).resolve()
            expected = (root / 'mysql').resolve()
            # Before creating /data, an existing canonical configuration is valid.
            canonical_config = actual == Path('/data/mysql').resolve()
            pending = canonical_config and (same_path(root, Path('/data')) or allow_pending_link)
            if not same_path(actual, expected) and not pending:
                raise ValueError('MySQL datadir 不属于所选配置根目录，未操作数据库：' + str(actual))
    if inspect_container:
        try:
            result = subprocess.run(['docker', 'inspect', 'seal_system'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, timeout=20)
        except FileNotFoundError:
            return
        if result.returncode == 0:
            for mount in json.loads(result.stdout)[0].get('Mounts', []):
                if mount.get('Destination') == '/Seal_system/config.ini':
                    if not same_path(Path(mount.get('Source', '')), root / 'Config_files/config.ini'):
                        raise ValueError('运行中的平台容器配置不属于所选根目录，未操作现有平台')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('fresh', 'repair', 'verify', 'clean'), required=True)
    parser.add_argument('--data-root', default=os.environ.get('PLATFORM_DATA_ROOT', '/data'))
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--configure-services', action='store_true')
    parser.add_argument('--cleanup-aliases', action='store_true')
    args = parser.parse_args()
    selected = resolve_selected_root(normalize_data_root(args.data_root))
    normalize_data_root(selected.resolve().as_posix())  # Also reject aliases to protected paths.
    layout = 'children' if Path('/home') in selected.resolve().parents else 'root'
    root = validate_root(selected, 'repair' if args.configure_services else args.mode, layout=layout)
    if args.mode in ('fresh', 'repair') and any(
            parent == root or parent in root.parents
            for parent in (Path('/root'), Path('/var/tmp'))):
        raise ValueError('平台服务启用了 ProtectHome/PrivateTmp，请使用 /data、/srv/platform 等服务可访问的数据目录')
    if layout == 'root' and args.mode in ('fresh', 'repair') and not same_path(root, Path('/data')):
        fstab = Path('/etc/fstab')
        if fstab.is_file() and any(len(parts) > 1 and parts[1] == '/data'
                                  for parts in (line.split() for line in fstab.read_text().splitlines())
                                  if parts and not parts[0].startswith('#')):
            raise ValueError('/etc/fstab 已配置 /data 挂载，请使用该原目录；未创建兼容链接')
        if any(Path(path).exists() for path in ('/etc/systemd/system/data.mount', '/run/systemd/system/data.mount')):
            raise ValueError('现有 data.mount 单元管理 /data，请使用该原目录；未创建兼容链接')
    check_service_roots(root, allow_pending_link=args.mode in ('fresh', 'repair'))
    if args.prepare:
        root = validate_root(selected, args.mode, prepare=True, layout=layout)
    if args.configure_services:
        if args.mode not in ('fresh', 'repair'):
            raise ValueError('只允许安装模式适配服务路径')
        configure_services(root)
    if args.cleanup_aliases:
        if args.mode != 'clean':
            raise ValueError('仅 clean 可删除失效的平台目录别名')
        for name in MANAGED_DIRS:
            alias = Path('/data') / name
            if alias.is_symlink() and alias.resolve() == root / name and not (root / name).exists():
                alias.unlink()
    print(str(root))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit('配置目录检查失败：' + str(exc))
