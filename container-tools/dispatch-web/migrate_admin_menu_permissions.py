"""Apply built-in role defaults within explicit scopes; preserve existing site choices."""
import configparser
import json
import re

import pymysql


MENU_SCOPE = ('user', 'role', 'data-push', 'storage')
REQUIRED_ACTIONS = ('c', 'r', 'u', 'd')
USER_DEFAULT_ROOTS = (1, 6, 9, 14)


def ordinary_menu_ids(menus, legacy=False):
    """Business groups plus only the device-monitoring page and its parents."""
    roots = USER_DEFAULT_ROOTS + ((21,) if legacy else ())
    selected = {menu for menu, parent, link in menus if menu in roots and parent is None}
    while True:
        expanded = selected | {menu for menu, parent, link in menus if parent in selected}
        if expanded == selected:
            break
        selected = expanded
    if not legacy:
        parents = {menu: parent for menu, parent, link in menus}
        for menu, parent, link in menus:
            if (link or '').strip('/') != 'ygzx':
                continue
            while menu in parents and menu not in selected:
                selected.add(menu)
                menu = parents[menu]
    return selected


def read_actions(raw):
    """Read JSON lists or legacy unquoted action tokens without evaluating code."""
    text = (raw or '[]').strip()
    try:
        actions = json.loads(text)
    except (ValueError, TypeError):
        token = r'[A-Za-z_][A-Za-z0-9_.:-]*'
        if not re.fullmatch(r'\[\s*(?:' + token + r'(?:\s*,\s*' + token + r')*)?\s*\]', text):
            raise ValueError('admin scoped menu grant must contain a JSON list or legacy action list')
        actions = [action.strip() for action in text[1:-1].split(',') if action.strip()]
    if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
        raise ValueError('admin scoped menu grant must contain a JSON list of action strings')
    return actions


def migrate_admin_permissions(db):
    """Ensure the ordinary role and migrate defaults while retaining manual grants."""
    changed = 0
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM t_permission WHERE permission_code=%s", ('admin',))
            roles = [row[0] for row in cursor.fetchall()]
            placeholders = ','.join(['%s'] * len(MENU_SCOPE))
            cursor.execute("SELECT id FROM t_menu WHERE menu_status='1' AND menu_link IN (" + placeholders + ")", MENU_SCOPE)
            menus = [row[0] for row in cursor.fetchall()]
            for role in roles:
                cursor.execute('SELECT id FROM t_menu WHERE menu_link=%s', ('platform-upgrade',))
                for menu, in cursor.fetchall():
                    cursor.execute('DELETE FROM t_premission_menu WHERE premission_id=%s AND menu_id=%s', (role, menu))
                    changed += cursor.rowcount
                for menu in menus:
                    cursor.execute('SELECT id,permissions_list FROM t_premission_menu WHERE premission_id=%s AND menu_id=%s', (role, menu))
                    grants = cursor.fetchall()
                    if not grants:
                        cursor.execute('INSERT INTO t_premission_menu (premission_id,menu_id,permissions_list) VALUES (%s,%s,%s)',
                                       (role, menu, json.dumps(list(REQUIRED_ACTIONS))))
                        changed += 1
                    for grant, raw in grants:
                        actions = read_actions(raw)
                        missing = [action for action in REQUIRED_ACTIONS if action not in actions]
                        if missing:
                            cursor.execute('UPDATE t_premission_menu SET permissions_list=%s WHERE id=%s',
                                           (json.dumps(actions + missing, ensure_ascii=False), grant))
                            changed += 1
            cursor.execute('SELECT id FROM t_permission WHERE permission_code=%s', ('user',))
            if not cursor.fetchall():
                cursor.execute('SELECT COUNT(*) FROM t_user')
                if cursor.fetchone()[0]:
                    cursor.execute('INSERT INTO t_permission (permission_name,permission_code,permission_content,permission_status) VALUES (%s,%s,%s,%s)',
                                   ('普通用户', 'user', '普通用户', '1'))
                    changed += 1
            # Only empty grants or the exact prior read-only default are
            # upgraded. An administrator's custom permissions stay as saved.
            cursor.execute("SELECT id FROM t_permission WHERE permission_code=%s AND permission_status='1'", ('user',))
            ordinary_roles = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT id,menu_parent_id,menu_link FROM t_menu WHERE menu_status='1'")
            menus = cursor.fetchall()
            selected = ordinary_menu_ids(menus)
            previous = ordinary_menu_ids(menus, legacy=True)
            for role in ordinary_roles:
                cursor.execute('SELECT menu_id,permissions_list FROM t_premission_menu WHERE premission_id=%s', (role,))
                grants = cursor.fetchall()
                if grants and (selected == previous or not ({row[0] for row in grants} == previous
                                   and all(set(read_actions(row[1])) == {'r'} for row in grants))):
                    continue
                if grants:
                    cursor.execute('DELETE FROM t_premission_menu WHERE premission_id=%s', (role,))
                    changed += cursor.rowcount
                for menu in sorted(selected):
                    cursor.execute('INSERT INTO t_premission_menu (premission_id,menu_id,permissions_list) VALUES (%s,%s,%s)',
                                   (role, menu, '["r"]'))
                    changed += 1
        db.commit()
        print('ADMIN_MENU_MIGRATION=APPLIED; scope=admin:user,role,data-push,storage; remove=platform-upgrade; user=business-and-device-monitoring-read-only; changed=' + str(changed))
        return changed
    except Exception:
        db.rollback()
        raise


def main():
    config = configparser.ConfigParser(interpolation=None)
    config.read('/Seal_system/config.ini')
    settings = config['database']
    db = pymysql.connect(host=settings['DB_HOST'], port=int(settings.get('DB_PORT', 3306)),
                         user=settings['DB_USER'], password=settings['DB_PASSWORD'],
                         database=settings['DB_NAME'], charset='utf8mb4')
    try:
        migrate_admin_permissions(db)
    finally:
        db.close()


if __name__ == '__main__':
    main()
