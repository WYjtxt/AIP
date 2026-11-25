"""Run the architecture's existing image entrypoint with the applied site address."""

import hashlib
import os
from pathlib import Path
import runpy
import stat
import sys
import tempfile

from platform_site_config import applied_environment


_STOCK_SCHEDULER_SHA256 = '8bacc3e3c187c19aeeb78e09510601ea233951e74720fe777dacaea649219fc1'


def prepare_sophon_startup(root, sdk=Path('/opt/sophon')):
    receiver = root / 'platform_algorithm_start/comm/data_receive.py'
    if receiver.is_file() and not receiver.is_symlink():
        original = receiver.read_bytes()
        if hashlib.sha256(original).hexdigest() == _STOCK_SCHEDULER_SHA256:
            updated = original.replace(b'import ast\n', b'import ast\nimport logging\n', 1)
            with tempfile.NamedTemporaryFile(dir=receiver.parent, prefix='.data_receive-', delete=False) as output:
                pending = Path(output.name)
                output.write(updated)
            try:
                pending.chmod(stat.S_IMODE(receiver.stat().st_mode))
                pending.replace(receiver)
            finally:
                if pending.exists():
                    pending.unlink()
    current = sdk / 'libsophon-current'
    version = sdk / 'libsophon-0.5.1'
    module = version / 'lib/tpu_module/libbm1684x_kernel_module.so'
    if not os.path.lexists(current) and module.is_file():
        try:
            current.symlink_to(version.name, target_is_directory=True)
        except FileExistsError:
            pass



def _apply_tailgate_inject(root):
    """容器启动时注入人员尾随模板/配置页（幂等，失败不影响平台启动）。"""  # TAILGATE_ENTRY_HOOK_V1
    import subprocess
    role = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == 'run' else ''
    script = root / 'model_algorithm_package/tailgate_ext/inject.py'
    if not role or not script.is_file():
        return
    try:
        subprocess.run([sys.executable, str(script), role], timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


def prepare_network_status_ui(root):
    # This site overlay applies only to the exact IP management bundle it replaces.
    web = root / 'frontend'
    index = web / 'index.html'
    original = index.read_bytes()
    old_ref = b'platform-site-ui.5de37d698adf.js?v=5de37d698adf'
    if old_ref not in original:
        return
    assets = web / 'static/js'
    if hashlib.sha256((assets / 'platform-site-ui.5de37d698adf.js').read_bytes()).hexdigest() != '5de37d698adf072056ee9862101667912dd11e71c7cf8635fc6d4511e4abe71e':
        return
    source = (root / 'Config_files' / 'platform-site-ui.200c60522e99.js').read_bytes()
    if hashlib.sha256(source).hexdigest() != '200c60522e99e0f776a06cd9450be5da04583f16daa91b00ee7f3b4b7bca2d2e':
        raise ValueError('IP management UI checksum mismatch')
    for target, content in ((assets / 'platform-site-ui.200c60522e99.js', source), (index, original.replace(old_ref, b'platform-site-ui.200c60522e99.js?v=200c60522e99'))):
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            scratch = Path(stream.name)
            stream.write(content)
        try:
            scratch.chmod(stat.S_IMODE(index.stat().st_mode))
            scratch.replace(target)
        finally:
            if scratch.exists():
                scratch.unlink()


def main():
    root = Path('/data/AIGO/platform_start')
    os.environ.update(applied_environment(root, dict(os.environ)))
    if os.environ.get('PLATFORM_ALGORITHM_FAMILY') == 'sophon' and sys.argv[1:3] == ['run', 'algorithm-master']:
        prepare_sophon_startup(root)
    _apply_tailgate_inject(root)
    if sys.argv[1:3] == ['run', 'web']:
        try:
            prepare_network_status_ui(root)
        except (OSError, ValueError) as error:
            print('IP management UI update skipped: ' + str(error), file=sys.stderr)
    runpy.run_path('/opt/ai-platform/container_runtime.py', run_name='__main__')


if __name__ == '__main__':
    main()
