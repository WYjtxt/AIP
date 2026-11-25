"""Durable, bounded IPv4 handovers on one explicitly selected physical port.

The system timer, not a browser or a platform container, owns recovery. Waiting
for carrier never writes a NetworkManager profile. Tickets grant confirmation
of one already authorised operation only; they cannot edit configuration.
"""
import argparse
import contextlib
import copy
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

import platform_site_operations as site
from platform_network_manager import NetworkManagerDriver, NetworkError

ACTIVE = ('waiting_link', 'queued', 'applying', 'awaiting_confirmation', 'finalizing',
          'awaiting_final_confirmation', 'rolling_back')
CONFIRM_SECONDS = 180
MUTATION_SECONDS = 720
TERMINAL = ('completed', 'rolled_back', 'failed', 'conflict', 'cancelled')


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


class NetworkOperations(site.SiteOperations):
    def __init__(self, root=site.INSTALL_ROOT, state=site.OPS_STATE, driver=None,
                 boot=None, sleeper=None, unit_active=None, watchdog=None, **options):
        super().__init__(root, state, **options)
        self.directory = Path(state).absolute() / 'network-config-ui'
        self.driver = driver or NetworkManagerDriver()
        self.boot = boot or boot_id
        self.sleep = sleeper or time.sleep
        self.unit_active = unit_active or self._unit_active
        self.watchdog = watchdog or self._watchdog_ready

    def _watchdog_ready(self):
        try:
            for name, source in timer_units(self.root, '/usr/bin/python3').items():
                path = Path('/etc/systemd/system') / name
                if path.is_symlink() or path.read_text(encoding='utf-8') != source:
                    return False
            for action in ('is-enabled', 'is-active'):
                result = subprocess.run(['systemctl', action, '--quiet', 'platform-network-watch.timer'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
                if result.returncode:
                    return False
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _unit_active(unit):
        try:
            result = subprocess.run(['systemctl', 'is-active', '--quiet', unit],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return None

    def _save(self, job, **values):
        job.update(values, updated_at=self.clock())
        self._write(self._job_path(job['id']), job)
        return job

    def _public(self, job, actor=None, tickets=True):
        keys = ('id', 'status', 'message', 'error', 'created_at', 'updated_at', 'finished_at',
                'old_entry', 'new_entry', 'confirm_entry', 'deadline', 'interface', 'request')
        result = {key: job[key] for key in keys if key in job}
        result['blocks_operations'] = job['status'] in ACTIVE or job['status'] == 'conflict' and bool(job.get('mutation_started'))
        result['can_cancel'] = actor == job['actor'] and job['status'] in ACTIVE and job['status'] != 'rolling_back'
        result['can_rollback'] = actor == job['actor'] and job['status'] == 'conflict' and bool(job.get('mutation_started'))
        if tickets and actor == job['actor'] and job['status'] in ('awaiting_confirmation', 'awaiting_final_confirmation'):
            result['handoff'] = self._handoff(job)
        return result

    @staticmethod
    def _handoff(job):
        phase = 'candidate' if job['status'] == 'awaiting_confirmation' else 'final'
        return {'job_id': job['id'], 'token': job['tickets'][phase], 'phase': phase,
                'confirm_url': job['confirm_entry']}

    def blocking(self):
        return next((job for job in self._jobs() if job['status'] in ACTIVE or
            job['status'] == 'conflict' and job.get('mutation_started')), None)

    def config(self, actor):
        inventory = self.driver.inspect()
        jobs = self._jobs()
        selected = self.blocking() or (jobs[0] if jobs else None)
        public = {key: inventory[key] for key in ('available', 'backend', 'version', 'reason', 'revision', 'interfaces')}
        public['watchdog_ready'] = self.watchdog()
        if public['available'] and not public['watchdog_ready']:
            public.update(available=False, reason='独立网络恢复服务未就绪，暂不能编辑网口')
        public.update(active_job=self._public(selected, actor) if selected else None,
                      latest_job=self._public(jobs[0], actor) if jobs else None,
                      confirmation_seconds=CONFIRM_SECONDS)
        return public

    def _baseline(self):
        manager = self._manager()
        plan, _, state = manager.plan()
        if plan['master_pending'] or plan['changes']:
            raise site.OperationError('现有平台地址尚有待同步配置，请先在 IP 管理底部点击“预览派发”并应用，完成后再预览网口变更', 409)
        return manager, plan, state

    def preview(self, body, actor):
        actor = site._actor(actor)
        if not isinstance(body, dict) or set(body) != {'revision', 'config'}:
            raise site.OperationError('网络预览只允许 revision 和 config 字段')
        with self._lock():
            if self.blocking():
                raise site.OperationError('已有网口切换任务，请先完成或取消', 409)
            if any(job['status'] in site.ACTIVE for job in site.SiteOperations(self.root, self.directory.parent)._jobs()):
                raise site.OperationError('已有平台配置维护任务', 409)
            manager, current, state = self._baseline()
            receipt = self.driver.plan(body['config'], body['revision'])
            request = receipt['request']
            old = state['applied']['node']['address']
            new = request['address'] if request['use_for_platform'] else old
            # Deleting the current business address requires an explicit handover.
            if (request['replace_ipv4'] and request['replace_ipv4'].split('/')[0] == old
                    and not request['use_for_platform']):
                raise site.OperationError('替换当前平台地址时，请勾选平台使用此 IP', 409)
            desired = copy.deepcopy(state['applied'])
            desired['node']['address'] = new
            core_plan = manager.plan(desired)[0]
            identifier, now = secrets.token_hex(16), self.clock()
            saved = {'id': identifier, 'actor': actor, 'created_at': now, 'expires_at': now + site.PLAN_TTL,
                     'receipt': receipt, 'core_plan': core_plan, 'baseline_id': current['plan_id'],
                     'consumed_by': None, 'old_entry': 'https://' + old + ':8888/',
                     'new_entry': 'https://' + new + ':8888/'}
            plans = self.directory / 'plans'
            retained = 0
            for path in plans.glob('*.json'):
                value = self._read(path)
                if value['expires_at'] <= now and not value.get('consumed_by'):
                    path.unlink()
                elif not value.get('consumed_by'):
                    retained += 1
            if retained >= site.MAX_PLANS:
                raise site.OperationError('待执行网络预览过多，请稍后重试', 429)
            self._write(plans / (identifier + '.json'), saved)
            labels = {'connection.autoconnect': '重新接线或开机后自动连接', 'ipv4.method': 'IPv4 配置方式',
                      'ipv4.addresses': 'IPv4 地址', 'ipv4.gateway': '网关', 'ipv4.never-default': '不参与默认出口',
                      'ipv4.route-metric': '路由优先级', 'ipv4.dns': 'DNS'}
            changes = [{'field': key, 'label': labels.get(key, key), 'before': receipt['before'][key],
                        'after': receipt['final'][key]} for key in receipt['owned_fields']
                       if receipt['before'][key] != receipt['final'][key]]
            return {'plan_id': identifier, 'expires_in': site.PLAN_TTL, 'request': request,
                    'old_entry': saved['old_entry'], 'new_entry': saved['new_entry'],
                    'changes': changes, 'requires_restarts': site._affected(core_plan),
                    'warnings': ['未接线时只保存计划，接线后自动检查并切换。',
                        '请保持本页打开；切换后需从确认入口验证，超时将自动回滚。',
                        '切换期间请勿在系统或其它工具中修改所选连接。'] + receipt.get('warnings', [])}

    def apply(self, body, actor):
        actor = site._actor(actor)
        if not isinstance(body, dict) or set(body) != {'plan_id', 'request_id'}:
            raise site.OperationError('应用请求只允许 plan_id 和 request_id 字段')
        identifier, plan_id = site._ident(body['request_id']), site._ident(body['plan_id'])
        with self._lock():
            prior = self._read(self._job_path(identifier))
            if prior:
                if prior['actor'] != actor or prior['preview_id'] != plan_id:
                    raise site.OperationError('请求编号已用于其它操作', 409)
                return {'job': self._public(prior, actor)}
            if self.blocking():
                raise site.OperationError('已有网口切换任务，请先完成或取消', 409)
            plan = self._read(self.directory / 'plans' / (plan_id + '.json'))
            if not plan or plan['actor'] != actor or plan['expires_at'] <= self.clock() or plan.get('consumed_by'):
                raise site.OperationError('预览已失效，请重新预览', 409)
            # Saving a waiting plan may not change any OS network properties.
            now = self.clock()
            job = {'id': identifier, 'actor': actor, 'preview_id': plan_id,
                   'status': 'waiting_link', 'message': '已保存，等待目标网口链路就绪',
                   'created_at': now, 'updated_at': now, 'request': plan['receipt']['request'],
                   'interface': plan['receipt']['interface'], 'receipt': plan['receipt'],
                   'core_plan': plan['core_plan'], 'baseline_id': plan['baseline_id'],
                   'old_entry': plan['old_entry'], 'new_entry': plan['new_entry'],
                   'confirm_entry': plan['new_entry'], 'mutation_started': False,
                   'tickets': {}, 'acks': {}, 'cancel_requested': False}
            self._write(self._job_path(identifier), job)
            plan['consumed_by'] = identifier
            self._write(self.directory / 'plans' / (plan_id + '.json'), plan)
            return {'job': self._public(job, actor)}

    def job(self, identifier, actor):
        value = self._read(self._job_path(identifier))
        if not value or value['actor'] != site._actor(actor):
            raise site.OperationError('网络任务不存在或不属于当前账号', 404)
        return {'job': self._public(value, actor)}

    def inactive_request(self, identifier, actor):
        # Synchronize with preview/apply: a delayed POST must not still be able
        # to start a change after the browser releases its local reference.
        with self._lock():
            value = self._read(self._job_path(identifier))
            if (value and value['actor'] == actor) or self.blocking():
                return False
            plans = self.directory / 'plans'
            self._safe_chain(plans)
            for path in plans.glob('*.json'):
                plan = self._read(path)
                if plan['actor'] == actor and not plan.get('consumed_by') and plan['expires_at'] > self.clock():
                    return False
            return True

    def cancel(self, identifier, actor, retry=False):
        with self._lock():
            self.job(identifier, actor)
            job = self._read(self._job_path(identifier))
            if retry:
                if not (job['status'] == 'conflict' and job.get('mutation_started')):
                    raise site.OperationError('当前任务无需再次回滚', 409)
                self._save(job, status='rolling_back', message='等待重新核对并回滚', recovery_pending=True,
                           deadline=self.clock() + MUTATION_SECONDS)
            elif job['status'] == 'waiting_link':
                self._save(job, status='cancelled', message='已取消，未修改网络', finished_at=self.clock())
            elif job['status'] in ACTIVE and job['status'] != 'rolling_back':
                self._save(job, cancel_requested=True, message='已请求取消，正在安全回滚')
            else:
                raise site.OperationError('当前任务不能取消', 409)
            return {'job': self._public(job, actor)}

    def _launch(self, job, rollback=False):
        unit = 'platform-network-' + job['id'] + ('-restore-' + secrets.token_hex(4) if rollback else '')
        job.update(unit=unit, launched_at=self.clock(), boot_id=self.boot())
        self._save(job)
        command = [shutil.which('systemd-run') or '/usr/bin/systemd-run', '--quiet', '--collect',
                   '--unit=' + unit, '--property=Type=exec', '--property=UMask=0077',
                   '--property=RuntimeMaxSec=900', '--property=TimeoutStopSec=15',
                   '--property=StandardOutput=null', '--property=StandardError=null',
                   '--setenv=PLATFORM_NATIVE_ROOT=' + str(self.root),
                   '--setenv=PLATFORM_OPS_STATE_DIR=' + str(self.directory.parent),
                   sys.executable, str(Path(__file__).resolve()), '--restore' if rollback else '--worker', job['id']]
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if result.returncode:
            raise site.OperationError('无法启动独立网络维护进程', 503)

    def tick(self):
        """Short system-timer tick; long service actions execute in owned workers."""
        with self._lock():
            job = self.blocking()
            if not job or job['status'] == 'conflict':
                return
            if job['status'] == 'waiting_link':
                try:
                    inventory, interface, profile = self.driver._current(job['receipt'])
                    if profile != job['receipt']['before']:
                        raise site.OperationError('等待期间连接被修改，请重新预览', 409)
                    if interface['carrier'] is not True:
                        return
                    if not self.watchdog():
                        raise site.OperationError('独立网络恢复服务未就绪，未修改网口', 503)
                    self._save(job, status='queued', message='链路已就绪，正在启动网络切换')
                    self.launcher(job)
                except Exception as error:
                    self._save(job, status='failed', message='网络计划未执行',
                               error=self._reason(error), finished_at=self.clock())
                return
            if job['status'] == 'queued' and not job.get('mutation_started'):
                active = self.unit_active(job.get('unit', '')) if job.get('unit') else False
                if active is False and self.clock() - job.get('launched_at', job['updated_at']) > 30:
                    self._save(job, status='failed', message='网络维护进程未启动，未修改网络', finished_at=self.clock())
                return
            active = self.unit_active(job.get('unit', '')) if job.get('unit') else False
            expired = job.get('deadline', 0) <= self.clock() or job.get('boot_id') != self.boot()
            if active is None:
                return
            if active and not expired and not job.get('recovery_pending'):
                return
            if active:
                # Unit names are generated by us, persisted before launch, never accepted from HTTP.
                if not re.fullmatch(r'platform-network-' + job['id'] + r'(?:-restore-[a-f0-9]{8})?', job['unit']):
                    self._save(job, status='conflict', error='网络维护进程标识不正确，请核对恢复记录')
                    return
                result = subprocess.run(['systemctl', 'stop', job['unit']], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=25)
                if result.returncode:
                    return
            self._save(job, status='rolling_back', message='维护中断或确认超时，正在恢复原网络',
                       recovery_pending=False, deadline=self.clock() + MUTATION_SECONDS)
            try:
                self._launch(job, rollback=True)
            except Exception as error:
                self._save(job, status='conflict', message='自动恢复进程未启动，请重试回滚', error=self._reason(error))

    def _reason(self, error):
        return str(error)[:600] if isinstance(error, (site.OperationError, NetworkError, self.core.SiteConfigError)) else '网络检查未通过，请核对维护记录'

    def _find_backup(self, job):
        matches = []
        for path in (self.root / 'platform_ops/backups').glob('site-*/manifest.json'):
            record = self._read(path)
            if (record.get('context') or {}).get('network_job_id') == job['id']:
                matches.append(path.parent)
        if len(matches) > 1:
            raise site.OperationError('网络事务关联了多个平台备份，请人工核对', 409)
        return matches[0] if matches else None

    def _restore(self, job):
        backup = self._find_backup(job)
        if backup:
            # The final phase may already have retired the old address. Restore
            # its reachability before old-IP listeners restart, retaining the
            # candidate until the platform transaction has safely rolled back.
            self.driver.prepare_rollback(job['receipt'])
            journal = self._read(backup / 'manifest.json')
            if journal['status'] != 'rolled_back':
                controller = (self.controller_factory or site._controller(self.root))(self.root, require_running=False)
                self._manager().rollback(str(backup), restore=controller.restore)
        # Never delete the candidate address while platform restore is conflicted.
        self.driver.rollback(job['receipt'])
        with self._lock():
            current = self._read(self._job_path(job['id']))
            self._save(current, status='rolled_back', message='已恢复原网口和平台配置',
                       mutation_started=False, finished_at=self.clock(), tickets={})

    def _await(self, identifier, phase):
        status = 'awaiting_confirmation' if phase == 'candidate' else 'awaiting_final_confirmation'
        with self._lock():
            job = self._read(self._job_path(identifier))
            tickets = dict(job['tickets']); tickets[phase] = secrets.token_urlsafe(32)
            self._save(job, status=status, tickets=tickets, deadline=self.clock() + CONFIRM_SECONDS,
                       message='等待浏览器验证候选入口' if phase == 'candidate' else '等待浏览器验证最终网络')
        while True:
            with self._lock():
                job = self._read(self._job_path(identifier))
                if job.get('cancel_requested'):
                    raise site.OperationError('用户取消，恢复原配置', 409)
                if job['deadline'] <= self.clock():
                    raise site.OperationError('管理端确认超时，恢复原配置', 409)
                if job['acks'].get(phase):
                    return job
            self.sleep(1)

    def worker(self, identifier, restore=False):
        identifier = site._ident(identifier)
        with self._lock():
            job = self._read(self._job_path(identifier))
            if not job or (not restore and job['status'] != 'queued') or (restore and job['status'] != 'rolling_back'):
                raise site.OperationError('网络任务已结束或不存在', 409)
        try:
            with self.maintenance():
                if restore:
                    self._restore(job)
                    return
                if not self.watchdog():
                    raise site.OperationError('独立网络恢复服务未就绪，未修改网口', 503)
                manager, baseline, state = self._baseline()
                if baseline['plan_id'] != job['baseline_id']:
                    raise site.OperationError('等待期间平台配置已变化，请重新预览', 409)
                if job.get('cancel_requested'):
                    raise site.OperationError('已取消网络切换', 409)
                with self._lock():
                    job = self._read(self._job_path(identifier))
                    if job.get('cancel_requested'):
                        raise site.OperationError('已取消网络切换', 409)
                    self._save(job, status='applying', message='正在准备候选网络和平台配置',
                               mutation_started=True, boot_id=self.boot(), deadline=self.clock() + MUTATION_SECONDS)
                self.driver.stage_candidate(job['receipt'])
                readiness = self.driver.ready(job['receipt'])
                if not readiness['ready']:
                    raise site.OperationError(readiness['reason'], 409)
                if job['core_plan']['node_changed']:
                    controller = (self.controller_factory or site._controller(self.root))(self.root, retain_old_ip=True)
                    def prepare(plan):
                        context = controller.prepare(plan)
                        context['network_job_id'] = job['id']
                        return context
                    manager.apply(job['core_plan']['plan_id'], job['core_plan']['desired'],
                        prepare=prepare, activate=controller.activate, verify=controller.verify, restore=controller.restore)
                job = self._await(identifier, 'candidate')
                with self._lock():
                    job = self._read(self._job_path(identifier))
                    if job.get('cancel_requested'):
                        raise site.OperationError('用户取消，恢复原配置', 409)
                    self._save(job, status='finalizing', message='候选入口已确认，正在完成网口配置', deadline=self.clock() + 90)
                self.driver.finalize(job['receipt'])
                readiness = self.driver.ready(job['receipt'])
                if not readiness['ready']:
                    raise site.OperationError(readiness['reason'], 409)
                job = self._await(identifier, 'final')
                with self._lock():
                    job = self._read(self._job_path(identifier))
                    if job.get('cancel_requested') or job['deadline'] <= self.clock() or job.get('boot_id') != self.boot():
                        raise site.OperationError('最终确认已过期或被取消，恢复原配置', 409)
                    self._save(job, status='completed', message='网口及平台配置已生效，管理端验证通过',
                               finished_at=self.clock(), deadline=None, mutation_started=False)
        except Exception as error:
            with self._lock():
                job = self._read(self._job_path(identifier))
                if not job.get('mutation_started'):
                    self._save(job, status='failed', message='网络切换未执行', error=self._reason(error), finished_at=self.clock())
                    return
                self._save(job, status='rolling_back', message='检查未通过，正在恢复原配置', error=self._reason(error),
                           deadline=self.clock() + MUTATION_SECONDS)
            try:
                with self.maintenance():
                    self._restore(job)
            except Exception as recovery_error:
                with self._lock():
                    latest = self._read(self._job_path(identifier))
                    self._save(latest, status='conflict', message='恢复遇到外部修改，已保留可恢复地址',
                               error=self._reason(recovery_error), finished_at=self.clock())

    def confirm(self, body):
        if not isinstance(body, dict) or set(body) != {'job_id', 'token', 'phase', 'destination', 'origin', 'peer'}:
            raise site.OperationError('确认请求无效')
        identifier = site._ident(body['job_id'])
        phase, token = body['phase'], body['token']
        if phase not in ('candidate', 'final') or not isinstance(token, str) or len(token) > 100:
            raise site.OperationError('确认凭据无效', 403)
        with self._lock():
            job = self._read(self._job_path(identifier))
            if not job or not hmac.compare_digest(job.get('tickets', {}).get(phase, ''), token) or not token:
                raise site.OperationError('确认凭据无效或已失效', 403)
            entry = urlsplit(job['confirm_entry'])
            try:
                peer = ipaddress.ip_address(body['peer'])
                destination = ipaddress.ip_address(body['destination'])
                if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped:
                    peer = peer.ipv4_mapped
            except (ValueError, TypeError):
                raise site.OperationError('确认入口校验失败', 403)
            if (str(destination) != entry.hostname or body['origin'] != entry.scheme + '://' + entry.netloc
                    or peer.is_loopback or peer.is_unspecified or str(peer) == entry.hostname):
                raise site.OperationError('请从管理电脑打开指定确认入口', 403)
            inventory = self.driver.inspect()
            if not inventory['available'] or any(str(peer) == row['address'] for item in inventory['interfaces'] for row in item['addresses']):
                raise site.OperationError('服务器自身检查不能代替管理端确认', 403)
            if job['status'] in ('rolled_back', 'failed', 'conflict', 'cancelled'):
                raise site.OperationError('网络切换未完成，原配置已保留或等待恢复', 409)
            expected = 'awaiting_confirmation' if phase == 'candidate' else 'awaiting_final_confirmation'
            if job['status'] == expected and not job['acks'].get(phase):
                if job['deadline'] <= self.clock() or job.get('cancel_requested') or job.get('boot_id') != self.boot():
                    raise site.OperationError('确认已过期，正在恢复原配置', 409)
                acks = dict(job['acks']); acks[phase] = self.clock()
                self._save(job, acks=acks)
            elif not job['acks'].get(phase):
                raise site.OperationError('当前确认阶段不匹配', 409)
            result = {'job': self._public(job, tickets=False)}
            # Acknowledged candidate ticket may poll; it cannot acknowledge final.
            if phase == 'candidate' and job['status'] == 'awaiting_final_confirmation':
                result['handoff'] = self._handoff(job)
            return result


_OPERATIONS = None


def operations():
    global _OPERATIONS
    if _OPERATIONS is None:
        _OPERATIONS = NetworkOperations()
    return _OPERATIONS


def ensure_no_active(root, state):
    engine = NetworkOperations(root, state)
    if engine.blocking():
        raise site.OperationError('已有网口切换任务，请先完成或取消', 409)


def dispatch(method, path, body, actor):
    creating = method == 'POST' and path == '/site-config/network/apply'
    try:
        engine = operations()
        base = '/site-config/network/'
        route = path[len(base):]
        if urlsplit(path).query:
            raise site.OperationError('不支持的查询参数')
        if method == 'POST' and route == 'confirm':
            result = engine.confirm(body)
        else:
            site._actor(actor)
            if method == 'GET' and route == 'config':
                result = engine.config(actor)
            elif method == 'POST' and route == 'preview':
                result = engine.preview(body, actor)
            elif creating:
                result = engine.apply(body, actor)
            elif method == 'GET' and re.fullmatch(r'jobs/[a-f0-9]{32}', route):
                result = engine.job(route.split('/')[1], actor)
            elif method == 'POST' and re.fullmatch(r'jobs/[a-f0-9]{32}/(?:cancel|rollback)', route) and body == {}:
                result = engine.cancel(route.split('/')[1], actor, retry=route.endswith('/rollback'))
            else:
                raise site.OperationError('网口操作不存在', 404)
        return 200, {'code': 200, 'data': result}
    except (site.OperationError, NetworkError) as error:
        status = getattr(error, 'status', 409)
        result = {'code': status, 'msg': str(error)[:600]}
        if creating and isinstance(body, dict) and isinstance(body.get('request_id'), str) and site.IDENT.fullmatch(body['request_id']):
            result['safe_to_repreview'] = operations()._read(operations()._job_path(body['request_id'])) is None
        if method == 'GET' and status == 404 and re.fullmatch(r'/site-config/network/jobs/[a-f0-9]{32}', path):
            identifier = path.rsplit('/', 1)[1]
            if engine.inactive_request(identifier, actor):
                result['inactive_request'] = identifier
        return status, result
    except Exception:
        return 500, {'code': 500, 'msg': '网口操作未通过校验，请核对维护记录'}


def timer_units(root, python):
    def arg(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    root = Path(root).absolute()
    service = ('[Unit]\nDescription=Recover platform network handovers\nAfter=NetworkManager.service\n'
               '[Service]\nType=oneshot\nUser=root\nUMask=0077\nTimeoutStartSec=55\n'
               'Environment=' + arg('PLATFORM_NATIVE_ROOT=' + str(root)) + '\n'
               'Environment=' + arg('PLATFORM_OPS_STATE_DIR=' + str(root / 'platform_ops/state')) + '\n'
               'ExecStart=' + arg(python) + ' ' + arg(root / 'platform_ops/platform_network_operations.py') + ' --tick\n')
    timer = ('[Unit]\nDescription=Watch platform network handovers\n[Timer]\nOnBootSec=15s\n'
             'OnUnitInactiveSec=3s\nAccuracySec=1s\nUnit=platform-network-watch.service\n'
             '[Install]\nWantedBy=timers.target\n')
    return {'platform-network-watch.service': service, 'platform-network-watch.timer': timer}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--tick', action='store_true')
    group.add_argument('--worker')
    group.add_argument('--restore')
    options = parser.parse_args()
    if options.tick:
        operations().tick()
    else:
        operations().worker(options.worker or options.restore, restore=bool(options.restore))
