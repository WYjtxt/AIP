"""Host-side CLI for the unified configuration pilot (Docker host networking)."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Config_files'))
from platform_site_config import (MASTER, STATE, SiteManager, SiteConfigError, atomic,
                                  encoded, sha, unique_json, validate)

FIXED = '/data/AIGO/platform_start'


def run(arguments, source=None, timeout=60):
    answer = subprocess.run([str(x) for x in arguments], input=source, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)
    if answer.returncode:
        raise SiteConfigError('平台控制命令未通过：' + str(arguments[0]))
    return answer.stdout


DATABASE = r'''
import configparser,hashlib,json,pymysql,sys
sys.path.insert(0,'/data/AIGO/platform_start/Config_files')
from platform_host_identity import (TABLE, _missing_table, bind_identity, ensure_schema,
                                    identity_rows, read_host_identity, resolve_device, update_address)
c=configparser.ConfigParser(interpolation=None);c.read('/data/AIGO/platform_start/Config_files/config.ini',encoding='utf-8');d=c['database']
db=pymysql.connect(host=d['DB_HOST'],port=int(d.get('DB_PORT',3306)),user=d['DB_USER'],password=d['DB_PASSWORD'],database=d['DB_NAME'],charset='utf8mb4')
request=json.loads(sys.argv[1])
try:
 with db.cursor() as cur:
  action=request['action']
  identity=read_host_identity()
  if request.get('host_uid') not in (None,identity['host_uid']):raise RuntimeError('Local machine identity changed')
  device=resolve_device(cur,identity,request.get('old'),lock=True)
  if device is None and action=='restore_address':
   device=resolve_device(cur,identity,request['new'],lock=True)
  if not device:raise RuntimeError('Local identity not bound')
  if request.get('computing_id') not in (None,device['computing_id']):raise RuntimeError('Local server association changed')
  if action in ('address','restore_address'):
   if device['computing_ip'] not in (request['old'],request['new']):raise RuntimeError('Address changed concurrently')
   if action=='address' and request.get('identity_source') not in (None,device['source']):
    raise RuntimeError('Local machine binding changed concurrently')
   cid=device['computing_id']
   if action=='address' and device['source']=='legacy_ip':
    # Create only the independent identity table. DDL may release the earlier
    # locks, so recheck the exact legacy row and binding afterwards.
    try:identity_rows(cur,cid,identity['host_uid'],lock=True)
    except Exception as error:
     if not _missing_table(error):raise
     ensure_schema(db)
    locked=resolve_device(cur,identity,request['old'],lock=True)
    if locked!=device:raise RuntimeError('Legacy identity changed concurrently')
    cur.execute('SELECT id FROM t_computing_equipment WHERE computing_ip=%s AND server_type=1 ORDER BY id FOR UPDATE',(request['old'],))
    if list(cur.fetchall())!=[(cid,)]:raise RuntimeError('Legacy analysis server is no longer unique')
    bind_identity(cur,cid,identity)
   if action=='restore_address' and device['source']=='legacy_ip':
    if device['computing_ip']!=request['new']:raise RuntimeError('Cannot restore an unbound changed server')
   elif device['computing_ip']!=request['new']:
    update_address(cur,cid,request['new'],identity)
    if action=='restore_address' and request.get('identity_source')=='legacy_ip':
     cur.execute('DELETE FROM '+TABLE+' WHERE computing_id=%s AND host_uid=%s AND anchor_uid <=> %s',
                 (cid,identity['host_uid'],identity.get('anchor_uid')))
     if cur.rowcount!=1:raise RuntimeError('Legacy machine binding changed during rollback')
  cur.execute('SELECT id,computing_name,computing_code,computing_user,computing_status,server_type FROM t_computing_equipment ORDER BY id');devices=cur.fetchall()
  cur.execute('SELECT id,computing_id,dev_id,dev_get_sn FROM t_resource_usage ORDER BY id');cards=cur.fetchall()
  cur.execute('SELECT id,computing_id,resource_id,status,conf_area,cross_line_area,conf_img_resolution FROM t_algorithm_config ORDER BY id');tasks=cur.fetchall()
  result={'business_sha256':hashlib.sha256(json.dumps([devices,cards,tasks],ensure_ascii=False,default=str).encode()).hexdigest(),'computing_id':device['computing_id'],'host_uid':identity['host_uid'],'identity_source':device['source'],'task_bindings':[list(r[:4]) for r in tasks]}
 db.commit();print(json.dumps(result))
finally:db.close()
'''
def count_directory(record):
    env = dict(item.split('=', 1) for item in record['Config'].get('Env', []) if '=' in item)
    directory = PurePosixPath(env.get('PLATFORM_COUNT_STATE_DIR') or str(PurePosixPath(FIXED).parent / 'platform_counts'))
    if not directory.is_absolute() or '..' in directory.parts:
        raise SiteConfigError('计数状态目录无法安全识别')
    for mount in sorted(record.get('Mounts', []), key=lambda row: len(row['Destination']), reverse=True):
        target = PurePosixPath(mount['Destination'])
        if directory == target or target in directory.parents:
            source = Path(mount['Source'])
            path = source.joinpath(*directory.relative_to(target).parts)
            if (mount.get('Type') != 'bind' or not source.is_absolute()
                    or any(part.is_symlink() for part in (path, *path.parents))):
                raise SiteConfigError('计数状态目录必须使用可核验的持久绑定挂载')
            return path
    raise SiteConfigError('算法容器缺少计数状态持久挂载')


def count_snapshot(directory):
    if directory is None:
        return []
    if not directory.is_dir() or directory.is_symlink():
        raise SiteConfigError('计数状态持久目录不可用')
    rows = []
    for path in sorted(directory.glob('conf_*.sqlite3')):
        if not re.fullmatch(r'conf_[1-9][0-9]*\.sqlite3', path.name):
            continue
        sidecars = [Path(str(path) + suffix) for suffix in ('-wal', '-shm')]
        if path.is_symlink() or not path.is_file() or any(item.is_symlink() for item in sidecars):
            raise SiteConfigError('计数状态文件无法安全核验')
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
            row = connection.execute('SELECT conf_id,boundary,entered,exited,revision FROM counter WHERE singleton=1').fetchone()
        if row:
            rows.append(list(row))
    return rows


class LiveController:
    def __init__(self, root, require_running=True, retain_old_ip=False):
        if not isinstance(retain_old_ip, bool):
            raise SiteConfigError('旧地址证书保留选项必须为布尔值')
        self.retain_old_ip = retain_old_ip
        self.root = Path(root).absolute()
        self.manager = SiteManager(self.root)
        compose = unique_json((self.root / 'container/compose.json').read_bytes())
        self.specs = compose['services']
        if not self.specs or any(s.get('network_mode') != 'host' for s in self.specs.values()):
            raise SiteConfigError('此控制器仅支持已验证的容器 host 网络部署')
        self.names = {s['container_name']: role for role, s in self.specs.items()}
        if len(self.names) != len(self.specs):
            raise SiteConfigError('平台容器名称重复')
        records = self.records()
        self.running_roles = set()
        self.counts_dir = None
        if set(records) != set(self.names):
            raise SiteConfigError('平台容器不完整')
        for name, record in records.items():
            role = self.names[name]
            labels = record['Config'].get('Labels') or {}
            if labels.get('com.docker.compose.project') != 'aiplatform':
                raise SiteConfigError('容器不属于此平台')
            if record['State']['Running']:
                self.running_roles.add(role)
            elif require_running and role != 'algorithm-master':
                raise SiteConfigError('存在未运行的容器，先核对现状')
            mounts = record.get('Mounts', [])
            if not any(m['Source'] == str(self.root / 'Config_files') and m['Destination'] == FIXED + '/Config_files' for m in mounts):
                raise SiteConfigError('平台配置目录挂载不匹配')
            if role == 'algorithm-master':
                self.counts_dir = count_directory(record)
        self.before_ids = {name: row['Id'] for name, row in records.items()}
        self.cert_changes = {}
        self.affected = []
        self.database_changed = False

    def records(self):
        rows = json.loads(run(['docker', 'inspect'] + list(self.names)))
        records = {row['Name'].lstrip('/'): row for row in rows}
        if len(records) != len(rows):
            raise SiteConfigError('平台容器状态存在重复记录')
        return records

    def _running(self, context):
        # Older receipts were produced only when every service was running.
        roles = set(context.get('running_roles', self.specs))
        if not roles <= set(self.specs):
            raise SiteConfigError('维护记录包含未知容器角色')
        return roles

    def _active_local_tasks(self, before):
        return [str(row[0]) for row in before.get('task_bindings', [])
                if str(row[3]) == '1' and str(row[1]) == str(before['computing_id'])]

    def _algorithm_health(self, expected):
        path = self.root.parent / 'platform_runtime_health/health.json'
        try:
            health = unique_json(path.read_bytes())
            tasks = {str(task['conf_id']): task for task in health['tasks']}
            if time.time() - health['epoch'] < 15 and all(tasks.get(i, {}).get('healthy') for i in expected):
                return {i: tasks[i].get('progress', []) for i in expected}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    @staticmethod
    def _address_request(action, old, new, before):
        return {'action': action, 'old': old, 'new': new, 'computing_id': before.get('computing_id'),
                'host_uid': before.get('host_uid'), 'identity_source': before.get('identity_source')}

    def inside(self, role, source, request=None):
        arguments = ['docker', 'exec', self.specs[role]['container_name'], FIXED + '/runtime/bin/python', '-c', source]
        if request is not None:
            arguments.append(json.dumps(request))
        return unique_json(run(arguments, timeout=40))

    def snapshot(self):
        applied = unique_json(self.manager.path(STATE).read_bytes())['applied']
        data = self.inside('backend', DATABASE, {'action': 'read', 'old': applied['node']['address']})
        data['counts'] = count_snapshot(self.counts_dir)
        protected = [Path('/etc/machine-id'), self.root / 'Config_files/platform-security.json']
        protected += list((self.root / 'config_dispatch/tls/ca').glob('*'))
        protected += list((self.root / 'platform_gateway/tls').glob('*.key'))
        protected += list((self.root / 'config_dispatch/tls').glob('*.key'))
        data['protected'] = {str(p): sha(p.read_bytes()) for p in protected if p.is_file()}
        return data

    def prepare(self, plan):
        before = self.snapshot()
        expected = self._active_local_tasks(before) if 'algorithm-master' in self.running_roles else []
        if expected and self._algorithm_health(expected) is None:
            raise SiteConfigError('本机运行任务缺少可核验的算法健康数据，未切换平台配置')
        affected = set()
        for change in plan['changes']:
            path = change['path']
            if path.startswith(('platform_algorithm_start/', 'model_algorithm_package/')):
                affected.add('algorithm-master')
            elif path.startswith('platform_gateway/') or path in ('Config_files/config.js', 'Config_files/secure-transport.js'):
                affected.add('web')
            elif path == 'Config_files/config.ini':
                affected.update(('backend', 'algorithm-master'))
            elif path == 'Config_files/kafka.properties':
                affected.add('kafka')
            elif path == 'Config_files/zlk/config.ini':
                affected.add('media')
            elif path == 'config_dispatch/security-settings.json':
                affected.add('dispatch')
            elif path.startswith('config_dispatch/gateway/'):
                affected.add('dispatch-web')
        cert_backup = []
        if plan['generation'] == 0:
            affected.update(('dispatch', 'backend'))  # Load guards and persistent identity adapters.
        if plan['node_changed']:
            addresses = run(['hostname', '-I']).split()
            if plan['node'] not in addresses:
                raise SiteConfigError('新业务 IP 尚未配置到本机；未修改网卡或平台')
            if before.get('identity_source') == 'legacy_ip':
                from platform_host_identity import read_host_identity
                if (plan['previous_node'] not in addresses
                        or before['host_uid'] != read_host_identity()['host_uid']):
                    raise SiteConfigError('原业务地址与本机机器码无法核验，未绑定服务器')
            from platform_site_certificates import plan_certificates, build_certificates
            packet = plan_certificates(self.root, plan['previous_node'], plan['node'], retain_old_ip=self.retain_old_ip)
            self.cert_changes = build_certificates(packet)['changes']
            folder = self.root / 'platform_ops/backups'
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            import tempfile
            backup = Path(tempfile.mkdtemp(prefix='site-cert-', dir=str(folder)))
            backup.chmod(0o700)
            for index, (name, value) in enumerate(self.cert_changes.items()):
                path = Path(name)
                path.relative_to(self.root)
                destination = backup / ('%03d.bin' % index)
                old = path.read_bytes() if path.exists() else None
                if old is not None:
                    atomic(destination, old)
                cert_backup.append({'path': name, 'backup': str(destination) if old is not None else None,
                                    'before': sha(old) if old is not None else None, 'after': sha(value)})
            affected.update(('backend', 'algorithm-master', 'web', 'dispatch', 'dispatch-web', 'media', 'kafka'))
        self.affected = sorted(affected & self.running_roles)
        return {'before': before, 'affected': self.affected, 'container_ids': self.before_ids,
                'running_roles': sorted(self.running_roles), 'certificates': cert_backup}

    def syntax(self):
        for role, relative in [('web', 'platform_gateway'), ('dispatch-web', 'config_dispatch/gateway')]:
            if role in self.affected:
                run(['docker', 'exec', self.specs[role]['container_name'], FIXED + '/runtime/bin/nginx',
                     '-t', '-p', FIXED + '/' + relative + '/', '-c', FIXED + '/' + relative + '/nginx.conf'])

    def restart(self, roles):
        # Restart existing containers, preserving their image, mounts and writable layer.
        for role in ('kafka', 'media', 'backend', 'dispatch', 'web', 'dispatch-web', 'algorithm-master'):
            if role in roles:
                run(['docker', 'restart', '-t', '40', self.specs[role]['container_name']], timeout=100)

    def activate(self, plan, context):
        records = self.records()
        if ({name: row['Id'] for name, row in records.items()} != context['container_ids']
                or {self.names[name] for name, row in records.items() if row['State']['Running']} != self._running(context)):
            raise SiteConfigError('容器在切换前已更换或启停，未重启容器')
        for name, value in self.cert_changes.items():
            path = Path(name)
            atomic(path, value, path.stat() if path.exists() else None)
        if plan['node_changed']:
            # Persisted intent is already in the core journal before this commit.
            request = self._address_request('address', plan['previous_node'], plan['node'], context['before'])
            self.inside('backend', DATABASE, request)
            self.database_changed = True
        self.syntax()
        self.restart(self.affected)

    def restore(self, plan, context):
        self.affected = sorted(set(context['affected']) & self._running(context))
        for record in context['certificates']:
            path = Path(record['path'])
            current = sha(path.read_bytes()) if path.exists() else None
            if current == record['after']:
                if record['backup']:
                    atomic(path, Path(record['backup']).read_bytes(), path.stat())
                elif path.exists():
                    path.unlink()
            elif current != record['before']:
                raise SiteConfigError('证书已被外部修改，未覆盖')
        if plan['node_changed']:
            self.restart(['backend'])
            request = self._address_request('restore_address', plan['node'], plan['previous_node'], context['before'])
            self.inside('backend', DATABASE, request)
        self.restart(self.affected)
        self.verify(dict(plan, node=plan['previous_node']), context)

    def verify(self, plan, context):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=str(self.root / 'config_dispatch/tls/ca/root.crt'))))
        deadline = time.monotonic() + 140
        checks = {}
        baseline = None
        running = self._running(context)
        expected = self._active_local_tasks(context['before']) if 'algorithm-master' in running else []
        while time.monotonic() < deadline:
            try:
                records = self.records()
                checks['container_ids_unchanged'] = {name: row['Id'] for name, row in records.items()} == context['container_ids']
                checks['containers_healthy'] = all(
                    (row['State']['Running'] and row['State'].get('Health', {}).get('Status', 'healthy') == 'healthy')
                    if self.names[name] in running else not row['State']['Running'] for name, row in records.items())
                for port, path, key in [(8888, '/', 'platform'), (8899, '/login', 'dispatch'), (8888, '/api/captcha', 'captcha')]:
                    with opener.open('https://' + plan['node'] + ':' + str(port) + path, timeout=5) as response:
                        body = response.read()
                        checks[key] = response.status == 200 and (body.startswith(b'\x89PNG') if key == 'captcha' else len(body) > 100)
                if expected:
                    current = self._algorithm_health(expected)
                    checks['tasks_healthy'] = current is not None
                    checks['inference_advanced'] = current is not None and baseline is not None and all(
                        any(new > old for new, old in zip(current[i], baseline[i])) for i in expected)
                    if baseline is None and current is not None:
                        baseline = current
                after = self.snapshot()
                checks['business_and_identity_preserved'] = all(after[k] == context['before'][k] for k in ('business_sha256', 'computing_id', 'host_uid', 'task_bindings', 'protected'))
                counts = {row[0]: row for row in after['counts']}
                checks['durable_counts_preserved'] = all(row[0] in counts and counts[row[0]][1] == row[1]
                    and all(new >= old for new, old in zip(counts[row[0]][2:], row[2:])) for row in context['before']['counts'])
                if all(checks.values()):
                    return {'ok': True, 'checks': checks, 'counter_records': len(counts),
                            'stopped_roles': sorted(set(self.specs) - running)}
            except Exception:
                pass
            time.sleep(2)
        raise SiteConfigError('应用后检查未通过：' + ','.join(k for k, value in checks.items() if not value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=FIXED)
    sub = parser.add_subparsers(dest='action', required=True)
    initial = sub.add_parser('import'); initial.add_argument('--address', required=True)
    sub.add_parser('plan')
    apply = sub.add_parser('apply'); apply.add_argument('--plan-id', required=True)
    rollback = sub.add_parser('rollback'); rollback.add_argument('--backup', required=True)
    args = parser.parse_args()
    manager = SiteManager(args.root)
    try:
        if args.action == 'import':
            result = manager.initialize(args.address)
        elif args.action == 'plan':
            result = manager.plan()[0]
        elif args.action == 'apply':
            runtime = LiveController(args.root)
            result = manager.apply(args.plan_id, prepare=runtime.prepare, activate=runtime.activate,
                                   verify=runtime.verify, restore=runtime.restore)
        else:
            runtime = LiveController(args.root, require_running=False)
            result = manager.rollback(args.backup, restore=runtime.restore)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SiteConfigError as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    except Exception as error:
        print(json.dumps({'ok': False, 'error': '内部校验未通过，详细配置未输出',
                          'error_type': type(error).__name__}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
