# native-recorder-sync-v2
from common.platform_auth import platform_jwt_required
from typing import Union

import pymysql
import base64
import pytz
import redis
import os
import subprocess
import platform
import cv2
import numpy as np
import stat
import base64
import urllib.parse
import paramiko
import socket
import io
import json
import re
import random
import string
import threading
import multiprocessing
import time
import requests
import xml.etree.ElementTree as ET
import configparser
from urllib.parse import quote

from sqlalchemy.exc import SQLAlchemyError


from tool.getDevStatus import getRunStatus,Pinger
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import defaultdict
from datetime import datetime,timedelta,date
from requests.auth import HTTPDigestAuth
from flask_bcrypt import Bcrypt  # 密码操作
from sqlalchemy import and_,func,update
from flask_jwt_extended import create_access_token,get_jwt_identity,jwt_required,JWTManager,get_jwt,verify_jwt_in_request
from flask import session, jsonify, request,g
# from flask_login import LoginManager, login_user, login_required,logout_user, current_user
from functools import wraps
from flask_migrate import Migrate
import re


import random, string, io, os

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value


def load_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

import os

# 获取当前文件所在目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))

config_path = os.path.join(current_dir, "config.ini")
config_path1 = "./config.ini"
config = load_config(config_path1)
version_path = os.path.join(current_dir, "version.cfg")
version = load_config(version_path)
sftp_path = "/data/AIGO/platform_start/vqd_data/"
sftp_port = 22
nginx_port = 9001


# 从配置文件中读取数据库和Redis配置
DB_HOST = config['database']['DB_HOST']
DB_USER = config['database']['DB_USER']
DB_PORT = config['database']['DB_PORT']
DB_PASSWORD = config['database']['DB_PASSWORD']
DB_NAME = config['database']['DB_NAME']

Redis_ip = config['redis']['Redis_ip']
Redis_port = config['redis']['Redis_port']
Redis_password = config['redis']['Redis_password']

Box_ip = config['box_ip']['Box_ip']
Box_user = config['box_ip']['Box_user']
Box_password = config['box_ip']['Box_password']
remote_ip = config['aicam']['remote_ip']
remote_port = config['aicam']['remote_port']
AIFZ_HOST = config['aicam']['AIFZ_HOST']
AIFZ_PORT = config['aicam']['AIFZ_PORT']
VERSION = version['metadata']['version']
bcrypt = Bcrypt()  # 加密配置
redis_client = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, db=2)
# 盒子服务器上传类 （算法包上传）
class SSH_Func(object):
    def __init__(self,ip_addrress,user,password):

        # self.Folder_SSH = '/data2/model_algorithm_package/'  # 华为云上传文件默认地址(家里)
        self.Folder_SSH = '/data/AIGO/platform_start/model_algorithm_package/'  # 华为云上传文件默认地址
        self.ssh_host = ip_addrress
        self.ssh_user = user
        self.ssh_password = password
        self.ssh = paramiko.SSHClient()

    # ssh连接华为云服务器
    # def connect_ssh(self):
    #     # SSH连接信息
    #     # 标识符
    #     connected = False
    #     # 最大连接次数
    #     attempts = 0
    #
    #     while connected == False and attempts < 180:
    #         try:
    #             self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #             self.ssh.connect(self.ssh_host, username=self.ssh_user, password=self.ssh_password)
    #             print("SSH连接成功")
    #             connected = True
    #         except Exception as e:
    #             print("SSH连接失败:", e)
    #             print("正在进行连接重试...")
    #             attempts += 1
    #             print(attempts, '次数')
    #             time.sleep(1)
    #     if connected == False:
    #         print('连接超过最大次数限制,无法连接到SSH服务器')
    #         return None
    #     return self.ssh
    def connect_ssh(self):
        # SSH连接信息
        # 标识符
        connected = False
        # 最大连接次数
        attempts = 0
        status = None

        while connected == False and attempts < 1:
            try:
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(self.ssh_host, username=self.ssh_user, password=self.ssh_password)
                print("SSH连接成功")
                connected = True
                status = 1  # 正常连接
            except paramiko.AuthenticationException:
                print("SSH连接失败: 账号或密码错误")
                print("正在进行连接重试...")
                attempts += 1
                print(attempts, '次数')
                time.sleep(1)
                status = 3  # 账密错误
            except paramiko.SSHException as ssh_ex:
                print(f"SSH连接失败: 可能是IP不可达或SSH服务未开启 - {ssh_ex}")
                print("正在进行连接重试...")
                attempts += 1
                print(attempts, '次数')
                time.sleep(1)
                status = 2  # IP不可达
            except Exception as ex:
                print(f"SSH连接失败: 发生未知错误 - {ex}")
                print("正在进行连接重试...")
                attempts += 1
                print(attempts, '次数')
                time.sleep(1)
                status = 2
        if connected == False:
            print('连接超过最大次数限制,无法连接到SSH服务器')
            return None, status
        return self.ssh,status


    # 华为云文件夹创建相关逻辑
    def Add_Folder(self):

        ssh, _= self.connect_ssh()
        if ssh is None:
            return

        sftp = ssh.open_sftp()
        remote_folder_1st_level = os.path.dirname(self.Folder_SSH)

        try:
            # 先检查目录是否存在，避免依赖异常
            try:
                sftp.stat(remote_folder_1st_level)  # 如果能获取到文件状态，说明目录存在
                print(f'算法模型目录已经存在: {remote_folder_1st_level}')
                return '上传成功!'
            except FileNotFoundError:
                # 目录不存在，继续创建
                sftp.mkdir(remote_folder_1st_level)
                print('成功创建算法模型目录:', remote_folder_1st_level)
                return '上传成功!'

        except PermissionError as e:
            print(f"权限错误: {str(e)}")
            return '权限不足,无法上传!'
        except Exception as e:
            error_message = str(e)
            print(f'创建目录时发生其他错误: {error_message}')
            return '上传失败'
        finally:
            sftp.close()
            ssh.close()


    def upload_send_file(self, extracted_file_content, filename):
        ssh,status = self.connect_ssh()
        if status != 1:
            return '服务器连接异常'
        sftp = ssh.open_sftp()
        try:
            # 查找默认路径+当前文件夹文件下列表
            remote_file_list = sftp.listdir(os.path.join(self.Folder_SSH))

            # 远程路径
            remote_item_path = os.path.join(self.Folder_SSH, filename).replace('\\', '/')

            # 当文件不存在于云服务器时执行上传操作
            if filename not in remote_file_list:
                try:
                    # 将字节内容转换为文件对象
                    file_obj = io.BytesIO(extracted_file_content)
                    file_obj.name = filename  # 设置文件名，以便SFTP使用

                    # 上传文件
                    sftp.putfo(file_obj, remote_item_path)
                    print('成功上传文件:', filename, '到', remote_item_path)
                    return remote_item_path
                except (paramiko.SSHException, socket.error) as e:
                    print('上传中断:', e)
                    return '上传中断，请稍后重试'
                except Exception as e:
                    print('无法上传文件:', filename, e)
                    return '无法上传文件'
            else:
                print('文件已存在，跳过上传:', filename)
                return remote_item_path

        except Exception as e:
            print('文件目录不存在', e)
            return '无法上传文件'

        finally:
            sftp.close()
            ssh.close()

    def delete_remote_file(self, remote_file_path):
        """
        删除远程服务器上的文件
        :param remote_file_path: 远程文件的完整路径
        :return: 删除结果状态
        """
        ssh, status = self.connect_ssh()
        if status != 1:
            return '服务器连接异常'

        sftp = ssh.open_sftp()
        try:
            # 检查文件是否存在
            try:
                sftp.stat(remote_file_path)
            except FileNotFoundError:
                print(f'文件不存在，无需删除: {remote_file_path}')
                return '文件不存在'

            # 删除文件
            sftp.remove(remote_file_path)
            print(f'成功删除文件: {remote_file_path}')
            return '删除成功'
        except PermissionError as e:
            print(f'权限不足，无法删除文件: {e}')
            return '权限不足'
        except Exception as e:
            print(f'删除文件失败: {e}')
            return f'删除失败: {str(e)}'
        finally:
            sftp.close()
            ssh.close()

    # arr =SSH_Func()
# arr.Add_Folder()

    def download_files(self, remote_files_paths, local_directory):
        local_pics = []
        ssh, _ = self.connect_ssh()
        if ssh is None:
            return None

        sftp = ssh.open_sftp()
        try:
            for remote_file_path in remote_files_paths:
                # 假设 remote_file_path 包含文件名，我们可以使用它来构建本地文件路径
                local_file_path = os.path.join(local_directory, os.path.basename(remote_file_path))
                # 下载单个文件
                if not os.path.exists(local_file_path):
                    sftp.get(remote_file_path, local_file_path)
                    print(f'成功下载文件: {remote_file_path} 到 {local_file_path}')
                    local_pics.append(local_file_path)
                else:
                    print(f'文件已存在，跳过下载: {local_file_path}')
                    local_pics.append(local_file_path)
        except Exception as e:
            print(f'下载文件失败: {e}')
        finally:
            sftp.close()
            ssh.close()
        return local_pics



