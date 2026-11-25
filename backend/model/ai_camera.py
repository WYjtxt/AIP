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

class Algorithm_library_3588(db.Model):

    """算法仓表"""
    __tablename__ = "t_algorithm_library_3588"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法仓表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算法id')  # 整型的主键，会默认设置为自增主键
    algorithm_file_name =  db.Column(db.String(255),comment='文件名称')
    algorithm_file_path = db.Column(db.String(500), comment='算法文件存储路径')
    algorithm_name =  db.Column(db.String(255),comment='算法名称')
    algorithm_type =  db.Column(db.String(32),comment='算法类型 1（通用检测模型） 2（单类检测模型）')
    algorithm_type_list =  db.Column(db.Text,comment='算法检测类型，列表')
    algorithm_version =  db.Column(db.String(32),comment='算法版本')
    algorithm_status =  db.Column(db.String(32),server_default='1',comment='算法状态 1.运行 2.停止')
    algorithm_trade_type =  db.Column(db.String(32),server_default='1',comment='算法厂商 1.寒武纪 2.算能 3 华为')
    algorithm_path = db.Column(db.Text, comment='算法包路径')
    create_time = db.Column(db.DateTime, server_default=db.func.now(),comment='安装时间')
    algorithm_ps = db.Column(db.Text, comment='算法备注')
    model_type_name = db.Column(db.String(255), comment='模板大类名称')
    model_name = db.Column(db.String(255), comment='算法类型名称')
    template_small_name = db.Column(db.String(255), comment='模板小类名称')
    analysis_type = db.Column(db.String(255), comment='解析类型')

    # 父类 （用于标识算法包筛选）
    algorithm_parent = db.Column(db.String(10),comment='算法父类')
    # 子类 （用于标识算法包筛选）
    algorithm_child = db.Column(db.String(10),comment='算法子类')
    # equipment_id = db.Column(db.Integer,comment='设备id')
    # computing_resource_id = db.Column(db.Integer,comment='计算资源id')


class Algorithm_test_type_3588(db.Model):
    """检测类型表"""
    __tablename__ = "t_algorithm_test_type_3588"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '检测类型表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='检测类型id')  # 整型的主键，会默认设置为自增主键
    test_type_cname = db.Column(db.String(50), comment='检测类型中文名称')
    test_type_ename = db.Column(db.String(50), comment='检测类型英文名称')
    Algorithm_library_id = db.Column(db.Integer,comment='算法id')


class AlgorithmLibrary2Camera(db.Model):

    """算法仓表"""
    __tablename__ = "t_algorithmlibrary2camera"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '摄像头与算法关联表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    equipment_id = db.Column(db.Integer,comment='设备id')
    computing_resource_id = db.Column(db.Integer,comment='计算资源id')
    algorithm_libary_id = db.Column(db.Integer,comment='算法id')
    algorithm_camera_id = db.Column(db.Integer,comment='算法摄像头本地id')
    create_time = db.Column(db.DateTime, server_default=db.func.now(),comment='安装时间')




