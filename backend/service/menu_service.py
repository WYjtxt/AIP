# native-role-policy-v1
from service.platform_role_policy import restricted_actor
# native-role-management-v1
from service.platform_role_management import role_actions
from data.menu_data import MenuData
from config.configs import convert_folder_to_dict_list
import json
from data.exts import db
from model.admin import *


class MenuService:
    """
    菜单服务层，处理菜单和权限相关的业务逻辑
    """

    # 权限赋值相关方法
    @staticmethod
    def menu_manage_select():
        """Menu management owns its catalog; user and role modules are not queried."""
        try:
            fields = ('menu_name', 'menu_link', 'menu_icon', 'menu_status', 'menu_order', 'menu_parent_id')
            rows = [dict({'menu_id': row.id, 'permissions_list': []},
                         **{name: getattr(row, name) for name in fields})
                    for row in MenuData.get_management_menus()]
            rows.sort(key=lambda row: (row['menu_order'] or 0, row['menu_id']))
            return True, {'menu_list': MenuService.build_tree(rows)}
        except Exception:
            return False, '菜单列表读取失败，请刷新重试'

    @staticmethod
    def permission_give(user_id, permission_id):
        """
        权限赋值

        Args:
            user_id (str): 用户ID
            permission_id (str): 权限ID

        Returns:
            tuple: (success, message)，success 为布尔值，message 为消息
        """
        try:
            # 去除所传数据中的首尾空格
            user_id = user_id.strip() if user_id else None
            permission_id = permission_id.strip() if permission_id else None

            if user_id is None or permission_id is None:
                return False, "用户权限数据必须填写"

            # 查询选择用户id跟权限id 如果权限不存在 将权限赋值到用户权限表
            userper_data = MenuData.get_user_permission(user_id)
            if userper_data:
                # 更新用户权限
                MenuData.update_user_permission(userper_data, permission_id)
                return True, '权限修改完成'

            # 创建用户权限
            MenuData.create_user_permission(user_id, permission_id)
            return True, '权限赋值完成'
        except Exception as e:
            print(f"权限赋值失败: {e}")
            return False, f"权限赋值失败: {str(e)}"

    # 菜单展示相关方法
    @staticmethod
    def menu_show(user_id):
        """
        对应权限菜单展示

        Args:
            user_id (str): 用户ID

        Returns:
            tuple: (success, result)，success 为布尔值，result 为数据或消息
        """
        try:
            # 判断用户是否存在
            if not user_id:
                return False, '用户不存在'

            # 获取用户信息
            user_info = MenuData.get_user(user_id)
            if not user_info:
                return False, '用户不存在'

            # 获取用户权限数据
            permission_data = MenuData.get_user_permission_data(user_info.id)
            if not permission_data:
                return False, '用户权限不存在'

            # 查找到用户对应权限列表，去权限菜单表里查询对应拥有该权限的菜单
            user_permission_data = [int(i['permission_id']) for i in convert_folder_to_dict_list(permission_data, ['permission_id'])]

            # 获取到该用户权限标识列表 ，去权限与菜单关联表查找对应权限菜单
            permission_menu_list = MenuData.get_permission_menu_list(user_permission_data)

            # 提取菜单标识字段并去重 (集合{}唯一去重)
            menu_ids = {item.menu_id for item in permission_menu_list}

            # 将结果转换为列表
            menu_ids_list = list(menu_ids)

            # 查找菜单表中 menu_ids_list所对应id的记录
            menu_list = convert_folder_to_dict_list(
                MenuData.get_menus(menu_ids_list),
                ['menu_id', 'menu_name', 'menu_link', 'menu_status', 'menu_icon', 'menu_order', 'menu_parent_id',]
            )

            if restricted_actor():
                menu_list = [item for item in menu_list if str(item.get('menu_link') or '').strip('/') != 'platform-upgrade']

            # 组装数据，把多个权限对应增删改查列表进行组合
            merge_permissions_list = MenuService.merge_permissions(
                convert_folder_to_dict_list(
                    MenuData.get_permission_menu_by_permission_ids(list({item.premission_id for item in permission_menu_list})),
                    ['menu_id', 'permissions_list']
                )
            )

            # 将menu_list与 merge_permissions_list整和，判断当menu_id 相同时，两个数据合一起
            menu_list = MenuService.merge_menu_permissions(menu_list, merge_permissions_list)

            # 对菜单项列表进行排序
            sorted_menu_items = sorted(menu_list, key=MenuService.custom_sort)

            # 调用方法获取父子菜单组装数据
            menu_list = MenuService.build_tree(sorted_menu_items)

            return True, menu_list
        except Exception as e:
            print(f"菜单展示失败: {e}")
            return False, f"菜单展示失败: {str(e)}"

    # 菜单修改相关方法
    @staticmethod
    def menu_manage_update(status, menu_id, menu_name, menu_link, menu_order, menu_icon, menu_parent_id, menu_status):
        """
        菜单修改对应配置

        Args:
            status (str): 状态，1目录，2菜单
            menu_id (str): 菜单ID
            menu_name (str): 菜单名称
            menu_link (str): 菜单路径
            menu_order (str): 菜单顺序
            menu_icon (str): 菜单图标
            menu_parent_id (str): 菜单父ID
            menu_status (str): 菜单状态

        Returns:
            tuple: (success, message)，success 为布尔值，message 为消息
        """
        try:
            # 去除所传数据中的首尾空格
            status = status.strip() if status else None
            menu_id = menu_id.strip() if menu_id else None
            menu_name = menu_name.strip() if menu_name else None
            menu_link = menu_link.strip() if menu_link else None
            menu_order = menu_order.strip() if menu_order else None
            menu_icon = menu_icon.strip() if menu_icon else None
            menu_parent_id = menu_parent_id.strip() if menu_parent_id else None
            menu_status = menu_status.strip() if menu_status else None

            # 参数构建判断是否为空
            params = [status, menu_id, menu_name, menu_order]
            if not all(params):
                return False, '设备数据有未填写项'

            # 查询菜单 ID 是否存在
            menu_id_data = MenuData.get_menu_by_id(menu_id)
            if not menu_id_data:
                return False, '当前菜单ID不存在！'

            if int(status) == 1:
                # 当为目录时，设为顶级父类，parent_id 为 None
                success = MenuData.update_menu(
                    menu_id, menu_name, menu_link, menu_icon, menu_order, menu_status, None
                )
            else:
                # 当为菜单时，设为子菜单，parent_id 为所选父类 ID
                success = MenuData.update_menu(
                    menu_id, menu_name, menu_link, menu_icon, menu_order, menu_status, menu_parent_id
                )

            if success:
                return True, '修改成功！'
            else:
                return False, '修改失败！'
        except Exception as e:
            print(f"菜单修改失败: {e}")
            return False, f"数据库更新失败: {str(e)}"

    # 菜单添加相关方法
    @staticmethod
    def menu_manage_add(status, menu_name, menu_link, menu_order, menu_icon, menu_status, menu_parent_id):
        """
        菜单配置添加

        Args:
            status (str): 状态，1目录，2菜单
            menu_name (str): 菜单名称
            menu_link (str): 菜单路径
            menu_order (str): 菜单顺序
            menu_icon (str): 菜单图标
            menu_status (str): 菜单状态
            menu_parent_id (str): 菜单父ID

        Returns:
            tuple: (success, message)，success 为布尔值，message 为消息
        """
        try:
            # 去除所传数据中的首尾空格
            status = status.strip() if status else None
            menu_name = menu_name.strip() if menu_name else None
            menu_link = menu_link.strip() if menu_link else None
            menu_order = menu_order.strip() if menu_order else None
            menu_icon = menu_icon.strip() if menu_icon else None
            menu_status = menu_status.strip() if menu_status else '1'
            menu_parent_id = menu_parent_id.strip() if menu_parent_id else None

            # 参数构建判断是否为空
            params = [status, menu_name, menu_order]
            if not all(params):
                return False, '设备数据有未填写项'

            # 查询菜单名称是否存在，如果已经存在提示
            if db.session.query(Menu).filter(Menu.menu_name == menu_name).first() is not None:
                return False, '该菜单已经存在'

            if int(status) == 1:
                # 当为目录时，设为顶级父类，parent_id 为 None
                MenuData.create_menu(
                    menu_name, menu_link, menu_icon, menu_order, menu_status, None
                )
            else:
                # 当为菜单时，设为子菜单，parent_id 为所选父类 ID
                MenuData.create_menu(
                    menu_name, menu_link, menu_icon, menu_order, menu_status, menu_parent_id
                )

            return True, '添加成功！'
        except Exception as e:
            print(f"菜单添加失败: {e}")
            return False, f"数据库添加失败: {str(e)}"

    # 菜单状态修改相关方法
    @staticmethod
    def menu_manage_status_update(menu_id, menu_status):
        """
        菜单状态修改

        Args:
            menu_id (str): 菜单ID
            menu_status (str): 菜单状态，1启用 0禁用

        Returns:
            tuple: (success, message)，success 为布尔值，message 为消息
        """
        try:
            # 当用户id与用户状态存在
            if menu_id and menu_status:
                # 更新菜单状态
                success = MenuData.update_menu_status(menu_id, menu_status)
                if success:
                    return True, '菜单状态修改成功'
                else:
                    return False, '菜单状态修改失败'
            return False, '菜单及状态未输入'
        except Exception as e:
            print(f"菜单状态修改失败: {e}")
            return False, f"菜单状态修改失败: {str(e)}"

    # 菜单删除相关方法
    @staticmethod
    def menu_manage_delete(menu_list):
        """
        菜单删除

        Args:
            menu_list (str): 菜单ID列表，JSON 格式的字符串

        Returns:
            tuple: (success, message)，success 为布尔值，message 为消息
        """
        try:
            # 将字符串转换为列表，确保 menu_list 是 JSON 格式的字符串
            try:
                menu_ids = json.loads(menu_list)
            except json.JSONDecodeError:
                return False, '无效的菜单列表格式!'

            # 查找所有匹配的菜单数据
            menus_to_delete = MenuData.get_menus_to_delete(menu_ids)
            if not menus_to_delete:
                return False, '菜单不存在!'

            # 批量删除菜单
            success = MenuData.delete_menus(menu_ids)
            if success:
                return True, '菜单删除成功!'
            else:
                return False, '菜单删除失败!'
        except Exception as e:
            print(f"菜单删除失败: {e}")
            return False, f'删除菜单时发生错误: {str(e)}'

    # 辅助方法
    @staticmethod
    def merge_permissions(permission_menu_list):
        combined = {}
        for item in permission_menu_list:
            try:
                actions = role_actions(item.get('permissions_list', '[]'))
            except (TypeError, ValueError):
                actions = []
            combined.setdefault(item.get('menu_id'), set()).update(actions)
        return [{'menu_id': menu_id, 'permissions_list': [action for action in 'crud' if action in actions]}
                for menu_id, actions in combined.items()]

    @staticmethod
    def merge_menu_permissions(menu_list, merge_permissions_list):
        """
        将 menu_list 和 merge_permissions_list 根据 menu_id 整合

        Args:
            menu_list (list): 包含菜单项的列表
            merge_permissions_list (list): 包含权限信息的列表

        Returns:
            list: 整合后的菜单列表
        """
        merged_data = [
            {
                **menu,
                # 从 merge_permissions_list 获取权限信息
                **next((perm for perm in merge_permissions_list if perm['menu_id'] == menu['menu_id']), {})
            }
            for menu in menu_list
        ]
        return merged_data

    @staticmethod
    def custom_sort(menu):
        """
        自定义排序函数

        Args:
            menu (dict): 菜单项

        Returns:
            int: 排序值
        """
        return menu.get('menu_order', 0)

    @staticmethod
    def build_tree(data, parent_id=None):
        """
        构建菜单树

        Args:
            data (list): 菜单项列表
            parent_id (str, optional): 父菜单ID. Defaults to None.

        Returns:
            list: 菜单树
        """
        tree = []
        for item in data:
            if item['menu_parent_id'] == parent_id:
                children = MenuService.build_tree(data, item['menu_id'])
                if children:
                    item['children'] = children
                tree.append(item)
        return tree

