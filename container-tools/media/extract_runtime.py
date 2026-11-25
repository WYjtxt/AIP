"""Extract release code while preserving existing site configuration and secrets."""
import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

PRESERVE = {
    'data/Config_files/config.ini', 'data/Config_files/config.js',
    'data/Config_files/platform-security.json', 'data/Config_files/zlk/config.ini',
    'data/config_dispatch/security-settings.json',
    'data/platform_algorithm_start/config/ApiConfig.ini',
    'etc/my.cnf', 'etc/docker/daemon.json', 'usr/local/etc/redis.conf',
    'opt/nginx/conf/nginx.conf',
}


def extract(bundle, root=Path('/')):
    root = Path(root).resolve()
    with tarfile.open(bundle) as archive:
        entries = []
        for member in archive:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not member.isfile():
                raise ValueError('Invalid runtime archive entry: ' + member.name)
            target = (root / str(name)).resolve()
            if root not in target.parents:
                raise ValueError('Runtime entry escapes target root')
            entries.append((member, target, str(name)))
        for member, target, name in entries:
            if target.exists() and name in PRESERVE:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + '.oneclick-new')
            with archive.extractfile(member) as source, temp.open('wb') as output:
                shutil.copyfileobj(source, output)
            os.chmod(str(temp), member.mode & 0o755)
            temp.replace(target)
    print('RUNTIME_CODE_UPDATED; existing site settings preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('bundle')
    extract(parser.parse_args().bundle)
