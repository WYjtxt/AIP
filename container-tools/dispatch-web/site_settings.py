"""Return existing site credentials to the parent shell without logging values."""
import configparser
import os
from pathlib import Path
import shlex

path = Path('/data/Config_files/config.ini')
if path.exists():
    config = configparser.ConfigParser(interpolation=None)
    config.read(str(path))
    database = config['database']
    if database.get('DB_USER') != 'root' or database.get('DB_HOST') not in ('127.0.0.1','localhost','::1',os.environ.get('TARGET_IP')) or database.get('DB_NAME')!='seal_system':
        raise SystemExit('Full repair requires the existing local root DB configuration; use platform mode for an external/custom DB')
    values = {'MYSQL_ROOT_PASS': database['DB_PASSWORD'], 'PRESERVE_SITE_CONFIG': '1'}
    for section in config.sections():
        if config[section].get('Box_password'):
            values['BOX_PASS'] = config[section]['Box_password']
    for name, value in values.items():
        print('export ' + name + '=' + shlex.quote(value))
