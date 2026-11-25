# native-five-module-crud-v1

FIVE_MODULE_PERMISSIONS = {
    'model_view': {
        'equipment_create': ('sbtj', 'c'),
        'equipment_delete': ('sbtj', 'd'),
        'VCR_data_sync': ('sbtb', 'c'),
        'CVR_data_sync': ('spcctb', 'c'),
        'manual_sync': ('sbtb', 'u'),
        'VCR_data_delete': ('sbtb', 'd'),
        'mine_insert': ('sbtj', 'c'),
        'mine_update': ('sbtj', 'u'),
        'mine_delete': ('sbtj', 'd'),
    },
    'scheduler_task': {
        'add_task': ('spzlzdpz', 'c'),
        'update_task': ('spzlzdpz', 'u'),
        'delete_task': ('spzlzdpz', 'd'),
        'show_task': ('spzlzdpz', 'r'),
        'task_detail': ('spzlzdpz', 'r'),
    },
    'model_views': {
        'diagnosis_all': ('spzlzd', 'r'),
        'diagnosis_reference': ('spzlzd', 'u'),
    },
    'hik_security_platform_info_view': {
        'hik_security_platform_add': ('hkaf_sbtb', 'c'),
        'hik_security_platform_delete': ('hkaf_sbtb', 'd'),
    },
    'ziguang_platform_info_view': {
        'ziguang_platform_add': ('zghzpttb', 'c'),
        'ziguang_security_platform_delete': ('zghzpttb', 'd'),
    },
    'resource_view': {
        'computing_insert': ('slsbzx', 'c'),
        'computing_update': ('slsbzx', 'u'),
        'computing_delete': ('slsbzx', 'd'),
        'algorithm_metadata': ('sfgl', 'u'),
    },
    'ai_camera_view': {
        'algorithm_add': ('sxtpz', 'c'),
        'algorithm_add_models': ('sxtpz', 'c'),
        'algorithm_update': ('sxtpz', 'u'),
        'algorithm_update_models': ('sxtpz', 'u'),
        'algorithm_conf_update': ('sxtpz', 'u'),
        'algorithm_data_delete': ('sxtpz', 'd'),
        'algorithm_upload_aicam': ('sxtsf', 'c'),
        'algorithm_upload_sub_aicam': ('sxtsf', 'c'),
        'algorithm_deploy_aicam': ('sxtsf', 'u'),
        'algorithm_data_update': ('sxtsf', 'u'),
        'algorithm_library_delete_aicam': ('sxtsf', 'd'),
        'algorithm_sync_aicam': ('sxtpz', 'u'),
        'image_calibration': ('sxtpz', 'u'),
        'algorithm_result_callback': ('sxtpz', 'u'),
        'model_status_callback': ('sxtpz', 'u'),
        'algorithm_config_add_callback': ('sxtpz', 'c'),
        'algorithm_config_update_callback': ('sxtpz', 'u'),
        'algorithm_config_del_callback': ('sxtpz', 'd'),
        'config_statusup_callback': ('sxtpz', 'u'),
        'algorithm_config_add_models_callback': ('sxtpz', 'c'),
        'algorithm_config_update_models_callback': ('sxtpz', 'u'),
    },
}

# native-role-policy-v1
from service.platform_role_policy import is_superadmin, forbidden_management_request
# native-role-management-v1
"""Default authentication and explicit menu/action checks for browser APIs.

Existing account/role/menu tables remain the source of authorization.  An
unknown management route or missing menu/action grant is never an allow rule.
"""
import ast
import json

from flask import g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import LargeBinary, cast

from common.platform_auth import enabled_platform_user
from data.exts import db
from model.admin import Menu, Permission, PermissionMenu, UserPermission


# Only these bootstrap or password-verifying routes are public. The QR image
# contains the machine request identifier only, so a new device can request
# activation before login. The separate first-import endpoints enforce state,
# origin, session challenge and license checks themselves. License contents,
# issuance and the existing authenticated upload remain protected.
PUBLIC_ROUTES = {
    '/user_view/token': frozenset(('POST',)),
    '/user_view/login': frozenset(('GET', 'POST')),
    '/user_view/loginfree': frozenset(('GET',)),
    '/captcha': frozenset(('GET',)),
    '/uuid_qr': frozenset(('GET',)),
    '/activate/activate_verify': frozenset(('GET',)),
    '/activate/bootstrap': frozenset(('GET',)),
    '/activate/bootstrap_upload': frozenset(('POST',)),
}


