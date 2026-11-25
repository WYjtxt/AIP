"""Native code updates, version history and rollback to the previous version."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid
import zipfile

try:
    import fcntl
except ImportError:  # Enables isolated package tests on the Windows build host.
    fcntl = None

INSTALL_ROOT = Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parent.parent)))
STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', str(INSTALL_ROOT / 'platform_ops/state')))
ROOT = STATE / 'upgrades'
MAX_UPLOAD = 1024 ** 3
MAX_EXPANDED = 2 * 1024 ** 3
CHUNK_BYTES = 4 * 1024 ** 2
ACTIVE = ('validating', 'backing_up', 'applying', 'health_check', 'rolling_back')
SERVICES = {'backend': 'ai-platform-backend', 'frontend': 'ai-platform-web'}
PROTECTED = ['Config_files', 'mysql', 'redis', 'kafka', 'runtime', 'model_algorithm_package',
             'platform_algorithm_start', 'platform_gateway', 'platform_ops', 'outputs',
             'frontend/static/js/config.js', 'frontend/static/js/certificate-help.js',
             'frontend/static/certificates',
             'site authorization, certificates and configuration']
LOCK = threading.RLock()


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(str(temporary), 0o600)
    os.replace(str(temporary), str(path))


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def ident(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('升级任务编号无效')
    return value


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def acquire(wait_seconds=0):
    ROOT.mkdir(parents=True, exist_ok=True)
    handle = (ROOT / 'maintenance.lock').open('a+b')
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                raise ValueError('另一项维护操作正在执行，请稍后重试')
            time.sleep(0.2)
    return handle


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('升级包路径无效')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() in ('', '.'):
        raise ValueError('升级包包含越界路径')
    return path.as_posix()


def target_path(role, name):
    name = relative(name)
    if role not in SERVICES:
        raise ValueError('原生升级仅支持前端和后端代码')
    parts = PurePosixPath(name).parts
    if any(part.startswith('.') or part in ('__pycache__', 'backups', 'logs', 'flask_session') for part in parts):
        raise ValueError('不能更新运行数据或隐藏目录：' + role + '/' + name)
    if role == 'backend' and not name.endswith('.py'):
        raise ValueError('后端升级仅接收Python源代码，配置与授权文件必须保留')
    if role == 'frontend' and (parts[0] in ('Config_files', 'config') or
            name.startswith('static/certificates/') or name == 'static/js/certificate-help.js' or
            parts[-1] in ('config.js', 'config.ini') or Path(name).suffix.lower() in ('.key', '.pem', '.crt', '.ak')):
        raise ValueError('不能更新站点配置、授权或证书')
    base = (INSTALL_ROOT / role).resolve()
    target = base.joinpath(*parts)
    if target.is_symlink() or base not in target.resolve().parents:
        raise ValueError('目标文件越界或为站点软链接：' + role + '/' + name)
    if target.exists() and not target.is_file():
        raise ValueError('目标不是普通代码文件：' + role + '/' + name)
    return target


def extract(package, destination):
    destination.mkdir(parents=True, exist_ok=True)
    total, seen = 0, set()
    if zipfile.is_zipfile(str(package)):
        archive = zipfile.ZipFile(str(package))
        entries = [(entry.filename, entry.file_size, entry.is_dir(),
                    stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR), entry)
                   for entry in archive.infolist()]
        opener = archive.open
    else:
        archive = tarfile.open(str(package), 'r:*')
        entries = [(entry.name, entry.size, entry.isdir(), not (entry.isfile() or entry.isdir()), entry)
                   for entry in archive.getmembers()]
        opener = archive.extractfile
    try:
        if len(entries) > 20000:
            raise ValueError('升级包文件数量过多')
        for name, size, directory, special, entry in entries:
            name = relative(name.rstrip('/'))
            if special or name in seen:
                raise ValueError('升级包含软链接、特殊文件或重复路径')
            seen.add(name)
            if directory:
                continue
            total += size
            if total > MAX_EXPANDED:
                raise ValueError('升级包解压内容过大')
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with opener(entry) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    finally:
        archive.close()


def architecture():
    name = os.uname().machine if hasattr(os, 'uname') else os.environ.get('PROCESSOR_ARCHITECTURE', '')
    return {'arm64': 'aarch64', 'AMD64': 'x86_64', 'amd64': 'x86_64'}.get(name, name)


def job_path(job_id):
    return ROOT / 'jobs' / (ident(job_id) + '.json')


def phase(job, status, message, action=None, state='done', detail=None, **values):
    job.update(status=status, message=message, updated_at=now(), updated_epoch=time.time(), **values)
    if action:
        step = {'action': action, 'state': state, 'at': now()}
        if detail:
            step['detail'] = detail
        job.setdefault('steps', []).append(step)
    atomic(job_path(job['id']), job)


def check_package(upload_id, job):
    folder = ROOT / 'uploads' / ident(upload_id)
    upload = read(folder / 'upload.json', {})
    if not upload.get('finished') or digest(folder / 'package') != upload.get('sha256'):
        raise ValueError('上传未完成或升级包已发生变化')
    stage = ROOT / 'staging' / ident(job['id'])
    extract(folder / 'package', stage)
    manifest = read(stage / 'manifest.json', {})
    if manifest.get('schema') != 'platform-native' or manifest.get('schema_version') != 1:
        raise ValueError('请使用platform-native版本1原生代码升级包')
    if manifest.get('architecture') != architecture():
        raise ValueError('升级包架构与当前服务器不一致')
    release = manifest.get('release')
    if not isinstance(release, str) or not release.strip() or len(release) > 160:
        raise ValueError('升级版本名称无效')
    components = manifest.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('升级包未声明更新组件')
    actual, targets, roles = [], set(), set()
    for component in components:
        role = component.get('role')
        if role not in SERVICES or component.get('type') != 'patch' or role in roles:
            raise ValueError('组件必须是唯一的frontend/backend原生代码patch')
        roles.add(role)
        files = component.get('files')
        if not isinstance(files, list) or not files or len(files) > 10000:
            raise ValueError('组件更新文件清单无效')
        checked = []
        for item in files:
            name, package_name = relative(item.get('path')), relative(item.get('file'))
            target = target_path(role, name)
            identity = role + '/' + name
            if identity in targets:
                raise ValueError('升级目标文件重复：' + identity)
            targets.add(identity)
            source = stage.joinpath(*PurePosixPath(package_name).parts)
            checksum = item.get('sha256', '')
            if not re.fullmatch('[a-f0-9]{64}', checksum) or not source.is_file() or digest(source) != checksum:
                raise ValueError('升级文件SHA256校验失败：' + identity)
            current = digest(target) if target.is_file() else None
            if 'base_sha256' in item and item['base_sha256'] != current:
                raise ValueError('当前代码与升级包要求不一致：' + identity)
            if role == 'backend':
                compile(source.read_bytes(), identity, 'exec')
            checked.append({'path': name, 'file': package_name, 'sha256': checksum, 'base_sha256': current})
        actual.append({'role': role, 'type': 'patch', 'files': checked})
    services = [SERVICES[role] for role in ('backend', 'frontend') if role in roles]
    plan = {'schema': 'platform-native', 'release': release, 'architecture': architecture(),
            'stage': str(stage), 'components': actual, 'restart_services': services}
    atomic(folder / 'plan.json', dict(plan, job_id=job['id']))
    job.update(release=release, components=actual, preview={
        'restart_services': services, 'protected_paths': PROTECTED,
        'verification_steps': ['文件SHA256与目标架构', '现场代码基线',
                               '前端更新时备份index.html并刷新脚本缓存版本', '平台HTTP与后端业务状态', '算法进程保持运行'],
        'generated_files': ['frontend/index.html'] if 'frontend' in roles else [],
        'changes': [{'role': component['role'], 'files': component['files']} for component in actual]})
    return plan


def validate(job):
    handle = None
    try:
        handle = acquire()
        check_package(job['upload_id'], job)
        phase(job, 'ready', '升级包校验通过，请核对文件和服务范围后执行', 'validate')
    except Exception as error:
        phase(job, 'failed', str(error)[:500], 'validate', 'failed', error=str(error)[:500])
    finally:
        if handle:
            handle.close()


def run(args, timeout=120):
    return subprocess.run([str(item) for item in args], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout, check=True)


def start_worker(job):
    unit = 'ai-platform-native-upgrade-' + job['id']
    interpreter = INSTALL_ROOT / 'runtime/bin/python'
    run(['systemd-run', '--quiet', '--collect', '--unit=' + unit,
         '--property=Type=exec', '--property=UMask=0077',
         '--setenv=PLATFORM_NATIVE_ROOT=' + str(INSTALL_ROOT),
         '--setenv=PLATFORM_OPS_STATE_DIR=' + str(STATE),
         str(interpreter), '-B', str(Path(__file__).resolve()), 'worker', job['id']], timeout=30)


def model_pid():
    try:
        return run(['systemctl', 'show', 'model_start', '--property=MainPID', '--value'], 10).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ''


def health(services, previous_model_pid):
    for attempt in range(30):
        try:
            for service in services:
                run(['systemctl', 'is-active', '--quiet', service], 10)
            urls = [('https://127.0.0.1:8888/', False),
                    ('http://127.0.0.1:5000/activate/activate_verify', True)]
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
            for url, business_response in urls:
                with opener.open(url, timeout=5) as response:
                    if response.status != 200:
                        raise ValueError('平台HTTP健康检查失败')
                    if business_response and json.loads(response.read().decode('utf-8')).get('code') != 200:
                        raise ValueError('后端业务健康检查失败')
            if previous_model_pid not in ('', '0') and model_pid() != previous_model_pid:
                raise ValueError('算法启动进程发生变化')
            return {'services_running': services, 'http_checks': len(urls), 'algorithm_process_preserved': True}
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)


def planned_files(plan):
    for component in plan['components']:
        for item in component['files']:
            yield component['role'], item


def replace_file(source, target, mode):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name('.' + target.name + '.native-upgrade')
    try:
        shutil.copyfile(str(source), str(temporary))
        os.chmod(str(temporary), mode)
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()


def refresh_asset_versions():
    """Keep native_frontend_fixes cache semantics compatible with Python 3.7."""
    frontend = INSTALL_ROOT / 'frontend'
    index = frontend / 'index.html'
    source = index.read_text(encoding='utf-8')
    def version(match):
        url = urlsplit(match.group(2))
        if url.scheme or url.netloc or not url.path.endswith('.js'):
            return match.group(0)
        name = url.path[2:] if url.path.startswith('./') else url.path
        name = name.lstrip('/')
        if name in ('static/js/config.js', 'static/js/secure-transport.js'):
            return match.group(0)
        asset = frontend / name
        if not asset.is_file():
            return match.group(0)
        parameters = [(key, value) for key, value in parse_qsl(url.query, keep_blank_values=True) if key != 'v']
        parameters.append(('v', 'native-asset-' + digest(asset)[:12]))
        updated = urlunsplit(('', '', url.path, urlencode(parameters), url.fragment))
        return match.group(1) + updated + match.group(3)
    updated = re.sub(r'(\b(?:src|href)=["\'])([^"\']+)(["\'])', version, source)
    if updated != source:
        with index.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(updated)


def apply_job(job_id):
    job = read(job_path(job_id))
    if job.get('operation') == 'rollback':
        return rollback_job(job_id)
    try:
        handle = acquire(wait_seconds=30)
    except ValueError as error:
        phase(job, 'failed', '维护锁繁忙，代码未修改，请重新预检后重试',
              'acquire', 'failed', error=str(error), recovered=True)
        return
    backup = ROOT / 'backups' / ident(job_id)
    originals, changed = [], []
    previous_release = read(STATE / 'release.json')
    previous_pid = model_pid()
    services = []
    try:
        if job.get('status') != 'backing_up':
            raise ValueError('升级任务不处于可执行状态')
        plan = read(ROOT / 'uploads' / ident(job['upload_id']) / 'plan.json')
        if not plan or plan.get('job_id') != job_id or plan['architecture'] != architecture():
            raise ValueError('升级计划已变化，请重新预检')
        services = plan['restart_services']
        stage = Path(plan['stage'])
        planned = list(planned_files(plan))
        backup_targets = list(planned)
        if any(role == 'frontend' for role, item in planned) and not any(
                role == 'frontend' and item['path'] == 'index.html' for role, item in planned):
            index = target_path('frontend', 'index.html')
            backup_targets.append(('frontend', {'path': 'index.html', 'file': None,
                                   'base_sha256': digest(index) if index.exists() else None}))
        for role, item in backup_targets:
            target = target_path(role, item['path'])
            current = digest(target) if target.is_file() else None
            source = stage.joinpath(*PurePosixPath(item['file']).parts) if item['file'] else None
            if current != item['base_sha256'] or (source is not None and digest(source) != item['sha256']):
                raise ValueError('预检后的代码发生变化，请重新预检：' + role + '/' + item['path'])
            original = {'role': role, 'path': item['path'], 'existed': target.exists(), 'sha256': current,
                        'mode': stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644}
            if original['existed']:
                saved = backup / 'files' / role / item['path']
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(target), str(saved))
                if digest(saved) != current:
                    raise ValueError('代码备份校验失败：' + role + '/' + item['path'])
            originals.append(original)
        atomic(backup / 'files.json', originals)
        phase(job, 'applying', '代码备份完成，正在替换预检通过的文件', 'backup', backup_path=str(backup),
              operation='upgrade', previous_release=previous_release)
        for original, pair in zip(originals, planned):
            role, item = pair
            target = target_path(role, item['path'])
            replace_file(stage.joinpath(*PurePosixPath(item['file']).parts), target, original['mode'])
            changed.append(original)
            if digest(target) != item['sha256']:
                raise ValueError('更新后文件SHA256校验失败：' + role + '/' + item['path'])
        if any(role == 'frontend' for role, item in planned):
            if len(originals) > len(planned):
                changed.append(originals[-1])
            refresh_asset_versions()
        phase(job, 'applying', '代码已更新，正在重启受影响的平台服务', 'replace_files')
        for service in services:
            run(['systemctl', 'restart', service])
        phase(job, 'health_check', '正在检查平台服务与算法进程', 'restart_services')
        evidence = health(services, previous_pid)
        files = [dict(item, installed_sha256=digest(target_path(item['role'], item['path'])))
                 for item in originals]
        versions = component_versions(previous_release)
        for component in plan['components']:
            versions[component['role']] = plan['release']
        job['version_files'] = files
        atomic(STATE / 'release.json', {'release': plan['release'], 'runtime': 'native', 'updated_at': now(),
               'job_id': job_id, 'source': 'upgrade', 'component_versions': versions})
        phase(job, 'completed', '原生代码更新完成，服务检查通过', 'health_check', evidence=evidence)
    except Exception as error:
        message = str(error)[:500]
        recovered = not changed
        if changed:
            phase(job, 'rolling_back', '运行验证失败，正在恢复更新前代码', 'health_check', 'failed', error=message)
            try:
                for original in reversed(changed):
                    target = target_path(original['role'], original['path'])
                    if original['existed']:
                        replace_file(backup / 'files' / original['role'] / original['path'], target, original['mode'])
                    elif target.exists():
                        target.unlink()
                for service in services:
                    run(['systemctl', 'restart', service])
                health(services, previous_pid)
                if previous_release is not None:
                    atomic(STATE / 'release.json', previous_release)
                elif (STATE / 'release.json').exists():
                    (STATE / 'release.json').unlink()
                recovered = True
            except Exception as recovery_error:
                message += '; 代码恢复后服务验证失败：' + str(recovery_error)[:200]
        phase(job, 'failed', '升级失败，已恢复原代码' if recovered else '升级失败，需要检查备份与服务',
              'recovery', 'done' if recovered else 'failed', error=message,
              recovered=recovered, backup_path=str(backup))
    finally:
        handle.close()


def release_label(release):
    return (release or {}).get('release', 'native')


def component_versions(release):
    release = release or {}
    result = {'frontend': release_label(release), 'backend': release_label(release), 'media': 'native'}
    result.update(release.get('component_versions', {}))
    return result


def record_deployment(release):
    """A direct deployment is a new baseline, not a reversible code patch."""
    if not isinstance(release, str) or not release.strip() or len(release) > 160:
        raise ValueError('部署版本名称无效')
    handle = acquire()
    try:
        previous = read(STATE / 'release.json')
        job_id = uuid.uuid4().hex
        current = {'release': release, 'runtime': 'native', 'updated_at': now(), 'job_id': None,
                   'deployment_id': job_id, 'source': 'deployment',
                   'component_versions': {role: release for role in ('frontend', 'backend', 'media')}}
        atomic(STATE / 'release.json', current)
        job = {'id': job_id, 'operation': 'deployment', 'created_at': now(), 'steps': [],
               'release': release, 'previous_release': previous,
               'components': [{'role': role, 'type': 'deployment', 'files': []} for role in SERVICES]}
        phase(job, 'completed', '原生部署完成，已建立新的代码版本基线')
        return current
    finally:
        handle.close()


def rollback_source(job_id, verify_files=True):
    """Check the installed patch and its originals before allowing an undo."""
    job_id = ident(job_id)
    current = read(STATE / 'release.json', {})
    if current.get('job_id') != job_id:
        raise ValueError('只能回退当前生效的最近一次升级；请按版本顺序逐次回退')
    job = read(job_path(job_id), {})
    if job.get('status') != 'completed' or job.get('operation', 'upgrade') != 'upgrade':
        raise ValueError('该升级当前不处于可回退状态')
    files = job.get('version_files')
    if not files or 'previous_release' not in job:
        raise ValueError('旧升级缺少完整回退校验记录；新升级将自动保存可回退版本')
    backup = ROOT / 'backups' / job_id
    if not (backup / 'files.json').is_file() or read(backup / 'files.json') != [
            {key: value for key, value in item.items() if key != 'installed_sha256'} for item in files]:
        raise ValueError('升级备份清单缺失或发生变化，不能回退')
    if not verify_files:
        return job
    for item in files:
        target = target_path(item['role'], item['path'])
        current_sha = digest(target) if target.is_file() else None
        if current_sha != item.get('installed_sha256'):
            raise ValueError('当前代码已变化，不能覆盖现场修改：' + item['role'] + '/' + item['path'])
        saved = backup / 'files' / item['role'] / item['path']
        if item['existed'] and (not saved.is_file() or saved.is_symlink() or digest(saved) != item.get('sha256')):
            raise ValueError('原版本备份SHA256校验失败：' + item['role'] + '/' + item['path'])
    return job


def restore_files(files, backup):
    for item in reversed(files):
        target = target_path(item['role'], item['path'])
        if item['existed']:
            replace_file(backup / 'files' / item['role'] / item['path'], target, item['mode'])
        elif target.exists():
            target.unlink()


def restore_release(release):
    if release is not None:
        atomic(STATE / 'release.json', release)
    elif (STATE / 'release.json').exists():
        (STATE / 'release.json').unlink()


def rollback_job(job_id):
    job = read(job_path(job_id))
    try:
        handle = acquire(wait_seconds=30)
    except ValueError as error:
        phase(job, 'failed', '维护锁繁忙，代码未修改，请稍后重试回退',
              'acquire', 'failed', error=str(error), recovered=True)
        return
    backup = ROOT / 'backups' / ident(job_id)
    current_release = read(STATE / 'release.json')
    previous_pid, services, originals, changed = model_pid(), [], [], []
    try:
        if job.get('status') != 'backing_up':
            raise ValueError('回退任务不处于可执行状态')
        source = rollback_source(job['source_job_id'])
        services = source.get('preview', {}).get('restart_services', [])
        for item in source['version_files']:
            target = target_path(item['role'], item['path'])
            saved = backup / 'files' / item['role'] / item['path']
            original = {'role': item['role'], 'path': item['path'], 'existed': target.exists(),
                        'sha256': digest(target) if target.is_file() else None,
                        'mode': stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644}
            if original['existed']:
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(target), str(saved))
                if digest(saved) != original['sha256']:
                    raise ValueError('回退前代码备份校验失败')
            originals.append(original)
        atomic(backup / 'files.json', originals)
        phase(job, 'rolling_back', '当前版本已备份，正在恢复上一版本代码', 'backup', backup_path=str(backup))
        for item, original in zip(source['version_files'], originals):
            # Include a file before replacement so recovery also covers an interrupted write.
            changed.append(original)
            restore_files([item], ROOT / 'backups' / source['id'])
        if any(item['role'] == 'frontend' for item in source['version_files']):
            refresh_asset_versions()
        phase(job, 'rolling_back', '上一版本代码已恢复，正在重启受影响的平台服务', 'restore_files')
        for service in services:
            run(['systemctl', 'restart', service])
        phase(job, 'health_check', '正在检查回退后的平台服务与算法进程', 'restart_services')
        evidence = health(services, previous_pid)
        restored = dict(source.get('previous_release') or {'release': 'native', 'runtime': 'native'})
        restored.update(updated_at=now(), restored_at=now(), last_operation_id=job_id)
        atomic(STATE / 'release.json', restored)
        phase(source, 'rolled_back', '已回退到上一版本', rollback_job_id=job_id, rolled_back_at=now())
        phase(job, 'completed', '已回退到上一版本，服务检查通过', 'health_check', evidence=evidence)
    except Exception as error:
        message, recovered = str(error)[:500], not changed
        if changed:
            phase(job, 'rolling_back', '回退验证失败，正在恢复回退前版本',
                  'health_check', 'failed', error=message)
            try:
                restore_files(changed, backup)
                for service in services:
                    run(['systemctl', 'restart', service])
                health(services, previous_pid)
                restore_release(current_release)
                recovered = True
            except Exception as recovery_error:
                message += '; 恢复回退前版本失败：' + str(recovery_error)[:200]
        phase(job, 'failed', '回退失败，已保留回退前版本' if recovered else '回退失败，需要检查备份与服务',
              'recovery', 'done' if recovered else 'failed', error=message,
              recovered=recovered, backup_path=str(backup))
    finally:
        handle.close()


def upload_chunk(upload_id, offset, raw):
    with LOCK:
        folder = ROOT / 'uploads' / ident(upload_id)
        upload = read(folder / 'upload.json', {})
        if not upload or upload.get('finished'):
            raise ValueError('上传不存在或已经完成')
        if int(offset) != upload['received']:
            raise ValueError('上传分片顺序错误，请重新上传')
        if not raw or len(raw) > CHUNK_BYTES or upload['received'] + len(raw) > upload['size']:
            raise ValueError('上传分片大小错误')
        with (folder / 'package').open('ab') as stream:
            stream.write(raw)
        upload['received'] += len(raw)
        atomic(folder / 'upload.json', upload)
        return 200, {'code': 200, 'data': {'received': upload['received']}}


def jobs():
    result = [read(path) for path in (ROOT / 'jobs').glob('*.json')]
    return sorted(result, key=lambda item: (item.get('updated_epoch', 0), item.get('updated_at', '')), reverse=True)


def examples():
    sample = {'schema': 'platform-native', 'schema_version': 1, 'release': 'native-example',
              'architecture': architecture()}
    def component(role):
        path = 'service/example.py' if role == 'backend' else 'static/js/example.js'
        return {'role': role, 'type': 'patch', 'files': [{'path': path, 'file': 'files/' + role + '/' + path,
                'sha256': '0' * 64, 'base_sha256': None}]}
    return {name: dict(sample, components=[component(role) for role in roles]) for name, roles in (
        ('frontend_patch', ['frontend']), ('backend_patch', ['backend']), ('paired_patches', ['frontend', 'backend']))}


def native_status():
    current = read(STATE / 'release.json', {'release': 'native', 'runtime': 'native'})
    versions = component_versions(current)
    services = []
    for role, service in (('backend', 'ai-platform-backend'), ('frontend', 'ai-platform-web'),
                          ('media', 'ai-platform-media')):
        try:
            run(['systemctl', 'is-active', '--quiet', service], 10)
            running = True
        except (OSError, subprocess.SubprocessError):
            running = False
        services.append({'name': service, 'version': versions[role],
                         'running': running, 'status': 'active' if running else 'inactive'})
    history, entries, previous = [], jobs(), None
    rollback_reason = ('当前为一键部署基线；从后续网页升级开始保留可回退版本'
                       if current.get('source') == 'deployment' else '当前版本缺少完整回退记录；从新升级开始支持一键回退')
    active = any(item.get('status') in ACTIVE or item.get('status') == 'interrupted' for item in entries)
    for item in entries:
        item['operation'] = item.get('operation', 'upgrade')
        item['rollback_eligible'] = False
        if item['id'] == current.get('job_id') and item['operation'] == 'upgrade':
            try:
                source = rollback_source(item['id'], verify_files=False)
                if active:
                    raise ValueError('已有维护任务正在执行或需要核查')
                item['rollback_eligible'] = True
                item['rollback_block_reason'] = ''
                rollback_reason = ''
                previous = source.get('previous_release') or {'release': 'native', 'runtime': 'native'}
            except (ValueError, OSError) as error:
                item['rollback_block_reason'] = str(error)
                rollback_reason = str(error)
        elif item['operation'] == 'deployment':
            item['rollback_block_reason'] = '一键部署建立了新的代码基线；从后续网页升级开始保留回退版本'
        elif item['status'] == 'rolled_back':
            item['rollback_block_reason'] = '该升级已回退'
        elif not item.get('version_files'):
            item['rollback_block_reason'] = '旧升级缺少完整回退校验记录；从新升级开始支持一键回退'
        else:
            item['rollback_block_reason'] = '仅当前生效的最近一次升级可回退'
        if item.get('release') and item['status'] in ('completed', 'rolled_back', 'failed', 'interrupted'):
            history.append({key: item.get(key) for key in ('id', 'operation', 'release', 'created_at', 'updated_at',
                           'status', 'components', 'rollback_eligible', 'rollback_block_reason')})
            history[-1].update(previous_release=release_label(item.get('previous_release')),
                current=item['id'] == current.get('last_operation_id', current.get('job_id') or current.get('deployment_id')))
    visible = entries[:20]
    eligible = next((item for item in entries if item['rollback_eligible']), None)
    if eligible is not None and eligible not in visible:
        visible[-1:] = [eligible]
    return {'runtime': 'native', 'release': current, 'current_version': current, 'previous_version': previous,
            'rollback_job_id': eligible['id'] if eligible else None, 'rollback_block_reason': rollback_reason,
            'version_history': history[:50],
            'architecture': architecture(), 'services': services, 'containers': [], 'jobs': visible,
            'max_upload_bytes': MAX_UPLOAD, 'backup_ready': INSTALL_ROOT.is_dir(),
            'package_schema': 'platform-native', 'supported_package_schemas': ['platform-native'],
            'database_migrations_supported': False, 'manual_rollback_supported': True,
            'capabilities': [{'role': role, 'type': 'patch', 'label': label}
                             for role, label in (('frontend', '原生前端代码'), ('backend', '原生后端代码'))],
            'package_examples': examples(), 'data_policy': '只更新清单代码，保留配置、数据库、授权、算法进程和历史数据'}


def recover_interrupted_jobs():
    ROOT.mkdir(parents=True, exist_ok=True)
    for job in jobs():
        if job.get('status') not in ACTIVE:
            continue
        if job['status'] == 'validating':
            phase(job, 'failed', '升级包预检曾中断，代码未修改，请重新预检', 'validate', 'failed', recovered=True)
            continue
        if job['status'] != 'validating':
            try:
                run(['systemctl', 'is-active', '--quiet', 'ai-platform-native-upgrade-' + job['id']], 10)
                continue
            except (OSError, subprocess.SubprocessError):
                pass
        current = read(job_path(job['id']))
        if current.get('status') in ACTIVE:
            phase(current, 'interrupted', '维护任务曾中断，请核查任务备份与服务后再执行更新', 'interrupted', 'failed')


def dispatch(method, path, body=None):
    body = body or {}
    if method == 'GET' and path in ('/upgrade/status', '/upgrade/capabilities'):
        return 200, {'code': 200, 'data': native_status()}
    if method == 'GET' and path == '/upgrade/examples':
        return 200, {'code': 200, 'data': examples()}
    if method == 'GET' and re.fullmatch('/upgrade/jobs/[a-f0-9]{32}', path):
        job = read(job_path(path.rsplit('/', 1)[-1]))
        return (200, {'code': 200, 'data': {'job': job}}) if job else (404, {'code': 404, 'msg': '升级任务不存在'})
    if method == 'GET' and re.fullmatch('/upgrade/uploads/[a-f0-9]{32}', path):
        upload = read(ROOT / 'uploads' / ident(path.rsplit('/', 1)[-1]) / 'upload.json')
        return (200, {'code': 200, 'data': upload}) if upload else (404, {'code': 404, 'msg': '上传不存在'})
    if method == 'POST' and path == '/upgrade/uploads':
        filename, size = body.get('filename', ''), int(body.get('size', 0))
        if not filename.lower().endswith(('.tar', '.tar.gz', '.tgz', '.zip')) or not 0 < size <= MAX_UPLOAD:
            raise ValueError('请选择大小不超过1GB的原生tar.gz或zip代码包')
        upload_id = uuid.uuid4().hex
        atomic(ROOT / 'uploads' / upload_id / 'upload.json', {'id': upload_id, 'filename': Path(filename).name,
            'size': size, 'received': 0, 'finished': False, 'expected_sha256': body.get('sha256')})
        return 200, {'code': 200, 'data': {'upload_id': upload_id, 'chunk_bytes': CHUNK_BYTES}}
    if method == 'POST' and re.fullmatch('/upgrade/uploads/[a-f0-9]{32}/finish', path):
        folder = ROOT / 'uploads' / ident(path.split('/')[3])
        with LOCK:
            upload = read(folder / 'upload.json', {})
            if not upload or upload.get('received') != upload.get('size'):
                raise ValueError('升级包尚未上传完整')
            checksum = digest(folder / 'package')
            if upload.get('expected_sha256') and upload['expected_sha256'] != checksum:
                raise ValueError('升级包整体SHA256不一致')
            upload.update(finished=True, sha256=checksum)
            atomic(folder / 'upload.json', upload)
        return 200, {'code': 200, 'data': upload}
    if method == 'POST' and path == '/upgrade/rollback':
        handle = acquire()
        try:
            if any(item.get('status') in ACTIVE or item.get('status') == 'interrupted' for item in jobs()):
                raise ValueError('已有维护任务正在执行或需要核查，请稍后重试')
            source = rollback_source(body.get('job_id'))
            previous = source.get('previous_release')
            job = {'id': uuid.uuid4().hex, 'operation': 'rollback', 'source_job_id': source['id'],
                   'release': release_label(previous), 'previous_release': read(STATE / 'release.json'),
                   'created_at': now(), 'steps': [], 'components': source['components'],
                   'preview': dict(source.get('preview', {}), target_release=release_label(previous)),
                   'rollback_eligible': False, 'rollback_block_reason': '回退操作不支持反向重做；需要时重新上传升级包'}
            phase(job, 'backing_up', '回退任务已提交，正在准备独立维护进程')
        finally:
            handle.close()
        try:
            start_worker(job)
        except Exception as error:
            phase(job, 'failed', '无法启动独立回退进程，代码未修改', 'launch', 'failed', error=str(error)[:300])
            raise ValueError('无法启动独立回退进程，请检查systemd维护服务')
        return 200, {'code': 200, 'data': {'job': job}}
    if method == 'POST' and path in ('/upgrade/plan', '/upgrade/apply'):
        handle = acquire()
        try:
            if any(job.get('status') in ACTIVE or job.get('status') == 'interrupted' for job in jobs()):
                raise ValueError('已有维护任务正在执行或需要核查，请稍后重试')
            upload_id = ident(body.get('upload_id'))
            if not read(ROOT / 'uploads' / upload_id / 'upload.json', {}).get('finished'):
                raise ValueError('升级包尚未完成上传')
            if path == '/upgrade/plan':
                job = {'id': uuid.uuid4().hex, 'operation': 'upgrade', 'upload_id': upload_id,
                       'created_at': now(), 'steps': [], 'components': [], 'rollback_eligible': False,
                       'rollback_block_reason': '成功升级并保留完整备份后才可回退'}
                phase(job, 'validating', '正在校验原生代码包')
            else:
                plan = read(ROOT / 'uploads' / upload_id / 'plan.json', {})
                job = read(job_path(plan.get('job_id')), {})
                if job.get('status') != 'ready':
                    raise ValueError('请先完成升级包预检')
                phase(job, 'backing_up', '任务已提交，正在准备独立升级进程')
        finally:
            handle.close()
        if path == '/upgrade/plan':
            threading.Thread(target=validate, args=(job,), daemon=True).start()
        else:
            try:
                start_worker(job)
            except Exception as error:
                phase(job, 'failed', '无法启动独立升级进程，代码未修改', 'launch', 'failed', error=str(error)[:300])
                raise ValueError('无法启动独立升级进程，请检查systemd维护服务')
        return 200, {'code': 200, 'data': {'job': job}}
    return 404, {'code': 404, 'msg': '原生升级操作不存在'}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'worker':
        apply_job(ident(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == 'baseline':
        record_deployment(sys.argv[2])
    else:
        raise SystemExit('Usage: upgrade_operations.py worker JOB_ID | baseline RELEASE')
