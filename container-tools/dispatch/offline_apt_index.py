"""Produce an APT Packages index from hash-validated, architecture-scoped debs."""
import hashlib
from pathlib import Path
import subprocess
import sys

def main(folder):
    root = Path(folder).resolve()
    records = []
    for path in sorted(root.glob('*.deb')):
        control = subprocess.check_output(['dpkg-deb', '-f', str(path)], universal_newlines=True)
        fields = dict(line.split(': ', 1) for line in control.splitlines() if ': ' in line and not line.startswith(' '))
        if fields.get('Architecture') not in ('amd64', 'all'):
            raise ValueError('Ubuntu x86 介质包含错误架构：' + path.name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(control.rstrip() + '\nFilename: ./' + path.name + '\nSize: ' + str(path.stat().st_size) + '\nSHA256: ' + digest + '\n')
    if not records:
        raise ValueError('离线 deb 目录为空')
    (root / 'Packages').write_text('\n'.join(records), encoding='utf-8')

if __name__ == '__main__':
    main(sys.argv[1])
