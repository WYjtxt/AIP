"""Install the supplied BM1684X algorithm and matching offline Python SDK."""
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess


PYTHON_PACKAGES = ('numpy==1.24.4','opencv-python-headless==4.10.0.84','Pillow==10.4.0',
                   'PyMySQL==1.1.1','DBUtils==3.1.0','kafka-python==2.0.2',
                   'requests==2.32.3','PyYAML==6.0.2','scipy==1.10.1','shapely==2.0.6')


def sdk_environment(root):
    root = PurePosixPath(Path(root).as_posix())
    ffmpeg = PurePosixPath('/opt/sophon/sophon-ffmpeg_0.10.0')
    libs = PurePosixPath('/opt/sophon/libsophon-0.5.1')
    opencv = PurePosixPath('/opt/sophon/sophon-opencv_0.10.0')
    return {'PATH': str(ffmpeg/'bin') + ':' + str(root/'runtime/sophon-python/bin') + ':' +
                    str(root/'runtime/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'LD_LIBRARY_PATH': ':'.join(str(p) for p in (libs/'lib',ffmpeg/'lib',opencv/'lib')),
            'FFMPEG_BIN': str(ffmpeg/'bin/ffmpeg'), 'FFPROBE_BIN': str(ffmpeg/'bin/ffprobe'),
            'PYTHONNOUSERSITE':'1','CV2_NUM_THREADS':'1'}


def install(root, packages, env, run, unit):
    root, packages = Path(root), Path(packages)
    from install_native_dependencies import install_os_packages
    sdk = packages/'x86_64/sophon'
    if not sdk.is_dir():
        sdk = packages/'sophon'
    if not Path('/sys/module/bmsophon').is_dir():
        install_os_packages(['dkms','linux-headers-'+platform.release()],packages,'x86_64',env)
        run(['dpkg','-i',sdk/'sophon-driver_0.5.1_amd64.deb'])
        run(['modprobe','bmsophon'])
    install_os_packages(['libncurses5','libatomic1','libglib2.0-0'],packages,'x86_64',env)
    # Ubuntu 20.04's Python 3.8 matches the supplied vendor SAIL extension.
    if subprocess.run(['/usr/bin/python3','-c','import sys,venv;assert sys.version_info[:2]==(3,8)'],
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        install_os_packages(['python3.8','python3.8-venv','python3-pip'],packages,'x86_64',env)
    required = ('sophon-libsophon_0.5.1_amd64.deb','sophon-mw-sophon-ffmpeg_0.10.0_amd64.deb',
                'sophon-mw-sophon-opencv_0.10.0_amd64.deb')
    if not (Path('/opt/sophon/libsophon-0.5.1/lib/libbmlib.so').exists() and
            Path('/opt/sophon/sophon-ffmpeg_0.10.0/bin/ffmpeg').is_file() and
            Path('/opt/sophon/sophon-opencv_0.10.0/lib').is_dir()):
        run(['dpkg','-i'] + [sdk/name for name in required])
        run(['ldconfig'])
    virtual = root/'runtime/sophon-python'
    if not (virtual/'bin/python').exists():
        install_os_packages(['python3.8-venv'],packages,'x86_64',env)
        run(['/usr/bin/python3','-m','venv',virtual])
    wheelhouse = packages/'x86_64/python/wheels'
    if not wheelhouse.is_dir():
        wheelhouse = packages/'python/wheels'
    wheel = sdk/'python_wheels/sophon-3.10.7-py3-none-any.whl'
    run([virtual/'bin/python','-m','pip','install','--no-index','--find-links',wheelhouse,
         '--disable-pip-version-check'] + list(PYTHON_PACKAGES) + [wheel])
    settings = sdk_environment(root)
    check_env = dict(os.environ, **settings)
    check_env.pop('PYTHONPATH',None)
    check_env.pop('PYTHONHOME',None)
    run([virtual/'bin/python','-c',
         'import cv2,numpy,sophon.sail as sail;assert sail.get_available_tpu_num()>0;'
         'assert all(str(sail.Handle(i).get_target()).lower()=="bm1684x" for i in range(sail.get_available_tpu_num()))'],
        env=check_env)
    encoders = subprocess.run([settings['FFMPEG_BIN'],'-hide_banner','-encoders'],env=check_env,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,check=True).stdout
    if 'h264_bm' not in encoders:
        raise RuntimeError('算能FFmpeg缺少h264_bm编码器，算法服务未启动')
    names = []
    for name,folder,script in (('model_start','platform_algorithm_start','model_start.py'),
                               ('resource','model_algorithm_package','Sophon_resource.py'),
                               ('kafka_consumer','model_algorithm_package','kafka_consumer.py')):
        unit(name,[virtual/'bin/python',root/folder/script],root/folder,settings)
        names.append(name)
    return names