# --------装饰器--------
def jwt_required_with_refresh(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Retain the production activation requirement after account checks.
        activations = db.session.query(Activate_info).filter(Activate_info.activate_status == 1).first()
        if not activations:
            return jsonify({"msg": "该系统尚未激活！请登录运管中心授权！", 'code': 400})
        return fn(*args, **kwargs)
    return platform_jwt_required(wrapper)

# 默认静态文件路径获取
def get_static_path():
    # 获取当前文件的绝对路径
    current_file_path = os.path.abspath(__file__)
    # 获取当前文件所在的目录路径（即 config 目录）
    current_directory = os.path.dirname(current_file_path)
    # 向上跳转一级目录，进入项目根目录
    root_directory = os.path.dirname(current_directory)
    # 构建目标路径：static 文件夹在根目录下
    target_path = os.path.join(root_directory, 'static')
    return target_path


# 静态路径赋值
FILE_SAVE_PATH = get_static_path()


# 预警筛选
type_status = [
    {'id': '1', 'value': 'I级报警'},
    {'id': '2', 'value': 'II级报警'},
    {'id': '3', 'value': 'III级报警'},
    {'id': '4', 'value': 'IV级报警'},
    {'id': '5', 'value': 'V级报警'},
    {'id': '6', 'value': 'VI级报警'},
    {'id': '7', 'value': 'VII级报警'},
    {'id': '8', 'value': 'VIII级报警'}
]

# 算法运行停止状态
status = [
    {'id': '1', 'value': '运行'},
    {'id': '2', 'value': '停止'},
]

# 定时任务状态
vcr_status = [
    {'id': '1', 'value': '启用'},
    {'id': '2', 'value': '禁用'},
]

# 算法类型
algorithm_type = [
    {'id': '1', 'value': '通用检测模型'},
    {'id': '2', 'value': '单类检测模型'},
]

# 设备类型筛选

equipment_type = [
    {'id': '1', 'value': '摄像头'},
    {'id': '2', 'value': '录像机'},
    {'id': '3', 'value': '安防平台'},
    {'id': '4', 'value': '紫光华智'},
    {'id': '5', 'value': '视频中心存储'},
    {'id': '6', 'value': 'AI单光摄像头'},
    {'id': '7', 'value': 'AI双光摄像头'},
]

lingdaohuanban_result = [
    {'id': '1', 'value': '带班打卡成功'},
    {'id': '2', 'value': '换班打卡成功'},
    {'id': '3', 'value': '疑似有人未携带定位卡'},
]
# equipment_type = [
#     {'id': '1', 'value': '摄像头'},
#     {'id': '2', 'value': '录像机'},
#     {'id': '3', 'value': '特殊摄像头'},
#     {'id': '4', 'value': '浙江双视热成像'},
#     {'id': '5', 'value': '安防平台'},
# ]

# 筛选设备类型
def get_equipment_type(equipment_type, equipment_type_name):
    for equipment in equipment_type:
        if equipment['value'] == equipment_type_name:
            return equipment['id']
    return None  # 如果没有找到对应的类型，返回 None


# 厂商类型筛选
manufacturer_type = [
    {'id': '1', 'value': '海康'},
    {'id': '2', 'value': '大华'},
    {'id': '3', 'value': '索尼'},
    {'id': '4', 'value': '宇视'},
    {'id': '5', 'value': '天地伟业'},
    {'id': '6', 'value': '三星'},
    {'id': '7', 'value': '浙江双视'},
    {'id': '8', 'value': '艾斯卡普'},
    {'id': '9', 'value': '阳光三极'}
]


# 码流类型
equipment_codetype = [
    {'id': '1', 'value': 'H265'},
    {'id': '2', 'value': 'H264'},
]

# 接入方式
vcr_way = [
    {'id': '1', 'value': '私有SDK'},
    {'id': '2', 'value': 'Onvif'},
    {'id': '3', 'value': 'GB28181'},
]

YSNVR_manufacturer_type = {
    'HIKVISION': '海康',
    'Dahua': '大华',
    'UNIVIEW': '宇视'
}
# 序列key
activate_key = _required_site_value("AIP_ACTIVATION_KEY")

from cryptography.fernet import Fernet,InvalidToken
# 生成用于加密和解密的密钥
key_key = Fernet.generate_key()
cipher_suite = Fernet(key_key)

# SQLAlchemy数据库配置
class Config(object):
    """配置参数"""
    # sqlalchemy的配置参数
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://{}:{}@{}:{}/{}".format(urllib.parse.quote(DB_USER), urllib.parse.quote(DB_PASSWORD), DB_HOST,DB_PORT,DB_NAME)

    # 设置sqlalchemy自动更新跟踪数据库
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}


# 图片转换base64方法
def return_img_stream(img_local_path):
    with open(img_local_path, 'rb') as img:
        # 使用base64进行编码
        b64encode = base64.b64encode(img.read())
        s = b64encode.decode()
        b64_encode = 'data:image/jpg;base64,%s' % s
        # print(b64_encode[0:30])
        # 返回base64编码字符串
        # print(type(b64_encode))
        return b64_encode


def convert_to_dict(item, fields):
    item_dict = {}  # 创建一个空字典，用于存储对象字段的键-值对
    for field in fields:
        # 遍历传入的字段列表
        if hasattr(item, field):
            # 使用 hasattr 函数检查对象 item 是否包含字段 field
            # 如果对象包含该字段，则为 True；否则为 False
            item_dict[field] = getattr(item, field)
            # 如果字段存在，使用 getattr 函数获取字段的值，并将其添加到字典中
    return item_dict
    # 返回包含对象字段的字典


# 序列化器
def convert_folder_to_dict_list(folder_res, fields):
    if isinstance(folder_res, list):
        # 检查输入参数 folder_res 是否为列表
        # 如果是列表，表示要处理多个对象
        # 对列表中的每个对象应用 convert_to_dict 函数
        return [convert_to_dict(item, fields) for item in folder_res]
    else:
        # 如果输入参数不是列表，表示要处理单个对象
        # 直接应用 convert_to_dict 函数来将单个对象转换为字典
        return convert_to_dict(folder_res, fields)


# 密码进行加密
def password_encryption(password):
    # 使用 bcrypt 来加密密码
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    return hashed_password


# 用户登录时验证密码
def password_decryption(input_password, hashed_password):
    return bcrypt.check_password_hash(hashed_password, input_password)

# 验证密码复杂度
def validate_password_complexity(password):
    """
    正则表达式来检查密码是否包含至少一个小写字母、一个大写字母和一个数字

    """
    patterns = [
        r'[a-z]',  # 至少一个小写字母
        r'[A-Z]',  # 至少一个大写字母
        r'[0-9]',  # 至少一个数字
        r'[!@#$%^&*(),.<>{}[\]\/?\\|`~\-=_+]'  # 特殊字符
    ]

    # 计算匹配的字符类型数量
    types_count = sum(bool(re.search(pattern, password)) for pattern in patterns)

    # 确保密码长度至少为12位且至少包含三种不同类型的字符
    if len(password) >= 9 and types_count >= 3:
        return True
    else:
        return False


# 字符串时间转换 # Mon, 27 Nov 2023 14:42:12 GMT
def time_to_gmt_format(input_str, input_format="%Y-%m-%d %H:%M:%S", output_format="%a, %d %b %Y %H:%M:%S GMT",
                       output_timezone='GMT'):
    # 将字符串转换为 datetime 对象
    input_datetime = datetime.strptime(input_str, input_format)

    # 设置时区
    input_timezone = pytz.timezone(output_timezone)
    input_datetime = input_timezone.localize(input_datetime)

    # 将 datetime 对象格式化为指定字符串格式
    output_str = input_datetime.strftime(output_format)

    time_obj = datetime.strptime(output_str, "%a, %d %b %Y %H:%M:%S %Z")

    formatted_str = time_obj.strftime("%Y-%m-%d %H:%M:%S")

    return formatted_str


# 数据库类配置
class MySQL:
    """ mysql类 """

    def __init__(self):
        """ 连接数据库 """
        try:
            self.conn = pymysql.connect(host=DB_HOST,
                                        user=DB_USER,
                                        password=DB_PASSWORD,
                                        database=DB_NAME,
                                        charset='utf8',
                                        cursorclass=pymysql.cursors.DictCursor)
        # 出现异常时执行的代码
        except Exception as e:
            print(e)
        # 没有异常时执行的代码
        else:
            print(" * Database connection succeeded!")
            # 获取游标
            self.cursor = self.conn.cursor()

    def insert(self, sql):
        """
        插入方法
        :param sql:
        :return:
        """

        # 执行sql语句
        self.cursor.execute(sql)
        # 提交sql
        self.conn.commit()

        return "insert ok"

    def delete(self, sql):
        """
        删除
        :param sql:
        :return:
        """
        # 执行sql语句
        self.cursor.execute(sql)
        # 提交sql
        self.conn.commit()

        return "delete ok"

    def update(self, sql):
        """
        修改方法
        :param sql:
        :return:
        """

        # 执行sql语句
        self.cursor.execute(sql)
        # 提交sql
        self.conn.commit()

        return "update ok"

    def get_one(self, sql):
        """
        查询单个数据
        :param sql:
        :return:对象
        """

        # 执行sql语句
        self.cursor.execute(sql)
        # 获取数据
        res = self.cursor.fetchone()
        # 返回结果集
        return res


    def get_all(self, sql):
        """
        查询多个数据
        :param sql:
        :return:数据集
        """

        # 执行sql语句
        self.cursor.execute(sql)
        # 获取数据
        res = self.cursor.fetchall()
        # 返回结果集
        return res

    def __del__(self):
        """
        析构方法
        :return:
        """

        # 关闭游标
        self.cursor.close()
        # 关闭数据库链接
        self.conn.close()


# redus 队列
class TestQueue:
    def __init__(self):
        self.r = redis.Redis(host=Redis_ip, port=Redis_port,password=Redis_password,decode_responses=True, db=1)
        self.key = "queue"  # 并行算法队列
        self.key1 = "queue1" # 监听模型状态队列
        self.key2 = "queue2" # 串行算法 队列


    # 入队
    # def push(self,total):
    #
    #     if total == 0 :
    #         # 在尾部加入数据
    #         self.r.rpush(self.key,'1')
    #     else:
    #         # 在尾部加入数据
    #         data_to_push = [total] * total
    #         self.r.rpush(self.key, *data_to_push)
    #     return '队列数据添加成功'

    # 入队
    def push(self):

        self.r.rpush(self.key,'1') # 并行算法 队列
        self.r.rpush(self.key1, '1') # 监听模型监控点状态队列
        return '队列数据添加成功'



    def push_quque3(self):

        self.r.rpush(self.key1, '1') # 监听模型监控点状态队列
        self.r.rpush(self.key2,'1')  # 串行算法 队列
        return '队列数据添加成功'



    # 出队
    def pop(self):
        # 阻塞地从头部移除数据
        result = self.r.blpop(self.key, timeout=0)
        if result:
            return result[1]  # 返回数据
        else:
            return None  # 如果超时返回 None

    # 返回队列数据列表
    def get_all(self):
        return self.r.lrange(self.key, 0, -1)


    # 获取id对应key进行配置归0
    def set_id_key(self,id):
        return self.r.set('{}_key'.format(id), 0)


# redis类配置   第一个参数为ip，第二个参数端口号，第三个参数为key值
class Redis(object):
    def __init__(self, Redis_ip, Redis_port, dada_list, decode_responses=True):

        self.connection = redis.Redis(host=Redis_ip, port=Redis_port,password=Redis_password,decode_responses=decode_responses)
        # list
        self.dada_list = dada_list

    # 插入绘制区域图片数据
    def set_string(self, data, value):
        self.connection.set(data, value)
        return '插入成功'

    # 根据key查找数据
    def get_string(self, data):
        res = self.connection.get(data)
        return res

    # 队列数据添加
    def list_insert(self, data):

        if self.list_length() >= 3:
            return '该队列数据已经超出,队列长度为{}'.format(self.list_length())

        self.connection.rpush(self.dada_list, data)
        return '添加成功'

    # 队列数据根据已知value删除
    def list_dell(self, data):
        deleted_count = self.connection.lrem(self.dada_list, 0, data)
        print(deleted_count)
        if deleted_count > 0:
            return '删除成功'
        else:
            return '未找到要删除的元素'

    # 队列数据删除
    def list_lpop(self):

        if self.list_length() == 0:
            return '该队列数据为空,无法删除'
        self.connection.lpop(self.dada_list)
        return '删除成功'

    # 队列数据查看
    def list_show(self):

        result = self.connection.lrange(self.dada_list, 0, -1)
        return result

    # 队列长度
    def list_length(self):

        result = self.connection.llen(self.dada_list)
        return result

    # 判断key是否存在
    def list_exists(self):

        result = self.connection.exists(self.dada_list)
        return result

    # 删除某个key
    def list_del(self):

        self.connection.delete(self.dada_list)
        return 'key删除成功'


