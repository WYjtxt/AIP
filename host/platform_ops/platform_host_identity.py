"""Stable host identity and card ownership; IP remains a mutable address.

This module has no import-time I/O and is shared byte-for-byte by the backend,
scheduler and vendor collectors. It never writes or returns /etc/machine-id.
"""
import hashlib
import hmac
from pathlib import Path
import re
import secrets

TABLE = 't_platform_computing_identity'
APP_KEY = b'ai-platform.computing.v1'
ANCHOR_KEY = b'ai-platform.computing.anchor.v1'


class IdentityConflict(ValueError):
    pass


def _digest(value, key=APP_KEY):
    return hmac.new(key, value, hashlib.sha256).hexdigest()


def _uid(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise IdentityConflict('设备身份无效，未修改设备关联')
    return value


def derive_uid(machine_id):
    value = str(machine_id or '').strip().lower()
    if not re.fullmatch('[a-f0-9]{32}', value) or value == '0' * 32:
        raise IdentityConflict('宿主机 machine-id 无效，无法核实设备身份')
    return _digest(value.encode('ascii'))


def read_host_identity(machine_path='/etc/machine-id', system_root='/'):
    uid = derive_uid(Path(machine_path).read_text(encoding='ascii'))
    root = Path(system_root)
    anchor = None
    for name in ('/sys/class/dmi/id/product_uuid', '/sys/firmware/devicetree/base/serial-number'):
        path = root / name.lstrip('/')
        try:
            raw = path.read_bytes().strip(b'\x00\r\n ')
        except (FileNotFoundError, PermissionError):
            continue
        if raw and raw.lower() not in (b'none', b'unknown', b'not specified') and raw.replace(b'-', b'').strip(b'0'):
            anchor = _digest(name.encode() + b'\x00' + raw, ANCHOR_KEY)
            break
    return {'host_uid': uid, 'anchor_uid': anchor}


def ensure_schema(connection):
    # No existing business table or primary key is altered. MySQL DDL commits
    # independently, so callers back up before this separate preparation step.
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + ' ('
            'computing_id INTEGER NOT NULL PRIMARY KEY, '
            'host_uid VARCHAR(64) NOT NULL UNIQUE, anchor_uid VARCHAR(64), '
            'created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, '
            'updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    connection.commit()


def _missing_table(error):
    return (getattr(error, 'args', [None])[0] == 1146 or
            'no such table: ' + TABLE in str(error))


def _verify_anchor(saved, current):
    if saved is not None and saved != current:
        raise IdentityConflict('机器码重复或宿主机硬件身份变化，请核实后重新绑定')


def identity_rows(cursor, computing_id=None, host_uid=None, lock=False):
    query = 'SELECT computing_id,host_uid,anchor_uid FROM ' + TABLE
    args = ()
    if computing_id is not None and host_uid is not None:
        query += ' WHERE computing_id=%s OR host_uid=%s'; args = (int(computing_id), _uid(host_uid))
    elif computing_id is not None:
        query += ' WHERE computing_id=%s'; args = (int(computing_id),)
    elif host_uid is not None:
        query += ' WHERE host_uid=%s'; args = (_uid(host_uid),)
    query += ' ORDER BY computing_id' + (' FOR UPDATE' if lock else '')
    cursor.execute(query, args)
    return [dict(zip(('computing_id', 'host_uid', 'anchor_uid'), row)) for row in cursor.fetchall()]


def bind_identity(cursor, computing_id, identity):
    cid = int(computing_id)
    uid = _uid(identity['host_uid'])
    anchor = identity.get('anchor_uid')
    if anchor is not None: _uid(anchor)
    rows = identity_rows(cursor, cid, uid, lock=True)
    cursor.execute('SELECT id,server_type FROM t_computing_equipment WHERE id=%s FOR UPDATE', (cid,))
    device = cursor.fetchone()
    if not device or int(device[1]) != 1:
        raise IdentityConflict('没有对应的分析服务器，未绑定机器码')
    for row in rows:
        if row['computing_id'] != cid or row['host_uid'] != uid:
            raise IdentityConflict('该机器码已绑定其他服务器，或该服务器已绑定其他机器码')
        _verify_anchor(row['anchor_uid'], anchor)
    if rows:
        if rows[0]['anchor_uid'] is None and anchor is not None:
            cursor.execute('UPDATE ' + TABLE + ' SET anchor_uid=%s,updated_at=CURRENT_TIMESTAMP WHERE computing_id=%s', (anchor,cid))
            return True
        return False
    cursor.execute('INSERT INTO ' + TABLE + ' (computing_id,host_uid,anchor_uid) VALUES (%s,%s,%s)', (cid,uid,anchor))
    return True


def resolve_device(cursor, identity, legacy_ip=None, lock=False):
    """Resolve known identity first, even when configured IP is stale or empty.

    Legacy fallback is allowed only for one unbound server. An existing binding
    is never replaced because an IP was reused, an image cloned, or OS rebuilt.
    """
    uid = _uid(identity['host_uid'])
    try:
        rows = identity_rows(cursor, host_uid=uid, lock=lock)
        schema = True
    except Exception as error:
        if not _missing_table(error): raise
        rows, schema = [], False
    if rows:
        row = rows[0]; _verify_anchor(row['anchor_uid'],identity.get('anchor_uid'))
        cursor.execute('SELECT id,computing_ip,server_type FROM t_computing_equipment WHERE id=%s', (row['computing_id'],))
        device = cursor.fetchone()
        if not device or int(device[2]) != 1:
            raise IdentityConflict('机器码的服务器记录已不存在，需重新登记绑定')
        return {'computing_id':int(device[0]), 'computing_ip':device[1], 'source':'machine_id'}
    if not legacy_ip:
        return None
    cursor.execute('SELECT id,computing_ip,server_type FROM t_computing_equipment '
                   'WHERE computing_ip=%s AND server_type=1 ORDER BY id', (str(legacy_ip).strip(),))
    devices = cursor.fetchall()
    if len(devices) > 1:
        raise IdentityConflict('旧 IP 对应多台服务器，未自动选择或合并')
    if not devices:
        return None
    device = devices[0]
    if schema and identity_rows(cursor, computing_id=device[0]):
        raise IdentityConflict('该 IP 已属于其他机器码，未接管原服务器')
    return {'computing_id':int(device[0]),'computing_ip':device[1],'source':'legacy_ip'}


def publish_resources(connection, rows, identity, legacy_ip=None):
    """Use stable server + logical card ID, retaining existing resource PKs."""
    try:
        with connection.cursor() as cursor:
            device = resolve_device(cursor,identity,legacy_ip,lock=True)
            if device is None:
                raise IdentityConflict('本机未登记，未写入或新建算力卡')
            cid, address = device['computing_id'], device['computing_ip']
            updated = []
            for values in rows:
                if len(values) != 9:
                    raise ValueError('Invalid vendor resource sample')
                dev_id = int(values[1])
                if dev_id < 0:
                    raise ValueError('Invalid logical card ID')
                cursor.execute('SELECT id,dev_get_sn FROM t_resource_usage WHERE computing_id=%s AND dev_id=%s ORDER BY id FOR UPDATE', (cid,dev_id))
                matching = cursor.fetchall()
                if len(matching) > 1:
                    raise IdentityConflict('同一服务器存在重复算力卡记录，请核实后处理')
                if matching:
                    rid, saved_sn = matching[0]
                    if saved_sn and values[3] and str(saved_sn) != str(values[3]):
                        raise IdentityConflict('算力卡序列号变化，未覆盖原卡或任务关联')
                    cursor.execute('UPDATE t_resource_usage SET dev_ip=%s,dev_get_target=%s,dev_get_sn=%s,'
                        'board_temp=%s,chip_temp=%s,mem_used_mem_total=%s,memory_usage_rate=%s,tpu_util=%s,'
                        'updated_at=CURRENT_TIMESTAMP WHERE id=%s AND computing_id=%s',
                        (address,) + tuple(values[2:]) + (rid,cid))
                else:
                    cursor.execute('INSERT INTO t_resource_usage (dev_ip,dev_id,dev_get_target,dev_get_sn,'
                        'board_temp,chip_temp,mem_used_mem_total,memory_usage_rate,tpu_util,computing_id,resource_num,created_at,updated_at) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',
                        (address,dev_id) + tuple(values[2:]) + (cid,))
                    rid = cursor.lastrowid
                updated.append(int(rid))
        connection.commit()
        return {'computing_id':cid,'resource_ids':updated,'identity_source':device['source']}
    except Exception:
        connection.rollback()
        raise


def update_address(cursor, computing_id, address, identity):
    """Caller verified the remote identity; update addresses, never their PKs."""
    cid = int(computing_id)
    address = str(address or '').strip()
    if not address or len(address) > 50:
        raise ValueError('服务器地址无效')
    rows = identity_rows(cursor,cid,identity['host_uid'],lock=True)
    if len(rows) != 1 or rows[0]['computing_id'] != cid or rows[0]['host_uid'] != identity['host_uid']:
        raise IdentityConflict('新地址的机器码与原服务器不一致')
    _verify_anchor(rows[0]['anchor_uid'],identity.get('anchor_uid'))
    cursor.execute('SELECT id FROM t_computing_equipment WHERE computing_ip=%s AND id<>%s', (address,cid))
    if cursor.fetchone():
        raise IdentityConflict('新地址已登记为其他设备，未合并或覆盖')
    cursor.execute('UPDATE t_computing_equipment SET computing_ip=%s,updated_at=CURRENT_TIMESTAMP '
                   'WHERE id=%s AND computing_ip<>%s',(address,cid,address))
    cursor.execute('UPDATE t_resource_usage SET dev_ip=%s WHERE computing_id=%s AND (dev_ip IS NULL OR dev_ip<>%s)',(address,cid,address))


def register_device(connection, address, name, username, password, identity=None, allow_existing=False):
    """Register or re-use a verified host without creating a second server."""
    address = str(address or '').strip()
    if not address or len(address) > 50:
        raise ValueError('服务器地址无效')
    try:
        with connection.cursor() as cursor:
            mapped = identity_rows(cursor,host_uid=identity['host_uid'],lock=True) if identity else []
            if mapped:
                row = mapped[0]; _verify_anchor(row['anchor_uid'],identity.get('anchor_uid'))
                if not allow_existing:
                    raise IdentityConflict('同一台机器已经登记，请修改原服务器地址，无需重复添加')
                cid = row['computing_id']
                cursor.execute('SELECT computing_name,computing_ip FROM t_computing_equipment WHERE id=%s AND server_type=1',(cid,))
                previous=cursor.fetchone()
                if previous is None:raise IdentityConflict('原服务器记录已不存在，需重新绑定')
                update_address(cursor,cid,address,identity)
                result={'created':False,'computing_id':cid,'ip':address,'name':previous[0],
                        'status':'existing_preserved' if previous[1]==address else 'address_updated','identity_source':'machine_id'}
            else:
                cursor.execute('SELECT id,computing_name,server_type FROM t_computing_equipment WHERE computing_ip=%s ORDER BY id FOR UPDATE',(address,))
                rows=cursor.fetchall()
                if rows and (not allow_existing or len(rows)!=1 or int(rows[0][2])!=1):
                    raise IdentityConflict('该地址已经登记或存在歧义，未新增或覆盖服务器')
                if rows:
                    cid=rows[0][0]
                    if identity:bind_identity(cursor,cid,identity)
                    result={'created':False,'computing_id':cid,'ip':address,'name':rows[0][1],
                            'status':'existing_preserved','identity_source':'machine_id' if identity else 'legacy_ip'}
                else:
                    if not all(isinstance(value,str) and value for value in (name,username,password)) or any(len(value)>50 for value in (name,username,password)):
                        raise ValueError('缺少有效的服务器名称或 SSH 账号密码')
                    cursor.execute('INSERT INTO t_computing_equipment '
                        '(computing_ip,computing_name,computing_code,computing_user,computing_password,computing_status,server_type,created_at,updated_at) '
                        'VALUES (%s,%s,%s,%s,%s,1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',
                        (address,name,'YGSJ-'+secrets.token_hex(5),username,password))
                    cid=cursor.lastrowid
                    if identity:bind_identity(cursor,cid,identity)
                    result={'created':True,'computing_id':cid,'ip':address,'name':name,
                            'status':'created','identity_source':'machine_id' if identity else 'legacy_ip'}
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def rebind_after_reinstall(cursor, computing_id, expected_old_uid, identity):
    """Explicit recovery only when both the old binding and hardware match.

    This is never called by runtime lookup or address edits. A reinstall can
    change machine-id; matching independently derived hardware permits an
    administrator to retain the existing server/card/task primary keys.
    """
    cid=int(computing_id);old=_uid(expected_old_uid);new=_uid(identity['host_uid'])
    rows=identity_rows(cursor,computing_id=cid,host_uid=new,lock=True)
    own=[row for row in rows if row['computing_id']==cid]
    if len(own)!=1 or own[0]['host_uid']!=old or any(row['computing_id']!=cid for row in rows):
        raise IdentityConflict('原绑定已变化或新机器码被占用，未重新绑定')
    if own[0]['anchor_uid'] is None:
        raise IdentityConflict('缺少独立硬件指纹，需人工核实原服务器')
    _verify_anchor(own[0]['anchor_uid'],identity.get('anchor_uid'))
    cursor.execute('UPDATE '+TABLE+' SET host_uid=%s,updated_at=CURRENT_TIMESTAMP WHERE computing_id=%s AND host_uid=%s',(new,cid,old))
    return cursor.rowcount==1
