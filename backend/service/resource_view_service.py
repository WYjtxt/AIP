# host-identity-backend-v1
from data.resource_view_data import ResourceViewData
import random
import string
from datetime import datetime, timedelta
from config.configs import *

import json
import time
import os
import socket
import threading
import hashlib
import uuid
from weakref import WeakValueDictionary
from datetime import timezone
import paramiko
import redis as host_metrics_redis

# Host measurements belong to the configured SSH host, never the Linux
# application's container. No database schema or scheduler changes are needed.
_HOST_METRICS_TTL = 10
_HOST_METRICS_LOCK_TTL = 20
_HOST_METRICS_REDIS = None
_HOST_LOCAL_CACHE = {}
_HOST_LOCAL_LOCKS = WeakValueDictionary()
_HOST_LOCAL_GUARD = threading.Lock()
_HOST_READ_COMMAND = ("LC_ALL=C sh -c 'head -n 1 /proc/stat; sleep 0.5; "
                      "head -n 1 /proc/stat; cat /proc/meminfo'")


def _host_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _host_metrics_empty(status, error):
    return {'cpu_usage': None, 'host_mem_usage': None,
            'host_metrics_sampled_at': None,
            'host_metrics_attempted_at': _host_timestamp(),
            'host_metrics_status': status, 'host_metrics_error': error}


def _parse_host_sample(output):
    """CPU busy/total across all cores; memory uses Linux MemAvailable.

    guest/guest_nice are already included in user/nice and are not summed twice.
    Idle includes iowait. Missing metrics remain null rather than a false 0%.
    """
    result = _host_metrics_empty('error', '')
    errors = []
    cpu_lines = [line.split()[1:] for line in output.splitlines()
                 if line.startswith('cpu ')]
    try:
        if len(cpu_lines) != 2 or any(len(values) < 4 for values in cpu_lines):
            raise ValueError()
        first, second = [[int(v) for v in values[:8]] for values in cpu_lines]
        if len(first) != len(second):
            raise ValueError()
        delta = [b - a for a, b in zip(first, second)]
        total = sum(delta)
        idle = delta[3] + (delta[4] if len(delta) > 4 else 0)
        if total <= 0 or any(v < 0 for v in delta) or not 0 <= idle <= total:
            raise ValueError()
        result['cpu_usage'] = '{:.1f}%'.format((total - idle) * 100.0 / total)
    except (ValueError, TypeError, IndexError):
        errors.append('CPU 差分采样无效')
    try:
        memory = {}
        for line in output.splitlines():
            if ':' in line:
                name, value = line.split(':', 1)
                if name in ('MemTotal', 'MemAvailable'):
                    memory[name] = int(value.split()[0])
        total = memory['MemTotal']
        available = memory['MemAvailable']
        if total <= 0 or not 0 <= available <= total:
            raise ValueError()
        result['host_mem_usage'] = '{:.1f}%'.format((total - available) * 100.0 / total)
    except (ValueError, TypeError, KeyError, IndexError):
        errors.append('主机未提供有效 MemAvailable/内存容量')
    measured = (result['cpu_usage'] is not None or result['host_mem_usage'] is not None)
    result['host_metrics_sampled_at'] = _host_timestamp() if measured else None
    result['host_metrics_status'] = ('ok' if not errors else 'partial' if measured else 'error')
    result['host_metrics_error'] = '；'.join(errors) or None
    return result