# 获取子集默认通道 code
def children_list_get_code(children_list):

    # 通道编码
    equipment_aisles_value = 1

    current_value = 101  # 起始值，递增分配

    for i in range(len(children_list)):
        # 为每个子集项分配当前值
        children_list[i]['code'] = current_value
        children_list[i]['equipment_aisles'] = equipment_aisles_value
        # 递增当前值
        current_value += 100
        equipment_aisles_value += 1

    return children_list


# native_hik_stream integration
def _is_hik_snapshot_url(url):
    from service.algorithm_platform_source import HikSnapshotUrl
    return isinstance(url, HikSnapshotUrl)


def get_video_dimensions(rtsp_url, timeout=30):
    """
    获取 RTSP 视频流分辨率
    """
    try:
        cmd = [
            'ffprobe',
            '-rtsp_transport', 'tcp',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            '-read_intervals', '%+1',
            rtsp_url
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout
        )

        data = json.loads(result.stdout.decode('utf-8', errors='ignore'))
        streams = data.get('streams', [])

        if streams:
            width = streams[0].get('width')
            height = streams[0].get('height')
            if width and height:
                return int(width), int(height)

        print("未获取到视频尺寸")
        return None, None

    except subprocess.TimeoutExpired:
        print("获取视频尺寸超时")
        return None, None
    except Exception as e:
        if not _is_hik_snapshot_url(rtsp_url):
            print(f"获取视频尺寸时出错: {e}")
        return None, None


# 获取视频宽度高度
# def get_video_dimensions(rtsp_url):
#     # 打开 RTSP 视频流
#     cap = cv2.VideoCapture(rtsp_url)
#     # 检查视频流是否成功打开
#     if not cap.isOpened():
#         print("无法打开 RTSP 视频流")
#         return None, None
#     # 获取视频帧的宽度和高度
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     # 释放视频捕获对象
#     cap.release()
#     return width, height


# 将h265流转换opencv可编译格式返回
def get_frame_from_rtsp(rtsp_url, img_resolution):
    print(img_resolution.split('x'), '字符串分割')

    # 验证RTSP URL格式
    if not rtsp_url or not rtsp_url.startswith('rtsp://'):
        print("无效的RTSP URL")
        return None

    # （ linux，windwos）  docker容器内部使用  两者兼容  当环境为linux时将传输协议改为tcp，否则转换失败 ( '-rtsp_transport', 'tcp')
    command = [
        'ffmpeg',
        #  rtsp_transport 参数，通过设定这个参数值为 tcp ，使得ffmpeg强制使用tcp协议传输RTSP流（RTSP流模式使用UDP方式传输）。
        '-rtsp_transport', 'tcp',
        # '-timeout', '10000000',
        # 减小探测大小以提高启动速度
        # '-analyzeduration', '5M',
        # '-probesize', '5M',
        '-skip_frame', 'nokey',
        # 指定输入文件（RTSP 流）的 URL。
        '-i', rtsp_url,
        '-vframes', '1',
        '-vf', 'scale={}:{}'.format(img_resolution.split("x")[0], img_resolution.split("x")[1]),
        # 指定输出格式为图像流。在这里，将输出格式设置为图像流，以便后续通过管道读取。
        '-f', 'image2pipe',
        #设置像素格式为 BGR24。在这里，将像素格式设置为 24 位 BGR 格式，即每个像素占据 3 字节。
        '-pix_fmt', 'bgr24',
        # 设置视频编解码器为原始视频。 如果设置为264需要额外增添参数   '-vcodec', 'libx264'
        '-vcodec', 'rawvideo', '-',
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**7)

    try:
        # 使用communicate代替直接read，添加超时控制
        stdout, stderr = process.communicate(timeout=15)
        
        frame_size = int(img_resolution.split("x")[0]) * int(img_resolution.split("x")[1]) * 3
        
        if len(stdout) >= frame_size:
            raw_frame = stdout[:frame_size]
        else:
            print(f"获取的数据不足: 期望 {frame_size} 字节，实际获得 {len(stdout)} 字节")
            if stderr and not _is_hik_snapshot_url(rtsp_url):
                print("FFmpeg错误输出:")
                print(stderr.decode('utf-8', errors='ignore'))
            process.terminate()
            return None
            
    except subprocess.TimeoutExpired:
        print("FFmpeg执行超时")
        process.kill()
        process.communicate()
        return None
    except Exception as e:
        if not _is_hik_snapshot_url(rtsp_url):
            print(f"读取帧时发生错误: {e}")
        if process.poll() is None:
            process.kill()
            process.communicate()
        return None

    # 将帧数据转换为 numpy 数组
    try:
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((
            int(img_resolution.split("x")[1]), 
            int(img_resolution.split("x")[0]), 
            3
        ))
    except Exception as e:
        print(f"帧数据转换失败: {e}")
        return None
        
    return frame


def get_frame_from_mp4(mp4_url, img_resolution):
    """
    从 MP4 流中获取一帧图像

    Args:
        mp4_url (str): MP4 流地址
        img_resolution (str): 图像分辨率，格式如 "1920x1080"

    Returns:
        numpy.ndarray: 图像帧数据，如果失败返回 None
    """
    print(f"尝试从 MP4 流获取帧：{mp4_url}, 分辨率：{img_resolution}")

    try:
        # 使用 FFmpeg 从 MP4 流获取一帧
        command = [
            'ffmpeg',
            '-i', mp4_url,
            '-vframes', '1',
            '-vf', f'scale={img_resolution.split("x")[0]}:{img_resolution.split("x")[1]}',
            '-f', 'image2pipe',
            '-pix_fmt', 'bgr24',
            '-vcodec', 'rawvideo', '-'
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 ** 7)

        # 使用 communicate 添加超时控制
        stdout, stderr = process.communicate(timeout=15)

        frame_size = int(img_resolution.split("x")[0]) * int(img_resolution.split("x")[1]) * 3

        if len(stdout) >= frame_size:
            raw_frame = stdout[:frame_size]
        else:
            print(f"获取的数据不足：期望 {frame_size} 字节，实际获得 {len(stdout)} 字节")
            if stderr:
                print("FFmpeg 错误输出:")
                print(stderr.decode('utf-8', errors='ignore'))
            process.terminate()
            return None

    except subprocess.TimeoutExpired:
        print("FFmpeg 执行超时")
        process.kill()
        process.communicate()
        return None
    except Exception as e:
        print(f"读取 MP4 帧时发生错误：{e}")
        if process.poll() is None:
            process.kill()
            process.communicate()
        return None

    # 将帧数据转换为 numpy 数组
    try:
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((
            int(img_resolution.split("x")[1]),
            int(img_resolution.split("x")[0]),
            3
        ))
    except Exception as e:
        print(f"帧数据转换失败：{e}")
        return None

    return frame

# 读取rtsp流是否存在，存在返回True
def check_rtsp_stream(rtsp_url):
    """检查 RTSP 流是否在线"""
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return False
    # 尝试读取一帧数据
    ret, _ = cap.read()
    cap.release()  # 关闭流
    return ret  # 如果成功读取返回 True，否则返回 False


def check_mp4_stream(mp4_url, timeout_seconds=10):
    """
    检查 MP4 流是否可用

    Args:
        mp4_url (str): MP4 流地址
        timeout_seconds (int): 超时时间（秒）

    Returns:
        bool: 如果流可用返回 True，否则返回 False
    """
    try:
        cap = cv2.VideoCapture(mp4_url)

        # 设置超时
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)

        # 检查是否成功打开
        if not cap.isOpened():
            cap.release()
            return False

        # 尝试读取一帧确保流真正可用
        ret, _ = cap.read()
        cap.release()

        return ret
    except Exception as e:
        print(f"检查 MP4 流时出错：{e}")
        if 'cap' in locals():
            cap.release()
        return False

def check_rtsp_url(rtsp_url, timeout_seconds=10):
    """
    检查 RTSP URL 是否可用
    
    Args:
        rtsp_url (str): RTSP 流地址
        timeout_seconds (int): 超时时间（秒）
    
    Returns:
        bool: 如果流可用返回 True，否则返回 False
    """
    try:
        cap = cv2.VideoCapture(rtsp_url)
        
        # 检查是否成功打开
        if not cap.isOpened():
            cap.release()
            return False
            
        # 尝试读取一帧确保流真正可用
        ret, _ = cap.read()
        cap.release()
        
        return ret
    except Exception as e:
        print(f"检查 RTSP 流时出错: {e}")
        if 'cap' in locals():
            cap.release()
        return False
# def check_rtsp_url(rtsp_url, timeout_seconds=6):
#
#     # 创建管道用于与子进程通信
#     parent_conn, child_conn = multiprocessing.Pipe()
#
#     # 启动 RTSP 捕获进程，并传递连接对象和 RTSP URL
#     capture_process = multiprocessing.Process(target=rtsp_capture_process, args=(child_conn, rtsp_url))
#     capture_process.start()
#
#     start_time = time.time()
#
#     # 等待进程执行完成或超时
#     while capture_process.is_alive():
#         elapsed_time = time.time() - start_time
#         if elapsed_time > timeout_seconds:
#             # 如果超时，终止子进程并返回 False
#             capture_process.terminate()
#             capture_process.join()
#             return False
#
#         time.sleep(0.5)  # 小睡一段时间，避免过于频繁检查
#
#     # 获取结果
#     if parent_conn.poll():  # 检查子进程是否有数据返回
#         result = parent_conn.recv()  # 获取子进程的返回结果
#     else:
#         result = False  # 如果没有数据返回，视为失败
#
#     capture_process.join()  # 确保子进程已完全退出
#
#     # 返回结果
#     return result


def rtsp_capture_process(conn, rtsp_url):
    try:
        cap = cv2.VideoCapture(rtsp_url)

        # 检查是否成功打开
        if cap.isOpened():
            success = True
        else:
            success = False

        # 释放资源
        cap.release()

    except Exception as e:
        print(f"错误：{e}")
        success = False

    # 发送结果到主进程
    conn.send(success)
    conn.close()


