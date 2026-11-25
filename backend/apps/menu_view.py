from flask import jsonify,request, Blueprint,url_for
from config.configs import *
from service.menu_service import MenuService

# 创建蓝图，对应的register目录
menu_view = Blueprint('menu_view', __name__)


@menu_view.route('/menu_manage_select', methods=['GET'])
@jwt_required_with_refresh
def menu_manage_select():
    success, result = MenuService.menu_manage_select()
    if success:
        return jsonify({'code': 200, 'data': result})
    return jsonify({'code': 500, 'msg': result}), 500

# 权限赋值接口
@menu_view.route('/permission_give', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def permission_give():

    # 获取权限id 用户id  写入用户权限表 进行赋值
    user_id = request.form.get('user_id')
    permission_id = request.form.get('permission_id')

    # 调用服务层方法进行权限赋值
    success, message = MenuService.permission_give(user_id, permission_id)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 对应权限菜单展示接口
@menu_view.route('/menu_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def menu_show():

    # 获取用户id   查找该用户所拥有权限 1.超级管理员 2。普通用户
    user_id = request.args.get('user_id', None)

    # 调用服务层方法获取菜单列表
    success, result = MenuService.menu_show(user_id)

    if success:
        return jsonify({'code': 200, 'menu_list': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 菜单修改对应配置接口
@menu_view.route('/menu_manage_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def menu_manage_update():
    """
    菜单修改对应配置接口

    参数:
        status       状态 (str): 1目录， 2菜单 （选择目录parent_id就为none值，选择菜单，展示对应路径，parent_id有值）
        parent_id    修改菜单父id (str): 要更新的菜单父id。
        menu_id      修改菜单id (str): 要更新的菜单id。
        menu_name    菜单名称 (str): 更新的菜单名称。
        menu_link    菜单路径 (str): 更新的菜单路径。
        menu_order   菜单顺序 (str): 更新的菜单顺序。
        menu_icon    菜单图标 (str): 更新的菜单图标。
    """

    # 先判断状态，当为目录或者菜单时执行不同的逻辑
    status = strip_whitespace(request.form.get('status', None))
    menu_id = strip_whitespace(request.form.get('menu_id', None))
    menu_name = strip_whitespace(request.form.get('menu_name', None))
    menu_link = strip_whitespace(request.form.get('menu_link', None))
    menu_order = strip_whitespace(request.form.get('menu_order', None))
    menu_icon = strip_whitespace(request.form.get('menu_icon', None))
    menu_parent_id = strip_whitespace(request.form.get('menu_parent_id', None))
    menu_status = strip_whitespace(request.form.get('menu_status', None))

    # 调用服务层方法更新菜单
    success, message = MenuService.menu_manage_update(
        status, menu_id, menu_name, menu_link, menu_order, menu_icon, menu_parent_id, menu_status
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 菜单配置添加接口
@menu_view.route('/menu_manage_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def menu_manage_add():
    """
    菜单配置添加接口

    参数:
        status       状态 (str): 1目录， 2菜单 （选择目录parent_id就为none值，选择菜单，展示对应路径，parent_id有值）
        parent_id    菜单父id (str): 菜单父id。
        menu_id      菜单id (str): 菜单id。
        menu_name    菜单名称 (str): 菜单名称。
        menu_link    菜单路径 (str): 菜单路径。
        menu_order   菜单顺序 (str): 菜单顺序。
        menu_icon    菜单图标 (str): 菜单图标。
    """

    # 先判断状态，当为目录或者菜单时执行不同的逻辑
    status = strip_whitespace(request.form.get('status', None))
    menu_name = strip_whitespace(request.form.get('menu_name', None))
    menu_link = strip_whitespace(request.form.get('menu_link', None))
    menu_order = strip_whitespace(request.form.get('menu_order', None))
    menu_icon = strip_whitespace(request.form.get('menu_icon', None))
    menu_status = strip_whitespace(request.form.get('menu_status', 1))
    menu_parent_id = strip_whitespace(request.form.get('menu_parent_id', None))

    # 调用服务层方法添加菜单
    success, message = MenuService.menu_manage_add(
        status, menu_name, menu_link, menu_order, menu_icon, menu_status, menu_parent_id
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 菜单状态修改（菜单管理）
@menu_view.route('/menu_manage_status_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def menu_manage_status_update():
    # 菜单id
    menu_id = request.form.get('menu_id', None)
    # 菜单启用状态  1启用 0禁用
    menu_status = request.form.get('menu_status', 1)

    # 调用服务层方法更新菜单状态
    success, message = MenuService.menu_manage_status_update(menu_id, menu_status)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})


# 菜单删除（菜单管理）
@menu_view.route('/menu_manage_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def menu_manage_delete():
    """
    删除菜单数据

    参数:
        menu_id (str): 要删除的角色ID
    返回:
        json: 响应结果，包含状态码和消息
    """
    # 获取角色ID
    menu_list = request.form.get('menu_list', None)

    # 调用服务层方法删除菜单
    success, message = MenuService.menu_manage_delete(menu_list)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})
