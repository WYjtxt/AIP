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
from model.admin import TimestampMixin

local_tz = pytz.timezone('Asia/Shanghai')

# 录像机同步表
class VCR_data(db.Model):
    """录像机同步表"""
    __tablename__ = "t_vcr_data"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '录像机同步表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='录像机id')  # 整型的主键，会默认设置为自增主键
    vcr_type = db.Column(db.Enum('海康', '大华','索尼','宇视','天地伟业','三星'),comment='厂商类型')
    vcr_way = db.Column(db.Enum('私有SDK', 'Onvif','GB28181'),comment='接入方式')
    vcr_name = db.Column(db.String(50), comment='录像机名称')
    vcr_ip = db.Column(db.String(50), comment='录像机ip')
    vcr_username = db.Column(db.String(50), comment='录像机用户')
    vcr_password = db.Column(db.String(50), comment='录像机密码')
    vcr_port = db.Column(db.String(50), comment='录像机端口')
    vcr_status = db.Column(db.String(50), comment='录像机同步状态 1 同步完成 2 同步未完成' )
    Mine_id = db.Column(db.Integer,comment='矿名称id')
    create_time = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')
    online = db.Column(db.Integer,comment='是否在线  1 在线  0 离线')
    type = db.Column(db.String(50), comment='录像机/CVR 1录像机 2CVR')

# 设备表
class Equipment(db.Model):

    """设备表"""
    __tablename__ = "t_equipment"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '设备表'
    }


    id = db.Column(db.Integer, primary_key=True,autoincrement=True,comment='设备id')  # 整型的主键，会默认设置为自增主键
    equipment_type = db.Column(db.Enum('摄像头','录像机','特殊摄像头','安防平台','浙江双视热成像','紫光华智','视频中心存储','AI单光摄像头','AI双光摄像头'),comment='设备类型')
    manufacturer_type = db.Column(db.Enum('海康', '大华','索尼','宇视','天地伟业','三星','浙江双视','紫光华智','艾斯卡普','阳光三极'),comment='厂商类型')
    equipment_name = db.Column(db.String(255),comment='设备名称')
    # equipment_ip = db.Column(db.String(32),unique=True,comment='IP地址')
    equipment_ip = db.Column(db.String(32),comment='IP地址')
    equipment_uname = db.Column(db.String(32),comment='用户名')
    equipment_password = db.Column(db.String(255),comment='密码')
    equipment_aisles = db.Column(db.Integer,comment='通道')
    equipment_codetype = db.Column(db.Enum('H265','H264','MJPEG'),comment='码流类型')
    equipment_width_height = db.Column(db.String(255),comment='视频分辨率')
    equipment_constantBitRate = db.Column(db.String(255),comment='视频码率')
    equipment_maxFrameRate = db.Column(db.String(255),comment='视频帧率')
    equipment_port = db.Column(db.Integer,comment='端口')
    user_status = db.Column(db.String(32),server_default='1',comment='设备状态 1.启用 0.禁用')
    flower_frames = db.Column(db.String(20),comment='花帧阈值')
    Hik_rtsp_url = db.Column(db.Text,comment='安防平台长时效性url')
    Hik_indexCode = db.Column(db.String(255),unique=True,comment='安防平台监控点编号')
    Hik_id = db.Column(db.Integer,comment='安防平台上级区域id')
    code = db.Column(db.String(255),comment='录像机子集默认通道配置')
    parent_id = db.Column(db.Integer,comment='录像机父id')
    Mine_id = db.Column(db.Integer,comment='矿名称id')
    VCR_data_id = db.Column(db.Integer,comment='录像机同步id，用于查找同步设备及下方子设备')
    online = db.Column(db.Integer,comment='是否在线  1 在线  0 离线')
    duration_time = db.Column(db.String(255), comment='设备离线持续时间')
    create_time = db.Column(db.DateTime, server_default=db.func.now(),comment='创建时间')
    Ziguang_ape_indexCode = db.Column(db.String(255),unique=True,comment='紫光华智监控点编号')
    Ziguang_ape_rtsp_url =  db.Column(db.Text,comment='紫光华智时效性url')
    Ziguang_id = db.Column(db.Integer,comment='紫光华智平台id')
    Onvif_rtsp_url = db.Column(db.Text,comment='onvif协议url')
    GB28181_code = db.Column(db.String(255),comment='GB28181通道编码')
    person_count_url = db.Column(db.Text,comment='人员统计url')
    alarm_device_ip = db.Column(db.String(255),comment='报警设备ip')
    # 外键（关联t_zlk_data表的id）
    zlk_dat_id = db.Column(db.Integer, db.ForeignKey('t_zlk_data.id'), comment='ZLK流媒体数据id', nullable=True, unique=True)
    # zlk_data = db.relationship('Zlk_data', backref='equipment', lazy=True, cascade="all, delete-orphan")
    # 一对一关系配置

    # 一对一关系映射：关联Zlk_data，双向查询用back_populates绑定
    zlk_data = db.relationship(
        'Zlk_data',
        back_populates='equipment',
        lazy='joined',
        cascade="all",
        single_parent=True,
        uselist=False  # 明确一对一，返回单个对象
    )
    uwb_ip = db.Column(db.String(32), comment='读卡器IP(绑定摄像头ip)')

