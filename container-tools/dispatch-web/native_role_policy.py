"""Apply the small role hierarchy policy without changing account data."""
import ast
from pathlib import Path
import textwrap

try:
    from .native_backend_fixes import _source_node_end
except ImportError:
    from native_backend_fixes import _source_node_end


ROLE_POLICY = '''"""Live role-code boundaries for management APIs and selectors."""
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
'''


FIVE_MODULE_ROUTES = '''
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
'''


def _replace_function(source, name, replacement, owner=None):
    tree = ast.parse(source)
    nodes = tree.body if owner is None else next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner).body
    node = next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name)
    start = min([node.lineno] + [item.lineno for item in node.decorator_list]) - 1
    lines = source.splitlines(keepends=True)
    lines[start:_source_node_end(tree, node, lines)] = [textwrap.indent(textwrap.dedent(replacement).strip(), '    ' if owner else '') + '\n']
    return ''.join(lines)


def patch_native_role_policy(root):
    """Accept either original or v1 backend sources; never migrate live data."""
    try:
        from .native_backend_fixes import patch_native_role_management, patch_native_user_capabilities
    except ImportError:
        from native_backend_fixes import patch_native_role_management, patch_native_user_capabilities
    prerequisite_changes = patch_native_role_management(root) + patch_native_user_capabilities(root)
    backend = Path(root) / 'backend'
    marker = '# native-role-policy-v1'
    outputs = {backend / 'service/platform_role_policy.py': ROLE_POLICY}

    def edit(relative, apply):
        path = backend / relative
        source = path.read_text(encoding='utf-8')
        if marker not in source:
            source = marker + '\n' + apply(source)
        outputs[path] = source

    def role_data(source):
        source = 'from service.platform_role_policy import visible_roles, add_default_role_menus\n' + source
        source = source.replace('db.session.query(Permission).paginate(',
                              'visible_roles(db.session.query(Permission)).paginate(', 1)
        source = source.replace('        db.session.add(new_permission)\n        db.session.commit()',
            '        db.session.add(new_permission)\n        db.session.flush()\n'
            '        add_default_role_menus(new_permission)\n        db.session.commit()', 1)
        return source
    edit('data/role_view_data.py', role_data)

    def user_data(source):
        source = 'from service.platform_role_policy import visible_users, visible_roles\n' + source
        source = source.replace('return query.paginate(', 'return visible_users(query).paginate(', 1)
        source = source.replace('return db.session.query(Permission).all()',
                                'return visible_roles(db.session.query(Permission)).all()', 1)
        return source
    edit('data/user_view_data.py', user_data)

    def menu_service(source):
        source = 'from service.platform_role_policy import restricted_actor\n' + source
        return source.replace('            # 组装数据，把多个权限对应增删改查列表进行组合',
            '            if restricted_actor():\n'
            '                menu_list = [item for item in menu_list if str(item.get(\'menu_link\') or \'\').strip(\'/\') != \'platform-upgrade\']\n\n'
            '            # 组装数据，把多个权限对应增删改查列表进行组合', 1)
    edit('service/menu_service.py', menu_service)

    def five_routes(source):
        if '# native-five-module-crud-v1' in source:
            return source
        source = '# native-five-module-crud-v1\n' + FIVE_MODULE_ROUTES + '\n' + source
        anchor = "    prefix, _, name = request.path.strip('/').partition('/')\n"
        source = source.replace(anchor, anchor +
            "    if prefix == 'model_view' and name == 'equipment_update':\n"
            "        # This legacy POST also serves the edit form's read query.\n"
            "        try:\n"
            "            mode = int(request.form.get('type'))\n"
            "        except (TypeError, ValueError):\n"
            "            return False\n"
            "        return ('sbtj', 'r' if mode == 1 else 'u')\n"
            "    if prefix == 'model_view' and name == 'VCR_data_update':\n"
            "        # This legacy GET mutates only when type_st is 2.\n"
            "        try:\n"
            "            mode = int(request.args.get('type_st'))\n"
            "        except (TypeError, ValueError):\n"
            "            return False\n"
            "        return ('sbtb', 'u' if mode == 2 else 'r')\n"
            "    if name in FIVE_MODULE_PERMISSIONS.get(prefix, {}):\n"
            "        return FIVE_MODULE_PERMISSIONS[prefix][name]\n", 1)
        return source

    def access(source):
        source = 'from service.platform_role_policy import is_superadmin, forbidden_management_request\n' + source
        source = source.replace("    'user_data_manage_detile': ('user', 'r'),\n", '')
        source = source.replace("    'user_data_manage_detail': ('user', 'r'),",
            "    'user_data_manage_detail': ('user', 'r'),\n    'user_data_manage_detile': ('user', 'r'),", 1)
        source = source.replace('    if action not in (\'c\', \'r\', \'u\', \'d\'):',
            "    if is_superadmin(user_id):\n        return True\n    if action not in ('c', 'r', 'u', 'd'):", 1)
        source = source.replace('        g.platform_user = user\n',
            "        g.platform_user = user\n        if forbidden_management_request():\n"
            "            return jsonify({'code': 403, 'msg': '当前账号不能管理超级管理员或执行平台升级'}), 403\n", 1)
        return source
    edit('common/platform_access.py', access)
    access_path = backend / 'common/platform_access.py'
    outputs[access_path] = five_routes(outputs[access_path])

    def capabilities(source):
        source = 'from service.platform_role_policy import is_admin, is_superadmin\n' + source
        source = source.replace("'is_superadmin': _platform_is_superadmin(user_info.id),",
            "'is_superadmin': is_superadmin(user_info.id),\n                    'is_admin': is_admin(user_info.id),")
        return source
    edit('service/user_view_service.py', capabilities)

    def admin_policy(source):
        return _replace_function(source, 'is_administrator', '''
            def is_administrator(user_id):
                from service.platform_role_policy import is_superadmin
                return is_superadmin(user_id)
        ''')
    edit('service/resource_admission_settings_api.py', admin_policy)

    def ops(source):
        source = _replace_function(source, '_admin', '''
            def _admin(operation):
                from service.platform_role_policy import maintenance_allowed
                return maintenance_allowed(operation)
        ''')
        return source.replace('if not _admin():', 'if not _admin(operation):', 1).replace(
            '只有超级管理员可管理平台维护设置', '当前账号没有此维护操作的权限')
    edit('apps/platform_ops_view.py', ops)

    def storage(source):
        source = _replace_function(source, '_can_edit_settings', '''
            def _can_edit_settings():
                from flask import g
                from common.platform_access import has_menu_permission
                return has_menu_permission(g.platform_user.id, 'storage', 'u')
        ''')
        # Read grant is enough to open settings; can_edit still reflects u.
        source = source.replace('    if not can_edit:\n',
            "    from flask import g\n    from common.platform_access import has_menu_permission\n"
            "    if not can_edit and (request.method == 'POST' or not has_menu_permission(g.platform_user.id, 'storage', 'r')):\n", 1)
        return source.replace('只有超级管理员可查看和修改存储设置', '当前账号没有存储设置操作权限').replace(
            '只有超级管理员可预估或清理报警存储', '当前账号没有存储清理操作权限')
    edit('apps/storage_retention_view.py', storage)
    for path, source in outputs.items():
        compile(source, str(path), 'exec')
    changed = []
    for path, source in outputs.items():
        if not path.is_file() or path.read_text(encoding='utf-8') != source:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(source)
            changed.append(path.relative_to(backend).as_posix())
    return list(dict.fromkeys(prerequisite_changes + changed))
