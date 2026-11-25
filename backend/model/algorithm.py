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



# 算法仓表
class Algorithm_library(db.Model):

    """算法仓表"""
    __tablename__ = "t_algorithm_library"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法仓表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算法id')  # 整型的主键，会默认设置为自增主键
    algorithm_file_name =  db.Column(db.String(255),comment='文件名称')
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




class Algorithm_test_type(db.Model):
    """检测类型表"""
    __tablename__ = "t_algorithm_test_type"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '检测类型表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='检测类型id')  # 整型的主键，会默认设置为自增主键
    test_type_cname = db.Column(db.String(50), comment='检测类型中文名称')
    test_type_ename = db.Column(db.String(50), comment='检测类型英文名称')
    Algorithm_library_id = db.Column(db.Integer,comment='算法id')


# 算法配置表
class Algorithm_config(db.Model):

    """算法配置表"""
    __tablename__ = "t_algorithm_config"

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
    stream_type = db.Column(db.String(8), nullable=True, comment='NULL沿用原地址 main主码流 sub子码流')
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
    #人员计数回传进入离开人数
    Entering_num = db.Column(db.String(100), comment='进入人数')
    Exiting_num = db.Column(db.String(100), comment='离开人数')
    all_Entering_num = db.Column(db.String(100), comment='累计进入人数')
    all_Exiting_num = db.Column(db.String(100), comment='累计离开人数')
    cross_line_area = db.Column(db.Text, comment='划线参数')

