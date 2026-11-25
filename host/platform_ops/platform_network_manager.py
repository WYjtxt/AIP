"""Scoped NetworkManager IPv4 transactions; importing this module performs no I/O.

The caller persists each plan before mutation and owns the independent watchdog,
platform migration, and management-client confirmations. nmcli 1.32 has no
atomic versioned update: selected-profile checks detect stale edits, while a
maintenance window must exclude concurrent manual writes to that profile.
"""
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

NMCLI = '/usr/bin/nmcli'
IP = '/usr/sbin/ip'
ARPING = '/usr/sbin/arping'
MAX_OUTPUT = 2 * 1024 * 1024
VERSION = 1
PROFILE_FIELDS = (
    'connection.uuid', 'connection.id', 'connection.interface-name', 'connection.type',
    'connection.master', 'connection.slave-type', 'connection.autoconnect',
    '802-3-ethernet.mac-address', 'ipv4.method', 'ipv4.addresses', 'ipv4.gateway',
    'ipv4.never-default', 'ipv4.route-metric', 'ipv4.routes', 'ipv4.dns',
    'ipv4.ignore-auto-dns',
)
WRITABLE = frozenset(('connection.autoconnect', 'ipv4.method', 'ipv4.addresses', 'ipv4.gateway',
                      'ipv4.never-default', 'ipv4.route-metric', 'ipv4.dns'))
IFNAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}')
UUID = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')


class NetworkError(ValueError):
    def __init__(self, message, code='network_error'):
        super().__init__(message)
        self.code = code


def _require(condition, message, code='invalid_request'):
    if not condition:
        raise NetworkError(message, code)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _fingerprint(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _run(arguments, timeout=8):
    return subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        env=dict(os.environ, LC_ALL='C', LANG='C', NO_COLOR='1'), check=False)


def _text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def _unescape(value):
    return re.sub(r'\\([:\\])', r'\1', value)


def _split(line):
    values, current, escaped = [], [], False
    for char in line:
        if escaped:
            current.append(char); escaped = False
        elif char == '\\':
            escaped = True
        elif char == ':':
            values.append(''.join(current)); current = []
        else:
            current.append(char)
    if escaped:
        current.append('\\')
    values.append(''.join(current))
    return values


def _empty(value):
    return '' if value in ('', '--', None) else str(value).strip()


def _list(value):
    return [item.strip() for item in _empty(value).split(',') if item.strip()]


def _cidr(value):
    try:
        result = ipaddress.IPv4Interface(value)
    except (ValueError, TypeError):
        raise NetworkError('IPv4 地址或前缀无效', 'invalid_request')
    address = result.ip
    _require(not (address.is_loopback or address.is_unspecified or address.is_multicast or address.is_link_local),
             '请选择有效的业务 IPv4 地址')
    _require(1 <= result.network.prefixlen <= 32, 'IPv4 前缀须为 1 至 32')
    _require(result.network.prefixlen >= 31 or address not in (result.network.network_address, result.network.broadcast_address),
             '不能使用子网地址或广播地址')
    return str(result)


def _ipv4(value):
    try:
        result = ipaddress.IPv4Address(value)
    except (ValueError, TypeError):
        raise NetworkError('IPv4 地址无效', 'invalid_request')
    _require(not (result.is_loopback or result.is_unspecified or result.is_multicast or result.is_link_local),
             'IPv4 地址不能为回环、链路本地、多播或空地址')
    return str(result)


