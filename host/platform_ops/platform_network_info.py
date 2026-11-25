"""Read-only host interface inventory; addresses never identify a machine.

The host operations service calls this module in the host network namespace.
Only IPv4 addresses are candidates for the platform's current IPv4 settings.
No interface name, index, MAC or address is persisted by this module.
"""
import ipaddress
import json
import re
import subprocess
import time


MAX_OUTPUT = 2 * 1024 * 1024
TIMEOUT = 4


def _run(arguments):
    answer = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=TIMEOUT, check=False)
    if answer.returncode:
        raise RuntimeError('Network inventory query failed')
    return answer.stdout


def _records(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if not isinstance(value, str) or len(value) > MAX_OUTPUT:
        raise ValueError('Invalid network inventory')
    data = json.loads(value)
    if not isinstance(data, list) or len(data) > 4096:
        raise ValueError('Invalid network inventory')
    return data


def _name(value):
    if (not isinstance(value, str) or not 0 < len(value) <= 64
            or any(ord(c) < 32 or c.isspace() for c in value) or '/' in value):
        raise ValueError('Invalid interface name')
    return value


def _index(value):
    if type(value) is not int or not 0 < value < 2 ** 31:
        raise ValueError('Invalid interface index')
    return value


def _flags(value):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError('Invalid interface flags')
    return set(item.upper() for item in value)


def _kind(row):
    info = row.get('linkinfo') or {}
    if not isinstance(info, dict):
        raise ValueError('Invalid link metadata')
    value = info.get('info_kind') or row.get('link_type') or 'unknown'
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,48}', value):
        return 'unknown'
    return value.lower()


def _internal(name, kind, flags):
    # A business bridge, bond or VLAN is valid. Only known host/container
    # infrastructure interfaces are hidden from default address candidates.
    return (name == 'lo' or 'LOOPBACK' in flags or kind in ('loopback', 'veth')
            or bool(re.match(r'^(docker\d*|veth.*|br-[a-f0-9]{12}|cni\d*|flannel[.\d]*|virbr\d*)$', name)))


def _carrier(row, flags):
    value = row.get('carrier')
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    if 'NO-CARRIER' in flags:
        return False
    if 'LOWER_UP' in flags:
        return True
    return None


def _interfaces(address_rows, link_rows):
    links, names = {}, set()
    for row in link_rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid link row')
        index, name = _index(row.get('ifindex')), _name(row.get('ifname'))
        if index in links or name in names:
            raise ValueError('Duplicate link row')
        links[index] = row
        names.add(name)
    rows, seen = [], set()
    for address_row in address_rows:
        if not isinstance(address_row, dict):
            raise ValueError('Invalid address row')
        index = _index(address_row.get('ifindex'))
        name = _name(address_row.get('ifname'))
        if index in seen:
            raise ValueError('Duplicate address row')
        seen.add(index)
        details = links.get(index, address_row)
        if details.get('ifname') != name:
            raise ValueError('Interface changed during discovery')
        flags = _flags(details.get('flags', address_row.get('flags', [])))
        kind = _kind(details)
        internal = _internal(name, kind, flags)
        operstate = str(details.get('operstate', address_row.get('operstate', 'UNKNOWN'))).upper()
        if operstate not in ('UP', 'DOWN', 'UNKNOWN', 'LOWERLAYERDOWN', 'DORMANT', 'NOTPRESENT', 'TESTING'):
            operstate = 'UNKNOWN'
        carrier = _carrier(details, flags)
        admin_up = 'UP' in flags
        down = not admin_up or carrier is False or operstate in ('DOWN', 'LOWERLAYERDOWN', 'NOTPRESENT')
        link_state = 'DOWN' if down else 'UP' if carrier is True or operstate == 'UP' else 'UNKNOWN'
        addresses = []
        values = address_row.get('addr_info', [])
        if not isinstance(values, list):
            raise ValueError('Invalid address list')
        for value in values:
            if not isinstance(value, dict):
                raise ValueError('Invalid address metadata')
            if value.get('family') != 'inet':
                continue
            address = ipaddress.IPv4Address(value.get('local', value.get('address')))
            prefix = value.get('prefixlen')
            if type(prefix) is not int or not 0 <= prefix <= 32:
                raise ValueError('Invalid address prefix')
            scope = value.get('scope', 'unknown')
            if scope not in ('global', 'host', 'link', 'site', 'nowhere'):
                scope = 'unknown'
            candidate = (not internal and scope == 'global' and not address.is_loopback
                         and not address.is_unspecified and not address.is_multicast
                         and not address.is_link_local)
            entry = {'address': str(address), 'prefixlen': prefix, 'family': 'inet',
                     'scope': scope, 'candidate': candidate}
            if entry not in addresses:
                addresses.append(entry)
        addresses.sort(key=lambda item: (int(ipaddress.IPv4Address(item['address'])), item['prefixlen']))
        result = {'name': name, 'index': index, 'type': kind, 'operstate': operstate,
                  'admin_up': admin_up, 'carrier': carrier, 'link_state': link_state,
                  'internal': internal, 'addresses': addresses}
        master = details.get('master')
        if master is not None:
            if type(master) is int:
                master = links.get(master, {}).get('ifname')
            if isinstance(master, str):
                result['master'] = _name(master)
        info = details.get('linkinfo') or {}
        vlan = (info.get('info_data') or {}).get('id') if kind == 'vlan' else None
        if type(vlan) is int and 0 <= vlan <= 4094:
            result['vlan_id'] = vlan
        rows.append(result)
    return sorted(rows, key=lambda row: (row['index'], row['name']))