TEMPLATE_PERMISSIONS = {
    'model_type_template_show': ('modelbig', 'r'),
    'model_type_template_detail': ('modelbig', 'r'),
    'model_type_template_add': ('modelbig', 'c'),
    'model_type_template_update': ('modelbig', 'u'),
    'model_type_template_delete': ('modelbig', 'd'),
    'model_template_show': ('modellist', 'r'),
    'model_template_detail': ('modellist', 'r'),
    'model_template_add': ('modellist', 'c'),
    'model_template_update': ('modellist', 'u'),
    'model_template_delete': ('modellist', 'd'),
    'model_template_small_show': ('modelsmall', 'r'),
    'model_small_detail': ('modelsmall', 'r'),
    'model_template_small_add': ('modelsmall', 'c'),
    'model_template_small_update': ('modelsmall', 'u'),
    'model_template_small_delete': ('modelsmall', 'd'),
    # The production warning-message routes are retained.  Their menu link
    # must exist and be explicitly granted; a missing menu fails closed.
    'model_warnmessage_show': ('modelwarning', 'r'),
    'model_warn_maessage_add': ('modelwarning', 'c'),
    'model_warn_maessage_update': ('modelwarning', 'u'),
    'model_warning_message_delete': ('modelwarning', 'd'),
}

USER_PERMISSIONS = {
    'register': ('user', 'c'),
    'user_data_manage': ('user', 'r'),
    'user_data_manage_add': ('user', 'c'),
    'user_data_manage_write': ('user', 'u'),
    'user_password_modification': ('user', 'u'),
    'user_data_manage_status_update': ('user', 'u'),
    'user_data_manage_detail': ('user', 'r'),
    'user_data_manage_detile': ('user', 'r'),
    # permission_menu_select is a shared read catalog, checked below.
    'user_data_manage_delete': ('user', 'd'),
}

ROLE_PERMISSIONS = {
    'permission_manage_data': ('role', 'r'),
    'permission_manage_select': ('role', 'r'),
    'permission_manage_add': ('role', 'c'),
    'permission_manage_info_update': ('role', 'u'),
    'permission_manage_update': ('role', 'u'),
    'permission_manage_status_update': ('role', 'u'),
    'permission_manage_delete': ('role', 'd'),
}

MENU_PERMISSIONS = {
    'menu_manage_select': ('menu', 'r'),
    'permission_give': ('user', 'u'),
    'menu_manage_update': ('menu', 'u'),
    'menu_manage_add': ('menu', 'c'),
    'menu_manage_status_update': ('menu', 'u'),
    'menu_manage_delete': ('menu', 'd'),
}

MEDIA_MANAGEMENT_PERMISSIONS = {
    'recovery/status': ('lmtgl', 'r'),
    'addStreamProxy': ('lmtgl', 'c'),
    'delStreamProxy': ('lmtgl', 'd'),
    'restartServer': ('lmtgl', 'u'),
    'kick_session': ('lmtgl', 'u'),
    'stream/list': ('lmtgl', 'r'),
    'getMediaList': ('lmtgl', 'r'),
    'getMediaPlayerList': ('lmtgl', 'r'),
    'listStreamProxy': ('lmtgl', 'r'),
    'getServerConfig': ('lmtgl', 'r'),
    'getWorkThreadsLoad': ('lmtgl', 'r'),
    'getStatistic': ('lmtgl', 'r'),
    'getAllSession': ('lmtgl', 'r'),
    'version': ('lmtgl', 'r'),
}

