"""Read a bounded, fresh host mount snapshot without entering the host namespace.

The collector owns this fixed file. Request parameters cannot choose a path,
and container disk_usage is retained only for old API clients as an explicitly
marked fallback. New clients must use disks and disk_summary.
"""
import json
import math
import os
import posixpath
import re
import shutil
import stat
import time
from datetime import datetime, timezone


HOST_DISKS_PATH = '/data/AIGO/platform_storage/host-disks.json'
MAX_SNAPSHOT_BYTES = 256 * 1024
MAX_AGE_SECONDS = 180
MAX_FUTURE_SECONDS = 30
REFRESH_INTERVAL_SECONDS = 60
MAX_BYTES = 2 ** 63 - 1
_PSEUDO_FILESYSTEMS = frozenset((
    'overlay', 'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'cgroup', 'cgroup2',
    'devpts', 'mqueue', 'hugetlbfs', 'securityfs', 'debugfs', 'tracefs',
    'configfs', 'pstore', 'bpf', 'autofs', 'squashfs', 'nsfs', 'ramfs',
    'fusectl', 'efivarfs', 'binfmt_misc', 'rpc_pipefs',
))
_DISK_KEYS = frozenset((
    'fs_id', 'device', 'mountpoint', 'fs_type', 'total_bytes', 'used_bytes',
    'free_bytes', 'available_bytes', 'used_percent', 'read_only', 'kind', 'aliases',
))


class InvalidSnapshot(ValueError):
    pass


def _integer(value, minimum=0, maximum=MAX_BYTES):
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidSnapshot('invalid integer')
    return value


def _string(value, maximum=4096):
    if (type(value) is not str or not value or len(value) > maximum
            or any(ord(character) < 32 for character in value)):
        raise InvalidSnapshot('invalid text')
    return value


def _path(value, device=False):
    value = _string(value)
    if (not value.startswith('/') or value.startswith('//')
            or posixpath.normpath(value) != value
            or (device and not value.startswith('/dev/'))):
        raise InvalidSnapshot('invalid path')
    return value


def _boolean(value):
    if type(value) is not bool:
        raise InvalidSnapshot('invalid boolean')
    return value


def _percent(value):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not 0 <= value <= 100):
        raise InvalidSnapshot('invalid percentage')
    return value