def associate_business(interfaces, address):
    """Derive the current interface mapping; do not store or choose an address."""
    selected = {'address': address, 'status': 'missing', 'interface_names': [],
                'message': '当前业务 IP 未配置在本机网口上'}
    try:
        normalized = str(ipaddress.IPv4Address(address))
    except (ValueError, TypeError, ipaddress.AddressValueError):
        selected.update(status='unavailable', message='业务地址为主机名或非 IPv4 地址，暂不判断网口归属')
        return selected
    matches = [row for row in interfaces
               if any(item['address'] == normalized for item in row['addresses'])]
    selected['interface_names'] = [row['name'] for row in matches]
    if len(matches) > 1:
        selected.update(status='ambiguous', message='同一业务 IP 出现在多个网口，请核实承载关系')
    elif matches:
        if matches[0]['link_state'] == 'DOWN':
            selected.update(status='down', message='业务 IP 所属网口链路未连接或已停用')
        elif matches[0]['link_state'] == 'UNKNOWN':
            selected.update(status='unavailable', message='已找到业务 IP 所属网口，链路状态暂无法确认')
        else:
            selected.update(status='ready', message='业务 IP 已配置，所属网口链路正常')
    return selected


def unavailable(address, collected_at=None, error_code='network_query_failed'):
    messages = {'ip_unavailable': '系统网络查询工具不可用',
                'query_timeout': '系统网络信息查询超时',
                'invalid_network_data': '系统网络信息暂无法解析',
                'helper_unavailable': '网口信息模块暂不可用',
                'network_query_failed': '系统网络信息暂不可用'}
    message = messages.get(error_code, messages['network_query_failed'])
    return {'available': False, 'collected_at': time.time() if collected_at is None else collected_at,
            'interfaces': [], 'business': {'address': address, 'status': 'unavailable',
            'interface_names': [], 'message': message}, 'error': message, 'error_code': error_code}


def snapshot(address, runner=None, clock=None):
    """Read two iproute2 JSON queries; all failures become bounded metadata."""
    collected_at = (clock or time.time)()
    execute = runner or _run
    try:
        address_rows = _records(execute(['ip', '-j', 'address', 'show']))
        link_rows = _records(execute(['ip', '-j', '-d', 'link', 'show']))
        interfaces = _interfaces(address_rows, link_rows)
        return {'available': True, 'collected_at': collected_at, 'interfaces': interfaces,
                'business': associate_business(interfaces, address), 'error': None, 'error_code': None}
    except FileNotFoundError:
        return unavailable(address, collected_at, 'ip_unavailable')
    except subprocess.TimeoutExpired:
        return unavailable(address, collected_at, 'query_timeout')
    except (ValueError, TypeError, UnicodeError, KeyError):
        return unavailable(address, collected_at, 'invalid_network_data')
    except Exception:
        return unavailable(address, collected_at, 'network_query_failed')
