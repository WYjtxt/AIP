from service.algorithm_archive_recovery import (
    AlgorithmArchiveRecoveryError, recover_camera_algorithm_archive)
from service.algorithm_package_validation import (AlgorithmPackageError, read_uploaded_zip,
    open_package_zip, inspect_algorithm_package, inspect_algorithm_group,
    require_matching_devices, require_server_package, require_camera_package,
    canonical_algorithm_zip, same_model_slot)
import bdb
import datetime
import os
import ast
import dbutils.steady_db
from flask import jsonify, request, Blueprint, make_response
from config.configs import *
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from model.ai_camera import *
from sqlalchemy import and_, func, update, select, text, cast, Integer, or_
import yaml
import io
import zipfile
from datetime import datetime, timedelta
import cv2
from urllib.parse import urlparse, quote
import time
import json
import random
import string
import asyncio
from sqlalchemy.exc import SQLAlchemyError
from data.algorithm_model_data import *
import config.configs as configs
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tool.manual_extrinsic_H3 import compute_homography_with_error
from data.ai_camera_data import AiCameraCalibrationData

# def handle_algorithm_upload_single_aicam(uploaded_file, algorithm_status, algorithm_ps, equipment_ids):
#     """
#     处理算法子包上传逻辑
#     :param uploaded_file: 上传的文件
#     :param algorithm_status: 算法运行状态 1运行 2停止
#     :param algorithm_ps: 算法备注
#     :param equipment_ids: 设备ID列表，用逗号分隔的字符串
#     """
#
#     def call_camera_api(camera_ip, file_content, algorithm_filename):
#         """
#         调用摄像头API上传算法
#         :param camera_ip: 摄像头IP
#         :param file_content: 文件内容（ZIP压缩包）
#         :param algorithm_filename: 文件名
#         :return: 响应结果
#         """
#         try:
#             url = f"http://{camera_ip}:5000/model_view/algorithm_upload_sub"
#             files = {'files': (algorithm_filename, io.BytesIO(file_content), 'application/zip')}
#             response = requests.post(url, files=files, timeout=60)
#             return response.json()
#         except Exception as e:
#             return {'code': 500, 'msg': f'请求失败: {str(e)}'}
#
#     # 解析设备ID列表
#     if not equipment_ids:
#         return jsonify({'code': 400, 'msg': '请提供设备ID列表'})
#
#     try:
#         equipment_id_list = [int(eid.strip()) for eid in equipment_ids.split(',') if eid.strip()]
#     except ValueError:
#         return jsonify({'code': 400, 'msg': '设备ID格式不正确'})
#
#     if not equipment_id_list:
#         return jsonify({'code': 400, 'msg': '设备ID列表为空'})
#
#     # 获取设备信息
#     equipment_list = db.session.query(Equipment).filter(
#         Equipment.id.in_(equipment_id_list)
#     ).all()
#
#     if not equipment_list:
#         return jsonify({'code': 400, 'msg': '未找到指定的设备'})
#
#     try:
#         file_size = os.fstat(uploaded_file.stream.fileno()).st_size
#         max_file_size = 100 * 1024 * 1024  # 100MB
#         if file_size > max_file_size:
#             return jsonify({'code': 400, 'msg': '文件大小超过100MB限制，请重新上传'})
#
#         if uploaded_file and uploaded_file.filename.endswith('.zip'):
#
#             # 读取压缩包内容
#             zip_content = uploaded_file.read()
#             with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
#                 yaml_filename = 'data.yaml'
#                 # 检查 YAML 文件是否存在
#                 if yaml_filename in zip_ref.namelist():
#                     # 解析 YAML 文件
#                     with zip_ref.open(yaml_filename) as yaml_file:
#                         yaml_data = yaml.safe_load(yaml_file)
#                         labels = yaml_data.get('lables', [])
#                         algorithm_type_list = [label['lable'] for label in labels]
#                         print(algorithm_type_list, type(algorithm_type_list), '----------------------------')
#                         type_num = yaml_data.get('nc', None)  # 检测类型数量
#                         if type_num is None:
#                             return jsonify({'code': 400, 'msg': '压缩包文件不符合！'})
#                         algorithm_type = '1' if type_num > 1 else '2'
#
#                 # 检查后缀为bmodel的算法文件是否存在
#                 mine = db.session.query(Mine).first()
#                 mine_name = mine.mine_name
#                 file_extension = '.bmodel'
#                 files_to_check = [f for f in zip_ref.namelist() if f.endswith(file_extension)]
#                 if files_to_check:
#                     algorithm_filename_old = files_to_check[0]
#                     # 尝试使用UTF-8解码文件名，如果失败，尝试使用GBK
#                     try:
#                         algorithm_filename = algorithm_filename_old.encode('cp437').decode('utf-8')
#                     except (UnicodeDecodeError, UnicodeEncodeError) as e:
#                         try:
#                             algorithm_filename = algorithm_filename_old.encode('cp437').decode('gbk')
#                         except (UnicodeDecodeError, UnicodeEncodeError) as e:
#                             algorithm_filename = algorithm_filename_old
#
#                     words_in_filename = algorithm_filename[:-len(file_extension)].split('_')
#                     words_in_filename[0] = mine_name
#                     filename = '_'.join(words_in_filename)
#                     analysis_type = words_in_filename[1]
#                     algorithm_version = words_in_filename[9]
#                     trade = words_in_filename[7]
#                     chip_type = words_in_filename[8]
#                     model_type_name = words_in_filename[2]
#                     model_name = words_in_filename[3]
#                     template_small_name = words_in_filename[4]
#                     algorithm_trade_type = f"{trade}-{chip_type}"
#
#                     alg_parent = words_in_filename[10]
#                     alg_child = words_in_filename[11]
#
#                     trade_type_id = db.session.query(Dict_data.data_id).filter(
#                         func.lower(Dict_data.data_value) == trade).first()
#                     if trade_type_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该厂商，需在厂商编码表中添加'})
#
#                     model_type_name_id = db.session.query(Model_template_config_type_3588.id).filter(
#                         Model_template_config_type.model_type_name == model_type_name).first()
#                     if model_type_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型大类，需在模型大类表中添加'})
#
#                     model_name_id = db.session.query(Model_template_config_3588.id).filter(
#                         Model_template_config.model_name == model_name).first()
#                     if model_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型模板，需在模型名称表中添加'})
#
#                     model_small_name_id = db.session.query(Model_template_small_3588.id).filter(
#                         Model_template_small.template_small_name == template_small_name).first()
#                     if model_small_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型小类，需在模型小类表中添加'})
#
#
#                     config_data = Algorithm_library_3588(
#                         algorithm_file_name=algorithm_filename,
#                         algorithm_name=filename,
#                         algorithm_type=algorithm_type,
#                         algorithm_type_list=str(algorithm_type_list),
#                         algorithm_status=algorithm_status,
#                         algorithm_version=algorithm_version,
#                         algorithm_trade_type=trade_type_id[0],
#                         algorithm_ps=algorithm_ps,
#                         model_type_name=model_type_name,
#                         model_name=model_name,
#                         template_small_name=template_small_name,
#                         algorithm_parent=alg_parent if alg_parent else 1,
#                         algorithm_child=alg_child if alg_child else 1,
#                         analysis_type=analysis_type
#                     )
#                     db.session.add(config_data)
#                     db.session.flush()
#
#                     # 将算法检测列表写入检测类型表
#                     for label in labels:
#                         algorithm_test_type_res = Algorithm_test_type_3588(
#                             test_type_ename=label['lable'],
#                             test_type_cname=label['name'],
#                             Algorithm_library_id=config_data.id
#                         )
#                         db.session.add(algorithm_test_type_res)
#
#                     db.session.commit()
#                     algorithm_libary_id = config_data.id
#
#                     # 并行调用各个摄像头的API
#                     success_devices = []
#                     failed_devices = []
#
#                     def upload_to_device(equipment):
#                         """上传算法到单个设备"""
#                         try:
#                             camera_ip = equipment.equipment_ip
#                             if not camera_ip:
#                                 return {
#                                     'equipment_id': equipment.id,
#                                     'equipment_name': equipment.equipment_name,
#                                     'success': False,
#                                     'msg': '设备IP为空'
#                                 }
#
#                             result = call_camera_api(camera_ip, zip_content, uploaded_file.filename)
#
#                             if result.get('code') == 200:
#                                 algorithm_camera_id = None
#                                 if result.get('data') and isinstance(result['data'], dict):
#                                     algorithm_camera_id = result['data'].get('algorithm_id')
#
#                                 return {
#                                     'equipment_id': equipment.id,
#                                     'equipment_name': equipment.equipment_name,
#                                     'camera_ip': camera_ip,
#                                     'success': True,
#                                     'msg': '上传成功',
#                                     'algorithm_camera_id': algorithm_camera_id  # 保存摄像头返回的算法ID
#                                 }
#                             else:
#                                 return {
#                                     'equipment_id': equipment.id,
#                                     'equipment_name': equipment.equipment_name,
#                                     'camera_ip': camera_ip,
#                                     'success': False,
#                                     'msg': result.get('msg', '未知错误')
#                                 }
#                         except Exception as e:
#                             return {
#                                 'equipment_id': equipment.id,
#                                 'equipment_name': equipment.equipment_name,
#                                 'success': False,
#                                 'msg': str(e)
#                             }
#
#                     # 使用线程池并行调用
#                     with ThreadPoolExecutor(max_workers=min(10, len(equipment_list))) as executor:
#                         future_to_equipment = {
#                             executor.submit(upload_to_device, eq): eq
#                             for eq in equipment_list
#                         }
#
#                         for future in as_completed(future_to_equipment):
#                             result = future.result()
#                             if result['success']:
#                                 success_devices.append(result)
#                             else:
#                                 failed_devices.append(result)
#
#                     # 记录成功的设备到关联表
#                     for device in success_devices:
#                         try:
#                             # 根据设备IP查找对应的算力资源ID
#                             camera_ip = device.get('camera_ip')
#                             computing_resource_id = None
#
#                             if camera_ip:
#                                 computing_equipment = db.session.query(Computing_equipment).filter(
#                                     Computing_equipment.computing_ip == camera_ip
#                                 ).first()
#
#                                 if computing_equipment:
#                                     computing_resource_id = computing_equipment.id
#
#                             relation = AlgorithmLibrary2Camera(
#                                 equipment_id=device['equipment_id'],
#                                 computing_resource_id=computing_resource_id,
#                                 algorithm_libary_id=algorithm_libary_id,
#                                 algorithm_camera_id=device.get('algorithm_camera_id')  # 写入摄像头返回的算法ID
#                             )
#                             db.session.add(relation)
#                         except Exception as e:
#                             print(f"记录设备关联失败: {e}")
#
#                     db.session.commit()
#
#                     response_data = {
#                         'algorithm_type_list': algorithm_type_list,
#                         'algorithm_type': algorithm_type,
#                         'algorithm_trade_type': algorithm_trade_type,
#                         'algorithm_version': algorithm_version,
#                         'filename': filename,
#                         'algorithm_libary_id': algorithm_libary_id,
#                         'success_count': len(success_devices),
#                         'failed_count': len(failed_devices),
#                         'success_devices': success_devices,
#                         'failed_devices': failed_devices
#                     }
#
#                     msg = f'算法添加完成，成功{len(success_devices)}个设备，失败{len(failed_devices)}个设备'
#
#                     result = {'code': 200, 'msg': msg, 'data': response_data}
#                     return jsonify(result)
#                 else:
#                     return jsonify({'code': 400, 'msg': '没有找到.bmodel文件'})
#         else:
#             return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'code': 400, 'msg': str(e)})
# def handle_algorithm_upload_single_aicam(uploaded_file, algorithm_status, algorithm_ps):
#     """
#     处理算法子包上传逻辑（上传zip压缩包到server_type=1的算力设备）
#     :param uploaded_file: 上传的文件
#     :param algorithm_status: 算法运行状态 1运行 2停止
#     :param algorithm_ps: 算法备注
#     """
#
#     def upload_to_multiple_servers(SSH_list, file_content, filename):
#         """
#         上传文件到多个服务器
#         :param SSH_list: 包含多个 SSH 对象的列表
#         :param file_content: 文件内容
#         :param filename: 文件名
#         :return: 所有服务器的上传路径或错误信息
#         """
#         upload_results = []
#
#         for ssh_client in SSH_list:
#             try:
#                 # 上传文件到服务器
#                 res = ssh_client.upload_send_file(file_content, filename)
#                 if res in ['无法上传文件', '上传中断，请稍后重试', '服务器连接异常']:
#                     upload_results.append('无法上传文件')
#                 else:
#                     upload_results.append(res)
#             except Exception as e:
#                 upload_results.append('无法上传文件')
#
#         return upload_results
#
#     try:
#         file_size = os.fstat(uploaded_file.stream.fileno()).st_size
#         max_file_size = 100 * 1024 * 1024  # 100MB
#         if file_size > max_file_size:
#             return jsonify({'code': 400, 'msg': '文件大小超过100MB限制，请重新上传'})
#
#         if uploaded_file and uploaded_file.filename.endswith('.zip'):
#             # 查找 server_type=1 的算力设备
#             computing_info = db.session.query(Computing_equipment).filter(
#                 Computing_equipment.server_type == 1
#             ).all()
#
#             if not computing_info:
#                 return jsonify({'code': 400, 'msg': '请先配置server_type=1的算力设备信息！'})
#
#             # 创建多个 SSH 实例，表示要上传的服务器
#             SSH_list = [SSH_Func(i.computing_ip, i.computing_user, i.computing_password) for i in computing_info]
#
#             # 读取压缩包内容
#             zip_content = uploaded_file.read()
#             with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
#                 yaml_filename = 'data.yaml'
#                 # 检查 YAML 文件是否存在
#                 if yaml_filename in zip_ref.namelist():
#                     # 解析 YAML 文件
#                     with zip_ref.open(yaml_filename) as yaml_file:
#                         yaml_data = yaml.safe_load(yaml_file)
#                         labels = yaml_data.get('lables', [])
#                         algorithm_type_list = [label['lable'] for label in labels]
#                         print(algorithm_type_list, type(algorithm_type_list), '----------------------------')
#                         type_num = yaml_data.get('nc', None)  # 检测类型数量
#                         if type_num is None:
#                             return jsonify({'code': 400, 'msg': '压缩包文件不符合！'})
#                         algorithm_type = '1' if type_num > 1 else '2'
#
#                 # 检查后缀为.rknn的算法文件是否存在
#                 mine = db.session.query(Mine).first()
#                 mine_name = mine.mine_name
#                 file_extension = '.rknn'
#                 files_to_check = [f for f in zip_ref.namelist() if f.endswith(file_extension)]
#                 if files_to_check:
#                     algorithm_filename_old = files_to_check[0]
#                     # 尝试使用UTF-8解码文件名，如果失败，尝试使用GBK
#                     try:
#                         algorithm_filename = algorithm_filename_old.encode('cp437').decode('utf-8')
#                     except (UnicodeDecodeError, UnicodeEncodeError) as e:
#                         try:
#                             algorithm_filename = algorithm_filename_old.encode('cp437').decode('gbk')
#                         except (UnicodeDecodeError, UnicodeEncodeError) as e:
#                             algorithm_filename = algorithm_filename_old
#
#                     words_in_filename = algorithm_filename[:-len(file_extension)].split('_')
#                     words_in_filename[0] = mine_name
#                     filename = '_'.join(words_in_filename)
#                     analysis_type = words_in_filename[1]
#                     algorithm_version = words_in_filename[9]
#                     trade = words_in_filename[7]
#                     chip_type = words_in_filename[8]
#                     model_type_name = words_in_filename[2]
#                     model_name = words_in_filename[3]
#                     template_small_name = words_in_filename[4]
#                     algorithm_trade_type = f"{trade}-{chip_type}"
#
#                     alg_parent = words_in_filename[10]
#                     alg_child = words_in_filename[11]
#
#                     trade_type_id = db.session.query(Dict_data.data_id).filter(
#                         func.lower(Dict_data.data_value) == trade).first()
#                     if trade_type_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该厂商，需在厂商编码表中添加'})
#
#                     model_type_name_id = db.session.query(Model_template_config_type_3588.id).filter(
#                         Model_template_config_type.model_type_name == model_type_name).first()
#                     if model_type_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型大类，需在模型大类表中添加'})
#
#                     model_name_id = db.session.query(Model_template_config_3588.id).filter(
#                         Model_template_config.model_name == model_name).first()
#                     if model_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型模板，需在模型名称表中添加'})
#
#                     model_small_name_id = db.session.query(Model_template_small_3588.id).filter(
#                         Model_template_small.template_small_name == template_small_name).first()
#                     if model_small_name_id is None:
#                         return jsonify({'code': 400, 'msg': '未找到该模型小类，需在模型小类表中添加'})
#
#                     # 上传整个zip压缩包到多个服务器
#                     res = upload_to_multiple_servers(SSH_list, zip_content, uploaded_file.filename)
#
#                     if '无法上传文件' not in res and '上传中断，请稍后重试' not in res and '服务器连接异常' not in res:
#                         # 数据库操作
#                         config_data = Algorithm_library_3588(
#                             algorithm_file_name=algorithm_filename,
#                             algorithm_name=filename,
#                             algorithm_type=algorithm_type,
#                             algorithm_type_list=str(algorithm_type_list),
#                             algorithm_status=algorithm_status,
#                             algorithm_version=algorithm_version,
#                             algorithm_path=str(res[0]),  # 使用第一个服务器的路径
#                             algorithm_trade_type=trade_type_id[0],
#                             algorithm_ps=algorithm_ps,
#                             model_type_name=model_type_name,
#                             model_name=model_name,
#                             template_small_name=template_small_name,
#                             algorithm_parent=alg_parent if alg_parent else 1,
#                             algorithm_child=alg_child if alg_child else 1,
#                             analysis_type=analysis_type
#                         )
#                         db.session.add(config_data)
#                         db.session.flush()
#
#                         # 将算法检测列表写入检测类型表
#                         for label in labels:
#                             algorithm_test_type_res = Algorithm_test_type_3588(
#                                 test_type_ename=label['lable'],
#                                 test_type_cname=label['name'],
#                                 Algorithm_library_id=config_data.id
#                             )
#                             db.session.add(algorithm_test_type_res)
#
#                         db.session.commit()
#                         algorithm_libary_id = config_data.id
#
#                         response_data = {
#                             'algorithm_type_list': algorithm_type_list,
#                             'algorithm_type': algorithm_type,
#                             'algorithm_trade_type': algorithm_trade_type,
#                             'algorithm_version': algorithm_version,
#                             'filename': filename,
#                             'algorithm_libary_id': algorithm_libary_id,
#                             'algorithm_path': str(res[0]),
#                             'upload_results': res
#                         }
#
#                         msg = '算法信息已保存并上传到服务器'
#                         result = {'code': 200, 'msg': msg, 'data': response_data}
#                         return jsonify(result)
#                     else:
#                         return jsonify({'code': 400, 'msg': '服务器连接异常，请检查算力设备并重新上传！'})
#                 else:
#                     return jsonify({'code': 400, 'msg': '没有找到.rknn文件'})
#         else:
#             return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'code': 400, 'msg': str(e)})
#

