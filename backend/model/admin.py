from data.exts import db
from sqlalchemy import Index, Column, Integer, String, ForeignKey,event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship,validates
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from flask import request, g
import pytz
import traceback
import socket
import json

local_tz = pytz.timezone('Asia/Shanghai')


# TimestampMixin 是一个方便的 Mixin 类，用于在多个模型中添加创建和更新时间戳字段。
# TimestampMixin 类与其他模型类一起继承，你可以轻松地将这两个时间戳字段添加到任何模型中，而无需重复代码
class TimestampMixin(object):
    # created_at = db.Column(db.DateTime, default=lambda: datetime.now(local_tz), comment='创建时间')
    # updated_at = db.Column(db.DateTime, default=lambda: datetime.now(local_tz), onupdate=lambda: datetime.now(local_tz), comment='更新时间')
    created_at = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')
    updated_at = db.Column(db.DateTime, server_default=db.func.now(),onupdate=db.func.now(), comment='更新时间')


# 菜单表
class Menu(db.Model):
    """菜单表"""
    __tablename__ = "t_menu"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '菜单表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='菜单id')
    menu_name = db.Column(db.String(32), comment='菜单名称')
    menu_link = db.Column(db.String(255), comment='url请求地址')
    menu_icon = db.Column(db.String(255), comment='图标')
    menu_order = db.Column(db.Integer, comment='菜单顺序')
    menu_parent_id = db.Column(db.Integer, comment='父菜单id')  # 如果此项为 null，那么它就是顶级菜单
    menu_permission_list = db.Column(db.String(32),comment='权限标识列表')  # 【1,2,3】  parent_id 加权限列表来给出菜单
    menu_status = db.Column(db.String(32), server_default='1', comment='状态 1.启用 0.禁用')



# 权限表
class Permission(db.Model,TimestampMixin):
    """权限表"""
    __tablename__ = "t_permission"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '权限表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='权限id')
    permission_name = db.Column(db.String(32), comment='权限名称')
    permission_code = db.Column(db.String(32), comment='权限代码')
    permission_content = db.Column(db.String(255), comment='权限描述')
    permission_status = db.Column(db.String(32), server_default='1', comment='状态 1.启用 0.禁用')



# 用户权限关联表
class UserPermission(db.Model,TimestampMixin):
    """用户权限关联表"""
    __tablename__ = "t_user_permission"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '用户权限关联表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='关联表id')
    user_id = db.Column(db.Integer,comment='用户id')
    permission_id = db.Column(db.String(33),comment='权限id')


# 权限菜单关联表
class PermissionMenu(db.Model, TimestampMixin):
    __tablename__ = 't_premission_menu'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '权限菜单关联表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')
    premission_id = db.Column(db.Integer,comment='权限ID')
    menu_id = db.Column(db.Integer,comment='菜单ID')
    permissions_list = db.Column(db.String(100), nullable=True, comment='增删改查权限', default='[c,r,u,d]')
    extra_field = db.Column(db.String(255), nullable=True, comment='额外字段')


# 用户表
class User(db.Model):
    """用户表"""
    __tablename__ = "t_user"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '用户表'
    }

    id = db.Column(db.Integer, primary_key=True,autoincrement=True,comment='用户id')  # 整型的主键，会默认设置为自增主键
    name = db.Column(db.String(32),comment='姓名')
    username = db.Column(db.String(32),comment='用户名称')
    password = db.Column(db.Text,comment='用户密码')
    email = db.Column(db.String(32),comment='用户邮箱')
    user_status = db.Column(db.String(32),server_default='1',comment='账号状态 1.启用 0.禁用')
    create_time = db.Column(db.DateTime, server_default=db.func.now(),comment='创建时间')
    end_login_time = db.Column(db.DateTime,comment='最后登录时间')
    free_secret = db.Column(db.Integer,comment='免密登录 1.启用 0.禁用')


    def get_id(self):
        return str(self.id)

    # 实现 UserMixin 的方法
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.user_status == '1'

    @property
    def is_anonymous(self):
        return False


# 矿名称表  单独作为一个表，来关联对应下方设备
class Mine(db.Model):
    """矿名称表"""
    __tablename__ = "t_mine"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '矿名称表'
    }

    id = db.Column(db.Integer, primary_key=True,autoincrement=True,comment='id')  # 整型的主键，会默认设置为自增主键
    mine_name = db.Column(db.String(100), comment='节点名称（省/市/县/集团/煤矿名称）')
    # parent_id = db.Column(db.Integer, comment='父节点ID，顶级节点为NULL')
    # level = db.Column(db.Integer, comment='层级，省为1，市为2，县为3，集团为4，煤矿为5')
    mine_code = db.Column(db.String(200), comment='煤矿编码，仅煤矿层级有值')
    combined_field = db.Column(db.String(200), comment='自动拼接字段')  # 新增字段，用于存储自动拼接的内容


    # 静态方法
    @staticmethod
    def register_listeners():
        """
        注册事件监听器
        """
        # 新增数据时定义字段发生改变
        @event.listens_for(Mine, 'before_insert')
        def before_insert_listener(mapper, connection, target):
            """
            监听器函数，在插入新记录之前被调用。
            自动设置 `combined_field` 字段的值。

            :param mapper: SQLAlchemy 的映射器对象
            :param connection: 数据库连接对象
            :param target: 正在插入的目标对象（即 Mine 实例）
            """
            print('增加逻辑')  # 打印调试信息，表示触发了插入逻辑
            # 设置 `combined_field` 的值
            target.combined_field = f"{target.mine_name} -----------"

        # 数据更新时定义字段发生改变
        @event.listens_for(Mine, 'before_update')
        def before_update_listener(mapper, connection, target):
            """
            监听器函数，在插入新记录之前被调用。
            自动设置 `combined_field` 字段的值。

            :param mapper: SQLAlchemy 的映射器对象
            :param connection: 数据库连接对象
            :param target: 正在插入的目标对象（即 Mine 实例）
            """
            print('修改逻辑')  # 打印调试信息，表示触发了更新逻辑
            # 设置 `combined_field` 的值
            target.combined_field = f"{target.mine_name} -----------"


    # 序列化
    def to_json(self):
        return {
            'id': self.id,
            'mine_name': self.mine_name,
            'combined_field': self.combined_field,
        }

