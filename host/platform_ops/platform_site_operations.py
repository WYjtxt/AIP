"""Protected host-side API and restart-independent unified network jobs."""
import argparse
import contextlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

INSTALL_ROOT = Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parent.parent)))
OPS_STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', str(INSTALL_ROOT / 'platform_ops/state')))
ACTIVE = ('queued', 'running')
PLAN_TTL = 600
MAX_JSON = 1024 * 1024
MAX_PLANS = 128
IDENT = re.compile(r'[a-f0-9]{32}')
LOCK = threading.RLock()


class OperationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise OperationError('维护记录编号无效')
    return value


def _actor(value):
    if not isinstance(value, str) or not value or len(value) > 180 or any(ord(c) < 32 for c in value):
        raise OperationError('维护账号标识无效', 403)
    return value


def _core(root):
    directory = str(Path(root) / 'Config_files')
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return importlib.import_module('platform_site_config')


def _controller(root):
    directory = str(Path(root) / 'platform_ops')
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return importlib.import_module('platform_site_control').LiveController


def _affected(plan):
    if plan['node_changed']:
        return ['backend', 'algorithm-master', 'web', 'dispatch', 'dispatch-web', 'media', 'kafka']
    result = set()
    for change in plan['changes']:
        path = change['path']
        if path.startswith(('platform_algorithm_start/', 'model_algorithm_package/')):
            result.add('algorithm-master')
        elif path.startswith('platform_gateway/') or path in ('Config_files/config.js', 'Config_files/secure-transport.js'):
            result.add('web')
        elif path == 'Config_files/config.ini':
            result.update(('backend', 'algorithm-master'))
        elif path == 'Config_files/kafka.properties':
            result.add('kafka')
        elif path == 'Config_files/zlk/config.ini':
            result.add('media')
        elif path == 'config_dispatch/security-settings.json':
            result.add('dispatch')
        elif path.startswith('config_dispatch/gateway/'):
            result.add('dispatch-web')
    if plan['generation'] == 0 and (plan['changes'] or plan['master_pending']):
        result.update(('backend', 'dispatch'))
    return sorted(result)