def handle_algorithm_upload_single_aicam(uploaded_file, algorithm_status, algorithm_ps):
    """
    处理算法子包上传逻辑（上传zip压缩包到server_type=1的算力设备）
    :param uploaded_file: 上传的文件
    :param algorithm_status: 算法运行状态 1运行 2停止
    :param algorithm_ps: 算法备注
    """

    def upload_to_multiple_servers(SSH_list, file_content, filename):
        """
        上传文件到多个服务器
        :param SSH_list: 包含多个 SSH 对象的列表
        :param file_content: 文件内容
        :param filename: 文件名
        :return: 所有服务器的上传路径或错误信息
        """
        upload_results = []

        for ssh_client in SSH_list:
            try:
                # 上传文件到服务器
                res = ssh_client.upload_send_file(file_content, filename)
                if res in ['无法上传文件', '上传中断，请稍后重试', '服务器连接异常']:
                    upload_results.append('无法上传文件')
                else:
                    upload_results.append(res)
            except Exception as e:
                upload_results.append('无法上传文件')

        return upload_results

    try:
        if str(algorithm_status) not in ('1', '2'):
            raise AlgorithmPackageError('算法启用状态必须是运行或停止')
        algorithm_status = str(algorithm_status)
        zip_content = read_uploaded_zip(uploaded_file)

        if uploaded_file and uploaded_file.filename.casefold().endswith('.zip'):
            # 查找 server_type=1 的算力设备
            computing_info = db.session.query(Computing_equipment).filter(
                Computing_equipment.server_type == 1
            ).all()

            if not computing_info:
                return jsonify({'code': 400, 'msg': '请先配置server_type=1的算力设备信息！'})

            # 创建多个 SSH 实例，表示要上传的服务器
            SSH_list = []  # Archive targets; not RKNN execution devices.

            # 读取压缩包内容
            with open_package_zip(zip_content) as zip_ref:
                package = inspect_algorithm_package(zip_ref)
                require_camera_package(package)
                zip_content = canonical_algorithm_zip(zip_ref, package)
                archive_name = package.filename[:-len(package.extension)] + '.zip'
                # Validated RKNN archive; storing it does not deploy it to a camera.
                files_to_check = [package.model_member]
                if files_to_check:
                    algorithm_filename_old = package.model_member
                    algorithm_filename = package.filename
                    file_extension = package.extension
                    labels = list(package.labels)
                    algorithm_type_list = [label['lable'] for label in labels]
                    algorithm_type = package.algorithm_type
                    mine = db.session.query(Mine).first()
                    if mine is None:
                        raise AlgorithmPackageError('请先配置单位信息，再上传算法')
                    filename = package.display_name(mine.mine_name)
                    words_in_filename = list(package.words)
                    analysis_type = words_in_filename[1]
                    algorithm_version = words_in_filename[9]
                    trade = package.trade
                    chip_type = package.chip
                    model_type_name = words_in_filename[2]
                    model_name = words_in_filename[3]
                    template_small_name = words_in_filename[4]
                    algorithm_trade_type = f"{trade}-{chip_type}"
                    alg_parent = words_in_filename[10]
                    alg_child = words_in_filename[11]
                    SSH_list = [SSH_Func(item.computing_ip, item.computing_user, item.computing_password)
                                for item in computing_info]

                    trade_type_id = db.session.query(Dict_data.data_id).filter(
                        func.lower(Dict_data.data_value) == trade).first()
                    if trade_type_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该厂商，需在厂商编码表中添加'})

                    model_type_name_id = db.session.query(Model_template_config_type_3588.id).filter(
                        Model_template_config_type_3588.model_type_name == model_type_name).first()
                    if model_type_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型大类，需在模型大类表中添加'})

                    model_name_id = db.session.query(Model_template_config_3588.id).filter(
                        Model_template_config_3588.model_name == model_name).first()
                    if model_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型模板，需在模型名称表中添加'})

                    model_small_name_id = db.session.query(Model_template_small_3588.id).filter(
                        Model_template_small_3588.template_small_name == template_small_name).first()
                    if model_small_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型小类，需在模型小类表中添加'})

                    # ✅ 保存zip文件到项目目录下的 algorithms 文件夹
                    import uuid
                    # 使用项目根目录（main.py 所在目录）
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    upload_dir = os.path.join(base_dir, 'algorithms')
                    os.makedirs(upload_dir, exist_ok=True)

                    import hashlib
                    unique_filename = f"{uuid.uuid4().hex}_{hashlib.sha256(zip_content).hexdigest()}.zip"  # Bind the archive to its digest.
                    local_file_path = os.path.join(upload_dir, unique_filename)

                    with open(local_file_path, 'wb') as f:
                        f.write(zip_content)

                    # 上传整个zip压缩包到多个服务器
                    res = upload_to_multiple_servers(SSH_list, zip_content, unique_filename)

                    if '无法上传文件' not in res and '上传中断，请稍后重试' not in res and '服务器连接异常' not in res:
                        # 数据库操作
                        config_data = Algorithm_library_3588(
                            algorithm_file_name=algorithm_filename,
                            algorithm_name=filename,
                            algorithm_type=algorithm_type,
                            algorithm_type_list=str(algorithm_type_list),
                            algorithm_status=algorithm_status,
                            algorithm_version=algorithm_version,
                            algorithm_path=str(res[0]),  # 远程服务器路径
                            algorithm_file_path=local_file_path,  # ✅ 本地路径（项目目录）
                            algorithm_trade_type=trade_type_id[0],
                            algorithm_ps=algorithm_ps,
                            model_type_name=model_type_name,
                            model_name=model_name,
                            template_small_name=template_small_name,
                            algorithm_parent=alg_parent if alg_parent else 1,
                            algorithm_child=alg_child if alg_child else 1,
                            analysis_type=analysis_type
                        )
                        db.session.add(config_data)
                        db.session.flush()

                        # 将算法检测列表写入检测类型表
                        for label in labels:
                            algorithm_test_type_res = Algorithm_test_type_3588(
                                test_type_ename=label['lable'],
                                test_type_cname=label['name'],
                                Algorithm_library_id=config_data.id
                            )
                            db.session.add(algorithm_test_type_res)

                        db.session.commit()
                        algorithm_libary_id = config_data.id

                        response_data = {
                            'algorithm_type_list': algorithm_type_list,
                            'algorithm_type': algorithm_type,
                            'algorithm_trade_type': algorithm_trade_type,
                            'algorithm_version': algorithm_version,
                            'filename': filename,
                            'algorithm_libary_id': algorithm_libary_id,
                            'algorithm_path': str(res[0]),
                            'algorithm_file_path': local_file_path,
                            'upload_results': res,
                            'deployment_status': 'not_deployed'
                        }

                        msg = 'RKNN 算法已收录至 AI摄像仪算法库并归档，尚未下发摄像仪；请选择目标摄像仪后执行下发'
                        result = {'code': 200, 'msg': msg, 'data': response_data}
                        return jsonify(result)
                    else:
                        # 上传失败时删除本地文件
                        if os.path.exists(local_file_path):
                            os.remove(local_file_path)
                        return jsonify({'code': 400, 'msg': '服务器连接异常，请检查算力设备并重新上传！'})
                else:
                    return jsonify({'code': 400, 'msg': '没有找到.rknn文件'})
        else:
            return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})
    except AlgorithmPackageError as error:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': str(error)})
    except (zipfile.BadZipFile, OSError, RuntimeError):
        db.session.rollback()
        return jsonify({'code': 400, 'msg': '无法读取或归档算法压缩包，请检查文件和服务器存储状态'})
    except Exception:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '摄像仪算法收录失败，请联系管理员检查服务日志'})

def deploy_algorithm_to_cameras(algorithm_libary_id, equipment_ids):
    """
    将算法下发到指定摄像头设备
    :param algorithm_libary_id: 算法库ID
    :param equipment_ids: 设备ID列表，用逗号分隔的字符串
    """

    def call_camera_api(camera_ip, file_content, algorithm_filename):
        """
        调用摄像头API上传算法
        :param camera_ip: 摄像头IP
        :param file_content: 文件内容（ZIP压缩包）
        :param algorithm_filename: 文件名
        :return: 响应结果
        """
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_upload_sub"
            files = {'files': (algorithm_filename, io.BytesIO(file_content), 'application/zip')}
            data = {
                'algorithm_status': '1',
            }
            response = requests.post(url, files=files, data=data, timeout=60)
            return response.json()
        except Exception as e:
            return {'code': 500, 'msg': f'请求失败: {str(e)}'}
    # 解析设备ID列表
    if not equipment_ids:
        return jsonify({'code': 400, 'msg': '请提供设备ID列表'})
    try:
        if isinstance(equipment_ids, list):
            # 已经是列表格式 [1, 2, 3]
            equipment_id_list = [int(eid) for eid in equipment_ids if eid]
        elif isinstance(equipment_ids, str):
            # 字符串格式 "1,2,3"
            equipment_id_list = [int(eid.strip()) for eid in equipment_ids.split(',') if eid.strip()]
        else:
            # 单个数字
            equipment_id_list = [int(equipment_ids)]
    except ValueError:
        return jsonify({'code': 400, 'msg': '设备ID格式不正确'})

    if not equipment_id_list:
        return jsonify({'code': 400, 'msg': '设备ID列表为空'})

    # 获取算法信息
    algorithm = db.session.query(Algorithm_library_3588).filter(
        Algorithm_library_3588.id == algorithm_libary_id
    ).first()

    if not algorithm:
        return jsonify({'code': 400, 'msg': '未找到指定的算法'})

    # 获取算法文件路径
    file_path = getattr(algorithm, 'algorithm_file_path', None)
    if not file_path or not os.path.exists(file_path):
        try:
            archive_servers = db.session.query(Computing_equipment).filter(
                Computing_equipment.server_type == 1).all()
            archive_directory = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'algorithms')
            file_path = recover_camera_algorithm_archive(
                algorithm, archive_servers, SSH_Func, archive_directory)
        except AlgorithmArchiveRecoveryError as error:
            return jsonify({'code': 400, 'msg': str(error)})
        except Exception:
            return jsonify({'code': 500, 'msg': '无法恢复算法归档，请检查服务器存储和配置'})

    # 读取压缩包内容
    with open(file_path, 'rb') as f:
        zip_content = f.read()

    # 获取设备信息
    equipment_list = db.session.query(Equipment).filter(
        Equipment.id.in_(equipment_id_list)
    ).all()

    if not equipment_list:
        return jsonify({'code': 400, 'msg': '未找到指定的设备'})

    try:
        # 并行调用各个摄像头的API
        success_devices = []
        failed_devices = []

        def upload_to_device(equipment):
            """上传算法到单个设备"""
            try:
                camera_ip = equipment.equipment_ip
                if not camera_ip:
                    return {
                        'equipment_id': equipment.id,
                        'equipment_name': equipment.equipment_name,
                        'success': False,
                        'msg': '设备IP为空'
                    }

                # 从本地文件路径中提取原始的ZIP文件名
                original_zip_filename = os.path.basename(algorithm.algorithm_file_path)
                # 去除UUID前缀，获取原始上传的ZIP文件名（格式：uuid_原始文件名.zip）
                if '_' in original_zip_filename:
                    original_zip_filename = original_zip_filename.split('_', 1)[1]
                result = call_camera_api(camera_ip, zip_content, original_zip_filename)

                if result.get('code') == 200:
                    algorithm_camera_id = None
                    if result.get('data') and isinstance(result['data'], dict):
                        algorithm_camera_id = result['data'].get('algorithm_id')

                    return {
                        'equipment_id': equipment.id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'success': True,
                        'msg': '上传成功',
                        'algorithm_camera_id': algorithm_camera_id
                    }
                else:
                    return {
                        'equipment_id': equipment.id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'success': False,
                        'msg': result.get('msg', '未知错误')
                    }
            except Exception as e:
                return {
                    'equipment_id': equipment.id,
                    'equipment_name': equipment.equipment_name,
                    'success': False,
                    'msg': str(e)
                }

        # 使用线程池并行调用
        with ThreadPoolExecutor(max_workers=min(10, len(equipment_list))) as executor:
            future_to_equipment = {
                executor.submit(upload_to_device, eq): eq
                for eq in equipment_list
            }

            for future in as_completed(future_to_equipment):
                result = future.result()
                if result['success']:
                    success_devices.append(result)
                else:
                    failed_devices.append(result)

        # 记录成功的设备到关联表
        for device in success_devices:
            try:
                # 根据设备IP查找对应的算力资源ID
                camera_ip = device.get('camera_ip')
                computing_resource_id = None

                if camera_ip:
                    computing_equipment = db.session.query(Computing_equipment).filter(
                        Computing_equipment.computing_ip == camera_ip
                    ).first()

                    if computing_equipment:
                        computing_resource_id = computing_equipment.id

                relation = AlgorithmLibrary2Camera(
                    equipment_id=device['equipment_id'],
                    computing_resource_id=computing_resource_id,
                    algorithm_libary_id=algorithm_libary_id,
                    algorithm_camera_id=device.get('algorithm_camera_id')
                )
                db.session.add(relation)
            except Exception as e:
                print(f"记录设备关联失败: {e}")

        db.session.commit()

        response_data = {
            'algorithm_libary_id': algorithm_libary_id,
            'success_count': len(success_devices),
            'failed_count': len(failed_devices),
            'success_devices': success_devices,
            'failed_devices': failed_devices
        }

        msg = f'算法下发完成，成功{len(success_devices)}个设备，失败{len(failed_devices)}个设备'

        result = {'code': 200, 'msg': msg, 'data': response_data}
        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': str(e)})

