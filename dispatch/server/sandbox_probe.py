import ctypes,errno,json,os,socket
from pathlib import Path
from secure_server import load_legacy
from security_config import SecurityConfig
root=Path('/data/AIGO/platform_start/config_dispatch/state/sandbox-probe')
file=root/'Config_files/config.ini'
legacy=load_legacy('/data/AIGO/platform_start/config_dispatch/config_dispatch.py')
ips=legacy.detect_ips()
assert any(item['ip']=='172.16.129.236' for item in ips)
legacy.discover=lambda force=False:[{'kind':'Config_files','path':str(file.parent),'files':[{'key':'app_ini','rel':'config.ini','label':'probe','path':str(file),'exists':True}]}]
guard=SecurityConfig(legacy,[str(file)],root/'backups',data_root=root,strict_permissions=True)
plan=guard.preview({'files':[str(file)],'values':{'db_host':'127.0.0.2','db_password':''}},'disposable-probe-session')
result=guard.apply({'plan_id':plan['plan_id']},'disposable-probe-session')
assert result['applied']==1 and file.stat().st_uid==1000 and file.stat().st_gid==1000
assert 'disposable-probe-value' in file.read_text()
blocked=False
sock=socket.socket()
try:sock.connect(('127.0.0.1',22))
except PermissionError as error:blocked=error.errno==errno.EPERM
finally:sock.close()
assert blocked
libc=ctypes.CDLL(None,use_errno=True)
parameters=ctypes.create_string_buffer(256)
assert libc.syscall(425,1,ctypes.byref(parameters))==-1 and ctypes.get_errno()==errno.EPERM
assert os.geteuid()!=0 and not os.access('/data/AIGO/platform_start/config_dispatch/secure_server.py',os.W_OK)
Path('/data/AIGO/platform_start/config_dispatch/state/sandbox-safe.json').write_text(json.dumps({'nonroot':True,'ip_detection':True,'outbound_connect_blocked':True,'io_uring_blocked':True,'atomic_write_owner_preserved':True,'blank_secret_preserved':True}))
