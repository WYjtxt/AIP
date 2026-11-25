import subprocess
from pathlib import Path
from storage_operations import StorageManager
slot=Path('/data/AIGO/platform_storage/alarm-volumes')
slot.mkdir(parents=True,exist_ok=True)
if subprocess.call(['mountpoint','-q',str(slot)]):subprocess.run(['mount','--bind',str(slot),str(slot)],check=True)
subprocess.run(['mount','--make-shared',str(slot)],check=True)
StorageManager().restore()