# def algorithm_data_service_aicam(params):
#     try:
#         page = int(params.get('page', 1))
#         per_page = int(params.get('per_page', 15))
#         algorithm_file_name = params.get('algorithm_file_name')
#         algorithm_name = params.get('algorithm_name')
#         algorithm_status = params.get('algorithm_status')
#         algorithm_trade_type = params.get('algorithm_trade_type')
#
#         filters = []
#         if algorithm_file_name:
#             filters.append(Algorithm_library_3588.algorithm_file_name.ilike(f"%{algorithm_file_name}%"))
#         if algorithm_name:
#             filters.append(Algorithm_library_3588.algorithm_name.ilike(f"%{algorithm_name}%"))
#         if algorithm_status:
#             filters.append(Algorithm_library_3588.algorithm_status == int(algorithm_status))
#         if algorithm_trade_type:
#             filters.append(Algorithm_library_3588.algorithm_trade_type == int(algorithm_trade_type))
#
#         if len(filters) >= 2:
#             query_filter = and_(*filters)
#         else:
#             query_filter = filters[0] if filters else None
#
#         # 构建基础查询，关联 AlgorithmLibrary2Camera、Algorithm_library_3588、Equipment 表
#         base_query = db.session.query(
#             Algorithm_library_3588.id.label('algorithm_libary_id'),
#             Algorithm_library_3588.algorithm_file_name,
#             Algorithm_library_3588.algorithm_name,
#             Algorithm_library_3588.algorithm_type,
#             Algorithm_library_3588.algorithm_type_list,
#             Algorithm_library_3588.algorithm_version,
#             Algorithm_library_3588.algorithm_status,
#             Algorithm_library_3588.algorithm_trade_type,
#             Algorithm_library_3588.algorithm_ps,
#             Algorithm_library_3588.model_type_name,
#             Algorithm_library_3588.model_name,
#             Algorithm_library_3588.template_small_name,
#             Algorithm_library_3588.analysis_type,
#             Algorithm_library_3588.create_time,
#             AlgorithmLibrary2Camera.equipment_id,
#             Equipment.equipment_name,
#             Equipment.equipment_ip,
#             Equipment.equipment_type,
#             Computing_equipment.computing_name,
#             Computing_equipment.computing_ip
#         ).outerjoin(
#             AlgorithmLibrary2Camera,
#             Algorithm_library_3588.id == AlgorithmLibrary2Camera.algorithm_libary_id
#         ).outerjoin(
#             Equipment,
#             AlgorithmLibrary2Camera.equipment_id == Equipment.id
#         ).outerjoin(
#             Computing_equipment,
#             AlgorithmLibrary2Camera.computing_resource_id == Computing_equipment.id
#         ).order_by(Algorithm_library_3588.create_time.desc())
#
#         if query_filter is not None:
#             base_query = base_query.filter(query_filter)
#
#         # 分页查询
#         pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
#
#         # 组装数据
#         algorithm_info = []
#         for item in pagination.items:
#
#             algorithm_info.append({
#                 'id': item.algorithm_libary_id,
#                 'algorithm_file_name': item.algorithm_file_name,
#                 'algorithm_name': extract_chinese(item.algorithm_name),
#                 'algorithm_type': configs.algorithm_type[int(item.algorithm_type) - 1][
#                     'value'] if item.algorithm_type else '',
#                 'algorithm_version': item.algorithm_version,
#                 'algorithm_status': configs.status[int(item.algorithm_status) - 1][
#                     'value'] if item.algorithm_status else '',
#                 'algorithm_trade_type': item.algorithm_trade_type,
#                 'algorithm_ps': item.algorithm_ps,
#                 'create_time': item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else '',
#                 'equipment_id': item.equipment_id,
#                 'equipment_name': item.equipment_name,
#                 'equipment_ip': item.equipment_ip,
#                 'equipment_type': item.equipment_type,
#                 'computing_name': item.computing_name,
#                 'computing_ip': item.computing_ip,
#             })
#
#         response_data = {
#             'total_items': pagination.total,
#             'total_pages': pagination.pages,
#             'current_page': pagination.page,
#             'per_page': per_page,
#             'data': algorithm_info,
#         }
#         return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
#     except Exception as e:
#         return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_data_service_aicam(params):
    try:
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        algorithm_file_name = params.get('algorithm_file_name')
        algorithm_name = params.get('algorithm_name')
        algorithm_status = params.get('algorithm_status')
        algorithm_trade_type = params.get('algorithm_trade_type')

        filters = []
        if algorithm_file_name:
            filters.append(Algorithm_library_3588.algorithm_file_name.ilike(f"%{algorithm_file_name}%"))
        if algorithm_name:
            filters.append(Algorithm_library_3588.algorithm_name.ilike(f"%{algorithm_name}%"))
        if algorithm_status:
            filters.append(Algorithm_library_3588.algorithm_status == int(algorithm_status))
        if algorithm_trade_type:
            filters.append(Algorithm_library_3588.algorithm_trade_type == int(algorithm_trade_type))

        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else None

        # ✅ 优化：直接从算法库表查询，不依赖关联表
        base_query = db.session.query(
            Algorithm_library_3588.id.label('algorithm_libary_id')
        )

        if query_filter is not None:
            base_query = base_query.filter(query_filter)

        base_query = base_query.order_by(Algorithm_library_3588.create_time.desc())
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)

        # 获取所有算法ID
        algorithm_ids = [item.algorithm_libary_id for item in pagination.items]

        if not algorithm_ids:
            return {'code': 200, 'msg': '查询成功', 'data_list': {
                'total_items': 0,
                'total_pages': 0,
                'current_page': page,
                'per_page': per_page,
                'data': []
            }}

        # ✅ 一次性查询所有相关的检测类型
        test_types_query = db.session.query(
            Algorithm_test_type_3588.Algorithm_library_id,
            Algorithm_test_type_3588.test_type_ename,
            Algorithm_test_type_3588.test_type_cname
        ).filter(
            Algorithm_test_type_3588.Algorithm_library_id.in_(algorithm_ids)
        ).all()

        # 构建算法ID到检测类型的映射
        test_types_map = {}
        for tt in test_types_query:
            if tt.Algorithm_library_id not in test_types_map:
                test_types_map[tt.Algorithm_library_id] = []
            test_types_map[tt.Algorithm_library_id].append({
                'test_type_ename': tt.test_type_ename,
                'test_type_cname': tt.test_type_cname
            })

        # ✅ 一次性查询所有主数据，使用 outerjoin 确保即使没有关联数据也能查到算法
        main_query = db.session.query(
            Algorithm_library_3588.id.label('algorithm_libary_id'),
            Algorithm_library_3588.algorithm_file_name,
            Algorithm_library_3588.algorithm_name,
            Algorithm_library_3588.algorithm_type,
            Algorithm_library_3588.algorithm_type_list,
            Algorithm_library_3588.algorithm_version,
            Algorithm_library_3588.algorithm_status,
            Algorithm_library_3588.algorithm_trade_type,
            Algorithm_library_3588.algorithm_ps,
            Algorithm_library_3588.model_type_name,
            Algorithm_library_3588.model_name,
            Algorithm_library_3588.template_small_name,
            Algorithm_library_3588.analysis_type,
            Algorithm_library_3588.create_time,
            Algorithm_library_3588.algorithm_path,
            AlgorithmLibrary2Camera.equipment_id,
            Equipment.equipment_name,
            Equipment.equipment_ip,
            Equipment.equipment_type,
            Computing_equipment.computing_name,
            Computing_equipment.computing_ip
        ).outerjoin(
            AlgorithmLibrary2Camera,
            Algorithm_library_3588.id == AlgorithmLibrary2Camera.algorithm_libary_id
        ).outerjoin(
            Equipment,
            AlgorithmLibrary2Camera.equipment_id == Equipment.id
        ).outerjoin(
            Computing_equipment,
            AlgorithmLibrary2Camera.computing_resource_id == Computing_equipment.id
        ).filter(
            Algorithm_library_3588.id.in_(algorithm_ids)
        ).order_by(Algorithm_library_3588.create_time.desc()).all()

        # ✅ 按算法ID分组，一个算法可能关联多个设备
        algorithm_dict = {}
        for item in main_query:
            alg_id = item.algorithm_libary_id
            if alg_id not in algorithm_dict:
                algorithm_dict[alg_id] = {
                    'id': item.algorithm_libary_id,
                    'algorithm_file_name': item.algorithm_file_name,
                    'algorithm_name': extract_chinese(item.algorithm_name),
                    'algorithm_type': configs.algorithm_type[int(item.algorithm_type) - 1][
                        'value'] if item.algorithm_type else '',
                    'algorithm_type_list': item.algorithm_type_list,
                    'algorithm_version': item.algorithm_version,
                    'algorithm_status': configs.status[int(item.algorithm_status) - 1][
                        'value'] if item.algorithm_status else '',
                    'algorithm_trade_type': item.algorithm_trade_type,
                    'algorithm_ps': item.algorithm_ps,
                    'model_type_name': item.model_type_name,
                    'model_name': item.model_name,
                    'template_small_name': item.template_small_name,
                    'analysis_type': item.analysis_type,
                    'create_time': item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else '',
                    'algorithm_path': item.algorithm_path,
                    'test_types': test_types_map.get(item.algorithm_libary_id, []),
                    'deployed_devices': []  # 已下发的设备列表
                }

            # 如果有设备信息，添加到设备列表
            if item.equipment_id:
                algorithm_dict[alg_id]['deployed_devices'].append({
                    'equipment_id': item.equipment_id,
                    'equipment_name': item.equipment_name,
                    'equipment_ip': item.equipment_ip,
                    'equipment_type': item.equipment_type,
                    'computing_name': item.computing_name,
                    'computing_ip': item.computing_ip
                })

        # 转换为列表
        algorithm_info = list(algorithm_dict.values())

        response_data = {
            'total_items': pagination.total,
            'total_pages': pagination.pages,
            'current_page': pagination.page,
            'per_page': per_page,
            'data': algorithm_info,
        }
        return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_library_delete_service_aicam(payload):
    try:
        equipment_id = payload.get('equipment_id', None)
        algorithm_libary_id = payload.get('algorithm_libary_id', None)

        # 参数校验
        if not equipment_id or not algorithm_libary_id:
            return {'code': 400, 'msg': '缺少设备ID或算法ID参数'}

        # 根据设备ID和算法ID查找关联记录
        relation = db.session.query(AlgorithmLibrary2Camera).filter(
            and_(
                AlgorithmLibrary2Camera.equipment_id == equipment_id,
                AlgorithmLibrary2Camera.algorithm_libary_id == algorithm_libary_id
            )
        ).first()

        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录'}

        # 获取algorithm_camera_id（摄像头返回的算法ID）
        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

        # 根据设备ID查找设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}

        # 调用摄像头API删除算法，使用algorithm_camera_id作为参数
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_library_delete"
            data = {'id': algorithm_camera_id}
            response = requests.post(url, json=data, timeout=30)
            result = response.json()

            if result.get('code') == 200:
                # 删除成功，删除关联表中的记录
                db.session.delete(relation)
                db.session.commit()

                return {
                    'code': 200,
                    'msg': '删除成功',
                    'data': {
                        'equipment_id': equipment_id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': algorithm_libary_id,
                        'algorithm_camera_id': algorithm_camera_id
                    }
                }
            else:
                # 摄像头返回失败
                return {
                    'code': 400,
                    'msg': f'删除失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'equipment_id': equipment_id,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': algorithm_libary_id,
                        'algorithm_camera_id': algorithm_camera_id
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'equipment_id': equipment_id,
                    'camera_ip': camera_ip,
                    'algorithm_libary_id': algorithm_libary_id,
                    'algorithm_camera_id': algorithm_camera_id
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'equipment_id': equipment_id,
                    'camera_ip': camera_ip,
                    'algorithm_libary_id': algorithm_libary_id,
                    'algorithm_camera_id': algorithm_camera_id
                }
            }

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_library_delete_service_aicam(payload):
    """
    删除算法：支持单设备删除和批量删除
    :param payload:
        - 单设备删除: {'equipment_id': 设备ID, 'algorithm_libary_id': 算法ID}
        - 批量删除: {'algorithm_libary_id': 算法ID}
    """
    try:
        equipment_id = payload.get('equipment_id', None)
        algorithm_libary_id = payload.get('id', None)

        # 参数校验
        if not algorithm_libary_id:
            return {'code': 400, 'msg': '缺少算法ID参数'}

        # ✅ 判断是单设备删除还是批量删除
        if equipment_id:
            # ========== 单设备删除模式 ==========
            return _delete_single_device_algorithm(equipment_id, algorithm_libary_id)
        else:
            # ========== 批量删除模式 ==========
            return _delete_batch_algorithm(algorithm_libary_id)

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def _delete_single_device_algorithm(equipment_id, algorithm_libary_id):
    """
    单个设备删除算法
    """
    try:
        # 根据设备ID和算法ID查找关联记录
        relation = db.session.query(AlgorithmLibrary2Camera).filter(
            and_(
                AlgorithmLibrary2Camera.equipment_id == equipment_id,
                AlgorithmLibrary2Camera.algorithm_libary_id == algorithm_libary_id
            )
        ).first()

        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录'}

        # 获取algorithm_camera_id（摄像头返回的算法ID）
        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

        # 根据设备ID查找设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}

        # 调用摄像头API删除算法
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_library_delete"
            data = {'id': [algorithm_camera_id]}
            response = requests.post(url, json=data, timeout=30)
            print(response,'333333333333333333333')
            result = response.json()

            if result.get('code') == 200:
                # 删除成功，删除关联表中的记录
                db.session.delete(relation)
                db.session.commit()

                return {
                    'code': 200,
                    'msg': '删除成功',
                    'data': {
                        'equipment_id': equipment_id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': algorithm_libary_id,
                        'algorithm_camera_id': algorithm_camera_id
                    }
                }
            else:
                # 摄像头返回失败
                return {
                    'code': 400,
                    'msg': f'删除失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'equipment_id': equipment_id,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': algorithm_libary_id,
                        'algorithm_camera_id': algorithm_camera_id
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'equipment_id': equipment_id,
                    'camera_ip': camera_ip,
                    'algorithm_libary_id': algorithm_libary_id,
                    'algorithm_camera_id': algorithm_camera_id
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'equipment_id': equipment_id,
                    'camera_ip': camera_ip,
                    'algorithm_libary_id': algorithm_libary_id,
                    'algorithm_camera_id': algorithm_camera_id
                }
            }

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def _parse_algorithm_ids(algorithm_libary_id):
    """
    解析算法ID，支持多种格式
    :param algorithm_libary_id: 可以是 int, str, list
    :return: 算法ID列表
    """
    if isinstance(algorithm_libary_id, list):
        # 已经是列表格式 [1, 2, 3]
        return [int(id) for id in algorithm_libary_id if id]
    elif isinstance(algorithm_libary_id, str):
        # 字符串格式 "1,2,3" 或 "1"
        if ',' in algorithm_libary_id:
            return [int(id.strip()) for id in algorithm_libary_id.split(',') if id.strip()]
        else:
            return [int(algorithm_libary_id)]
    else:
        # 单个数字
        return [int(algorithm_libary_id)]


