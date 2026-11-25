"""Hash-pinned release media; offline mode never performs a network request."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import urllib.request


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or not name:
        raise ValueError('介质清单路径无效：' + name)
    root = Path(root).resolve()
    path = (root / name).resolve()
    if root not in path.parents:
        raise ValueError('介质清单路径越界：' + name)
    return path


def audit(root, profile, mode='offline', base_url='', scope='full'):
    root = Path(root)
    manifest = json.loads((root / 'release-lock.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or profile not in manifest['profiles']:
        raise ValueError('发布清单缺少匹配的安装配置：' + profile)
    if mode not in ('offline', 'online'):
        raise ValueError('安装来源必须为 online 或 offline')
    missing = []
    for entry in manifest['profiles'][profile]['files']:
        if scope == 'platform' and entry.get('scope', 'full') != 'platform':
            continue
        path = safe_path(root, entry['path'])
        if not re.fullmatch('[a-f0-9]{64}', entry['sha256']):
            raise ValueError('无效 SHA256：' + entry['path'])
        if path.is_file() and path.stat().st_size == entry['bytes'] and sha256(path) == entry['sha256']:
            continue
        url = entry.get('url') or (base_url.rstrip('/') + '/' + urllib.parse.quote(entry['path']) if base_url else '')
        if mode == 'offline' or not url:
            missing.append(entry['path'])
            continue
        if urllib.parse.urlparse(url).scheme != 'https':
            raise ValueError('在线介质只接受 HTTPS 地址：' + entry['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + '.partial')
        print('[下载] ' + entry['path'], flush=True)
        try:
            with urllib.request.urlopen(url, timeout=60) as source, partial.open('wb') as target:
                while True:
                    block = source.read(4 * 1024 * 1024)
                    if not block:
                        break
                    target.write(block)
            if partial.stat().st_size != entry['bytes'] or sha256(partial) != entry['sha256']:
                raise ValueError('下载内容校验失败：' + entry['path'])
            partial.replace(path)
        finally:
            if partial.exists():
                partial.unlink()
    if missing:
        raise ValueError('介质缺失或 SHA256 不一致（尚未安装/清理）：\n  ' + '\n  '.join(missing))
    return manifest['profiles'][profile]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--profile', required=True)
    parser.add_argument('--mode', choices=('online', 'offline'), default='offline')
    parser.add_argument('--base-url', default='')
    parser.add_argument('--scope', choices=('full', 'platform'), default='full')
    args = parser.parse_args()
    audit(args.root, args.profile, args.mode, args.base_url, args.scope)
    print('RELEASE_MEDIA=PASS')


if __name__ == '__main__':
    main()
