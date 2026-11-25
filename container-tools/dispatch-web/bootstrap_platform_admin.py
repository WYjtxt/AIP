"""Create the two built-in accounts only when all four auth tables are empty."""
import configparser
import json
import os
from pathlib import Path
import tempfile
import bcrypt
import pymysql

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value



# User-specified initial 8888 account. Existing accounts are never reset here.
INITIAL_ACCOUNTS = (('sysadmin', '超级管理员'), ('admin', '管理员'))
ADMIN_READ_ONLY_MENUS = ('dict',)
ADMIN_HIDDEN_MENUS = ('platform-upgrade',)


def write_initial_credentials(path, password):
    """Publish a private credentials record without following a stale target."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         prefix='.oneclick-admin-', dir=str(path.parent),
                                         delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(str(temporary), 0o600)
            # Older verification tools read the top-level admin credentials.
            json.dump({'username': 'admin', 'password': password,
                       'accounts': [{'username': username, 'password': password,
                                     'role': username, 'role_name': name}
                                    for username, name in INITIAL_ACCOUNTS]},
                      stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def seed_initial_accounts(db, path):
    try:
        with db.cursor() as cursor:
            counts=[]
            for table in ('t_user','t_permission','t_user_permission','t_premission_menu'):
                cursor.execute('SELECT COUNT(*) FROM '+table);counts.append(cursor.fetchone()[0])
            if any(counts):
                if counts[0]==0: raise ValueError('认证表部分初始化；保留原内容，需人工核对')
                print('ADMIN=EXISTING_PRESERVED')
                return False
            # A retained temporary record from an earlier failed installation
            # must not override the requested initial password for an empty DB.
            password = _required_site_value("AIP_INITIAL_ADMIN_PASSWORD")
            for username, name in INITIAL_ACCOUNTS:
                hashed=bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt()).decode('ascii')
                description=('内置超级管理员；全部启用菜单 CRUD' if username=='sysadmin' else
                             '初始管理员；业务及普通用户/角色管理 CRUD')
                cursor.execute("INSERT INTO t_permission (permission_name,permission_code,permission_content,permission_status) VALUES (%s,%s,%s,%s)",
                               (name,username,description,'1'))
                role=cursor.lastrowid
                if username=='sysadmin':
                    cursor.execute("INSERT INTO t_premission_menu (premission_id,menu_id,permissions_list) SELECT %s,id,%s FROM t_menu WHERE menu_status='1'",(role,'["c","r","u","d"]'))
                else:
                    cursor.execute("INSERT INTO t_premission_menu (premission_id,menu_id,permissions_list) "
                                   "SELECT %s,id,CASE WHEN menu_link IN (%s) THEN %s ELSE %s END "
                                   "FROM t_menu WHERE menu_status='1' AND (menu_link IS NULL OR menu_link NOT IN (%s))",
                                   (role,)+ADMIN_READ_ONLY_MENUS+('["r"]','["c","r","u","d"]')+ADMIN_HIDDEN_MENUS)
                cursor.execute("INSERT INTO t_user (name,username,password,user_status,free_secret) VALUES (%s,%s,%s,%s,%s)",
                               (name,username,hashed,'1','0'))
                cursor.execute('INSERT INTO t_user_permission (user_id,permission_id) VALUES (%s,%s)',(cursor.lastrowid,str(role)))
            write_initial_credentials(path, password)
            cursor.execute("INSERT INTO t_mine (mine_name,combined_field) SELECT %s,%s WHERE NOT EXISTS (SELECT 1 FROM t_mine)", ('新部署单位','新部署单位 -----------'))
            db.commit()
            print('ADMIN=CREATED; accounts=sysadmin,admin; initial credentials retained in protected deployment file')
            return True
    except Exception:
        db.rollback();raise


def main():
    config=configparser.ConfigParser(interpolation=None);config.read('/Seal_system/config.ini')
    c=config['database']
    db=pymysql.connect(host=c['DB_HOST'],port=int(c.get('DB_PORT',3306)),user=c['DB_USER'],
                       password=c['DB_PASSWORD'],database=c['DB_NAME'],charset='utf8mb4')
    try:
        seed_initial_accounts(db,Path('/tmp/oneclick-initial-admin.json'))
    finally:db.close()


if __name__=='__main__':main()