def _delete_batch_algorithm(algorithm_libary_id):
    """
    批量删除算法：删除所有关联该算法的摄像头上的算法，并删除数据库记录
    :param algorithm_libary_id: 可以是单个ID、ID列表或逗号分隔的字符串
    """
    try:
        # ✅ 解析算法ID列表
        algorithm_ids = _parse_algorithm_ids(algorithm_libary_id)

        if not algorithm_ids:
            return {'code': 400, 'msg': '算法ID列表为空'}

        # 查找所有关联这些算法的记录
        relations = db.session.query(AlgorithmLibrary2Camera).filter(
            AlgorithmLibrary2Camera.algorithm_libary_id.in_(algorithm_ids)
        ).all()


        if not relations:
            print('[算法删除] 未找到这些算法的关联记录，跳过设备删除，直接删除算法库和本地文件')
            # 获取所有涉及的算法信息
            algorithms = db.session.query(Algorithm_library_3588).filter(
                Algorithm_library_3588.id.in_(algorithm_ids)
            ).all()
            algorithm_dict = {alg.id: alg for alg in algorithms}
            # 删除算法库表中的记录
            deleted_algorithms = []
            for alg_id in algorithm_ids:
                if alg_id in algorithm_dict:
                    algorithm = algorithm_dict[alg_id]
                    try:
                        db.session.delete(algorithm)
                        deleted_algorithms.append({
                            'algorithm_id': alg_id,
                            'algorithm_name': algorithm.algorithm_name
                        })
                        print(f"[算法删除] 已标记删除算法库记录: id={alg_id}, name={algorithm.algorithm_name}")
                    except Exception as e:
                        print(f"[算法删除] 删除算法库记录失败: id={alg_id}, error={str(e)}")
            # 删除本地算法文件
            deleted_files = []
            for alg_id in algorithm_ids:
                if alg_id in algorithm_dict:
                    algorithm = algorithm_dict[alg_id]
                    if algorithm.algorithm_file_path and os.path.exists(algorithm.algorithm_file_path):
                        try:
                            os.remove(algorithm.algorithm_file_path)
                            deleted_files.append({
                                'algorithm_id': alg_id,
                                'file_path': algorithm.algorithm_file_path
                            })
                            print(f"[算法删除] 已删除本地文件: {algorithm.algorithm_file_path}")
                        except Exception as e:
                            print(f"[算法删除] 删除本地文件失败: {e}")
            db.session.commit()
            msg = f'算法删除完成，无设备关联，已删除算法库和本地文件，共{len(algorithm_ids)}个算法'
            response_data = {
                'algorithm_ids': algorithm_ids,
                'total_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'success_devices': [],
                'failed_devices': [],
                'deleted_files': deleted_files,
                'deleted_algorithms': deleted_algorithms,
            }
            return {'code': 200, 'msg': msg, 'data': response_data}

        # 获取所有涉及的算法信息
        algorithms = db.session.query(Algorithm_library_3588).filter(
            Algorithm_library_3588.id.in_(algorithm_ids)
        ).all()

        algorithm_dict = {alg.id: alg for alg in algorithms}

        # ✅ 预先查询所有设备信息（避免在线程中访问数据库）
        equipment_ids = [rel.equipment_id for rel in relations]
        equipments = db.session.query(Equipment).filter(
            Equipment.id.in_(equipment_ids)
        ).all()

        equipment_map = {eq.id: eq for eq in equipments}

        # 按算法ID分组统计
        total_relations = len(relations)

        # 并行调用各个摄像头的删除API
        success_devices = []
        failed_devices = []

        def delete_from_device(relation, equipment_map):
            """从单个设备删除算法"""
            try:
                equipment_id = relation.equipment_id
                algorithm_camera_id = relation.algorithm_camera_id
                alg_id = relation.algorithm_libary_id

                if not algorithm_camera_id:
                    return {
                        'equipment_id': equipment_id,
                        'algorithm_libary_id': alg_id,
                        'success': False,
                        'msg': '关联记录中未保存摄像头算法ID'
                    }

                # ✅ 从预查询的字典中获取设备信息（不需要访问数据库）
                equipment = equipment_map.get(equipment_id)

                if not equipment:
                    return {
                        'equipment_id': equipment_id,
                        'algorithm_libary_id': alg_id,
                        'success': False,
                        'msg': '未找到指定的设备'
                    }

                camera_ip = equipment.equipment_ip
                if not camera_ip:
                    return {
                        'equipment_id': equipment_id,
                        'equipment_name': equipment.equipment_name,
                        'algorithm_libary_id': alg_id,
                        'success': False,
                        'msg': '设备IP为空'
                    }

                # 调用摄像头API删除算法
                try:
                    url = f"http://{camera_ip}:5000/model_view/algorithm_library_delete"
                    data = {'id': [algorithm_camera_id]}

                    print(f"[算法删除] 开始调用摄像头接口: IP={camera_ip}, algorithm_camera_id={algorithm_camera_id}")

                    response = requests.post(url, json=data, timeout=30)
                    result = response.json()

                    print(f"[算法删除] 摄像头响应: code={result.get('code')}, msg={result.get('msg')}")

                    if result.get('code') == 200:
                        print(
                            f"[算法删除] 成功: equipment_id={equipment_id}, algorithm_camera_id={algorithm_camera_id}")
                        return {
                            'equipment_id': equipment_id,
                            'equipment_name': equipment.equipment_name,
                            'camera_ip': camera_ip,
                            'algorithm_libary_id': alg_id,
                            'algorithm_camera_id': algorithm_camera_id,
                            'success': True,
                            'msg': '删除成功'
                        }
                    else:
                        print(f"[算法删除] 失败: equipment_id={equipment_id}, msg={result.get('msg')}")
                        return {
                            'equipment_id': equipment_id,
                            'equipment_name': equipment.equipment_name,
                            'camera_ip': camera_ip,
                            'algorithm_libary_id': alg_id,
                            'algorithm_camera_id': algorithm_camera_id,
                            'success': False,
                            'msg': result.get('msg', '未知错误')
                        }
                except requests.exceptions.RequestException as e:
                    print(f"[算法删除] 请求异常: equipment_id={equipment_id}, error={str(e)}")
                    return {
                        'equipment_id': equipment_id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': alg_id,
                        'success': False,
                        'msg': f'请求失败: {str(e)}'
                    }
                except Exception as e:
                    print(f"[算法删除] 调用异常: equipment_id={equipment_id}, error={str(e)}")
                    return {
                        'equipment_id': equipment_id,
                        'equipment_name': equipment.equipment_name,
                        'camera_ip': camera_ip,
                        'algorithm_libary_id': alg_id,
                        'success': False,
                        'msg': f'调用异常: {str(e)}'
                    }

            except Exception as e:
                return {
                    'equipment_id': relation.equipment_id,
                    'algorithm_libary_id': relation.algorithm_libary_id,
                    'success': False,
                    'msg': str(e)
                }

        # 使用线程池并行调用
        with ThreadPoolExecutor(max_workers=min(10, len(relations))) as executor:
            future_to_relation = {
                executor.submit(delete_from_device, rel, equipment_map): rel
                for rel in relations
            }

            for future in as_completed(future_to_relation):
                result = future.result()
                if result['success']:
                    success_devices.append(result)
                else:
                    failed_devices.append(result)
                    print(f"[算法删除] 设备删除失败: equipment_id={result.get('equipment_id')}, "
                          f"msg={result.get('msg')}, camera_ip={result.get('camera_ip')}")

        # 统计失败数量
        if failed_devices:
            print(f"[算法删除] 警告: {len(failed_devices)}个设备删除失败，将跳过关联记录和本地文件的删除")

            # 如果有设备删除失败，回滚并返回错误
            db.session.rollback()

            return {
                'code': 400,
                'msg': f'部分设备删除失败，共{len(failed_devices)}个失败',
                'data': {
                    'success_count': len(success_devices),
                    'failed_count': len(failed_devices),
                    'failed_devices': failed_devices
                }
            }

        # ✅ 所有设备都成功后，才删除数据库关联记录
        print(f"[算法删除] 所有设备删除成功，开始清理数据库关联记录")
        for relation in relations:
            try:
                db.session.delete(relation)
            except Exception as e:
                print(f"[算法删除] 删除关联记录失败: {e}")
        # ✅ 删除算法库表中的记录
        print(f"[算法删除] 开始删除算法库记录: algorithm_ids={algorithm_ids}")
        deleted_algorithms = []
        for alg_id in algorithm_ids:
            if alg_id in algorithm_dict:
                algorithm = algorithm_dict[alg_id]
                try:
                    db.session.delete(algorithm)
                    deleted_algorithms.append({
                        'algorithm_id': alg_id,
                        'algorithm_name': algorithm.algorithm_name
                    })
                    print(f"[算法删除] 已标记删除算法库记录: id={alg_id}, name={algorithm.algorithm_name}")
                except Exception as e:
                    print(f"[算法删除] 删除算法库记录失败: id={alg_id}, error={str(e)}")

        # ✅ 删除本地算法文件
        deleted_files = []
        for alg_id in algorithm_ids:
            if alg_id in algorithm_dict:
                algorithm = algorithm_dict[alg_id]
                if algorithm.algorithm_file_path and os.path.exists(algorithm.algorithm_file_path):
                    try:
                        os.remove(algorithm.algorithm_file_path)
                        deleted_files.append({
                            'algorithm_id': alg_id,
                            'file_path': algorithm.algorithm_file_path
                        })
                        print(f"[算法删除] 已删除本地文件: {algorithm.algorithm_file_path}")
                    except Exception as e:
                        print(f"[算法删除] 删除本地文件失败: {e}")

        db.session.commit()
        print(f"[算法删除] 完成: 成功{len(success_devices)}个，失败{len(failed_devices)}个")

        response_data = {
            'algorithm_ids': algorithm_ids,
            'total_count': total_relations,
            'success_count': len(success_devices),
            'failed_count': len(failed_devices),
            'success_devices': success_devices,
            'failed_devices': failed_devices,
            'deleted_files': deleted_files,
            'deleted_algorithms': deleted_algorithms,
        }

        msg = f'算法删除完成，共{len(algorithm_ids)}个算法，{total_relations}个设备关联，成功{len(success_devices)}个，失败{len(failed_devices)}个'

        return {'code': 200, 'msg': msg, 'data': response_data}

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def add_algorithm_config_aicam(payload):
    try:
        conf_name = payload.get('conf_name')
        Algorithm_library_id = payload.get('Algorithm_library_id')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id')
        conf_area = payload.get('conf_area')
        status = payload.get('status')
        test_type_id = payload.get('test_type_id')
        shield_status = payload.get('shield_status')
        tem_conf_area = payload.get('tem_conf_area')
        tem_frames = payload.get('tem_frames')
        confidence = payload.get('confidence')
        draw_type = payload.get('draw_type')
        interval_time = payload.get('interval_time', 0)
        img_resolution = payload.get('img_resolution')
        duration_time = payload.get('duration_time', 0)
        image_draw_type = payload.get('image_draw_type', 1)
        Algorithm_config_ps = payload.get('Algorithm_config_ps')
        scene_typename = payload.get('scene_typename')
        sensitivity = payload.get('sensitivity')
        resource_id = payload.get('resource_id')
        defense_time_start = payload.get('defense_time_start')
        defense_time_end = payload.get('defense_time_end')
        model_template_config_id = payload.get('model_template_config_id')
        template_list_area = payload.get('template_list_area')
        image_count = payload.get('image_count')
        template_small_id = payload.get('template_small_id')
        count_time = payload.get('count_time', 0)
        res_type = payload.get('res_type')
        computing_id = payload.get('computing_id')
        template_data = payload.get('template_data')
        label_list = payload.get('label_list')
        model_template_type_id = payload.get('model_template_type_id')
        amp = payload.get('amp', 10)
        alg_select_type = payload.get('alg_select_type', 3)
        model_two_type = payload.get('model_two_type')
        model_two_data = payload.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = payload.get('priority')
        run_time = payload.get('run_time')
        uwb_distance=payload.get('uwb_distance')
        cross_line_area = payload.get('cross_line_area')
        Entering_num = payload.get('Entering_num')
        Exiting_num = payload.get('Exiting_num')
        all_Entering_num = payload.get('all_Entering_num')
        all_Exiting_num = payload.get('all_Exiting_num')
        base_params = [conf_name, Algorithm_library_id, Mine_id, Equipment_id, test_type_id,
                       model_template_config_id, model_template_type_id]
        if not all(base_params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        if get_algorithm_config_by_name_aicam(conf_name,Equipment_id):
            return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}

        if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
            return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}

        if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
            return {'code': 400, 'msg': '算法库id不存在'}

        _ = get_mine_by_id(Mine_id)

        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == Equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}

        if not computing_id:
            computing_equipment = db.session.query(Computing_equipment).filter(
                Computing_equipment.computing_ip == camera_ip
            ).first()

            if computing_equipment:
                computing_id = computing_equipment.id

        # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
        if equipment.parent_id is None:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()
        else:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()

        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录，请先下发算法到该设备'}

        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}
        if not equipment.code:
            cam_equipment_id = 1
        else:
            cam_equipment_id = int(str(equipment.code)[0])

        # 根据检测类型ID查询检测类型中文名称
        test_type = db.session.query(Algorithm_test_type_3588).filter(
            Algorithm_test_type_3588.id == test_type_id
        ).first()

        if not test_type:
            return {'code': 400, 'msg': '未找到指定的检测类型'}

        test_type_cname = test_type.test_type_cname

        # 调用摄像头接口添加算法配置
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_add"
            # 构建请求参数（与数据库字段一致）
            webhook_trigger = 0
            camera_payload = {
                'conf_name': conf_name,
                'Algorithm_library_id': algorithm_camera_id,
                'Mine_id': Mine_id,
                'Equipment_id': cam_equipment_id,
                'conf_area': conf_area if conf_area else [],
                'status': status if status else '1',
                # 'test_type_cname': test_type_cname,
                'shield_status': shield_status,
                'tem_conf_area': tem_conf_area if tem_conf_area else [],
                'tem_frames': tem_frames,
                'confidence': confidence,
                'draw_type': draw_type,
                'interval_time': interval_time,
                'img_resolution': img_resolution,
                'duration_time': duration_time,
                'image_draw_type': image_draw_type,
                'Algorithm_config_ps': Algorithm_config_ps,
                'scene_typename': scene_typename,
                'sensitivity': sensitivity,
                'resource_id': resource_id,
                'defense_time_start': defense_time_start,
                'defense_time_end': defense_time_end,
                'model_template_config_id': model_template_config_id,
                'template_list_area': template_list_area if template_list_area else [],
                'image_count': image_count,
                'template_small_id': template_small_id,
                'count_time': count_time,
                'res_type': res_type,
                # 'computing_id': computing_id,
                'template_data': template_data if template_data else '',
                'label_list': label_list if label_list else [],
                'model_template_type_id': model_template_type_id,
                'amp': amp,
                'alg_select_type': alg_select_type,
                'model_two_type': model_two_type,
                'model_two_data': model_two_data,
                'priority': priority,
                'run_time': run_time,
                'uwb_distance':uwb_distance,
                'cross_line_area':cross_line_area ,
                'Entering_num': Entering_num,
                'Exiting_num': Exiting_num,
                'all_Entering_num':all_Entering_num,
                'all_Exiting_num' : all_Exiting_num,
                'webhook_trigger': int(webhook_trigger),

            }

            response = requests.post(url, json=camera_payload, timeout=30)
            result = response.json()

            camera_config_id = result.get('algorithm_id')

            # 只有摄像头接口返回200才继续写入本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'camera_ip': camera_ip,
                        'equipment_id': Equipment_id,
                        'conf_name': conf_name
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }

        # 摄像头接口调用成功后，才写入本地数据库
        fields = {
            'conf_name': conf_name,
            'Algorithm_library_id': Algorithm_library_id,
            'Mine_id': Mine_id,
            'Equipment_id': Equipment_id,
            'conf_area': str(conf_area) if conf_area else str([]),
            'status': status if status else '1',
            'test_type_id': test_type_id,
            'shield_status': shield_status,
            'tem_conf_area': tem_conf_area,
            'tem_frames': tem_frames,
            'confidence': confidence,
            'draw_type': draw_type,
            'interval_time': interval_time,
            'img_resolution': img_resolution,
            'duration_time': duration_time,
            'image_draw_type': image_draw_type,
            'Algorithm_config_ps': Algorithm_config_ps,
            'scene_typename': scene_typename,
            'sensitivity': sensitivity,
            'resource_id': resource_id,
            'defense_time_start': defense_time_start,
            'defense_time_end': defense_time_end,
            'model_template_config_id': model_template_config_id,
            'template_list_area': template_list_area,
            'image_count': image_count,
            'template_small_id': template_small_id,
            'count_time': count_time,
            'res_type': res_type,
            'computing_id': computing_id,
            'template_data': template_data,
            'label_list': label_list,
            'model_template_type_id': model_template_type_id,
            'amp': amp,
            'alg_select_type': alg_select_type,
            'model_two_type': model_two_type,
            'model_two_data': model_two_data,
            'priority': priority,
            'run_time': run_time,
            'camera_config_id':camera_config_id,
            'uwb_distance':uwb_distance,
            'cross_line_area':cross_line_area,
            'Entering_num' : Entering_num,
            'Exiting_num': Exiting_num,
            'all_Entering_num': all_Entering_num,
            'all_Exiting_num': all_Exiting_num,
        }
        config_obj = insert_algorithm_config_aicam(fields)

        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def update_algorithm_config_aicam(payload):
    try:
        id = payload.get('id')
        conf_name = payload.get('conf_name')
        Algorithm_library_id = payload.get('Algorithm_library_id')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id')
        conf_area = payload.get('conf_area')
        test_type_id = payload.get('test_type_id')
        shield_status = payload.get('shield_status')
        tem_conf_area = payload.get('tem_conf_area')
        tem_frames = payload.get('tem_frames')
        confidence = payload.get('confidence')
        draw_type = payload.get('draw_type')
        interval_time = payload.get('interval_time', 0)
        img_resolution = payload.get('img_resolution')
        duration_time = payload.get('duration_time', 0)
        image_draw_type = payload.get('image_draw_type', 1)
        Algorithm_config_ps = payload.get('Algorithm_config_ps')
        scene_typename = payload.get('scene_typename')
        sensitivity = payload.get('sensitivity')
        resource_id = payload.get('resource_id')
        defense_time_start = payload.get('defense_time_start')
        defense_time_end = payload.get('defense_time_end')
        model_template_config_id = payload.get('model_template_config_id')
        template_list_area = payload.get('template_list_area')
        image_count = payload.get('image_count', 5)
        template_small_id = payload.get('template_small_id')
        count_time = payload.get('count_time', 0)
        res_type = payload.get('res_type', 1)
        resource_id_old = payload.get('resource_id_old')
        computing_id = payload.get('computing_id')
        template_data = payload.get('template_data')
        label_list = payload.get('label_list')
        model_template_type_id = payload.get('model_template_type_id')
        amp = payload.get('amp', 10)
        alg_select_type = payload.get('alg_select_type', 3)
        model_two_type = payload.get('model_two_type')
        model_two_data = payload.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = payload.get('priority')
        run_time = payload.get('run_time')
        uwb_distance = payload.get('uwb_distance')
        cross_line_area = payload.get('cross_line_area')
        Entering_num = payload.get('Entering_num')
        Exiting_num = payload.get('Exiting_num')
        all_Entering_num = payload.get('all_Entering_num')
        all_Exiting_num = payload.get('all_Exiting_num')
        params = [id, conf_name, Algorithm_library_id, Mine_id, Equipment_id, conf_area, test_type_id, model_template_config_id]
        if not all(params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        camera_config_id = db.session.query(Algorithm_config_3588.camera_config_id).filter(
            Algorithm_config_3588.id == id
        ).first()
        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == Equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}

        if not computing_id:
            computing_equipment = db.session.query(Computing_equipment).filter(
                Computing_equipment.computing_ip == camera_ip
            ).first()

            if computing_equipment:
                computing_id = computing_equipment.id
        # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
        if equipment.parent_id is None:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()
        else:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()


        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录，请先下发算法到该设备'}

        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}
        if not equipment.code:
            cam_equipment_id = 1
        else:
            cam_equipment_id = int(str(equipment.code)[0])
        # 根据检测类型ID查询检测类型中文名称
        test_type = db.session.query(Algorithm_test_type_3588).filter(
            Algorithm_test_type_3588.id == test_type_id
        ).first()

        if not test_type:
            return {'code': 400, 'msg': '未找到指定的检测类型'}

        test_type_cname = test_type.test_type_cname
        # 调用摄像头接口添加算法配置

        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_update"
            webhook_trigger = 0
            # 构建请求参数（与数据库字段一致）
            camera_payload = {
                'id':camera_config_id[0] ,
                'conf_name': conf_name,
                'Algorithm_library_id': algorithm_camera_id,
                'Mine_id': Mine_id,
                'Equipment_id': cam_equipment_id,
                'conf_area': conf_area if conf_area else [],
                'status': status if status else '1',
                # 'test_type_cname': test_type_cname,
                'shield_status': shield_status,
                'tem_conf_area': tem_conf_area if tem_conf_area else [],
                'tem_frames': tem_frames,
                'confidence': confidence,
                'draw_type': draw_type,
                'interval_time': interval_time,
                'img_resolution': img_resolution,
                'duration_time': duration_time,
                'image_draw_type': image_draw_type,
                'Algorithm_config_ps': Algorithm_config_ps,
                'scene_typename': scene_typename,
                'sensitivity': sensitivity,
                'resource_id': resource_id,
                'defense_time_start': defense_time_start,
                'defense_time_end': defense_time_end,
                'model_template_config_id': model_template_config_id,
                'template_list_area': template_list_area if template_list_area else [],
                'image_count': image_count,
                'template_small_id': template_small_id,
                'count_time': count_time,
                'res_type': res_type,
                'computing_id': computing_id,
                'template_data': template_data if template_data else '',
                'label_list': label_list if label_list else [],
                'model_template_type_id': model_template_type_id,
                'amp': amp,
                'alg_select_type': alg_select_type,
                'model_two_type': model_two_type,
                'model_two_data': model_two_data,
                'priority': priority,
                'run_time': run_time,
                'uwb_distance': uwb_distance,
                'cross_line_area': cross_line_area,
                'Entering_num': Entering_num,
                'Exiting_num': Exiting_num,
                'all_Entering_num': all_Entering_num,
                'all_Exiting_num': all_Exiting_num,
                'webhook_trigger': int(webhook_trigger)
            }

            response = requests.post(url, data=camera_payload, timeout=30)
            result = response.json()

            # 只有摄像头接口返回200才继续写入本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'camera_ip': camera_ip,
                        'equipment_id': Equipment_id,
                        'conf_name': conf_name
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }

        updated_fields = {
            'conf_name': conf_name,
            'Algorithm_library_id': Algorithm_library_id,
            'Mine_id': Mine_id,
            'Equipment_id': Equipment_id,
            'conf_area': str(conf_area),
            'Algorithm_test_type_id': test_type_id,
            'shield_status': shield_status,
            'tem_conf_area': str(tem_conf_area) if tem_conf_area else None,
            'tem_frames': tem_frames if tem_frames else None,
            'draw_type': draw_type,
            'confidence': confidence,
            'interval_time': interval_time if tem_frames else 0,
            'conf_img_resolution': img_resolution,
            'duration_time': duration_time if duration_time else 0,
            'image_draw_type': image_draw_type if image_draw_type else 1,
            'Algorithm_config_ps': Algorithm_config_ps if Algorithm_config_ps else None,
            'scene_typename': scene_typename if scene_typename else None,
            'sensitivity': sensitivity if sensitivity else 0,
            'resource_id': int(resource_id) if resource_id and str(resource_id).lower() != 'null' else None,
            'defense_time_start': defense_time_start if defense_time_start else None,
            'defense_time_end': defense_time_end if defense_time_end else None,
            'model_template_config_id': model_template_config_id if model_template_config_id else None,
            'template_list_area': str(template_list_area),
            'image_count': image_count if image_count else 5,
            'template_small_id': template_small_id if template_small_id else None,
            'count_time': count_time,
            'conf_status': 1,
            'computing_id': computing_id,
            'template_data': template_data,
            'label_list': label_list,
            'model_status': 1,
            'model_template_type_id': model_template_type_id,
            'amp': amp,
            'alg_select_type': alg_select_type,
            'model_two_data': model_two_data,
            'model_two_type': model_two_type,
            'priority': priority,
            'run_time': run_time,
            'uwb_distance': uwb_distance,
            'cross_line_area': cross_line_area,
            'Entering_num': Entering_num,
            'Exiting_num': Exiting_num,
            'all_Entering_num': all_Entering_num,
            'all_Exiting_num': all_Exiting_num,
        }
        update_algorithm_config_fields_aicam(id, updated_fields)
        return {'code': 200, 'msg': '算法配置数据修改完成'}

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}
# 一路多模型新增
def add_algorithm_config_models_aicam(payload):
    try:
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id') or payload.get('equipment_name')
        model_data = payload.get('model_data', [])
        uwb_distance = payload.get('uwb_distance')
        if not all([conf_name, Mine_id, Equipment_id]) or not model_data:
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        first_model = model_data[0]
        Algorithm_library_id = first_model.get('Algorithm_library_id')
        conf_area = first_model.get('conf_area')
        status = first_model.get('status')
        test_type_id = first_model.get('test_type_id')
        shield_status = first_model.get('shield_status')
        tem_conf_area = first_model.get('tem_conf_area')
        tem_frames = first_model.get('tem_frames')
        confidence = first_model.get('confidence')
        draw_type = first_model.get('draw_type')
        interval_time = first_model.get('interval_time', 0)
        img_resolution = first_model.get('img_resolution')
        duration_time = first_model.get('duration_time', 0)
        image_draw_type = first_model.get('image_draw_type', 1)
        Algorithm_config_ps = first_model.get('Algorithm_config_ps')
        scene_typename = first_model.get('scene_typename')
        sensitivity = first_model.get('sensitivity')
        resource_id = first_model.get('resource_id',None)
        defense_time_start = first_model.get('defense_time_start')
        defense_time_end = first_model.get('defense_time_end')
        model_template_config_id = first_model.get('model_template_config_id')
        template_list_area = first_model.get('template_list_area')
        image_count = first_model.get('image_count')
        template_small_id = first_model.get('template_small_id')
        count_time = first_model.get('count_time', 0)
        res_type = first_model.get('res_type')
        computing_id = first_model.get('computing_id', None)
        template_data = first_model.get('template_data')
        label_list = first_model.get('label_list')
        model_template_type_id = first_model.get('model_template_type_id')
        amp = first_model.get('amp', 10)
        alg_select_type = first_model.get('alg_select_type', 3)
        model_two_type = first_model.get('model_two_type')
        model_two_data = first_model.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = first_model.get('priority')
        run_time = first_model.get('run_time')
        if get_algorithm_config_by_name_aicam(conf_name,Equipment_id):
            return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
            return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
            return {'code': 400, 'msg': '算法库id不存在'}
        _ = get_mine_by_id(Mine_id)
        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == Equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}
        if not computing_id:
            computing_equipment = db.session.query(Computing_equipment).filter(
                Computing_equipment.computing_ip == camera_ip
            ).first()

            if computing_equipment:
                computing_id = computing_equipment.id

        # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
        if equipment.parent_id is None:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()
        else:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()

        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录，请先下发算法到该设备'}

        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

        if not equipment.code:
            cam_equipment_id = 1
        else:
            cam_equipment_id = int(str(equipment.code)[0])

        extra_models_data = []
        for i in range(1, len(model_data)):
            model = model_data[i]
            algorithm_info = get_algorithm_library_by_id_aicam(model.get('Algorithm_library_id'))
            # resource_info = get_resource_usage_by_id(model.get('resource_id'))
            extra_model_data = {
                'Algorithm_library_id': model.get('Algorithm_library_id'),
                'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                'conf_area': convert_data_format(model.get('conf_area', [])),
                'confidence': model.get('confidence', ''),
                'interval_time': model.get('interval_time', 0),
                'duration_time': model.get('duration_time', 0),
                'dev_id': None,
                'res_type': model.get('res_type', 1),
                'algorithm_type_list': str(algorithm_info.algorithm_type_list) if algorithm_info else '',
                'label_list': model.get('label_list', [])
            }
            extra_models_data.append(extra_model_data)
        # 构建发送给摄像头的model_data，替换equipment_name和Algorithm_library_id
        model_data_camera = []
        for model_item in model_data:
            # 复制原始配置数据
            camera_model = model_item.copy()

            # 获取当前配置的Algorithm_library_id
            original_algorithm_id = model_item.get('Algorithm_library_id')

            # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
            if equipment.parent_id is None:
                algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                    and_(
                        AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                        AlgorithmLibrary2Camera.algorithm_libary_id == original_algorithm_id
                    )
                ).first()
            else:
                algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                    and_(
                        AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                        AlgorithmLibrary2Camera.algorithm_libary_id == original_algorithm_id
                    )
                ).first()

            # 如果找到关联记录，使用algorithm_camera_id替换Algorithm_library_id
            if algo_relation and algo_relation.algorithm_camera_id:
                camera_model['Algorithm_library_id'] = algo_relation.algorithm_camera_id
            else:
                return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

            # 替换equipment_name为cam_equipment_id
            camera_model['equipment_name'] = cam_equipment_id

            model_data_camera.append(camera_model)
        # 调用摄像头接口添加算法配置
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_add_models"
            # 构建请求参数（与数据库字段一致）
            webhook_trigger = 0
            camera_payload = {
                'conf_name': conf_name,
                'Mine_id': Mine_id,
                'equipment_name': cam_equipment_id,
                'model_data': model_data_camera ,
                'uwb_distance':uwb_distance,
                'webhook_trigger': int(webhook_trigger),

            }

            response = requests.post(url, json=camera_payload, timeout=30)
            result = response.json()
            camera_config_id = result.get('algorithm_id')

            # 只有摄像头接口返回200才继续写入本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'camera_ip': camera_ip,
                        'equipment_id': Equipment_id,
                        'conf_name': conf_name
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        fields = {
            'conf_name': conf_name,
            'Algorithm_library_id': Algorithm_library_id,
            'Mine_id': Mine_id,
            'Equipment_id': Equipment_id,
            'conf_area': conf_area,
            'status': status,
            'test_type_id': test_type_id,
            'shield_status': shield_status,
            'tem_conf_area': tem_conf_area,
            'tem_frames': tem_frames,
            'confidence': confidence,
            'draw_type': draw_type,
            'interval_time': interval_time,
            'img_resolution': img_resolution,
            'duration_time': duration_time,
            'image_draw_type': image_draw_type,
            'Algorithm_config_ps': Algorithm_config_ps,
            'scene_typename': scene_typename,
            'sensitivity': sensitivity,
            'resource_id': resource_id,
            'defense_time_start': defense_time_start,
            'defense_time_end': defense_time_end,
            'model_template_config_id': model_template_config_id,
            'template_list_area': template_list_area,
            'image_count': image_count,
            'template_small_id': template_small_id,
            'count_time': count_time,
            'res_type': res_type,
            'computing_id': computing_id,
            'template_data': template_data,
            'label_list': label_list,
            'model_template_type_id': model_template_type_id,
            'amp': amp,
            'alg_select_type': alg_select_type,
            'model_two_type': model_two_type,
            'model_two_data': model_two_data,
            'priority': priority,
            'run_time': run_time,
            'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
            'model_algo_data_ori': json.dumps(model_data[1:], ensure_ascii=False) if len(model_data) > 1 else '',
            'multimodels_type': 1,
            'camera_config_id': camera_config_id,
            'uwb_distance': uwb_distance
        }
        config_obj = insert_algorithm_config_aicam(fields)

        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