class Algorithm_config_history(db.Model):

    """算法配置历史记录表"""
    __tablename__ = "t_algorithm_config_history"
    __table_args__ = (

        Index('idx_algorithm_config_mine_id', 'Mine_id'),
        Index('idx_algorithm_config_equipment_id', 'Equipment_id'),
        Index('idx_algorithm_config_algorithm_library_id', 'Algorithm_library_id'),

        {
            'mysql_engine': 'InnoDB',
            'comment': '算法配置历史记录表'
        },

    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算法配置历史记录id')  # 整型的主键，会默认设置为自增主键
    conf_name = db.Column(db.String(255),comment='名称')
    stream_type = db.Column(db.String(8), nullable=True, comment='历史输入码流选择')

    conf_object = db.Column(db.String(32),comment='分析对象')
    conf_area = db.Column(db.Text,comment='分析区域')
    tem_conf_area = db.Column(db.String(255),comment='热成像检测消除区域')
    tem_frames = db.Column(db.String(30),comment='温度阈值')
    confidence = db.Column(db.String(30),comment='置信度阈值')
    interval_time = db.Column(db.Integer,comment='报警间隔时间')
    update_time = db.Column(db.DateTime, server_default=db.func.now(),comment='更新时间')
    Algorithm_config_ps = db.Column(db.Text, comment='算法配置备注')
    operation_type = db.Column(db.String(32), comment='操作类型')
    duration_time = db.Column(db.Integer, comment='持续时间')
    conf_img_resolution = db.Column(db.String(20),comment='算法配置图片分辨率')
    scene_typename = db.Column(db.String(255), comment='场景类型')
    sensitivity = db.Column(db.Integer, comment=('灵敏度'))

    status = db.Column(db.String(32),server_default='1',comment='算法配置算法运行状态 1 运行  2 停止')
    shield_status = db.Column(db.String(32),server_default='2',comment='遮挡参数 1 遮挡  2 未遮挡')
    image_draw_type = db.Column(db.Integer, comment=('图片结果矩形框  1. 绘制   2.不绘制'))
    draw_type = db.Column(db.String(20),comment='绘制状态  1矩形 2线条')

    conf_time = db.Column(db.DateTime, server_default=db.func.now(), comment='配置时间')
    defense_time_start = db.Column(db.String(30), comment=('布防时间起始'))
    defense_time_end = db.Column(db.String(30), comment=('布防时间结束'))


    Algorithm_library_id= db.Column(db.Integer,comment='算法id')
    Mine_id = db.Column(db.Integer,comment='分析矿id')
    Equipment_id = db.Column(db.Integer,comment='分析矿监控点id')
    Algorithm_test_type_id = db.Column(db.Integer,comment='检测类型id')
    config_id = db.Column(db.Integer, comment='配置id')
    resource_id = db.Column(db.Integer, comment=('算力卡信息配置id'))
    res_type = db.Column(db.String(32), comment='报警类型   1 I级报警  2 II报警  3 III级报警')
    # 模板信息配置id
    model_template_config_id = db.Column(db.Integer, comment=('模板信息配置id'))
    model_status = db.Column(db.Integer, comment=('模型运行状态 1运行 2等待  3异常 4停止'))
    # 串行算法区域列表
    template_list_area = db.Column(db.Text,comment='串行算法区域列表')
    # 返回图片数量
    image_count = db.Column(db.String(20), default='5', comment='图片数量')
    # 大类下方模板id
    template_small_id = db.Column(db.Integer, comment='大类别下方模板id')
    # 数据变换状态
    conf_status = db.Column(db.Integer, comment=('数据变换状态'))

    # 统计持续时间
    count_time = db.Column(db.Integer, comment=('统计持续时间'))




# 算法(预警)结果表
class Algorithm_result(db.Model):

    """算法结果表"""
    __tablename__ = "t_algorithm_result"
    __table_args__ = (

        # Index('t_algorithm_result_Algorithm_config_id_IDX', 'Algorithm_config_id'),
        # Index('t_algorithm_result_Mine_id_IDX', 'Mine_id'),
        # Index('t_algorithm_result_Equipment_id_IDX', 'Equipment_id'),
        # Index('t_algorithm_result_Equipment_parent_id_IDX', 'Equipment_parent_id'),
        # Index('t_algorithm_result_res_type_IDX', 'res_type'),

        Index('t_algorithm_result_res_time_IDX', 'res_time'),
        Index('idx_config_all', 'res_type', 'res_time', 'Algorithm_config_id','Equipment_id','Equipment_parent_id','Mine_id'),

        {
            'mysql_engine': 'InnoDB',
            'comment': '算法结果表'
        },
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='算法结果id')  # 整型的主键，会默认设置为自增主键
    Algorithm_config_id = db.Column(db.Integer,comment='算法配置id')
    res_type = db.Column(db.String(32), comment='报警类型   1 I级报警  2 II报警  3 III级报警')
    res_image = db.Column(db.String(255), comment='报警图片')
    res_video = db.Column(db.String(255), comment='报警视频')
    res_frame_skip = db.Column(db.String(32), comment='跳帧数')
    res_time = db.Column(db.DateTime, server_default=db.func.now(),comment='分析时间')
    res_result = db.Column(db.String(32),comment='分析结果')
    res_temperature = db.Column(db.Text,comment='测温数据   0位最大值 1位最小值 2位温度')
    xmin_xmax_ymin_ymax = db.Column(db.Text,comment='检测结果框点坐标')
    res_confidence = db.Column(db.Text,comment='置信度结果')
    Mine_id = db.Column(db.Integer,comment='分析矿id')  # 矿id
    Equipment_id = db.Column(db.Integer, comment='分析矿监控点id') # 监控点id
    Equipment_parent_id = db.Column(db.Integer, comment='分析矿父亲id') # 父亲id用于筛选
    # 轮播图图片路径
    carousel_images_list = db.Column(db.Text, comment='轮播图图片路径')

    # 原图轮播图图片路径
    ori_images_list = db.Column(db.Text, comment='轮播图图片路径 (原图) ')

    # 统计检测数量
    result_count = db.Column(db.String(100), comment='统计数量')
    # 统计时间段
    result_count_time = db.Column(db.DateTime,comment='统计时间段')

    template_type_id = db.Column(db.Integer, comment='模板大类id')
    template_id = db.Column(db.Integer, comment='模板id')
    Algorithm_library_id = db.Column(db.Integer, comment='算法id')
    Entering_num = db.Column(db.String(100), comment='进入人数')
    Exiting_num = db.Column(db.String(100), comment='离开人数')
    approval_status = db.Column(db.String(32), comment='审批状态 0正常 1误报',)
    disposal_status = db.Column(db.String(32), default=0,comment='处置状态 0待处理 1处理中 2已处理')
    approval_opinion = db.Column(db.Text, comment='审批意见')
    disposal_opinion = db.Column(db.Text, comment='处置措施')
    disposal_time = db.Column(db.DateTime, comment='处置时间')
    uwb_id = db.Column(db.String(100), comment='uwb数据-展示卡名字')

    conf_name = db.Column(db.String(255), comment='配置名称')
    conf_img_resolution = db.Column(db.String(255), comment='配置图片分辨率')
    algorithm_name = db.Column(db.String(255), comment='算法名称')
    equipment_name = db.Column(db.String(255), comment='监控点名称')
    equipment_type = db.Column(db.String(255), comment='监控点类型')
    mine_name = db.Column(db.String(255), comment='矿名称')
    warning_message = db.Column(db.String(255), comment='报警信息')
    warning_video = db.Column(db.String(255), comment='报警视频')
    analysis_type = db.Column(db.String(2), comment='人员计数-识别类型01,02,03')
    analysis_case = db.Column(db.String(4), comment='人员计数-识别结果0001,0002,0003')

# 诊断类型检测项表
class Diagnosis_type(db.Model):
    """诊断类型检测项表"""
    __tablename__ = 't_diagnosis_type'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '诊断类型检测项表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='检测项ID')
    name = db.Column(db.String(255), comment='检测项名称')
    prewarn = db.Column(db.String(25),server_default='30',comment='预警值')
    warn = db.Column(db.String(25),server_default='70',comment='报警值')
    create_time = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')



# 质量诊断数据表
class Diagnosis_data(db.Model):
    """质量诊断数据表"""
    __tablename__ = 't_diagnosis_data'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '质量诊断数据表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='诊断ID')
    equipment_id = db.Column(db.Integer, comment='监控点设备id')
    equipment_ip = db.Column(db.String(100), comment='监控点设备ip')
    equipment_name = db.Column(db.String(100), comment='监控点名称')
    vcr_ip = db.Column(db.String(100), comment='录像机ip')
    diagnosis_time = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now() , comment='诊断时间')
    diagnosis_type = db.Column(db.String(20), comment='诊断状态  达标 一般  很差  失败')
    db101 = db.Column(db.String(10), comment='视频抖动')
    db102 = db.Column(db.String(10), comment='条纹干扰')
    db103 = db.Column(db.String(10), comment='视频丢失')
    db104 = db.Column(db.String(10), comment='视频遮挡')
    db105 = db.Column(db.String(10), comment='视频冻结')
    db106 = db.Column(db.String(10), comment='高亮度')
    db107 = db.Column(db.String(10), comment='低亮度')
    db108 = db.Column(db.String(10), comment='视频噪声')
    db109 = db.Column(db.String(10), comment='偏色')
    db110 = db.Column(db.String(10), comment='清晰度')
    db111 = db.Column(db.String(10), comment='场景变化')
    db112 = db.Column(db.String(10), comment='对比度')
    db113 = db.Column(db.String(10), comment='横纹干扰')
    db114 = db.Column(db.String(10), comment='滚动条纹')
    db115 = db.Column(db.String(10), comment='横波干扰')
    db116 = db.Column(db.String(10), comment='花帧检测')
    diagnosis_pic = db.Column(db.String(255), comment='诊断图片')
    diagnosis_reason = db.Column(db.String(512), nullable=True, comment='诊断失败或未完成原因')
    parent_name = db.Column(db.String(255), comment='父类设备名称')
    create_time = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')


