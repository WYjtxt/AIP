#!/usr/bin/env python3
"""Install the offline multi-image platform with persistent host data."""
import configparser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import secrets
import shlex
import shutil
import socket
import ssl
import subprocess
import tarfile
import time
import urllib.request
import uuid

from container_runtime import ROOT, build_compose, persistent_paths, algorithm_environment
from data_root import normalize_data_root


HOST_SERVICES = ('platform-ops', 'platform-push-worker', 'platform-alarm-storage', 'platform-host-disks.timer')
FORWARD_ENV = ('TARGET_IP', 'MYSQL_ROOT_PASS', 'MYSQL_ADMIN_PASS', 'BOX_USER', 'BOX_PASS',
               'BOOTSTRAP_SSH_USER', 'BOOTSTRAP_SSH_PASSWORD', 'ADMIN_8899_USER', 'ADMIN_8899_PASS')


def run(args, env=None, text=None, check=True, timeout=1800):
    result = subprocess.run([str(a) for a in args], input=text, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(str(args[0]) + ' ' + str(args[1] if len(args) > 1 else '') +
                           ' failed: ' + (result.stderr or result.stdout)[-1800:])
    return result


def write(path, value, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')
    path.chmod(mode)


def atomic_json(path, value, mode=0o600):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n', mode)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def arch_name(value):
    return {'arm64':'aarch64', 'amd64':'x86_64'}.get(value.strip(), value.strip())


def load_manifest(path, stage, arch, include_full=True):
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    selected = manifest.get('architectures', {}).get(arch)
    if not selected or not selected.get('images'):
        raise ValueError('镜像清单缺少当前架构：' + arch)
    records = [row for row in manifest.get('common_files', []) + selected.get('files', [])
               if include_full or row.get('scope') != 'full']
    for record in records:
        relative = Path(record['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('镜像清单路径无效')
        artifact = Path(stage) / relative
        if not artifact.is_file() or artifact.stat().st_size != int(record['size']):
            raise ValueError('镜像介质缺失或大小不一致：' + str(relative))
        if sha256(artifact) != record['sha256'].lower():
            raise ValueError('镜像介质SHA256不一致：' + str(relative))
    return manifest, selected, records


def install_engine(stage, records):
    if not shutil.which('docker'):
        archive = next((Path(stage)/r['path'] for r in records
                        if Path(r['path']).name.startswith('docker-') and r['path'].endswith('.tgz')), None)
        if archive is None:
            raise ValueError('离线安装包缺少Docker引擎')
        with tarfile.open(str(archive)) as package:
            for item in package:
                if item.isfile() and Path(item.name).parent.as_posix() == 'docker':
                    target = Path('/usr/local/bin') / Path(item.name).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with package.extractfile(item) as source, target.open('wb') as destination:
                        shutil.copyfileobj(source, destination)
                    target.chmod(0o755)
    if run(['docker', 'compose', 'version'], check=False).returncode:
        binary = next((Path(stage)/r['path'] for r in records if Path(r['path']).name == 'docker-compose'), None)
        if binary is None:
            raise ValueError('离线安装包缺少Docker Compose')
        target = Path('/usr/local/lib/docker/cli-plugins/docker-compose')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(binary), str(target));target.chmod(0o755)
    daemon = Path('/etc/docker/daemon.json')
    if not daemon.exists():
        Path('/home/AIGO/container-runtime/docker').mkdir(parents=True, exist_ok=True)
        atomic_json(daemon, {'data-root':'/home/AIGO/container-runtime/docker'}, 0o644)
    service = Path('/etc/systemd/system/docker.service')
    if not service.exists() and not Path('/usr/lib/systemd/system/docker.service').exists() and not Path('/lib/systemd/system/docker.service').exists():
        executable = shutil.which('dockerd') or '/usr/local/bin/dockerd'
        write(service, '[Unit]\nDescription=Docker Engine\nAfter=network-online.target\nWants=network-online.target\n'
              '[Service]\nType=notify\nExecStart=' + executable + '\nRestart=always\nRestartSec=3\n'
              'Delegate=yes\nLimitNOFILE=1048576\nLimitNPROC=infinity\nTasksMax=infinity\n'
              '[Install]\nWantedBy=multi-user.target\n')
    run(['systemctl','daemon-reload']);run(['systemctl','enable','--now','docker'])
    run(['docker','info'], timeout=60);run(['docker','compose','version'], timeout=30)


def compose(root, *args, **kwargs):
    return run(['docker','compose','--project-directory',Path(root)/'container', '-f',
                Path(root)/'container/compose.json'] + list(args), **kwargs)


def load_images(stage, selected, records, arch):
    for record in records:
        relative = record['path'].replace('\\','/')
        if relative.startswith('packages/container/') and relative.endswith(('.tar','.tar.gz','.tgz')):
            print('导入离线镜像：' + Path(relative).name, flush=True)
            run(['docker','load','-i',Path(stage)/relative], timeout=3600)
    images = selected['images']
    if not all(role in images for role in ('application','middleware','algorithm')):
        raise ValueError('发布清单应包含application、middleware与algorithm镜像')
    for tag in images.values():
        actual = run(['docker','image','inspect','--format','{{.Architecture}}',tag]).stdout.strip()
        if arch_name(actual) != arch:
            raise ValueError('镜像架构不匹配：' + tag)
    return images


def copy_from_image(container, source, target, required=False):
    target = Path(target)
    if target.exists() or target.is_symlink():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run(['docker','cp',str(container)+':'+str(source),target], check=False)
    if result.returncode:
        if required:
            raise ValueError('干净镜像缺少初始化模板：' + str(source))
        return False
    return True


def seed(root, image):
    root = Path(root);root.mkdir(parents=True, exist_ok=True)
    ident = run(['docker','create',image,'/bin/true']).stdout.strip()
    paths = persistent_paths()
    try:
        for relative in paths['directories']:
            target = root/relative
            copy_from_image(ident, ROOT/relative, target)
            target.mkdir(parents=True, exist_ok=True)
        for relative in paths['files']:
            if not copy_from_image(ident, ROOT/relative, root/relative) and not (root/relative).exists():
                write(root/relative, '{}\n' if relative.endswith('.json') else '')
        # A clean switch may preseed TLS to retain the host's trusted CA.
        copy_from_image(ident,ROOT/'platform_gateway/default.conf',root/'platform_gateway/default.conf',required=True)
        for name in ('platform_ops/platform_ops_server.py','platform_ops/push_operations.py',
                     'platform_ops/push_outbox.py','platform_ops/push_worker.py','platform_ops/storage_operations.py',
                     'platform_algorithm_start/templates/alarm_directory.py'):
            copy_from_image(ident, ROOT/name, root/name)
        for name in paths['shared']:
            (root.parent/name).mkdir(parents=True, exist_ok=True)
    finally:
        run(['docker','rm',ident], check=False)


def family_and_devices():
    from native_initial_device import detect_driver_family
    family = detect_driver_family()
    if family == 'unknown':return 'none', []
    patterns = ('davinci[0-9]*','davinci_manager','devmm_svm','hisi_hdc') if family == 'huawei' else ('bm-sophon[0-9]*','bmdev-ctl')
    devices = sorted({str(path) for pattern in patterns for path in Path('/dev').glob(pattern)})
    return family, devices


def one_shot(root, env, code):
    options=[]
    for key in FORWARD_ENV:
        if key in env:options += ['-e',key]
    if env.get('TARGET_ARCH') == 'x86_64':
        openssl=Path(env.get('ONECLICK_ROOT','/root/oneclick'))/'packages/container-tools/x86_64/openssl'
        if not openssl.is_file():raise ValueError('缺少x86离线证书工具：'+str(openssl))
        openssl.chmod(0o755)
        options += ['--volume',str(openssl)+':/usr/bin/openssl:ro']
    prefix="""import os,sys
from pathlib import Path
sys.path.insert(0,'/opt/ai-platform')
from container_runtime import ROOT,aliases,configuration_links,render_target_ip
aliases(os.environ.get('PLATFORM_HOST_ROOT',str(ROOT)))
configuration_links()
render_target_ip('backend',os.environ.get('TARGET_IP'))
os.environ['PLATFORM_SECURITY_CONFIG']=str(ROOT/'Config_files/platform-security.json')
os.environ['HOST_MACHINE_ID']=Path('/etc/machine-id').read_text().strip()
"""
    result = compose(root, 'run','--rm','-T','--no-deps',*options,'backend',str(ROOT/'runtime/bin/python'),
                     '-B','-c',prefix+code, env=dict(os.environ,**env))
    if result.stdout.strip():print(result.stdout.strip(), flush=True)
    return result


def middleware_defaults(root,target_ip):
    base=PurePosixPath(root.as_posix() if hasattr(root,'as_posix') else str(root))
    mysql=base/'mysql'
    return {
        'mysql.cnf':('[mysqld]\nuser=root\nbasedir='+str(base/'runtime/mysql')+'\ndatadir='+str(mysql)+
            '\nsocket='+str(mysql/'mysql.sock')+'\npid-file='+str(mysql/'mysqld.pid')+
            '\nlog-error='+str(mysql/'mysqld.log')+'\nport=3306\nbind-address=0.0.0.0\n'
            'lower_case_table_names=1\ncharacter-set-server=utf8mb4\n[client]\nsocket='+str(mysql/'mysql.sock')+'\n'),
        'redis.conf':('bind 127.0.0.1\nprotected-mode yes\nport 6379\ndaemonize no\ndir '+str(base/'redis')+
            '\nappendonly no\nlogfile ""\n'),
        'kafka.properties':('process.roles=broker,controller\nnode.id=1\n'
            'controller.quorum.voters=1@127.0.0.1:9093\nlisteners=PLAINTEXT://:9092,CONTROLLER://:9093\n'
            'advertised.listeners=PLAINTEXT://'+target_ip+':9092\ninter.broker.listener.name=PLAINTEXT\n'
            'controller.listener.names=CONTROLLER\nlistener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT\n'
            'log.dirs='+str(base/'kafka/kraft-combined-logs')+'\nnum.partitions=1\n'
            'offsets.topic.replication.factor=1\ntransaction.state.log.replication.factor=1\n'
            'transaction.state.log.min.isr=1\ngroup.initial.rebalance.delay.ms=0\n')}


def configure_inside(root, env, new_site):
    import inspect
    from deploy_native import certificates
    from native_frontend_fixes import (model_upload_layout_script, MODEL_UPLOAD_LAYOUT_MARKER,
                                       recorder_form_script, RECORDER_FORM_MARKER, refresh_certificate_help)
    from native_playback_recovery import playback_recovery_script, update_config_source
    code = """
import configparser,os,secrets,sys
from pathlib import Path
sys.path.insert(0,'/opt/ai-platform')
from container_runtime import ROOT,aliases
aliases(os.environ.get('PLATFORM_HOST_ROOT',str(ROOT)))
import deploy_native as native
exec(__CERTIFICATES_FUNCTION__,native.__dict__)
import native_frontend_fixes as frontend_fixes
exec(__CERTIFICATE_HELP_FUNCTION__,frontend_fixes.__dict__)
for folder in ('Config_files','model_algorithm_package','platform_algorithm_start/config','platform_gateway','config_dispatch'):
 for path in (ROOT/folder).rglob('*'):
  if path.is_file() and not path.is_symlink() and path.suffix in ('.py','.ini','.conf','.json','.cnf','.js','.sh') and path.stat().st_size<12*1024*1024:
   try:source=path.read_text(encoding='utf-8')
   except UnicodeError:continue
   if '__PLATFORM_TARGET_IP__' in source:path.write_text(source.replace('__PLATFORM_TARGET_IP__',os.environ['TARGET_IP']),encoding='utf-8')
native.rewrite_sources(ROOT,os.environ['TARGET_IP'],('Config_files','model_algorithm_package','platform_algorithm_start','platform_gateway','config_dispatch'))
native.configure(ROOT,os.environ['TARGET_IP'],dict(os.environ),__NEW__)
defaults=__MIDDLEWARE_DEFAULTS__
for name,source in defaults.items():
 path=ROOT/'Config_files'/name
 if not path.exists():path.write_text(source,encoding='utf-8')
for folder in ('mysql','redis','kafka/kraft-combined-logs','logs/kafka'):(ROOT/folder).mkdir(parents=True,exist_ok=True)
settings=configparser.ConfigParser(interpolation=None);settings.read(str(ROOT/'Config_files/config.ini'),encoding='utf-8')
settings['database']['DB_HOST']='127.0.0.1'
with (ROOT/'Config_files/config.ini').open('w',encoding='utf-8') as stream:settings.write(stream)
dispatch_ca=ROOT/'config_dispatch/dispatch-root-ca.cer'
if dispatch_ca.is_symlink():dispatch_ca.unlink()
native.certificates(ROOT,os.environ['TARGET_IP'])
native.gateways(ROOT,str(ROOT/'runtime/bin/nginx'))
token=ROOT/'config_dispatch/state/bootstrap.token'
if not (ROOT/'config_dispatch/state/auth.sqlite3').exists() and not token.exists():
 token.write_text(secrets.token_hex(32));token.chmod(0o600)
from native_ffmpeg import verify
verify(ROOT)
config_js=ROOT/'Config_files/config.js'
__PLAYBACK_SOURCE_FUNCTION__
source=config_js.read_text(encoding='utf-8')
if __MODEL_LAYOUT_MARKER__ not in source:
 config_js.write_text(source+'\\n'+__MODEL_LAYOUT_SCRIPT__,encoding='utf-8')
if __RECORDER_FORM_MARKER__ not in source:
 config_js.write_text(config_js.read_text(encoding='utf-8')+'\\n'+__RECORDER_FORM_SCRIPT__,encoding='utf-8')
source=config_js.read_text(encoding='utf-8')
updated=update_config_source(source,__PLAYBACK_RECOVERY_SCRIPT__)
if updated!=source:config_js.write_text(updated,encoding='utf-8')
""".replace('__NEW__', repr(bool(new_site))).replace('__MIDDLEWARE_DEFAULTS__',repr(middleware_defaults(ROOT,env['TARGET_IP']))).replace('__CERTIFICATES_FUNCTION__',repr(inspect.getsource(certificates))).replace('__CERTIFICATE_HELP_FUNCTION__',repr(inspect.getsource(refresh_certificate_help))).replace('__MODEL_LAYOUT_MARKER__',repr(MODEL_UPLOAD_LAYOUT_MARKER)).replace('__MODEL_LAYOUT_SCRIPT__',repr(model_upload_layout_script())).replace('__RECORDER_FORM_MARKER__',repr(RECORDER_FORM_MARKER)).replace('__RECORDER_FORM_SCRIPT__',repr(recorder_form_script())).replace('__PLAYBACK_SOURCE_FUNCTION__',inspect.getsource(update_config_source)).replace('__PLAYBACK_RECOVERY_SCRIPT__',repr(playback_recovery_script()))
    one_shot(root,env,code)


def initialize_database(root, env):
    from install_native_dependencies import sql_literal
    bootstrap_source = (Path(__file__).resolve().parent / 'bootstrap_platform_admin.py').read_text(encoding='utf-8')
    compose(root,'exec','-T','mysql',str(ROOT/'runtime/mysql/bin/mysql'),'--no-defaults','--version')
    base = ['exec','-T','-e','MYSQL_PWD','mysql',str(ROOT/'runtime/mysql/bin/mysql'),
            '--no-defaults','-uroot','--socket='+str(ROOT/'mysql/mysql.sock')]
    def query(sql,password):
        return compose(root,*base,env=dict(os.environ,MYSQL_PWD=password),text="SET SESSION sql_mode='';\n"+sql,check=False)
    password=env['MYSQL_ROOT_PASS']
    if query('SELECT 1;','').returncode==0:
        if query("ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY "+sql_literal(password)+';', '').returncode:
            raise ValueError('容器MySQL初始账号创建失败')
    elif query('SELECT 1;',password).returncode:
        raise ValueError('容器MySQL现有口令不匹配，数据库已保留')
    admin=env.get('MYSQL_ADMIN_PASS') or password
    sql=("CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED WITH caching_sha2_password BY "+sql_literal(password)+
         "; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;\n"
         "CREATE USER IF NOT EXISTS 'admin'@'%' IDENTIFIED WITH mysql_native_password BY "+sql_literal(admin)+
         "; GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%';\n"
         "CREATE DATABASE IF NOT EXISTS seal_system CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
    if query(sql,password).returncode:raise ValueError('容器数据库初始化失败')
    one_shot(root,env,"""
import os,sys
from pathlib import Path
sys.path.insert(0,'/opt/ai-platform')
root=Path('/data/AIGO/platform_start')
os.chdir(str(root/'backend'));sys.path.insert(0,str(root/'backend'))
for name in ('sync_reference_database.py','bootstrap_platform_admin.py','migrate_admin_menu_permissions.py'):
 source=(__BOOTSTRAP_SOURCE__ if name=='bootstrap_platform_admin.py' else (Path('/opt/ai-platform')/name).read_text(encoding='utf-8')).replace('/Seal_system',str(root/'backend')).replace('/tmp/oneclick-reference.json','/opt/ai-platform/reference-47/database.json').replace('/tmp/oneclick-initial-admin.json',str(root/'Config_files/initial-access.json'))
 exec(compile(source,name,'exec'),{'__name__':'__main__'})
""".replace('__BOOTSTRAP_SOURCE__', repr(bootstrap_source)))
    credentials=Path(root)/'Config_files/initial-access.json'
    alias=Path(root)/'initial-access.json'
    if credentials.is_file() and not alias.exists() and not alias.is_symlink():alias.symlink_to(credentials)


def initialize_content(root, env, family, phase):
    one_shot(root,env,"""
import os,sys
from pathlib import Path
sys.path.insert(0,'/opt/ai-platform')
import native_initial_content as content
from container_runtime import ROOT,aliases
aliases(os.environ.get('PLATFORM_HOST_ROOT',str(ROOT)))
content.detect_driver_family=lambda:__FAMILY__
content.initialize(ROOT,Path('/opt/ai-platform/preinstalled_models'),__PHASE__)
""".replace('__FAMILY__',repr('unknown' if family=='none' else family)).replace('__PHASE__',repr(phase)))


def health(root, services=None, timeout=240):
    document=json.loads((Path(root)/'container/compose.json').read_text(encoding='utf-8'))
    selected=services or list(document['services'])
    deadline=time.monotonic()+timeout
    while True:
        output=compose(root,'ps','--all','--format','json').stdout.strip()
        rows=json.loads(output) if output.startswith('[') else [json.loads(line) for line in output.splitlines() if line]
        rows={row['Service']:row for row in rows}
        pending={name:{'state':rows.get(name,{}).get('State','missing'),'health':rows.get(name,{}).get('Health','')}
                 for name in selected if name not in rows or rows[name].get('State')!='running' or rows[name].get('Health','') not in ('','healthy')}
        if not pending:return
        if time.monotonic()>=deadline:raise ValueError('容器健康检查未通过：'+json.dumps(pending,ensure_ascii=False))
        time.sleep(3)


def install_host_forwarders(root, family, project='aiplatform'):
    root=Path(root)
    docker=shutil.which('docker') or '/usr/local/bin/docker'
    from native_ffmpeg import media_environment
    base_environment=media_environment(ROOT)
    base_environment['PLATFORM_NATIVE_ROOT']=str(ROOT)
    base_environment['PLATFORM_SECURITY_CONFIG']=str(ROOT/'Config_files/platform-security.json')
    base_options=' '.join('-e '+shlex.quote(key+'='+value) for key,value in base_environment.items())
    for name in ('python','ffmpeg','ffprobe'):
        inside=ROOT/'runtime/bin'/name
        write(root/'runtime/bin'/name,'#!/bin/sh\n# AI_PLATFORM_CONTAINER_FORWARDER_V1\nexec '+shlex.quote(docker)+
              ' exec -i '+base_options+' -w '+shlex.quote(str(ROOT/'backend'))+' '+shlex.quote(project+'-backend')+' '+shlex.quote(str(inside))+' "$@"\n',0o755)
    if family!='none':
        env=algorithm_environment(family)
        options=' '.join('-e '+shlex.quote(k+'='+v) for k,v in env.items())
        relative='runtime/sophon-python/bin/python' if family=='sophon' else 'runtime/miniconda3/envs/yolo/bin/python'
        source='#!/bin/sh\n# AI_PLATFORM_CONTAINER_FORWARDER_V1\nexec '+shlex.quote(docker)+' exec -i '+options+' -w '+shlex.quote(str(ROOT/'platform_algorithm_start'))+' '+shlex.quote(project+'-algorithm-master')+' '+shlex.quote(str(ROOT/relative))+' "$@"\n'
        write(root/relative,source,0o755)
    from native_ffmpeg import install_host_commands
    install_host_commands(root)


def storage_adapter(source, project):
    start=source.index('    def backend_probe(');end=source.index('    def media_probe(',start)
    replacement='''    def backend_probe(self, slot, expected, config_path):
        code = 'import os,json; p=' + repr(str(slot)) + '; s=os.stat(p); print(json.dumps([s.st_dev,s.st_ino]))'
        seen = json.loads(self.run(['docker','exec',__CONTAINER__,__PYTHON__,'-B','-c',code]))
        if seen != expected:
            raise StorageError(409, '目标挂载尚未同步到后端，未切换写入目录')

'''.replace('__CONTAINER__',repr(project+'-backend')).replace('__PYTHON__',repr(str(ROOT/'runtime/bin/python')))
    return source[:start]+replacement+source[end:]


def install_host_operations(root, pay, env, project='aiplatform'):
    from native_host_features import render,native_host_disks,unit_arg
    root,pay=Path(root),Path(pay);ops=root/'platform_ops';ops.mkdir(parents=True,exist_ok=True)
    reference=pay/'reference-47'
    for name in ('platform_ops_server.py','push_operations.py','push_outbox.py','push_worker.py','storage_operations.py'):
        source=(reference/'data/platform_ops'/name).read_text(encoding='utf-8')
        if name=='storage_operations.py':source=storage_adapter(source,project)
        rendered=render(source,root,env['TARGET_IP'])
        rendered=rendered.replace(str(root/'runtime/nginx/conf/nginx.conf'),str(root/'platform_gateway/nginx.conf'))
        write(ops/name,rendered)
    write(ops/'upgrade_operations.py',(pay/'container_operations.py').read_text(encoding='utf-8'))
    collector=(reference/'usr/local/sbin/platform-host-disks.py').read_text(encoding='utf-8')
    write(ops/'platform-host-disks.py',render(native_host_disks(collector),root,env['TARGET_IP']))
    key_file=ops/'server.json'
    old=json.loads(key_file.read_text(encoding='utf-8')) if key_file.is_file() else {}
    key=old.get('key')
    if not isinstance(key,str) or len(key)<48:key=secrets.token_urlsafe(48)
    for name in ('server.json','backend-client.json'):atomic_json(ops/name,{'key':key})
    shared=root.parent/'platform_storage/alarm-volumes';shared.mkdir(parents=True,exist_ok=True)
    if run(['mountpoint','-q',shared],check=False).returncode:run(['mount','--bind',shared,shared])
    run(['mount','--make-shared',shared])
    write(ops/'container-storage.py',"""import subprocess
from pathlib import Path
from storage_operations import StorageManager
slot=Path(__SLOT__)
slot.mkdir(parents=True,exist_ok=True)
if subprocess.call(['mountpoint','-q',str(slot)]):subprocess.run(['mount','--bind',str(slot),str(slot)],check=True)
subprocess.run(['mount','--make-shared',str(slot)],check=True)
StorageManager().restore()
""".replace('__SLOT__',repr(str(shared))))
    common=('WorkingDirectory='+str(ops).replace('%','%%')+'\nUser=root\nEnvironment=PYTHONDONTWRITEBYTECODE=1\n'+
            ''.join('Environment='+unit_arg(k+'='+str(v))+'\n' for k,v in {
                'PLATFORM_NATIVE_ROOT':root,'PLATFORM_OPS_STATE_DIR':ops/'state',
                'PLATFORM_OPS_SERVER_CONFIG':ops/'server.json','CONTAINER_PROJECT_DIR':root/'container',
                'CONTAINER_IMAGE_CACHE':'/home/AIGO/container-upgrades'}.items()))
    python=shutil.which('python3') or '/usr/bin/python3'
    units={'platform-ops':('platform_ops_server.py','',True),
           'platform-push-worker':('push_worker.py','',True),
           'platform-alarm-storage':('container-storage.py','',False),
           'platform-host-disks':('platform-host-disks.py','',False)}
    for name,(script,extra,long_running) in units.items():
        body='[Unit]\nDescription=AI platform container host operations\nAfter=network.target docker.service\n[Service]\nType='+('simple' if long_running else 'oneshot')+'\n'+common
        body+='ExecStart='+unit_arg(python)+' '+unit_arg(ops/script)+extra+'\n'
        if long_running:body+='Restart=on-failure\nRestartSec=3\n'
        elif name=='platform-alarm-storage':body+='RemainAfterExit=yes\n'
        body+='[Install]\nWantedBy=multi-user.target\n'
        write(Path('/etc/systemd/system')/(name+'.service'),body)
    write('/etc/systemd/system/platform-host-disks.timer','[Unit]\nDescription=Platform host disk collection\n[Timer]\nOnBootSec=10s\nOnUnitActiveSec=60s\nUnit=platform-host-disks.service\n[Install]\nWantedBy=timers.target\n')
    run(['systemctl','daemon-reload']);run(['systemctl','enable']+list(HOST_SERVICES))
    run(['systemctl','restart']+list(HOST_SERVICES))


def complete_storage(root,pay,family):
    from native_host_features import render
    root,pay=Path(root),Path(pay)
    source=render((pay/'complete_alarm_storage.py').read_text(encoding='utf-8'),root,'127.0.0.1')
    source=source.replace(str(root/'runtime/nginx/conf/nginx.conf'),str(root/'platform_gateway/nginx.conf'))
    helper=root/'platform_ops/complete_alarm_storage.py'
    write(helper,source,0o700)
    command=[shutil.which('python3') or '/usr/bin/python3',helper,'--install','--wait-seconds','60']
    if family=='none':command.append('--runtime-unavailable')
    result=run(command,timeout=150)
    if result.stdout.strip():print(result.stdout.strip(),flush=True)


def backup_native(root,env):
    root=Path(root);state=root/'native-deployment.json'
    if not state.is_file():return None,[]
    record=json.loads(state.read_text(encoding='utf-8'))
    if Path(record['root']).resolve()!=root.resolve():raise ValueError('原生部署记录与所选目录不一致')
    backup=root.parent/'platform-backups'/('before-container-'+time.strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True,mode=0o700)
    dump=record['dependencies'].get('mysqldump')
    if dump:
        result=run([dump,'--no-defaults','-uroot','--single-transaction','--all-databases'],
                   env=dict(os.environ,MYSQL_PWD=env['MYSQL_ROOT_PASS']))
        write(backup/'mysql.sql',result.stdout,0o600)
    for relative in ('Config_files','config_dispatch/state','platform_gateway','platform_ops','native-deployment.json'):
        source=root/relative;target=backup/relative
        if source.is_dir():shutil.copytree(str(source),str(target),symlinks=True)
        elif source.is_file():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(source),str(target))
    active=[];enabled=[]
    for name in record.get('services',[]):
        unit=Path('/etc/systemd/system')/((name[:-8] if name.endswith('.service') else name)+'.service')
        if unit.is_file() and str(root) in unit.read_text(encoding='utf-8') and run(['systemctl','is-active','--quiet',name],check=False).returncode==0:
            active.append(name)
        if unit.is_file() and str(root) in unit.read_text(encoding='utf-8') and run(['systemctl','is-enabled','--quiet',name],check=False).returncode==0:
            enabled.append(name)
    atomic_json(backup/'transition.json',{'root':str(root),'active_services':active,'enabled_services':enabled,'database_dumped':bool(dump)})
    if active:run(['systemctl','stop']+active)
    return backup,active


def stop_native_units(root):
    """Prevent old units from starting against the new container forwarding scripts."""
    names=('ai-platform-backend','ai-platform-web','ai-platform-media','config-dispatch',
           'config-dispatch-gateway','ai-platform-mysql','ai-platform-redis','ai-platform-kafka',
           'model_start','resource','kafka_consumer')
    owned=[]
    for name in names:
        path=Path('/etc/systemd/system')/(name+'.service')
        if path.is_file():
            text=path.read_text(encoding='utf-8')
            if str(root)+'/' in text or 'WorkingDirectory='+str(root)+'\n' in text:owned.append(name)
    if owned:run(['systemctl','disable','--now']+owned)
    return owned


def restore_native_configuration(root,backup,active):
    for folder in ('Config_files','config_dispatch/state','platform_gateway','platform_ops'):
        source=Path(backup)/folder
        if source.is_dir():
            for path in source.rglob('*'):
                target=Path(root)/folder/path.relative_to(source)
                if path.is_dir():target.mkdir(parents=True,exist_ok=True)
                elif path.is_file() and not path.is_symlink():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(path),str(target))
    record=json.loads((Path(backup)/'transition.json').read_text(encoding='utf-8'))
    if record.get('enabled_services'):run(['systemctl','enable']+record['enabled_services'])
    if active:run(['systemctl','start']+active)


def verify(root):
    root=Path(root)
    record=json.loads((root/'container/images.json').read_text(encoding='utf-8'))
    health(root)
    context=ssl._create_unverified_context()
    for port,path in ((8888,'/'),(8888,'/api/activate/activate_verify'),(8899,'/login')):
        url='https://'+record['target_ip']+':'+str(port)+path
        with urllib.request.urlopen(url,context=context,timeout=10) as response:
            if response.status!=200:raise ValueError('平台入口检查失败')
        print('HTTP=200 '+url,flush=True)
    print('VERIFY_RESULT=PASS',flush=True)


def clean(root):
    from uninstall_platform import uninstall
    return uninstall(root, runtime='container')


def deploy(env):
    env=dict(env)
    root=Path(normalize_data_root(env.get('PLATFORM_DATA_ROOT','/data/AIGO/platform_start')))
    mode=env.get('MODE','repair')
    if mode=='verify':verify(root);return
    if mode=='clean':clean(root);return
    if mode not in ('fresh','repair','platform'):raise ValueError('不支持的部署模式')
    new_site=not (root/'Config_files/config.ini').is_file()
    if mode=='fresh' and not new_site:raise ValueError('所选目录已有平台配置，请选择repair或先备份清洗')
    if mode=='platform' and not (root/'container/images.json').is_file():raise ValueError('所选目录不是已安装的容器平台，请选择repair迁移')
    if not new_site:
        settings=configparser.ConfigParser(interpolation=None);settings.read(str(root/'Config_files/config.ini'),encoding='utf-8')
        env['MYSQL_ROOT_PASS']=settings['database']['DB_PASSWORD']
    arch=arch_name(env.get('TARGET_ARCH') or platform.machine())
    manifest_path=Path(env.get('CONTAINER_RELEASE_MANIFEST','/root/oneclick/payload/container-release.json'))
    pay=manifest_path.parent;stage=pay.parent
    manifest,selected,records=load_manifest(manifest_path,stage,arch,include_full=mode!='platform')
    install_engine(stage,records)
    images=load_images(stage,selected,records,arch)
    verified_baseline=(root/'container-deployment.json').is_file()
    previous_state=json.loads((root/'container/images.json').read_text(encoding='utf-8')) if verified_baseline and (root/'container/images.json').is_file() else None
    previous_compose=json.loads((root/'container/compose.json').read_text(encoding='utf-8')) if (root/'container/compose.json').is_file() else None
    backup,active=backup_native(root,env) if not (root/'container/images.json').is_file() else (None,[])
    from container_operations import backup_algorithm_programs, restore_algorithm_programs, sync_algorithm_programs
    program_backup=[]
    try:
        stopped_native=stop_native_units(root)
        if (root/'container/compose.json').is_file():compose(root,'stop')
        seed(root,images['application'])
        family,devices=family_and_devices()
        document=build_compose(str(root),images,family,devices=devices,target_ip=env['TARGET_IP'])
        atomic_json(root/'container/compose.json',document)
        state={'runtime':'container','release':manifest.get('release','container'),'images':images,'architecture':arch,
               'root':str(root),'target_ip':env['TARGET_IP'],'family':family,'installed_at':time.strftime('%Y-%m-%d %H:%M:%S'),
               'updated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        atomic_json(root/'container/images.json',state)
        atomic_json(root/'container/native-services.json',{'disabled_owned_services':stopped_native})
        if family!='none':
            program_backup=backup_algorithm_programs(root,root/'platform_ops/state/deployment-programs'/uuid.uuid4().hex,document)
        configure_inside(root,env,new_site)
        if family!='none':
            sync_algorithm_programs(root,images['algorithm'],document)
        install_host_operations(root,pay,env)
        compose(root,'up','-d','--remove-orphans','mysql','redis','kafka');health(root,['mysql','redis','kafka'])
        initialize_database(root,env)
        initialize_content(root,env,family,'device')
        compose(root,'up','-d','--remove-orphans');health(root)
        install_host_forwarders(root,family)
        initialize_content(root,env,family,'model')
        complete_storage(root,pay,family)
        from deploy_native import bootstrap_dispatch
        bootstrap_dispatch(env['TARGET_IP'],root,env)
        verify(root)
        atomic_json(root/'platform_ops/state/release.json',state)
        atomic_json(root/'container-deployment.json',state)
        print('DEPLOY_RESULT=PASS',flush=True)
    except Exception:
        restore_algorithm_programs(root,program_backup)
        if previous_state and previous_compose:
            atomic_json(root/'container/images.json',previous_state)
            atomic_json(root/'container/compose.json',previous_compose)
            compose(root,'up','-d','--remove-orphans')
        elif backup:
            compose(root,'down',check=False)
            restore_native_configuration(root,backup,active)
        raise


if __name__=='__main__':
    try:deploy(dict(os.environ))
    except Exception as error:
        print('[FAIL] '+str(error),flush=True)
        print('DEPLOY_RESULT=FAIL',flush=True)
        raise
