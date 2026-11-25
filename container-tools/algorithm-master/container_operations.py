"""Host maintenance bridge for offline Compose image upgrades and rollback.

Installed as platform_ops/upgrade_operations.py for container deployments only.
Business containers never receive the Docker socket or a host command endpoint.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import tarfile
import threading
import time
import uuid
import zipfile

try:
    import fcntl
except ImportError:
    fcntl = None

INSTALL_ROOT = Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parent.parent)))
STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', str(INSTALL_ROOT / 'platform_ops/state')))
ROOT = STATE / 'upgrades'
UPLOADS = Path(os.environ.get('CONTAINER_IMAGE_CACHE', str(ROOT / 'uploads')))
PROJECT = Path(os.environ.get('CONTAINER_PROJECT_DIR', str(INSTALL_ROOT / 'container')))
MAX_UPLOAD = 64 * 1024 ** 3
CHUNK_BYTES = 4 * 1024 ** 2
ACTIVE = ('validating', 'backing_up', 'applying', 'health_check', 'rolling_back')
IMAGE_ROLES = ('application', 'middleware', 'algorithm')
TAG = re.compile(r'^aiplatform/[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
LOCK = threading.RLock()


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def ident(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('维护任务ID无效')
    return value


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b''):
            value.update(block)
    return value.hexdigest()


def run(args, timeout=1200):
    return subprocess.check_output([str(a) for a in args], stderr=subprocess.STDOUT,
                                   timeout=timeout, universal_newlines=True)


def compose(*args):
    return run(['docker', 'compose', '--project-directory', PROJECT,
                '-f', PROJECT / 'compose.json'] + list(args))


def acquire():
    ROOT.mkdir(parents=True, exist_ok=True)
    handle = (ROOT / 'maintenance.lock').open('a+')
    if fcntl:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise ValueError('已有维护操作正在执行')
    return handle


def architecture():
    name = platform.machine().lower()
    return {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(name, name)


def jobs():
    return sorted([read(path) for path in (ROOT / 'jobs').glob('*.json')],
                  key=lambda row: row.get('updated_epoch', 0), reverse=True)


def phase(job, status, message, action=None, state='done', **fields):
    job.update(status=status, message=message, updated_at=now(), updated_epoch=time.time(), **fields)
    if action:
        job.setdefault('steps', []).append({'action': action, 'state': state, 'at': now()})
    atomic(ROOT / 'jobs' / (ident(job['id']) + '.json'), job)


def current_release():
    return read(STATE / 'release.json', read(PROJECT / 'images.json',
        {'release': 'container', 'runtime': 'container', 'images': {}}))


def container_rows():
    output = compose('ps', '--all', '--format', 'json').strip()
    if not output:
        return []
    if output.startswith('['):
        return json.loads(output)
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def health(services):
    deadline = time.monotonic() + 180
    while True:
        rows = {row['Service']: row for row in container_rows()}
        if all(name in rows and rows[name].get('State') == 'running' and
               rows[name].get('Health', '') in ('', 'healthy') for name in services):
            return
        if time.monotonic() >= deadline:
            raise ValueError('容器健康检查未通过')
        time.sleep(3)


def apply_images(images):
    """Change image references only: binds, ports and all persistent data stay fixed."""
    document = read(PROJECT / 'compose.json')
    affected = []
    for name, service in document['services'].items():
        role = service.get('labels', {}).get('com.aiplatform.image-role', 'application')
        if role in images and service['image'] != images[role]:
            service['image'] = images[role]
            affected.append(name)
    atomic(PROJECT / 'compose.json', document)
    if affected:
        compose('up', '-d', '--no-deps', '--pull', 'never', '--force-recreate', *affected)
        health(affected)
    return affected


def restore_snapshot(snapshot):
    """Restore image references and version metadata, without copying site data."""
    previous = snapshot['release']
    document = snapshot['compose']
    current = read(PROJECT / 'compose.json', {'services': {}})
    affected = [name for name, service in document['services'].items()
                if current['services'].get(name, {}).get('image') != service['image']]
    atomic(PROJECT / 'compose.json', document)
    # A failed recreation may already have restored compose.json before it died.
    affected = sorted(set(affected) | set(snapshot.get('affected_services', [])))
    if affected:
        compose('up', '-d', '--no-deps', '--pull', 'never', '--force-recreate', *affected)
        health(affected)
    atomic(STATE / 'release.json', previous)
    atomic(PROJECT / 'images.json', previous)


@contextlib.contextmanager
def package_entries(path):
    if zipfile.is_zipfile(str(path)):
        with zipfile.ZipFile(str(path)) as archive:
            entries = {item.filename: item for item in archive.infolist() if not item.is_dir()}
            if len(entries) != len([i for i in archive.infolist() if not i.is_dir()]):
                raise ValueError('升级包存在同名文件')
            yield entries, lambda name: archive.open(entries[name])
    else:
        with tarfile.open(str(path), 'r:*') as archive:
            members = archive.getmembers()
            if any(not item.isfile() and not item.isdir() for item in members):
                raise ValueError('升级包不允许链接或特殊文件')
            entries = {item.name: item for item in members if item.isfile()}
            if len(entries) != len([i for i in members if i.isfile()]):
                raise ValueError('升级包存在同名文件')
            yield entries, lambda name: archive.extractfile(entries[name])


def validate_manifest(manifest):
    if manifest.get('schema') != 'platform-container' or manifest.get('schema_version') != 1:
        raise ValueError('请选择platform-container镜像升级包')
    if manifest.get('architecture') != architecture():
        raise ValueError('升级包架构与服务器不匹配')
    if not isinstance(manifest.get('release'), str) or not manifest['release'].strip():
        raise ValueError('升级包缺少版本号')
    images = manifest.get('images')
    if not isinstance(images, dict) or not images or set(images) - set(IMAGE_ROLES):
        raise ValueError('升级包镜像角色无效')
    archives = []
    for role, row in images.items():
        if not isinstance(row, dict) or not TAG.fullmatch(row.get('tag', '')):
            raise ValueError('镜像标签必须属于aiplatform命名空间并包含版本')
        name = row.get('archive', '')
        parsed = PurePosixPath(name)
        if not name.startswith('images/') or '..' in parsed.parts or parsed.is_absolute() or '\\' in name:
            raise ValueError('镜像归档路径无效')
        if not re.fullmatch('[a-f0-9]{64}', row.get('sha256', '')):
            raise ValueError('镜像缺少SHA256')
        archives.append(name)
    if len(set(archives)) != len(archives):
        raise ValueError('每个镜像归档只能声明一次；共享同一镜像时声明application角色')
    return images


def validate(job):
    try:
        folder = UPLOADS / ident(job['upload_id'])
        with package_entries(folder / 'package') as (entries, open_member):
            if 'manifest.json' not in entries:
                raise ValueError('升级包缺少manifest.json')
            with open_member('manifest.json') as stream:
                manifest = json.loads(stream.read(1024 * 1024).decode('utf-8'))
            images = validate_manifest(manifest)
            if any(row['tag'] in current_release().get('images', {}).values() for row in images.values()):
                raise ValueError('升级必须使用新镜像版本标签，当前生效的标签保持不变')
            declared = {'manifest.json'} | {row['archive'] for row in images.values()}
            if set(entries) != declared:
                raise ValueError('升级包包含清单外文件或缺少镜像')
            extracted = folder / 'images'
            extracted.mkdir(exist_ok=True)
            for role, row in images.items():
                target = extracted / (role + '.tar')
                checksum = hashlib.sha256()
                with open_member(row['archive']) as source, target.open('wb') as output:
                    for block in iter(lambda: source.read(CHUNK_BYTES), b''):
                        checksum.update(block)
                        output.write(block)
                if checksum.hexdigest() != row['sha256']:
                    raise ValueError('镜像SHA256不一致：' + role)
                # The offline Docker archive must import only its declared tag.
                with tarfile.open(str(target), 'r:*') as image_archive:
                    saved = json.load(image_archive.extractfile('manifest.json'))
                    if not isinstance(saved, list) or len(saved) != 1:
                        raise ValueError('每个镜像归档必须只包含一个镜像：' + role)
                    tags = {tag for part in saved for tag in (part.get('RepoTags') or [])}
                    if tags != {row['tag']}:
                        raise ValueError('镜像归档标签与升级清单不一致：' + role)
                    config = image_archive.extractfile(saved[0]['Config']).read()
                    metadata = json.loads(config.decode('utf-8'))
                    expected_arch = 'arm64' if architecture() == 'aarch64' else 'amd64'
                    if metadata.get('architecture') != expected_arch or metadata.get('os') != 'linux':
                        raise ValueError('镜像归档架构与服务器不匹配：' + role)
                    image_id = 'sha256:' + hashlib.sha256(config).hexdigest()
                    if row.get('image_id') and row['image_id'] != image_id:
                        raise ValueError('镜像配置ID与清单不一致：' + role)
                    row['image_id'] = image_id
                try:
                    old = json.loads(run(['docker', 'image', 'inspect', row['tag']]))[0]
                except subprocess.CalledProcessError:
                    old = None
                if old and old['Id'] != image_id:
                    raise ValueError('镜像版本标签已被其他内容占用：' + role)
            job.update(release=manifest['release'], manifest=manifest,
                previous_release=current_release(), components=[{'role': role, 'type': 'image',
                    'image': row['tag'], 'image_id': row['image_id'], 'file': row['archive']} for role, row in images.items()],
                preview={'changes': [{'role': role, 'image': row['tag'], 'image_id': row['image_id'],
                                      'type': 'image', 'file': row['archive']} for role, row in images.items()],
                         'restart_services': [name for name, service in read(PROJECT / 'compose.json')['services'].items()
                             if service.get('labels', {}).get('com.aiplatform.image-role', 'application') in images],
                         'protected_paths': ['数据库', 'Config_files', 'outputs', '算法任务配置', '现场授权和证书'],
                         'verification_steps': ['镜像归档SHA256与架构', '镜像标签', '容器启动及健康检查']})
            atomic(folder / 'plan.json', {'job_id': job['id']})
            phase(job, 'ready', '镜像升级包校验通过，请核对涉及服务后执行', 'validate')
    except Exception as error:
        phase(job, 'failed', str(error)[:300], 'validate', 'failed')


def apply_job(job):
    try:
        handle = acquire()
    except ValueError:
        phase(job, 'failed', '已有维护操作正在执行，镜像未切换', 'lock', 'failed')
        return
    previous = current_release()
    old_compose = read(PROJECT / 'compose.json')
    affected = []
    snapshot = {'release': previous, 'compose': old_compose, 'affected_services': []}
    backup = ROOT / 'backups' / ident(job['id']) / 'deployment.json'
    try:
        atomic(backup, snapshot)
        job['backup_path'] = str(backup)
        if job['operation'] == 'rollback':
            target = job['target_release']
            phase(job, 'rolling_back', '正在恢复上一镜像版本', 'rollback', 'running')
        else:
            phase(job, 'applying', '正在导入离线镜像', 'load', 'running')
            for role, row in job['manifest']['images'].items():
                run(['docker', 'image', 'load', '-i', UPLOADS / job['upload_id'] / 'images' / (role + '.tar')])
                inspection = json.loads(run(['docker', 'image', 'inspect', row['tag']]))[0]
                expected_arch = 'arm64' if architecture() == 'aarch64' else 'amd64'
                if inspection.get('Architecture') != expected_arch:
                    raise ValueError('加载的镜像架构不匹配')
                if row.get('image_id') and inspection['Id'] != row['image_id']:
                    raise ValueError('加载的镜像ID与清单不一致')
            target = {'release': job['release'], 'images': dict(previous.get('images', {})), 'runtime': 'container'}
            target['images'].update({role: row['tag'] for role, row in job['manifest']['images'].items()})
        phase(job, 'health_check', '正在重建涉及容器并验证健康状态', 'restart', 'running')
        affected = [name for name, service in old_compose['services'].items()
                    if target['images'].get(service.get('labels', {}).get('com.aiplatform.image-role', 'application'),
                                            service['image']) != service['image']]
        snapshot['affected_services'] = affected
        atomic(backup, snapshot)
        affected = apply_images(target['images'])
        target = dict(target, updated_at=now(), source='upgrade' if job['operation']=='upgrade' else 'rollback',
                      last_operation_id=job['id'])
        if job['operation'] == 'upgrade':
            target['job_id'] = job['id']
        atomic(STATE / 'release.json', target)
        atomic(PROJECT / 'images.json', target)
        phase(job, 'completed', '镜像版本切换完成，容器检查通过', 'health', previous_release=previous,
              affected_services=affected, rollback_eligible=job['operation']=='upgrade')
    except Exception as error:
        recovered = False
        try:
            restore_snapshot(snapshot)
            recovered = True
        except Exception:
            pass
        phase(job, 'failed', '镜像切换失败，已恢复原版本' if recovered else '镜像切换失败，请检查容器状态',
              'recovery', 'done' if recovered else 'failed', recovered=recovered,
              error_type=type(error).__name__, error=str(error)[:500])
    finally:
        handle.close()


def native_status():
    current = current_release()
    entries = jobs()
    current_job = next((job for job in entries if job['id'] == current.get('job_id')), None)
    active = any(job['status'] in ACTIVE for job in entries)
    eligible = current_job if current_job and current_job.get('status') == 'completed' and current_job.get('previous_release') and not active else None
    try:
        containers = container_rows()
    except (OSError, subprocess.SubprocessError):
        containers = []
    services = []
    for role, name in (('backend','ai-platform-backend'),('web','ai-platform-web'),('media','ai-platform-media')):
        row = next((item for item in containers if item.get('Service') == role), {})
        running = row.get('State') == 'running' and row.get('Health','') in ('','healthy')
        services.append({'name':name,'version':current.get('release','container'),
                         'running':running,'status':'active' if running else 'inactive'})
    for job in entries:
        job['rollback_eligible'] = bool(eligible and job['id']==eligible['id'])
        job['rollback_block_reason'] = '' if job['rollback_eligible'] else '仅当前生效的镜像版本可回退'
    history = [{key: job.get(key) for key in ('id','operation','release','previous_release','created_at','updated_at','status','components')}
               for job in entries if job['status'] in ('completed','failed')]
    for row in history:
        row['current'] = row['id'] == current.get('last_operation_id', current.get('job_id'))
    return {'runtime':'container','release':current,'current_version':current,
        'previous_version':eligible.get('previous_release') if eligible else None,
        'rollback_job_id':eligible['id'] if eligible else None,
        'rollback_block_reason':'' if eligible else '暂无可回退的镜像升级版本',
        'version_history':history[:50],'architecture':architecture(),'services':services,'containers':containers,
        'jobs':entries[:20],'max_upload_bytes':MAX_UPLOAD,'backup_ready':PROJECT.is_dir(),
        'package_schema':'platform-container','supported_package_schemas':['platform-container'],
        'manual_rollback_supported':True,'database_migrations_supported':False,
        'capabilities':[{'role':'application','type':'image','label':'离线镜像版本更新'}],
        'package_examples':examples(),'data_policy':'切换镜像版本，保留数据库、配置、授权、算法任务和历史媒体'}


def examples():
    return {'container_images':{'schema':'platform-container','schema_version':1,'release':'V3.0.1-container',
        'architecture':architecture(),'images':{'application':{'tag':'aiplatform/application:3.0.1',
        'archive':'images/application.tar','sha256':'0'*64}}}}


def recover_interrupted_jobs():
    ROOT.mkdir(parents=True, exist_ok=True)
    handle = acquire()
    try:
        for job in jobs():
            if job.get('status') not in ACTIVE:
                continue
            snapshot = read(ROOT / 'backups' / ident(job['id']) / 'deployment.json')
            recovered = job.get('status') == 'validating'
            error = ''
            if snapshot:
                try:
                    restore_snapshot(snapshot)
                    recovered = True
                except Exception as failure:
                    error = str(failure)[:500]
            phase(job, 'failed', '维护进程曾中断，已恢复原镜像版本' if recovered else
                  '维护进程曾中断，请核对当前镜像及容器后重新操作',
                  'interrupted', 'done' if recovered else 'failed', recovered=recovered, error=error)
    finally:
        handle.close()


def upload_chunk(upload_id, offset, raw):
    with LOCK:
        folder = UPLOADS / ident(upload_id)
        upload = read(folder / 'upload.json', {})
        if not upload or upload.get('finished') or int(offset) != upload['received']:
            raise ValueError('上传分片状态或顺序无效')
        if not raw or len(raw)>CHUNK_BYTES or upload['received']+len(raw)>upload['size']:
            raise ValueError('上传分片大小无效')
        with (folder / 'package').open('ab') as stream:
            stream.write(raw)
        upload['received'] += len(raw)
        atomic(folder / 'upload.json', upload)
        return 200, {'code':200,'data':{'received':upload['received']}}


def dispatch(method,path,body=None):
    body = body or {}
    if method=='GET' and path in ('/upgrade/status','/upgrade/capabilities'):
        return 200,{'code':200,'data':native_status()}
    if method=='GET' and path=='/upgrade/examples':
        return 200,{'code':200,'data':examples()}
    if method=='GET' and re.fullmatch('/upgrade/jobs/[a-f0-9]{32}',path):
        job=read(ROOT/'jobs'/(path.rsplit('/',1)[-1]+'.json'))
        return (200,{'code':200,'data':{'job':job}}) if job else (404,{'code':404,'msg':'升级任务不存在'})
    if method=='GET' and re.fullmatch('/upgrade/uploads/[a-f0-9]{32}',path):
        upload=read(UPLOADS/path.rsplit('/',1)[-1]/'upload.json')
        return (200,{'code':200,'data':upload}) if upload else (404,{'code':404,'msg':'上传不存在'})
    if method=='POST' and path=='/upgrade/uploads':
        size=int(body.get('size',0));filename=body.get('filename','')
        if not filename.lower().endswith(('.tar','.tar.gz','.tgz','.zip')) or not 0<size<=MAX_UPLOAD:
            raise ValueError('请选择不超过64GiB的镜像升级包')
        upload_id=uuid.uuid4().hex
        atomic(UPLOADS/upload_id/'upload.json',{'id':upload_id,'filename':Path(filename).name,
            'size':size,'received':0,'finished':False,'expected_sha256':body.get('sha256')})
        return 200,{'code':200,'data':{'upload_id':upload_id,'chunk_bytes':CHUNK_BYTES}}
    if method=='POST' and re.fullmatch('/upgrade/uploads/[a-f0-9]{32}/finish',path):
        folder=UPLOADS/ident(path.split('/')[3]);upload=read(folder/'upload.json',{})
        if not upload or upload['received']!=upload['size']:
            raise ValueError('升级包尚未上传完整')
        checksum=digest(folder/'package')
        if upload.get('expected_sha256') and upload['expected_sha256']!=checksum:
            raise ValueError('升级包整体SHA256不一致')
        upload.update(finished=True,sha256=checksum);atomic(folder/'upload.json',upload)
        return 200,{'code':200,'data':upload}
    if method=='POST' and path in ('/upgrade/plan','/upgrade/apply','/upgrade/rollback'):
        handle=acquire()
        try:
            if any(job['status'] in ACTIVE for job in jobs()):
                raise ValueError('已有维护任务正在执行')
            if path=='/upgrade/rollback':
                state=native_status();source=next((j for j in jobs() if j['id']==body.get('job_id')),None)
                if not source or state['rollback_job_id']!=source['id']:
                    raise ValueError('该镜像版本不可回退')
                target=source['previous_release']
                job={'id':uuid.uuid4().hex,'operation':'rollback','created_at':now(),'steps':[],
                     'release':target['release'],'target_release':target,'components':source['components'],
                     'previous_release':current_release()}
                phase(job,'backing_up','已提交镜像回退任务')
            else:
                upload_id=ident(body.get('upload_id'));folder=UPLOADS/upload_id
                if not read(folder/'upload.json',{}).get('finished'):
                    raise ValueError('升级包尚未完成上传')
                if path=='/upgrade/plan':
                    job={'id':uuid.uuid4().hex,'operation':'upgrade','upload_id':upload_id,'created_at':now(),'steps':[],'components':[]}
                    phase(job,'validating','正在校验离线镜像包')
                else:
                    plan=read(folder/'plan.json',{});job=read(ROOT/'jobs'/(ident(plan.get('job_id'))+'.json'),{})
                    if job.get('status')!='ready':raise ValueError('请先完成镜像包预检')
                    phase(job,'backing_up','已提交镜像切换任务')
        finally:
            handle.close()
        threading.Thread(target=validate if path=='/upgrade/plan' else apply_job,args=(job,),daemon=True).start()
        return 200,{'code':200,'data':{'job':job}}
    return 404,{'code':404,'msg':'容器维护操作不存在'}