# Algorithm installation and task configuration have distinct menu owners.
# Shared read selectors accept grants from their existing consuming pages.
ALGORITHM_PERMISSIONS = {
    'algorithm_upload': ('sfc', 'c'),
    'algorithm_upload_sub': ('sfc', 'c'),
    'algorithm_library_delete': ('sfc', 'd'),
    'algorithm_data_update': ('sfc', 'u'),
    'algorithm_data': ('sfc', 'r'),
    'algorithm_add': ('sfgl', 'c'),
    'algorithm_add_models': ('sfgl', 'c'),
    'algorithm_update': ('sfgl', 'u'),
    'algorithm_update_models': ('sfgl', 'u'),
    'algorithm_data_delete': ('sfgl', 'd'),
    'algorithm_conf_update': ('sfgl', 'u'),
    'algorithm_conf_batch_update': ('sfgl', 'u'),
    'algorithm_history_show': ('sfgl', 'r'),
    'algorithm_config_history': ('sfgl', 'r'),
    'algorithm_result': ('bjlb', 'r'),
    'algorithm_result_sqlalchemy': ('bjlb', 'r'),
    'algorithm_result_manage': ('bjlb', 'u'),
    'alg_result_delete': ('bjlb', 'd'),
    'algorithm_ratio': ('bjtj', 'r'),
}
ALGORITHM_SHARED_READS = frozenset((
    'Algorithm_type_select', 'algorithm_data_show', 'algorithm_status',
    'config_name_check', 'type_select', 'image_show', 'algo_result_pop',
))


def permission_actions(value):
    """Read JSON, legacy quoted lists, or the model's [c,r,u,d] default safely."""
    if isinstance(value, str):
        text = value.strip()
        try:
            value = json.loads(text)
        except ValueError:
            try:
                value = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                # Historic SQLAlchemy defaults omit quotes around c/r/u/d.
                if not (text.startswith('[') and text.endswith(']')):
                    return frozenset()
                value = [part.strip() for part in text[1:-1].split(',')]
    if not isinstance(value, list) or any(type(item) is not str or item not in 'crud'
                                         or len(item) != 1 for item in value):
        return frozenset()
    return frozenset(value)


def has_menu_permission(user_id, menu_link, action):
    if is_superadmin(user_id):
        return True
    if action not in ('c', 'r', 'u', 'd'):
        return False
    rows = db.session.query(PermissionMenu.permissions_list).select_from(PermissionMenu).join(
        Permission, Permission.id == PermissionMenu.premission_id
    ).join(
        UserPermission, cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)
    ).join(
        Menu, Menu.id == PermissionMenu.menu_id
    ).filter(
        UserPermission.user_id == user_id,
        Permission.permission_status == '1',
        Menu.menu_status == '1',
        Menu.menu_link.in_((menu_link, '/' + menu_link)),
    ).all()
    return any(action in permission_actions(row.permissions_list) for row in rows)


def _payload():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else request.form


def _own_user(value, user):
    return type(value) in (str, int) and str(value) == str(user.id)


def _route_permission(user):
    """Return (menu link, action), None for identity only, False to deny."""
    prefix, _, name = request.path.strip('/').partition('/')
    if prefix == 'model_view' and name == 'equipment_update':
        # This legacy POST also serves the edit form's read query.
        try:
            mode = int(request.form.get('type'))
        except (TypeError, ValueError):
            return False
        return ('sbtj', 'r' if mode == 1 else 'u')
    if prefix == 'model_view' and name == 'VCR_data_update':
        # This legacy GET mutates only when type_st is 2.
        try:
            mode = int(request.args.get('type_st'))
        except (TypeError, ValueError):
            return False
        return ('sbtb', 'u' if mode == 2 else 'r')
    if name in FIVE_MODULE_PERMISSIONS.get(prefix, {}):
        return FIVE_MODULE_PERMISSIONS[prefix][name]
    if prefix == 'model_view':
        if name in ALGORITHM_PERMISSIONS:
            return ALGORITHM_PERMISSIONS[name]
        if name in ALGORITHM_SHARED_READS:
            # Existing selectors serve the configuration/analysis/alarm pages.
            # config_name_check historically uses POST but is strictly read-only.
            allowed_methods = ('POST',) if name == 'config_name_check' else ('GET', 'HEAD')
            if request.method not in allowed_methods:
                return False
            return None if any(has_menu_permission(user.id, link, 'r') for link in (
                'sfgl', 'sfc', 'spfx', 'bjlb', 'bjtj', 'sbtj', 'sbtb', 'spcctb',
                'jsyl', 'sxtsf', 'sxtpz', 'spzlzdpz', 'spzlzd', 'ygzx')) else False
        if name.startswith(('algorithm_', 'alg_')):
            return False
        return None  # Unrelated device/catalog routes retain their existing policy.
    if prefix == 'model_template':
        return TEMPLATE_PERMISSIONS.get(name, False)
    if prefix == 'role_view':
        return ROLE_PERMISSIONS.get(name, False)
    if prefix == 'zlmediakit_view':
        if name.startswith('stream/play/') and name[len('stream/play/'):]:
            return ('lmtgl', 'r')
        return MEDIA_MANAGEMENT_PERMISSIONS.get(name, False)
    if prefix == 'menu_view':
        if name == 'menu_show':
            return None if _own_user(request.args.get('user_id'), user) else ('user', 'r')
        return MENU_PERMISSIONS.get(name, False)
    if prefix == 'user_view':
        if name in ('token_refresh', 'protected'):
            return None
        if name == 'permission_menu_select':
            # This read-only catalog is shared by user, role and menu forms.
            # Require an enabled read grant on one of those owning modules.
            if request.method not in ('GET', 'HEAD'):
                return False
            return None if any(has_menu_permission(user.id, link, 'r')
                               for link in ('user', 'role', 'menu')) else False
        if name == 'user_password_modification' and _own_user(_payload().get('user_id'), user):
            return None
        return USER_PERMISSIONS.get(name, False)
    return None