# 算法配置表
class Algorithm_config_3588(db.Model):

    """算法配置表"""
    __tablename__ = "t_algorithm_config_3588"

    # __table_args__ = {
    #     'mysql_engine': 'InnoDB',
    #     'comment': '算法配置表'
    # }

    __table_args__ = (

        Index('idx_algorithm_config_mine_id', 'Mine_id'),
        Index('idx_algorithm_config_equipment_id', 'Equipment_id'),
        Index('idx_algorithm_config_algorithm_library_id', 'Algorithm_library_id'),

        {
            'mysql_engine': 'InnoDB',
            'comment': '算法配置表'
        },

    )


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算法配置id')  # 整型的主键，会默认设置为自增主键
    conf_name = db.Column(db.String(32),comment='名称')
    Algorithm_library_id=  db.Column(db.Integer,comment='算法id')
    Mine_id = db.Column(db.Integer,comment='分析矿id')
    Equipment_id = db.Column(db.Integer,comment='分析矿监控点id')
    Algorithm_test_type_id = db.Column(db.Integer,comment='检测类型id')
    conf_object = db.Column(db.String(32),comment='分析对象')
    conf_area = db.Column(db.Text,comment='分析区域')
    status = db.Column(db.String(32),server_default='1',comment='算法配置算法运行状态 1 运行  2 停止')
    shield_status = db.Column(db.String(32),server_default='2',comment='遮挡参数 1 遮挡  2 未遮挡')
    conf_time = db.Column(db.DateTime, server_default=db.func.now(), comment='配置时间')
    tem_conf_area = db.Column(db.String(255),comment='热成像检测消除区域')
    tem_frames = db.Column(db.String(30),comment='温度阈值')
    confidence = db.Column(db.String(30),comment='置信度阈值')
    draw_type = db.Column(db.String(20),comment='绘制状态  1矩形 2线条')
    interval_time = db.Column(db.Integer,comment='报警间隔时间')
    Algorithm_config_ps = db.Column(db.Text, comment='算法配置备注')
    duration_time = db.Column(db.Integer, comment='持续时间')
    conf_img_resolution = db.Column(db.String(20),comment='算法配置图片分辨率')
    scene_typename = db.Column(db.String(255),comment='场景类型')
    image_draw_type = db.Column(db.Integer, comment=('图片结果矩形框  1. 绘制   2.不绘制'))
    sensitivity = db.Column(db.Integer, comment=('灵敏度'))
    model_status = db.Column(db.Integer, comment=('模型运行状态 1运行 2停止'))
    resource_id = db.Column(db.Integer, comment=('算力卡信息配置id'))
    update_time = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), comment='更新时间')
    defense_time_start = db.Column(db.String(30), comment=('布防时间起始'))
    defense_time_end = db.Column(db.String(30), comment=('布防时间结束'))
    res_type = db.Column(db.String(32), comment='报警类型   1 I级报警  2 II报警  3 III级报警')
    uwb_distance = db.Column(db.Integer, comment=('UWB距离'))   

    # 模板信息配置id
    model_template_config_id = db.Column(db.Integer, comment=('模板信息配置id'))
    model_template_type_id = db.Column(db.Integer, comment=('模板大类id'))
    template_list_area = db.Column(db.Text,comment='串行算法区域列表')
    image_count = db.Column(db.String(20), default='5', comment='图片数量')
    template_small_id = db.Column(db.Integer, comment='大类别下方模板id')
    conf_status = db.Column(db.Integer, comment=('数据变换状态'))
    count_time = db.Column(db.Integer, comment=('统计持续时间'))
    computing_id = db.Column(db.Integer, comment=('算力机器id'))
    template_data = db.Column(db.Text, comment=('模板数据'))
    label_list = db.Column(db.String(255), comment=('标签列表'))

    # 级联聚析（5）大类参数
    amp = db.Column(db.String(30),default=10,comment='扩增比例参数 （0-100）默认10')
    alg_select_type = db.Column(db.String(30),default=3,comment='裁剪/屏蔽/原图  1,2,3')
    model_two_data = db.Column(db.Text,default ='{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}',comment='级联聚析第二份参数')
    model_two_type = db.Column(db.String(30),comment='级联聚析算法包id')

    # 优先级参数
    priority = db.Column(db.String(30),comment='优先级等级1-10')
    run_time = db.Column(db.String(30),comment='单次运行时长')

    #单路多模算法配置参数
    model_algo_data_ori = db.Column(db.Text,comment='单路多模算法配置参数未处理版')
    model_algo_data = db.Column(db.Text,comment='单路多模算法配置参数')
    multimodels_type = db.Column(db.Integer,default=0,comment='多模算法类型标识')
    camera_config_id = db.Column(db.Integer,comment='摄像头配置id')
    sync_status = db.Column(db.String(20), default='pending', comment='同步状态: pending/synced/conflict/deleted')
    last_sync_time = db.Column(db.DateTime, comment='最后同步时间')
    config_version = db.Column(db.Integer, default=1, comment='配置版本号')
    sync_error = db.Column(db.Text, comment='同步错误信息')
    cross_line_area = db.Column(db.Text, comment='划线参数')
    #人员计数回传进入离开人数
    Entering_num = db.Column(db.String(100), comment='进入人数')
    Exiting_num = db.Column(db.String(100), comment='离开人数')
    all_Entering_num = db.Column(db.String(100), comment='累计进入人数')
    all_Exiting_num = db.Column(db.String(100), comment='累计离开人数')
    # ai摄像头标定算法配置标识 如果满足下方不能修改算法
    calibration_type = db.Column(db.String(20), comment='标定类型')



