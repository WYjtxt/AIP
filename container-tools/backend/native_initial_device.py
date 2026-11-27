"""Register the deployment host without replacing saved site device settings."""
from pathlib import Path
import configparser
import importlib.util


def load_host_identity(root):
    module_path = Path(root) / 'backend/common/platform_host_identity.py'
    spec = importlib.util.spec_from_file_location('platform_host_identity', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def detect_driver_family(system_root='/'):
    """Select a model family from installed drivers, independently of CPU arch."""
    root = Path(system_root)
    huawei = (root / 'usr/local/Ascend/driver/version.info').is_file()
    sophon = (root / 'sys/module/bmsophon').is_dir() or any(
        (root / 'dev').glob('bm-sophon[0-9]*'))
    if huawei and not sophon:
        return 'huawei'
    if sophon and not huawei:
        return 'sophon'
    return 'unknown'


def ensure_local_device(connection, ip, username, password, root='/data/AIGO/platform_start'):
    """Bind once; reinstall and address changes preserve the original host ID."""
    identity = load_host_identity(root)
    identity.ensure_schema(connection)
    return identity.register_device(connection, ip, '分析服务器', str(username or '').strip(),
                                    password, identity.read_host_identity(), allow_existing=True)


def bind_local_resources(connection, ip, computing_id, root='/data/AIGO/platform_start'):
    """Adopt only unowned cards from the verified host's pre-upgrade address."""
    identity = load_host_identity(root)
    try:
        with connection.cursor() as cursor:
            device = identity.resolve_device(cursor, identity.read_host_identity(), lock=True)
            if not device or device['computing_id'] != int(computing_id) or device['computing_ip'] != ip:
                raise identity.IdentityConflict('安装期间分析服务器身份或地址已变化')
            cursor.execute('UPDATE t_resource_usage SET computing_id=%s,updated_at=updated_at '
                           'WHERE dev_ip=%s AND (computing_id IS NULL OR computing_id=0)',
                           (int(computing_id), ip))
            changed = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return changed


def configure_local_collector(root, computing_id):
    """Keep the scheduler's legacy setting; the collector uses its machine ID."""
    root = Path(root)
    settings_path = root / 'platform_algorithm_start/config/ApiConfig.ini'
    settings = configparser.ConfigParser(interpolation=None)
    settings.read(str(settings_path), encoding='utf-8')
    if not settings.has_section('ipconfig') or settings['ipconfig'].get('computing_id') == str(int(computing_id)):
        return False
    settings['ipconfig']['computing_id'] = str(int(computing_id))
    with settings_path.open('w', encoding='utf-8', newline='\n') as stream:
        settings.write(stream)
    return True