def normalize_request(body):
    _require(isinstance(body, dict), '网口配置须为 JSON 对象')
    result = dict(body)
    for old, new in (('mode', 'operation'), ('ipv4', 'address'), ('prefix', 'prefixlen'),
                     ('platform_target', 'use_for_platform')):
        if old in result:
            _require(new not in result, '网口配置含重复别名字段')
            result[new] = result.pop(old)
    allowed = {'interface', 'connection_uuid', 'operation', 'replace_ipv4', 'address', 'prefixlen',
               'gateway', 'default_route', 'metric', 'dns', 'use_for_platform'}
    _require(not set(result) - allowed, '网口配置包含不支持的字段')
    name = result.get('interface')
    _require(isinstance(name, str) and IFNAME.fullmatch(name), '网口名称无效')
    identifier = result.get('connection_uuid')
    _require(identifier is None or isinstance(identifier, str) and UUID.fullmatch(identifier), '连接 UUID 无效')
    _require(result.get('operation') in ('add', 'replace'), '操作只允许新增或替换地址')
    prefix = result.get('prefixlen')
    _require(type(prefix) is int and 1 <= prefix <= 32, 'IPv4 前缀须为 1 至 32 的整数')
    address = _cidr(str(result.get('address')) + '/' + str(prefix))
    for key in ('default_route', 'use_for_platform'):
        _require(type(result.get(key, False)) is bool, key + ' 须为布尔值')
    gateway = result.get('gateway')
    _require(gateway is None or isinstance(gateway, str), '网关须为 IPv4 地址、空字符串或 null')
    if gateway not in (None, ''):
        gateway = _ipv4(gateway)
        network = ipaddress.IPv4Interface(address)
        _require(ipaddress.IPv4Address(gateway) in network.network and gateway != str(network.ip),
                 '首期仅支持同一子网内且不同于本机的网关')
    metric = result.get('metric')
    _require(metric is None or type(metric) is int and 0 <= metric <= 4294967295, '路由指标须为非负整数')
    default = result.get('default_route', False)
    _require(default or gateway is None and metric is None, '修改网关或路由指标须明确允许更改默认出口')
    _require(gateway in (None, '') or metric is not None, '指定默认网关时须明确填写路由指标')
    dns = result.get('dns')
    _require(dns is None or isinstance(dns, list) and len(dns) <= 8, 'DNS 须为最多 8 个 IPv4 地址的数组或 null')
    dns = list(dict.fromkeys(_ipv4(value) for value in dns)) if dns is not None else None
    old = result.get('replace_ipv4')
    if old is not None:
        old = _cidr(old)
    _require(result['operation'] == 'replace' or old is None, '新增地址不能同时删除原地址')
    return {'interface': name, 'connection_uuid': identifier, 'operation': result['operation'],
            'replace_ipv4': old, 'address': str(ipaddress.IPv4Interface(address).ip), 'prefixlen': prefix,
            'gateway': gateway, 'default_route': default, 'metric': metric, 'dns': dns,
            'use_for_platform': result.get('use_for_platform', False)}