def _sample_host_metrics(item, binding=None):
    host = str(item.computing_ip or '').strip()
    if os.name == 'nt' and not binding and host in ('127.0.0.1', 'localhost', '::1'):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory().percent
            if not (0 <= cpu <= 100 and 0 <= memory <= 100):
                raise ValueError()
            result = _host_metrics_empty('ok', None)
            result.update(cpu_usage='{:.1f}%'.format(cpu),
                          host_mem_usage='{:.1f}%'.format(memory),
                          host_metrics_sampled_at=_host_timestamp())
            return result
        except Exception:
            return _host_metrics_empty('error', '本机 CPU/内存采集失败')
    user = getattr(item, 'computing_user', None)
    password = getattr(item, 'computing_password', None)
    if not host or not user or password is None:
        return _host_metrics_empty('error', '未配置主机 SSH 登录信息')
    ssh = paramiko.SSHClient()
    try:
        # Preserve this platform's existing SSH host trust policy; use the
        # configured account with finite connect/auth/command timeouts.
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=3,
                    banner_timeout=3, auth_timeout=3,
                    allow_agent=False, look_for_keys=False)
        if binding:
            from service.computing_identity_service import identity_probe_source
            source = (identity_probe_source() + '\nimport os\n'
                      + 'os.execv("/bin/sh", ["sh", "-c", ' + repr(_HOST_READ_COMMAND) + '])\n')
            stdin, stdout, _ = ssh.exec_command('python3 -', timeout=4)
            stdin.write('exec(' + ascii(source) + ')')
            stdin.channel.shutdown_write()
        else:
            _, stdout, _ = ssh.exec_command(_HOST_READ_COMMAND, timeout=4)
        channel = stdout.channel
        deadline = time.monotonic() + 4
        chunks = []
        size = 0
        while True:
            if time.monotonic() >= deadline:
                raise socket.timeout()
            if channel.recv_ready():
                chunk = channel.recv(4096)
                size += len(chunk)
                if size > 65536:
                    return _host_metrics_empty('error', '主机采集输出异常')
                chunks.append(chunk)
            if channel.recv_stderr_ready():
                channel.recv_stderr(4096)  # Drain without exposing remote output.
            if (channel.exit_status_ready() and not channel.recv_ready()
                    and not channel.recv_stderr_ready()):
                break
            time.sleep(0.02)
        if channel.recv_exit_status() != 0:
            return _host_metrics_empty('error', '主机不支持当前 Linux 采集命令')
        output = b''.join(chunks).decode('utf-8', 'replace')
        if binding:
            from common.platform_host_identity import IdentityConflict, _verify_anchor
            identity_line, _, output = output.partition('\n')
            try:
                identity = json.loads(identity_line)
                if identity['host_uid'] != binding['host_uid']:
                    raise IdentityConflict('当前地址对应另一台设备')
                _verify_anchor(binding.get('anchor_uid'), identity.get('anchor_uid'))
            except (ValueError, KeyError, TypeError, AttributeError):
                return _host_metrics_empty('error', '当前 SSH 主机的设备身份与已绑定设备不一致')
        return _parse_host_sample(output)
    except paramiko.AuthenticationException:
        return _host_metrics_empty('error', '主机 SSH 账号认证失败')
    except (socket.timeout, TimeoutError):
        return _host_metrics_empty('error', '主机 CPU/内存采集超时')
    except Exception:
        # Exception messages can contain connection details; expose a fixed
        # message rather than credentials or remote command output.
        return _host_metrics_empty('error', '无法连接主机或读取 CPU/内存指标')
    finally:
        ssh.close()


def _host_metrics_client():
    global _HOST_METRICS_REDIS
    if _HOST_METRICS_REDIS is None:
        _HOST_METRICS_REDIS = host_metrics_redis.Redis(
            host=Redis_ip, port=int(Redis_port), password=Redis_password, db=2,
            protocol=2, socket_connect_timeout=1, socket_timeout=1)
    return _HOST_METRICS_REDIS


def _host_cached_metrics(client, key):
    cached = client.get(key)
    if not cached:
        return None
    try:
        data = json.loads(cached)
        if isinstance(data, dict) and all(name in data for name in (
                'cpu_usage', 'host_mem_usage', 'host_metrics_sampled_at',
                'host_metrics_status', 'host_metrics_error')):
            return data
    except (ValueError, TypeError):
        pass
    return None


