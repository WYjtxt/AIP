# native-role-policy-v1
from service.platform_role_policy import visible_roles, add_default_role_menus
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_


class RoleViewData:
    # 角色权限相关数据操作
    @staticmethod
    def get_permission_data(page, per_page):
        """
        获取角色权限数据（支持分页）
        """
        return visible_roles(db.session.query(Permission)).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def update_permission_status(permission_id, permission_status):
        """
        更新角色状态
        """
        result = db.session.query(Permission).filter(
            Permission.id == permission_id
        ).update({'permission_status': permission_status})
        db.session.commit()
        return result

    @staticmethod
    def get_permission_by_id(permission_id):
        """
        根据ID获取角色信息
        """
        return db.session.query(Permission).filter(Permission.id == permission_id).first()

    @staticmethod
    def delete_permission(permission_id):
        """
        删除角色信息
        """
        result = db.session.query(Permission).filter(Permission.id == permission_id).delete()
        db.session.commit()
        return result

    @staticmethod
    def delete_permission_menu(permission_id):
        """
        删除角色对应的菜单权限
        """
        result = db.session.query(PermissionMenu).filter(
            PermissionMenu.premission_id == permission_id
        ).delete(synchronize_session=False)
        db.session.commit()
        return result

    @staticmethod
    def get_permission_menu_by_permission_id(permission_id):
        """
        根据角色ID获取角色菜单权限
        """
        return db.session.query(PermissionMenu).filter(
            PermissionMenu.premission_id == permission_id
        ).all()

    @staticmethod
    def get_menu_by_ids(menu_ids_list, permission_id):
        """
        根据菜单ID列表获取菜单信息
        """
        return db.session.query(
            PermissionMenu.id.label('permissionmenu_id'),
            PermissionMenu.permissions_list,
            Menu.id.label('menu_id'), Menu.menu_name, Menu.menu_link,
            Menu.menu_icon, Menu.menu_order, Menu.menu_parent_id,
            Permission.id.label('permission_id'),
        ).join(
            Menu, PermissionMenu.menu_id == Menu.id
        ).join(
            Permission, PermissionMenu.premission_id == Permission.id
        ).filter(
            Menu.id.in_(menu_ids_list),
            Menu.menu_status == 1,
            Permission.id == permission_id
        ).all()

    @staticmethod
    def create_permission(permission_name, permission_content, permission_code, permission_status):
        """
        创建新角色
        """
        new_permission = Permission(
            permission_name=permission_name,
            permission_content=permission_content,
            permission_code=permission_code,
            permission_status=permission_status
        )
        db.session.add(new_permission)
        db.session.flush()
        add_default_role_menus(new_permission)
        db.session.commit()
        return new_permission

    @staticmethod
    def update_permission(permission_id, permission_name, permission_content, permission_code, permission_status):
        """
        更新角色信息
        """
        result = db.session.query(Permission).filter(
            Permission.id == permission_id
        ).update({
            'permission_name': permission_name,
            'permission_content': permission_content,
            'permission_code': permission_code,
            'permission_status': permission_status,
        })
        db.session.commit()
        return result

    @staticmethod
    def bulk_create_permission_menu(permission_id, permission_list):
        """
        批量创建角色菜单权限
        """
        new_permissions = [
            PermissionMenu(
                premission_id=permission_id,
                menu_id=item.get('menu_id'),
                permissions_list=item.get('permissions_list')
            ) for item in permission_list
        ]
        db.session.bulk_save_objects(new_permissions)
        db.session.commit()
        return new_permissions

    @staticmethod
    def get_permission_by_name(permission_name):
        """
        根据名称获取角色信息
        """
        return db.session.query(Permission).filter(Permission.permission_name == permission_name).first()