def _usage_percent(used, available):
    return round(100.0 * used / (used + available), 1) if used + available else 0.0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSnapshot('duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise InvalidSnapshot('non-finite JSON number')


def _read_snapshot():
    descriptor = os.open(HOST_DISKS_PATH, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                         | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as handle:
        metadata = os.fstat(handle.fileno())
        if (not stat.S_ISREG(metadata.st_mode)
                or not 0 < metadata.st_size <= MAX_SNAPSHOT_BYTES
                or (os.name == 'posix' and metadata.st_mode & 0o022)):
            raise InvalidSnapshot('unsafe snapshot file')
        raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise InvalidSnapshot('snapshot too large')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=_invalid_constant)


def _timestamp(snapshot, now):
    observed = _string(snapshot.get('observed_at'), 40)
    try:
        parsed = datetime.strptime(observed, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        parsed = datetime.strptime(observed, '%Y-%m-%dT%H:%M:%S.%fZ')
    epoch = _integer(snapshot.get('observed_at_epoch'), 1)
    if abs(parsed.replace(tzinfo=timezone.utc).timestamp() - epoch) >= 1:
        raise InvalidSnapshot('inconsistent snapshot time')
    age = now - epoch
    if age < -MAX_FUTURE_SECONDS:
        raise InvalidSnapshot('snapshot from the future')
    return observed, max(0, int(age))


def _disk(item):
    if type(item) is not dict or set(item) != _DISK_KEYS:
        raise InvalidSnapshot('invalid filesystem schema')
    fs_type = _string(item['fs_type'], 64)
    fs_id = _string(item['fs_id'], 128)
    if (fs_type in _PSEUDO_FILESYSTEMS
            or not re.match(r'^\d+:\d+:[A-Za-z0-9_.+-]+$', fs_id)
            or fs_id.rsplit(':', 1)[-1] != fs_type):
        raise InvalidSnapshot('invalid filesystem identity')
    mountpoint = _path(item['mountpoint'])
    kind = item['kind']
    expected_kind = ('root' if mountpoint == '/' else
                     'system' if mountpoint == '/boot' or mountpoint.startswith('/boot/') else 'data')
    if kind != expected_kind:
        raise InvalidSnapshot('inconsistent filesystem kind')
    total = _integer(item['total_bytes'], 1)
    used = _integer(item['used_bytes'])
    free = _integer(item['free_bytes'])
    available = _integer(item['available_bytes'])
    if used + free != total or available > free:
        raise InvalidSnapshot('inconsistent filesystem sizes')
    percent = _usage_percent(used, available)
    if abs(_percent(item['used_percent']) - percent) > 0.1000001:
        raise InvalidSnapshot('inconsistent filesystem percentage')
    aliases = item['aliases']
    if type(aliases) is not list or len(aliases) > 64:
        raise InvalidSnapshot('invalid mount aliases')
    aliases = [_path(alias) for alias in aliases]
    if mountpoint in aliases or len(set(aliases)) != len(aliases):
        raise InvalidSnapshot('duplicate mount alias')
    return {
        'device_id': fs_id, 'source': _path(item['device'], device=True),
        'mountpoint': mountpoint, 'filesystem': fs_type,
        'label': {'root': '服务器根盘', 'data': '数据分区', 'system': '系统分区'}[kind],
        'kind': kind, 'aliases': aliases, 'read_only': _boolean(item['read_only']),
        'total_bytes': total, 'used_bytes': used, 'free_bytes': available,
        'available_bytes': available, 'unallocated_free_bytes': free,
        'used_percent': percent,
    }


def _physical_disks(items):
    if type(items) is not list or len(items) > 128:
        raise InvalidSnapshot('invalid physical disk list')
    result, names, devices = [], set(), set()
    for item in items:
        if (type(item) is not dict or set(item) !=
                {'name', 'device', 'type', 'size_bytes', 'read_only'}):
            raise InvalidSnapshot('invalid physical disk schema')
        name = _string(item['name'], 128)
        device = _path(item['device'], device=True)
        if (not re.match(r'^[A-Za-z0-9_.!-]+$', name) or item['type'] != 'disk'
                or name in names or device in devices):
            raise InvalidSnapshot('invalid physical disk identity')
        names.add(name)
        devices.add(device)
        result.append({'name': name, 'device': device, 'type': 'disk',
                       'size_bytes': _integer(item['size_bytes'], 1),
                       'read_only': _boolean(item['read_only'])})
    return result


def _unmounted_devices(items):
    if type(items) is not list or len(items) > 256:
        raise InvalidSnapshot('invalid unmounted device list')
    result, names, devices = [], set(), set()
    for item in items:
        if (type(item) is not dict or set(item) !=
                {'name', 'device', 'type', 'fs_type', 'size_bytes', 'read_only', 'usage_available'}):
            raise InvalidSnapshot('invalid unmounted device schema')
        name = _string(item['name'], 128)
        device = _path(item['device'], device=True)
        fs_type = _string(item['fs_type'], 64)
        if (not re.match(r'^[A-Za-z0-9_.!-]+$', name)
                or item['type'] not in ('part', 'lvm')
                or fs_type in _PSEUDO_FILESYSTEMS
                or fs_type in ('swap', 'LVM2_member', 'crypto_LUKS', 'linux_raid_member')
                or item['usage_available'] is not False
                or name in names or device in devices):
            raise InvalidSnapshot('invalid unmounted device identity')
        names.add(name)
        devices.add(device)
        result.append({'name': name, 'device': device, 'type': item['type'],
                       'filesystem': fs_type, 'size_bytes': _integer(item['size_bytes'], 1),
                       'read_only': _boolean(item['read_only']), 'usage_available': False})
    return result


def _swap(value):
    if (type(value) is not dict or set(value) !=
            {'total_bytes', 'used_bytes', 'free_bytes', 'devices'}):
        raise InvalidSnapshot('invalid swap schema')
    total = _integer(value['total_bytes'])
    used = _integer(value['used_bytes'])
    free = _integer(value['free_bytes'])
    if used + free != total or type(value['devices']) is not list or len(value['devices']) > 128:
        raise InvalidSnapshot('inconsistent swap sizes')
    devices, seen = [], set()
    for item in value['devices']:
        if type(item) is not dict or set(item) != {'device', 'size_bytes', 'used_bytes', 'priority'}:
            raise InvalidSnapshot('invalid swap device schema')
        device = _path(item['device'])
        size = _integer(item['size_bytes'])
        consumed = _integer(item['used_bytes'])
        if device in seen or consumed > size:
            raise InvalidSnapshot('inconsistent swap device')
        seen.add(device)
        devices.append({'device': device, 'size_bytes': size, 'used_bytes': consumed,
                        'priority': _integer(item['priority'], -MAX_BYTES)})
    if sum(item['size_bytes'] for item in devices) != total or sum(item['used_bytes'] for item in devices) != used:
        raise InvalidSnapshot('inconsistent swap totals')
    return {'total_bytes': total, 'used_bytes': used, 'free_bytes': free, 'devices': devices}


def _unavailable(status, observed=None, age=None):
    return {'available': False, 'complete': False, 'status': status,
            'message': {'unavailable': '宿主机磁盘采集暂不可用，请检查采集服务。',
                        'stale': '宿主机磁盘采样已过期，当前容量未知，请检查采集服务。',
                        'invalid': '宿主机磁盘采样校验失败，当前容量未知，请检查采集服务。'}[status],
            'scope': 'host_mounted_filesystems', 'volume_count': 0,
            'total_bytes': None, 'used_bytes': None, 'free_bytes': None,
            'available_bytes': None, 'unallocated_free_bytes': None,
            'used_percent': None, 'collected_at': observed, 'age_seconds': age,
            'refresh_interval_seconds': REFRESH_INTERVAL_SECONDS,
            'physical_disks': [], 'swap': None, 'unmounted_devices': [], 'warnings': []}


def _collector_warnings(items):
    if type(items) is not list or len(items) > 32:
        raise InvalidSnapshot('invalid collector warnings')
    warnings, incomplete_filesystems = [], False
    for item in items:
        if type(item) is not dict:
            raise InvalidSnapshot('invalid collector warning schema')
        code = item.get('code')
        if code == 'filesystem_unavailable' and set(item) == {'code', 'mountpoint'}:
            mountpoint = _path(item['mountpoint'])
            warnings.append('无法读取文件系统：' + mountpoint)
            incomplete_filesystems = True
        elif code == 'unsupported_filesystem' and set(item) == {'code', 'mountpoint', 'fs_type'}:
            mountpoint = _path(item['mountpoint'])
            fs_type = _string(item['fs_type'], 64)
            warnings.append('文件系统暂不计入容量汇总：' + mountpoint + '（' + fs_type + '）')
            incomplete_filesystems = True
        elif code == 'physical_disk_inventory_unavailable' and set(item) == {'code'}:
            warnings.append('暂时无法读取物理设备清单。')
        elif code == 'swap_inventory_unavailable' and set(item) == {'code'}:
            warnings.append('暂时无法读取交换空间信息。')
        else:
            raise InvalidSnapshot('unknown collector warning')
    return warnings, incomplete_filesystems


def _host_disks():
    observed, age = None, None
    try:
        snapshot = _read_snapshot()
        if (type(snapshot) is not dict or type(snapshot.get('schema_version')) is not int
                or snapshot['schema_version'] != 1 or snapshot.get('source') != 'host'
                or not {'schema_version', 'source', 'observed_at', 'observed_at_epoch',
                        'disks', 'summary', 'warnings'} <= set(snapshot)
                or set(snapshot) - {'schema_version', 'source', 'observed_at', 'observed_at_epoch',
                                    'disks', 'summary', 'warnings', 'physical_disks', 'swap',
                                    'unmounted_devices'}):
            raise InvalidSnapshot('invalid snapshot schema')
        observed, age = _timestamp(snapshot, time.time())
        if age > MAX_AGE_SECONDS:
            return [], _unavailable('stale', observed, age)
        items = snapshot['disks']
        if type(items) is not list or not 0 < len(items) <= 128:
            raise InvalidSnapshot('invalid filesystem list')
        disks, identifiers, mounts = [], set(), set()
        for item in items:
            disk = _disk(item)
            mount_paths = [disk['mountpoint']] + disk['aliases']
            if disk['device_id'] in identifiers or any(path in mounts for path in mount_paths):
                raise InvalidSnapshot('duplicate filesystem')
            identifiers.add(disk['device_id'])
            mounts.update(mount_paths)
            disks.append(disk)
        if not any(disk['mountpoint'] == '/' for disk in disks):
            raise InvalidSnapshot('missing host root filesystem')
        disks.sort(key=lambda disk: (disk['mountpoint'] != '/', disk['kind'] == 'system', disk['mountpoint']))
        warnings, incomplete = _collector_warnings(snapshot['warnings'])
        total = sum(disk['total_bytes'] for disk in disks)
        used = sum(disk['used_bytes'] for disk in disks)
        free = sum(disk['unallocated_free_bytes'] for disk in disks)
        available = sum(disk['available_bytes'] for disk in disks)
        if total > MAX_BYTES:
            raise InvalidSnapshot('aggregate capacity too large')
        unmounted = _unmounted_devices(snapshot.get('unmounted_devices', []))
        mounted_devices = {disk['source'] for disk in disks}
        if any(item['device'] in mounted_devices for item in unmounted):
            raise InvalidSnapshot('mounted device listed as unmounted')
        # Never trust an independently supplied aggregate or add physical disks
        # to LVM filesystem capacity. The API recomputes from unique identities.
        summary = {
            'available': True, 'complete': not incomplete,
            'status': 'partial' if incomplete else 'ok',
            'message': ('部分文件系统无法采集，以下容量仅统计已采集分区。' if incomplete else
                        '磁盘容量已采集，部分设备信息暂不可用。' if warnings else ''),
            'scope': 'host_mounted_filesystems', 'volume_count': len(disks),
            'total_bytes': total, 'used_bytes': used, 'free_bytes': available,
            'available_bytes': available, 'unallocated_free_bytes': free,
            'used_percent': _usage_percent(used, available),
            'collected_at': observed, 'age_seconds': age,
            'refresh_interval_seconds': REFRESH_INTERVAL_SECONDS,
            'physical_disks': _physical_disks(snapshot.get('physical_disks', [])),
            'swap': _swap(snapshot['swap']) if 'swap' in snapshot else None,
            'unmounted_devices': unmounted,
            'warnings': warnings,
        }
        return disks, summary
    except OSError:
        return [], _unavailable('unavailable', observed, age)
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        return [], _unavailable('invalid', observed, age)


def storage_disk_settings(legacy_disk_path='/'):
    """Return fresh host filesystems plus the historical single-disk contract."""
    disks, summary = _host_disks()
    root = next((disk for disk in disks if disk['mountpoint'] == '/'), None)
    if root is not None:
        legacy = {'total_bytes': root['total_bytes'], 'used_bytes': root['used_bytes'],
                  'free_bytes': root['unallocated_free_bytes'],
                  'used_percent': round(100.0 * root['used_bytes'] / root['total_bytes'], 1),
                  'source': 'host', 'mountpoint': '/'}
    else:
        try:
            usage = shutil.disk_usage(legacy_disk_path)
            legacy = {'total_bytes': usage.total, 'used_bytes': usage.used,
                      'free_bytes': usage.free,
                      'used_percent': round(100.0 * usage.used / usage.total, 1),
                      'source': 'container_fallback', 'mountpoint': legacy_disk_path}
        except (OSError, ValueError, ZeroDivisionError):
            legacy = None
    return {'disks': disks, 'disk_summary': summary, 'disk': legacy}