def _host_local_metrics(item, key, binding=None):
    with _HOST_LOCAL_GUARD:
        lock = _HOST_LOCAL_LOCKS.setdefault(key, threading.Lock())
    if not lock.acquire(timeout=1):
        return _host_metrics_empty('collecting', '主机指标正在采集，请稍后刷新')
    try:
        with _HOST_LOCAL_GUARD:
            now = time.monotonic()
            expired = [name for name, (at, _) in _HOST_LOCAL_CACHE.items() if now - at >= _HOST_METRICS_TTL]
            for name in expired:
                _HOST_LOCAL_CACHE.pop(name)
            cached = _HOST_LOCAL_CACHE.get(key)
        if cached:
            return cached[1]
        result = _sample_host_metrics(item, binding)
        with _HOST_LOCAL_GUARD:
            _HOST_LOCAL_CACHE[key] = (time.monotonic(), result)
        return result
    finally:
        lock.release()


def _host_metrics_key(item, binding=None):
    identity = ('machine:' + binding['host_uid']) if binding else ('registry:' + str(item.id))
    return 'v3:resource_view:host_metrics:' + hashlib.sha256(identity.encode('utf-8')).hexdigest()


def _publish_host_metrics(item, result, binding=None):
    """Share the collector's fresh observation without adding a new sample.

    The collector keeps its existing cadence and lock. The UI uses the same
    bounded cache, identity and error semantics as its own measurements.
    Cache failure must not affect admission or cause a second SSH request.
    """
    try:
        _host_metrics_client().setex(_host_metrics_key(item, binding), _HOST_METRICS_TTL,
                                     json.dumps(result, ensure_ascii=False))
        return True
    except Exception:
        return False


