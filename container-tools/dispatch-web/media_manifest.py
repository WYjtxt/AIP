#!/usr/bin/env python3
"""Resolve offline media without confusing ARM and x86 native artifacts."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import struct
import tarfile


def normalize_arch(value):
    aliases = {'aarch64': 'aarch64', 'arm64': 'aarch64',
               'x86_64': 'x86_64', 'amd64': 'x86_64', 'x64': 'x86_64'}
    try:
        return aliases[str(value).strip().lower()]
    except KeyError:
        raise ValueError('仅支持 ARM64/aarch64 和 x86_64/amd64：' + str(value))


def docker_arch(value):
    return 'arm64' if normalize_arch(value) == 'aarch64' else 'amd64'


def _json_member(archive, name):
    member = archive.getmember(name)
    if not member.isfile() or member.size > 4 * 1024 * 1024:
        raise ValueError('镜像元数据无效：' + name)
    return json.load(archive.extractfile(member))


def inspect_image_archive(path, expected_arch=None):
    """Read docker-save metadata without extracting or executing an image."""
    records = []
    try:
        with tarfile.open(str(path), 'r:*') as archive:
            manifest = _json_member(archive, 'manifest.json')
            if not isinstance(manifest, list) or not manifest:
                raise ValueError('镜像 manifest.json 为空')
            for item in manifest:
                config = _json_member(archive, item['Config'])
                actual = docker_arch(config.get('architecture', ''))
                if config.get('os', 'linux') != 'linux':
                    raise ValueError('仅支持 Linux 容器镜像：' + str(path))
                if expected_arch and actual != docker_arch(expected_arch):
                    raise ValueError('镜像架构不匹配：%s (%s，目标 %s)' %
                                     (path, actual, docker_arch(expected_arch)))
                digest = re.sub(r'\.json$', '', Path(item['Config']).name)
                for tag in item.get('RepoTags') or []:
                    records.append({'tag': tag, 'architecture': actual,
                                    'config_digest': digest})
        if not records:
            raise ValueError('镜像包没有可部署的 RepoTags：' + str(path))
        return records
    except (KeyError, TypeError, tarfile.TarError, json.JSONDecodeError) as exc:
        raise ValueError('无效的 docker save 镜像包 %s：%s' % (path, exc)) from exc


def inspect_archive(path):
    records = inspect_image_archive(path)
    arches = {item['architecture'] for item in records}
    if len(arches) != 1:
        raise ValueError('单个镜像包包含多种架构：' + str(path))
    return {'architecture': records[0]['architecture'],
            'tags': [item['tag'] for item in records]}


def _role(tag):
    name = tag.rsplit('/', 1)[-1].split(':', 1)[0].lower()
    if name.startswith('seal_system_vue'):
        return 'frontend'
    if name.startswith('seal_system'):
        return 'backend'
    if name.startswith('zlmediakit'):
        return 'zlk'
    return None


def _version_key(record):
    return tuple(int(value) for value in re.findall(r'\d+', record['tag'].split(':')[-1]))


def resolve_media(base_dir, arch, mode, media_dir=''):
    """Return absolute selected media paths; legacy unscoped media is ARM only."""
    base = Path(base_dir).resolve()
    arch = normalize_arch(arch)
    candidates = [base / 'packages' / arch]
    if arch == 'aarch64':
        candidates += [base / 'packages' / 'arm64', base / 'packages' / 'arm']
    else:
        candidates += [base / 'packages' / 'amd64', base / 'packages' / 'x86']
    package_root = next((p for p in candidates if p.is_dir()), candidates[0])
    if arch == 'aarch64' and not package_root.is_dir():
        package_root = base / 'packages'

    def arch_images(folder):
        aliases = (arch, 'arm64', 'arm') if arch == 'aarch64' else (arch, 'amd64', 'x86')
        for alias in aliases:
            for candidate in (folder / alias / 'images', folder / alias):
                if candidate.is_dir():
                    return candidate
        return folder

    explicit = Path(media_dir).expanduser().resolve() if media_dir else None
    if explicit:
        if (explicit / 'images').is_dir():
            # Choosing the common images directory must not make an x86 target
            # reuse legacy ARM installers from packages/apps.
            if explicit != base / 'packages':
                package_root = explicit
            images_dir = arch_images(explicit / 'images')
        elif (explicit / arch / 'images').is_dir():
            package_root = explicit / arch
            images_dir = package_root / 'images'
        else:
            images_dir = arch_images(explicit)
    else:
        central = base / 'packages' / 'images'
        central_arch = arch_images(central)
        images_dir = central_arch if central_arch != central else package_root / 'images'
        if not images_dir.is_dir() and arch == 'x86_64':
            sibling = base.parent.parent / 'Images' / 'deploy' / 'x86'
            if sibling.is_dir():
                images_dir = sibling
    result = {'arch': arch, 'images_dir': str(images_dir),
              'apps_dir': str(package_root / 'apps'),
              'python_dir': str(package_root / 'python'),
              'ascend_dir': str(package_root / 'AscendConfig'), 'images': {}}
    runtime_paths = [package_root / 'runtime_bundle.tar.gz',
                     package_root / 'python' / 'runtime_bundle.tar.gz']
    if arch == 'aarch64':
        runtime_paths.append(base / 'payload' / '113100_bundle.tar.gz')
    result['runtime_bundle'] = str(next((p for p in runtime_paths if p.is_file()), runtime_paths[0]))
    if mode in ('verify', 'clean'):
        return result
    lock = base / 'release-lock.json'
    if lock.exists():
        profile = 'openeuler22.03-sp4-aarch64-ascend310p3' if arch == 'aarch64' else 'ubuntu20.04-x86_64-sc7'
        pinned = json.loads(lock.read_text(encoding='utf-8'))['profiles'][profile]['images']
        if explicit and explicit not in (base/'packages', base/'packages/images', images_dir, package_root):
            raise ValueError('此发布包仅使用 release-lock.json 固定的镜像目录')
        for role, entry in pinned.items():
            if mode == 'platform' and role == 'zlk':
                continue
            path = (base / entry['archive']).resolve()
            if base not in path.parents:
                raise ValueError('发布镜像路径越界')
            matches = [record for record in inspect_image_archive(path, arch) if record['tag'] == entry['tag']]
            if len(matches) != 1 or 'sha256:' + matches[0]['config_digest'] != entry.get('config_id', entry['image_id']):
                raise ValueError('发布镜像 ID 与固定清单不一致：' + role)
            result['images'][role] = dict(matches[0], archive=str(path))
        return result
    if not images_dir.is_dir():
        raise ValueError('缺少 %s 镜像目录：%s' % (arch, images_dir))
    for path in sorted(images_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(('.tar', '.tar.gz', '.tgz')):
            continue
        # A selected directory may contain dependency images as well.
        for record in inspect_image_archive(path):
            role = _role(record['tag'])
            if not role:
                continue
            if record['architecture'] != docker_arch(arch):
                if explicit:
                    raise ValueError('所选镜像目录包含错误架构：' + str(path))
                continue
            record = dict(record, archive=str(path.resolve()))
            old = result['images'].get(role)
            if old is None or _version_key(record) > _version_key(old):
                result['images'][role] = record
    required = ('backend', 'frontend') if mode == 'platform' else ('backend', 'frontend', 'zlk')
    missing = [role for role in required if role not in result['images']]
    if missing:
        raise ValueError('缺少 %s 镜像（%s）：%s' % (arch, images_dir, ', '.join(missing)))
    return result


def validate_native_archive(path, arch, binary_names):
    """Check a native ELF inside an installer archive before installation."""
    expected = 183 if normalize_arch(arch) == 'aarch64' else 62
    with tarfile.open(str(path), 'r:*') as archive:
        for member in archive:
            matches = any(member.name.endswith(name) for name in binary_names)
            if 'bin/python' in binary_names and re.search(r'(^|/)bin/python(?:\d+(?:\.\d+)?)?$', member.name):
                matches = True
            if member.isfile() and matches:
                with archive.extractfile(member) as stream:
                    header = stream.read(64)
                if header[:4] != b'\x7fELF' or len(header) < 20:
                    continue
                endian = '<' if header[5] == 1 else '>'
                machine = struct.unpack(endian + 'H', header[18:20])[0]
                if machine != expected:
                    raise ValueError('离线二进制架构不匹配：%s (%s)' % (path, member.name))
                return
    raise ValueError('离线包缺少可验证的本机二进制：' + str(path))


def validate_full_media(media, require_ascend=True):
    """Return a complete missing-media list before uploading full deployments."""
    arch = media['arch']
    apps, py, ascend = (Path(media[key]) for key in ('apps_dir', 'python_dir', 'ascend_dir'))
    patterns = [(apps, 'docker-26.1.4.tgz'), (apps, 'opt-nginx.tar.gz'),
                (apps, 'mysql-8.0.46-linux-glibc2.28-%s.tar.xz' % arch),
                (apps, 'redis-6.2.14.tar.gz'), (apps, 'kafka_2.12-3.6.2.tgz'),
                (apps, 'microsoft-jdk-11-linux-%s.tar.gz' % ('x64' if arch == 'x86_64' else arch)),
                (py, 'Miniconda3-py39_23.10.0-1-Linux-%s.sh' % arch)]
    if require_ascend:
        patterns.append((py, 'yolo-env.tar.gz'))
    if require_ascend:
        patterns += [(py, 'cann90-runtime-cann9.0.0.tgz'),
                     (ascend, 'Ascend-hdk-*-npu-driver_*linux-%s.run' % arch),
                     (ascend, 'Ascend-cann-toolkit_*linux-%s.run' % arch),
                     (ascend, 'Ascend-cann-*-ops_*linux-%s.run' % arch)]
    missing = []
    if not Path(media['runtime_bundle']).is_file():
        missing.append(media['runtime_bundle'])
    for directory, pattern in patterns:
        alternatives = [pattern]
        if pattern.startswith('microsoft-jdk-11-linux-'):
            alternatives.append('microsoft-jdk-11-linux-%s.tar.gz' % arch)
        if not any(path.is_file() for name in alternatives for path in directory.glob(name)):
            missing.append(str(directory / pattern))
    if missing:
        raise ValueError('缺少 %s 全量部署离线介质；尚未上传或修改目标机：\n%s\n可选择 platform 仅部署两平台，复用现有依赖。' %
                         (arch, '\n'.join('  - ' + name for name in missing)))
    return media


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-dir', default='/root/oneclick')
    parser.add_argument('--arch', required=True)
    parser.add_argument('--mode', default='repair')
    parser.add_argument('--shell-env', action='store_true')
    args = parser.parse_args()
    arch = normalize_arch(args.arch)
    required = ('backend', 'frontend') if args.mode == 'platform' else ('backend', 'frontend', 'zlk')
    # Uploaded directories can retain unrelated archives from an earlier run.
    # Explicit selected archives are authoritative and are individually checked.
    explicit_images = all(os.environ.get(role.upper() + '_IMAGE_ARCHIVE') for role in required)
    result = resolve_media(args.base_dir, arch, 'verify' if explicit_images else args.mode,
                           os.environ.get('MEDIA_IMAGES_DIR', ''))
    if explicit_images:
        for role in required:
            result['images'][role] = {'archive': os.environ[role.upper() + '_IMAGE_ARCHIVE']}
    values = {'TARGET_ARCH': arch, 'DOCKER_ARCH': docker_arch(arch)}
    for key in ('apps', 'images', 'python', 'ascend'):
        values['MEDIA_' + key.upper() + '_DIR'] = os.environ.get('MEDIA_' + key.upper() + '_DIR') or result[key + '_dir']
    values['RUNTIME_BUNDLE'] = os.environ.get('RUNTIME_BUNDLE') or result['runtime_bundle']
    for role, record in result['images'].items():
        prefix = {'frontend': 'FRONTEND', 'backend': 'BACKEND', 'zlk': 'ZLK'}[role]
        values[prefix + '_IMAGE_ARCHIVE'] = os.environ.get(prefix + '_IMAGE_ARCHIVE') or record['archive']
        checked = inspect_image_archive(values[prefix + '_IMAGE_ARCHIVE'], arch)
        tags = [item for item in checked if _role(item['tag']) == role]
        if not tags:
            raise ValueError('镜像包缺少对应镜像：' + role)
        values[prefix + '_IMAGE'] = sorted(tags, key=_version_key)[-1]['tag']
    if args.shell_env:
        for name, value in values.items():
            print('export %s=%s' % (name, shlex.quote(str(value))))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
