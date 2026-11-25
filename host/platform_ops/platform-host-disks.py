#!/usr/bin/env python3
"""Read host filesystem capacity and publish a bounded, non-secret snapshot.

No mounts, partitions, retention policies, or application data are modified.
The host copy is private; the application receives only this JSON document.
Compatible with Python 3.7+ and standard-library only.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
import uuid

SCHEMA_VERSION = 1
OUTPUT_DIRECTORY = Path('/data/AIGO/platform_storage')
OUTPUT_FILENAME = 'host-disks.json'
PSEUDO_FILESYSTEMS = frozenset((
    'autofs', 'binfmt_misc', 'bpf', 'cgroup', 'cgroup2', 'configfs', 'debugfs',
    'devpts', 'devtmpfs', 'efivarfs', 'fusectl', 'hugetlbfs', 'mqueue', 'nsfs',
    'overlay', 'proc', 'pstore', 'ramfs', 'rpc_pipefs', 'securityfs', 'squashfs',
    'sysfs', 'tmpfs', 'tracefs'))
NON_BLOCK_STORAGE_FILESYSTEMS = frozenset((
    'zfs', 'nfs', 'nfs4', 'cifs', 'smb3', 'ceph', 'glusterfs',
    'fuse.glusterfs', 'fuse.sshfs', 'fuse.rclone'))


def unescape_mount(value):
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), value)


def parse_mountinfo(text):
    """Select one canonical mount for each persistent block filesystem."""
    groups = {}
    for line in text.splitlines():
        left, separator, right = line.partition(' - ')
        before, after = left.split(), right.split()
        if not separator or len(before) < 6 or len(after) < 3:
            continue
        major_minor, root, mountpoint = before[2], unescape_mount(before[3]), unescape_mount(before[4])
        fs_type, device = after[0], unescape_mount(after[1])
        if (fs_type in PSEUDO_FILESYSTEMS or not re.fullmatch(r'\d+:\d+', major_minor)
                or not device.startswith('/dev/') or not mountpoint.startswith('/')):
            continue
        # A root overlay and Docker bind mounts cannot contribute capacity twice.
        # Same block device with the same filesystem is one capacity pool.
        fs_id = major_minor + ':' + fs_type
        item = {'fs_id': fs_id, 'device': device, 'mountpoint': mountpoint,
                'fs_type': fs_type, 'read_only': 'ro' in before[5].split(','),
                '_root': root}
        groups.setdefault(fs_id, []).append(item)
    mounts = []
    for candidates in groups.values():
        candidates.sort(key=lambda row: (row['_root'] != '/', row['mountpoint'].count('/'), len(row['mountpoint']), row['mountpoint']))
        selected = dict(candidates[0])
        selected.pop('_root')
        selected['aliases'] = sorted(set(row['mountpoint'] for row in candidates[1:]) - {selected['mountpoint']})
        selected['kind'] = ('root' if selected['mountpoint'] == '/' else
                            'system' if selected['mountpoint'] == '/boot' or selected['mountpoint'].startswith('/boot/') else 'data')
        mounts.append(selected)
    return sorted(mounts, key=lambda row: (row['mountpoint'] != '/', row['mountpoint']))


def usage_percent(used, available):
    return round(100.0 * used / (used + available), 1) if used + available else 0.0


def collect_filesystems(mount_text, statvfs=None):
    native_stats = statvfs is None
    statvfs = os.statvfs if statvfs is None else statvfs
    disks, warnings = [], []
    seen_unsupported = set()
    for line in mount_text.splitlines():
        left, separator, right = line.partition(' - ')
        before, after = left.split(), right.split()
        if separator and len(before) >= 6 and len(after) >= 3 and after[0] in NON_BLOCK_STORAGE_FILESYSTEMS:
            mountpoint = unescape_mount(before[4])
            identity = (mountpoint, after[0])
            if identity not in seen_unsupported and not unescape_mount(after[1]).startswith('/dev/'):
                warnings.append({'code': 'unsupported_filesystem', 'mountpoint': mountpoint, 'fs_type': after[0]})
                seen_unsupported.add(identity)
    for mount in parse_mountinfo(mount_text):
        try:
            if native_stats:
                device_before = os.stat(mount['mountpoint']).st_dev
                actual_identity = '%d:%d' % (os.major(device_before), os.minor(device_before))
                if actual_identity != mount['fs_id'].rsplit(':', 1)[0]:
                    raise OSError('Mount changed before filesystem sampling')
            info = statvfs(mount['mountpoint'])
            if native_stats and os.stat(mount['mountpoint']).st_dev != device_before:
                raise OSError('Mount changed during filesystem sampling')
            fragment = int(info.f_frsize or info.f_bsize)
            total = int(info.f_blocks) * fragment
            free = int(info.f_bfree) * fragment
            available = max(0, int(info.f_bavail)) * fragment
            if total <= 0 or not (0 <= available <= free <= total):
                raise ValueError('inconsistent filesystem capacity')
            item = dict(mount)
            item.update(total_bytes=total, used_bytes=total - free, free_bytes=free,
                        available_bytes=available, used_percent=usage_percent(total - free, available))
            disks.append(item)
        except (OSError, ValueError, OverflowError):
            warnings.append({'code': 'filesystem_unavailable', 'mountpoint': mount['mountpoint']})
    if not disks or not any(row['mountpoint'] == '/' for row in disks):
        raise RuntimeError('Host root filesystem capacity could not be read')
    summary = {'filesystem_count': len(disks), 'includes_system': True}
    for key in ('total_bytes', 'used_bytes', 'free_bytes', 'available_bytes'):
        summary[key] = sum(row[key] for row in disks)
    summary['used_percent'] = usage_percent(summary['used_bytes'], summary['available_bytes'])
    return disks, summary, warnings


def parse_physical_disks(value):
    result = []

    def walk(rows):
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get('type') == 'disk':
                name = str(row.get('name') or '')
                device = str(row.get('path') or '/dev/' + name)
                size = int(row.get('size') or 0)
                if size > 0 and re.fullmatch(r'[A-Za-z0-9._-]{1,128}', name) and device.startswith('/dev/'):
                    result.append({'name': name, 'device': device, 'type': 'disk',
                                   'size_bytes': size, 'read_only': row.get('ro') in (True, 1, '1')})
            children = row.get('children')
            if isinstance(children, list):
                walk(children)
    rows = value.get('blockdevices') if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ValueError('Invalid lsblk output')
    walk(rows)
    return sorted({row['device']: row for row in result}.values(), key=lambda row: row['device'])


def parse_unmounted_devices(value):
    result = []
    excluded = {'', 'swap', 'LVM2_member', 'crypto_LUKS', 'linux_raid_member', 'squashfs'}

    def walk(rows):
        for row in rows:
            if not isinstance(row, dict):
                continue
            filesystem = str(row.get('fstype') or '')
            mounts = row.get('mountpoints') if 'mountpoints' in row else row.get('mountpoint')
            mounted = any(mounts) if isinstance(mounts, list) else bool(mounts)
            if row.get('type') in ('part', 'lvm') and filesystem not in excluded and not mounted:
                name = str(row.get('name') or '')
                device = str(row.get('path') or '/dev/' + name)
                size = int(row.get('size') or 0)
                if size > 0 and re.fullmatch(r'[A-Za-z0-9._-]{1,128}', name) and device.startswith('/dev/'):
                    result.append({'name': name, 'device': device, 'type': row['type'],
                                   'fs_type': filesystem, 'size_bytes': size,
                                   'read_only': row.get('ro') in (True, 1, '1'), 'usage_available': False})
            children = row.get('children')
            if isinstance(children, list):
                walk(children)
    rows = value.get('blockdevices') if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ValueError('Invalid lsblk output')
    walk(rows)
    return sorted({row['device']: row for row in result}.values(), key=lambda row: row['device'])


def collect_block_inventory():
    completed = subprocess.run(['lsblk', '--bytes', '--json', '--output', 'NAME,PATH,TYPE,SIZE,RO,FSTYPE,MOUNTPOINT'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
    if len(completed.stdout) > 1024 * 1024:
        raise ValueError('lsblk output exceeds limit')
    data = json.loads(completed.stdout.decode('utf-8'))
    return {'physical_disks': parse_physical_disks(data), 'unmounted_devices': parse_unmounted_devices(data)}


def parse_swap(text):
    devices = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) != 5:
            continue
        device = unescape_mount(fields[0])
        size, used, priority = int(fields[2]) * 1024, int(fields[3]) * 1024, int(fields[4])
        if device.startswith('/') and 0 <= used <= size:
            devices.append({'device': device, 'size_bytes': size, 'used_bytes': used, 'priority': priority})
    total = sum(row['size_bytes'] for row in devices)
    used = sum(row['used_bytes'] for row in devices)
    return {'total_bytes': total, 'used_bytes': used, 'free_bytes': total - used, 'devices': devices}


def build_snapshot(mount_text=None, statvfs=None, epoch=None, physical_loader=collect_block_inventory, swap_text=None):
    if mount_text is None:
        mount_text = Path('/proc/1/mountinfo').read_text(encoding='utf-8')
    disks, summary, warnings = collect_filesystems(mount_text, statvfs)
    epoch = int(time.time()) if epoch is None else int(epoch)
    observed = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    snapshot = {'schema_version': SCHEMA_VERSION, 'source': 'host', 'observed_at': observed,
                'observed_at_epoch': epoch, 'disks': disks, 'summary': summary, 'warnings': warnings}
    try:
        inventory = physical_loader()
        snapshot['physical_disks'] = inventory['physical_disks']
        snapshot['unmounted_devices'] = inventory['unmounted_devices']
    except (OSError, ValueError, subprocess.SubprocessError):
        warnings.append({'code': 'physical_disk_inventory_unavailable'})
    try:
        snapshot['swap'] = parse_swap(Path('/proc/swaps').read_text(encoding='utf-8') if swap_text is None else swap_text)
    except (OSError, ValueError):
        warnings.append({'code': 'swap_inventory_unavailable'})
    return snapshot


def ensure_private_directory(directory):
    directory = Path(directory)
    if not directory.is_absolute():
        raise ValueError('Snapshot directory must be absolute')
    # Reject every existing symlink component before creating or writing data.
    for component in reversed((directory,) + tuple(directory.parents)):
        if component.is_symlink():
            raise RuntimeError('Snapshot path contains a symlink')
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise RuntimeError('Snapshot directory owner or type is unsafe')
    os.chmod(str(directory), 0o700)


def atomic_write_snapshot(snapshot, directory=OUTPUT_DIRECTORY):
    directory = Path(directory)
    ensure_private_directory(directory)
    target = directory / OUTPUT_FILENAME
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise RuntimeError('Snapshot target is unsafe')
    descriptor, temporary = tempfile.mkstemp(prefix='.host-disks-', suffix='.json', dir=str(directory))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(snapshot, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        os.replace(temporary, str(target))
        directory_fd = os.open(str(directory), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true')
    parser.parse_args()
    snapshot = build_snapshot()
    path = atomic_write_snapshot(snapshot)
    print(json.dumps({'ok': True, 'path': str(path),
                      'filesystem_count': snapshot['summary']['filesystem_count'],
                      'total_bytes': snapshot['summary']['total_bytes']}))


if __name__ == '__main__':
    main()