# 离线信息表
class Offline_info(db.Model):
    """离线信息表"""
    __tablename__ = "t_offline_info"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '设备离线信息表'
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='离线信息id')
    equipment_id = db.Column(db.Integer, comment='设备id')
    create_time = db.Column(db.DateTime,server_default=db.func.now(),comment='创建时间')
    equipment_ip = db.Column(db.String(32), server_default=None, comment='设备ip')

# 海康安防平台信息表
class Hik_security_platform_info(db.Model,TimestampMixin):
    """海康安防平台信息表"""
    __tablename__ = "t_hik_security_platform_info"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '海康安防平台信息表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    hik_name = db.Column(db.String(255), comment='安防平台主区域名称')
    hik_host = db.Column(db.String(50), comment='安防平台接入ip地址')
    hik_port = db.Column(db.String(50), comment='安防平台接入ip端口')
    hik_appKey = db.Column(db.String(255), comment='安防平台接入appKey')
    hik_appSecret = db.Column(db.String(255), comment='安防平台接入appSecret')
    hik_artemis = db.Column(db.String(255),server_default='artemis',comment='安防平台规定地址')
    hik_status = db.Column(db.String(50), comment='安防平台同步状态  1 同步成功 0同步失败')
    hik_methon = db.Column(db.String(50),server_default='POST',comment='安防平台请求方式')
    Mine_id = db.Column(db.Integer,comment='矿名称id')


# 海康安防平台上级区域表
class Hik_security_platform_up_area(db.Model,TimestampMixin):
    """海康安防平台上级区域表"""
    __tablename__ = "t_hik_security_platform_up_area"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '海康安防平台上级区域表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    indexCode = db.Column(db.Text, comment='区域编号')
    nodeType = db.Column(db.String(255), comment='节点类型')
    name = db.Column(db.String(255), comment='区域名称')
    regionPath = db.Column(db.String(255), comment='区域完整目录')
    parentIndexCode = db.Column(db.Text, comment='父区域唯一标识码')
    cascadeType = db.Column(db.String(255),comment='区域标识 0：本级 1：级联 2：混合')
    externalIndexCode = db.Column(db.Text, comment='外码(如：国际码)')
    sort = db.Column(db.String(255),comment='同级区域顺序')
    hik_createTime = db.Column(db.DateTime,comment='创建时间，要求遵守ISO8601标准，如2018-07-26T21:30:08.322+08:00')
    hik_updateTime = db.Column(db.DateTime,comment='创建时间，要求遵守ISO8601标准，如2018-07-26T21:30:08.322+08:00')
    available = db.Column(db.Integer,comment='用于标识区域节点是否有权限操作，true：有权限 false：无权限')
    leaf = db.Column(db.String(255),comment='true:是叶子节点，表示该区域下面未挂区域 false:不是叶子节点，表示该区域下面挂有区域')
    catalogType = db.Column(db.String(255),comment='区域类型， 国标区域：0， 雪亮工程区域：1， 司法行政区域：2， 自定义区域')
    cascadeCode = db.Column(db.String(255),comment='级联平台标识，多个级联编号以@分隔，本级区域默认值“0”')
    hik_info_id = db.Column(db.Integer,comment='安防平台信息id')
    Mine_id = db.Column(db.Integer, comment='矿名称id')


