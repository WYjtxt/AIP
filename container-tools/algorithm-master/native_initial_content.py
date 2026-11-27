"""Set up the local analysis server and matching bundled model during installation."""
import argparse
import configparser
import json
import os
from pathlib import Path
import sys

from native_initial_device import (bind_local_resources, configure_local_collector,
                                   detect_driver_family, ensure_local_device)


def database_connection(root):
    import pymysql
    settings = configparser.ConfigParser(interpolation=None)
    settings.read(str(root / 'Config_files/config.ini'), encoding='utf-8')
    database = settings['database']
    return pymysql.connect(host=database['DB_HOST'], port=int(database.get('DB_PORT', '3306')),
                           user=database['DB_USER'], password=database['DB_PASSWORD'],
                           database=database['DB_NAME'], charset='utf8mb4')


def initialize(root, models_root, phase, env=None):
    env = os.environ if env is None else env
    root, models_root = Path(root), Path(models_root)
    state = root / 'platform_ops/state/initial-content.json'
    report = json.loads(state.read_text(encoding='utf-8')) if state.exists() else {}
    connection = database_connection(root)
    try:
        if phase == 'device':
            report['device'] = ensure_local_device(connection, env.get('TARGET_IP'),
                env.get('BOOTSTRAP_SSH_USER') or env.get('BOX_USER'),
                env.get('BOOTSTRAP_SSH_PASSWORD') or env.get('BOX_PASS'), root=root)
            report['collector_updated'] = configure_local_collector(root, report['device']['computing_id'])
        else:
            device = report['device']
            bind_local_resources(connection, device['ip'], device['computing_id'], root=root)
    finally:
        connection.close()
    report['family'] = detect_driver_family()
    if phase == 'model':
        os.environ['PLATFORM_SECURITY_CONFIG'] = str(root / 'Config_files/platform-security.json')
        os.environ['HOST_MACHINE_ID'] = Path('/etc/machine-id').read_text().strip()
        os.chdir(str(root / 'backend'))
        sys.path.insert(0, str(root / 'backend'))
        from server_app_factory import create_app
        from native_initial_model import preinstall_model
        app = create_app(start_scheduler=False)
        with app.app_context():
            report['model'] = preinstall_model(models_root, report['family'], device['computing_id'])
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    state.chmod(0o600)
    print('INITIAL_CONTENT=' + json.dumps(report, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--models-root', type=Path, required=True)
    parser.add_argument('--phase', choices=('device', 'model'), required=True)
    args = parser.parse_args()
    try:
        initialize(args.root, args.models_root, args.phase)
    except Exception as error:
        # Credentials from the deployment environment must not enter logs.
        print('INITIAL_CONTENT=FAIL; error_type=' + type(error).__name__, flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