# 获取区域图片数据
# def get_img_from_camera_net(path,mp4, equipment_id, type,img_resolution):
#
#     r = Redis(Redis_ip, Redis_port, 'list')
#     try:
#         # 同步
#         if type == 1:
#             if path:
#                 # 判断rtsp是否存在 如果不存在返回falsk
#                 result = check_rtsp_url(path)
#                 if result == False:
#                     return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#
#                 # 获取视频流宽度与高度
#                 width, height = get_video_dimensions(path)
#                 # 当没有获取到前端分辨率参数的时候调用视频流的宽高分辨率，如果获取到执行获取的视频分辨率
#                 if not img_resolution:
#                     img_resolution = str(width) + 'x' + str(height)
#
#                 frame = get_frame_from_rtsp(path,img_resolution)
#                 if frame is not None:
#                     # 图片名称
#                     images = 'em_{}'.format(equipment_id) + '.jpg'
#                     # 文件保存
#
#                     img_path = os.path.join(FILE_SAVE_PATH, images)
#                     cv2.imwrite(img_path, frame)
#
#                     # 保存数据到redis
#                     r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
#                     r.set_string('img_resolution_{}'.format(equipment_id),img_resolution)
#                     # 从 Redis 中读取图像数据
#                     res_image = r.get_string('em_{}'.format(equipment_id))
#                     res_image = os.path.basename(res_image)
#                     return {'code': 200, 'msg': '/static/' + str(res_image),'img_resolution':img_resolution}
#                 else:
#                     return {'code': 400, 'msg': '无法获取到图像', 'l': frame, 'z': path}
#             else:
#                 return {'code': 400, 'msg': '请选择录像机子集'}
#         else:
#             # 检查是否存在缓存
#             cached_path = r.get_string('em_{}'.format(equipment_id))
#             cached_img_resolution = r.get_string('img_resolution_{}'.format(equipment_id))
#
#             if cached_path and os.path.isfile(cached_path) :
#
#                 res_image = os.path.basename(cached_path)
#
#                 return {'code': 200, 'msg': '/static/' + str(res_image),'img_resolution':cached_img_resolution}
#             else:
#                 # 判断rtsp是否存在 如果不存在返回falsk
#
#                 result = check_rtsp_url(path)
#
#                 if result == False:
#                     return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                 if path:
#                     # 获取视频流宽度与高度
#                     width, height = get_video_dimensions(path)
#                     # 当没有获取到前端分辨率参数的时候调用视频流的宽高分辨率，如果获取到执行获取的视频分辨率
#                     if not img_resolution:
#                         img_resolution = str(width) + 'x' + str(height)
#                     frame = get_frame_from_rtsp(path,img_resolution)
#                     print(frame is not None)
#                     if frame is not None:
#                         # 图片名称
#                         images = 'em_{}'.format(equipment_id) + '.jpg'
#                         # 文件保存
#                         img_path = os.path.join(FILE_SAVE_PATH, images)
#                         cv2.imwrite(img_path, frame)  # 存储为图像
#
#                         # 保存数据到redis
#                         r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
#                         r.set_string('img_resolution_{}'.format(equipment_id),img_resolution)
#                         # 从 Redis 中读取图像数据
#                         res_image = r.get_string('em_{}'.format(equipment_id))
#                         res_image = os.path.basename(res_image)
#                         return {'code': 200, 'msg': '/static/' + str(res_image),'img_resolution':img_resolution}
#                     else:
#                         return {'code': 400, 'msg': '无法获取到图像', 'l': frame, 'z': path}
#                 else:
#                     return {'code': 400, 'msg': '请选择录像机子集'}
#     except Exception as e:
#         print(f"处理图像时发生异常: {str(e)}")
#         return {'code': 500, 'msg': f'内部错误: {str(e)}'}
#
# def get_img_from_camera_net(path, mp4, equipment_id, type, img_resolution):
#     """
#     从摄像头获取图像，支持 RTSP 和 MP4 双路流
#
#     Args:
#         path (str): RTSP 流地址
#         mp4 (str): MP4 流地址（备用）
#         equipment_id (int): 设备 ID
#         type (int): 类型（1=同步，其他=异步/缓存）
#         img_resolution (str): 图像分辨率
#
#     Returns:
#         dict: 包含状态码、消息和图像路径的字典
#     """
#     r = Redis(Redis_ip, Redis_port, 'list')
#     try:
#         # 同步模式
#         if type == 1:
#             if path or mp4:
#                 # 优先尝试 RTSP 流
#                 use_mp4 = False
#                 stream_path = path
#
#                 # 如果 RTSP 存在，先检查 RTSP
#                 # if path:
#                 #    print('12111111111111111')
#                 #    result = check_rtsp_url(path)
#                 #    if result == False and mp4:
#                 # RTSP 失败且有 MP4 备用，切换到 MP4
#                 #        print(f"RTSP 流获取失败，尝试使用 MP4 备用流：{mp4}")
#                 #        result = check_mp4_stream(mp4)
#                 #        if result == False:
#                 #            return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                 #        use_mp4 = True
#                 #        stream_path = mp4
#                 #    elif result == False:
#                 #        return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                 # elif mp4:
#                 # 没有 RTSP，直接使用 MP4
#                 #    use_mp4 = True
#                 #    stream_path = mp4
#                 #    result = check_mp4_stream(mp4)
#                 #    if result == False:
#                 #        return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                 # print('1212121212121212121')
#                 # 获取视频流宽度与高度
#                 width, height = get_video_dimensions(stream_path)
#                 # 当没有获取到前端分辨率参数的时候调用视频流的宽高分辨率
#                 if not img_resolution:
#                     img_resolution = str(width) + 'x' + str(height)
#
#                 # 根据流类型选择获取帧的方法
#                 if use_mp4:
#                     frame = get_frame_from_mp4(stream_path, img_resolution)
#                 else:
#                     frame = get_frame_from_rtsp(stream_path, img_resolution)
#
#                 if frame is not None:
#                     # 图片名称
#                     images = 'em_{}'.format(equipment_id) + '.jpg'
#                     # 文件保存
#                     img_path = os.path.join(FILE_SAVE_PATH, images)
#                     cv2.imwrite(img_path, frame)
#
#                     # 保存数据到 redis
#                     r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
#                     r.set_string('img_resolution_{}'.format(equipment_id), img_resolution)
#                     # 从 Redis 中读取图像数据
#                     res_image = r.get_string('em_{}'.format(equipment_id))
#                     res_image = os.path.basename(res_image)
#                     return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': img_resolution}
#                 else:
#                     return {'code': 400, 'msg': '无法获取到图像', 'l': frame, 'z': stream_path}
#             else:
#                 return {'code': 400, 'msg': '请选择录像机子集'}
#         else:
#             # 异步模式 - 检查是否存在缓存
#             cached_path = r.get_string('em_{}'.format(equipment_id))
#             cached_img_resolution = r.get_string('img_resolution_{}'.format(equipment_id))
#
#             if cached_path and os.path.isfile(cached_path):
#                 res_image = os.path.basename(cached_path)
#                 return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': cached_img_resolution}
#             else:
#                 # 缓存不存在，重新获取
#                 if path or mp4:
#                     # 优先尝试 RTSP 流
#                     use_mp4 = False
#                     stream_path = path
#
#                     # 如果 RTSP 存在，先检查 RTSP
#                     # if path:
#                     #     result = check_rtsp_url(path)
#                     #     if result == False and mp4:
#                     #         # RTSP 失败且有 MP4 备用，切换到 MP4
#                     #         print(f"RTSP 流获取失败，尝试使用 MP4 备用流：{mp4}")
#                     #         result = check_mp4_stream(mp4)
#                     #         if result == False:
#                     #             return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                     #         use_mp4 = True
#                     #         stream_path = mp4
#                     #     elif result == False:
#                     #         return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#                     # elif mp4:
#                     #     # 没有 RTSP，直接使用 MP4
#                     #     use_mp4 = True
#                     #     stream_path = mp4
#                     #     result = check_mp4_stream(mp4)
#                     #     if result == False:
#                     #         return {'code': 400, 'msg': '无法获取到图像', 'z': path}
#
#                     # 获取视频流宽度与高度
#                     width, height = get_video_dimensions(stream_path)
#                     # 当没有获取到前端分辨率参数的时候调用视频流的宽高分辨率
#                     if not img_resolution:
#                         img_resolution = str(width) + 'x' + str(height)
#
#                     # 根据流类型选择获取帧的方法
#                     if use_mp4:
#                         frame = get_frame_from_mp4(stream_path, img_resolution)
#                     else:
#                         frame = get_frame_from_rtsp(stream_path, img_resolution)
#
#                     print(frame is not None)
#                     if frame is not None:
#                         # 图片名称
#                         images = 'em_{}'.format(equipment_id) + '.jpg'
#                         # 文件保存
#                         img_path = os.path.join(FILE_SAVE_PATH, images)
#                         cv2.imwrite(img_path, frame)  # 存储为图像
#
#                         # 保存数据到 redis
#                         r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
#                         r.set_string('img_resolution_{}'.format(equipment_id), img_resolution)
#                         # 从 Redis 中读取图像数据
#                         res_image = r.get_string('em_{}'.format(equipment_id))
#                         res_image = os.path.basename(res_image)
#                         return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': img_resolution}
#                     else:
#                         return {'code': 400, 'msg': '无法获取到图像', 'l': frame, 'z': stream_path}
#                 else:
#                     return {'code': 400, 'msg': '请选择录像机子集'}
#     except Exception as e:
#         print(f"处理图像时发生异常：{str(e)}")
#         return {'code': 500, 'msg': f'内部错误：{str(e)}'}