# 质量诊断历史数据表
class Diagnosis_data_old(db.Model):
    """质量诊断数据表"""
    __tablename__ = 't_diagnosis_data_old'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '质量诊断历史数据表'
    }


    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='诊断ID')
    equipment_id = db.Column(db.Integer, comment='监控点设备id')
    equipment_ip = db.Column(db.String(100), comment='监控点设备ip')
    equipment_name = db.Column(db.String(100), comment='监控点名称')
    vcr_ip = db.Column(db.String(100), comment='录像机ip')
    diagnosis_type = db.Column(db.String(20), comment='诊断状态  达标 一般  很差  失败')
    db101 = db.Column(db.String(10), comment='视频抖动')
    db102 = db.Column(db.String(10), comment='条纹干扰')
    db103 = db.Column(db.String(10), comment='视频丢失')
    db104 = db.Column(db.String(10), comment='视频遮挡')
    db105 = db.Column(db.String(10), comment='视频冻结')
    db106 = db.Column(db.String(10), comment='高亮度')
    db107 = db.Column(db.String(10), comment='低亮度')
    db108 = db.Column(db.String(10), comment='视频噪声')
    db109 = db.Column(db.String(10), comment='偏色')
    db110 = db.Column(db.String(10), comment='清晰度')
    db111 = db.Column(db.String(10), comment='场景变化')
    db112 = db.Column(db.String(10), comment='对比度')
    db113 = db.Column(db.String(10), comment='横纹干扰')
    db114 = db.Column(db.String(10), comment='滚动条纹')
    db115 = db.Column(db.String(10), comment='横波干扰')
    db116 = db.Column(db.String(10), comment='花帧检测')
    diagnosis_pic = db.Column(db.String(255), comment='诊断图片')
    diagnosis_reason = db.Column(db.String(512), nullable=True, comment='诊断失败或未完成原因')
    parent_name = db.Column(db.String(255), comment='父类设备名称')
    create_time = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')

class Model_template_config_type(db.Model, TimestampMixin):
    """算法类型模板大类"""
    __tablename__ = "t_model_template_config_type"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法类型模板大类表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='id')  # 整型的主键，会默认设置为自增主键
    model_type_name = db.Column(db.String(255), comment='算法类型模板大类名称')
    model_type_content = db.Column(db.String(255), comment='算法类型模板大类描述')


# 算法类型模板表
class Model_template_config(db.Model, TimestampMixin):
    """算法类型模板表"""
    __tablename__ = "t_model_template_config"
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
class Model_template_small(db.Model, TimestampMixin):
    """大类别下方模板表"""
    __tablename__ = "t_model_template_small"
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

# 算法运行状态表
class Algorithm_run_status(db.Model):
    """算法运行状态表"""
    __tablename__ = 't_algorithm_run_status'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法运行状态表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conf_name = db.Column(db.String(100))
    alarm_start_time = db.Column(db.String(100))
    send_flag = db.Column(db.Integer)

class Algorithm_result_delete(db.Model):
    """定时删除已删除的算法id对应报警结果"""
    __tablename__ = 't_algorithm_result_delete'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '已删除算法id表'
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    algorithm_id = db.Column(db.Integer,comment='已删除算法id')


class Algorithm_result_warning_message(db.Model):
    """定时删除已删除的算法id对应报警结果"""
    __tablename__ = 't_algorithm_result_warning_message'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '报警信息表'
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    algorithm_name = db.Column(db.String(100),comment='算法类型名字')
    template_type_id = db.Column(db.Integer, comment='模板大类id')
    warning_message = db.Column(db.Text, comment='报警信息')
    message_index = db.Column(db.Integer, comment='报警序号（同一算法下从1开始递增，用于前端展示和标识）')
