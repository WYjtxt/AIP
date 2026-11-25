# native-role-policy-v1
from service.platform_role_policy import is_admin, is_superadmin
# native-role-management-v1
from service.platform_role_management import protected_user
# native-user-capabilities-v1
from data.user_view_data import UserViewData
from flask_jwt_extended import create_access_token, get_jwt_identity
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from config.configs import *
from common.platform_auth import enabled_platform_user
from common.platform_captcha import consume_captcha
import json


# 登录限流参数
LOGIN_MAX_FAIL = 5          # 5 次失败
LOGIN_WINDOW_SEC = 300      # 窗口 5 分钟
LOGIN_LOCK_SEC = 300        # 锁定 5 分钟


def _login_rate_check(remote_addr, username):
    """返回 (是否允许, 错误消息)。被锁时拒绝。"""
    if not remote_addr:
        return True, None
    lock_key = f"login:locked:{remote_addr}"
    if redis_client.exists(lock_key):
        ttl = redis_client.ttl(lock_key)
        return False, f"登录失败次数过多，请 {ttl} 秒后再试。"
    return True, None


def _login_rate_record_fail(remote_addr, username):
    if not remote_addr:
        return
    fail_key = f"login:fail:{remote_addr}"
    pipe = redis_client.pipeline()
    pipe.incr(fail_key)
    pipe.expire(fail_key, LOGIN_WINDOW_SEC)
    results = pipe.execute()
    count = results[0]
    if count >= LOGIN_MAX_FAIL:
        redis_client.setex(f"login:locked:{remote_addr}", LOGIN_LOCK_SEC, "1")
        redis_client.delete(fail_key)


def _login_rate_clear(remote_addr):
    if remote_addr:
        redis_client.delete(f"login:fail:{remote_addr}", f"login:locked:{remote_addr}")


def _permission_ids(value):
    """Accept only a JSON/native list of positive integer role IDs."""
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or any(type(item) is not int or item <= 0 for item in value):
        raise ValueError('权限ID必须是正整数列表')
    return set(value)