class SiteOperations:
    def __init__(self, root=INSTALL_ROOT, state=OPS_STATE, manager_factory=None,
                 controller_factory=None, launcher=None, clock=None, maintenance=None,
                 network_provider=None):
        self.root = Path(root).absolute()
        self.directory = Path(state).absolute() / 'site-config-ui'
        self.core = _core(self.root)
        self.manager_factory = manager_factory or self.core.SiteManager
        self.controller_factory = controller_factory
        self.launcher = launcher or self._launch
        self.clock = clock or time.time
        self.maintenance = maintenance or self._maintenance
        self.network_provider = network_provider

    def _manager(self):
        return self.manager_factory(self.root)

    def _safe_chain(self, path):
        for part in [Path(path)] + list(Path(path).parents):
            if part.is_symlink():
                raise OperationError('维护记录目录不能包含符号链接', 409)
            if part == self.directory.parent:
                break

    def _read(self, path, default=None):
        self._safe_chain(path)
        if not path.exists():
            return default
        if not path.is_file() or path.stat().st_size > MAX_JSON:
            raise OperationError('维护记录格式不正确', 409)
        return self.core.unique_json(path.read_bytes())

    def _write(self, path, value):
        self._safe_chain(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._safe_chain(path)
        os.chmod(str(path.parent), 0o700)
        self.core.atomic(path, self.core.encoded(value))

    @contextlib.contextmanager
    def _lock(self):
        with LOCK:
            self._safe_chain(self.directory)
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(str(self.directory), 0o700)
            path = self.directory / 'api.lock'
            self._safe_chain(path)
            with path.open('a+b') as stream:
                if os.name == 'posix':
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == 'posix':
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _job_path(self, value):
        return self.directory / 'jobs' / (_ident(value) + '.json')

    def _jobs(self):
        self._safe_chain(self.directory / 'jobs')
        values = []
        for path in (self.directory / 'jobs').glob('*.json'):
            if IDENT.fullmatch(path.stem):
                value = self._read(path)
                if value:
                    values.append(value)
        return sorted(values, key=lambda v: (v['created_at'], v['id']), reverse=True)

    @staticmethod
    def _public_job(job):
        allowed = ('id', 'operation', 'status', 'message', 'error', 'created_at', 'updated_at',
                   'finished_at', 'backup', 'result', 'target_address', 'node_changed')
        return {key: job[key] for key in allowed if key in job}

    def _last_backup(self, generation):
        parent = self.root / 'platform_ops/backups'
        options = []
        for path in parent.glob('site-*/manifest.json'):
            if path.parent.is_symlink() or path.is_symlink():
                continue
            packet = self._read(path)
            if packet.get('status') == 'applied' and packet.get('generation') == generation - 1:
                options.append(str(path.parent))
        return max(options) if options else None

    def config(self):
        self.recover_interrupted_jobs()
        manager = self._manager()
        master = self.core.unique_json(manager.path(self.core.MASTER).read_bytes())
        receipt = self.core.unique_json(manager.path(self.core.STATE).read_bytes())
        self.core.validate(master)
        self.core.validate(receipt['applied'])
        jobs = self._jobs()
        active = next((job for job in jobs if job['status'] in ACTIVE), None)
        result = {'desired': master, 'applied': receipt['applied'], 'generation': receipt['generation'],
                  'managed_files': len(receipt.get('bindings', {})),
                  'managed_bindings': sum(len(v) for v in receipt.get('bindings', {}).values()),
                  'can_edit': True, 'busy': active is not None,
                  'active_job': self._public_job(active) if active else None,
                  'latest_job': self._public_job(jobs[0]) if jobs else None,
                  'jobs': [self._public_job(job) for job in jobs[:20]],
                  'last_backup': self._last_backup(receipt['generation']),
                  'features': {'preview': True, 'apply': True, 'rollback': True,
                               'persistent_jobs': True, 'stable_machine_identity': True}}
        try:
            identity = importlib.import_module('platform_host_identity').read_host_identity()
            result['host_identity'] = {'host_uid': identity['host_uid']}
        except Exception:
            result['host_identity'] = {'host_uid': None}
        address = receipt['applied']['node']['address']
        try:
            provider = self.network_provider or importlib.import_module('platform_network_info').snapshot
            result['network'] = provider(address)
            result['features']['network_interfaces'] = True
        except Exception:
            # Keep existing configuration and maintenance available when an
            # inventory helper is missing during a partial/offline upgrade.
            message = '网口信息模块暂不可用'
            result['network'] = {'available': False, 'collected_at': self.clock(),
                                 'interfaces': [], 'business': {'address': address,
                                 'status': 'unavailable', 'interface_names': [], 'message': message},
                                 'error': message, 'error_code': 'helper_unavailable'}
            result['features']['network_interfaces'] = False
        if not active:
            try:
                public, _, _ = manager.plan()
                result.update(pending=public['master_pending'] or bool(public['changes']), drift=None)
            except self.core.SiteConfigError as error:
                result.update(pending=True, drift=str(error)[:800])
        else:
            result.update(pending=True, drift=None)
        return result

    def preview(self, body, actor):
        if not isinstance(body, dict) or set(body) != {'config'}:
            raise OperationError('预览请求只允许 config 字段')
        actor = _actor(actor)
        with self._lock():
            self._network_guard()
            if any(job['status'] in ACTIVE for job in self._jobs()):
                raise OperationError('已有统一配置任务正在执行', 409)
            retained = 0
            for path in (self.directory / 'plans').glob('*.json'):
                if IDENT.fullmatch(path.stem):
                    saved = self._read(path)
                    if saved['expires_at'] <= self.clock() and not saved.get('consumed_by'):
                        path.unlink()
                    elif not saved.get('consumed_by'):
                        retained += 1
            if retained >= MAX_PLANS:
                raise OperationError('待执行预览过多，请先完成现有预览或稍后重试', 429)
            plan, _, _ = self._manager().plan(body['config'])
            identifier = secrets.token_hex(16)
            now = self.clock()
            packet = {'id': identifier, 'actor': actor, 'created_at': now, 'expires_at': now + PLAN_TTL,
                      'core_plan': plan, 'consumed_by': None}
            self._write(self.directory / 'plans' / (identifier + '.json'), packet)
            return dict(plan, plan_id=identifier, expires_in=PLAN_TTL, affected_services=_affected(plan))

    def _pending_job(self, operation, actor, **values):
        now = self.clock()
        job = {'id': secrets.token_hex(16), 'operation': operation, 'actor': actor,
               'status': 'queued', 'message': '已提交，等待执行', 'created_at': now,
               'updated_at': now, **values}
        job['unit'] = 'platform-site-config-' + job['id']
        return job

    def apply(self, body, actor):
        if not isinstance(body, dict) or set(body) != {'plan_id'}:
            raise OperationError('应用请求只允许 plan_id 字段')
        actor = _actor(actor)
        with self._lock():
            self._network_guard()
            if any(job['status'] in ACTIVE for job in self._jobs()):
                raise OperationError('已有统一配置任务正在执行', 409)
            path = self.directory / 'plans' / (_ident(body['plan_id']) + '.json')
            packet = self._read(path)
            if not packet or packet['actor'] != actor or packet['expires_at'] <= self.clock() or packet.get('consumed_by'):
                raise OperationError('预览已失效或不属于当前账号，请重新预览', 409)
            desired = packet['core_plan']['desired']
            current = self._manager().plan(desired)[0]
            if current['plan_id'] != packet['core_plan']['plan_id']:
                raise OperationError('预览后配置发生变化，请重新预览', 409)
            job = self._pending_job('apply', actor, preview_id=packet['id'],
                                    target_address=current['node'], node_changed=current['node_changed'])
            packet['consumed_by'] = job['id']
            self._write(path, packet)
            self._write(self._job_path(job['id']), job)
            self._launch_checked(job)
            return {'job': self._public_job(self._read(self._job_path(job['id'])))}

    def rollback(self, body, actor):
        if not isinstance(body, dict) or set(body) != {'backup'} or not isinstance(body['backup'], str):
            raise OperationError('回滚请求只允许 backup 字段')
        actor = _actor(actor)
        with self._lock():
            self._network_guard()
            if any(job['status'] in ACTIVE for job in self._jobs()):
                raise OperationError('已有统一配置任务正在执行', 409)
            manager = self._manager()
            receipt_raw = manager.path(self.core.STATE).read_bytes()
            receipt = self.core.unique_json(receipt_raw)
            backup = self._last_backup(receipt['generation'])
            if body['backup'] != backup or not backup:
                raise OperationError('只允许回滚当前生效代次的已验证备份', 409)
            job = self._pending_job('rollback', actor, backup=backup, receipt_sha256=self.core.sha(receipt_raw))
            self._write(self._job_path(job['id']), job)
            self._launch_checked(job)
            return {'job': self._public_job(self._read(self._job_path(job['id'])))}

    def _launch_checked(self, job):
        try:
            self.launcher(job)
        except Exception:
            job.update(status='failed', message='维护任务未能启动', error='无法启动独立维护任务，请稍后重试',
                       updated_at=self.clock(), finished_at=self.clock())
            self._write(self._job_path(job['id']), job)
            raise OperationError('无法启动独立维护任务，请稍后重试', 503) from None

    def _launch(self, job):
        executable = shutil.which('systemd-run')
        if not executable or not Path('/run/systemd/system').is_dir():
            raise OperationError('主机不支持独立维护任务', 503)
        arguments = [executable, '--quiet', '--collect', '--unit=' + job['unit'],
                     '--property=Type=exec', '--property=UMask=0077',
                     '--property=RuntimeMaxSec=900', '--property=StandardOutput=null',
                     '--property=StandardError=null',
                     '--setenv=PLATFORM_NATIVE_ROOT=' + str(self.root),
                     '--setenv=PLATFORM_OPS_STATE_DIR=' + str(self.directory.parent),
                     sys.executable, str(Path(__file__).resolve()), '--worker', job['id']]
        result = subprocess.run(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if result.returncode:
            raise OperationError('无法创建独立维护任务', 503)

    @staticmethod
    @contextlib.contextmanager
    def _maintenance():
        import upgrade_operations
        handle = upgrade_operations.acquire()
        try:
            yield
        finally:
            handle.close()

    def _network_guard(self):
        import platform_network_operations
        platform_network_operations.ensure_no_active(self.root, self.directory.parent)

    def worker(self, identifier):
        identifier = _ident(identifier)
        with self._lock():
            job = self._read(self._job_path(identifier))
            if not job or job['status'] != 'queued':
                raise OperationError('维护任务已执行或不存在', 409)
            job.update(status='running', message='正在校验并应用配置', updated_at=self.clock())
            self._write(self._job_path(identifier), job)
        try:
            with self.maintenance():
                self._network_guard()
                manager = self._manager()
                controller_class = self.controller_factory or _controller(self.root)
                runtime = controller_class(self.root, **({'require_running': False} if job['operation'] == 'rollback' else {}))
                if job['operation'] == 'apply':
                    packet = self._read(self.directory / 'plans' / (job['preview_id'] + '.json'))
                    if not packet or packet.get('consumed_by') != identifier or packet['actor'] != job['actor']:
                        raise OperationError('维护任务的预览绑定无效', 409)
                    plan = packet['core_plan']
                    result = manager.apply(plan['plan_id'], plan['desired'], prepare=runtime.prepare,
                                           activate=runtime.activate, verify=runtime.verify, restore=runtime.restore)
                else:
                    current = manager.path(self.core.STATE).read_bytes()
                    if self.core.sha(current) != job['receipt_sha256']:
                        raise OperationError('提交后配置代次发生变化，未执行回滚', 409)
                    result = manager.rollback(job['backup'], restore=runtime.restore)
            safe_result = {key: result[key] for key in ('ok', 'generation', 'applied', 'backup', 'no_op', 'checks') if key in result}
            job.update(status='completed', message='配置已应用并验证' if job['operation'] == 'apply' else '已恢复上一代配置',
                       result=safe_result, backup=result.get('backup'), finished_at=self.clock())
        except Exception as error:
            reason = str(error)[:800] if isinstance(error, (OperationError, self.core.SiteConfigError)) else '维护检查未通过，请核对任务及配置备份'
            job.update(status='failed', message='维护任务未通过检查', error=reason, finished_at=self.clock())
        job['updated_at'] = self.clock()
        with self._lock():
            self._write(self._job_path(identifier), job)
        return self._public_job(job)

    def job(self, identifier):
        self.recover_interrupted_jobs()
        result = self._read(self._job_path(identifier))
        if not result:
            raise OperationError('维护任务不存在', 404)
        return {'job': self._public_job(result)}

    def recover_interrupted_jobs(self):
        with self._lock():
            for job in self._jobs():
                if job['status'] not in ACTIVE or self.clock() - job['created_at'] < 30:
                    continue
                try:
                    answer = subprocess.run(['systemctl', 'is-active', '--quiet', job['unit']],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
                except (OSError, subprocess.TimeoutExpired):
                    continue  # Uncertain unit status cannot invalidate a live job.
                if answer.returncode == 0:
                    continue
                job.update(status='failed', message='维护任务曾中断，请核对配置备份后重试',
                           error='独立维护进程已结束，未自动覆盖配置', updated_at=self.clock(), finished_at=self.clock())
                self._write(self._job_path(job['id']), job)


_OPERATIONS = None


def operations():
    global _OPERATIONS
    if _OPERATIONS is None:
        _OPERATIONS = SiteOperations()
    return _OPERATIONS


def dispatch(method, path, body=None, actor=''):
    if path.startswith('/site-config/network/'):
        import platform_network_operations
        return platform_network_operations.dispatch(method, path, body, actor)
    try:
        _actor(actor)
        if urlsplit(path).query:
            raise OperationError('不支持的查询参数')
        engine = operations()
        if method == 'GET' and path == '/site-config/config':
            result = engine.config()
        elif method == 'POST' and path == '/site-config/preview':
            result = engine.preview(body, actor)
        elif method == 'POST' and path == '/site-config/apply':
            result = engine.apply(body, actor)
        elif method == 'POST' and path == '/site-config/rollback':
            result = engine.rollback(body, actor)
        elif method == 'GET' and re.fullmatch(r'/site-config/jobs/[a-f0-9]{32}', path):
            result = engine.job(path.rsplit('/', 1)[-1])
        else:
            raise OperationError('统一配置维护操作不存在', 404)
        return 200, {'code': 200, 'data': result}
    except OperationError as error:
        return error.status, {'code': error.status, 'msg': str(error)}
    except Exception as error:
        if _OPERATIONS is not None and isinstance(error, _OPERATIONS.core.SiteConfigError):
            return 409, {'code': 409, 'msg': str(error)[:800]}
        return 500, {'code': 500, 'msg': '统一配置操作未通过校验，请核对维护记录'}


def recover_interrupted_jobs():
    return operations().recover_interrupted_jobs()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True)
    options = parser.parse_args()
    outcome = operations().worker(options.worker)
    sys.exit(0 if outcome['status'] == 'completed' else 1)