def get_img_from_camera_net(path, mp4, equipment_id, type, img_resolution):
    """
    从摄像头获取图像，支持 RTSP 和 MP4 双路流并发获取

    Args:
        path (str): RTSP 流地址
        mp4 (str): MP4 流地址（备用）
        equipment_id (int): 设备 ID
        type (int): 类型（1=同步，其他=异步/缓存）
        img_resolution (str): 图像分辨率

    Returns:
        dict: 包含状态码、消息和图像路径的字典
    """
    from common.camera_snapshots import persist_snapshot, SnapshotWriteError
    r = Redis(Redis_ip, Redis_port, 'list')

    def fetch_frame_from_rtsp(result_dict, stop_event):
        """从 RTSP 获取帧的线程函数"""
        if not path:
            return

        try:
            width, height = get_video_dimensions(path)
            if not img_resolution and width and height:
                result_dict['resolution'] = f"{width}x{height}"

            resolution = img_resolution or result_dict.get('resolution', '')
            if not resolution:
                return

            frame = get_frame_from_rtsp(path, resolution)
            if frame is not None and not stop_event.is_set():
                result_dict['frame'] = frame
                result_dict['source'] = 'rtsp'
                result_dict['resolution'] = resolution
                stop_event.set()  # 通知其他线程停止
        except Exception as e:
            if not _is_hik_snapshot_url(path):
                print(f"RTSP 线程异常：{str(e)}")

    def fetch_frame_from_mp4(result_dict, stop_event):
        """从 MP4 获取帧的线程函数"""
        if not mp4:
            return

        try:
            width, height = get_video_dimensions(mp4)
            if not img_resolution and width and height:
                result_dict['resolution'] = f"{width}x{height}"

            resolution = img_resolution or result_dict.get('resolution', '')
            if not resolution:
                return

            frame = get_frame_from_mp4(mp4, resolution)
            if frame is not None and not stop_event.is_set():
                result_dict['frame'] = frame
                result_dict['source'] = 'mp4'
                result_dict['resolution'] = resolution
                stop_event.set()  # 通知其他线程停止
        except Exception as e:
            print(f"MP4 线程异常：{str(e)}")

    try:
        if type == 1:
            if not path and not mp4:
                return {'code': 400, 'msg': '请选择录像机子集'}

            shared_result = {}
            stop_event = threading.Event()

            threads = []

            if path:
                rtsp_thread = threading.Thread(target=fetch_frame_from_rtsp, args=(shared_result, stop_event))
                rtsp_thread.daemon = True
                threads.append(rtsp_thread)

            if mp4:
                mp4_thread = threading.Thread(target=fetch_frame_from_mp4, args=(shared_result, stop_event))
                mp4_thread.daemon = True
                threads.append(mp4_thread)

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join(timeout=20)

            if shared_result.get('frame') is not None:
                frame = shared_result['frame']
                resolution = shared_result.get('resolution', img_resolution)

                img_path = persist_snapshot(frame, equipment_id, FILE_SAVE_PATH)

                r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
                r.set_string('img_resolution_{}'.format(equipment_id), resolution)

                res_image = r.get_string('em_{}'.format(equipment_id))
                res_image = os.path.basename(res_image)

                source = shared_result.get('source', 'unknown')
                print(f"成功从 {source} 获取图像")

                return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': resolution}
            else:
                return {'code': 400, 'msg': '无法获取到图像'}
        else:
            cached_path = r.get_string('em_{}'.format(equipment_id))
            cached_img_resolution = r.get_string('img_resolution_{}'.format(equipment_id))

            if cached_path and os.path.isfile(cached_path):
                res_image = os.path.basename(cached_path)
                return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': cached_img_resolution}
            else:
                if not path and not mp4:
                    return {'code': 400, 'msg': '请选择录像机子集'}

                shared_result = {}
                stop_event = threading.Event()

                threads = []

                if path:
                    rtsp_thread = threading.Thread(target=fetch_frame_from_rtsp, args=(shared_result, stop_event))
                    rtsp_thread.daemon = True
                    threads.append(rtsp_thread)

                if mp4:
                    mp4_thread = threading.Thread(target=fetch_frame_from_mp4, args=(shared_result, stop_event))
                    mp4_thread.daemon = True
                    threads.append(mp4_thread)

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join(timeout=20)

                if shared_result.get('frame') is not None:
                    frame = shared_result['frame']
                    resolution = shared_result.get('resolution', img_resolution)

                    img_path = persist_snapshot(frame, equipment_id, FILE_SAVE_PATH)

                    r.set_string('em_{}'.format(equipment_id), img_path.replace('\\', '/'))
                    r.set_string('img_resolution_{}'.format(equipment_id), resolution)

                    res_image = r.get_string('em_{}'.format(equipment_id))
                    res_image = os.path.basename(res_image)

                    source = shared_result.get('source', 'unknown')
                    print(f"成功从 {source} 获取图像")

                    return {'code': 200, 'msg': '/static/' + str(res_image), 'img_resolution': resolution}
                else:
                    return {'code': 400, 'msg': '无法获取到图像'}
    except SnapshotWriteError:
        return {'code': 500, 'msg': '截图保存失败，请检查平台截图目录权限和可用空间后重试'}
    except Exception as e:
        if _is_hik_snapshot_url(path):
            return {'code': 500, 'msg': '海康安防平台抓图失败'}
        print(f"处理图像时发生异常：{str(e)}")
        return {'code': 500, 'msg': f'内部错误：{str(e)}'}


# 查询算法配置数据总条数写入队列，算法程序进行重启
def total_count():
    total_records = db.session.query(Algorithm_config). \
        join(Algorithm_library, Algorithm_config.Algorithm_library_id == Algorithm_library.id). \
        join(Mine, Algorithm_config.Mine_id == Mine.id). \
        join(Equipment, Algorithm_config.Equipment_id == Equipment.id). \
        join(Algorithm_test_type, Algorithm_config.Algorithm_test_type_id == Algorithm_test_type.id). \
        filter(Algorithm_library.algorithm_status == 1). \
        filter(Algorithm_config.status == 1). \
        count()
    return total_records


# # 递归查找 parent_id 直到没有 向下找
# def find_parent_id(parent_id):
#     # 使用生成器
#     def recursive_query(parent_id):
#         from sqlalchemy.orm import aliased
#
#         # 创建别名，用于查询父设备
#         parent_alias = aliased(Equipment)
#
#         with_parent_id = db.session.query(
#             Equipment.id, Equipment.equipment_type,
#             Equipment.manufacturer_type, Equipment.equipment_name,
#             Equipment.equipment_ip, Equipment.equipment_uname,
#             Equipment.equipment_password, Equipment.equipment_aisles,
#             Equipment.equipment_codetype, Equipment.user_status,
#             Equipment.create_time, Equipment.parent_id,
#             Equipment.code, Equipment.flower_frames,Equipment.equipment_width_height,
#             Equipment.online,Equipment.equipment_maxFrameRate,Equipment.equipment_constantBitRate,
#             Equipment.Hik_rtsp_url,Equipment.Hik_indexCode,Equipment.Ziguang_ape_indexCode,
#             Equipment.Ziguang_ape_rtsp_url,Equipment.Ziguang_id,
#             parent_alias.equipment_ip.label('parent_ip')  # 加入父设备的IP
#
#         ).join(
#             parent_alias, Equipment.parent_id == parent_alias.id, isouter=True
#         ).filter(Equipment.parent_id == parent_id).all()
#
#
#         for folder in with_parent_id:
#             # 根据设备类型生成 rtsp 字段
#             equipment_uname = quote(folder.equipment_uname, safe='') if folder.equipment_uname else ''
#             equipment_password = quote(folder.equipment_password, safe='') if folder.equipment_password else ''
#             equipment_ip = quote(folder.equipment_ip, safe='') if folder.equipment_ip else ''
#             if folder.equipment_type == '摄像头':
#                 rtsp = f'rtsp://{equipment_uname}:{equipment_password}@{equipment_ip}'
#             elif folder.equipment_type == '特殊摄像头':
#                 rtsp = get_children_rtsp(folder.parent_id, folder.code, 2)
#             elif folder.equipment_type == '录像机':
#                 rtsp = get_children_rtsp(folder.parent_id, folder.code, 1,folder.equipment_aisles)
#             elif folder.equipment_type == '视频中心存储':
#                 rtsp = get_children_rtsp(folder.parent_id, folder.code, 1)
#             elif folder.equipment_type == '浙江双视热成像':
#                 rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(equipment_uname, equipment_password, equipment_ip)
#             elif folder.equipment_type == '安防平台':
#                 rtsp = folder.Hik_rtsp_url
#             elif folder.equipment_type == '紫光华智':
#                 rtsp = folder.Ziguang_ape_rtsp_url
#
#             # 添加 rtsp 到结果
#             result = {
#                 'id': folder.id,
#                 'equipment_type': folder.equipment_type,
#                 'manufacturer_type': folder.manufacturer_type,
#                 'equipment_name': folder.equipment_name,
#                 'equipment_ip': folder.equipment_ip,
#                 'equipment_uname': folder.equipment_uname,
#                 'equipment_password': folder.equipment_password,
#                 'equipment_aisles': folder.equipment_aisles,
#                 'equipment_codetype': folder.equipment_codetype,
#                 'user_status': folder.user_status,
#                 'create_time': folder.create_time,
#                 'parent_id': folder.parent_id,
#                 'code': folder.code,
#                 'flower_frames': folder.flower_frames,
#                 'parent_ip': folder.parent_ip,
#                 'rtsp': rtsp,
#                 'equipment_width_height': folder.equipment_width_height,
#                 'online': folder.online,
#                 'equipment_constantBitRate': folder.equipment_constantBitRate,
#                 'equipment_maxFrameRate': folder.equipment_maxFrameRate,
#                 'Hik_indexCode': folder.Hik_indexCode,
#                 'Ziguang_ape_rtsp_url': folder.Ziguang_ape_rtsp_url,
#                 'Ziguang_ape_indexCode': folder.Ziguang_ape_indexCode,
#             }
#
#             yield result
#             # 递归查找子设备
#             yield from recursive_query(folder.id)
#
#     return list(recursive_query(parent_id))
# 递归查找 parent_id 直到没有 向下找
def find_parent_id(parent_id):
    # 使用生成器
    def recursive_query(parent_id):
        from sqlalchemy.orm import aliased

        # 创建别名，用于查询父设备
        parent_alias = aliased(Equipment)

        with_parent_id = db.session.query(
            Equipment.id, Equipment.equipment_type,
            Equipment.manufacturer_type, Equipment.equipment_name,
            Equipment.equipment_ip, Equipment.equipment_uname,
            Equipment.equipment_password, Equipment.equipment_aisles,
            Equipment.equipment_codetype, Equipment.user_status,
            Equipment.create_time, Equipment.parent_id,
            Equipment.code, Equipment.flower_frames,Equipment.equipment_width_height,
            Equipment.online,Equipment.equipment_maxFrameRate,Equipment.equipment_constantBitRate,
            Equipment.Hik_rtsp_url,Equipment.Hik_indexCode,Equipment.Ziguang_ape_indexCode,
            Equipment.Ziguang_ape_rtsp_url,Equipment.Ziguang_id,
            parent_alias.equipment_ip.label('parent_ip')  # 加入父设备的IP

        ).join(
            parent_alias, Equipment.parent_id == parent_alias.id, isouter=True
        ).filter(Equipment.parent_id == parent_id).all()


        for folder in with_parent_id:
            # 初始化rtsp和mp4默认值
            rtsp = None
            mp4 = None
            # 根据设备类型生成 rtsp 和 mp4 字段
            equipment_uname = quote(folder.equipment_uname, safe='') if folder.equipment_uname else ''
            equipment_password = quote(folder.equipment_password, safe='') if folder.equipment_password else ''
            equipment_ip = quote(folder.equipment_ip, safe='') if folder.equipment_ip else ''
            if folder.equipment_type == '摄像头':
                rtsp = f'rtsp://{equipment_uname}:{equipment_password}@{equipment_ip}'
                mp4 = None  # 摄像头无mp4地址，设为None
            elif folder.equipment_type == '特殊摄像头':
                # 调用get_children_rtsp获取rtsp和mp4
                rtsp_mp4_data = get_children_rtsp(folder.parent_id, folder.code, 2)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
                    mp4 = rtsp_mp4_data['mp4']
            elif folder.equipment_type == 'AI双光摄像头':
                # 调用get_children_rtsp获取rtsp和mp4
                rtsp_mp4_data = get_children_rtsp(folder.parent_id, folder.code, 2)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
                    mp4 = rtsp_mp4_data['mp4']
            elif folder.equipment_type == '录像机':
                rtsp_mp4_data = get_children_rtsp(folder.parent_id, folder.code, 1, folder.equipment_aisles)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
                    mp4 = rtsp_mp4_data['mp4']
            elif folder.equipment_type == '视频中心存储':
                rtsp_mp4_data = get_children_rtsp(folder.parent_id, folder.code, 1)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
                    mp4 = rtsp_mp4_data['mp4']
            elif folder.equipment_type == '浙江双视热成像':
                rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(equipment_uname, equipment_password, equipment_ip)
                mp4 = None  # 浙江双视热成像无mp4地址，设为None
            elif folder.equipment_type == '安防平台':
                rtsp = folder.Hik_rtsp_url
                mp4 = None  # 安防平台无mp4地址，设为None
            elif folder.equipment_type == '紫光华智':
                rtsp = folder.Ziguang_ape_rtsp_url
                mp4 = None  # 紫光华智无mp4地址，设为None

            # 添加 rtsp 和 mp4 到结果
            result = {
                'id': folder.id,
                'equipment_type': folder.equipment_type,
                'manufacturer_type': folder.manufacturer_type,
                'equipment_name': folder.equipment_name,
                'equipment_ip': folder.equipment_ip,
                'equipment_uname': folder.equipment_uname,
                'equipment_password': folder.equipment_password,
                'equipment_aisles': folder.equipment_aisles,
                'equipment_codetype': folder.equipment_codetype,
                'user_status': folder.user_status,
                'create_time': folder.create_time,
                'parent_id': folder.parent_id,
                'code': folder.code,
                'flower_frames': folder.flower_frames,
                'parent_ip': folder.parent_ip,
                'rtsp': rtsp,
                'mp4': mp4,  # 新增mp4字段
                'equipment_width_height': folder.equipment_width_height,
                'online': folder.online,
                'equipment_constantBitRate': folder.equipment_constantBitRate,
                'equipment_maxFrameRate': folder.equipment_maxFrameRate,
                'Hik_indexCode': folder.Hik_indexCode,
                'Ziguang_ape_rtsp_url': folder.Ziguang_ape_rtsp_url,
                'Ziguang_ape_indexCode': folder.Ziguang_ape_indexCode,
            }

            yield result
            # 递归查找子设备
            yield from recursive_query(folder.id)

    return list(recursive_query(parent_id))

