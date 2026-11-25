"""Retain original containers until the new platform has passed its final checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(os.environ.get('ONECLICK_ROOT','/root/oneclick'))
STATE=ROOT/'container-transaction.json'
NAMES=('zlk','seal_system','seal_system_vue')


def run(args,check=True):
    return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,check=check,timeout=180)


def save(state):
    temp=STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state,indent=2),encoding='utf-8');temp.chmod(0o600)
    temp.replace(STATE)


def archive_history(history):
    """Publish a verified snapshot on the backup disk before removing its source."""
    if STATE.is_symlink():
        raise ValueError('Refusing a symlink container transaction state')
    original_stat = STATE.stat()
    content = STATE.read_bytes()
    previous = json.loads(content)
    if previous.get('status') == 'pending':
        raise ValueError('存在未完成容器事务，请先执行 container_transaction.py rollback')
    history.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if history.exists():
        raise ValueError('Container transaction history already exists: ' + str(history))
    fd, name = tempfile.mkstemp(prefix='.' + history.name + '.', suffix='.tmp', dir=str(history.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Both paths are on the backup filesystem; STATE may be on another disk.
        temporary.replace(history)
        if history.read_bytes() != content:
            raise ValueError('Container transaction history verification failed')
        current_stat = STATE.stat()
        if (STATE.is_symlink() or (current_stat.st_dev, current_stat.st_ino) !=
                (original_stat.st_dev, original_stat.st_ino) or STATE.read_bytes() != content):
            raise ValueError('Container transaction state changed while archiving; original retained')
        STATE.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare():
    if STATE.exists():
        history=ROOT/'backups'/('container-transaction-'+str(time.time_ns())+'.json')
        archive_history(history)
    state={'status':'pending','containers':{}};save(state)
    try:
        for name in NAMES:
            result=run(['docker','inspect',name],False)
            if result.returncode:continue
            info=json.loads(result.stdout)[0]
            record={'id':info['Id'],'backup_name':name+'-before-oneclick-'+str(int(time.time())),
                    'running':info['State']['Running'],'restart':info['HostConfig']['RestartPolicy'],'renamed':False}
            state['containers'][name]=record;save(state)
        # Snapshot every original before stopping any one of them.
        for name,record in state['containers'].items():
            run(['docker','stop',name])
            run(['docker','rename',name,record['backup_name']])
            record['renamed']=True;save(state)
            run(['docker','update','--restart=no',record['backup_name']])
    except Exception:
        rollback();raise


def rollback():
    if not STATE.exists():return
    state=json.loads(STATE.read_text())
    if state['status']!='pending':return
    for name in reversed(NAMES):
        record=state['containers'].get(name)
        current=run(['docker','inspect',name],False)
        if current.returncode==0:
            info=json.loads(current.stdout)[0]
            if not record or info['Id']!=record['id']:
                if (info['Config'].get('Labels') or {}).get('oneclick.release')!='v2.2-20261030':
                    raise ValueError('容器名称被非本次部署占用，拒绝删除：'+name)
                run(['docker','rm','-f',name])
        if record:
            if record['renamed']:run(['docker','rename',record['backup_name'],name])
            policy=record['restart']['Name'] or 'no'
            if policy=='on-failure' and record['restart'].get('MaximumRetryCount'):
                policy+=':'+str(record['restart']['MaximumRetryCount'])
            run(['docker','update','--restart='+policy,name])
            if record['running']:run(['docker','start',name])
    state['status']='rolled_back';save(state)
    print('CONTAINERS_ROLLED_BACK; database/config backup must be reviewed if schema changed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','rollback','commit'));args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='rollback':rollback()
    else:
        state=json.loads(STATE.read_text());state['status']='verified';save(state)
        print('CONTAINERS_VERIFIED; previous containers retained stopped for rollback')


if __name__=='__main__':
    os.umask(0o077)
    main()