class UserViewService:
    # 用户登录相关业务逻辑
    @staticmethod
    def login(username, password, captcha=None, remote_addr=None, host=None, user_agent=None):
        """
        用户登录
        """
        # 限流检查
        allowed, msg = _login_rate_check(remote_addr, username)
        if not allowed:
            return False, msg, None
        try:
            # 每浏览器独立且只可消费一次，不再使用全局 captcha:default。
            if not consume_captcha(redis_client, captcha):
                _login_rate_record_fail(remote_addr, username)
                return False, "验证码错误，请刷新后重试。", None

            # 去除用户名和密码中的首尾空格
            username = username.strip() if username else None
            password = password.strip() if password else None

            if username is None or password is None:
                return False, "用户名或者密码为空！", None

            # 查询用户信息
            user_info = UserViewData.get_user_by_username(username)

            if user_info is None:
                return False, "用户名或密码错误", None

            if user_info.user_status != '1':
                return False, "账号禁用！", None

            # 验证密码
            if user_info and password_decryption(password, user_info.password):
                user_info, message = enabled_platform_user(username)
                if user_info is None:
                    return False, message, None
                # 更新最后登录时间
                login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                UserViewData.update_user_login_time(user_info.id, login_time)

                # 获取用户权限信息
                query = UserViewData.get_user_permissions_with_names(user_info.id)

                # 生成token
                access_token = create_access_token(identity=username)

                # 记录登录日志
                try:
                    UserViewData.create_login_log(
                        user_info.id, username, remote_addr, host, user_agent
                    )
                except SQLAlchemyError as e:
                    print(f"写入登录日志失败: {str(e)}")

                _login_rate_clear(remote_addr)
                return True, '登录成功！', {
                    'access_token': access_token,
                    'user_id': user_info.id,
                    'user_name': user_info.name,
                    'user_role_name': query.permissions_name if query else None,
                    'user_role_id': query.role_id if query else None,
                    'is_superadmin': is_superadmin(user_info.id),
                    'is_admin': is_admin(user_info.id),
                    'datatime_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            else:
                _login_rate_record_fail(remote_addr, username)
                return False, "用户名或密码错误", None
        except Exception as e:
            _login_rate_record_fail(remote_addr, username)
            return False, f'登录失败: {str(e)}', None

    @staticmethod
    def loginfree(username, password, remote_addr=None, host=None, user_agent=None):
        """
        免验证码登录
        """
        allowed, msg = _login_rate_check(remote_addr, username)
        if not allowed:
            return False, msg, None
        try:
            # 去除用户名和密码中的首尾空格
            username = username.strip() if username else None
            password = password.strip() if password else None

            if username is None or password is None:
                return False, "用户名或者密码为空！", None

            # 查询用户信息
            user_info = UserViewData.get_user_by_username(username)

            if user_info is None:
                return False, "用户名或密码错误", None

            if user_info.user_status != '1':
                return False, "账号禁用！", None

            # 验证密码
            if user_info and password_decryption(password, user_info.password):
                user_info, message = enabled_platform_user(username)
                if user_info is None:
                    return False, message, None
                # 更新最后登录时间
                login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                UserViewData.update_user_login_time(user_info.id, login_time)

                # 获取用户权限信息
                query = UserViewData.get_user_permissions_with_names(user_info.id)

                # 生成token
                access_token = create_access_token(identity=username)

                # 记录登录日志
                try:
                    UserViewData.create_login_log(
                        user_info.id, username, remote_addr, host, user_agent
                    )
                except SQLAlchemyError as e:
                    print(f"写入登录日志失败: {str(e)}")

                _login_rate_clear(remote_addr)
                return True, '登录成功！', {
                    'access_token': access_token,
                    'user_id': user_info.id,
                    'user_name': user_info.name,
                    'user_role_name': query.permissions_name if query else None,
                    'user_role_id': query.role_id if query else None,
                    'is_superadmin': is_superadmin(user_info.id),
                    'is_admin': is_admin(user_info.id),
                    'datatime_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            else:
                _login_rate_record_fail(remote_addr, username)
                return False, "用户名或密码错误", None
        except Exception as e:
            _login_rate_record_fail(remote_addr, username)
            return False, f'登录失败: {str(e)}', None

    @staticmethod
    def token_refresh(username=None):
        """
        刷新当前 Bearer JWT；保留旧参数签名，但不使用外部用户名。
        """
        verify_jwt_in_request(locations=['headers'])
        identity = get_jwt_identity()
        user_info, message = enabled_platform_user(identity)
        if user_info is None:
            return False, message, None
        try:
            access_token = create_access_token(identity=identity)
            return True, None,{'access_token': access_token}
        except Exception as e:
            return False, f'刷新token失败: {str(e)}', None

    @staticmethod
    def protected():
        """
        获取受保护的用户信息
        """
        try:
            # 获取当前用户
            current_user = get_jwt_identity()

            # 查找用户信息
            user_info = UserViewData.get_user_by_username(current_user)

            # 获取用户权限数据
            permission_data = UserViewData.get_user_permissions(user_info.id)
            permission_data = [
                {'permission_id': i.userpermission_id, 'permission_name': i.permission_name}
                for i in permission_data
            ]

            # 序列化用户数据
            user_data = convert_folder_to_dict_list(
                user_info, ['id', 'username', 'email', 'create_time']
            )

            # 合并数据
            user_data = {**user_data, **{'permission_data': permission_data}}

            return True, None,{
                'logged_in_as': current_user,
                'is_superadmin': is_superadmin(user_info.id),
                    'is_admin': is_admin(user_info.id),
                'user_info': user_data
            }
        except Exception as e:
            return False, f'获取用户信息失败: {str(e)}', None

    # 用户注册相关业务逻辑
    @staticmethod
    def register(username, password, name=None):
        """
        用户注册
        """
        try:
            # 去除用户名和密码中的首尾空格
            username = username.strip() if username else None
            password = password.strip() if password else None

            if username is None or password is None:
                return False, '用户名和密码必须提供！'

            # 验证密码复杂度
            if not validate_password_complexity(password):
                return False, '密码不符合复杂度要求！'

            # 检查用户名是否已存在
            user = UserViewData.get_user_by_username(username)
            if user:
                return False, '该用户已经存在！'

            # 创建新用户
            UserViewData.create_user(username, password_encryption(password), name, user_status=1)

            return True, '注册成功！'
        except Exception as e:
            return False, f'注册失败: {str(e)}'

    # 用户管理相关业务逻辑
    @staticmethod
    def get_users(page, per_page, name=None, username=None, user_status=None):
        """
        获取用户列表（支持分页和筛选）
        """
        try:
            pagination = UserViewData.get_users_with_permissions(
                page, per_page, name, username, user_status
            )

            # 将结果转换为字典列表
            user_permission_datalist = convert_folder_to_dict_list(
                pagination.items,
                ['id', 'name', 'username', 'permissions_name', 'user_status', 'create_time', 'end_login_time']
            )

            for item in user_permission_datalist:
                item['is_protected'] = protected_user(item)

            return True ,None,{
                'data': user_permission_datalist,
                'total_items': pagination.total,
                'total_pages': pagination.pages,
                'current_page': pagination.page,
                'per_page': pagination.per_page,
            }
        except Exception as e:
            return False, f'获取用户列表失败: {str(e)}', None

    @staticmethod
    def add_user(name, username, password, email, permission_list_id):
        """
        添加用户
        """
        try:
            # 检查是否提供了必要的用户信息
            if not all([name, username, email, password]):
                return False, '用户姓名、用户名和邮箱为必填项！'

            # 检查传入的权限ID列表
            try:
                new_permissions = _permission_ids(permission_list_id)
            except (TypeError, ValueError) as e:
                return False, f'权限列表数据解析错误: {str(e)}'

            # 创建新用户
            new_user = UserViewData.create_user(
                username, password_encryption(password), name, email
            )
            user_id = new_user.id

            # 添加用户权限
            if new_permissions:
                UserViewData.add_user_permissions(user_id, new_permissions)

            return True, '用户添加成功！'
        except Exception as e:
            return False, f'用户添加失败: {str(e)}'

    @staticmethod
    def update_user(user_id, name=None, username=None, email=None, permission_list_id='[]'):
        """
        更新用户信息
        """
        try:
            # 检查用户ID是否存在
            if not user_id:
                return False, '用户ID未提供！'

            # 在任何数据库读写之前拒绝不合法权限参数。
            try:
                new_permissions = _permission_ids(permission_list_id)
            except (TypeError, ValueError) as e:
                return False, f'权限列表数据解析错误: {str(e)}'

            # 获取用户信息
            user_info = UserViewData.get_user_by_id(user_id)
            if not user_info:
                return False, '用户不存在！'

            # 更新用户基本信息
            UserViewData.update_user_info(user_id, name, username, email)

            # 获取用户当前权限
            current_permissions = UserViewData.get_user_permissions_ids(user_id)

            # 计算需要添加和删除的权限
            to_add = new_permissions - current_permissions
            to_delete = current_permissions - new_permissions

            # 删除不再需要的权限
            if to_delete:
                UserViewData.delete_user_permissions(user_id, to_delete)

            # 添加新的权限
            if to_add:
                UserViewData.add_user_permissions(user_id, to_add)

            return True, '用户信息和权限更新成功！'
        except Exception as e:
            return False, f'更新用户信息失败: {str(e)}'

    @staticmethod
    def update_user_password(user_id, current_password, new_password, password_confirm):
        """
        修改用户密码
        """
        try:
            # 获取用户信息
            user_info = UserViewData.get_user_by_id(user_id)
            if user_info:
                if password_decryption(current_password, user_info.password):
                    if new_password:
                        if not validate_password_complexity(new_password):
                            return False, '密码不符合复杂度要求！'
                        if new_password == password_confirm:
                            UserViewData.update_user_password(
                                user_id, password_encryption(new_password)
                            )
                            return True, '密码修改成功！'
                        else:
                            return False, '两次输入的新密码不一致！'
                    else:
                        return False, '请输入新密码！'
                else:
                    return False, '旧密码不正确！'
            else:
                return False, '用户不存在！'
        except Exception as e:
            return False, f'修改密码失败: {str(e)}'

    @staticmethod
    def update_user_status(user_id, status):
        """
        更新用户状态
        """
        try:
            if user_id and status:
                UserViewData.update_user_status(user_id, status)
                return True, '用户状态修改成功'
            else:
                return False, '用户及状态未输入'
        except Exception as e:
            return False, f'更新用户状态失败: {str(e)}'

    @staticmethod
    def get_user_detail(user_id, page=1, per_page=15):
        """
        获取用户详情
        """
        try:
            user_detail = UserViewData.get_user_detail(user_id,page, per_page)
            if not user_detail:
                return False, '用户不存在', None
            data = {
                'total_items': user_detail.total,
                'total_pages': user_detail.pages,
                'current_page': user_detail.page,
                'per_page': per_page,
                'data': [
                    {'id': i.id, 'name': i.name, 'username': i.username, 'permissions_ids': i.permissions_ids}
                    for i in user_detail.items
                ]
            }
            return True,None,data
        except Exception as e:
            return False, f'获取用户详情失败: {str(e)}', None

    @staticmethod
    def delete_user(user_id):
        """
        删除用户
        """
        try:
            if not user_id:
                return False, '用户ID缺失!'

            # 查找对应用户数据
            user_data = UserViewData.get_user_by_id(user_id)
            if not user_data:
                return False, '用户不存在!'

            if protected_user(user_data):
                return False, '内置超级管理员账户不能删除'

            # 删除用户数据
            UserViewData.delete_user(user_id)

            return True, '用户删除成功!'
        except Exception as e:
            return False, f'删除用户时发生错误: {str(e)}'

    # 权限菜单相关业务逻辑
    @staticmethod
    def get_permission_menu():
        """
        获取权限和菜单列表
        """
        try:
            # 角色列表返回
            permission_data = convert_folder_to_dict_list(
                UserViewData.get_all_permissions(),
                ['id', 'permission_name', 'permission_content', 'permission_status', 'permission_code', 'created_at']
            )

            # 菜单列表返回
            menu_list = [{
                'menu_id': i.id, 'menu_name': i.menu_name, 'menu_link': i.menu_link,
                'menu_icon': i.menu_icon, 'menu_status': i.menu_status,
                'menu_order': i.menu_order, 'menu_parent_id': i.menu_parent_id,
                'permissions_list': [],
            } for i in UserViewData.get_all_menus() if i.menu_name != '菜单管理']

            # 自定义排序函数
            def custom_sort(menu):
                return menu.get('menu_order', 0)

            # 对菜单项列表进行排序
            sorted_menu_items = sorted(menu_list, key=custom_sort)

            # 递归构建菜单树
            def build_tree(data, parent_id=None):
                tree = []
                for item in data:
                    if item['menu_parent_id'] == parent_id:
                        children = build_tree(data, item['menu_id'])
                        if children:
                            item['children'] = children
                        tree.append(item)
                return tree

            # 调用方法获取父子菜单组装数据
            menu_list = build_tree(sorted_menu_items)

            data_list = {
                'permission_data': permission_data,
                'menu_list': menu_list,
            }
            return True,None, data_list
        except Exception as e:
            return False, f'获取权限菜单失败: {str(e)}', None


def _platform_is_superadmin(user_id):
    # Import on request to avoid coupling the user service's module startup.
    from service.resource_admission_settings_api import is_administrator
    return bool(is_administrator(user_id))