# 转换函数
def row_to_dict(row, keys):
    return {key: value for key, value in zip(keys, row)}

# 子数据
def children_data(equipment_list,vcr_ids):
    for i, equipment in enumerate(equipment_list):
        # 定义子集列表，如果有数据则填入
        # children = []
        id = equipment['id']
        # 在 vcr_ids 中查找匹配的 id
        if id in vcr_ids:
            # 使用 find_parent_id 获取与当前录像机关联的设备
            results = find_parent_id(id)
            # 检查是否有结果
            if results:
                # 获取字段名列表 sqlalemy专属
                # keys = results[0]._mapping.keys()
                # 使用 find_parent_id 获取与当前录像机关联的设备
                # children = [row_to_dict(result, keys) for result in results]

                # 将 children 赋值给当前记录的 'children' 字段
                equipment_list[i]['children'] = results
            else:
                equipment_list[i]['children'] = []
    return equipment_list


def add_rtsp_mp4_to_cameras(equipment_list):
    """
    为设备列表中的摄像头类型设备添加RTSP和MP4字段
    参数:
    - equipment_list: 设备列表，每个设备包含相关信息
    返回:
    - 更新后的设备列表，摄像头设备会新增rtsp和mp4字段
    """
    for i, equipment in enumerate(equipment_list):
        # 检查是否为摄像头类型
        if equipment.get('equipment_type') == '摄像头':
            id = equipment['id']
            zlm_mp4 = db.session.query(Zlk_data.zlk_mp4).filter(Zlk_data.equipment_id == id).first()
            mp4 = zlm_mp4.zlk_mp4 if zlm_mp4 else None
            zlm_rtsp = db.session.query(Zlk_data.zlk_rtsp).filter(Zlk_data.equipment_id == id).first()
            rtsp = zlm_rtsp.zlk_rtsp if zlm_rtsp else None
            equipment_list[i]['rtsp'] = rtsp if rtsp else None
            equipment_list[i]['mp4'] = mp4  if mp4 else None
    return equipment_list

# 判断是否可以对象
def safe_eval(data):
    try:
        # 尝试解析 em_id 为列表或其他有效的 Python 表达式
        eval_result = eval(data)

        # 检查是否是列表（假设 em_id 是一个列表）
        if isinstance(eval_result, list):
            return eval_result
        else:
            raise ValueError("data 不是有效的列表格式")
    except (SyntaxError, NameError, ValueError) as e:
        # 捕获 eval 过程中的异常并给出相应提示
        print(f"错误: data 格式不正确，无法解析！")
        print(f"详细错误信息: {e}")
        return None  # 返回 None 或其他适当的值来处理错误

# 获取监控点下方详情  默认为当天
def datainfo(equipment_id,now):
    # 1为以前时间  2为当天时间
    if now == 1:
        filters = [Algorithm_result.Equipment_id == equipment_id, db.func.date(Algorithm_result.res_time) < datetime.now().date()]
    else:
        filters = [Algorithm_result.Equipment_id == equipment_id, db.func.date(Algorithm_result.res_time) == datetime.now().date()]

    if len(filters) >= 2:
        query_filter = and_(*filters)
    else:
        query_filter = filters[0] if filters else None

    res = db.session.query(Algorithm_library.algorithm_name,Algorithm_config.conf_name,Algorithm_result.res_time,Algorithm_result.res_type,Algorithm_result.id.label('res_id')
                           ).join(Algorithm_config, Algorithm_config.Algorithm_library_id == Algorithm_library.id
                           ).join(Algorithm_result,Algorithm_config.id == Algorithm_result.Algorithm_config_id
                           ).filter(query_filter).order_by(Algorithm_result.res_time.desc()).limit(50).all()
    data = [{'algorithm_name': i.algorithm_name, 'conf_name':i.conf_name,'res_time':(i.res_time).strftime("%Y-%m-%d %H:%M:%S"),'res_type':type_status[int(i.res_type)-1]['value'],'res_id':i.res_id} for i in res]
    return data


# 获取视频为录像机子集或者特殊摄像头的返回格式  参数为  父级id  子集通道code(更新后的type和equipment_aisles入参不需要)
def get_children_rtsp(id, code, type, equipment_aisles=None):
    # 校验入参非空
    if not all([id, code]):
        return None

    # 多条件查询设备：id + code必须同时满足
    parent_data = db.session.query(Equipment).filter(
        Equipment.parent_id == id,
        Equipment.code == code,
    ).first()
    # 校验设备是否存在
    if not parent_data:
        return None
    # 校验zlk_dat_id是否存在
    if not parent_data.zlk_dat_id:
        return None
    # 通过zlk_dat_id查询流媒体数据，获取zlk_rtsp
    zlk_data = db.session.query(Zlk_data).filter(Zlk_data.id == parent_data.zlk_dat_id).first()
    if zlk_data:
        result = {
            'rtsp': zlk_data.zlk_rtsp if zlk_data.zlk_rtsp else None,
            'mp4': zlk_data.zlk_mp4 if zlk_data.zlk_mp4 else None
        }
    else:
        result = None

    db.session.close()
    return result

def get_camera_rtsp(equipment_ip):
    # 校验入参非空
    if not equipment_ip:
        return None
    parent_data = db.session.query(Equipment).filter(
        Equipment.equipment_ip == equipment_ip
    ).first()
    # 校验设备是否存在
    if not parent_data:
        return None
    # 校验zlk_dat_id是否存在
    # if not parent_data.zlk_dat_id:
    #     return None
    # 通过zlk_dat_id查询流媒体数据，获取zlk_rtsp
    zlk_data = db.session.query(Zlk_data).filter(Zlk_data.id == parent_data.zlk_dat_id).first()
    if zlk_data:
        result = {
            'rtsp': zlk_data.zlk_rtsp if zlk_data.zlk_rtsp else None,
            'mp4': zlk_data.zlk_mp4 if zlk_data.zlk_mp4 else None
        }
    else:
        result = None
    db.session.close()
    return result
# # 获取视频为录像机子集或者特殊摄像头的返回格式  参数为  父级id  子集通道code
# def get_children_rtsp(id,code,type,equipment_aisles=None):
#     # 检查 id 是否为 None 或者数据库中不存在对应的记录
#     if id is None:
#         return None
#
#     parent_data = db.session.query(Equipment).filter(Equipment.id == id).first()
#
#     # 检查 parent_data 是否存在
#     if parent_data is None:
#         return None
#
#     # 检查 parent_data.VCR_data_id 是否存在再查询 vcr_data
#     if parent_data.VCR_data_id is not None:
#         vcr_data = db.session.query(VCR_data).filter(VCR_data.id == parent_data.VCR_data_id).first()
#     else:
#         vcr_data = None
#
#     user = parent_data.equipment_uname
#     # password = urllib.parse.quote(parent_data.equipment_password)
#     password = parent_data.equipment_password
#     ip = parent_data.equipment_ip
#
#     if parent_data.manufacturer_type == '海康':
#         if type == 1:
#             result = 'rtsp://{}:{}@{}:554/Streaming/Unicast/Channels/{}'.format(user,password,ip,code)
#         else:
#             result = 'rtsp://{}:{}@{}:554/Streaming/Channels/{}'.format(user, password, ip, code)
#     elif parent_data.manufacturer_type == '宇视':
#             result = 'rtsp://{}:{}@{}:554/unicast/c{}/s1/live'.format(user,password,ip,equipment_aisles)
#     elif parent_data.manufacturer_type == '大华' and vcr_data and vcr_data.vcr_way == 'Onvif':
#         # 查找子设备中对应的通道，使用其Onvif_rtsp_url
#         child_device = db.session.query(Equipment).filter(
#             Equipment.parent_id == id,
#             Equipment.equipment_aisles == equipment_aisles
#         ).first()
#
#         if child_device and child_device.Onvif_rtsp_url:
#             # 在URL中添加用户名和密码
#             onvif_rtsp = child_device.Onvif_rtsp_url
#             if onvif_rtsp.startswith('rtsp://'):
#                 # 在RTSP协议后添加认证信息
#                 result = 'rtsp://{}:{}@{}'.format(user, password, onvif_rtsp[7:])
#             else:
#                 result = None
#         else:
#             result = None
#     else:
#         result = None
#
#     return result