# 一路多模型修改
def update_algorithm_config_models_aicam(payload):
    try:
        id = payload.get('id')
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('equipment_name') or payload.get('Equipment_id')
        model_data = payload.get('model_data')
        uwb_distance = payload.get('uwb_distance')
        if not model_data:
            return {'code': 400, 'msg': '缺少算法模型参数'}
        first_model = model_data[0]
        Algorithm_library_id = first_model.get('Algorithm_library_id')
        conf_area = first_model.get('conf_area')
        test_type_id = first_model.get('test_type_id')
        shield_status = first_model.get('shield_status')
        tem_conf_area = first_model.get('tem_conf_area')
        tem_frames = first_model.get('tem_frames')
        confidence = first_model.get('confidence')
        draw_type = first_model.get('draw_type')
        interval_time = first_model.get('interval_time', 0)
        img_resolution = first_model.get('img_resolution')
        duration_time = first_model.get('duration_time', 0)
        image_draw_type = first_model.get('image_draw_type', 1)
        Algorithm_config_ps = first_model.get('Algorithm_config_ps')
        scene_typename = first_model.get('scene_typename')
        sensitivity = first_model.get('sensitivity')
        resource_id = first_model.get('resource_id')
        defense_time_start = first_model.get('defense_time_start')
        defense_time_end = first_model.get('defense_time_end')
        model_template_config_id = first_model.get('model_template_config_id')
        template_list_area = first_model.get('template_list_area')
        image_count = first_model.get('image_count', 5)
        template_small_id = first_model.get('template_small_id')
        count_time = first_model.get('count_time', 0)
        res_type = first_model.get('res_type', 1)
        resource_id_old = first_model.get('resource_id_old')
        computing_id = first_model.get('computing_id')
        template_data = first_model.get('template_data')
        label_list = first_model.get('label_list')
        model_template_type_id = first_model.get('model_template_type_id')
        amp = first_model.get('amp', 10)
        alg_select_type = first_model.get('alg_select_type', 3)
        model_two_type = first_model.get('model_two_type')
        model_two_data = first_model.get('model_two_data',
                                         '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = first_model.get('priority')
        run_time = first_model.get('run_time')
        params = [id, conf_name, Mine_id, Equipment_id]
        if not all(params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        camera_config_id = db.session.query(Algorithm_config_3588.camera_config_id).filter(
            Algorithm_config_3588.id == id
        ).first()
        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == Equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}
        if not computing_id:
            computing_equipment = db.session.query(Computing_equipment).filter(
                Computing_equipment.computing_ip == camera_ip
            ).first()

            if computing_equipment:
                computing_id = computing_equipment.id

        # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
        if equipment.parent_id is None:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()
        else:
            relation = db.session.query(AlgorithmLibrary2Camera).filter(
                and_(
                    AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                    AlgorithmLibrary2Camera.algorithm_libary_id == Algorithm_library_id
                )
            ).first()

        if not relation:
            return {'code': 400, 'msg': '未找到设备与算法的关联记录，请先下发算法到该设备'}

        algorithm_camera_id = relation.algorithm_camera_id
        if not algorithm_camera_id:
            return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

        if not equipment.code:
            cam_equipment_id = 1
        else:
            cam_equipment_id = int(str(equipment.code)[0])
        extra_models_data = []
        for i in range(1, len(model_data)):
            model = model_data[i]
            algorithm_info = get_algorithm_library_by_id_aicam(model.get('Algorithm_library_id'))
            # resource_info = get_resource_usage_by_id(model.get('resource_id'))
            conf_area_raw = model.get('conf_area', [])
            try:
                conf_area_eval = eval(conf_area_raw) if isinstance(conf_area_raw, str) else conf_area_raw
            except Exception:
                conf_area_eval = conf_area_raw
            conf_area_data = convert_data_format(conf_area_eval)
            if isinstance(conf_area_data, str):
                try:
                    conf_area_data = ast.literal_eval(conf_area_data)
                except Exception:
                    pass
            extra_model_data = {
                'Algorithm_library_id': model.get('Algorithm_library_id'),
                'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                'conf_area': conf_area_data,
                'confidence': model.get('confidence', ''),
                'interval_time': model.get('interval_time', 0),
                'duration_time': model.get('duration_time', 0),
                'dev_id': None,
                'res_type': model.get('res_type', 1),
                'algorithm_type_list': algorithm_info.algorithm_type_list if algorithm_info else '',
                'label_list': model.get('label_list', [])
            }
            extra_models_data.append(extra_model_data)
        # 构建发送给摄像头的model_data，替换equipment_name和Algorithm_library_id
        model_data_camera = []
        for model_item in model_data:
            # 复制原始配置数据
            camera_model = model_item.copy()

            # 获取当前配置的Algorithm_library_id
            original_algorithm_id = model_item.get('Algorithm_library_id')

            # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
            if equipment.parent_id is None:
                algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                    and_(
                        AlgorithmLibrary2Camera.equipment_id == Equipment_id,
                        AlgorithmLibrary2Camera.algorithm_libary_id == original_algorithm_id
                    )
                ).first()
            else:
                algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                    and_(
                        AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                        AlgorithmLibrary2Camera.algorithm_libary_id == original_algorithm_id
                    )
                ).first()

            # 如果找到关联记录，使用algorithm_camera_id替换Algorithm_library_id
            if algo_relation and algo_relation.algorithm_camera_id:
                camera_model['Algorithm_library_id'] = algo_relation.algorithm_camera_id
            else:
                return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

            # 替换equipment_name为cam_equipment_id
            camera_model['equipment_name'] = cam_equipment_id

            model_data_camera.append(camera_model)
        # 调用摄像头接口添加算法配置
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_update_models"
            # 构建请求参数（与数据库字段一致）
            webhook_trigger = 0
            camera_payload = {
                'conf_name': conf_name,
                'Mine_id': Mine_id,
                'equipment_name': cam_equipment_id,
                'model_data': model_data_camera ,
                'uwb_distance':uwb_distance,
                'id': camera_config_id[0],
                'webhook_trigger': int(webhook_trigger),

            }

            response = requests.post(url, json=camera_payload, timeout=30)
            result = response.json()

            # 只有摄像头接口返回200才继续写入本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'camera_ip': camera_ip,
                        'equipment_id': Equipment_id,
                        'conf_name': conf_name
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': Equipment_id,
                    'conf_name': conf_name
                }
            }
        conf_fields = {
            'conf_name': conf_name,
            'Algorithm_library_id': Algorithm_library_id,
            'Mine_id': Mine_id,
            'Equipment_id': Equipment_id,
            'conf_area': str(conf_area),
            'Algorithm_test_type_id': test_type_id,
            'shield_status': shield_status,
            'tem_conf_area': str(tem_conf_area) if tem_conf_area else None,
            'tem_frames': tem_frames if tem_frames else None,
            'draw_type': draw_type,
            'confidence': confidence,
            'interval_time': interval_time if tem_frames else 0,
            'conf_img_resolution': img_resolution,
            'duration_time': duration_time if duration_time else 0,
            'image_draw_type': image_draw_type if image_draw_type else 1,
            'Algorithm_config_ps': Algorithm_config_ps if Algorithm_config_ps else None,
            'scene_typename': scene_typename if scene_typename else None,
            'sensitivity': sensitivity if sensitivity else 0,
            'resource_id': resource_id if resource_id else 0,
            'defense_time_start': defense_time_start if defense_time_start else None,
            'defense_time_end': defense_time_end if defense_time_end else None,
            'model_template_config_id': model_template_config_id if model_template_config_id else None,
            'template_list_area': str(template_list_area),
            'image_count': image_count if image_count else 5,
            'template_small_id': template_small_id if template_small_id else None,
            'count_time': count_time,
            'conf_status': 0,
            'computing_id': computing_id,
            'template_data': template_data if template_data else '',
            'res_type': res_type if res_type else 1,
            'label_list': str(label_list) if label_list else str([]),
            'amp': amp,
            'alg_select_type': alg_select_type,
            'model_two_type': model_two_type,
            # 'model_two_data': model_two_data ,
            'priority': priority,
            'run_time': run_time,
            'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
            'model_algo_data_ori': json.dumps(model_data[1:], ensure_ascii=False) if len(model_data) > 1 else '',
            'uwb_distance': uwb_distance
        }
        update_algorithm_config_fields_aicam(id, conf_fields)
        return {'code': 200, 'msg': '算法配置数据修改完成'}

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_data_show_service_aicam(params):
    try:
        r = Redis(Redis_ip, Redis_port, 'list')
        conf_id = params.get('conf_id')
        data_id = params.get('data_id')
        if conf_id:
            algorithm_res = fetch_algorithm_config_detail_aicam(conf_id)
            if algorithm_res:
                if data_id == '0' or data_id is None:
                    algorithm_data = {
                        'id': algorithm_res.id,
                        'image': (
                            '/static/' + str(os.path.basename(r.get_string('em_{}'.format(algorithm_res.Equipment_id))))
                        ) if algorithm_res.Equipment_id and r.get_string('em_{}'.format(algorithm_res.Equipment_id)) else '',
                        'Algorithm_library_id': algorithm_res.Algorithm_library_id,
                        'algorithm_name': extract_chinese(algorithm_res.algorithm_name),
                        'Mine_id': algorithm_res.Mine_id,
                        'mine_name': algorithm_res.mine_name,
                        'Equipment_id': algorithm_res.Equipment_id,
                        'equipment_name': algorithm_res.equipment_name,
                        'equipment_type': algorithm_res.equipment_type,
                        'equipment_code': algorithm_res.code,
                        'conf_name': algorithm_res.conf_name if algorithm_res.conf_name else '',
                        'conf_object': algorithm_res.conf_object if algorithm_res.conf_object else '',
                        'conf_time': (algorithm_res.conf_time).strftime("%Y-%m-%d %H:%M:%S"),
                        'conf_area': algorithm_res.conf_area if algorithm_res.conf_area else '',
                        'conf_status,': algorithm_res.conf_status if algorithm_res.conf_status else '',
                        'test_type_id': algorithm_res.test_type_id if algorithm_res.test_type_id else '',
                        'status': configs.status[int(algorithm_res.status) - 1]['value'],
                        'shield_status': algorithm_res.shield_status,
                        'tem_conf_area': algorithm_res.tem_conf_area,
                        'tem_frames': algorithm_res.tem_frames,
                        'draw_type': algorithm_res.draw_type,
                        'confidence': algorithm_res.confidence,
                        'interval_time': algorithm_res.interval_time,
                        'img_resolution': algorithm_res.conf_img_resolution,
                        'duration_time': algorithm_res.duration_time,
                        'image_draw_type': algorithm_res.image_draw_type,
                        'update_time': (algorithm_res.update_time).strftime("%Y-%m-%d %H:%M:%S") if algorithm_res.update_time else '',
                        'Algorithm_config_ps': algorithm_res.Algorithm_config_ps if algorithm_res.Algorithm_config_ps else '',
                        'scene_typename': algorithm_res.scene_typename if algorithm_res.scene_typename else '',
                        'sensitivity': algorithm_res.sensitivity if algorithm_res.sensitivity else 0,
                        'model_status': algorithm_res.model_status if algorithm_res.model_status else 0,
                        'resource_id': algorithm_res.resource_id ,
                        'defense_time_start': algorithm_res.defense_time_start if algorithm_res.defense_time_start else '',
                        'defense_time_end': algorithm_res.defense_time_end if algorithm_res.defense_time_end else '',
                        'model_template_config_id': algorithm_res.model_template_config_id if algorithm_res.model_template_config_id else '',
                        'template_list_area': algorithm_res.template_list_area if algorithm_res.template_list_area else '',
                        'image_count': algorithm_res.image_count if algorithm_res.image_count else '',
                        'template_small_id': algorithm_res.template_small_id if algorithm_res.template_small_id else '',
                        'count_time': algorithm_res.count_time if algorithm_res.count_time else 0,
                        'res_type': algorithm_res.res_type if algorithm_res.res_type else 1,
                        'template_data': eval(algorithm_res.template_data) if algorithm_res.template_data else '',
                        'label_list': eval(algorithm_res.label_list) if algorithm_res.label_list else [],
                        'amp': algorithm_res.amp,
                        'alg_select_type': algorithm_res.alg_select_type,
                        'model_two_data': json.loads(algorithm_res.model_two_data),
                        'model_two_type': algorithm_res.model_two_type,
                        'priority': algorithm_res.priority,
                        'run_time': algorithm_res.run_time,
                        'multimodels_type': algorithm_res.multimodels_type,
                        'uwb_distance': algorithm_res.uwb_distance if algorithm_res.uwb_distance else '',
                        'camera_config_id': algorithm_res.camera_config_id if algorithm_res.camera_config_id else '',
                        'cross_line_area' : algorithm_res.cross_line_area if algorithm_res.cross_line_area else '',
                        'Entering_num': algorithm_res.Entering_num if algorithm_res.Entering_num else '',
                        'Exiting_num': algorithm_res.Exiting_num if algorithm_res.Exiting_num else '',
                        'all_Entering_num': algorithm_res.all_Entering_num if algorithm_res.all_Entering_num else '',
                        'all_Exiting_num': algorithm_res.all_Exiting_num if algorithm_res.all_Exiting_num else '',

                    }
                else:
                    try:
                        model_algo_data_ori = json.loads(algorithm_res.model_algo_data_ori) if isinstance(
                            algorithm_res.model_algo_data_ori, str) else algorithm_res.model_algo_data_ori
                        if model_algo_data_ori and len(model_algo_data_ori) > (int(data_id) - 1):
                            data_resouce = model_algo_data_ori[int(data_id) - 1]
                        else:
                            data_resouce = {}
                    except Exception:
                        model_algo_data_ori = []
                        data_resouce = {}
                    algorithm_data = {
                        'id': algorithm_res.id,
                        'image': (
                            '/static/' + str(os.path.basename(r.get_string('em_{}'.format(algorithm_res.Equipment_id))))
                        ) if algorithm_res.Equipment_id and r.get_string('em_{}'.format(algorithm_res.Equipment_id)) else '',
                        'Algorithm_library_id': int(data_resouce.get('Algorithm_library_id', 0)),
                        'algorithm_name': data_resouce.get('algorithm_name', ''),
                        'Mine_id': algorithm_res.Mine_id,
                        'mine_name': algorithm_res.mine_name,
                        'Equipment_id': algorithm_res.Equipment_id,
                        'equipment_name': algorithm_res.equipment_name,
                        'equipment_type': algorithm_res.equipment_type,
                        'equipment_code': algorithm_res.code,
                        'conf_name': algorithm_res.conf_name if algorithm_res.conf_name else '',
                        'conf_object': algorithm_res.conf_object if algorithm_res.conf_object else '',
                        'conf_time': (algorithm_res.conf_time).strftime("%Y-%m-%d %H:%M:%S"),
                        'conf_area': str(data_resouce.get('conf_area', '[]')),
                        'conf_status': algorithm_res.conf_status if algorithm_res.conf_status else '',
                        'test_type_id': data_resouce.get('test_type_id', ''),
                        'status': algorithm_res.status,
                        'shield_status': data_resouce.get('shield_status', ''),
                        'tem_conf_area': data_resouce.get('tem_conf_area', []),
                        'tem_frames': data_resouce.get('tem_frames', ''),
                        'draw_type': data_resouce.get('draw_type', ''),
                        'confidence': data_resouce.get('confidence', ''),
                        'interval_time': data_resouce.get('interval_time', ''),
                        'img_resolution': data_resouce.get('img_resolution', ''),
                        'duration_time': data_resouce.get('duration_time', ''),
                        'image_draw_type': data_resouce.get('image_draw_type', ''),
                        'update_time': (algorithm_res.update_time).strftime("%Y-%m-%d %H:%M:%S") if algorithm_res.update_time else '',
                        'Algorithm_config_ps': algorithm_res.Algorithm_config_ps if algorithm_res.Algorithm_config_ps else '',
                        'scene_typename': algorithm_res.scene_typename if algorithm_res.scene_typename else '',
                        'sensitivity': data_resouce.get('sensitivity', 0),
                        'model_status': algorithm_res.model_status,
                        'resource_id': data_resouce.get('resource_id', 0),
                        'defense_time_start': data_resouce.get('defense_time_start', ''),
                        'defense_time_end': data_resouce.get('defense_time_end', ''),
                        'model_template_config_id': data_resouce.get('model_template_config_id', ''),
                        'template_list_area': data_resouce.get('template_list_area', ''),
                        'image_count': data_resouce.get('image_count', ''),
                        'template_small_id': data_resouce.get('template_small_id', ''),
                        'count_time': algorithm_res.count_time,
                        'res_type': data_resouce.get('res_type', 1),
                        'label_list': eval(data_resouce.get('label_list', '[]')),
                        'amp': data_resouce.get('amp', ''),
                        'alg_select_type': data_resouce.get('alg_select_type', ''),
                        'model_two_data': data_resouce.get('model_two_data', '[]'),
                        'model_two_type': data_resouce.get('model_two_type', ''),
                        'priority': data_resouce.get('priority', ''),
                        'run_time': data_resouce.get('run_time', ''),
                        'multimodels_type': algorithm_res.multimodels_type,
                        'uwb_distance': algorithm_res.uwb_distance if algorithm_res.uwb_distance else '',
                        'camera_config_id': algorithm_res.camera_config_id if algorithm_res.camera_config_id else '',
                        'cross_line_area': algorithm_res.cross_line_area if algorithm_res.cross_line_area else '',
                        'Entering_num': algorithm_res.Entering_num if algorithm_res.Entering_num else '',
                        'Exiting_num': algorithm_res.Exiting_num if algorithm_res.Exiting_num else '',
                        'all_Entering_num': algorithm_res.all_Entering_num if algorithm_res.all_Entering_num else '',
                        'all_Exiting_num': algorithm_res.all_Exiting_num if algorithm_res.all_Exiting_num else '',
                    }
                return {'code': 200, 'datalist': algorithm_data, 'msg': '查询成功'}
            else:
                return {'code': 400, 'datalist': [], 'msg': '未有该配置的详情信息'}
        else:
            algorithm_name = params.get('algorithm_name')
            start_time = params.get('start_time')
            end_time = params.get('end_time')
            Mine_id = params.get('Mine_id')
            conf_name = params.get('conf_name')
            algorithm_library_id = params.get('algorithm_library_id')
            page = int(params.get('page', 1))
            per_page = int(params.get('per_page', 15))
            filters = []
            if Mine_id:
                filters.append(Algorithm_config_3588.Mine_id == Mine_id)
            if conf_name:
                filters.append(Algorithm_config_3588.conf_name.ilike(f"%{conf_name}%"))
            if algorithm_name:
                filters.append(Algorithm_library_3588.algorithm_name == algorithm_name)
            if start_time and end_time:
                filters.append(Algorithm_config_3588.conf_time.between(time_to_gmt_format(start_time), time_to_gmt_format(end_time)))
            if len(filters) >= 2:
                query_filter = and_(*filters)
            else:
                query_filter = filters[0] if filters else None
            algorithm_res = fetch_algorithm_configs_aicam(query_filter)
            if not query_filter:
                algorithm_res = fetch_algorithm_configs_aicam()
            algorithm_data = []
            filtered_items = []
            if algorithm_library_id:
                target_alg_id = int(algorithm_library_id)
                for item in algorithm_res:
                    if item.Algorithm_library_id == target_alg_id:
                        filtered_items.append(item)
                        continue
                    if item.model_algo_data_ori:
                        try:
                            model_algo_data = eval(item.model_algo_data_ori)
                            if isinstance(model_algo_data, list):
                                for model_item in model_algo_data:
                                    if isinstance(model_item, dict) and model_item.get('Algorithm_library_id') == target_alg_id:
                                        filtered_items.append(item)
                                        break
                        except Exception as e:
                            print(e)
            else:
                filtered_items = algorithm_res
            total_filtered = len(filtered_items)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_items = filtered_items[start:end]
            for i in paginated_items:
                algorithm_data_merge = {
                    'id': i.id,
                    'image': ('/static/' + str(os.path.basename(r.get_string('em_{}'.format(i.Equipment_id))))) if i.Equipment_id and r.get_string('em_{}'.format(i.Equipment_id)) else '',
                    'Algorithm_library_id': i.Algorithm_library_id,
                    'algorithm_name': extract_chinese(i.algorithm_name),
                    'Mine_id': i.Mine_id,
                    'mine_name': i.mine_name,
                    'Equipment_id': i.Equipment_id,
                    'equipment_name': i.equipment_name,
                    'equipment_type': i.equipment_type,
                    'equipment_code': i.code,
                    'conf_name': i.conf_name if i.conf_name else '',
                    'conf_object': i.conf_object if i.conf_object else '',
                    'conf_time': (i.conf_time).strftime("%Y-%m-%d %H:%M:%S"),
                    'conf_area': i.conf_area if i.conf_area else '',
                    'conf_status': i.conf_status if i.conf_status else '',
                    'status': configs.status[int(i.status) - 1]['value'],
                    'shield_status,': i.shield_status,
                    'tem_conf_area': i.tem_conf_area,
                    'tem_frames': i.tem_frames,
                    'draw_type': i.draw_type,
                    'confidence': i.confidence,
                    'interval_time': i.interval_time,
                    'img_resolution': i.conf_img_resolution,
                    'duration_time': i.duration_time,
                    'image_draw_type': i.image_draw_type,
                    'update_time': (i.update_time).strftime("%Y-%m-%d %H:%M:%S") if i.update_time else '',
                    'Algorithm_config_ps': i.Algorithm_config_ps if i.Algorithm_config_ps else '',
                    'scene_typename': i.scene_typename if i.scene_typename else '',
                    'sensitivity': i.sensitivity if i.sensitivity else 0,
                    'model_status': i.model_status if i.model_status else 1,
                    'resource_id': i.resource_id if i.resource_id else 0,
                    'defense_time_start': i.defense_time_start if i.defense_time_start else '',
                    'defense_time_end': i.defense_time_end if i.defense_time_end else '',
                    'defense_time_status': 1 if i.defense_time_start and i.defense_time_end else '',
                    'model_template_config_id': i.model_template_config_id if i.model_template_config_id else '',
                    'template_list_area': i.template_list_area if i.template_list_area else '',
                    'image_count': i.image_count if i.image_count else '',
                    'template_small_id': i.template_small_id if i.template_small_id else '',
                    'count_time': i.count_time if i.count_time else 0,
                    'res_type': i.res_type if i.res_type else 1,
                    'template_data': eval(i.template_data) if i.template_data else '',
                    'label_list': eval(i.label_list) if i.label_list else [],
                    'amp': i.amp,
                    'alg_select_type': i.alg_select_type,
                    'model_two_data': json.loads(i.model_two_data),
                    'model_two_type': i.model_two_type,
                    'priority': i.priority,
                    'run_time': i.run_time,
                    'multimodels_type': i.multimodels_type,
                    'uwb_distance': i.uwb_distance if i.uwb_distance else '',
                    'camera_config_id': i.camera_config_id if i.camera_config_id else '',
                    'cross_line_area': i.cross_line_area if i.cross_line_area else '',
                    'Entering_num' : i.Entering_num if i.Entering_num else '',
                    'Exiting_num' : i.Exiting_num if i.Exiting_num else '',
                    'all_Entering_num' : i.all_Entering_num if i.all_Entering_num else '',
                    'all_Exiting_num' : i.all_Exiting_num if i.all_Exiting_num else '',
                }
                if i.multimodels_type == 1:
                    try:
                        model_algo_data_ori = eval(i.model_algo_data_ori) if i.model_algo_data_ori else []
                        if isinstance(model_algo_data_ori, list):
                            first_model_data = {
                                'equipment_name': i.Equipment_id,
                                'Mine_id': i.Mine_id,
                                'Equipment_id': i.Equipment_id,
                                'conf_area': i.conf_area if i.conf_area else '',
                                'shield_status': i.shield_status,
                                'tem_conf_area': i.tem_conf_area if i.tem_conf_area else [],
                                'draw_type': i.draw_type if i.draw_type else '',
                                'img_resolution': i.conf_img_resolution if i.conf_img_resolution else '',
                                'image_draw_type': i.image_draw_type if i.image_draw_type else 1,
                                'template_list_area': i.template_list_area if i.template_list_area else [],
                                'priority': i.priority if i.priority else '',
                                'run_time': i.run_time if i.run_time else '',
                                'mine_name': i.mine_name if i.mine_name else '',
                                'algorithm_name': extract_chinese(i.algorithm_name),
                                'Algorithm_library_id': i.Algorithm_library_id,
                                'type': 0,
                                'confidence': i.confidence if i.confidence else '',
                                'tem_frames': i.tem_frames if i.tem_frames else '',
                                'duration_time': i.duration_time if i.duration_time else 0,
                                'interval_time': i.interval_time if i.interval_time else 0,
                                'sensitivity': i.sensitivity if i.sensitivity else 0,
                                'defense_time_start': i.defense_time_start if i.defense_time_start else '',
                                'defense_time_end': i.defense_time_end if i.defense_time_end else '',
                                'image_count': i.image_count if i.image_count else '',
                                'template_data': eval(i.template_data) if i.template_data else [],
                                'test_type_id': i.test_type_id if i.test_type_id else '',
                                'label_list': eval(i.label_list) if i.label_list else [],
                                'amp': i.amp if i.amp else '',
                                'alg_select_type': i.alg_select_type if i.alg_select_type else '',
                                'model_two_data': json.loads(i.model_two_data) if i.model_two_data else [],
                                'model_two_type': i.model_two_type if i.model_two_type else '',
                                'res_type': i.res_type if i.res_type else '',
                                'model_template_config_id': i.model_template_config_id if i.model_template_config_id else '',
                                'template_small_id': i.template_small_id if i.template_small_id else '',
                                'resource_id': i.resource_id if i.resource_id else '',
                                'model_template_type_id': i.model_template_type_id if i.model_template_type_id else '',
                                'computing_id': i.computing_id if i.computing_id else ''
                            }
                            merged_data = {
                                'Mine_id': i.Mine_id,
                                'conf_name': i.conf_name,
                                'equipment_name': i.Equipment_id,
                                'model_data': [first_model_data],
                                'uwb_distance': i.uwb_distance
                            }
                            merged_data['model_data'].extend(model_algo_data_ori)
                            algorithm_data_merge['merged_model_data'] = merged_data
                    except Exception as e:
                        print(e)
                else:
                    algorithm_data_merge['merged_model_data'] = '[]'
                algorithm_data.append(algorithm_data_merge)
            response_data = {
                'total_items': total_filtered,
                'total_pages': (total_filtered + per_page - 1) // per_page,
                'current_page': page,
                'per_page': per_page,
                'data': algorithm_data,
            }
            return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_conf_update_service_aicam(params):
    try:
        id = params.get('id')
        status = params.get('status')

        if not id or not status:
            return {'code': 400, 'msg': '缺少配置ID或状态参数'}

        # 查找当前配置信息
        data = db.session.query(Algorithm_config_3588).filter(
            Algorithm_config_3588.id == id
        ).first()

        if not data:
            return {'code': 400, 'msg': '未找到指定的配置'}

        # 获取摄像头配置ID和设备ID
        camera_config_id = data.camera_config_id
        equipment_id = data.Equipment_id

        if not camera_config_id:
            return {'code': 400, 'msg': '该配置未同步到摄像头，无法更新'}

        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到对应的设备'}

        camera_ip = equipment.equipment_ip
        if not camera_ip:
            return {'code': 400, 'msg': '设备IP为空'}


        # 调用摄像头接口更新配置状态
        try:
            url = f"http://{camera_ip}:5000/model_view/algorithm_conf_update"
            webhook_trigger = 0
            payload = {
                'id': camera_config_id,
                'status': status,
                'webhook_trigger': int(webhook_trigger)
            }

            response = requests.post(url, data=payload, timeout=30)
            result = response.json()

            # 只有摄像头接口返回200才继续修改本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                    'data': {
                        'camera_ip': camera_ip,
                        'equipment_id': equipment_id,
                        'config_id': id,
                        'camera_config_id': camera_config_id
                    }
                }
        except requests.exceptions.RequestException as e:
            return {
                'code': 400,
                'msg': f'请求摄像头接口失败: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': equipment_id,
                    'config_id': id,
                    'camera_config_id': camera_config_id
                }
            }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'调用摄像头接口异常: {str(e)}',
                'data': {
                    'camera_ip': camera_ip,
                    'equipment_id': equipment_id,
                    'config_id': id,
                    'camera_config_id': camera_config_id
                }
            }

        # 摄像头接口调用成功后，修改本地数据库
        if status == '运行':
            data.status = 1
            data.conf_status = 0
        else:
            data.status = 2
            data.conf_status = 0
            data.model_status = 2

        db.session.commit()

        return {
            'code': 200,
            'msg': '修改成功',
            'data': {
                'config_id': id,
                'camera_config_id': camera_config_id,
                'status': status,
                'camera_ip': camera_ip
            }
        }
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_data_delete_service_aicam(id_payload):
    try:
        id_list = id_payload if isinstance(id_payload, list) else None
        if not id_list:
            return {'code': 400, 'msg': '缺少配置id参数'}

        ids = [item['id'] for item in id_list]

        # 查询要删除的配置信息
        configs_to_delete = db.session.query(
            Algorithm_config_3588.id,
            Algorithm_config_3588.camera_config_id,
            Algorithm_config_3588.Equipment_id,
            Equipment.equipment_ip
        ).join(
            Equipment,
            Algorithm_config_3588.Equipment_id == Equipment.id
        ).filter(
            Algorithm_config_3588.id.in_(ids)
        ).all()

        if not configs_to_delete:
            return {'code': 404, 'msg': '未找到相关配置'}

        # 按IP分组，将相同IP的配置组合到一起
        ip_config_map = {}
        for config in configs_to_delete:
            camera_ip = config.equipment_ip
            if not camera_ip:
                continue

            if camera_ip not in ip_config_map:
                ip_config_map[camera_ip] = []

            ip_config_map[camera_ip].append({
                'config_id': config.id,
                'camera_config_id': config.camera_config_id
            })

        # 记录删除结果
        success_configs = []
        failed_configs = []

        # 遍历每个IP，批量调用摄像头接口
        for camera_ip, config_list in ip_config_map.items():
            try:
                # 过滤出有camera_config_id的配置
                valid_configs = [c for c in config_list if c['camera_config_id']]

                if not valid_configs:
                    # 没有摄像头配置ID的记录，标记为失败
                    for c in config_list:
                        failed_configs.append({
                            'config_id': c['config_id'],
                            'msg': '未找到摄像头配置ID'
                        })
                    continue

                # 调用摄像头接口删除配置
                url = f"http://{camera_ip}:5000/model_view/algorithm_data_delete"
                webhook_trigger = 0
                # 将所有camera_config_id放入列表中
                payload = {
                    'id': [{'id': c['camera_config_id']} for c in valid_configs],
                    'webhook_trigger': int(webhook_trigger)

                }

                response = requests.post(url, json=payload, timeout=30)
                result = response.json()

                if result.get('code') == 200:
                    # 摄像头删除成功，记录成功的配置ID
                    success_configs.extend([c['config_id'] for c in valid_configs])
                else:
                    # 摄像头删除失败
                    for c in valid_configs:
                        failed_configs.append({
                            'config_id': c['config_id'],
                            'msg': f'摄像头接口返回失败: {result.get("msg", "未知错误")}'
                        })

            except requests.exceptions.RequestException as e:
                # 网络请求失败
                for c in config_list:
                    failed_configs.append({
                        'config_id': c['config_id'],
                        'msg': f'请求摄像头接口失败: {str(e)}'
                    })
            except Exception as e:
                # 其他异常
                for c in config_list:
                    failed_configs.append({
                        'config_id': c['config_id'],
                        'msg': f'调用摄像头接口异常: {str(e)}'
                    })

        # 只有摄像头接口全部成功后，才删除本地数据库
        if failed_configs:
            return {
                'code': 400,
                'msg': f'部分配置删除失败',
                'data': {
                    'success_count': len(success_configs),
                    'failed_count': len(failed_configs),
                    'success_configs': success_configs,
                    'failed_configs': failed_configs
                }
            }

        # 所有摄像头接口都成功，删除本地数据库
        delete_algorithm_configs_by_ids_aicam(success_configs)

        return {
            'code': 200,
            'msg': f'删除成功，共删除{len(success_configs)}条配置',
            'data': {
                'success_count': len(success_configs),
                'deleted_configs': success_configs
            }
        }

    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'删除失败: {str(e)}'}

