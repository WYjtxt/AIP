"""Shared account checks for the platform's existing Bearer JWT login."""
from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import LargeBinary, cast

from data.exts import db
from model.admin import Permission, User, UserPermission


def enabled_platform_user(identity):
    """Resolve an enabled user with at least one enabled, associated role.

    Role IDs are stored as text in t_user_permission. Compare their bytes
    rather than letting MySQL coerce a malformed value to an integer ID or
    compare text using different deployment-specific column collations.
    Account/role state is read on every request so disabling access also
    rejects access tokens that have not expired yet.
    """
    if not isinstance(identity, str) or not identity:
        return None, '登录用户无效，请重新登录！'
    user = db.session.query(User).filter(User.username == identity).first()
    if user is None:
        return None, '用户不存在，请重新登录！'
    if user.user_status != '1':
        return None, '账号已禁用，请联系管理员！'
    role = db.session.query(Permission.id).join(
        UserPermission, cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)
    ).filter(
        UserPermission.user_id == user.id,
        Permission.permission_status == '1',
    ).first()
    if role is None:
        return None, '账号没有启用的角色，请联系管理员！'
    return user, None


def platform_jwt_required(fn):
    """Require a signed Bearer JWT and current account/role eligibility."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request(locations=['headers'])
        user, message = enabled_platform_user(get_jwt_identity())
        if user is None:
            return jsonify({'code': 401, 'msg': message}), 401
        g.platform_user = user
        return fn(*args, **kwargs)
    return wrapper