def _get_host_metrics(item, binding=None):
    key = _host_metrics_key(item, binding)
    token = uuid.uuid4().hex
    try:
        client = _host_metrics_client()
        cached = _host_cached_metrics(client, key)
        if cached:
            return cached
        if not client.set(key + ':lock', token, nx=True, ex=_HOST_METRICS_LOCK_TTL):
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                time.sleep(0.1)
                cached = _host_cached_metrics(client, key)
                if cached:
                    return cached
            return _host_metrics_empty('collecting', '主机指标正在采集，请稍后刷新')
    except Exception:
        return _host_local_metrics(item, key, binding)
    try:
        result = _sample_host_metrics(item, binding)
        try:
            client.setex(key, _HOST_METRICS_TTL, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass
        return result
    finally:
        try:
            # Release only our token, never another worker's renewed lock.
            client.eval("if redis.call('get',KEYS[1]) == ARGV[1] then "
                        "return redis.call('del',KEYS[1]) else return 0 end",
                        1, key + ':lock', token)
        except Exception:
            pass  # The finite lock TTL recovers even if Redis is unavailable.


def _resource_task_counts(configs):
    from collections import Counter
    from service.algorithm_config_safety import literal_data

    def data_list(value):
        try:
            decoded = literal_data(value)
            return decoded if isinstance(decoded, list) else []
        except (TypeError, ValueError):
            return []

    counts = Counter()
    for config in configs:
        resource_id = config.resource_id
        if resource_id is not None:
            counts[int(resource_id)] += 1
        children = data_list(getattr(config, 'model_algo_data_ori', None))
        if not children:
            # Historical model_algo_data starts with the primary model.
            children = data_list(getattr(config, 'model_algo_data', None))[1:]
        for child in children:
            if not isinstance(child, dict):
                continue
            candidate = child.get('resource_id')
            if isinstance(candidate, (str, int)) and str(candidate).isdigit() and int(candidate) > 0:
                counts[int(candidate)] += 1
            elif resource_id is not None:
                counts[int(resource_id)] += 1
    return counts


def _current_resource_slots(resources):
    """Choose the machine-ID sample ahead of older address-based duplicates."""
    from common.platform_host_identity import card_serial
    slots = {}
    for card in resources:
        logical_id = card['dev_id']
        key = ('slot', logical_id) if logical_id is not None else ('legacy', card['id'])
        slots.setdefault(key, []).append(card)
    for cards in slots.values():
        current = min(cards, key=lambda card: (
            not bool(card['identity_sample']), card['sample_age'] is None,
            float(card['sample_age'] or 0), card['id']))
        serial = card_serial(current['dev_get_sn'])
        related_ids = [card['id'] for card in cards
                       if not serial or card_serial(card['dev_get_sn']) in (None, serial)]
        yield current, serial, related_ids


def _current_resources(resources, counts, now):
    grouped = {}
    for current, serial, related_ids in _current_resource_slots(resources):
        resource = {key: value for key, value in current.items() if key not in ('sample_age', 'sample_token')}
        age = float(current['sample_age']) if current['sample_age'] is not None else None
        resource['card_data_updated_at'] = (
            (now - timedelta(seconds=age)).isoformat(timespec='milliseconds')
            if age is not None and age >= 0 else None)
        resource['resource_num'] = sum(counts.get(resource_id, 0) for resource_id in related_ids)
        resource['identity_sample'] = bool(current['identity_sample'])
        label = 'YGSJ-TPU-' + (serial or str(current['dev_get_target'] or '未知'))
        grouped.setdefault(label, []).append(resource)
    return grouped


class ResourceViewService:
    @staticmethod
    def get_resource_data():
        """Get current host and card measurements without using IP as identity."""
        try:
            from service.computing_identity_service import binding_map

            hosts = [host for host in ResourceViewData.get_all_computing_equipment()
                     if int(getattr(host, 'server_type', 1) or 1) == 1]
            if not hosts:
                return True, []
            bindings = binding_map()
            counts = _resource_task_counts(ResourceViewData.get_valid_algorithm_configs())
            result = []
            for host in hosts:
                binding = bindings.get(host.id)
                host_metrics = _get_host_metrics(host, binding)
                cards = ResourceViewData.get_resource_usage_by_computing_id(host.id)
                now = datetime.now(timezone.utc)
                result.append({
                    'computing_id': host.id,
                    'computing_ip': host.computing_ip,
                    'computing_name': host.computing_name,
                    'host_uid': binding['host_uid'] if binding else None,
                    **host_metrics,
                    'host_metrics_server_time': now.isoformat(timespec='milliseconds'),
                    'grouped_resources': _current_resources(cards, counts, now),
                })
            return True, result
        except Exception:
            return False, '获取算力资源数据失败，请检查服务和数据库'


    # 算力设备相关业务逻辑
    @staticmethod
    def add_computing_equipment(computing_ip, computing_name, computing_user, computing_password):
        from service.computing_identity_service import add
        return add(computing_ip,computing_name,computing_user,computing_password)

    @staticmethod
    def delete_computing_equipment(id):
        """
        删除算力设备
        """
        try:
            # 参数校验
            if not id:
                return False, '要删除ID未填写'

            # 检查设备是否存在
            computing_detail = ResourceViewData.get_computing_equipment_by_id(id)
            if not computing_detail:
                return False, '算力机器不存在'

            # 删除设备
            ResourceViewData.delete_computing_equipment(id)

            return True, '删除成功'
        except Exception as e:
            return False, f'删除算力设备失败: {str(e)}'

    @staticmethod
    def update_computing_equipment(id, computing_ip=None, computing_name=None, computing_user=None, computing_password=None):
        from service.computing_identity_service import update
        return update(id,computing_ip,computing_name,computing_user,computing_password)

    @staticmethod
    def get_computing_equipment_paginated(page, per_page):
        """
        分页获取算力设备信息
        """
        try:
            # 获取分页数据
            pagination = ResourceViewData.get_computing_equipment_paginated(page, per_page)

            # 构造返回数据
            from service.computing_identity_service import SAVED_SECRET_MASK, uid_map
            _identity_uids=uid_map()
            data_list = [
                {
                    'id': item.id,
                    'computing_ip': item.computing_ip,
                    'computing_name': item.computing_name,
                    'computing_user': item.computing_user,
                    # The existing edit form submits this placeholder to keep the saved value.
                    'computing_password': SAVED_SECRET_MASK if item.computing_password else '',
                    'computing_code': item.computing_code,
                    'host_uid': _identity_uids.get(item.id),
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                    'computing_status': item.computing_status
                }
                for item in pagination.items
            ]

            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }

            return True, {
                'code': 200,
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取算力设备列表失败: {str(e)}'
