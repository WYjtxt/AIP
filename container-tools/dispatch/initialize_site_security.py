"""Generate missing site secrets; leave existing private settings unchanged."""
import json
import os
from pathlib import Path
import secrets
import configparser


def main():
    path=Path('/data/Config_files/platform-security.json')
    if path.exists():
        data=json.loads(path.read_text(encoding='utf-8'))
    else:
        data={}
    changed=False
    for key in ('SESSION_SECRET_KEY','JWT_SECRET_KEY','MEDIA_SESSION_SECRET_KEY'):
        value=data.get(key)
        if not value or value in ('GENERATE_ON_TARGET','__GENERATE_ON_TARGET__'):
            data[key]=secrets.token_hex(48)
            changed=True
    if changed:
        path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(str(path),os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream: json.dump(data,stream)
        os.chmod(str(path),0o600)
    site=Path('/data/Config_files/config.ini')
    settings=configparser.ConfigParser(interpolation=None);settings.read(str(site))
    if settings.has_section('ZLK') and settings['ZLK'].get('ZLK_SECRET')=='__ONECLICK_ZLK_SECRET__':
        key=secrets.token_hex(24)
        for filename in (site,Path('/data/Config_files/zlk/config.ini')):
            if filename.exists():
                filename.write_text(filename.read_text(encoding='utf-8').replace('__ONECLICK_ZLK_SECRET__',key),encoding='utf-8')
    print('SITE_SIGNING_KEYS=READY')


if __name__=='__main__':main()
