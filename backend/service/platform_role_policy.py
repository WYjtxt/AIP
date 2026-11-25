"""Live role-code boundaries for management APIs and selectors."""
import json
from flask import g, has_request_context, request
from sqlalchemy import LargeBinary, cast, or_
from data.exts import db
from model.admin import Menu, Permission, PermissionMenu, UserPermission, User

SUPER_CODES = ('sysadmin', 'bootstrap_superadmin', 'bootstrap-admin')


def role_codes(user_id):
    rows = db.session.query(Permission.permission_code).join(UserPermission,
        cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)).filter(
        UserPermission.user_id == user_id, Permission.permission_status == '1').all()
    return {row[0] for row in rows}


def is_superadmin(user_id):
    return bool(role_codes(user_id).intersection(SUPER_CODES))


def is_admin(user_id):
    return 'admin' in role_codes(user_id)


def restricted_actor():
    user = getattr(g, 'platform_user', None) if has_request_context() else None
    return user is not None and not is_superadmin(user.id)


def visible_roles(query):
    if restricted_actor():
        query = query.filter(or_(Permission.permission_code.is_(None),
                                 ~Permission.permission_code.in_(SUPER_CODES)))
    return query


def protected_user_ids():
    return db.session.query(UserPermission.user_id).join(Permission,
        cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)).filter(
        Permission.permission_code.in_(SUPER_CODES)).correlate(None)


def visible_users(query):
    if restricted_actor():
        query = query.filter(~User.id.in_(protected_user_ids()), User.username != 'sysadmin')
    return query


def add_default_role_menus(role):
    if role.permission_code in SUPER_CODES or role.permission_code == 'admin':
        return
    # New ordinary roles start read-only. Existing grants are never rewritten.
    menus = db.session.query(Menu).filter(Menu.menu_status == '1').all()
    selected = {row.id for row in menus if row.id in (1, 6, 9, 14) and row.menu_parent_id is None}
    while True:
        expanded = selected | {row.id for row in menus if row.menu_parent_id in selected}
        if expanded == selected:
            break
        selected = expanded
    parents = {row.id: row.menu_parent_id for row in menus}
    for row in menus:
        if (row.menu_link or '').strip('/') == 'ygzx':
            menu_id = row.id
            while menu_id in parents and menu_id not in selected:
                selected.add(menu_id)
                menu_id = parents[menu_id]
    db.session.add_all([PermissionMenu(premission_id=role.id, menu_id=menu_id, permissions_list='[r]')
                        for menu_id in sorted(selected)])


def protected_role_id(value):
    return db.session.query(Permission.id).filter(
        Permission.id == str(value).strip(), Permission.permission_code.in_(SUPER_CODES)).first() is not None


def protected_user_id(value):
    return db.session.query(User.id).filter(User.id == str(value).strip(),
        or_(User.id.in_(protected_user_ids()), User.username == 'sysadmin')).first() is not None


def forbidden_management_request():
    """Runs after identity authentication, before any endpoint can write."""
    user = g.platform_user
    if is_superadmin(user.id):
        return False
    prefix, _, name = request.path.strip('/').partition('/')
    body = request.get_json(silent=True)
    values = body if isinstance(body, dict) else request.form
    if request.method in ('GET', 'HEAD'):
        values = request.args
    if prefix == 'platform_ops' and (name == 'upgrade' or name.startswith('upgrade/')):
        return True
    if prefix == 'role_view':
        if values.get('permission_id') and protected_role_id(values['permission_id']):
            return True
        if str(values.get('permission_code', '')).strip() in SUPER_CODES:
            return True
    if prefix in ('user_view', 'menu_view'):
        if values.get('user_id') and protected_user_id(values['user_id']):
            # Own password changes remain subject to the existing password check.
            if not (name == 'user_password_modification' and str(values['user_id']) == str(user.id)):
                return True
        if name in ('user_data_manage_add', 'user_data_manage_write', 'permission_give'):
            if str(values.get('username', '')).strip() == 'sysadmin':
                return True
            try:
                raw = values.get('permission_list_id', '[]')
                ids = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(ids, list):
                    return True
                if values.get('permission_id') is not None:
                    ids = ids + [values['permission_id']]
                if any(protected_role_id(value) for value in ids):
                    return True
            except (TypeError, ValueError):
                return True
    return False


def maintenance_allowed(operation):
    user = g.platform_user
    if is_superadmin(user.id):
        return True
    # Upgrade and unknown maintenance operations never inherit a general grant.
    owner = operation.split('/', 1)[0]
    if owner not in ('push', 'storage'):
        return False
    from common.platform_access import has_menu_permission
    link = 'data-push' if owner == 'push' else 'storage'
    action = 'r' if request.method in ('GET', 'HEAD') else 'u'
    return has_menu_permission(user.id, link, action)
