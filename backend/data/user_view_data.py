# native-role-policy-v1
from service.platform_role_policy import visible_users, visible_roles
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_, func


class UserViewData:
    # 用户相关数据操作
    @staticmethod
    def get_user_by_username(username):
        """
        根据用户名获取用户信息
        """
        return db.session.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(user_id):
        """
        根据ID获取用户信息
        """
        return db.session.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_user(username, password, name=None, email=None, user_status=1):
        """
        创建新用户
        """
        new_user = User(
            username=username,
            password=password,
            name=name,
            email=email,
            user_status=user_status
        )
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def update_user_login_time(user_id, login_time):
        """
        更新用户最后登录时间
        """
        user_info = db.session.query(User).filter(User.id == user_id).first()
        if user_info:
            user_info.end_login_time = login_time
            db.session.commit()
        return user_info

    @staticmethod
    def update_user_status(user_id, status):
        """
        更新用户状态
        """
        result = db.session.query(User).filter(User.id == user_id).update({'user_status': status})
        db.session.commit()
        return result

    @staticmethod
    def update_user_info(user_id, name=None, username=None, email=None):
        """
        更新用户基本信息
        """
        user_info = db.session.query(User).filter(User.id == user_id).first()
        if user_info:
            if name:
                user_info.name = name
            if username:
                user_info.username = username
            if email:
                user_info.email = email
            db.session.commit()
        return user_info

    @staticmethod
    def update_user_password(user_id, password):
        """
        更新用户密码
        """
        user_info = db.session.query(User).filter(User.id == user_id).first()
        if user_info:
            user_info.password = password
            db.session.commit()
        return user_info

    @staticmethod
    def delete_user(user_id):
        """
        删除用户
        """
        result = db.session.query(User).filter(User.id == user_id).delete()
        db.session.commit()
        return result

    @staticmethod
    def get_users_with_permissions(page, per_page, name=None, username=None, user_status=None):
        """
        获取用户列表及其权限（支持分页和筛选）
        """
        filters = []
        if name:
            filters.append(User.name.like(f"%{name}%"))
        if username:
            filters.append(User.username.like(f"%{username}%"))
        if user_status:
            filters.append(User.user_status == user_status)

        query = db.session.query(
            User.id,
            User.name,
            User.username,
            User.user_status,
            User.create_time,
            User.end_login_time,
            func.group_concat(Permission.permission_name.distinct()).label('permissions_name')
        ).join(
            UserPermission, User.id == UserPermission.user_id
        ).join(
            Permission, UserPermission.permission_id == Permission.id
        ).group_by(
            User.id, User.name, User.username, User.user_status, User.create_time, User.end_login_time
        )

        if filters:
            query = query.filter(and_(*filters))

        return visible_users(query).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_user_detail(user_id,page,per_page):
        """
        获取用户详情
        """
        return db.session.query(
            User.id,
            User.name,
            User.username,
            User.password,
            User.email,
            func.group_concat(UserPermission.permission_id).label('permissions_ids')
        ).join(
            UserPermission, User.id == UserPermission.user_id
        ).filter(User.id == user_id).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_user_permissions(user_id):
        """
        获取用户权限信息
        """
        return db.session.query(
            User.id,
            User.username,
            Permission.id.label('userpermission_id'),
            Permission.permission_name
        ).join(
            UserPermission, User.id == UserPermission.user_id
        ).join(
            Permission, UserPermission.permission_id == Permission.id
        ).filter(User.id == user_id).all()

    @staticmethod
    def get_user_permissions_ids(user_id):
        """
        获取用户权限ID列表
        """
        permissions = db.session.query(UserPermission.permission_id).filter(
            UserPermission.user_id == user_id
        ).all()
        return {perm_id for perm_id, in permissions}

    @staticmethod
    def add_user_permissions(user_id, permission_ids):
        """
        批量添加用户权限
        """
        new_user_permissions = [
            UserPermission(user_id=user_id, permission_id=perm_id)
            for perm_id in permission_ids
        ]
        db.session.bulk_save_objects(new_user_permissions)
        db.session.commit()
        return new_user_permissions

    @staticmethod
    def delete_user_permissions(user_id, permission_ids):
        """
        批量删除用户权限
        """
        result = db.session.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id.in_(permission_ids)
        ).delete(synchronize_session=False)
        db.session.commit()
        return result

    @staticmethod
    def get_user_permissions_with_names(user_id):
        """
        获取用户权限信息（包含权限名称和ID）
        """
        return db.session.query(
            User.id,
            User.name,
            User.username,
            User.user_status,
            User.create_time,
            User.end_login_time,
            func.group_concat(Permission.permission_name.distinct()).label('permissions_name'),
            func.group_concat(Permission.id.distinct()).label('role_id')
        ).join(
            UserPermission, User.id == UserPermission.user_id
        ).join(
            Permission, UserPermission.permission_id == Permission.id
        ).group_by(
            User.id, User.name, User.username, User.user_status, User.create_time, User.end_login_time
        ).filter(User.id == user_id).first()

    # 权限相关数据操作
    @staticmethod
    def get_all_permissions():
        """
        获取所有权限
        """
        return visible_roles(db.session.query(Permission)).all()

    @staticmethod
    def get_all_menus():
        """
        获取所有菜单
        """
        return db.session.query(Menu).all()

    # 登录日志相关数据操作
    @staticmethod
    def create_login_log(user_id, user_name, ip_address, hostname, user_agent):
        """
        创建登录日志
        """
        login_log = Platform_login(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            hostname=hostname,
            user_agent=user_agent,
            status='成功',
            login_status='登录',
            error_message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(login_log)
        db.session.commit()
        return login_log
