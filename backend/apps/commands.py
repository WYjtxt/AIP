# 预制数据文件

from flask import Blueprint
from flask.cli import with_appcontext
from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *

import json

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value


cli = Blueprint('cli', __name__)

# 模型类型数据预置
@cli.cli.command('insert_predefined_data')
@with_appcontext
def insert_predefined_data_command():
    if not Menu.query.first():

        meuu_data = [


            {'id':1,'menu_name':'慧聚视频综览','menu_link':None,'menu_icon':'el-icon-video-camera','menu_order':1,'menu_parent_id':None,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':2,'menu_name':'海康摄像头','menu_link':'hksxt','menu_icon':'el-icon-video-camera','menu_order':2,'menu_parent_id':1,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id': 3, 'menu_name': '海康录像机', 'menu_link': 'sssp', 'menu_icon': 'el-icon-video-camera', 'menu_order': 3,
             'menu_parent_id': 1,'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 4, 'menu_name': '海康安防平台', 'menu_link': 'hkaf', 'menu_icon': 'el-icon-video-camera',
             'menu_order': 4,'menu_parent_id': 1,'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 5, 'menu_name': '实时预览', 'menu_link': 'jsyl', 'menu_icon': 'el-icon-video-camera',
             'menu_order': 5,'menu_parent_id': 1,'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},

            {'id':6,'menu_name':'报警信息','menu_link':None,'menu_icon':'el-icon-warning-outline','menu_order':6,'menu_parent_id':None,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':7,'menu_name':'报警列表','menu_link':'bjlb','menu_icon':'el-icon-warning-outline','menu_order':7,'menu_parent_id':6,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':8,'menu_name':'报警统计','menu_link':'bjtj','menu_icon':'el-icon-warning-outline','menu_order':8,'menu_parent_id':6,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},

            {'id':9,'menu_name':'算法仓','menu_link':None,'menu_icon':'el-icon-monitor','menu_order':9,'menu_parent_id':None,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id': 10, 'menu_name': '智能算法安装', 'menu_link': 'sfc', 'menu_icon': 'el-icon-monitor', 'menu_order': 10,'menu_parent_id': 9,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id':11,'menu_name':'智能算法配置','menu_link':'sfgl','menu_icon':'el-icon-monitor','menu_order':11,'menu_parent_id':9,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id': 12, 'menu_name': 'AI摄像仪算法安装', 'menu_link': 'sxtsf', 'menu_icon': 'el-icon-monitor',
             'menu_order':12, 'menu_parent_id': 9,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 13, 'menu_name': 'AI摄像仪算法配置', 'menu_link': 'sxtpz', 'menu_icon': 'el-icon-monitor',
             'menu_order': 13, 'menu_parent_id': 9,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},


            {'id':14,'menu_name':'设备管理','menu_link':None,'menu_icon':'el-icon-full-screen','menu_order':14,'menu_parent_id':None,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':15,'menu_name':'摄像头同步','menu_link':'sbtj','menu_icon':'el-icon-full-screen','menu_order':15,'menu_parent_id':14,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':16,'menu_name':'录像机设备同步','menu_link':'sbtb','menu_icon':'el-icon-full-screen','menu_order':16,'menu_parent_id':14,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id': 17, 'menu_name': '视频中心存储设备同步', 'menu_link': 'spcctb', 'menu_icon': 'el-icon-full-screen',
             'menu_order': 17, 'menu_parent_id': 14,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 18, 'menu_name': '安防平台同步', 'menu_link': 'hkaf_sbtb', 'menu_icon': 'el-icon-video-camera',
             'menu_order': 18,'menu_parent_id': 14,'menu_permission_list':json.dumps([1,2]), 'menu_status': '1'},
            {'id': 19, 'menu_name': '紫光华智平台同步', 'menu_link': 'zghzpttb', 'menu_icon': None, 'menu_order': 19,
             'menu_parent_id': 14,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 20, 'menu_name': '算力设备同步', 'menu_link': 'slsbzx', 'menu_icon': 'el-icon-video-camera',
             'menu_order': 20,
             'menu_parent_id': 14, 'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},



            {'id':21,'menu_name':'视频质量诊断','menu_link':None,'menu_icon':'el-icon-cpu','menu_order':21,'menu_parent_id':None,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':22,'menu_name':'预案配置','menu_link':'spzlzdpz','menu_icon':'el-icon-cpu','menu_order':22,'menu_parent_id':21,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},
            {'id':23,'menu_name':'诊断结果','menu_link':'spzlzd','menu_icon':'el-icon-cpu','menu_order':23,'menu_parent_id':21,
             'menu_permission_list':json.dumps([1,2]),'menu_status':'1'},

            {'id': 24, 'menu_name': '视频分析', 'menu_link': 'spfx', 'menu_icon': None, 'menu_order': 24,
             'menu_parent_id': None,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},


            {'id': 25, 'menu_name': '算法模板匹配', 'menu_link': None, 'menu_icon': None, 'menu_order': 25,
             'menu_parent_id': None,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 26, 'menu_name': '算法匹配', 'menu_link': 'modellist', 'menu_icon': None, 'menu_order': 26,
             'menu_parent_id': 25,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 27, 'menu_name': '算法体系', 'menu_link': 'modelbig', 'menu_icon': None, 'menu_order': 27,
             'menu_parent_id': 25,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 28, 'menu_name': '算法子类', 'menu_link': 'modelsmall', 'menu_icon': None, 'menu_order': 28,
             'menu_parent_id': 25,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},


            {'id': 29, 'menu_name': '云管中心', 'menu_link': None, 'menu_icon': 'el-icon-video-camera', 'menu_order': 29,
             'menu_parent_id': None, 'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 30, 'menu_name': '设备监测中心', 'menu_link': 'ygzx', 'menu_icon': 'el-icon-video-camera',
             'menu_order': 30,
             'menu_parent_id': 29, 'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},

            {'id': 31, 'menu_name': '日志管理', 'menu_link': None, 'menu_icon': None, 'menu_order': 31,
             'menu_parent_id': None,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 32, 'menu_name': '平台日志', 'menu_link': 'rzgl', 'menu_icon': None, 'menu_order': 32,
             'menu_parent_id': 31,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 33, 'menu_name': '登录日志', 'menu_link': 'dlrz', 'menu_icon': None, 'menu_order': 33,
             'menu_parent_id': 31,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 34, 'menu_name': '算法日志', 'menu_link': 'sfrz', 'menu_icon': None, 'menu_order': 34,
             'menu_parent_id': 31,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},


            {'id': 35, 'menu_name': '系统管理', 'menu_link': None, 'menu_icon': None, 'menu_order': 35,
             'menu_parent_id': None,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 36, 'menu_name': '用户管理', 'menu_link': 'user', 'menu_icon': None, 'menu_order': 36,
             'menu_parent_id': 35,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 37, 'menu_name': '角色管理', 'menu_link': 'role', 'menu_icon': None, 'menu_order': 37,
             'menu_parent_id': 35,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 38, 'menu_name': '字典管理', 'menu_link': 'dict', 'menu_icon': None, 'menu_order':38,
             'menu_parent_id': 35,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 39, 'menu_name': '菜单管理', 'menu_link': 'menu', 'menu_icon': None, 'menu_order': 39,
             'menu_parent_id': 35,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 40, 'menu_name': '信息管理', 'menu_link': 'mkxxgl', 'menu_icon': None, 'menu_order': 40,
             'menu_parent_id': 35,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
            {'id': 41, 'menu_name': '流媒体管理', 'menu_link': 'lmtgl', 'menu_icon': None, 'menu_order': 41,
             'menu_parent_id': None,
             'menu_permission_list': json.dumps([1, 2]), 'menu_status': '1'},
        ]

        for i in meuu_data:
            menu_res = Menu(id=i['id'],menu_name=i['menu_name'],menu_link=i['menu_link'],menu_order=i['menu_order'],menu_icon=i['menu_icon'],
                            menu_parent_id=i['menu_parent_id'],menu_permission_list=i['menu_permission_list'],menu_status=i['menu_status'])
            db.session.add(menu_res)
        db.session.commit()
        print('菜单预置数据插入完成！')

    if not Permission.query.first():

        permission_data = [
            {'id':1,'permission_name':'超级管理员','permission_code':None,'permission_content':'增删改查','permission_status':'1'},
            {'id':2,'permission_name':'普通用户','permission_code':None,'permission_content':'增删改查','permission_status':'1'},
        ]

        for i in permission_data:
            permission_res = Permission(id=i['id'],permission_name=i['permission_name'],permission_code=i['permission_code'],
                                        permission_content=i['permission_content'],permission_status=i['permission_status'])
            db.session.add(permission_res)
        db.session.commit()

        print('权限数据预置数据插入完成！')


    if not User.query.first():

        User_data = [
            {'id':1,'name':'超级管理员','username':'admin','password':_required_site_value("AIP_INITIAL_ADMIN_PASSWORD"),'user_status':'1','free_secret':'1'},
            {'id':2,'name':'管理员','username':'admin123','password':_required_site_value("AIP_INITIAL_SECONDARY_PASSWORD"),'user_status':'1','free_secret':'0'},
        ]

        for i in User_data:
            User_res = User(id=i['id'],username=i['username'],password=password_encryption(i['password']),name=i['name'],user_status=i['user_status'])
            db.session.add(User_res)
        db.session.commit()

        print('用户预置数据插入完成！')


    if not UserPermission.query.first():

        UserPermission_data = [
            {'id':1,'user_id':1,'permission_id':1,},
            {'id':2,'user_id':2,'permission_id':2,},
        ]

        for i in UserPermission_data:
            user_permission_res = UserPermission(id=i['id'],user_id=i['user_id'],permission_id=i['permission_id'])
            db.session.add(user_permission_res)
        db.session.commit()

        print('用户权限预置数据插入完成！')

    if not PermissionMenu.query.first():

        Permission_menu_data = [
            {'id':1,'premission_id':1,'menu_id':1,'permissions_list':'[c,r,u,d]'},
            {'id':2,'premission_id':1,'menu_id':2,'permissions_list':'[c,r,u,d]'},
            {'id':3,'premission_id':1,'menu_id':3,'permissions_list':'[c,r,u,d]'},
            {'id':4,'premission_id':1,'menu_id':4,'permissions_list':'[c,r,u,d]'},
            {'id':5,'premission_id':1,'menu_id':5,'permissions_list':'[c,r,u,d]'},
            {'id':6,'premission_id':1,'menu_id':6,'permissions_list':'[c,r,u,d]'},
            {'id':7,'premission_id':1,'menu_id':7,'permissions_list':'[c,r,u,d]'},
            {'id':8,'premission_id':1,'menu_id':8,'permissions_list':'[c,r,u,d]'},
            {'id':9,'premission_id':1,'menu_id':9,'permissions_list':'[c,r,u,d]'},
            {'id':10,'premission_id':1,'menu_id':10,'permissions_list':'[c,r,u,d]'},
            {'id':11,'premission_id':1,'menu_id':11,'permissions_list':'[c,r,u,d]'},
            {'id':12,'premission_id':1,'menu_id':12,'permissions_list':'[c,r,u,d]'},
            {'id':13,'premission_id':1,'menu_id':13,'permissions_list':'[c,r,u,d]'},
            {'id': 14, 'premission_id': 1, 'menu_id': 14, 'permissions_list': '[c,r,u,d]'},
            {'id': 15, 'premission_id': 1, 'menu_id': 15, 'permissions_list': '[c,r,u,d]'},
            {'id': 16, 'premission_id': 1, 'menu_id': 16, 'permissions_list': '[c,r,u,d]'},
            {'id': 17, 'premission_id': 1, 'menu_id': 17, 'permissions_list': '[c,r,u,d]'},
            {'id': 18, 'premission_id': 1, 'menu_id': 18, 'permissions_list': '[c,r,u,d]'},
            {'id': 19, 'premission_id': 1, 'menu_id': 19, 'permissions_list': '[c,r,u,d]'},
            {'id': 20, 'premission_id': 1, 'menu_id': 20, 'permissions_list': '[c,r,u,d]'},
            {'id': 21, 'premission_id': 1, 'menu_id': 21, 'permissions_list': '[c,r,u,d]'},
            {'id': 22, 'premission_id': 1, 'menu_id': 22, 'permissions_list': '[c,r,u,d]'},
            {'id': 23, 'premission_id': 1, 'menu_id': 23, 'permissions_list': '[c,r,u,d]'},
            {'id': 24, 'premission_id': 1, 'menu_id': 24, 'permissions_list': '[c,r,u,d]'},
            {'id': 25, 'premission_id': 1, 'menu_id': 25, 'permissions_list': '[c,r,u,d]'},
            {'id': 26, 'premission_id': 1, 'menu_id': 26, 'permissions_list': '[c,r,u,d]'},
            {'id': 27, 'premission_id': 1, 'menu_id': 27, 'permissions_list': '[c,r,u,d]'},
            {'id': 28, 'premission_id': 1, 'menu_id': 28, 'permissions_list': '[c,r,u,d]'},
            {'id': 29, 'premission_id': 1, 'menu_id': 29, 'permissions_list': '[c,r,u,d]'},
            {'id': 30, 'premission_id': 1, 'menu_id': 30, 'permissions_list': '[c,r,u,d]'},
            {'id': 31, 'premission_id': 1, 'menu_id': 31, 'permissions_list': '[c,r,u,d]'},
            {'id': 32, 'premission_id': 1, 'menu_id': 32, 'permissions_list': '[c,r,u,d]'},
            {'id': 33, 'premission_id': 1, 'menu_id': 33, 'permissions_list': '[c,r,u,d]'},
            {'id': 34, 'premission_id': 1, 'menu_id': 34, 'permissions_list': '[c,r,u,d]'},
            {'id': 35, 'premission_id': 1, 'menu_id': 35, 'permissions_list': '[c,r,u,d]'},
            {'id': 36, 'premission_id': 1, 'menu_id': 36, 'permissions_list': '[c,r,u,d]'},
            {'id': 37, 'premission_id': 1, 'menu_id': 37, 'permissions_list': '[c,r,u,d]'},
            {'id': 38, 'premission_id': 1, 'menu_id': 38, 'permissions_list': '[c,r,u,d]'},
            {'id': 39, 'premission_id': 1, 'menu_id': 39, 'permissions_list': '[c,r,u,d]'},

            {'id': 40, 'premission_id': 2, 'menu_id': 1, 'permissions_list': '[c,r,u,d]'},
            # {'id': 41, 'premission_id': 2, 'menu_id': 2, 'permissions_list': '[c,r,u,d]'},
            # {'id': 42, 'premission_id': 2, 'menu_id': 3, 'permissions_list': '[c,r,u,d]'},
            {'id': 43, 'premission_id': 2, 'menu_id': 4, 'permissions_list': '[c,r,u,d]'},
            {'id': 44, 'premission_id': 2, 'menu_id': 5, 'permissions_list': '[c,r,u,d]'},
            {'id': 45, 'premission_id': 2, 'menu_id': 6, 'permissions_list': '[c,r,u,d]'},
            {'id': 46, 'premission_id': 2, 'menu_id': 7, 'permissions_list': '[c,r,u,d]'},
            {'id': 47, 'premission_id': 2, 'menu_id': 8, 'permissions_list': '[c,r,u,d]'},
            {'id': 48, 'premission_id': 2, 'menu_id': 9, 'permissions_list': '[c,r,u,d]'},
            {'id': 49, 'premission_id': 2, 'menu_id': 10, 'permissions_list': '[c,r,u,d]'},
            {'id': 50, 'premission_id': 2, 'menu_id': 11, 'permissions_list': '[c,r,u,d]'},
            {'id': 51, 'premission_id': 2, 'menu_id': 12, 'permissions_list': '[c,r,u,d]'},
            {'id': 52, 'premission_id': 2, 'menu_id': 13, 'permissions_list': '[c,r,u,d]'},
            {'id': 53, 'premission_id': 2, 'menu_id': 14, 'permissions_list': '[c,r,u,d]'},
            {'id': 54, 'premission_id': 2, 'menu_id': 15, 'permissions_list': '[c,r,u,d]'},
            {'id': 55, 'premission_id': 2, 'menu_id': 16, 'permissions_list': '[c,r,u,d]'},
            {'id': 56, 'premission_id': 2, 'menu_id': 17, 'permissions_list': '[c,r,u,d]'},
            {'id': 57, 'premission_id': 2, 'menu_id': 18, 'permissions_list': '[c,r,u,d]'},
            {'id': 58, 'premission_id': 2, 'menu_id': 19, 'permissions_list': '[c,r,u,d]'},
            {'id': 59, 'premission_id': 2, 'menu_id': 20, 'permissions_list': '[c,r,u,d]'},
            {'id': 60, 'premission_id': 2, 'menu_id': 21, 'permissions_list': '[c,r,u,d]'},
            {'id': 61, 'premission_id': 2, 'menu_id': 22, 'permissions_list': '[c,r,u,d]'},

            {'id': 62, 'premission_id': 2, 'menu_id': 27, 'permissions_list': '[c,r,u,d]'},
            {'id': 63, 'premission_id': 2, 'menu_id': 28, 'permissions_list': '[c,r,u,d]'},


        ]

        for i in Permission_menu_data:
            permission_menu_res = PermissionMenu(id=i['id'],premission_id=i['premission_id'],menu_id=i['menu_id'],permissions_list=i['permissions_list'])
            db.session.add(permission_menu_res)
        db.session.commit()

        print('权限菜单预置数据插入完成！')


    if not Dict_data.query.first():

        # dict_type = [
        #     {'id':1,'type_name':'矿名编码表','type_code':'1','enable':'1'},
        #     {'id': 2, 'type_name': '算法类型编码表', 'type_code': '2', 'enable': '1'},
        #     {'id': 3, 'type_name': '厂商编码表', 'type_code': '3', 'enable': '1'}
        # ]
        dict_type = [
            {'type_name':'矿名编码表','type_code':'1','enable':'1'},
            { 'type_name': '算法类型编码表', 'type_code': '2', 'enable': '1'},
            {'type_name': '厂商编码表', 'type_code': '3', 'enable': '1'},
            {'type_name': '模型类型表', 'type_code': '4', 'enable': '1'}
        ]
        for i in dict_type:
            # type = DictType(id=i['id'],type_name=i['type_name'],type_code=i['type_code'],enable=i['enable'])
            type = DictType(type_name=i['type_name'], type_code=i['type_code'], enable=i['enable'])
            db.session.add(type)
            db.session.commit()

        dict_data = [
            {'id': 1,'data_id':0, 'data_label': '北峪',  'data_value':'beiyu','type_code':'1', 'enable':'1'},
            {'id': 2,'data_id':0, 'data_label': '富家凹', 'data_value': 'fujiawa', 'type_code': '1', 'enable': '1'},
            {'id': 3,'data_id':0, 'data_label': '凤凰台', 'data_value': 'fenghuangtai', 'type_code': '1', 'enable': '1'},
            {'id': 4, 'data_id':0,'data_label': '官庄河', 'data_value': 'guzhuanghe', 'type_code': '1', 'enable': '1'},
            {'id': 5, 'data_id':0,'data_label': '集广', 'data_value':'jiguang', 'type_code': '1', 'enable': '1'},
            {'id': 6, 'data_id':0, 'data_label': '气动式钻机检测算法模型', 'data_value': 'pneumatic_machine', 'type_code': '2', 'enable': '1'},
            {'id': 7, 'data_id':0,'data_label': '液压式钻机检测算法模型', 'data_value': 'hydraulic_machine', 'type_code': '2',
             'enable': '1'},
            {'id': 8, 'data_id':0,'data_label': '履带式钻机检测算法模型', 'data_value': 'crawler_machine', 'type_code': '2',
             'enable': '1'},
            {'id': 9, 'data_id':0,'data_label': '未戴安全帽算法模型', 'data_value': 'helmet', 'type_code': '2',
             'enable': '1'},
            {'id': 10, 'data_id':0, 'data_label': '危险区域入侵算法模型', 'data_value': '', 'type_code': '2',
             'enable': '1'},
            {'id': 11, 'data_id':1,'data_label': '寒武纪', 'data_value': 'Cambricon', 'type_code': '3',
             'enable': '1'},
            {'id': 12, 'data_id':2,'data_label': '算能', 'data_value': 'Sophon', 'type_code': '3',
             'enable': '1'},
            {'id': 13,  'data_id':3,'data_label': '华为', 'data_value': 'Huawei', 'type_code': '3',
             'enable': '1'},

            {'id': 14, 'data_id': 4, 'data_label': '串行', 'data_value': '1', 'type_code': '4',
             'enable': '1'},
            {'id': 15, 'data_id': 4, 'data_label': '单类', 'data_value': '2', 'type_code': '4',
             'enable': '1'},


        ]

        for i in dict_data:
            dict_res = Dict_data(id=i['id'],data_id=i['data_id'] if i.get('data_id') else None,data_label=i['data_label'],data_value=i['data_value'],type_code=i['type_code'],enable=i['enable'])
            db.session.add(dict_res)
        db.session.commit()

        print('字典翻译数据插入完成！')

    if not Mine.query.first():

        mine_data = [
            {'id':1,'mine_name':'阳光三极'},
        ]

        for i in mine_data:
            mine_res = Mine(id=i['id'],mine_name=i['mine_name'])
            db.session.add(mine_res)
        db.session.commit()
        print('矿数据插入完成！')

    if not Diagnosis_type.query.first():

        diag_data = [
            {'id':1,'name':'视频抖动','prewarn':30,'warn':70},
            {'id':2,'name':'条纹干扰','prewarn':30,'warn':70},
            {'id':3,'name':'视频丢失','prewarn':30,'warn':70},
            {'id':4,'name':'视频遮挡','prewarn':30,'warn':70},
            {'id':5,'name':'视频冻结','prewarn':30,'warn':70},
            {'id':6,'name':'高亮度','prewarn':30,'warn':70},
            {'id':7,'name':'低亮度','prewarn':30,'warn':70},
            {'id':8,'name':'视频噪声','prewarn':30,'warn':70},
            {'id':9,'name':'偏色','prewarn':30,'warn':70},
            {'id':10,'name':'清晰度','prewarn':30,'warn':70},
            {'id':11,'name':'场景变化','prewarn':30,'warn':70},
            {'id':12,'name':'对比度','prewarn':30,'warn':70},
            {'id':13,'name':'横纹干扰','prewarn':30,'warn':70},
            {'id':14,'name':'滚动条纹','prewarn':30,'warn':70},
            {'id':15,'name':'横波干扰','prewarn':30,'warn':70},
            {'id': 16, 'name': '花帧检测', 'prewarn': 30, 'warn': 70},
        ]

        for i in diag_data:
            diag_res = Diagnosis_type(id=i['id'],name=i['name'],prewarn=i['prewarn'],warn=i['warn'])
            db.session.add(diag_res)
        db.session.commit()
        print('诊断类型检测项表！')


    if not Model_template_config_type.query.first():

        template_config_type_data = [
            {'id':1,'model_type_name':'基础检测类','model_type_content':'目标识别基础方法，凭预定义或模型学习的特征，用检测机制，定位并分类识别单一目标物体，输出类别与坐标等关键信息，完成基础探测。'},
            {'id':2,'model_type_name':'智能衍生类','model_type_content':'基于基础检测结果拓展，经简单逻辑判断与处理，挖掘潜在价值，提升参考性，助力决策分析。'},
            {'id':3,'model_type_name':'数量统计类','model_type_content':'以目标检测为前提，对物体信息做量化统计分析，输出有统计意义结果，为宏观决策提供数据支撑。'},
            {'id':4,'model_type_name':'深度适配类','model_type_content':'针对复杂场景，在常规目标检测基础上深度定制，含复杂前后处理，引入自定义函数及参数，适配业务逻辑与精度要求。'},
            {'id':5,'model_type_name':'级联聚析类','model_type_content':'级联聚析类始于基础检测，串联两个模型协同工作。首模依基础检测法，定位、分类单一目标，输出类别与坐标等。次模以首模结果为基，先聚合信息，再多维分析，进一步精准定位与分类，提升复杂场景下检测的精度与可靠性，挖掘更多潜在价值。'},
        ]

        for i in template_config_type_data:
            template_config_data_res = Model_template_config_type(id=i['id'],model_type_name=i['model_type_name'],model_type_content=i['model_type_content'])
            db.session.add(template_config_data_res)
        db.session.commit()
        print('模板类型大类数据插入成功！')


    if not Model_template_config.query.first():

        template_config_data = [
            {'id':1,'model_name':'基础检测','model_type':2,'model_template_config_type_id':1},
            {'id':2,'model_name':'皮带跑偏','model_type':1,'model_template_config_type_id':2},
            {'id':3,'model_name':'灭火器识别','model_type':1,'model_template_config_type_id':2},
            {'id':4,'model_name':'人员脱岗','model_type':1,'model_template_config_type_id':2},
            {'id':5,'model_name':'人员聚集','model_type':1,'model_template_config_type_id':2},
            {'id':6,'model_name':'乘坐猴车不按规定排队','model_type':1,'model_template_config_type_id':2},
            {'id':7,'model_name':'行车不行人_警示牌','model_type':1,'model_template_config_type_id':2},

            {'id':8,'model_name':'人数计数','model_type':1,'model_template_config_type_id':3},
            {'id':9,'model_name':'车辆统计','model_type':1,'model_template_config_type_id':3},

            {'id':10,'model_name':'皮带运行时人员入侵','model_type':1,'model_template_config_type_id':4},
            {'id':11,'model_name':'行车不行人_警示牌','model_type':1,'model_template_config_type_id':4},
            {'id':12,'model_name':'车辆避让','model_type':1,'model_template_config_type_id':4},
            {'id':13,'model_name':'车厢门打开','model_type':1,'model_template_config_type_id':4},
            {'id':14,'model_name':'推车检测','model_type':1,'model_template_config_type_id':4},
            {'id':15,'model_name':'巡检轨迹','model_type':1,'model_template_config_type_id':4},
            {'id':16,'model_name':'开车前巡检','model_type':1,'model_template_config_type_id':4},
            {'id':17,'model_name':'绞车运行前车辆超挂','model_type':1,'model_template_config_type_id':4},
            {'id':18,'model_name':'探放水','model_type':1,'model_template_config_type_id':4},
            {'id':19,'model_name':'人脸识别','model_type':1,'model_template_config_type_id':4},

            {'id':20,'model_name':'车厢编号检测','model_type':1,'model_template_config_type_id':4},
            {'id':21,'model_name':'抽烟检测','model_type':1,'model_template_config_type_id':5},
            {'id':22,'model_name':'打电话','model_type':1,'model_template_config_type_id':5},
            {'id': 23, 'model_name': '人体静止', 'model_type': 1, 'model_template_config_type_id': 4},
            {'id': 24, 'model_name': '明火识别', 'model_type': 1, 'model_template_config_type_id': 4},
            {'id': 25, 'model_name': '领导换班', 'model_type': 1, 'model_template_config_type_id': 4},
        ]

        for i in template_config_data:
            template_config_data_res = Model_template_config(id=i['id'],model_name=i['model_name'],
                                                             model_type=i['model_type'],model_template_config_type_id=i['model_template_config_type_id']
                                                             )
            db.session.add(template_config_data_res)
        db.session.commit()
        print('模板类型数据插入成功！')

    if not Model_template_small.query.first():

        small_template_config_data = [

            {'id': 1, 'template_small_name': '基础检测', 'model_template_config_type_id': 1, 'list_data': '[{}]'},
            {'id': 2, 'template_small_name': '数量不足', 'model_template_config_type_id': 2,
             'list_data': '[{"触发数量":["0","触发报警数量，超量告警：如设置为3，报警逻辑大于3；数量不足：如设置为2，报警逻辑为小于2。取值范围：(0-10)"]}]'},
            {'id': 3, 'template_small_name': '指定数量', 'model_template_config_type_id': 2,
             'list_data': '[{"触发数量":["0","触发报警数量，超量告警：如设置为3，报警逻辑大于3；数量不足：如设置为2，报警逻辑为小于2。取值范围：(0-10)"]}]'},
            {'id': 4, 'template_small_name': '超量告警', 'model_template_config_type_id': 2,
             'list_data': '[{"触发数量":["0","触发报警数量，超量告警：如设置为3，报警逻辑大于3；数量不足：如设置为2，报警逻辑为小于2。取值范围：(0-10)"]}]'},
            {'id': 5, 'template_small_name': '多类协同', 'model_template_config_type_id': 2, 'list_data': '[{}]'},
            {'id': 6, 'template_small_name': '数量统计', 'model_template_config_type_id': 3,
             'list_data': '[{"上报时长":["300","数量统计的间隔时长，如设置为300，表示5分钟统计与上报一次。取值范围：(300-600)"]}]'},

            {'id': 7, 'template_small_name': '设备运行时人员入侵', 'model_template_config_type_id': 4,
             'list_data': '[{"亮度值":["15","场景光线越暗，适当减小该值；反之，越亮则增大该值。取值范围：(1-100)"]},{"清晰度":["13","清晰度越低，适当增大该值。取值范围：(7/13/19/21/27)"]}]'},
            {'id': 8, 'template_small_name': '行车不行人', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["65","车辆运行速度越慢，适当提高该值。取值范围：(1-100)"]}]'},
            {'id': 9, 'template_small_name': '车辆避让', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["50","车辆运行速度越慢，适当提高该值。取值范围：(1-100)"]}]'},
            {'id': 10, 'template_small_name': '车厢门打开', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["90","车辆运行速度越慢，适当提高该值。取值范围：(1-100)"]},{"连续帧":["10","挡车辆未移动，出现报警的情况，适当调高数值。取值范围：(1-100)"]}]'},
            {'id': 11, 'template_small_name': '推车检测', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["50","车辆运行速度越慢，适当提高该值。取值范围：(1-100)"]}]'},
            {'id': 12, 'template_small_name': '巡检轨迹', 'model_template_config_type_id': 4, 'list_data': '[{}]'},
            {'id': 13, 'template_small_name': '开车前巡检', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["90","车辆运行速度越快或者检测频率越高，适当提高该值。取值范围：(1-100)"]}]'},
            {'id': 14, 'template_small_name': '绞车运行前车辆超挂', 'model_template_config_type_id': 4,
             'list_data': '[{"运行速度":["65","车辆运行速度越快或者检测频率越高，适当提高该值。取值范围：(1-100)"]},{"告警数量":["2","触发报警数量，超量告警：如设置为3，报警逻辑大于3。取值范围：(1-10)"]}]'},

            {'id': 15, 'template_small_name': '探放水', 'model_template_config_type_id': 4, 'list_data': '[{}]'},
            {'id': 16, 'template_small_name': '人脸识别', 'model_template_config_type_id': 4,
             'list_data': '[{"识别精度":["80","人脸匹配阈值，阈值越大识别越准确。取值范围：(1-100)"]}]'},

            {'id': 17, 'template_small_name': '车厢编号检测', 'model_template_config_type_id': 5, 'list_data': '[{}]'},
            {'id': 18, 'template_small_name': '抽烟检测', 'model_template_config_type_id': 5, 'list_data': '[{}]'},
            {'id': 19, 'template_small_name': '玩手机检测', 'model_template_config_type_id': 5, 'list_data': '[{}]'},

        ]

        for i in small_template_config_data:
            model_template_small_data = Model_template_small(id=i['id'],template_small_name=i['template_small_name'],
                                                             list_data=i['list_data'],
                                                             model_template_config_type_id=i['model_template_config_type_id'],
                                                             )
            db.session.add(model_template_small_data)
        db.session.commit()
        print('模板小类数据插入成功！')


    if not Version.query.first():
        version_data = Version(id=1,version=VERSION)
        db.session.add(version_data)
        db.session.commit()
        print('版本数据插入成功！')
    else:
        version_data = Version(id=1, version=VERSION)
        db.session.merge(version_data)
        db.session.commit()
        print('版本数据更新成功！')

    if not Algorithm_result_warning_message.query.first():

        Algorithm_result_warning_message_data = [
            {'id':1,'algorithm_name':'危险区域入侵','template_type_id':1,'warning_message':'触发危险区域入侵报警'},
            {'id':2,'algorithm_name':'未戴安全帽','template_type_id':1,'warning_message':'触发未戴安全帽报警'},
            {'id':3, 'algorithm_name': '人员睡岗', 'template_type_id': 1, 'warning_message': '检测到人员睡岗'},
            {'id': 4, 'algorithm_name': '未穿工作服', 'template_type_id': 1, 'warning_message': '检测到未穿工作服'},
            {'id': 5, 'algorithm_name': '明火识别', 'template_type_id': 1, 'warning_message': '疑似检测到明火'},
            {'id': 6, 'algorithm_name': '烟雾识别', 'template_type_id': 1, 'warning_message': '疑似检测到烟雾'},
            {'id': 7, 'algorithm_name': '携带危险物品', 'template_type_id': 1, 'warning_message': '疑似携带危险物品'},
            {'id': 8, 'algorithm_name': '视频遮挡', 'template_type_id': 1, 'warning_message': '疑似视频遮挡'},
            {'id': 9, 'algorithm_name': '人员聚集', 'template_type_id': 2, 'warning_message': '触发人员聚集报警'},
            {'id': 10, 'algorithm_name': '人员脱岗', 'template_type_id': 2, 'warning_message': '检测到人员脱岗'},
            {'id': 11, 'algorithm_name': '灭火器识别', 'template_type_id': 2, 'warning_message': '检测到未摆放灭火器'},




        ]

        for i in Algorithm_result_warning_message_data:
            Algorithm_result_warning_message_res = Algorithm_result_warning_message(id=i['id'],algorithm_name=i['algorithm_name'],template_type_id=i['template_type_id'],warning_message=i['warning_message'])
            db.session.add(Algorithm_result_warning_message_res)
        db.session.commit()

        print('报警信息预置数据插入完成！')