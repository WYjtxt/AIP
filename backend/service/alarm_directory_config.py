"""Add explicitly registered mounted volumes to existing retention policy."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

CONFIG = '/data/AIGO/platform_storage/config/alarm-directory.json'
VOLUMES = '/data/AIGO/platform_storage/alarm-volumes'


def merge_retention(config):
    try:
        with open(os.environ.get('PLATFORM_ALARM_DIRECTORY_CONFIG', CONFIG), encoding='utf-8') as handle:
            doc = json.load(handle)
    except FileNotFoundError:
        return config
    # A malformed registry disables cleanup through the caller's fail-closed fallback.
    if doc.get('schema') != 1 or doc.get('version') != 'alarm-directory-v1':
        raise ValueError('Invalid alarm storage registry')
    result = dict(config)
    result['local_roots'] = list(config.get('local_roots', []))
    result['media_mappings'] = list(config.get('media_mappings', []))
    # Derive only the already trusted authority; never accept a supplied remote origin.
    origins = set()
    for mapping in result['media_mappings']:
        parsed = urlsplit(mapping['url_prefix'])
        if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username:
            origins.add(parsed.scheme + '://' + parsed.netloc)
    base = Path(os.environ.get('PLATFORM_ALARM_VOLUMES', VOLUMES))
    public = urlsplit(doc['public_origin'])
    if public.scheme != 'https' or not public.netloc or public.username or public.path not in ('', '/'):
        raise ValueError('Invalid platform media origin')
    origins = {public.scheme + '://' + public.netloc}
    for volume in doc['volumes']:
        root = Path(volume['root'])
        if (root.parent != base or root.name != volume['id'] or len(root.name) != 20
                or any(c not in '0123456789abcdef' for c in root.name)
                or root.is_symlink() or root.resolve() != root or not root.is_dir()
                or volume['url_path'] != '/media/alarm-storage/' + root.name + '/'):
            raise ValueError('Untrusted alarm storage volume')
        info = root.stat()
        if [info.st_dev, info.st_ino] != volume.get('target_identity'):
            raise ValueError('Changed alarm storage mount')
        with open('/proc/self/mountinfo') as handle:
            if not any(line.split()[4].replace('\\040', ' ').replace('\\134', '\\') == str(root) for line in handle):
                raise ValueError('Missing alarm storage mount')
        if str(root) not in result['local_roots']:
            result['local_roots'].append(str(root))
        for origin in origins:
            mapping = {'root': str(root), 'url_prefix': origin + volume['url_path']}
            if mapping not in result['media_mappings']:
                result['media_mappings'].append(mapping)
    # New roots are reference-driven only: do not broaden the orphan sweep implicitly.
    return result