class DictType(db.Model):
    """字典类型表"""
    __tablename__= 't_dict_type'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '字典类型表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True,comment='字典类型id')
    type_name = db.Column(db.String(255),comment='字典类型名称')
    type_code = db.Column(db.String(255),comment='字典类型标识')
    description = db.Column(db.String(255),comment='字典类型描述')
    enable = db.Column(db.String(32),server_default='1',comment='字典是否启用 1 启用 2 停止')
    create_time = db.Column(db.DateTime, default=db.func.now() , comment='创建时间')
    update_time = db.Column(db.DateTime, default=db.func.now() , onupdate=db.func.now() , comment='更新时间')


# 字典数据表
class Dict_data(db.Model):
    """字典数据表"""
    __tablename__ = "t_dict_data"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '字典数据表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    data_id = db.Column(db.Integer, comment = '字典子表id')
    data_label = db.Column(db.String(255),comment = '标签')
    data_value = db.Column(db.String(255),comment = '对应值')
    type_code = db.Column(db.String(255),comment = '字典类型标识')
    is_default = db.Column(db.Integer, comment='是否默认')
    enable = db.Column(db.String(32),server_default='1',comment='字典是否启用 1 启用 2 停止')
    remark = db.Column(db.String(255),comment='描述')
    create_time = db.Column(db.DateTime, default=db.func.now() , comment='创建时间')
    update_time = db.Column(db.DateTime, default=db.func.now() , onupdate=db.func.now() , comment='更新时间')



# 定时任务表
class ScheduledTask(db.Model):
    """定时任务表"""
    __tablename__ = 't_scheduled_tasks'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '定时任务表'
    }

    # 任务ID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='任务ID')
    # 任务名称 不能为空
    name = db.Column(db.String(255), nullable=False, comment='任务名称')
    # 任务执行的时间间隔（单位：秒）  不能为空
    interval_seconds = db.Column(db.Integer, nullable=False, comment='任务执行的时间间隔（单位：秒）')
    # 下一次任务执行的时间          可以为空
    next_run_time = db.Column(db.DateTime, nullable=True, comment='下一次任务执行的时间')

    # 时间类型  可以为空
    # weeks (int) – 间隔几周    days (int) – 间隔几天
    # hours (int) – 间隔几小时  minutes (int) – 间隔几分钟
    # seconds (int) – 间隔多少秒
    time_type = db.Column(db.String(255), nullable=False, comment='时间类型(字符串)')
    rtsp_list = db.Column(db.Text, nullable=False, comment='rtsp流')
    diagnosis_type_list = db.Column(db.Text, nullable=False, comment='诊断类型列表')
    scheduled_concent = db.Column(db.Text, nullable=False, comment='备注')
    scheduled_status = db.Column(db.Integer, nullable=False, comment='1 启用 0禁用')

    # 创建
    create_time = db.Column(db.DateTime, server_default=db.func.now(),comment='创建时间')

    def __repr__(self):
        return f'<ScheduledTask {self.name}>'

# 序列激活表
class Activate_info(db.Model,TimestampMixin):
    """序列激活表"""
    __tablename__ = 't_activate_info'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '序列激活表'
    }

    # 序列ID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='序列ID')
    # 用户名称
    activate_username = db.Column(db.String(255), comment='用户名称')
    # 公司
    activate_company = db.Column(db.String(255), comment='公司')
    # 国家
    activate_nation = db.Column(db.String(255), comment='国家')
    # 电话
    activate_mobile = db.Column(db.String(255), comment='电话')
    # 省
    activate_province = db.Column(db.String(255), comment='省')
    # 市
    activate_city = db.Column(db.String(255), comment='市')
    # 地址
    activate_address = db.Column(db.String(255), comment='地址')
    # 激活时间
    activate_time = db.Column(db.String(255), comment='激活时间')
    # 激活秘钥
    activate_key = db.Column(db.Text, comment='激活秘钥')
    # 激活码
    activate_encrypted_data = db.Column(db.Text, comment='激活码')
    # 激活状态
    activate_status = db.Column(db.String(255), comment='激活状态  0未激活 1激活')
    # 有效时间
    activate_valid_until = db.Column(db.String(255), comment='有效时间')

class Version(db.Model):
    """定时删除已删除的算法id对应报警结果"""
    __tablename__ = 't_version'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '平台版本表'
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.String(25),comment='平台版本号')

# 事件监听器
def register_all_listeners():
    Mine.register_listeners()

# 注册所有表的事件监听器
register_all_listeners()