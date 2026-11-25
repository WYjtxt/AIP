from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.user_view_service import UserViewService
from datetime import datetime
from common.platform_api_token import issue_api_token


# 创建蓝图，对应的register目录
user_view = Blueprint('user_view', __name__)


@user_view.route('/token', methods=['POST'])
def api_token():
    return issue_api_token()


@user_view.route('/login', methods=['GET', 'POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form if request.form else request.args
    username = data.get('username')
    password = data.get('password')
    captcha = data.get('captcha')

    # 调用服务层方法进行登录
    success, message, data = UserViewService.login(
        username, password, captcha, request.remote_addr, request.host, request.headers.get('User-Agent')
    )

    if success:
        return jsonify({
            'code': 200,
            'msg': message,
            **data
        })
    else:
        return jsonify({"msg": message, 'code': 400 if '验证码' in message or '空' in message else 401})


@user_view.route('/loginfree', methods=['GET'])
def loginfree():
    username = request.args.get('username', None)
    password = request.args.get('password', None)

    # 调用服务层方法进行免验证码登录
    success, message, data = UserViewService.loginfree(
        username, password, request.remote_addr, request.host, request.headers.get('User-Agent')
    )

    if success:
        return jsonify({
            'code': 200,
            'msg': message,
            **data
        })
    else:
        return jsonify({"msg": message, 'code': 400 if '禁用' in message or '空' in message else 401})


# token验证  如果失效 前端回退到登录页面
@user_view.route('/token_refresh', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def token_refresh():
    # 调用服务层方法刷新token
    success, message, data = UserViewService.token_refresh()

    if success:
        return jsonify(data)
    else:
        return jsonify({"msg": message, 'code': 400})


# token验证  如果失效 前端回退到登录页面
@user_view.route('/protected', methods=['GET', 'POST', 'DELETE', 'PUT', 'CATCH'])
# @jwt_required()
@jwt_required_with_refresh
def protected():
    # 调用服务层方法获取受保护的用户信息
    success, message, data = UserViewService.protected()

    if success:
        return jsonify({
            'code': 200,
            **data
        })
    else:
        return jsonify({"msg": message, 'code': 400})


# 用户注册接口
@user_view.route('/register', methods=['POST'])
def register():
    # 接受所传参数用户信息
    username = request.form.get('username', None)
    name = request.form.get('name', None)
    password = request.form.get('password', None)

    # 调用服务层方法进行注册
    success, message = UserViewService.register(username, password, name)

    if success:
        return jsonify({
            'code': 200,
            'msg': message,
        })
    else:
        return jsonify({
            'code': 400,
            'msg': message
        })


# 用户信息展示接口（用户管理）
@user_view.route('/user_data_manage', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage():
    name = request.args.get('name', None)
    username = request.args.get('username', None)
    user_status = request.args.get('user_status', 1)

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=15, type=int)

    # 调用服务层方法获取用户列表
    success, message, data = UserViewService.get_users(page, per_page, name, username, user_status)

    if success:
        return jsonify({
            'code': 200,
            **data
        })
    else:
        return jsonify({
            'code': 400,
            'msg': message
        })


# 用户信息添加接口（用户管理）
@user_view.route('/user_data_manage_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage_add():
    """
    用户信息添加接口
    """

    # 获取请求参数
    name = request.form.get('name', None)
    username = request.form.get('username', None)
    password = request.form.get('password', None)
    email = request.form.get('email', None)
    permission_list_id = request.form.get('permission_list_id', '[]')

    # 调用服务层方法添加用户
    success, message = UserViewService.add_user(name, username, password, email, permission_list_id)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 用户信息修改接口（用户管理）
@user_view.route('/user_data_manage_write', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage_write():
    """
    用户信息修改接口
    """

    # 获取请求参数
    user_id = request.form.get('user_id', None)
    name = request.form.get('name', None)
    username = request.form.get('username', None)
    email = request.form.get('email', None)
    permission_list_id = request.form.get('permission_list_id', '[]')

    # 调用服务层方法更新用户信息
    success, message = UserViewService.update_user(user_id, name, username, email, permission_list_id)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 用户密码修改接口（用户管理）
@user_view.route('/user_password_modification', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def user_password_modification():
    """
    用户密码修改接口
    """

    # 获取请求参数
    user_id = request.form.get('user_id', None)
    current_password = request.form.get('current_password', None)
    new_password = request.form.get('new_password', None)
    password_confirm = request.form.get('password_confirm', None)

    # 调用服务层方法修改用户密码
    success, message = UserViewService.update_user_password(user_id, current_password, new_password, password_confirm)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 用户启用状态修改接口（用户管理）
@user_view.route('/user_data_manage_status_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage_status_update():
    # 用户启用状态  1启用 2禁用
    status = request.form.get('user_status', 1)
    # 用户id
    user_id = request.form.get('user_id', None)

    # 调用服务层方法更新用户状态
    success, message = UserViewService.update_user_status(user_id, status)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})


# 用户信息详情获取（用户管理）
@user_view.route('/user_data_manage_detile', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage_detile():

    # 用户id
    user_id = request.args.get('user_id', None)
    # 第几页
    page = request.args.get('page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=15, type=int)

    # 调用服务层方法获取用户详情
    success, message, data = UserViewService.get_user_detail(user_id, page, per_page)

    if success:
        return jsonify({'code': 200, 'data': data, 'msg': '查询成功'})
    else:
        return jsonify({'code': 400, 'msg': message})


# 权限相关筛选接口
@user_view.route('/permission_menu_select', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def permission_menu_select():
    # 调用服务层方法获取权限和菜单列表
    success, message, data = UserViewService.get_permission_menu()

    if success:
        return jsonify({'code': 200, 'data': data})
    else:
        return jsonify({'code': 400, 'msg': message})


# 用户删除（用户管理）
@user_view.route('/user_data_manage_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def user_data_manage_delete():
    """
    删除用户数据

    参数:
        user_id (str): 要删除的用户ID
    返回:
        json: 响应结果，包含状态码和消息
    """
    # 获取用户ID
    user_id = request.form.get('user_id', None)

    # 调用服务层方法删除用户
    success, message = UserViewService.delete_user(user_id)

    if success:
        return jsonify({'code': 200, 'message': message})
    else:
        return jsonify({'code': 400, 'message': message})



# @user_view.route('/captcha_verify', methods=['POST'])
# def verify():
#     user_input = request.form.get('captcha')
#     correct_captcha = session.get('captcha')
#
#     if user_input and user_input.upper() == correct_captcha:
#         return '验证码验证成功！'
#     else:
#         return '验证码验证失败，请重试。'
