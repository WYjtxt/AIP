# native-role-management-v1
from service.platform_role_management import protected_role, replace_role_menus, canonical_actions
from data.role_view_data import RoleViewData
from config.configs import *

class RoleViewService:
    # 角色权限相关业务逻辑
    @staticmethod
    def get_permission_data(page, per_page):
        """
        获取角色权限数据（支持分页）
        """
        try:
            permission_data = RoleViewData.get_permission_data(page, per_page)

            # 构建返回的 JSON
            response_data = {
                'total_items': permission_data.total,
                'total_pages': permission_data.pages,
                'current_page': permission_data.page,
                'per_page': per_page,
                'data': [
                    {
                        'id': i.id, 
                        'permission_name': i.permission_name, 
                        'permission_content': i.permission_content,
                        'permission_status': i.permission_status,
                        'permission_code': i.permission_code,
                        'is_protected': protected_role(i),
                        'created_at': i.created_at
                    }
                    for i in permission_data.items
                ]
            }
            return True, response_data
        except Exception as e:
            return False, f'获取角色权限数据失败: {str(e)}'

    @staticmethod
    def update_permission_status(permission_id, permission_status):
        """
        更新角色状态
        """
        try:
            # 参数校验
            if not permission_id or permission_status is None:
                return False, '角色及状态未输入'

            # 更新角色状态
            RoleViewData.update_permission_status(permission_id, permission_status)
            return True, '角色状态修改成功'
        except Exception as e:
            return False, f'更新角色状态失败: {str(e)}'

    @staticmethod
    def delete_permission(permission_id):
        """
        删除角色及其对应权限数据
        """
        try:
            # 参数校验
            if not permission_id:
                return False, '角色ID缺失'

            # 查找对应角色数据
            permiss_data = RoleViewData.get_permission_by_id(permission_id)
            if not permiss_data:
                return False, '角色不存在'

            if protected_role(permiss_data):
                return False, '内置超级管理员角色不能删除'

            # 删除角色对应的所有权限数据
            RoleViewData.delete_permission_menu(permission_id)

            # 删除角色数据
            RoleViewData.delete_permission(permission_id)

            return True, '角色删除成功'
        except Exception as e:
            return False, f'删除角色时发生错误: {str(e)}'

    @staticmethod
    def get_permission_menu(permission_id):
        """
        获取角色相关菜单权限
        """
        try:
            # 参数校验
            if not permission_id:
                return False, '角色id不存在'

            # 获取角色权限数据
            permission_menu = RoleViewData.get_permission_menu_by_permission_id(permission_id)

            # 提取菜单标识字段并去重 (集合{}唯一去重)
            menu_ids = {item.menu_id for item in permission_menu}

            # 将结果转换为列表
            menu_ids_list = list(menu_ids)

            # 查找菜单表中 menu_ids_list所对应id的记录
            menu_result = RoleViewData.get_menu_by_ids(menu_ids_list, permission_id)

            # 转换为字典列表
            menu_list = convert_folder_to_dict_list(
                menu_result,
                ['menu_id', 'menu_name', 'menu_link', 'menu_icon', 'menu_status', 'menu_order', 
                 'menu_parent_id', 'permissionmenu_id', 'permission_id', 'permissions_list']
            )

            for item in menu_list:
                item['permissions_list'] = canonical_actions(item['permissions_list'])

            # 自定义排序函数  按照菜单表自定义顺序来对菜单进行排序
            def custom_sort(menu):
                return menu.get('menu_order', 0)

            # 对菜单项列表进行排序
            sorted_menu_items = sorted(menu_list, key=custom_sort)

            # 从 menu_parent_id为none主节点开始找  （递归找出所有子类菜单）
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

            return True, menu_list
        except Exception as e:
            return False, f'获取角色菜单权限失败: {str(e)}'

    @staticmethod
    def update_permission_menu(permission_id, menu_permissions_list):
        try:
            replace_role_menus(permission_id, menu_permissions_list)
            return True, '修改权限对应菜单标识完成！'
        except (TypeError, ValueError) as error:
            return False, str(error)
        except Exception:
            return False, '权限保存失败，原有授权已保留，请重试'

    @staticmethod
    def add_permission(permission_name, permission_content, permission_code, permission_status):
        """
        添加角色信息
        """
        try:
            # 检查是否提供了必要的角色信息
            if not all([permission_name, permission_content, permission_status]):
                return False, '角色姓名、描述为必填项！'

            # 检查角色名称是否已存在
            existing_permission = RoleViewData.get_permission_by_name(permission_name)
            if existing_permission:
                return False, '角色名称已经存在!'

            # 创建新的角色记录
            RoleViewData.create_permission(
                permission_name, permission_content, permission_code, permission_status
            )

            return True, '角色添加成功！'
        except Exception as e:
            return False, f'角色添加失败: {str(e)}'

    @staticmethod
    def update_permission_info(permission_id, permission_name, permission_content, permission_code, permission_status):
        """
        更新角色信息
        """
        try:
            # 检查是否提供了必要的角色信息
            if not permission_id:
                return False, '角色id不存在！'

            # 更新角色信息
            RoleViewData.update_permission(
                permission_id, permission_name, permission_content, permission_code, permission_status
            )

            return True, '角色信息修改成功！'
        except Exception as e:
            return False, f'角色修改失败: {str(e)}'
