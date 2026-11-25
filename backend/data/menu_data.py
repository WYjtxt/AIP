from data.exts import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_, update


class MenuData:
    """
    菜单数据层，处理菜单和权限相关的数据库操作
    """

    # 权限赋值相关方法
    @staticmethod
    def get_management_menus():
        """Read menu configuration including disabled entries, without user data."""
        return db.session.query(Menu).filter(Menu.menu_name != '菜单管理').all()

    @staticmethod
    def get_user_permission(user_id):
        """
        获取用户权限

        Args:
            user_id (str): 用户ID

        Returns:
            UserPermission: 用户权限对象
        """
        return db.session.query(UserPermission).filter(UserPermission.user_id == user_id).first()

    @staticmethod
    def create_user_permission(user_id, permission_id):
        """
        创建用户权限

        Args:
            user_id (str): 用户ID
            permission_id (str): 权限ID

        Returns:
            UserPermission: 创建的用户权限对象
        """
        userper = UserPermission(user_id=user_id, permission_id=permission_id)
        db.session.add(userper)
        db.session.commit()
        return userper

    @staticmethod
    def update_user_permission(userper_data, permission_id):
        """
        更新用户权限

        Args:
            userper_data (UserPermission): 用户权限对象
            permission_id (str): 权限ID

        Returns:
            UserPermission: 更新后的用户权限对象
        """
        userper_data.permission_id = permission_id
        db.session.commit()
        return userper_data

    # 菜单展示相关方法
    @staticmethod
    def get_user(user_id):
        """
        获取用户信息

        Args:
            user_id (str): 用户ID

        Returns:
            User: 用户对象
        """
        return db.session.query(User).filter(User.id == user_id, User.user_status == 1).first()

    @staticmethod
    def get_user_permission_data(user_id):
        """
        获取用户权限数据

        Args:
            user_id (str): 用户ID

        Returns:
            list: 用户权限数据列表
        """
        return db.session.query(UserPermission.permission_id).\
            join(Permission, UserPermission.permission_id == Permission.id).\
            filter(UserPermission.user_id == user_id, Permission.permission_status == 1).all()

    @staticmethod
    def get_permission_menu_list(permission_ids):
        """
        获取权限菜单关联列表

        Args:
            permission_ids (list): 权限ID列表

        Returns:
            list: 权限菜单关联列表
        """
        return db.session.query(PermissionMenu).filter(
            PermissionMenu.premission_id.in_(permission_ids)
        ).all()

    @staticmethod
    def get_menus(menu_ids):
        """
        获取菜单列表

        Args:
            menu_ids (list): 菜单ID列表

        Returns:
            list: 菜单列表
        """
        return db.session.query(
            Menu.id.label('menu_id'), Menu.menu_name,
            Menu.menu_link, Menu.menu_icon,
            Menu.menu_order, Menu.menu_parent_id,
            Menu.menu_status,
        ).filter(Menu.id.in_(menu_ids), Menu.menu_status == 1).all()

    @staticmethod
    def get_permission_menu_by_permission_ids(permission_ids):
        """
        根据权限ID列表获取权限菜单关联

        Args:
            permission_ids (list): 权限ID列表

        Returns:
            list: 权限菜单关联列表
        """
        return db.session.query(PermissionMenu).\
            filter(PermissionMenu.premission_id.in_(permission_ids)).all()

    # 菜单管理相关方法
    @staticmethod
    def get_menu_by_id(menu_id):
        """
        根据ID获取菜单

        Args:
            menu_id (str): 菜单ID

        Returns:
            Menu: 菜单对象
        """
        return db.session.query(Menu).filter(Menu.id == menu_id).first()

    @staticmethod
    def get_menu_by_name(menu_name):
        """
        根据名称获取菜单

        Args:
            menu_name (str): 菜单名称

        Returns:
            Menu: 菜单对象
        """
        return db.session.query(Menu).filter(Menu.menu_name == menu_name).first()

    @staticmethod
    def update_menu(menu_id, menu_name, menu_link, menu_icon, menu_order, menu_status, menu_parent_id):
        """
        更新菜单

        Args:
            menu_id (str): 菜单ID
            menu_name (str): 菜单名称
            menu_link (str): 菜单链接
            menu_icon (str): 菜单图标
            menu_order (str): 菜单顺序
            menu_status (str): 菜单状态
            menu_parent_id (str): 菜单父ID

        Returns:
            bool: 是否更新成功
        """
        try:
            update_query = (
                update(Menu)
                .where(Menu.id == menu_id)
                .values(
                    menu_name=menu_name,
                    menu_link=menu_link,
                    menu_icon=menu_icon,
                    menu_order=menu_order,
                    menu_status=menu_status,
                    menu_parent_id=menu_parent_id,
                )
            )
            db.session.execute(update_query)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"更新菜单失败: {e}")
            return False

    @staticmethod
    def create_menu(menu_name, menu_link, menu_icon, menu_order, menu_status, menu_parent_id):
        """
        创建菜单

        Args:
            menu_name (str): 菜单名称
            menu_link (str): 菜单链接
            menu_icon (str): 菜单图标
            menu_order (str): 菜单顺序
            menu_status (str): 菜单状态
            menu_parent_id (str): 菜单父ID

        Returns:
            Menu: 创建的菜单对象
        """
        add_query = Menu(
            menu_name=menu_name, menu_link=menu_link,
            menu_icon=menu_icon, menu_order=menu_order,
            menu_parent_id=menu_parent_id, menu_status=menu_status
        )
        db.session.add(add_query)
        db.session.commit()
        return add_query

    @staticmethod
    def update_menu_status(menu_id, menu_status):
        """
        更新菜单状态

        Args:
            menu_id (str): 菜单ID
            menu_status (str): 菜单状态

        Returns:
            bool: 是否更新成功
        """
        try:
            db.session.query(Menu).filter(Menu.id == menu_id).update({'menu_status': menu_status})
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"更新菜单状态失败: {e}")
            return False

    @staticmethod
    def delete_menus(menu_ids):
        """
        删除菜单

        Args:
            menu_ids (list): 菜单ID列表

        Returns:
            bool: 是否删除成功
        """
        try:
            menus_to_delete = db.session.query(Menu).filter(Menu.id.in_(menu_ids)).all()
            for menu_data in menus_to_delete:
                db.session.delete(menu_data)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"删除菜单失败: {e}")
            return False

    @staticmethod
    def get_menus_to_delete(menu_ids):
        """
        获取要删除的菜单

        Args:
            menu_ids (list): 菜单ID列表

        Returns:
            list: 要删除的菜单列表
        """
        return db.session.query(Menu).filter(Menu.id.in_(menu_ids)).all()