# def algorithm_sync_aicam(payload):
#     try:
#         Equipment_id = payload.get('Equipment_id')
#
#         # 根据设备ID查询设备IP
#         equipment = db.session.query(Equipment).filter(
#             Equipment.id == Equipment_id
#         ).first()
#
#         if not equipment:
#             return {'code': 400, 'msg': '未找到指定的设备'}
#
#         camera_ip = equipment.equipment_ip
#         computing_equipment = db.session.query(Computing_equipment).filter(
#             Computing_equipment.computing_ip == camera_ip
#         ).first()
#
#
#         # 调用摄像头接口添加算法配置
#         try:
#             url = f"http://{camera_ip}:5000/model_view/algorithm_sync_aicam"
#             # 构建请求参数（与数据库字段一致）
#             camera_payload = {}
#
#             response = requests.post(url, json=camera_payload, timeout=30)
#             result = response.json()
#
#             # 只有摄像头接口返回200才继续写入本地数据库
#             if result.get('code') != 200:
#                 return {
#                     'code': 400,
#                     'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
#                 }
#         except Exception as e:
#             return {
#                 'code': 400,
#                 'msg': f'同步失败: {str(e)}',
#             }
#         # 获取摄像头返回的算法数据列表
#         camera_algorithms = result.get('data', [])
#         if not camera_algorithms:
#             return {'code': 200, 'msg': '摄像头没有返回算法数据'}
#
#         # 遍历每条算法配置，匹配本地算法库并创建关联记录
#         failed_list = []
#
#         for camera_alg in camera_algorithms:
#             algorithm_file_name = camera_alg.get('algorithm_file_name')
#
#             if not algorithm_file_name:
#
#                 failed_list.append({'algorithm': camera_alg, 'reason': '缺少algorithm_file_name字段'})
#                 continue
#
#             # 在本地Algorithm_library_3588表中查找对应的算法
#             local_algorithm = db.session.query(Algorithm_library_3588).filter(
#                 Algorithm_library_3588.algorithm_file_name == algorithm_file_name
#             ).first()
#
#             if not local_algorithm:
#
#                 failed_list.append({
#                     'algorithm_file_name': algorithm_file_name,
#                     'reason': '本地算法库中未找到匹配的算法'
#                 })
#                 continue
#
#             # 检查是否已存在关联记录，避免重复插入
#             existing_relation = db.session.query(AlgorithmLibrary2Camera).filter(
#                 and_(
#                     AlgorithmLibrary2Camera.equipment_id == Equipment_id,
#                     AlgorithmLibrary2Camera.algorithm_libary_id == local_algorithm.id
#                 )
#             ).first()
#
#             if existing_relation:
#                 # 已存在关联记录，跳过
#                 continue
#
#             # 创建新的关联记录
#             new_relation = AlgorithmLibrary2Camera(
#                 equipment_id=Equipment_id,
#                 computing_resource_id=computing_equipment.id,
#                 algorithm_libary_id=local_algorithm.id,
#                 algorithm_camera_id=camera_alg.get('id')  # 摄像头端的算法ID
#             )
#             db.session.add(new_relation)
#
#         # 提交所有新增的关联记录
#         db.session.commit()
#
#         return {
#             'code': 200,
#             'msg': f'算法配置同步完成',
#         }
#     except Exception as e:
#         db.session.rollback()
#         return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_sync_aicam(equipment_id):
    try:

        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.id == equipment_id
        ).first()

        if not equipment:
            return {'code': 400, 'msg': '未找到指定的设备'}

        camera_ip = equipment.equipment_ip
        computing_equipment = db.session.query(Computing_equipment).filter(
            Computing_equipment.computing_ip == camera_ip
        ).first()

        # 调用摄像头接口添加算法配置
        try:
            url = f"http://{camera_ip}:5000/model_view/sync_algorithm_data"
            # 构建请求参数（与数据库字段一致）
            camera_payload = {}

            response = requests.get(url, json=camera_payload, timeout=30)
            result = response.json()
            print(result,'这是返回数据')

            # 只有摄像头接口返回200才继续写入本地数据库
            if result.get('code') != 200:
                return {
                    'code': 400,
                    'msg': f'摄像头接口调用失败: {result.get("msg", "未知错误")}',
                }
        except Exception as e:
            return {
                'code': 400,
                'msg': f'同步失败: {str(e)}',
            }

        # 获取摄像头返回的数据
        camera_data = result.get('data', {})
        camera_algorithms = camera_data.get('algorithm_config', [])
        camera_library = camera_data.get('algorithm_library', [])

        if not camera_library and not camera_algorithms:
            return {'code': 200, 'msg': '摄像头没有返回算法数据'}

        failed_list = []
        success_count = 0

        # ========== 第一步：处理 camera_library，创建关联记录 ==========
        for lib_item in camera_library:
            try:
                algorithm_file_name = lib_item.get('algorithm_file_name')
                camera_algorithm_id = lib_item.get('id')

                if not algorithm_file_name or not camera_algorithm_id:
                    failed_list.append({
                        'type': 'library',
                        'algorithm': lib_item,
                        'reason': '缺少algorithm_file_name或id字段'
                    })
                    continue

                # 在本地Algorithm_library_3588表中查找对应的算法
                local_algorithm = db.session.query(Algorithm_library_3588).filter(
                    Algorithm_library_3588.algorithm_file_name == algorithm_file_name
                ).first()

                if not local_algorithm:
                    failed_list.append({
                        'type': 'library',
                        'algorithm_file_name': algorithm_file_name,
                        'reason': '本地算法库中未找到匹配的算法'
                    })
                    continue

                # 检查是否已存在关联记录，避免重复插入
                existing_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                    and_(
                        AlgorithmLibrary2Camera.equipment_id == equipment_id,
                        AlgorithmLibrary2Camera.algorithm_libary_id == local_algorithm.id
                    )
                ).first()

                if not existing_relation:
                    # 创建新的关联记录
                    new_relation = AlgorithmLibrary2Camera(
                        equipment_id=equipment_id,
                        computing_resource_id=computing_equipment.id if computing_equipment else None,
                        algorithm_libary_id=local_algorithm.id,
                        algorithm_camera_id=camera_algorithm_id  # 摄像头端的算法ID
                    )
                    db.session.add(new_relation)

            except Exception as e:
                db.session.rollback()
                failed_list.append({
                    'type': 'library',
                    'algorithm': lib_item,
                    'reason': f'处理失败: {str(e)}'
                })
                continue

        # 提交所有关联记录
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {'code': 500, 'msg': f'关联记录提交失败: {str(e)}'}

        # ========== 第二步：处理 camera_algorithms，根据 multimodels_type 入库配置 ==========
        for camera_alg in camera_algorithms:
            try:
                conf_name = camera_alg.get('conf_name')
                multimodels_type = camera_alg.get('multimodels_type', 0)
                camera_config_id = camera_alg.get('id')
                algorithm_library_id = camera_alg.get('Algorithm_library_id')
                equipment_ip = equipment.equipment_ip
                Mine_id =  camera_alg.get('Mine_id')
                Equipment_id=camera_alg.get('Equipment_id')
                uwb_distance=camera_alg.get('uwb_distance')
                # 根据 multimodels_type 决定入库逻辑
                if multimodels_type == 1:
                    # 根据设备ID查询设备IP
                    equipment = db.session.query(Equipment).filter(
                        Equipment.equipment_ip == equipment_ip
                    ).first()
                    if Equipment_id == 1:
                        equ_id = db.session.query(Equipment).filter(
                            Equipment.equipment_ip == equipment_ip,
                            Equipment.equipment_type == 'AI单光摄像头'
                        ).first()
                        if not equ_id:
                            equ_id = db.session.query(Equipment).filter(
                                Equipment.code == '101',
                                Equipment.equipment_ip == equipment_ip,
                                Equipment.equipment_type == 'AI双光摄像头'
                            ).first()
                    else:

                        equ_id = db.session.query(Equipment).filter(
                            Equipment.code == '201',
                            Equipment.equipment_ip == equipment_ip,
                        ).first()
                    if not equipment and not equ_id:
                        failed_list.append({
                            'type': 'config',
                            'conf_name': conf_name,
                            'reason': '关联记录中未找到对应设备'
                        })
                        continue

                    # 多模型配置入库逻辑（参考 algorithm_config_add_models_callback）
                    model_data = camera_alg.get('merged_model_data', [])
                    # 处理模型数据
                    model_data_camera = []
                    for model_item in model_data:
                        camera_model = model_item.copy()
                        original_algorithm_id = model_item.get('Algorithm_library_id')

                        # 根据设备ID和算法ID查找关联记录，获取algorithm_camera_id
                        if equipment.parent_id is None:
                            algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                                and_(
                                    AlgorithmLibrary2Camera.equipment_id == equipment.id,
                                    AlgorithmLibrary2Camera.algorithm_camera_id == original_algorithm_id
                                )
                            ).first()
                        else:
                            algo_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                                and_(
                                    AlgorithmLibrary2Camera.equipment_id == equipment.parent_id,
                                    AlgorithmLibrary2Camera.algorithm_camera_id == original_algorithm_id
                                )
                            ).first()

                        # 如果找到关联记录，使用algorithm_camera_id替换Algorithm_library_id
                        if algo_relation and algo_relation.algorithm_libary_id:
                            camera_model['Algorithm_library_id'] = algo_relation.algorithm_libary_id
                        else:
                            failed_list.append({
                                'type': 'config',
                                'conf_name': conf_name,
                                'reason': '关联记录中未找到对应的algorithm_camera_id'
                            })
                            continue
                        # 替换equipment_name为cam_equipment_id
                        camera_model['equipment_name'] = equ_id.id

                        model_data_camera.append(camera_model)
                    first_model = model_data_camera[0]
                    Algorithm_library_id = first_model.get('Algorithm_library_id')
                    conf_area = first_model.get('conf_area')
                    status = first_model.get('status')
                    test_type_id = first_model.get('test_type_id')
                    shield_status = first_model.get('shield_status')
                    tem_conf_area = first_model.get('tem_conf_area')
                    tem_frames = first_model.get('tem_frames')
                    confidence = first_model.get('confidence')
                    draw_type = first_model.get('draw_type')
                    interval_time = first_model.get('interval_time', 0)
                    img_resolution = first_model.get('img_resolution')
                    duration_time = first_model.get('duration_time', 0)
                    image_draw_type = first_model.get('image_draw_type', 1)
                    Algorithm_config_ps = first_model.get('Algorithm_config_ps')
                    scene_typename = first_model.get('scene_typename')
                    sensitivity = first_model.get('sensitivity')
                    resource_id = first_model.get('resource_id', None)
                    defense_time_start = first_model.get('defense_time_start')
                    defense_time_end = first_model.get('defense_time_end')
                    model_template_config_id = first_model.get('model_template_config_id')
                    template_list_area = first_model.get('template_list_area')
                    image_count = first_model.get('image_count')
                    template_small_id = first_model.get('template_small_id')
                    count_time = first_model.get('count_time', 0)
                    res_type = first_model.get('res_type')
                    computing_id = first_model.get('computing_id', None)
                    template_data = first_model.get('template_data')
                    label_list = first_model.get('label_list')
                    model_template_type_id = first_model.get('model_template_type_id')
                    amp = first_model.get('amp', 10)
                    alg_select_type = first_model.get('alg_select_type', 3)
                    model_two_type = first_model.get('model_two_type')
                    model_two_data = first_model.get('model_two_data',
                                                     '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
                    priority = first_model.get('priority')
                    run_time = first_model.get('run_time')
                    _ = get_mine_by_id(Mine_id)

                    # 额外model数据
                    extra_models_data = []
                    for i in range(1, len(model_data_camera)):
                        model = model_data_camera[i]
                        print(model, type(model), model.get('conf_area', []), type(model.get('conf_area', [])),
                              '222222222222222')
                        algorithm_info = get_algorithm_library_by_id_aicam(model.get('Algorithm_library_id'))
                        # resource_info = get_resource_usage_by_id(model.get('resource_id'))
                        extra_model_data = {
                            'Algorithm_library_id': model.get('Algorithm_library_id'),
                            'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                            'conf_area': convert_data_format(model.get('conf_area', [])),
                            'confidence': model.get('confidence', ''),
                            'interval_time': model.get('interval_time', 0),
                            'duration_time': model.get('duration_time', 0),
                            'dev_id': None,
                            'res_type': model.get('res_type', 1),
                            'algorithm_type_list': str(algorithm_info.algorithm_type_list) if algorithm_info else '',
                            'label_list': model.get('label_list', [])
                        }
                        extra_models_data.append(extra_model_data)

                    fields = {
                        'conf_name': conf_name,
                        'Algorithm_library_id': Algorithm_library_id,
                        'Mine_id': Mine_id,
                        'Equipment_id': equ_id.id,
                        'conf_area': conf_area,
                        'status': status,
                        'test_type_id': test_type_id,
                        'shield_status': shield_status,
                        'tem_conf_area': tem_conf_area,
                        'tem_frames': tem_frames,
                        'confidence': confidence,
                        'draw_type': draw_type,
                        'interval_time': interval_time,
                        'img_resolution': img_resolution,
                        'duration_time': duration_time,
                        'image_draw_type': image_draw_type,
                        'Algorithm_config_ps': Algorithm_config_ps,
                        'scene_typename': scene_typename,
                        'sensitivity': sensitivity,
                        'resource_id': resource_id,
                        'defense_time_start': defense_time_start,
                        'defense_time_end': defense_time_end,
                        'model_template_config_id': model_template_config_id,
                        'template_list_area': template_list_area,
                        'image_count': image_count,
                        'template_small_id': template_small_id,
                        'count_time': count_time,
                        'res_type': res_type,
                        'computing_id': computing_id,
                        'template_data': template_data,
                        'label_list': label_list,
                        'model_template_type_id': model_template_type_id,
                        'amp': amp,
                        'alg_select_type': alg_select_type,
                        'model_two_type': model_two_type,
                        'model_two_data': model_two_data,
                        'priority': priority,
                        'run_time': run_time,
                        'model_algo_data': json.dumps(extra_models_data,
                                                      ensure_ascii=False) if extra_models_data else '',
                        'model_algo_data_ori': json.dumps(model_data_camera[1:], ensure_ascii=False) if len(
                            model_data) > 1 else '',
                        'multimodels_type': 1,
                        'camera_config_id': camera_config_id,
                        'uwb_distance': uwb_distance
                    }
                    insert_algorithm_config_aicam(fields)
                    success_count += 1


                else:
                    print(camera_alg,'2121212121')
                    camera_config_id = camera_alg.get('id')
                    conf_name = camera_alg.get('conf_name')
                    # equipment_ip = camera_alg.get('local_ip')
                    Mine_id = camera_alg.get('Mine_id', 1)
                    Algorithm_library_id = camera_alg.get('Algorithm_library_id')
                    Equipment_id = camera_alg.get('Equipment_id')
                    conf_area = camera_alg.get('conf_area')
                    status = camera_alg.get('status')
                    # test_type_id = camera_alg.get('test_type_id')
                    shield_status = camera_alg.get('shield_status')
                    tem_conf_area = camera_alg.get('tem_conf_area')
                    tem_frames = camera_alg.get('tem_frames')
                    confidence = camera_alg.get('confidence')
                    draw_type = camera_alg.get('draw_type')
                    interval_time = camera_alg.get('interval_time', 0)
                    img_resolution = camera_alg.get('img_resolution')
                    duration_time = camera_alg.get('duration_time', 0)
                    image_draw_type = camera_alg.get('image_draw_type', 1)
                    Algorithm_config_ps = camera_alg.get('Algorithm_config_ps')
                    scene_typename = camera_alg.get('scene_typename')
                    sensitivity = camera_alg.get('sensitivity')
                    resource_id = None
                    defense_time_start = camera_alg.get('defense_time_start')
                    defense_time_end = camera_alg.get('defense_time_end')
                    model_template_config_id = camera_alg.get('model_template_config_id')
                    template_list_area = camera_alg.get('template_list_area')
                    image_count = camera_alg.get('image_count')
                    template_small_id = camera_alg.get('template_small_id')
                    count_time = camera_alg.get('count_time', 0)
                    res_type = camera_alg.get('res_type')
                    # computing_id = camera_alg.get('computing_id')
                    template_data = camera_alg.get('template_data','[]')
                    label_list = camera_alg.get('label_list')
                    model_template_type_id = camera_alg.get('model_template_type_id')
                    amp = camera_alg.get('amp', 10)
                    alg_select_type = camera_alg.get('alg_select_type', 3)
                    model_two_type = camera_alg.get('model_two_type', 0)
                    model_two_data = camera_alg.get('model_two_data',
                                              '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
                    priority = camera_alg.get('priority')
                    run_time = camera_alg.get('run_time')
                    uwb_distance = camera_alg.get('uwb_distance')
                    cross_line_area = camera_alg.get('cross_line_area')
                    
                    _ = get_mine_by_id(Mine_id)

                    # 根据设备ID查询设备IP
                    equipment = db.session.query(Equipment).filter(
                        Equipment.equipment_ip == equipment_ip
                    ).first()
                    if Equipment_id == 1:
                        equ_id = db.session.query(Equipment).filter(
                            Equipment.equipment_ip == equipment_ip,
                            Equipment.equipment_type == 'AI单光摄像头'
                        ).first()
                        if not equ_id:
                            equ_id = db.session.query(Equipment).filter(
                                Equipment.code == '101',
                                Equipment.equipment_ip == equipment_ip,
                                Equipment.equipment_type == 'AI双光摄像头'
                            ).first()
                    else:

                        equ_id = db.session.query(Equipment).filter(
                            Equipment.code == '201',
                            Equipment.equipment_ip == equipment_ip,
                        ).first()
                    if not equipment and not equ_id:
                        failed_list.append({
                            'type': 'config',
                            'conf_name': conf_name,
                            'reason': '关联记录中未找到对应设备'
                        })
                        continue

                    # 根据传入的Algorithm_library_id（作为algorithm_camera_id）和Equipment_id查询关联表
                    algo_camera_relation = db.session.query(AlgorithmLibrary2Camera).filter(
                        and_(
                            AlgorithmLibrary2Camera.algorithm_camera_id == algorithm_library_id,
                            AlgorithmLibrary2Camera.equipment_id == equipment.id
                        )
                    ).first()

                    if not algo_camera_relation:
                        failed_list.append({
                            'type': 'config',
                            'conf_name': conf_name,
                            'reason': '关联记录中未找到对应的algo_camera_relation'
                        })
                        continue
                    # 根据computing_resource_id查询算力设备信息
                    computing_info = db.session.query(Computing_equipment).filter(
                        Computing_equipment.id == algo_camera_relation.computing_resource_id
                    ).first()

                    # 根据algorithm_libary_id查询算法库信息
                    algo_info = db.session.query(Algorithm_library_3588).filter(
                        Algorithm_library_3588.id == algo_camera_relation.algorithm_libary_id
                    ).first()

                    if not algo_info:
                        failed_list.append({
                            'type': 'config',
                            'conf_name': conf_name,
                            'reason': '关联记录中未找到对应的算法'
                        })
                        continue
                    test_type_id = None
                    if label_list:
                        # 如果label_list是字符串格式，先解析为列表
                        if isinstance(label_list, str):
                            try:
                                import ast
                                label_list = ast.literal_eval(label_list)
                            except:
                                pass

                        # 获取第一个标签作为test_type_ename
                        if isinstance(label_list, list) and len(label_list) > 0:
                            first_label = label_list[0]
                            if first_label:
                                test_type_obj = db.session.query(Algorithm_test_type_3588).filter(
                                    and_(
                                        Algorithm_test_type_3588.test_type_ename == first_label,
                                        Algorithm_test_type_3588.Algorithm_library_id == algo_info.id
                                    )
                                ).first()
                                if test_type_obj:
                                    test_type_id = test_type_obj.id
                    # 摄像头接口调用成功后，才写入本地数据库
                    fields = {
                        'conf_name': conf_name,
                        'Algorithm_library_id': algo_info.id,
                        'Mine_id': Mine_id,
                        'Equipment_id': equ_id.id,
                        'conf_area': str(conf_area) if conf_area else str([]),
                        'status': status if status else '1',
                        'test_type_id': test_type_id,
                        'shield_status': shield_status,
                        'tem_conf_area': tem_conf_area,
                        'tem_frames': tem_frames,
                        'confidence': confidence,
                        'draw_type': draw_type,
                        'interval_time': interval_time,
                        'img_resolution': img_resolution,
                        'duration_time': duration_time,
                        'image_draw_type': image_draw_type,
                        'Algorithm_config_ps': Algorithm_config_ps,
                        'scene_typename': scene_typename,
                        'sensitivity': sensitivity,
                        'resource_id': resource_id,
                        'defense_time_start': defense_time_start,
                        'defense_time_end': defense_time_end,
                        'model_template_config_id': model_template_config_id,
                        'template_list_area': template_list_area,
                        'image_count': image_count,
                        'template_small_id': template_small_id,
                        'count_time': count_time,
                        'res_type': res_type,
                        'computing_id': computing_info.id,
                        'template_data': template_data,
                        'label_list': label_list,
                        'model_template_type_id': model_template_type_id,
                        'amp': amp,
                        'alg_select_type': alg_select_type,
                        'model_two_type': 0,
                        'model_two_data': str(model_two_data),
                        'priority': priority,
                        'run_time': run_time,
                        'camera_config_id': camera_config_id,
                        'uwb_distance': uwb_distance,
                        'cross_line_area': cross_line_area
                    }
                    config_obj = insert_algorithm_config_aicam(fields)
                    success_count += 1

            except Exception as e:
                db.session.rollback()
                failed_list.append({
                    'type': 'config',
                    'algorithm': camera_alg,
                    'reason': f'处理失败: {str(e)}'
                })
                continue

        return {
            'code': 200,
            'msg': f'算法配置同步完成，成功{success_count}条，失败{len(failed_list)}条',
            'failed_list': failed_list if failed_list else None
        }
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def image_calibration_service(point_data):
    """
    AI摄像头图像标定服务

    :param point_data: 前端传递的点位数据列表
    [
        {
            "source_equipment_id": 1,
            "points": [{"x": 783, "y": 379}, {"x": 375, "y": 865}, ...]
        },
        {
            "source_equipment_id": 2,
            "points": [{"x": 1173, "y": 949}, {"x": 1266, "y": 727}, ...]
        }
    ]

    :return: dict with code, msg, data
    """
    try:
        # 1. 验证数据组数
        if not point_data or len(point_data) != 2:
            return {'code': 400, 'msg': '请提供两组摄像头点位数据'}

        # 2. 解析两组点位数据
        camera1_data = point_data[0]
        camera2_data = point_data[1]

        source_equipment_id_1 = camera1_data.get('source_equipment_id')
        source_equipment_id_2 = camera2_data.get('source_equipment_id')
        points1 = camera1_data.get('points', [])
        points2 = camera2_data.get('points', [])

        # 3. 验证必填字段
        if not source_equipment_id_1 or not source_equipment_id_2:
            return {'code': 400, 'msg': '缺少摄像头ID(source_equipment_id)'}

        # 4. 校验点位数据有效性
        is_valid, error_msg = AiCameraCalibrationData.check_calibration_points_valid(points1, points2)
        if not is_valid:
            return {'code': 400, 'msg': error_msg}

        # 5. 转换为numpy数组
        pts_src = AiCameraCalibrationData.convert_points_to_numpy(points1)
        pts_dst = AiCameraCalibrationData.convert_points_to_numpy(points2)

        # 6. 计算单应矩阵
        try:
            H, avg_test_err, test_errors = compute_homography_with_error(pts_src, pts_dst)
        except RuntimeError as e:
            return {'code': 400, 'msg': f'单应矩阵计算失败: {str(e)}'}

        # 7. 验证重投影误差
        if avg_test_err > 10:
            return {
                'code': 400,
                'msg': f'平均重投影误差为{avg_test_err:.3f}像素，超过阈值(10像素)，请重新标定'
            }

        # 8. 将单应矩阵转换为JSON字符串
        homography_matrix_str = json.dumps(H.tolist())

        # 9. 确定源相机和目标相机（较小的ID作为源相机）
        if source_equipment_id_1 < source_equipment_id_2:
            final_source_id = source_equipment_id_1
            final_target_id = source_equipment_id_2
        else:
            final_source_id = source_equipment_id_2
            final_target_id = source_equipment_id_1

        # 10. 检查是否已存在相同的标定记录
        existing_calibration = AiCameraCalibrationData.get_calibration_by_cameras(
            final_source_id,
            final_target_id
        )

        try:
            if existing_calibration:
                # 更新现有记录
                AiCameraCalibrationData.update_calibration_record(
                    existing_calibration,
                    homography_matrix_str,
                    avg_test_err
                )
                calibration_id = existing_calibration.id
            else:
                # 创建新记录
                new_calibration = AiCameraCalibrationData.create_calibration_record(
                    final_source_id,
                    final_target_id,
                    homography_matrix_str,
                    avg_test_err
                )
                calibration_id = new_calibration.id

            # 提交数据库事务
            AiCameraCalibrationData.commit_session()

            return {
                'code': 200,
                'msg': '标定成功',
                'data': {
                    'id': calibration_id,
                    'source_equipment_id': final_source_id,
                    'target_equipment_id': final_target_id,
                    'avg_test_err': avg_test_err,
                    'homography_matrix': H.tolist()
                }
            }

        except Exception as e:
            AiCameraCalibrationData.rollback_session()
            raise e

    except Exception as e:
        AiCameraCalibrationData.rollback_session()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def handle_algorithm_upload_group_aicam(uploaded_file, algorithm_status, algorithm_ps):
    """Validate all RKNN ZIP children, then store in the camera library only."""
    from werkzeug.datastructures import FileStorage
    try:
        content = read_uploaded_zip(uploaded_file)
        with open_package_zip(content) as archive:
            packages = inspect_algorithm_group(archive)
            for package in packages.values():
                require_camera_package(package)
            results = []
            for child_name in packages:
                with archive.open(child_name) as child:
                    child_content = child.read()
                child_file = FileStorage(stream=io.BytesIO(child_content),
                                         filename=os.path.basename(child_name.replace('\\', '/')))
                response = handle_algorithm_upload_single_aicam(child_file, algorithm_status, algorithm_ps)
                payload = response.get_json()
                results.append({'sub_zip_name': child_file.filename, 'code': payload.get('code', 500),
                                'msg': payload.get('msg', '处理失败'), 'data': payload.get('data')})
            succeeded = sum(item['code'] == 200 for item in results)
            return jsonify({'code': 200 if succeeded else 400, 'msg': 'AI摄像仪算法组包收录完成：成功 %s，失败 %s；尚未下发摄像仪' % (succeeded, len(results) - succeeded),
                            'data': results})
    except AlgorithmPackageError as error:
        return jsonify({'code': 400, 'msg': str(error)})
    except Exception:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '摄像仪算法组包收录失败，请联系管理员检查服务日志'})