# 算力设备表
class Computing_equipment(db.Model,TimestampMixin):
    """算力设备表"""
    __tablename__ = 't_computing_equipment'
    id = db.Column(db.Integer, primary_key=True)
    computing_ip = db.Column(db.String(50),comment='算力设备ip')  # 算力设备ip
    computing_name = db.Column(db.String(50),comment='算力设备名称')  # 算力设备名称
    computing_code = db.Column(db.String(50),comment='设备编码')  # 设备编码
    computing_user = db.Column(db.String(50),comment='设备登录用户名')  # 机器登录用户名
    computing_password = db.Column(db.String(50),comment='设备登录密码')  # 机器登录密码
    computing_status = db.Column(db.Integer,comment='设备状态1 在线 2 离线 3 账密错误')
    server_type = db.Column(db.Integer,comment='设备类型 1服务器 2摄像头')

# 为 Computing_equipment 模型添加事件监听器，实现自定义 id 分配
@event.listens_for(Computing_equipment, 'before_insert')
def before_insert_computing_equipment(mapper, connection, target):
    # 查询当前最大的 id 值
    max_id = connection.execute(
        db.select(db.func.max(Computing_equipment.id))
    ).scalar()
    # 如果没有记录，设置 id 为 1，否则设置为最大 id + 1
    target.id = 1 if max_id is None else max_id + 1


# 机器算力信息表
class Resource_usage(db.Model, TimestampMixin):
    """序列激活表"""
    __tablename__ = 't_resource_usage'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '机器算力信息表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算力设备id')
    dev_ip = db.Column(db.String(100), comment='算力设备ip')
    dev_id = db.Column(db.Integer, comment='对应卡数id')
    dev_get_sn = db.Column(db.String(255), comment='标识设备的序列码 sn')
    dev_get_target = db.Column(db.String(100), comment='智能视觉深度学习处理器型号 例如-bm1684x')
    board_temp = db.Column(db.String(100), comment='板温度')
    chip_temp = db.Column(db.String(100), comment='芯片温度')
    mem_used_mem_total = db.Column(db.String(100), comment='算力容量')
    memory_usage_rate = db.Column(db.String(100), comment='算力占用比例')
    tpu_util = db.Column(db.String(100), comment='tpu利用率')
    resource_num = db.Column(db.Integer, server_default='0', comment='算力卡配置数量')
    computing_id = db.Column(db.Integer, comment='机器设备id')


# 紫光华智数据同步表
class Ziguanhhuazhi_data(db.Model):
    """紫光华智数据同步表"""
    __tablename__ = "t_ziguanhhuazhi" \
                    "_data"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '紫光华智数据同步表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='紫光华智数据id')  # 整型的主键，会默认设置为自增主键
    ziguang_name = db.Column(db.String(50), comment='紫光华智数据名称')
    ziguang_ip = db.Column(db.String(50), comment='紫光华智数据ip')
    ziguang_id = db.Column(db.String(255), comment='紫光华智数据合作方id')
    ziguang_password = db.Column(db.String(255), comment='紫光华智数据合作方密码')
    ziguang_port = db.Column(db.String(50), comment='紫光华智数据端口')
    ziguang_status = db.Column(db.String(50), comment='紫光华智同步状态 1 同步完成 2 同步未完成' )
    Mine_id = db.Column(db.Integer,comment='矿名称id')
    create_time = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')