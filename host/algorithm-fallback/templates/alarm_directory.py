"""One hot-read alarm directory setting for image/video writers.

Missing configuration preserves the original paths, including ALARM_VIDEO_DIR.
Malformed active configuration fails closed instead of silently writing elsewhere.
"""
import json
import hashlib
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

DEFAULT_ROOT = '/data/AIGO/outputs'
CONFIG = '/data/AIGO/platform_storage/config/alarm-directory.json'
VERSION = 'alarm-directory-v1'
RECEIPTS = '/data/AIGO/platform_start/platform_ops/state/writer-receipts'
VOLUMES = Path('/data/AIGO/platform_storage/alarm-volumes')
# Only the installer replaces this literal with its validated physical root.
# Never infer trust from the target of an arbitrary /data/AIGO/platform_start symlink at runtime.
HOST_VOLUMES = Path('/data/AIGO/platform_storage/alarm-volumes')
HOST_LEGACY_ROOT = Path('/data/AIGO/outputs')


def physical_legacy_root(value):
    if value != DEFAULT_ROOT:
        raise RuntimeError('Untrusted legacy alarm root')
    original = Path(DEFAULT_ROOT)
    if original.resolve() == original:
        return original
    # deploy_all creates exactly /data/AIGO/platform_start/AIGO -> /home/AIGO. Admit that fixed
    # legacy mapping only; extra links below it or inside /home remain unsafe.
    alias = Path('/data/AIGO/platform_start/AIGO')
    if (HOST_VOLUMES.resolve() != HOST_VOLUMES
            or Path('/data/AIGO/platform_start').resolve() not in (Path('/data/AIGO/platform_start'), HOST_VOLUMES.parent.parent)
            or alias.resolve() != Path('/home/AIGO')
            or HOST_LEGACY_ROOT.resolve() != HOST_LEGACY_ROOT
            or original.resolve() != HOST_LEGACY_ROOT):
        raise RuntimeError('Legacy alarm compatibility root changed')
    child = alias
    for name in ('python', 'bingxing_model', 'results'):
        child = child / name
        if child.is_symlink():
            raise RuntimeError('Legacy alarm root contains an unexpected symlink')
    return HOST_LEGACY_ROOT


def physical_volume(volume):
    """Map only the installer's exact compatibility base, never arbitrary links."""
    volume_id = volume.get('id')
    if not isinstance(volume_id, str) or not re.fullmatch(r'[0-9a-f]{20}', volume_id):
        raise RuntimeError('Invalid alarm volume identifier')
    expected = VOLUMES / volume_id
    if volume.get('root') != str(expected):
        raise RuntimeError('Untrusted alarm volume root')
    if (not HOST_VOLUMES.is_absolute() or HOST_VOLUMES.resolve() != HOST_VOLUMES
            or VOLUMES.resolve() != HOST_VOLUMES):
        raise RuntimeError('Alarm compatibility root changed')
    physical = HOST_VOLUMES / volume_id
    if expected.is_symlink() or physical.is_symlink() or expected.resolve() != physical:
        raise RuntimeError('Alarm volume contains an unexpected symlink')
    return physical


def volume_aliases(volume):
    """Keep old stored canonical paths and new physical writer paths readable."""
    return (volume['root'], str(VOLUMES / volume['id']))


def mounted(path):
    with open('/proc/self/mountinfo') as handle:
        return any(line.split()[4].replace('\\040', ' ').replace('\\011', '\t').replace('\\134', '\\') == str(path) for line in handle)


def _load():
    path = os.environ.get('PLATFORM_ALARM_DIRECTORY_CONFIG', CONFIG)
    try:
        with open(path, encoding='utf-8') as handle:
            doc = json.load(handle)
    except FileNotFoundError:
        return None
    if doc.get('schema') != 1 or doc.get('version') != VERSION:
        raise RuntimeError('Unsupported alarm directory configuration')
    active = doc['active']
    # The registry remains in canonical /data/AIGO/platform_start coordinates for the backend
    # container. Resolve only registered volumes to the installer's host base
    # in this in-memory copy used by the native algorithm worker.
    volumes = doc.get('volumes')
    if not isinstance(volumes, list) or not isinstance(active, dict):
        raise RuntimeError('Invalid alarm storage registry')
    seen = set()
    selected = None
    for volume in volumes:
        if not isinstance(volume, dict):
            raise RuntimeError('Invalid alarm volume')
        physical = physical_volume(volume)
        if volume['id'] in seen:
            raise RuntimeError('Duplicate alarm volume')
        seen.add(volume['id'])
        if volume['id'] == active.get('id'):
            if active != volume:
                raise RuntimeError('Active alarm volume differs from registry')
            selected = volume
        volume['root'] = str(physical)
    if active.get('id') == 'legacy':
        active['root'] = str(physical_legacy_root(active.get('root')))
    elif selected is None:
        raise RuntimeError('Active alarm volume is not registered')
    else:
        doc['active'] = active = selected
    p = Path(active['root'])
    if not p.is_absolute() or p.is_symlink() or not p.is_dir() or p.resolve() != p:
        raise RuntimeError('Alarm storage root unavailable')
    if active['id'] != 'legacy':
        info = p.stat()
        if not mounted(p) or [info.st_dev, info.st_ino] != active.get('target_identity'):
            raise RuntimeError('Alarm storage mount unavailable or changed')
    return doc


def root():
    doc = _load()
    return doc['active']['root'] if doc else DEFAULT_ROOT


def relocate(path):
    """Snapshot the current destination once when starting an alarm write."""
    value = os.fspath(path)
    doc = _load()
    if not doc:
        return value
    roots = [DEFAULT_ROOT, str(HOST_LEGACY_ROOT)] + [value for v in doc['volumes'] for value in volume_aliases(v)]
    for old in sorted(roots, key=len, reverse=True):
        try:
            relative = Path(value).relative_to(old)
            return str(Path(doc['active']['root']) / relative)
        except ValueError:
            continue
    # Non-media runtime state and original fallback directories stay where they were.
    return value


def video_dir():
    doc = _load()
    return str(Path(doc['active']['root']) / 'videos') if doc else (os.environ.get('ALARM_VIDEO_DIR') or DEFAULT_ROOT + '/videos')


def media_url(path, host, port):
    """Resolve a captured path using its own historical volume, never today's root."""
    value = os.fspath(path)
    doc = _load()
    if doc:
        for volume in doc['volumes']:
            for prefix in volume_aliases(volume):
                try:
                    relative = str(Path(value).relative_to(prefix))
                    return doc['public_origin'].rstrip('/') + volume['url_path'] + quote(relative, safe='/')
                except ValueError:
                    continue
    # Nginx retains the old /data/AIGO/platform_start URL route for files on the fixed native path.
    try:
        value = str(Path(DEFAULT_ROOT) / Path(value).relative_to(HOST_LEGACY_ROOT))
    except ValueError:
        pass
    return 'http://%s:%s%s' % (host, port, quote(value, safe='/'))


def _register():
    """PID+starttime proves this particular worker imported the directory API."""
    try:
        pid = os.getpid()
        start = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()[19]
        directory = Path(os.environ.get('PLATFORM_ALARM_WRITER_RECEIPTS', RECEIPTS))
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.%d.' % pid, dir=str(directory))
        with os.fdopen(fd, 'w') as handle:
            json.dump({'pid': pid, 'start': start, 'version': VERSION, 'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, handle)
        os.chmod(tmp, 0o644)
        os.replace(tmp, directory / ('%d.json' % pid))
    except OSError:
        # Existing runtime behavior must stay available before the host service is installed.
        pass


_register()
if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=_register)
