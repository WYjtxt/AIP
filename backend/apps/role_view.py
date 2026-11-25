from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.role_view_service import RoleViewService


# 创建蓝图，对应的register目录
role_view = Blueprint('role_view', __name__)


# 角色信息获取（角色管理）
@role_view.route('/permission_manage_data', methods=['GET'])
@jwt_required()
def permission_manage_data():
    # 第几页
    page = request.args.get('page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=15, type=int)

    # 调用服务层方法获取角色权限数据
    success, result = RoleViewService.get_permission_data(page, per_page)

    if success:
        return jsonify({'code': 200, 'data': result, 'msg': '查询成功'})
    else:
        return jsonify({'code': 400, 'msg': result})


# 角色状态修改（角色管理）
@role_view.route('/permission_manage_status_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_status_update():
    # 角色id
    permission_id = request.form.get('permission_id', None)
    # 角色启用状态  1启用 2禁用
    permission_status = request.form.get('permission_status', 1)

    # 调用服务层方法更新角色状态
    success, message = RoleViewService.update_permission_status(permission_id, permission_status)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})


@role_view.route('permission_manage_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_delete():
    """
    删除角色及其对应权限数据

    参数:
        permission_id (str): 要删除的角色ID
    返回:
        json: 响应结果，包含状态码和消息
    """
    # 获取角色ID
    permission_id = request.form.get('permission_id', None)

    # 调用服务层方法删除角色
    success, message = RoleViewService.delete_permission(permission_id)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})


# 角色相关菜单筛选接口
@role_view.route('/permission_manage_select', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_select():

    # 角色id
    permission_id = request.args.get('permission_id', None)

    # 调用服务层方法获取角色菜单权限
    success, result = RoleViewService.get_permission_menu(permission_id)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'message': result})


# 角色相关菜单权限修改接口（角色管理）
@role_view.route('/permission_manage_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_update():
    """
    更新权限标识列表数据，先删除对应权限的所有数据，然后再批量新增。

    参数:
        permission_id (int): 要更新的权限 ID。
        menu_permissions_list (str): 权限标识列表（字符串格式，需要通过 eval 转换为列表）。
    """

    # 获取角色ID
    permission_id = request.form.get('permission_id', None)

    # 获取权限对应菜单及增删改查标识列表
    menu_permissions_list = request.form.get('permissions_list', '[]')

    # 调用服务层方法更新角色菜单权限
    success, message = RoleViewService.update_permission_menu(permission_id, menu_permissions_list)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 角色信息添加接口（角色管理）
@role_view.route('/permission_manage_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_add():
    """
    角色信息添加接口

    参数:
        permission_name (str): 要新增的角色名称。
        permission_content (str): 要新增的角色描述。
        permission_code (str): 要新增的角色标识。
        permission_status (str): 要新增的角色状态 1启用 0禁用。
    """

    permission_name = strip_whitespace(request.form.get('permission_name', None))
    permission_content = strip_whitespace(request.form.get('permission_content', None))
    permission_code = strip_whitespace(request.form.get('permission_code', None))
    permission_status = strip_whitespace(request.form.get('permission_status', 1))

    # 调用服务层方法添加角色
    success, message = RoleViewService.add_permission(
        permission_name, permission_content, permission_code, permission_status
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 角色信息修改接口（角色管理）
@role_view.route('/permission_manage_info_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_manage_info_update():
    """
    角色信息修改接口

    参数:
        permission_id (str): permission_id。
        permission_name (str): 要更新的角色名称。
        permission_content (str): 要更新的角色描述。
        permission_code (str): 要更新的角色标识。
        permission_status (str): 要更新的角色状态 1启用 0禁用。
    """

    permission_id = strip_whitespace(request.form.get('permission_id', None))
    permission_name = strip_whitespace(request.form.get('permission_name', None))
    permission_content = strip_whitespace(request.form.get('permission_content', None))
    permission_code = strip_whitespace(request.form.get('permission_code', None))
    permission_status = strip_whitespace(request.form.get('permission_status', 1))

    # 调用服务层方法更新角色信息
    success, message = RoleViewService.update_permission_info(
        permission_id, permission_name, permission_content, permission_code, permission_status
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})
