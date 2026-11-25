"""Package only this installation's public CA and the existing Windows installer."""
import os
from pathlib import Path
import subprocess
import zipfile

root=Path(os.environ.get('ONECLICK_ROOT','/root/oneclick'))
destination=root/'dispatch-certificate-windows.zip'
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    archive.write('/data/config_dispatch/dispatch-root-ca.cer','dispatch-root-ca.cer')
    for filename in ('install-dispatch-certificate.ps1','README.txt'):
        content=subprocess.check_output(['docker','exec','seal_system_vue','cat','/usr/share/nginx/html/static/certificates/'+filename])
        archive.writestr(filename,content)
destination.chmod(0o644)
print('TARGET_PUBLIC_CERTIFICATE_BUNDLE=READY')
