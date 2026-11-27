"""Backend bridge for verified host identities and editable connection addresses."""
import json
from pathlib import Path

from common.platform_host_identity import (IdentityConflict, _missing_table, _uid,
    _verify_anchor, bind_identity, identity_rows, read_host_identity, register_device, update_address)

SITE_STATE = Path(__file__).parents[2] / 'platform_ops/state/site-config.json'


def _guard_local_site_address(mapped, target):
    """Keep this host's cloud address behind the unified configuration writer."""
    if not mapped or not SITE_STATE.is_file():
        return
    if mapped[0]['host_uid'] != read_host_identity()['host_uid']:
        return  # Remote analysis servers keep their verified address editor.
    address = json.loads(SITE_STATE.read_text(encoding='utf-8'))['applied']['node']['address']
    if target != address:
        raise IdentityConflict('本机 IP 已由 Config_files/platform-site.json 统一管理，请通过统一配置预览并应用')


SAVED_SECRET_MASK = '*' * 6


class IdentityProbeUnavailable(ValueError):
    pass


def identity_probe_source():
    module = (Path(__file__).parents[1] / 'common/platform_host_identity.py').read_text(encoding='utf-8')
    return module + '\nimport json;print(json.dumps(read_host_identity()), flush=True)\n'


def probe_identity(address, username, password):
    """Read derived IDs through authenticated SSH; raw machine-id stays remote."""
    import paramiko
    ssh=paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(str(address),username=username,password=password,timeout=5,banner_timeout=5,
                    auth_timeout=5,look_for_keys=False,allow_agent=False)
        stdin,stdout,stderr=ssh.exec_command('python3 -',timeout=6)
        stdin.write('exec('+ascii(identity_probe_source())+')');stdin.channel.shutdown_write()
        raw=stdout.read(4096);error=stderr.read();code=stdout.channel.recv_exit_status()
        if code:raise IdentityProbeUnavailable('无法读取远程设备身份')
        value=json.loads(raw.decode('utf-8'));_uid(value['host_uid'])
        if value.get('anchor_uid') is not None:_uid(value['anchor_uid'])
        return {'host_uid':value['host_uid'],'anchor_uid':value.get('anchor_uid')}
    except IdentityProbeUnavailable:
        raise
    except Exception:
        # SSH exceptions can include connection details. Never return exception
        # strings, credentials or raw command output in HTTP responses/logs.
        raise IdentityProbeUnavailable('无法核实远程设备身份，请检查地址和 SSH 连接') from None
    finally:
        ssh.close()


def _connection():
    from model.equipment import db
    return db.engine.raw_connection()


def binding_map():
    connection=_connection()
    try:
        with connection.cursor() as cursor:
            try:rows=identity_rows(cursor)
            except Exception as error:
                if _missing_table(error):return {}
                raise
        return {row['computing_id']:row for row in rows}
    finally:connection.close()


def uid_map():
    return {key: row['host_uid'] for key, row in binding_map().items()}


def add(address, name, username, password):
    if not all([address,name,username,password]):return False,'模板数据有未填写项'
    connection=None
    try:
        try:identity=probe_identity(address,username,password)
        except IdentityProbeUnavailable:identity=None  # Preserve offline manual registration.
        connection=_connection()
        register_device(connection,address,name,username,password,identity,allow_existing=False)
        return True,'算力设备添加成功！'
    except (IdentityConflict,ValueError) as error:
        if connection:connection.rollback()
        return False,str(error)
    except Exception:
        if connection:connection.rollback()
        return False,'算力设备添加失败，请核对设备身份和连接配置'
    finally:
        if connection:connection.close()


def update(computing_id, address=None, name=None, username=None, password=None):
    connection=None
    try:
        connection=_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT computing_ip,computing_name,computing_user,computing_password,server_type '
                           'FROM t_computing_equipment WHERE id=%s',(int(computing_id),))
            old=cursor.fetchone()
            if not old:return False,'算力设备不存在'
            mapped=identity_rows(cursor,computing_id=int(computing_id))
        if password in ('', SAVED_SECRET_MASK):
            password=None
        target=old[0] if address is None else str(address).strip()
        user=old[2] if username is None else username
        secret=old[3] if password is None else password
        if not target or len(target)>50:raise ValueError('服务器地址无效')
        for value in (name,username,password):
            if value is not None and (not isinstance(value,str) or len(value)>50):raise ValueError('设备字段长度无效')
        # End the read transaction before network I/O. Lock and compare the
        # current row again after validation, so concurrent edits are preserved.
        connection.rollback()
        _guard_local_site_address(mapped, target)
        peer=None
        if target!=old[0]:
            peer=probe_identity(target,user,secret)
            expected=mapped[0] if mapped else probe_identity(old[0],old[2],old[3])
            if expected['host_uid']!=peer['host_uid']:raise IdentityConflict('新地址对应另一台机器，未修改原设备')
            _verify_anchor(expected.get('anchor_uid'),peer.get('anchor_uid'))
        with connection.cursor() as cursor:
            # Lock identity before device, consistently with collector/binder.
            identity_rows(cursor,computing_id=int(computing_id),lock=True)
            cursor.execute('SELECT computing_ip,computing_name,computing_user,computing_password,server_type '
                           'FROM t_computing_equipment WHERE id=%s FOR UPDATE',(int(computing_id),))
            if cursor.fetchone()!=old:raise IdentityConflict('设备配置同时被修改，请刷新后重试')
            if peer:
                bind_identity(cursor,int(computing_id),peer)
                update_address(cursor,int(computing_id),target,peer)
            values=[];fields=[]
            for column,value,previous in (('computing_name',name,old[1]),('computing_user',username,old[2]),('computing_password',password,old[3])):
                if value is not None and value!=previous:fields.append(column+'=%s');values.append(value)
            if fields:
                cursor.execute('UPDATE t_computing_equipment SET '+','.join(fields)+',updated_at=CURRENT_TIMESTAMP WHERE id=%s',tuple(values)+(int(computing_id),))
        connection.commit()
        return True,'修改成功'
    except (IdentityConflict,IdentityProbeUnavailable,ValueError) as error:
        if connection:connection.rollback()
        return False,str(error)
    except Exception:
        if connection:connection.rollback()
        return False,'更新算力设备失败，请核对设备身份和连接配置'
    finally:
        if connection:connection.close()


def delete_binding_and_device(computing_id):
    connection=_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM t_platform_computing_identity WHERE computing_id=%s',(int(computing_id),))
            cursor.execute('DELETE FROM t_computing_equipment WHERE id=%s',(int(computing_id),))
            result=cursor.rowcount
        connection.commit()
        return result
    except Exception:
        connection.rollback();raise
    finally:connection.close()