# 获取录像机下方设备基础信息-与状态
def VCR_data_info(username, password, ip, port):
    from common.nvr_sync_runtime import hik_channels
    return hik_channels(username, password, ip, port)

def CVR_data_info(username,password,ip,port):
    # 如果有命名空间前缀，则去掉
    def remove_namespace(tag):
        return tag.split('}')[-1] if '}' in tag else tag

    def xml_to_dict(element):
        result_list = []
        for child in element:
            result = {}
            if child.text is not None:
                result[remove_namespace(child.tag)] = child.text.strip()
            if len(child) > 0:
                result[remove_namespace(child.tag)] = xml_to_dict(child)
            result_list.append(result)
        return result_list

    # 状态xml序列化
    def parse_xml(response_info):

        # 使用 strip() 去除响应文本中的空白字符
        root = ET.fromstring(response_info.text.strip())

        # 将 XML 转换为列表套字典结构
        xml_dict = (xml_to_dict(root))

        # 定义存储结果的列表
        device_status_list = []

        for i in xml_dict:
            channel_info = {}

            # 获取通道ID
            channel_info['id'] = i['InputProxyChannelStatus'][0]['id']

            # 获取IP地址
            channel_info['ip_address'] = i['InputProxyChannelStatus'][1]['sourceInputPortDescriptor'][2]['ipAddress']

            # 获取是否在线状态
            channel_info['online'] = i['InputProxyChannelStatus'][2]['online']

            # 获取用户名
            channel_info['username'] = i['InputProxyChannelStatus'][1]['sourceInputPortDescriptor'][5]['userName']

            # 获取密码强度状态
            channel_info['password_status'] = i['InputProxyChannelStatus'][6]['SecurityStatus'][0]['PasswordStatus']

            device_status_list.append(channel_info)


        return device_status_list

    # 数据xml序列化
    def xml_data(response_info):

        # 使用 strip() 去除响应文本中的空白字符
        root = ET.fromstring(response_info.text.strip())

        # 将 XML 转换为列表套字典结构
        xml_dict = (xml_to_dict(root))

        device_status_list = []

        for i in xml_dict:
            channel_info = {}

            # 监控点ID
            channel_info['id'] = i['InputProxyChannel'][0]['id']

            # 名称
            #channel_info['name'] = i['InputProxyChannel'][1]['name']
            channel_info['name'] = i['InputProxyChannel'][1].get('name', '未命名') if i['InputProxyChannel'][1].get(
                'name') else '未命名'

            # IP地址
            channel_info['ip_address'] = i['InputProxyChannel'][3]['sourceInputPortDescriptor'][2]['ipAddress']

            # # 管理端口号
            channel_info['managePortNo'] = i['InputProxyChannel'][3]['sourceInputPortDescriptor'][3]['managePortNo']

            # # 用户名
            channel_info['username'] = i['InputProxyChannel'][3]['sourceInputPortDescriptor'][5]['userName']

            device_status_list.append(channel_info)
        return device_status_list

    # 数据xml序列化 帧率信息
    def xml_info(response_info):

        # 使用 strip() 去除响应文本中的空白字符
        root = ET.fromstring(response_info.text.strip())

        # 将 XML 转换为列表套字典结构
        xml_dict = (xml_to_dict(root))

        device_status_list = []

        for i in xml_dict:
            channel_info = {}

            # 监控点ID
            channel_info['id'] = i.get('StreamingChannel', [{}])[4].get('Video', [{}])[1].get('dynVideoInputChannelID',
                                                                                              None)
            # 监控点名称
            channel_name = i.get('StreamingChannel', [{}])[1].get('channelName', '')
            if channel_name.endswith('2'):
                continue
            channel_info['channelName'] = channel_name

            # 码流类型
            channel_info['videoCodecType'] = i.get('StreamingChannel', [{}])[4].get('Video', [{}])[2].get(
                'videoCodecType', None)

            # 视频分辨率宽高
            video_info = i.get('StreamingChannel', [{}])[4].get('Video', [{}])
            # channel_info['videoResolutionWidth'] = video_info[4].get('videoResolutionWidth', None)
            # channel_info['videoResolutionHeight'] = video_info[5].get('videoResolutionHeight', None)

            # 比特率
            channel_info['constantBitRate'] = video_info[7].get('constantBitRate', None)

            # # 帧率
            # maxFrameRate = video_info[9].get('maxFrameRate', '0')
            # channel_info['maxFrameRate'] = str(30) if maxFrameRate == '0' else str(int(int(maxFrameRate) / 100))


            device_status_list.append(channel_info)
            print(device_status_list,'33333333333333333333333333333')
        return device_status_list

    try:

        # 录像机下方信息
        url = 'http://{}:{}/ISAPI/ContentMgmt/InputProxy/channels'.format(ip,port)
        response = requests.get(url, auth=HTTPDigestAuth(username, password),timeout=15)


        # 录像机下方状态
        url_status = 'http://{}:{}/ISAPI/ContentMgmt/InputProxy/channels/status'.format(ip, port)
        response_status = requests.get(url_status, auth=HTTPDigestAuth(username, password),timeout=5)

        # 录像机下方通道信息
        # url_info = 'http://{}:{}/ISAPI/Streaming/channels'.format(ip, port)
        # response_info = requests.get(url_info, auth=HTTPDigestAuth(username, password), timeout=5)

        url_info = 'http://{}:{}/ISAPI/ContentMgmt/StreamingProxy/channels'.format(ip, port)
        response_info = requests.get(url_info, auth=HTTPDigestAuth(username, password), timeout=5)
        # 当请求状态为200的时候
        if response_status.status_code == 200 and response.status_code == 200 and response_info.status_code == 200:

            # device_status_list1 为录像机状态数据   device_status_list2 为录像机信息数据  device_status_list3 帧率信息
            device_status_list1,device_status_list2,device_status_list3 = parse_xml(response_status),xml_data(response),xml_info(response_info)
            # 合并数据
            merged_data = [
                {
                    **status,
                    # 来自 device_status_list2
                    **next((info for info in device_status_list1 if info['id'] == status['id']), {}),
                    # 来自 device_status_list1
                    **next((frame for frame in device_status_list3 if frame['id'] == status['id']), {})
                    # 来自 device_status_list3
                }
                for status in device_status_list2
            ]
            return merged_data

        else:
            return []

    except Exception as e:
        print(e)
        return []

# 宇视录像机数据
def YSVCR_data_info(username,password,ip,port):
    # 如果有命名空间前缀，则去掉
    def remove_namespace(tag):
        return tag.split('}')[-1] if '}' in tag else tag

    def xml_to_dict(element):
        result_list = []
        for child in element:
            result = {}
            if child.text is not None:
                result[remove_namespace(child.tag)] = child.text.strip()
            if len(child) > 0:
                result[remove_namespace(child.tag)] = xml_to_dict(child)
            result_list.append(result)
        return result_list

    # 通道信息
    def channel_info(response_info):
        # 检查响应状态码
        json_response = response_info.json()
        if json_response.get('Response', {}).get('StatusCode', -1) != 0:
            return []
        
        # 解析JSON数据
        device_list = []
        
        # 遍历DetailInfos中的每个设备
        for item in json_response.get('Response', {}).get('Data', {}).get('DetailInfos', []):
            # 只处理Status为0或1的记录，忽略Status为2的空位
            status = item.get('Status')
            if status not in [0, 1]:
                continue
                
            channel_info = {}

            # 获取通道ID
            channel_info['id'] = item.get('ID')

            # 获取IP地址
            channel_info['ip_address'] = item.get('AddressInfo', {}).get('Address')

            # 获取名称
            channel_info['name'] = item.get('Name')

            # 获取在线状态
            channel_info['online'] = item.get('Status')

            channel_info['Manufacturer'] = item.get('Manufacturer')

            device_list.append(channel_info)

        return device_list

     # 数据xml序列化 帧率信息
    def stream_info(response_info):
        # 检查响应状态码
        json_response = response_info.json()
        if json_response.get('Response', {}).get('StatusCode', -1) != 0:
            return []
        
        # 定义存储结果的列表
        stream_list = []
        
        # 编码格式映射
        encode_format_map = {
            0: 'MJPEG',
            1: 'H.264',
            2: 'H.265'
        }
        
        # 遍历VideoStreamInfos中的每个流信息，只处理ID为0的主码流
        for item in json_response.get('Response', {}).get('Data', {}).get('VideoStreamInfos', []):
            # 只处理ID为0的主码流信息
            if item.get('ID') != 0:
                continue
                
            channel_info = {}
            
            # 获取编码格式
            encode_format = item.get('VideoEncodeInfo', {}).get('EncodeFormat')
            channel_info['videoCodecType'] = encode_format_map.get(encode_format, 'Unknown')
            
            # 获取分辨率宽高
            resolution = item.get('VideoEncodeInfo', {}).get('Resolution', {})
            channel_info['videoResolutionWidth'] = resolution.get('Width')
            channel_info['videoResolutionHeight'] = resolution.get('Height')
            
            # 获取码率
            channel_info['constantBitRate'] = item.get('VideoEncodeInfo', {}).get('BitRate')
            
            # 获取帧率
            channel_info['maxFrameRate'] = item.get('VideoEncodeInfo', {}).get('FrameRate')
            
            stream_list.append(channel_info)
            
        return stream_list

    try:
        # 录像机通道信息
        url = 'http://{}:{}/LAPI/V1.0/Channels/System/ChannelDetailInfos'.format(ip,port)
        response = requests.get(url, auth=HTTPDigestAuth(username, password),timeout=15)

        # 检查主通道信息接口状态
        if response.status_code != 200:
            return []
            
        # 解析主通道信息
        device_list = channel_info(response)
        
        # 如果没有设备信息，直接返回空列表
        if not device_list:
            return []

        # 存储所有通道的流信息
        all_stream_info = []
        
        # 遍历每个通道，获取其流信息
        for device in device_list:
            channel_id = device['id']
            # 录像机下方状态（每个通道的流信息）
            url_status = 'http://{}:{}/LAPI/V1.0/Channels/{}/Media/Video/Streams/DetailInfos'.format(ip, port, channel_id)
            response_status = requests.get(url_status, auth=HTTPDigestAuth(username, password), timeout=5)
            
            # 检查流信息接口状态
            if response_status.status_code == 200:
                stream_data = stream_info(response_status)
                # 为每个流信息添加通道ID，以便后续匹配
                for stream in stream_data:
                    stream['channel_id'] = channel_id
                # 将流信息添加到总列表中
                all_stream_info.extend(stream_data)

        # 合并数据
        merged_data = []
        # 创建一个以通道ID为键的流信息字典，方便查找
        stream_dict = {}
        for stream in all_stream_info:
            stream_dict[stream['channel_id']] = stream
        
        for device in device_list:
            # 获取当前设备对应的流信息
            matching_stream = stream_dict.get(device['id'], {})
            # 删除channel_id字段，避免冗余
            matching_stream.pop('channel_id', None)
            
            # 合并设备信息和流信息
            merged_item = {**device, **matching_stream}
            merged_data.append(merged_item)
            
        return merged_data

    except Exception as e:
        print(f"Error in YSVCR_data_info: {e}")
        return []


