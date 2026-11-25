"""Install and verify the private FFmpeg tools used by native and container services."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile


HOST_PATH = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
WRAPPER_MARKER = '# AI_PLATFORM_NATIVE_MEDIA_WRAPPER_V1'


def media_environment(root):
    root = Path(root)
    return {'PATH': str(root / 'runtime/bin') + ':' + HOST_PATH,
            'FFMPEG_BIN': str(root / 'runtime/bin/ffmpeg'),
            'FFPROBE_BIN': str(root / 'runtime/bin/ffprobe')}


def _run(command, timeout=25):
    result = subprocess.run([str(value) for value in command], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)
    if result.returncode:
        # The verification uses local synthetic video only, never a camera URL.
        raise RuntimeError('FFmpeg verification failed: ' + str(command[0]) + '\n' + result.stderr[-1600:])
    return result.stdout


def verify(root):
    """Encode and probe a real H.264/FLV sample, using only packaged tools."""
    root = Path(root)
    tools = {name: root / 'runtime/bin' / name for name in ('ffmpeg', 'ffprobe')}
    for name, path in tools.items():
        if not path.is_file() or not os.access(str(path), os.X_OK):
            raise RuntimeError('缺少可执行的 ' + name + '，请使用完整的一键部署媒体包：' + str(path))
    versions = {name: _run([path, '-version']).splitlines()[0] for name, path in tools.items()}
    protocols = _run([tools['ffmpeg'], '-hide_banner', '-protocols'])
    if not all(re.search(r'(?m)^\s*' + name + r'\s*$', protocols) for name in ('tcp', 'rtmp')):
        raise RuntimeError('平台 FFmpeg 缺少 TCP/RTMP 协议支持')
    with tempfile.TemporaryDirectory(prefix='ffmpeg-check-', dir=str(root / 'runtime')) as temporary:
        sample = Path(temporary) / 'push-check.flv'
        _run([tools['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
              '-i', 'testsrc=size=160x90:rate=5', '-frames:v', '3', '-an', '-c:v', 'libx264',
              '-pix_fmt', 'yuv420p', '-f', 'flv', sample])
        result = json.loads(_run([tools['ffprobe'], '-v', 'error', '-select_streams', 'v:0',
                                 '-count_frames', '-show_entries', 'stream=codec_name,width,height,nb_read_frames',
                                 '-of', 'json', sample]))
        streams = result.get('streams', [])
        if not streams or any(streams[0].get(key) != value for key, value in
                              (('codec_name', 'h264'), ('width', 160), ('height', 90), ('nb_read_frames', '3'))):
            raise RuntimeError('平台 FFmpeg 实际 H.264 编码或 FFprobe 探测未通过')
    return {'result': 'PASS', 'versions': versions, 'h264_flv_frames': 3,
            'tcp': True, 'rtmp': True, 'source': 'packaged-runtime'}


def host_wrapper(root, name):
    return '#!/bin/sh\n' + WRAPPER_MARKER + '\nexec ' + shlex.quote(str(Path(root) / 'runtime/bin' / name)) + ' "$@"\n'


def _owned_wrapper(path):
    try:
        with path.open('rb') as source:
            return WRAPPER_MARKER.encode() in source.read(4096)
    except OSError:
        return False


def install_host_commands(root, host_bin='/usr/local/bin', host_path=HOST_PATH):
    """Make SSH-launched commands work without replacing unrelated host programs."""
    folder = Path(host_bin)
    result = {}
    for name in ('ffmpeg', 'ffprobe'):
        destination = folder / name
        if (destination.exists() or destination.is_symlink()) and not _owned_wrapper(destination):
            result[name] = 'preserved-existing-command'
            continue
        if not destination.exists() and not destination.is_symlink() and shutil.which(name, path=host_path):
            result[name] = 'preserved-existing-command'
            continue
        source = host_wrapper(root, name)
        if destination.is_file() and destination.read_text(encoding='utf-8') == source:
            destination.chmod(0o755)
            result[name] = 'already-installed'
            continue
        folder.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            destination.unlink()
        destination.write_text(source, encoding='utf-8')
        destination.chmod(0o755)
        result[name] = 'installed-private-runtime-wrapper'
    return result


def patch_remote_push(root):
    """The SSH entry point must not rely on a shell's optional system FFmpeg."""
    path = Path(root) / 'model_algorithm_package/rtsp_push_latest.py'
    if not path.is_file():
        return False
    source = path.read_text(encoding='utf-8')
    marker = '# native-private-ffmpeg-v1'
    if marker in source:
        return False
    before = ("    ffmpeg_bin = shutil.which('ffmpeg')\n"
              "    if ffmpeg_bin is None:\n"
              "        ffmpeg_bin = '/opt/sophon/sophon-ffmpeg-latest/bin/ffmpeg'")
    after = ("    " + marker + "\n"
             "    from pathlib import Path\n"
             "    private_ffmpeg = Path(__file__).resolve().parents[1] / 'runtime/bin/ffmpeg'\n"
             "    ffmpeg_bin = str(private_ffmpeg) if private_ffmpeg.is_file() else shutil.which('ffmpeg')\n"
             "    if not ffmpeg_bin:\n"
             "        raise RuntimeError('FFmpeg 未安装，请使用一键部署修复该算力服务器')")
    if source.count(before) != 1:
        raise ValueError('无法定位远程原始视频推流的 FFmpeg 入口')
    source = source.replace(before, after, 1)
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(source)
    return True


def configure_media(root):
    path = Path(root) / 'Config_files/zlk/config.ini'
    if not path.is_file():
        return False
    source = path.read_text(encoding='utf-8')
    private = str(Path(root) / 'runtime/bin/ffmpeg')
    updated = source.replace('/usr/bin/ffmpeg', private)
    updated = re.sub(r'(?m)^bin=ffmpeg[ \t]*$', lambda match: 'bin=' + private, updated)
    if source == updated:
        return False
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(updated)
    return True


def install(root, host_bin='/usr/local/bin', host_path=HOST_PATH):
    report = verify(root)
    report['host_commands'] = install_host_commands(root, host_bin, host_path)
    report['remote_push_updated'] = patch_remote_push(root)
    report['media_config_updated'] = configure_media(root)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Verify packaged encoding and probing without installing wrappers')
    args = parser.parse_args()
    report = verify(args.root) if args.check else install(args.root)
    print('NATIVE_FFMPEG=' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