class Aicam_image_calibration(db.Model):

    """算法仓表"""
    __tablename__ = "t_aicam_image_calibration"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '摄像头标定关联表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    source_equipment_id = db.Column(db.Integer,comment='源相机id')
    target_equipment_id = db.Column(db.Integer,comment='目标相机id')
    homography_matrix = db.Column(db.Text, comment='标定矩阵')
    avg_test_err = db.Column(db.Float, comment='平均测试误差')


# AI摄像头心跳日志表
# class AICameraHeartbeatLog(db.Model):
#     """AI摄像头心跳日志表"""
#     __tablename__ = "t_ai_camera_heartbeat_log"
#     __table_args__ = (
#         Index('idx_ai_heartbeat_camera_id', 'camera_id'),
#         Index('idx_ai_heartbeat_time', 'heartbeat_time'),
#         {
#             'mysql_engine': 'InnoDB',
#             'comment': 'AI摄像头心跳日志表'
#         }
#     )

#     id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='日志ID')
#     camera_id = db.Column(db.Integer, comment='AI摄像头ID')
#     heartbeat_time = db.Column(db.DateTime, server_default=db.func.now(), comment='心跳时间')

#     # 状态信息
#     online_status = db.Column(db.Integer, comment='在线状态 1.在线 0.离线')
#     camera_status = db.Column(db.String(32), comment='设备状态')

#     # 系统信息
#     system_uptime = db.Column(db.String(50), comment='系统运行时长')
#     disk_usage = db.Column(db.Float, comment='磁盘使用率')
#     network_status = db.Column(db.String(32), comment='网络状态')

#     # 算法运行信息
#     running_algorithm_count = db.Column(db.Integer, comment='运行算法数量')
#     algorithm_status_list = db.Column(db.Text, comment='算法状态列表JSON')

#     # 错误信息
#     error_message = db.Column(db.Text, comment='错误信息')

class Model_template_config_type_3588(db.Model, TimestampMixin):
    """算法类型模板大类"""
    __tablename__ = "t_model_template_config_type_3588"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法类型模板大类表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    model_type_name = db.Column(db.String(255), comment='算法类型模板大类名称')
    model_type_content = db.Column(db.String(255), comment='算法类型模板大类描述')


# 算法类型模板表
class Model_template_config_3588(db.Model, TimestampMixin):
    """算法类型模板表"""
    __tablename__ = "t_model_template_config_3588"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法类型模板表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    model_name = db.Column(db.String(255), comment='算法类型名称')
    model_type = db.Column(db.String(255), comment='1 串行 2 单类')
    model_conf_list = db.Column(db.Text, comment='基础配置参数')
    image = db.Column(db.String(255), comment='算法图例')
    content = db.Column(db.Text, comment='算法备注')
    # {'key1':'1','key2':'2','key3':'3','key4':'4','key5':'5','key6':'6',}
    model_template_config_type_id = db.Column(db.Integer, comment='算法类型模板大类id')


# 大类别下方模板表
class Model_template_small_3588(db.Model, TimestampMixin):
    """大类别下方模板表"""
    __tablename__ = "t_model_template_small_3588"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '大类别下方模板表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    model_template_config_type_id = db.Column(db.Integer, comment='算法模板大类id')
    list_data = db.Column(db.Text,comment='数据列表')
    template_small_name = db.Column(db.String(100), comment='模板小类名称')
    template_small_number = db.Column(db.String(100), comment='告警数量')
    template_small_gauss = db.Column(db.String(100), comment='高斯参数1-25 int 奇数')
    template_small_threshold = db.Column(db.String(100), comment='二值化阈值 0-255 int')
    template_small_iou = db.Column(db.String(100), comment='iou 1-99')
    template_small_start = db.Column(db.String(100), comment='开始上报时间')
    template_small_end = db.Column(db.String(100), comment='结束上报时间')
    template_small_upload = db.Column(db.String(100), comment='上报时间间隔')