class NetworkManagerDriver:
    def __init__(self, runner=None, physical=None, clock=None):
        self.runner = runner or _run
        self.physical = physical or (lambda name: (Path('/sys/class/net') / name / 'device').exists())
        self.clock = clock or time.time

    def _call(self, arguments, timeout=8):
        _require(arguments and arguments[0] in (NMCLI, IP), '网络命令不在白名单', 'unsupported')
        try:
            answer = self.runner(list(arguments), timeout=timeout)
            if isinstance(answer, str):
                return answer
            if isinstance(answer, dict):
                code, output = answer.get('returncode', answer.get('code', 0)), answer.get('stdout', answer.get('output', ''))
            else:
                code, output = answer.returncode, answer.stdout
            _require(code == 0, 'NetworkManager 命令未通过，请核对网口与连接状态', 'command_failed')
            result = _text(output)
            _require(len(result.encode('utf-8')) <= MAX_OUTPUT, '网络命令输出过大', 'invalid_output')
            return result
        except NetworkError:
            raise
        except subprocess.TimeoutExpired:
            raise NetworkError('网络操作超时，执行结果须核实后回滚', 'command_timeout')
        except (OSError, UnicodeError, TypeError, AttributeError):
            raise NetworkError('系统网络管理器暂不可用', 'unavailable')

    def _nm(self, arguments, timeout=8):
        return self._call([NMCLI, '--colors', 'no', '--escape', 'yes', '--terse'] + list(arguments), timeout)

    def _profile(self, identifier):
        _require(isinstance(identifier, str) and UUID.fullmatch(identifier), '连接 UUID 无效')
        output = self._nm(['--fields', ','.join(PROFILE_FIELDS), 'connection', 'show', 'uuid', identifier])
        result = {key: '' for key in PROFILE_FIELDS}
        for line in output.splitlines():
            key, separator, value = line.partition(':')
            _require(separator and key in result, '连接配置字段无法识别', 'invalid_output')
            result[key] = _empty(_unescape(value))
        _require(result['connection.uuid'] == identifier, '连接 UUID 已变化', 'conflict')
        for key in ('ipv4.addresses', 'ipv4.dns'):
            result[key] = ','.join(_list(result[key]))
        return result

    def inspect(self):
        try:
            version = self._call([NMCLI, '--version']).strip()[:120]
            states = {}
            for line in self._nm(['--fields', 'DEVICE,TYPE,STATE', 'device', 'status']).splitlines():
                cells = _split(line)
                _require(len(cells) == 3, '网口状态格式无法识别', 'invalid_output')
                states[cells[0]] = {'nm_type': cells[1], 'nm_state': cells[2]}
            active = {}
            for line in self._nm(['--fields', 'UUID,DEVICE', 'connection', 'show', '--active']).splitlines():
                cells = _split(line)
                _require(len(cells) == 2, '活动连接格式无法识别', 'invalid_output')
                for name in cells[1].split(','):
                    if name and name != '--':
                        active[name] = cells[0]
            identifiers = self._nm(['--get-values', 'UUID', 'connection', 'show']).splitlines()
            _require(len(identifiers) <= 256, '连接配置数量超出首期支持范围', 'unsupported')
            profiles = [self._profile(value.strip()) for value in identifiers if value.strip()]
            links = json.loads(self._call([IP, '-j', '-d', 'link', 'show']))
            addresses = json.loads(self._call([IP, '-j', '-4', 'address', 'show']))
            routes = json.loads(self._call([IP, '-j', '-4', 'route', 'show', 'table', 'main']))
            _require(all(isinstance(value, list) for value in (links, addresses, routes)), '网络清单格式无效', 'invalid_output')
            address_map = {row['ifname']: row for row in addresses}
            interfaces = []
            for link in links:
                name = link.get('ifname', '')
                _require(isinstance(name, str) and IFNAME.fullmatch(name), '系统网口名称无效', 'invalid_output')
                flags = link.get('flags', [])
                kind = (link.get('linkinfo') or {}).get('info_kind') or link.get('link_type', '')
                physical = bool(self.physical(name)) and kind in ('ether', 'ethernet')
                internal = bool(re.match(r'^(lo|docker\d*|veth.*|br-.*|virbr\d*|cni\d*|flannel.*|endvnic|tun\d*|tap\d*)$', name))
                state = states.get(name, {})
                blocked = ('首期仅支持实体以太网口' if not physical or internal else
                           '该网口属于桥接或绑定连接，请管理其上层逻辑接口' if link.get('master') else
                           '该网口未受 NetworkManager 管理' if state.get('nm_state') == 'unmanaged' or not state else '')
                carrier = True if 'LOWER_UP' in flags else False if 'NO-CARRIER' in flags or link.get('operstate') == 'DOWN' else None
                live = [{'address': row.get('local', row.get('address')), 'prefixlen': row['prefixlen'],
                         'cidr': str(row.get('local', row.get('address'))) + '/' + str(row['prefixlen']), 'family': 'inet'}
                        for row in address_map.get(name, {}).get('addr_info', []) if row.get('family') == 'inet']
                matching = []
                for profile in profiles:
                    belongs = (profile['connection.interface-name'] == name
                               or profile['connection.uuid'] == active.get(name)
                               or profile['802-3-ethernet.mac-address'] and profile['802-3-ethernet.mac-address'].lower() == str(link.get('address')).lower())
                    if belongs and profile['connection.type'] == '802-3-ethernet' and not profile['connection.master'] and not profile['connection.slave-type']:
                        matching.append(self._public_profile(profile, active.get(name) == profile['connection.uuid']))
                selected = next((profile for profile in matching if profile['active']), matching[0] if len(matching) == 1 else None)
                if not blocked and not matching:
                    blocked = '该网口没有受支持的绑定连接，请先建立 NetworkManager 连接'
                if not blocked and selected and selected['active'] and selected['method'] != 'manual':
                    blocked = '首期不修改活动 DHCP 或非手动连接'
                interfaces.append({'name': name, 'interface': name, 'index': link.get('ifindex'), 'type': kind,
                    'physical': physical and not internal, 'carrier': carrier,
                    'admin_up': 'UP' in flags,
                    'link_state': 'UP' if carrier is True else 'DOWN' if carrier is False else 'UNKNOWN',
                    'addresses': live, 'connection_uuid': selected['uuid'] if selected else None,
                    'active_connection_uuid': active.get(name), 'profiles': matching,
                    'editable': not bool(blocked), 'blocked_reason': blocked,
                    'gateway': selected['gateway'] if selected else None,
                    'metric': selected['metric'] if selected else None, 'dns': selected['dns'] if selected else []})
            data = {'available': True, 'backend': 'NetworkManager', 'version': version, 'reason': '',
                    'interfaces': interfaces, 'routes': routes, 'profiles': profiles}
            data['revision'] = _fingerprint(data)
            return data
        except (NetworkError, ValueError, KeyError, TypeError) as error:
            return {'available': False, 'backend': 'NetworkManager', 'version': None,
                    'reason': str(error) if isinstance(error, NetworkError) else '系统网络清单暂无法解析',
                    'revision': None, 'interfaces': [], 'routes': [], 'profiles': []}

    @staticmethod
    def _public_profile(profile, active):
        metric = profile['ipv4.route-metric']
        return {'uuid': profile['connection.uuid'], 'name': profile['connection.id'],
                'interface': profile['connection.interface-name'], 'method': profile['ipv4.method'],
                'addresses': _list(profile['ipv4.addresses']), 'gateway': profile['ipv4.gateway'] or None,
                'metric': int(metric) if metric and metric != '-1' else None,
                'dns': _list(profile['ipv4.dns']), 'never_default': profile['ipv4.never-default'] == 'yes', 'active': active}

    def plan(self, body, revision=None):
        request = normalize_request(body)
        inventory = self.inspect()
        _require(inventory['available'], inventory['reason'], 'unavailable')
        _require(revision is None or revision == inventory['revision'], '预览前网络配置已变化，请刷新', 'conflict')
        interface = next((row for row in inventory['interfaces'] if row['name'] == request['interface']), None)
        _require(interface is not None and interface['editable'], interface['blocked_reason'] if interface else '网口不存在', 'unsupported')
        identifier = request['connection_uuid'] or interface['connection_uuid']
        _require(identifier is not None, '网口存在多个连接，请明确选择连接 UUID')
        _require(any(row['uuid'] == identifier for row in interface['profiles']), '连接不属于所选实体网口', 'conflict')
        active = interface['active_connection_uuid']
        _require(active in (None, identifier), '所选网口正在使用另一个连接，请重新选择', 'conflict')
        before = next(row for row in inventory['profiles'] if row['connection.uuid'] == identifier)
        _require(before['ipv4.method'] in ('manual', 'auto', 'disabled'), '该 IPv4 配置方式不在首期支持范围', 'unsupported')
        _require(not (active and before['ipv4.method'] != 'manual'), '首期不修改活动 DHCP 或非手动连接', 'unsupported')
        _require(active or not interface['addresses'], '未激活连接的网口上已有外部配置地址，请先核实', 'conflict')
        candidate = request['address'] + '/' + str(request['prefixlen'])
        old = _list(before['ipv4.addresses'])
        _require(all(_cidr(value) == value for value in old), '原地址配置无法安全解析', 'unsupported')
        _require(all(ipaddress.IPv4Interface(value).ip != ipaddress.IPv4Interface(candidate).ip or value == candidate for value in old),
                 '首期不支持同一 IP 在线切换前缀', 'unsupported')
        for row in inventory['interfaces']:
            for value in row['addresses']:
                if value['address'] == request['address']:
                    _require(row['name'] == request['interface'] and value['cidr'] == candidate,
                             '该 IP 已用于另一个网口或不同前缀，未执行更改', 'conflict')
        replace = request['replace_ipv4']
        if request['operation'] == 'replace':
            if replace is None and len(old) == 1:
                replace = old[0]
            _require(replace in old, '替换时须明确选择该连接中的一个原 CIDR')
            _require(replace != candidate, '新旧地址相同，请改用新增或保留现有配置')
            _require(ipaddress.IPv4Interface(replace).ip != ipaddress.IPv4Interface(candidate).ip,
                     '首期不支持同一 IP 在线切换前缀', 'unsupported')
        request.update(connection_uuid=identifier, replace_ipv4=replace)
        staged = dict(before)
        staged['ipv4.addresses'] = ','.join(old + ([] if candidate in old else [candidate]))
        staged['ipv4.method'] = 'manual'
        if active is None:
            staged['connection.autoconnect'] = 'yes'
            if not request['default_route']:
                _require(not before['ipv4.gateway'],
                         '该未启用连接预设了网关；请明确允许默认出口，或允许更改出口并显式清除网关', 'unsupported')
                _require('0.0.0.0/0' not in before['ipv4.routes'] and not re.search(r'\bdefault\b', before['ipv4.routes']),
                         '未启用的连接含显式默认路由，请先核实以免新增默认出口', 'unsupported')
                staged['ipv4.never-default'] = 'yes'
        if request['default_route']:
            if request['gateway'] is not None:
                _require('0.0.0.0/0' not in before['ipv4.routes'], '该连接含显式默认路由，请先核实，避免覆盖独立路由', 'unsupported')
                staged['ipv4.gateway'] = request['gateway']
                if request['gateway']:
                    staged['ipv4.never-default'] = 'no'
            if request['metric'] is not None:
                staged['ipv4.route-metric'] = str(request['metric'])
        if request['dns'] is not None:
            staged['ipv4.dns'] = ','.join(request['dns'])
        _require(active is not None or staged != before,
                 '连接配置已相同，无需修改；当前流程不支持未激活连接的纯启用，请提交实际配置变化', 'unsupported')
        final = dict(staged)
        if replace is not None:
            final['ipv4.addresses'] = ','.join(value for value in _list(staged['ipv4.addresses']) if value != replace)
        if final['ipv4.gateway'] and final['ipv4.never-default'] != 'yes':
            _require(any(ipaddress.IPv4Address(final['ipv4.gateway']) in ipaddress.IPv4Interface(value).network
                         for value in _list(final['ipv4.addresses'])),
                     '最终地址无法直达保留的网关，请明确配置同网段网关', 'unsupported')
        recovery = dict(staged)
        recovery['ipv4.addresses'] = ','.join(dict.fromkeys(old + _list(staged['ipv4.addresses'])))
        for key in ('ipv4.gateway', 'ipv4.never-default', 'ipv4.route-metric', 'ipv4.dns'):
            recovery[key] = before[key]
        if active is None:
            # This profile had no active default before the transaction.
            # Suppress it until the final down/restore, including NM 1.32's
            # normalization that clears a gateway with never-default=yes.
            recovery['ipv4.gateway'] = ''
            recovery['ipv4.never-default'] = 'yes'
        owned = sorted(key for key in WRITABLE if before[key] != staged[key]
                       or staged[key] != final[key] or before[key] != recovery[key])
        plan = {'version': VERSION, 'id': uuid.uuid4().hex, 'interface': request['interface'],
                'connection_uuid': identifier, 'request': request, 'before': before, 'staged': staged,
                'final': final, 'recovery': recovery, 'owned_fields': owned, 'active_before': active, 'phase': 'planned',
                'created_at': self.clock(), 'inventory_revision': inventory['revision'],
                'before_fingerprint': _fingerprint(before),
                'staged_fingerprint': _fingerprint(staged), 'final_fingerprint': _fingerprint(final),
                'warnings': ['链路与本机地址正常不代表管理端可达；须由独立回滚任务与新地址确认保护'],
                'checkpoint': {'kind': 'selected_profile_snapshot', 'native_checkpoint': False}}
        if active is None and before['connection.autoconnect'] != 'yes':
            plan['warnings'].append('本次启用的连接将自动连接，成功后重启或重新插线仍会生效；回滚恢复原开关')
        plan['recovery_fingerprint'] = _fingerprint(recovery)
        plan['fingerprint'] = self._seal(plan)
        return plan

    @staticmethod
    def _seal(plan):
        return _fingerprint({key: value for key, value in plan.items() if key not in
                            ('fingerprint', 'phase', 'idempotent', 'external_active_profile_preserved')})

    def _check(self, plan):
        _require(isinstance(plan, dict) and plan.get('version') == VERSION
                 and plan.get('fingerprint') == self._seal(plan), '网络事务记录无效', 'invalid_receipt')
        request = normalize_request(plan.get('request'))
        _require(request['interface'] == plan.get('interface') and request['connection_uuid'] == plan.get('connection_uuid'),
                 '网络事务网口与连接不一致', 'invalid_receipt')
        _require(set(plan.get('owned_fields', [])) <= WRITABLE, '网络事务包含越界属性', 'invalid_receipt')
        for name in ('before', 'staged', 'final', 'recovery'):
            _require(set(plan.get(name, {})) == set(PROFILE_FIELDS)
                     and plan[name]['connection.uuid'] == plan['connection_uuid'], '网络事务快照无效', 'invalid_receipt')

    def _current(self, plan):
        self._check(plan)
        inventory = self.inspect()
        _require(inventory['available'], inventory['reason'], 'unavailable')
        interface = next((row for row in inventory['interfaces'] if row['name'] == plan['interface']), None)
        _require(interface is not None and interface['editable'], '事务网口已不存在或不再受支持', 'conflict')
        _require(any(row['uuid'] == plan['connection_uuid'] for row in interface['profiles']), '连接的网口关联已改变', 'conflict')
        profile = next(row for row in inventory['profiles'] if row['connection.uuid'] == plan['connection_uuid'])
        _require(all(profile[key] == plan['before'][key] for key in
                     ('connection.interface-name', 'connection.type', 'connection.master',
                      'connection.slave-type', '802-3-ethernet.mac-address')),
                 '连接身份或上层绑定已变化，未覆盖', 'conflict')
        return inventory, interface, profile

    @staticmethod
    def _unique_candidate(plan, inventory):
        for interface in inventory['interfaces']:
            for value in interface['addresses']:
                if value['address'] == plan['request']['address']:
                    _require(interface['name'] == plan['interface'] and value['prefixlen'] == plan['request']['prefixlen'],
                             '候选 IP 已用于其他网口或不同前缀', 'conflict')

    def _modify(self, identifier, changes):
        if not changes:
            return
        _require(set(changes) <= WRITABLE, '只允许修改本事务拥有的 IPv4 与自动连接属性', 'invalid_receipt')
        arguments = ['connection', 'modify', 'uuid', identifier]
        for key, value in sorted(changes.items()):
            arguments.extend((key, value))
        self._nm(arguments)

    def _activate(self, interface, identifier, active):
        _require(active in (None, identifier), '另一连接已占用目标网口，未覆盖', 'conflict')
        if active == identifier:
            self._nm(['--wait', '15', 'device', 'reapply', interface], timeout=20)
        else:
            self._nm(['--wait', '20', 'connection', 'up', 'uuid', identifier, 'ifname', interface], timeout=25)

    def _duplicate_probe(self, plan, interface):
        if any(row['address'] == plan['request']['address'] for row in interface['addresses']):
            return
        arguments = [ARPING, '-D', '-I', plan['interface'], '-c', '2', '-w', '3', plan['request']['address']]
        try:
            answer = self.runner(arguments, timeout=6)
            code = (answer.get('returncode', answer.get('code')) if isinstance(answer, dict)
                    else getattr(answer, 'returncode', None))
        except (OSError, subprocess.TimeoutExpired):
            raise NetworkError('无法完成候选 IP 冲突检查，未修改连接', 'dad_unavailable')
        # iputils -D succeeds with zero only when no duplicate reply arrived.
        if code == 1:
            raise NetworkError('候选 IP 已被其它设备使用，未修改连接', 'address_conflict')
        _require(code == 0, '无法判断候选 IP 是否冲突，未修改连接', 'dad_unavailable')

    def stage_candidate(self, plan):
        result = copy.deepcopy(plan)
        inventory, interface, current = self._current(result)
        self._unique_candidate(result, inventory)
        _require(interface['carrier'] is True, '网口尚未插线或链路未就绪，未修改连接', 'waiting_link')
        _require(interface['active_connection_uuid'] in (None, result['connection_uuid']), '网口活动连接已改变', 'conflict')
        _require(current == result['before'] or current == result['staged'], '预览后连接已被修改，未覆盖', 'conflict')
        _require(not (interface['active_connection_uuid'] and current['ipv4.method'] != 'manual'),
                 '连接已自动激活 DHCP，请重新核实后预览', 'conflict')
        self._duplicate_probe(result, interface)
        inventory, interface, after_probe = self._current(result)
        self._unique_candidate(result, inventory)
        _require(interface['carrier'] is True and after_probe == current,
                 '冲突检查期间网口或连接发生变化，未覆盖', 'conflict')
        if current == result['staged']:
            result.update(phase='staged', idempotent=True)
        else:
            self._modify(result['connection_uuid'], {key: result['staged'][key] for key in result['owned_fields']
                if current[key] != result['staged'][key]})
            result.update(phase='staged', idempotent=False)
        if result['owned_fields'] or interface['active_connection_uuid'] != result['connection_uuid']:
            self._activate(result['interface'], result['connection_uuid'], interface['active_connection_uuid'])
        actual = self._profile(result['connection_uuid'])
        _require(all(actual[key] == result['staged'][key] for key in result['owned_fields']),
                 '候选配置应用后出现外部变化，请核实并回滚', 'conflict')
        return result

    def ready(self, plan):
        try:
            inventory, interface, current = self._current(plan)
            self._unique_candidate(plan, inventory)
            candidate = plan['request']['address'] + '/' + str(plan['request']['prefixlen'])
            fields_match = all(current[key] in (plan['staged'][key], plan['final'][key]) for key in plan['owned_fields'])
            present = any(value['cidr'] == candidate for value in interface['addresses'])
            active = interface['active_connection_uuid'] == plan['connection_uuid']
            gateway = plan['request']['gateway'] if plan['request']['default_route'] else None
            route = (not gateway or any(row.get('dst') == 'default' and row.get('gateway') == gateway
                     and row.get('dev') == plan['interface'] and
                     (plan['request']['metric'] is None or row.get('metric', 0) == plan['request']['metric'])
                     for row in inventory['routes']))
            ready = interface['carrier'] is True and present and active and fields_match and route
            return {'ready': ready, 'carrier': interface['carrier'], 'address_present': present,
                    'active_connection_matches': active, 'profile_matches': fields_match, 'route_matches': route,
                    'reachability_verified': False, 'reason': '' if ready else '正在等待候选地址、链路与请求路由就绪'}
        except NetworkError as error:
            return {'ready': False, 'reachability_verified': False, 'reason': str(error), 'error_code': error.code}

    def finalize(self, plan):
        result = copy.deepcopy(plan)
        inventory, interface, current = self._current(result)
        self._unique_candidate(result, inventory)
        _require(interface['carrier'] is True, '确认前链路已断开，请恢复或回滚', 'waiting_link')
        _require(self.ready(result)['ready'], '候选地址或请求路由尚未就绪，未移除原地址', 'not_ready')
        for key in result['owned_fields']:
            _require(current[key] in (result['staged'][key], result['final'][key]), '确认前所选属性已被外部修改，未覆盖', 'conflict')
        changes = {key: result['final'][key] for key in result['owned_fields'] if current[key] != result['final'][key]}
        self._modify(result['connection_uuid'], changes)
        if changes:
            self._activate(result['interface'], result['connection_uuid'], interface['active_connection_uuid'])
        actual = self._profile(result['connection_uuid'])
        _require(all(actual[key] == result['final'][key] for key in result['owned_fields']), '最终配置出现外部变化，请核实并回滚', 'conflict')
        result.update(phase='finalized', idempotent=not bool(changes))
        return result

    def rollback(self, plan):
        result = copy.deepcopy(plan)
        inventory, interface, current = self._current(result)
        for key in result['owned_fields']:
            _require(current[key] in (result['before'][key], result['staged'][key], result['final'][key], result['recovery'][key]),
                     '回滚发现所选属性被外部修改，已停止以免覆盖人工配置', 'conflict')
        changes = {key: result['before'][key] for key in result['owned_fields'] if current[key] != result['before'][key]}
        active = interface['active_connection_uuid']
        external = active not in (None, result['connection_uuid'])
        if changes and result['active_before'] is None and active == result['connection_uuid']:
            self._nm(['--wait', '15', 'connection', 'down', 'uuid', result['connection_uuid']], timeout=20)
            active = None
        self._modify(result['connection_uuid'], changes)
        if changes and result['active_before'] == result['connection_uuid'] and not external and interface['carrier'] is True:
            self._activate(result['interface'], result['connection_uuid'], active)
        actual = self._profile(result['connection_uuid'])
        _require(all(actual[key] == result['before'][key] for key in result['owned_fields']), '回滚后配置不一致，请人工核实', 'conflict')
        result.update(phase='rolled_back', idempotent=not bool(changes), external_active_profile_preserved=external)
        return result

    def prepare_rollback(self, plan):
        """Restore old reachability while retaining the candidate for recovery.

        The caller restores platform files/listeners next. Only a subsequent
        rollback retires a candidate that this transaction introduced.
        """
        result = copy.deepcopy(plan)
        inventory, interface, current = self._current(result)
        for key in result['owned_fields']:
            _require(current[key] in (result['before'][key], result['staged'][key], result['final'][key], result['recovery'][key]),
                     '准备恢复时发现外部修改，已保留候选地址', 'conflict')
        if all(current[key] == result['before'][key] for key in result['owned_fields']):
            result.update(phase='rollback_prepared', idempotent=True)
            return result
        active = interface['active_connection_uuid']
        _require(active in (None, result['connection_uuid']), '另一个连接已占用网口，保留现场配置', 'conflict')
        changes = {key: result['recovery'][key] for key in result['owned_fields'] if current[key] != result['recovery'][key]}
        self._modify(result['connection_uuid'], changes)
        if changes and interface['carrier'] is True:
            self._activate(result['interface'], result['connection_uuid'], active)
        actual = self._profile(result['connection_uuid'])
        _require(all(actual[key] == result['recovery'][key] for key in result['owned_fields']),
                 '旧地址恢复过渡态未确认，请保留候选地址核实', 'conflict')
        result.update(phase='rollback_prepared', idempotent=not bool(changes))
        return result


def inspect():
    return NetworkManagerDriver().inspect()


def plan(request, revision=None):
    return NetworkManagerDriver().plan(request, revision)


def stage_candidate(receipt):
    return NetworkManagerDriver().stage_candidate(receipt)


def ready(receipt):
    return NetworkManagerDriver().ready(receipt)


def finalize(receipt):
    return NetworkManagerDriver().finalize(receipt)


def rollback(receipt):
    return NetworkManagerDriver().rollback(receipt)


def prepare_rollback(receipt):
    return NetworkManagerDriver().prepare_rollback(receipt)
