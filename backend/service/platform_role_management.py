"""Role-menu normalization, atomic saves and built-in account protection."""
import ast
import json

from sqlalchemy import LargeBinary, cast
from data.exts import db
from model.admin import Menu, Permission, PermissionMenu, UserPermission


BUILTIN_SUPERADMIN_CODES = frozenset(('sysadmin', 'bootstrap_superadmin', 'bootstrap-admin'))


def _value(row, key):
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def protected_role(role):
    return _value(role, 'permission_code') in BUILTIN_SUPERADMIN_CODES


def protected_user(user):
    if _value(user, 'username') == 'sysadmin':
        return True
    rows = db.session.query(Permission.permission_code).join(UserPermission,
        cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)).filter(
        UserPermission.user_id == _value(user, 'id')).all()
    return any(row[0] in BUILTIN_SUPERADMIN_CODES for row in rows)


def positive_id(value):
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0:
        return int(value)
    raise ValueError('角色或菜单ID必须是正整数')


def role_actions(actions):
    if isinstance(actions, str):
        text = actions.strip()
        try:
            actions = json.loads(text)
        except ValueError:
            try:
                actions = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                if not (text.startswith('[') and text.endswith(']')):
                    raise ValueError('菜单操作权限格式错误')
                actions = [part.strip() for part in text[1:-1].split(',')] if text[1:-1].strip() else []
    if (not isinstance(actions, list) or
            any(type(action) is not str or action not in ('c', 'r', 'u', 'd') for action in actions)):
        raise ValueError('菜单操作只能包含c、r、u、d')
    return [action for action in 'crud' if action in actions]


def canonical_actions(value):
    return '[' + ','.join(role_actions(value)) + ']'


def normalize_role_menus(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError('菜单权限必须是列表')
    combined = {}
    for item in value:
        if not isinstance(item, dict) or not {'menu_id', 'permissions_list'}.issubset(item):
            raise ValueError('菜单权限字段不完整')
        menu_id = positive_id(item['menu_id'])
        actions = role_actions(item['permissions_list'])
        combined.setdefault(menu_id, set()).update(actions)
    # Preserve the original browser/menu reader's unquoted action-list format.
    return [{'menu_id': menu_id, 'permissions_list': '[' + ','.join(action for action in 'crud' if action in actions) + ']'}
            for menu_id, actions in sorted(combined.items()) if actions]


def replace_role_menus(permission_id, value):
    role_id = positive_id(permission_id)
    rows = normalize_role_menus(value)
    session = db.session
    try:
        role = session.query(Permission).filter(Permission.id == role_id).with_for_update().first()
        if role is None:
            raise ValueError('角色不存在')
        ids = {row['menu_id'] for row in rows}
        if ids:
            existing = {row[0] for row in session.query(Menu.id).filter(Menu.id.in_(ids)).all()}
            if ids != existing:
                raise ValueError('菜单不存在，请刷新后重新授权')
        session.query(PermissionMenu).filter(PermissionMenu.premission_id == role_id).delete(synchronize_session=False)
        session.add_all([PermissionMenu(premission_id=role_id, **row) for row in rows])
        session.commit()
    except Exception:
        session.rollback()
        raise
