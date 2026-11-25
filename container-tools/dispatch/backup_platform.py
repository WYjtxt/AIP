"""Back up the existing platform before full repair; failure stops the deployment."""
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import sqlite3


def main():
    root=Path(os.environ.get('ONECLICK_ROOT','/root/oneclick'))
    target=root/'backups'/('before-repair-'+time.strftime('%Y%m%d_%H%M%S'))
    target.mkdir(parents=True,mode=0o700)
    os.chmod(str(target),0o700)
    config=Path('/data/Config_files/config.ini')
    if config.is_file() and Path('/data/mysql/mysql').is_dir():
        parser=configparser.ConfigParser(interpolation=None);parser.read(str(config))
        c=parser['database']
        tool=shutil.which('mysqldump')
        if not tool:raise ValueError('备份前找不到 mysqldump；未修改现有平台')
        env=dict(os.environ,MYSQL_PWD=c['DB_PASSWORD'])
        with (target/'seal_system.sql').open('wb') as output:
            subprocess.run([tool,'--no-defaults','--single-transaction','--routines','--triggers','--events',
                            '--no-tablespaces','--set-gtid-purged=OFF','--host='+c['DB_HOST'],
                            '--port='+c.get('DB_PORT','3306'),'--user='+c['DB_USER'],
                            '--databases',c['DB_NAME']],stdout=output,stderr=subprocess.PIPE,env=env,check=True,timeout=900)
    paths=['/data/Config_files','/data/config_dispatch','/data/platform_gateway','/data/platform_ops',
           '/data/platform_storage/config','/etc/my.cnf','/usr/local/etc/redis.conf']
    with tarfile.open(target/'configuration.tar.gz','w:gz') as archive:
        for name in paths:
            if Path(name).exists():
                archive.add(str(Path(name).resolve()),arcname=name.lstrip('/'),filter=lambda m:None if '/backups/' in m.name or '/logs/' in m.name or '/patches/' in m.name else m)
    result={'backup':str(target),'database_dump':(target/'seal_system.sql').exists(),'created_at':time.strftime('%Y-%m-%dT%H:%M:%S')}
    (target/'result.json').write_text(json.dumps(result))
    # SQLite backup API captures a consistent account store even with active WAL.
    auth=Path('/data/config_dispatch/state/auth.sqlite3')
    if auth.exists():
        with sqlite3.connect(str(auth)) as source, sqlite3.connect(str(target/'auth.sqlite3')) as destination:
            source.backup(destination)
    print('PLATFORM_BACKUP='+str(target))


if __name__=='__main__':
    os.umask(0o077)
    main()