def algorithm_data_update_service_aicam(params):
    try:
        library_id = params.get('id')
        status_value = {'运行': 1, '停止': 2, '1': 1, '2': 2}.get(str(params.get('status')))
        if isinstance(library_id, bool) or not str(library_id).isdigit() or int(library_id) < 1:
            return {'code': 400, 'msg': 'AI摄像仪算法ID无效'}
        if status_value is None:
            return {'code': 400, 'msg': '状态必须为运行或停止'}
        library = db.session.query(Algorithm_library_3588).filter(
            Algorithm_library_3588.id == int(library_id)).first()
        if library is None:
            return {'code': 404, 'msg': 'AI摄像仪算法不存在'}
        stopped_ids = []
        failed_ids = []
        if status_value == 2:
            camera_configs = db.session.query(Algorithm_config_3588).filter(
                Algorithm_config_3588.Algorithm_library_id == library.id).all()
            for config in camera_configs:
                if str(config.status) == '2':
                    # The existing camera service has already accepted this stop.
                    continue
                # Device IDs, forwarding and status semantics remain owned by
                # the camera-specific task service. It commits only after an
                # actual camera acknowledgement; it never writes ordinary tables.
                result = algorithm_conf_update_service_aicam(
                    {'id': config.id, 'status': '停止'})
                if isinstance(result, dict) and result.get('code') == 200:
                    stopped_ids.append(config.id)
                else:
                    failed_ids.append(config.id)
            if failed_ids:
                # Successful device operations are real and cannot be rolled
                # back by a local DB rollback. Keep library availability as it
                # was and report the partial result instead of claiming success.
                db.session.rollback()
                return {'code': 400,
                        'msg': '部分摄像头任务停止失败，算法库状态未更改；已停止任务保持停止，可重试',
                        'data': {'stopped_config_ids': stopped_ids,
                                 'failed_config_ids': failed_ids}}
        # Enabling an archive makes it selectable; it does not restart tasks.
        library.algorithm_status = status_value
        db.session.commit()
        return {'code': 200, 'msg': '修改成功',
                'data': {'stopped_config_ids': stopped_ids}}
    except Exception:
        db.session.rollback()
        return {'code': 500, 'msg': 'AI摄像仪算法状态更新失败，请稍后重试'}