def _valid_role_menu_update():
    from service.platform_role_management import normalize_role_menus
    try:
        normalize_role_menus(_payload().get('permissions_list'))
        return True
    except (TypeError, ValueError):
        return False


def install_platform_access(app):
    if app.extensions.get('platform_access_installed'):
        return
    app.extensions['platform_access_installed'] = True

    @app.before_request
    def platform_access():
        if request.endpoint is None:
            return None
        if (request.method == 'OPTIONS' and request.url_rule is not None
                and request.url_rule.provide_automatic_options):
            return None
        # These two endpoints verify their respective media grants themselves.
        if request.endpoint in ('platform_security.media_access', 'platform_security.recipient_media_access'):
            return None
        if request.endpoint == 'platform_security.media_session' and request.method == 'DELETE':
            return None
        if request.method in PUBLIC_ROUTES.get(request.path, ()):
            return None
        verify_jwt_in_request(locations=['headers'])
        user, message = enabled_platform_user(get_jwt_identity())
        if user is None:
            return jsonify({'code': 401, 'msg': message}), 401
        g.platform_user = user
        if forbidden_management_request():
            return jsonify({'code': 403, 'msg': '当前账号不能管理超级管理员或执行平台升级'}), 403
        policy = _route_permission(user)
        if policy is False or (policy is not None and not has_menu_permission(user.id, *policy)):
            return jsonify({'code': 403, 'msg': '当前账号没有此操作的权限'}), 403
        if request.path == '/role_view/permission_manage_update' and not _valid_role_menu_update():
            return jsonify({'code': 400, 'msg': '菜单权限必须是合法的菜单ID和增删改查标识列表'}), 400
        return None

# algorithm-first-access-v3
_algorithm_first_original_route_permission = _route_permission
def _route_permission(user):
    path = request.path.strip('/')
    prefix = 'model_view/algorithm_first/'
    if not path.startswith(prefix):
        return _algorithm_first_original_route_permission(user)
    operation = path[len(prefix):]
    if operation in ('catalog', 'cameras', 'options', 'task-context', 'resource-default') and request.method in ('GET', 'HEAD'):
        return ('sfgl', 'r')
    if operation in ('preview', 'create') and request.method == 'POST':
        return ('sfgl', 'c')
    if operation.startswith('jobs/') and operation.endswith('/start'):
        import re
        if re.fullmatch('[a-f0-9]{32}/start', operation[len('jobs/'):]):
            if request.method in ('GET', 'HEAD'):
                return ('sfgl', 'r')
            if request.method == 'POST':
                return ('sfgl', 'u')
        return False
    if operation.startswith('jobs/') and request.method in ('GET', 'HEAD'):
        import re
        if re.fullmatch('[a-f0-9]{32}', operation[len('jobs/'):]):
            return ('sfgl', 'r')
    return False