def Dahua_data_info(username, password, ip, port):
    """
    通过ONVIF协议获取大华设备的通道信息
    :param username: 用户名
    :param password: 密码
    :param ip: 设备IP地址
    :param port: 端口号
    :return: 通道信息列表
    """
    try:
        # 导入ONVIF适配器
        from tool.onvif_adapter import ONVIFAdapter

        # 创建ONVIF适配器实例，增加超时设置
        adapter = ONVIFAdapter(ip, port, username, password)

        # 连接设备
        if not adapter.connect():
            return []

        # 获取视频源信息 (包含Framerate和Resolution)
        video_sources = adapter.get_video_sources()
        if not video_sources:
            return []

        # 获取所有配置文件的流URI（一次性获取，避免重复调用）
        stream_uris = adapter.get_stream_uri_for_all_profiles()
        if not stream_uris:
            return []

        # 获取所有视频源的OSD信息（一次性获取，避免重复调用）
        osd_infos = adapter.get_osds()

        # 创建OSD信息字典，以token为键
        osd_dict = {}
        if osd_infos:
            for osd_info in osd_infos:
                if 'error' not in osd_info and osd_info.get('osds'):
                    osd_dict[osd_info['video_source_token']] = osd_info['osds']

        # 创建流URI字典，以profile_token为键，提高查找效率
        stream_uri_dict = {}
        for stream_uri in stream_uris:
            profile_token = stream_uri.get('profile_token', '')
            stream_uri_dict[profile_token] = stream_uri.get('uri', '')

        # 解析并组合数据
        result = []
        for i, video_source in enumerate(video_sources):
            channel_data = {}

            # 通道ID (使用索引作为ID)
            channel_data['id'] = i

            # 从VideoSource获取Framerate和Resolution
            channel_data['maxFrameRate'] = getattr(video_source, 'Framerate', None)
            if hasattr(video_source, 'Resolution') and video_source.Resolution:
                channel_data['videoResolutionWidth'] = getattr(video_source.Resolution, 'Width', None)
                channel_data['videoResolutionHeight'] = getattr(video_source.Resolution, 'Height', None)

            # 从OSD获取通道名称 (Type为Plain的PlainText)
            channel_name = f"Channel {i}"
            if video_source.token in osd_dict:
                for osd in osd_dict[video_source.token]:
                    # 查找Type为Plain的OSD
                    if hasattr(osd, 'TextString') and osd.TextString and \
                            hasattr(osd.TextString, 'Type') and osd.TextString.Type == 'Plain' and \
                            hasattr(osd.TextString, 'PlainText') and osd.TextString.PlainText:
                        channel_name = osd.TextString.PlainText
                        break
            channel_data['name'] = channel_name

            # 查找主码流URI (subtype=0)，使用优化的字典查找方式
            main_stream_uri = None
            # 构造可能的profile_token格式
            possible_tokens = [
                f"MediaProfile{video_source.token}",
                f"{video_source.token}_profile",
                f"profile_{video_source.token}"
            ]

            # 查找主码流URI
            for base_token in possible_tokens:
                # 精确匹配主码流
                for profile_token, uri in stream_uri_dict.items():
                    if profile_token.startswith(base_token) and ('subtype=0' in uri or 'MainStream' in profile_token):
                        main_stream_uri = uri
                        break
                if main_stream_uri:
                    break

                # 如果没有找到精确的主码流，使用第一个匹配的
                if not main_stream_uri:
                    for profile_token, uri in stream_uri_dict.items():
                        if profile_token.startswith(base_token):
                            main_stream_uri = uri
                            break
                    if main_stream_uri:
                        break

            channel_data['main_stream_uri'] = main_stream_uri
            result.append(channel_data)

        return result

    except Exception as e:
        print(f"Error in Dahua_data_info: {e}")
        return []


#获取监测点的运行状态
def getDevRunStatus(device_list):
    return  getRunStatus(device_list)



# 去除收尾空格方法
def strip_whitespace(value):
    if isinstance(value, str):
        return value.strip()
    return value


# 合并相同 menu_id(参数) 的权限列表
def merge_permissions(data):
    """
    合并相同 menu_id 的权限列表。

    参数:
    data (list): 包含权限数据的列表，每个字典元素包含 'menu_id' 和 'permissions_list'。

    返回:
    list: 每个 menu_id 的合并后的权限列表。
    """

    menu_permissions = defaultdict(set)

    for item in data:
        permissions_list = item['permissions_list']

        # 检查 permissions_list 是否是有效的字符串类型
        if isinstance(permissions_list, str):
            try:
                # 手动去掉中括号，转换为集合
                permissions = set(permissions_list.strip('[]').split(','))
                menu_permissions[item['menu_id']].update(permissions)
            except Exception as e:
                print(f"Error processing permissions_list for menu_id {item['menu_id']}: {e}")
        else:
            print(f"Invalid permissions_list format for menu_id {item['menu_id']}")

    # 将合并后的 permissions_list 转换回字符串形式
    merged_data = [
        {'menu_id': menu_id, 'permissions_list': sorted(list(permissions))}
        for menu_id, permissions in menu_permissions.items()
    ]

    return merged_data

def _algorithm_display_fields(text):
    from service.algorithm_package_validation import split_algorithm_filename_fields
    return split_algorithm_filename_fields(text)


def extract_chinese_without_trailing_underscore(text):
    parts = _algorithm_display_fields(text)
    return parts[0] + '_' + parts[1]


def extract_chinese(text):
    if text in ('人数统计_全身', '人数统计_头肩'):
        return text
    return _algorithm_display_fields(text)[1]


# 时间转换方法
def format_datetime(dt):
    """
        将 datetime 对象格式化为 YYYY-MM-DD HH:MM:SS 格式。

    参数:
    - dt (datetime): 一个 datetime 对象

    返回:
    - str: 格式化后的日期字符串，格式为 "YYYY-MM-DD HH:MM:SS"
    """
    # 格式化为 "YYYY-MM-DD HH:MM:SS" 格式
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# 获取机器唯一uuid代码编写(Windwos，Linux)
def get_machine_uuid():
    host_machine_id = os.environ.get('HOST_MACHINE_ID')
    if host_machine_id:
        return host_machine_id
    # system_name = platform.system()
    #
    # if system_name == "Linux":
    #     try:
    #         return subprocess.check_output("cat /etc/machine-id", shell=True).decode().strip()
    #     except Exception as e:
    #         return f"获取 Linux UUID 出错: {e}"
    #
    # elif system_name == "Windows":
    #     try:
    #         return subprocess.check_output("wmic csproduct get UUID", shell=True).decode().split("\n")[1].strip()
    #     except Exception as e:
    #         return f"获取 Windows UUID 出错: {e}"
    #
    # else:
    #     return "不支持的操作系统"

# 自动加载字体路径（兼容 Windows + Linux）
def get_system_font():
    system = platform.system()
    if system == 'Windows':
        win_font = "C:/Windows/Fonts/arial.ttf"
        if os.path.exists(win_font):
            return win_font
    elif system == 'Linux':
        linux_font = "/data/AIGO/platform_start/runtime/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if os.path.exists(linux_font):
            return linux_font
    raise RuntimeError("未找到系统字体，请手动指定字体路径")

# 生成随机验证码文本
def generate_captcha_text(length=4):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# 生成验证码图片
def generate_captcha_image(text, width=160, height=60):
    def random_color(start=64, end=255):
        return (random.randint(start, end), random.randint(start, end), random.randint(start, end))

    # 背景渐变
    image = Image.new('RGB', (width, height), random_color(200, 255))
    draw = ImageDraw.Draw(image)

    # 随机干扰线
    for _ in range(8):
        draw.line([
            (random.randint(0, width), random.randint(0, height)),
            (random.randint(0, width), random.randint(0, height))
        ], fill=random_color(100, 200), width=2)

    # 随机噪点
    for _ in range(1000):
        draw.point((random.randint(0, width), random.randint(0, height)), fill=random_color(150, 255))

    font_path = get_system_font()
    font_size = 36

    # 每个字符独立绘制、旋转
    for i, char in enumerate(text):
        font = ImageFont.truetype(font_path, font_size + random.randint(-2, 2))
        char_img = Image.new('RGBA', (40, 60), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((5, 10), char, font=font, fill=random_color(50, 150))

        rotated = char_img.rotate(random.randint(-30, 30), expand=1)
        image.paste(rotated, (i * 35 + random.randint(-2, 2), random.randint(0, 10)), rotated)

    # 应用模糊滤镜（更像图像验证码）
    image = image.filter(ImageFilter.GaussianBlur(0.5))
    return image

def convert_data_format(res):
    result = []
    for group in res:
        print(group,'555555555')
        if not group:
            continue
        common_type = group[0]['type']
        # 使用列表推导式删除 'type' 键
        data_without_type = [{k: v for k, v in item.items() if k != 'type' and  k != 'color'} for item in group]
        data = {'type': common_type, 'data': data_without_type}
        result.append([data])
    return result

def convert_time_format(time_str):
    """
    将时间字符串从 'YYYYMMDDHHMMSS' 格式转换为 ISO 8601 格式 'YYYY-MM-DDTHH:MM:SS.sss+08:00'
    """
    if not time_str:
        raise ValueError("时间字符串不能为空")

    # 移除非法字符（如 't'）
    cleaned_time_str = re.sub(r'[^0-9]', '', time_str)

    # 解析时间字符串
    try:
        dt = datetime.strptime(cleaned_time_str, '%Y%m%d%H%M%S')
    except ValueError as e:
        raise ValueError(f"时间字符串格式错误: {cleaned_time_str}") from e

    # 转换为 ISO 8601 格式
    iso_time = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+08:00'
    return iso_time
