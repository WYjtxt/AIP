"""Register the deployment host without replacing saved site device settings."""
from pathlib import Path
import configparser
import re
import secrets


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


def ensure_local_device(connection, ip, username, password):
    """Use the existing device schema and keep an existing matching IP intact.

    The schema and its SSH consumers currently support the normal SSH port 22;
    there is no separate vendor or SSH-port database column to populate.
    The caller supplies a regular PyMySQL connection. Results contain no secret.
    """
    ip = str(ip or '').strip()
    if not ip:
        raise ValueError('缺少部署服务器IP，无法录入分析服务器')
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id, computing_name FROM t_computing_equipment '
                           'WHERE computing_ip=%s ORDER BY id LIMIT 1', (ip,))
            existing = cursor.fetchone()
            if existing is not None:
                return {'created': False, 'computing_id': existing[0], 'ip': ip,
                        'name': existing[1], 'status': 'existing_preserved'}
            username = str(username or '').strip()
            if not username or not isinstance(password, str) or not password:
                raise ValueError('缺少部署SSH账号密码，无法录入分析服务器')
            if any(len(value) > 50 for value in (ip, username, password)):
                raise ValueError('部署服务器IP或SSH账号密码超出现有设备字段长度')
            cursor.execute(
                'INSERT INTO t_computing_equipment '
                '(computing_ip, computing_name, computing_code, computing_user, '
                'computing_password, computing_status, server_type, created_at, updated_at) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())',
                (ip, '分析服务器', 'YGSJ-' + secrets.token_hex(5), username, password, 1, 1))
            computing_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {'created': True, 'computing_id': computing_id, 'ip': ip,
            'name': '分析服务器', 'status': 'created'}


def bind_local_resources(connection, ip, computing_id):
    """Associate only this host's collected cards with its registered device."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('UPDATE t_resource_usage SET computing_id=%s WHERE dev_ip=%s '
                           'AND (computing_id IS NULL OR computing_id<>%s)',
                           (int(computing_id), ip, int(computing_id)))
            changed = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return changed


def configure_local_collector(root, computing_id):
    """Bind the selected native card collector and scheduler to this host ID."""
    root = Path(root)
    path = root / 'model_algorithm_package/Huawei_resource.py'
    if detect_driver_family() != 'huawei' and (root / 'model_algorithm_package/Sophon_resource.py').is_file():
        path = root / 'model_algorithm_package/Sophon_resource.py'
    if not path.is_file():
        return False
    source = path.read_text(encoding='utf-8')
    updated, count = re.subn(r'(?m)^([ \t]*COMPUTING_ID[ \t]*=[ \t]*)\d+([ \t]*(?:#.*)?)$',
                            lambda match: match.group(1) + str(int(computing_id)) + match.group(2),
                            source, count=1)
    if count != 1:
        raise ValueError('未找到本机算力采集器的设备ID配置')
    changed = source != updated
    if changed:
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(updated)
    if path.name == 'Sophon_resource.py':
        settings_path = root / 'platform_algorithm_start/config/ApiConfig.ini'
        settings = configparser.ConfigParser(interpolation=None)
        settings.read(str(settings_path), encoding='utf-8')
        if settings.has_section('ipconfig') and settings['ipconfig'].get('computing_id') != str(int(computing_id)):
            settings['ipconfig']['computing_id'] = str(int(computing_id))
            with settings_path.open('w', encoding='utf-8', newline='\n') as stream:
                settings.write(stream)
            changed = True
    return changed
