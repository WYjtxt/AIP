"""Install a real wheel in a temporary environment with indexes and network disabled."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(args, environment):
    result = subprocess.run(args, cwd='/', env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True, timeout=240)
    if result.returncode:
        raise RuntimeError(result.stdout[-4000:])
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default='/usr/bin/python3')
    parser.add_argument('--wheelhouse',required=True)
    parser.add_argument('--requirements')
    args=parser.parse_args()
    wheels=Path(args.wheelhouse).resolve()
    if not list(wheels.glob('*.whl')): raise SystemExit('离线 wheel 目录为空')
    env=dict(os.environ,PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',
             PIP_FIND_LINKS=str(wheels),PIP_NO_CACHE_DIR='1',PYTHONNOUSERSITE='1')
    for key in ('PYTHONPATH','PYTHONHOME','PIP_INDEX_URL','PIP_EXTRA_INDEX_URL','PIP_TRUSTED_HOST'):
        env.pop(key,None)
    version=run([args.python,'-m','pip','--version'],env)
    with tempfile.TemporaryDirectory(prefix='oneclick-pip-check-') as folder:
        # --target avoids depending on ensurepip/venv on minimal openEuler.
        run([args.python,'-m','pip','install','--no-index','--no-deps','--only-binary=:all:',
             '--find-links',str(wheels),'--target',folder,'packaging==24.2'],env)
        run([args.python,'-I','-c','import sys;sys.path.insert(0,sys.argv[1]);import packaging;assert packaging.__version__=="24.2"',folder],env)
    if args.requirements:
        run([args.python,'-m','pip','install','--no-index','--only-binary=:all:',
             '--find-links',str(wheels),'-r',args.requirements],env)
        run([args.python,'-m','pip','check'],env)
    print(json.dumps({'pip':version,'offline_wheel_install':'passed','index_access':False}))


if __name__=='__main__': main()
