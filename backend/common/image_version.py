"""Read the native platform release for the existing About endpoint."""
import json
import os
from pathlib import Path

INSTALL_ROOT = Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parents[2])))
STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', str(INSTALL_ROOT / 'platform_ops/state')))


def read_native_version():
    for path in (STATE / 'release.json', INSTALL_ROOT / 'native-deployment.json'):
        try:
            source = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            continue
        record = json.loads(source)
        version = record.get('release') if isinstance(record, dict) else None
        if not isinstance(version, str) or not version.strip():
            raise ValueError('Native release label unavailable')
        return effective_weekly_release(STATE, record) or version.strip()
    raise ValueError('Native release record unavailable')


def backend_version_response():
    try:
        return {'code': 200, 'msg': '查询成功', 'data': read_native_version()}
    except (OSError, ValueError):
        return {'code': 503, 'msg': '暂时无法读取平台版本，请稍后重试'}


# platform-about-weekly-release-v1
def effective_weekly_release(state, base_record):
    """Return the completed weekly version tied to these running image references."""
    import hashlib
    import re

    def document(path, limit):
        if path.is_symlink():
            return {}
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            return {}
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}

    if (not isinstance(base_record, dict) or base_record.get('runtime') != 'container'
            or not isinstance(base_record.get('release'), str)
            or not isinstance(base_record.get('images'), dict) or not base_record['images']):
        return None
    base = {key: base_record[key] for key in ('release', 'runtime', 'images')}
    try:
        image_key = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        upgrades = Path(state) / 'upgrades'
        marker = upgrades / 'weekly-full/head.json'
        head = document(marker, 4096)
        identifier = head.get('job_id')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier)
                or head.get('image_key') != image_key):
            return None
        job = document(upgrades / 'jobs' / (identifier + '.json'), 2 * 1024 * 1024)
        release, backup = job.get('release'), job.get('backup_id')
        if (job.get('id') == identifier and job.get('image_key') == image_key
                and job.get('package_schema') == 'platform-weekly-full' and job.get('operation') == 'upgrade'
                and job.get('status') == 'completed' and isinstance(backup, str)
                and re.fullmatch(r'weekly-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}', backup)
                and isinstance(release, str) and len(release) <= 80
                and re.fullmatch(r'V[0-9]+\.[0-9]+\.[0-9]+-weekly-[0-9]{8}-full(?:-r[1-9][0-9]*)?', release)
                and document(marker, 4096) == head):
            return release
    except (OSError, TypeError, ValueError, RecursionError):
        pass
    return None
