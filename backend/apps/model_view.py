from common.nvr_sync_runtime import InventoryUnavailable, hik_channels, online_value
from service.algorithm_stream_selection import stream_options
from service.people_count_editor import people_count_editor
from service.task_roi_thumbnail import task_roi_thumbnail
from service.algorithm_task_runtime import algorithm_task_runtime
from service.equipment_browser_service import EquipmentBrowser
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
from sqlalchemy import and_, func, update, select, text, cast, Integer, or_
import yaml
import io
import zipfile
from datetime import datetime, timedelta
import cv2
from urllib.parse import urlparse, quote
import time
from config.zlk_conf import del_stream_proxy, add_stream_proxy
from apps.scheduler_task import flatten_equipment_data
import json
import random
import string
import asyncio
from sqlalchemy.exc import SQLAlchemyError
from service.algorithm_model_service import *
from sqlalchemy import desc, func
from service.equipment_model_service import EquipmentService
import config.configs as configs
from service.scheduler_task_service import create_zlk_data_for_equipment,delete_zlk_data_for_equipment


# 创建蓝图，对应的register目录
model_view = Blueprint('model_view', __name__)


@model_view.route('/equipment_create', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_create():
    """APP接口层：设备创建接口"""
    try:
        # 获取请求参数
        equipment_type = request.json.get('equipment_type', None)
        manufacturer_type = request.json.get('manufacturer_type', None)
        equipment_name = request.json.get('equipment_name', None)
        equipment_ip = request.json.get('equipment_ip', None)
        equipment_uname = request.json.get('equipment_uname', None)
        equipment_password = request.json.get('equipment_password', None)
        equipment_aisles = request.json.get('equipment_aisles', None)
        equipment_codetype = request.json.get('equipment_codetype', None)
        Mine_id = request.json.get('Mine_id', None)
        flower_frames = request.json.get('flower_frames', None)
        children_list = request.json.get('children_list', None)
        uwb_ip = request.json.get('uwb_ip', None)
        alarm_device_ip = request.json.get('alarm_device_ip', None)
        # 调用service层处理业务逻辑
        result = EquipmentService.equipment_create_service(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                          equipment_uname, equipment_password, equipment_aisles, equipment_codetype,
                                          Mine_id, flower_frames, children_list, uwb_ip, alarm_device_ip)

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        err_msg = f"设备创建失败：{str(e)}"
        print(err_msg)
        return jsonify({'code': 400, 'msg': err_msg})
@model_view.route('/equipment_name_check', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_name_check():
    equipment_name = request.json.get('equipment_name', None)
    equipment_data = db.session.query(Equipment).filter(Equipment.equipment_name == equipment_name).first()
    if equipment_data:
        return jsonify({'code': 405, 'msg': '设备名称重复，请重新命名！'})


# 单设备数据详情展示接口
@model_view.route('/equipment_one_info', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_one_info():
    # 查找所传当前设备id
    equipment_id = request.args.get('equipment_id', None)

    # orm根据id查找对应详情
    equipment_info = db.session.query(
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code.label('equipment_code'),
    ).filter(Equipment.id == equipment_id).first()

    # 序列化
    equipment_info = convert_folder_to_dict_list(equipment_info, ['equipment_name', 'equipment_type', 'equipment_code'])
    return jsonify({'code': 200, 'msg': '查询成功', 'data': equipment_info, 'stream_capabilities': stream_options(equipment_id)})


def _online_status_view(model, filters=()):
    parts = (request.args.get('ids') or '').split(',')
    if len(parts) > 200 or any(not part.isascii() or not part.isdigit() or len(part) > 10 for part in parts):
        return jsonify({'code': 400, 'msg': '设备 ID 无效'})
    ids = {int(part) for part in parts}
    if min(ids) < 1 or max(ids) > 2147483647:
        return jsonify({'code': 400, 'msg': '设备 ID 无效'})
    rows = db.session.query(model.id, model.online).filter(model.id.in_(ids), *filters)
    return jsonify({'code': 200, 'data': {row.id: row.online for row in rows}})


# 设备数据展示接口 （新） 录像机父子
@model_view.route('/equipment_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_show():
    if request.args.get('scope') == 'status':
        return _online_status_view(Equipment)
    if request.args.get('scope') == 'devices':
        return jsonify(EquipmentBrowser(db.session, Equipment, Mine, configs).page(request.args))

    # '设备id'
    equipment_name = request.args.get('equipment_name', None)
    # '设备类型' ('摄像头','录像机','特殊摄像头',’浙江双视摄像头’,'视频中心存储')
    equipment_type = request.args.get('equipment_type', None)
    # 设备名字
    equipment_name1 = request.args.get('equipment_name1', None)

    # 第几页
    page = request.args.get('page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=15, type=int)


    # 判断是否为子类，如果是子类数据  if parent_id 写对应代码逻辑 如果是父类走下面代码逻辑
    # 查询该设备的 parent_id，如果 parent_id 不为 None，说明是子类
    parent_id = db.session.query(Equipment.parent_id).filter(Equipment.id == equipment_name).scalar()

    # 当 parent_id 不为空
    if parent_id is not None:

        # 子类逻辑
        # 假设前端传递的参数为 equipment_name 和 equipment_type，可能有一个或两个
        filters = []

        if equipment_name:
            filters.append(Equipment.id == equipment_name)

        type_list = []
        print(equipment_type, type(equipment_type))
        if equipment_type:
            # 按逗号拆分字符串，并去除每个值的前后空格
            type_ids = [s.strip() for s in equipment_type.split(',') if s.strip()]

            # 逐个转换为整数并获取对应类型名称
            for t_id in type_ids:
                try:
                    t_id_int = int(t_id)  # 转换为整数
                    # 从配置中获取类型名称，注意索引可能需要调整
                    type_name = configs.equipment_type[t_id_int - 1]['value']
                    type_list.append(type_name)
                except (ValueError, IndexError):
                    # 忽略无效值，继续处理其他值
                    continue
        if type_list:
            filters.append(Equipment.equipment_type.in_(type_list))

        if equipment_name1:
            filters.append(Equipment.equipment_name.like(f"%{equipment_name1}%"))
        # 如果有两个条件，使用 and 连接；如果只有一个条件，不使用 and

        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else None

        if query_filter is not None:
            equipment_info = db.session.query(
                Equipment.id, Equipment.equipment_type,
                Equipment.manufacturer_type, Equipment.equipment_name,
                Equipment.equipment_ip, Equipment.equipment_uname,
                Equipment.equipment_password, Equipment.equipment_aisles,
                Equipment.equipment_codetype, Equipment.user_status,
                Equipment.create_time,Equipment.parent_id,Equipment.code,
                Equipment.flower_frames,Equipment.equipment_width_height,
                Equipment.online,Equipment.equipment_constantBitRate,
                Equipment.equipment_maxFrameRate,Equipment.Hik_indexCode,
                Equipment.Ziguang_ape_rtsp_url, Equipment.Ziguang_ape_indexCode,Equipment.alarm_device_ip
            ).filter(query_filter).paginate(page=page, per_page=per_page, error_out=False)
        else:
                equipment_info = db.session.query(
                Equipment.id, Equipment.equipment_type,
                Equipment.manufacturer_type, Equipment.equipment_name,
                Equipment.equipment_ip, Equipment.equipment_uname,
                Equipment.equipment_password, Equipment.equipment_aisles,
                Equipment.equipment_codetype, Equipment.user_status,
                Equipment.create_time,Equipment.parent_id,Equipment.code,
                Equipment.flower_frames,Equipment.equipment_width_height,
                Equipment.online,Equipment.equipment_constantBitRate,
                Equipment.equipment_maxFrameRate,Equipment.Hik_indexCode,
                Equipment.Ziguang_ape_rtsp_url, Equipment.Ziguang_ape_indexCode,Equipment.alarm_device_ip
            ).paginate(page=page, per_page=per_page, error_out=False)


        # 连表查询获取模型应用数据列表
        equipment_list = [{
            'id': i.id, 'equipment_type': i.equipment_type,
            'manufacturer_type': i.manufacturer_type,
            'flower_frames': i.flower_frames,
            'equipment_name': i.equipment_name,
            'equipment_ip': i.equipment_ip,
            'equipment_uname': i.equipment_uname,
            'equipment_password': i.equipment_password,
            'equipment_aisles': i.equipment_aisles,
            'equipment_codetype': i.equipment_codetype,
            'equipment_code': i.code,
            'user_status': i.user_status,
            'parent_id': i.parent_id,
            'equipment_width_height': i.equipment_width_height,
            'equipment_constantBitRate': i.equipment_constantBitRate,
            'equipment_maxFrameRate': i.equipment_maxFrameRate,
            'Hik_indexCode': i.Hik_indexCode,
            'online': i.online,
            'Ziguang_ape_rtsp_url': i.Ziguang_ape_rtsp_url,
            'Ziguang_ape_indexCode': i.Ziguang_ape_indexCode,
            'alarm_device_ip' : i.alarm_device_ip,

        } for i in equipment_info.items]

        # 构建返回的 JSON
        response_data = {
            'total_items': equipment_info.total,
            'total_pages': equipment_info.pages,
            'current_page': equipment_info.page,
            'per_page': per_page,
            'data': equipment_list,
        }

        return jsonify({'code': 200, 'msg': '查询成功', 'data_list': response_data})

    # 当 parent_id 为空
    else:

        # 父类逻辑
        # 假设前端传递的参数为 equipment_name 和 equipment_type，可能有一个或两个
        filters = []
        if equipment_name1:
            if equipment_type == '1':   #模糊查询区分是否为摄像头
                if equipment_name:
                    filters.append(Equipment.id == equipment_name)

                # if equipment_type:
                #     equipment_type = (configs.equipment_type[int(equipment_type) - 1])['value']
                #     filters.append(Equipment.equipment_type == equipment_type)
                # if equipment_name:
                #     filters.append(Equipment.id == equipment_name)

                type_list = []
                print(equipment_type, type(equipment_type))
                if equipment_type:
                    # 按逗号拆分字符串，并去除每个值的前后空格
                    type_ids = [s.strip() for s in equipment_type.split(',') if s.strip()]

                    # 逐个转换为整数并获取对应类型名称
                    for t_id in type_ids:
                        try:
                            t_id_int = int(t_id)  # 转换为整数
                            # 从配置中获取类型名称，注意索引可能需要调整
                            type_name = configs.equipment_type[t_id_int - 1]['value']
                            type_list.append(type_name)
                        except (ValueError, IndexError):
                            # 忽略无效值，继续处理其他值
                            continue
                if type_list:
                    filters.append(Equipment.equipment_type.in_(type_list))

                if equipment_name1:
                    filters.append(Equipment.equipment_name.like(f"%{equipment_name1}%"))
                # 如果有两个条件，使用 and 连接；如果只有一个条件，不使用 and

                if len(filters) >= 2:
                    query_filter = and_(*filters)
                else:
                    query_filter = filters[0] if filters else None

                if query_filter is not None:
                    equipment_info = db.session.query(
                        Equipment.id, Equipment.equipment_type,
                        Equipment.manufacturer_type, Equipment.equipment_name,
                        Equipment.equipment_ip, Equipment.equipment_uname,
                        Equipment.equipment_password, Equipment.equipment_aisles,
                        Equipment.equipment_codetype, Equipment.user_status,
                        Equipment.create_time, Equipment.parent_id, Equipment.code,
                        Equipment.flower_frames, Equipment.equipment_width_height,
                        Equipment.online, Equipment.equipment_constantBitRate,
                        Equipment.equipment_maxFrameRate, Equipment.Hik_indexCode,Equipment.alarm_device_ip
                    ).filter(query_filter).paginate(page=page, per_page=per_page, error_out=False)
                else:
                    equipment_info = db.session.query(
                        Equipment.id, Equipment.equipment_type,
                        Equipment.manufacturer_type, Equipment.equipment_name,
                        Equipment.equipment_ip, Equipment.equipment_uname,
                        Equipment.equipment_password, Equipment.equipment_aisles,
                        Equipment.equipment_codetype, Equipment.user_status,
                        Equipment.create_time, Equipment.parent_id, Equipment.code,
                        Equipment.flower_frames, Equipment.equipment_width_height,
                        Equipment.online, Equipment.equipment_constantBitRate,
                        Equipment.equipment_maxFrameRate, Equipment.Hik_indexCode,Equipment.alarm_device_ip
                    ).paginate(page=page, per_page=per_page, error_out=False)

                # 连表查询获取模型应用数据列表
                equipment_list = [{
                    'id': i.id, 'equipment_type': i.equipment_type,
                    'manufacturer_type': i.manufacturer_type,
                    'flower_frames': i.flower_frames,
                    'equipment_name': i.equipment_name,
                    'equipment_ip': i.equipment_ip,
                    'equipment_uname': i.equipment_uname,
                    'equipment_password': i.equipment_password,
                    'equipment_aisles': i.equipment_aisles,
                    'equipment_codetype': i.equipment_codetype,
                    'equipment_code': i.code,
                    'user_status': i.user_status,
                    'parent_id': i.parent_id,
                    'equipment_width_height': i.equipment_width_height,
                    'equipment_constantBitRate': i.equipment_constantBitRate,
                    'equipment_maxFrameRate': i.equipment_maxFrameRate,
                    'Hik_indexCode': i.Hik_indexCode,
                    'online':i.online,
                    'alarm_device_ip':i.alarm_device_ip
                } for i in equipment_info.items]

                # 构建返回的 JSON
                response_data = {
                    'total_items': equipment_info.total,
                    'total_pages': equipment_info.pages,
                    'current_page': equipment_info.page,
                    'per_page': per_page,
                    'data': equipment_list,
                }

                return jsonify({'code': 200, 'msg': '查询成功', 'data_list': response_data})

            else:
                filters.append(Equipment.parent_id == None)

                if equipment_name:
                    filters.append(Equipment.id == equipment_name)

                matching_children = db.session.query(Equipment.parent_id).filter(
                    Equipment.parent_id != None,
                    Equipment.equipment_name.like(f"%{equipment_name1}%")
                ).distinct().all()

                matching_parent_ids = [child.parent_id for child in matching_children if child.parent_id is not None]

                # 添加到筛选条件中
                if matching_parent_ids:
                    filters.append(or_(
                        Equipment.id.in_(matching_parent_ids),  # 匹配的父设备
                        Equipment.parent_id.in_(matching_parent_ids)  # 以及它们的子设备
                    ))

                # if equipment_type:
                #
                #     equipment_type = (configs.equipment_type[int(equipment_type) - 1])['value']
                #     filters.append(Equipment.equipment_type == equipment_type)
                # if equipment_name:
                #     filters.append(Equipment.id == equipment_name)

                type_list = []
                print(equipment_type, type(equipment_type))
                if equipment_type:
                    # 按逗号拆分字符串，并去除每个值的前后空格
                    type_ids = [s.strip() for s in equipment_type.split(',') if s.strip()]

                    # 逐个转换为整数并获取对应类型名称
                    for t_id in type_ids:
                        try:
                            t_id_int = int(t_id)  # 转换为整数
                            # 从配置中获取类型名称，注意索引可能需要调整
                            type_name = configs.equipment_type[t_id_int - 1]['value']
                            type_list.append(type_name)
                        except (ValueError, IndexError):
                            # 忽略无效值，继续处理其他值
                            continue
                if type_list:
                    filters.append(Equipment.equipment_type.in_(type_list))

                # 如果有两个条件，使用 and 连接；如果只有一个条件，不使用 and

                if len(filters) >= 2:
                    query_filter = and_(*filters)
                else:
                    query_filter = filters[0] if filters else None

                if query_filter is not None:
                    equipment_info = db.session.query(
                        Equipment.id, Equipment.equipment_type,
                        Equipment.manufacturer_type, Equipment.equipment_name,
                        Equipment.equipment_ip, Equipment.equipment_uname,
                        Equipment.equipment_password, Equipment.equipment_aisles,
                        Equipment.equipment_codetype, Equipment.user_status,
                        Equipment.create_time, Equipment.parent_id, Equipment.code,
                        Equipment.flower_frames, Equipment.equipment_width_height,
                        Equipment.online, Equipment.equipment_constantBitRate,
                        Equipment.equipment_maxFrameRate, Equipment.Hik_indexCode,
                        Equipment.Ziguang_ape_rtsp_url, Equipment.Ziguang_ape_indexCode,
                        Equipment.alarm_device_ip
                    ).filter(query_filter).paginate(page=page, per_page=per_page, error_out=False)
                else:
                    equipment_info = db.session.query(
                        Equipment.id, Equipment.equipment_type,
                        Equipment.manufacturer_type, Equipment.equipment_name,
                        Equipment.equipment_ip, Equipment.equipment_uname,
                        Equipment.equipment_password, Equipment.equipment_aisles,
                        Equipment.equipment_codetype, Equipment.user_status,
                        Equipment.create_time, Equipment.parent_id, Equipment.code,
                        Equipment.flower_frames, Equipment.equipment_width_height,
                        Equipment.online, Equipment.equipment_constantBitRate,
                        Equipment.equipment_maxFrameRate, Equipment.Hik_indexCode,
                        Equipment.Ziguang_ape_rtsp_url, Equipment.Ziguang_ape_indexCode,Equipment.alarm_device_ip
                    ).paginate(page=page, per_page=per_page, error_out=False)

                    # 连表查询获取模型应用数据列表
                equipment_list = [{
                    'id': i.id, 'equipment_type': i.equipment_type,
                    'manufacturer_type': i.manufacturer_type,
                    'flower_frames': i.flower_frames,
                    'equipment_name': i.equipment_name,
                    'equipment_ip': i.equipment_ip,
                    'equipment_uname': i.equipment_uname,
                    'equipment_password': i.equipment_password,
                    'equipment_aisles': i.equipment_aisles,
                    'equipment_codetype': i.equipment_codetype,
                    'equipment_code': i.code,
                    'user_status': i.user_status,
                    'parent_id': i.parent_id,
                    'create_time': i.create_time,
                    'equipment_width_height': i.equipment_width_height,
                    'equipment_constantBitRate': i.equipment_constantBitRate,
                    'equipment_maxFrameRate': i.equipment_maxFrameRate,
                    'Hik_indexCode': i.Hik_indexCode,
                    'Ziguang_ape_rtsp_url': i.Ziguang_ape_rtsp_url,
                    'Ziguang_ape_indexCode': i.Ziguang_ape_indexCode,
                    'online': i.online,
                    'alarm_device_ip': i.alarm_device_ip
                } for i in equipment_info.items]

                # 使用列表推导式筛选设备类型为“录像机”的记录
                equipment_VCR = [record for record in equipment_info.items
                                 if record.equipment_type == '录像机' or record.equipment_type == '特殊摄像头'
                                 or record.equipment_type == '安防平台' or record.equipment_type == '紫光华智'
                                 or record.equipment_type == '视频中心存储' or record.equipment_type == 'AI双光摄像头'
                                 ]
                # 提取录像机的 ID
                vcr_ids = [record.id for record in equipment_VCR]
                equipment_list = children_data(equipment_list, vcr_ids)
                filtered_equipment_list = []
                for item in equipment_list:
                    if item.get('children'):  # 如果有子设备
                        # 筛选匹配的子设备
                        filtered_children = [
                            child for child in item['children']
                            if equipment_name1.lower() in child.get('equipment_name', '').lower()
                        ]
                        # 只保留有匹配子设备的父设备，并更新其子设备列表
                        if filtered_children:
                            item_copy = item.copy()
                            item_copy['children'] = filtered_children
                            filtered_equipment_list.append(item_copy)
                    else:
                        # 如果没有子设备，直接添加
                        filtered_equipment_list.append(item)

                equipment_list = filtered_equipment_list
                # 构建返回的 JSON
                response_data = {
                    'total_items': equipment_info.total,
                    'total_pages': equipment_info.pages,
                    'current_page': equipment_info.page,
                    'per_page': per_page,
                    'data': equipment_list,
                }

                return jsonify({'code': 200, 'msg': '查询成功', 'data_list': response_data})


        else:
            filters.append(Equipment.parent_id == None)

            if equipment_name:
                filters.append(Equipment.id == equipment_name)

            # if equipment_type:
            #
            #     equipment_type = (configs.equipment_type[int(equipment_type) - 1])['value']
            #     filters.append(Equipment.equipment_type == equipment_type)
            if equipment_name:
                filters.append(Equipment.id == equipment_name)

            type_list = []
            print(equipment_type, type(equipment_type))
            if equipment_type:
                # 按逗号拆分字符串，并去除每个值的前后空格
                type_ids = [s.strip() for s in equipment_type.split(',') if s.strip()]

                # 逐个转换为整数并获取对应类型名称
                for t_id in type_ids:
                    try:
                        t_id_int = int(t_id)  # 转换为整数
                        # 从配置中获取类型名称，注意索引可能需要调整
                        type_name = configs.equipment_type[t_id_int - 1]['value']
                        type_list.append(type_name)
                    except (ValueError, IndexError):
                        # 忽略无效值，继续处理其他值
                        continue
            if type_list:
                filters.append(Equipment.equipment_type.in_(type_list))

            # 如果有两个条件，使用 and 连接；如果只有一个条件，不使用 and

            if len(filters) >= 2:
                query_filter = and_(*filters)
            else:
                query_filter = filters[0] if filters else None


        if query_filter is not None:
            equipment_info = db.session.query(
                Equipment.id, Equipment.equipment_type,
                Equipment.manufacturer_type, Equipment.equipment_name,
                Equipment.equipment_ip, Equipment.equipment_uname,
                Equipment.equipment_password, Equipment.equipment_aisles,
                Equipment.equipment_codetype, Equipment.user_status,
                Equipment.create_time,Equipment.parent_id,Equipment.code,
                Equipment.flower_frames,Equipment.equipment_width_height,
                Equipment.online,Equipment.equipment_constantBitRate,
                Equipment.equipment_maxFrameRate,Equipment.Hik_indexCode,
                Equipment.Ziguang_ape_rtsp_url, Equipment.Ziguang_ape_indexCode,
                Equipment.alarm_device_ip
            ).filter(query_filter).paginate(page=page, per_page=per_page, error_out=False)
        else:
                equipment_info = db.session.query(
                Equipment.id, Equipment.equipment_type,
                Equipment.manufacturer_type, Equipment.equipment_name,
                Equipment.equipment_ip, Equipment.equipment_uname,
                Equipment.equipment_password, Equipment.equipment_aisles,
                Equipment.equipment_codetype, Equipment.user_status,
                Equipment.create_time,Equipment.parent_id,Equipment.code,
                Equipment.flower_frames,Equipment.equipment_width_height,
                Equipment.online,Equipment.equipment_constantBitRate,
                Equipment.equipment_maxFrameRate,Equipment.Hik_indexCode,
                Equipment.Ziguang_ape_rtsp_url,Equipment.Ziguang_ape_indexCode,Equipment.alarm_device_ip
            ).paginate(page=page, per_page=per_page, error_out=False)


        # 连表查询获取模型应用数据列表
        equipment_list = [{
            'id': i.id, 'equipment_type': i.equipment_type,
            'manufacturer_type': i.manufacturer_type,
            'flower_frames': i.flower_frames,
            'equipment_name': i.equipment_name,
            'equipment_ip': i.equipment_ip,
            'equipment_uname': i.equipment_uname,
            'equipment_password': i.equipment_password,
            'equipment_aisles': i.equipment_aisles,
            'equipment_codetype': i.equipment_codetype,
            'equipment_code': i.code,
            'user_status': i.user_status,
            'parent_id': i.parent_id,
            'create_time': i.create_time,
            'equipment_width_height': i.equipment_width_height,
            'equipment_constantBitRate': i.equipment_constantBitRate,
            'equipment_maxFrameRate': i.equipment_maxFrameRate,
            'Hik_indexCode': i.Hik_indexCode,
            'Ziguang_ape_rtsp_url': i.Ziguang_ape_rtsp_url,
            'Ziguang_ape_indexCode': i.Ziguang_ape_indexCode,
            'online': i.online,
            'alarm_device_ip' : i.alarm_device_ip
        } for i in equipment_info.items]

        equipment_list=add_rtsp_mp4_to_cameras(equipment_list)
        # 使用列表推导式筛选设备类型为“录像机”的记录
        equipment_VCR = [record for record in equipment_info.items
                         if record.equipment_type == '录像机' or record.equipment_type == '特殊摄像头'
                         or record.equipment_type == '安防平台' or record.equipment_type == '紫光华智'
                         or record.equipment_type == '视频中心存储'  or record.equipment_type == 'AI双光摄像头'
                         ]
        # 提取录像机的 ID
        vcr_ids = [record.id for record in equipment_VCR]

        equipment_list = children_data(equipment_list,vcr_ids)

        # 构建返回的 JSON
        response_data = {
            'total_items': equipment_info.total,
            'total_pages': equipment_info.pages,
            'current_page': equipment_info.page,
            'per_page': per_page,
            'data': equipment_list,
        }

        return jsonify({'code': 200, 'msg': '查询成功', 'data_list': response_data})

@model_view.route('/equipment_status', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_status():
    # '设备名称'
    equipmentInfo = db.session.query(Equipment.id, Equipment.equipment_ip, Equipment.online).all()
    resultList = convert_folder_to_dict_list(equipmentInfo, ['id', 'equipment_ip', 'online'])
    getDevRunStatus(resultList)
    for resultList_i in resultList:
        # 查询当前ip对应的设备是否存在
        equipment_result = db.session.query(Equipment).filter(
            Equipment.equipment_ip == resultList_i['equipment_ip']).first()
        print(equipment_result)
        if equipment_result is not None:
            equipment_result.online = resultList_i['online']
            # 提交会话以保存更改
        db.session.commit()
    print(resultList)
    return resultList


# 设备修改接口
@model_view.route('/equipment_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_update():
    # '设备id'
    equipment_name = request.form.get('equipment_name', None)

    # type 当type为1查询，当type为2修改
    type_s = request.form.get('type', None)

    params = [type_s, equipment_name]

    if not all(params):
        return jsonify({'code': 400, 'msg': '数据有未填写项'})

    # 查询操作
    if int(type_s) == 1:
        # 调用service层方法处理查询操作
        result = EquipmentService.equipment_update(type_s, equipment_name)
        return jsonify(result)

    # 修改操作
    else:
        # 构建设备数据
        equipment_data = {
            'id': request.form.get('id', None),
            'equipment_type': request.form.get('equipment_type', None),
            'manufacturer_type': request.form.get('manufacturer_type', None),
            'equipment_name': request.form.get('equipment_name', None),
            'equipment_ip': request.form.get('equipment_ip', None),
            'equipment_uname': request.form.get('equipment_uname', None),
            'equipment_password': request.form.get('equipment_password', None),
            'equipment_aisles': request.form.get('equipment_aisles', None),
            'equipment_codetype': request.form.get('equipment_codetype', None),
            'Mine_id': request.form.get('Mine_id', None),
            'flower_frames': request.form.get('flower_frames', None),
            'alarm_device_ip': request.form.get('alarm_device_ip', None),
        }

        # 调用service层方法处理修改操作
        result = EquipmentService.equipment_update(type_s, equipment_name, equipment_data)
        return jsonify(result)


# 设备删除接口
@model_view.route('/equipment_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_delete():
    # '设备id'
    equipment_id = request.json.get('equipment_id', None)
    print(equipment_id)

    # 调用service层方法处理设备删除操作
    result = EquipmentService.equipment_delete(equipment_id)
    return jsonify(result)

# 选择算法，返回算法对应检测类型
@model_view.route('/Algorithm_type_select', methods=['GET'])
def Algorithm_type_select():
    algorithm_library_id = request.args.get('id', None)
    result = get_algorithm_type_selection(algorithm_library_id)
    return jsonify(result)

def editor_dropdown_choices(params):
    from model.ai_camera import Algorithm_library_3588, Model_template_config_3588

    type_param = params.get('type')
    camera = type_param == '2'
    library = Algorithm_library_3588 if camera else Algorithm_library
    template = Model_template_config_3588 if camera else Model_template_config
    choice = EquipmentBrowser(db.session, Equipment, Mine, configs).choices(params)
    if camera:
        choice['equipment_list'] = [r for r in choice['equipment_list'] if r['equipment_type'] in _AI_CAMERA_TYPES]
    query = db.session.query(library.id, library.algorithm_name, library.algorithm_file_name,
                             library.algorithm_version, library.algorithm_type, library.algorithm_path,
                             library.algorithm_child, library.model_type_name, library.model_name,
                             library.analysis_type, library.template_small_name)
    rows = query.filter(library.algorithm_status == 1, library.algorithm_parent == 1,
                        library.algorithm_child.in_((1, 2))).order_by(library.id).all()
    basic, cascades = [], []
    for row in rows:
        item = dict(row._mapping)
        item['algorithm_name'] = extract_chinese(row.algorithm_name)
        child = str(item.pop('algorithm_child'))
        if child == '2':
            cascades.append(item)
        elif type_param != '1' or row.model_type_name == '基础检测类':
            basic.append(item)
    by_type = {}
    for row in db.session.query(template.id, template.model_name, template.model_type,
                                template.model_template_config_type_id).order_by(template.id).all():
        by_type.setdefault(row.model_template_config_type_id, []).append(dict(row._mapping))
    categories = [{'id': category.id, 'model_type_name': category.model_type_name,
                   'template_model_data_list': by_type.get(category.id, [])}
                  for category in list_model_template_types(type_param)]
    return {'code': 200, 'mine_list': choice['mine_list'], 'equipment_list': choice['equipment_list'],
            'algorithm_list': basic, 'algorithm_list_five': cascades,
            'model_type_template': categories, 'type_list': configs.type_status}


_AI_CAMERA_TYPES = ('AI单光摄像头', 'AI双光摄像头')


# 筛选返回接口
@model_view.route('/type_select', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def type_select():
    scope = request.args.get('scope')
    type_param = request.args.get('type')
    if scope == 'editor':
        return jsonify(editor_dropdown_choices(request.args))
    if scope == 'aicam_devices':
        query = db.session.query(Equipment.id, Equipment.equipment_name).filter(
            Equipment.parent_id.is_(None), Equipment.equipment_type.in_(_AI_CAMERA_TYPES))
        if request.args.get('mine_id'):
            query = query.filter(Equipment.Mine_id == request.args['mine_id'])
        rows = query.order_by(Equipment.id).all()
        return jsonify({'code': 200, 'equipment_list': [dict(row._mapping) for row in rows]})
    if scope == 'device_form':
        return jsonify({'code': 200,
                        'mine_list': [{'id': r.id, 'mine_name': r.mine_name} for r in list_mines_rows()],
                        'equipment_type': configs.equipment_type, 'manufacturer_type': configs.manufacturer_type,
                        'vcr_way': configs.vcr_way})
    if scope == 'diagnosis_types':
        rows = convert_folder_to_dict_list(list_diagnosis_type_rows(), ['id', 'name', 'prewarn', 'warn'])
        return jsonify({'code': 200, 'diagnosis_type_result': rows})
    if scope == 'alarm_statistics':
        choices = EquipmentBrowser(db.session, Equipment, Mine, configs).choices(request.args)
        return jsonify({'code': 200, 'equipment_list': choices['equipment_list'],
                        'mine_list': choices['mine_list'], 'type_list': configs.type_status,
                        'model_type_template': [{'id': r.id, 'model_type_name': r.model_type_name}
                                                for r in list_model_template_types(type_param)]})
    if scope == 'algorithm_tasks':
        return jsonify({
            'code': 200,
            'mine_list': [{'id': row.id, 'mine_name': row.mine_name} for row in list_mines_rows()],
            'algorithm_list': [{
                'id': row.id, 'algorithm_name': extract_chinese(row.algorithm_name),
            } for row in fetch_algorithm_library_basic(type_param)],
        })
    if scope in ('devices', 'alarm'):
        choices = EquipmentBrowser(db.session, Equipment, Mine, configs).choices(request.args)
        if scope == 'alarm':
            choices.update(
                algorithm_list=[
                    {
                        'id': row.id,
                        'algorithm_name': extract_chinese(row.algorithm_name),
                        'model_type_name': row.model_type_name,
                    }
                    for row in fetch_algorithm_library_basic()
                ],
                model_type_options=[
                    {'id': row.id, 'model_type_name': row.model_type_name}
                    for row in list_model_template_types()
                ],
                type_list=configs.type_status,
            )
        return jsonify(choices)
    params = {
        'mine_id': request.args.get('mine_id', None),
        'type': request.args.get('type', None),
    }
    result = type_select_service(params)
    return jsonify(result)

# 选取监控点图片返回接口
@model_view.route('/image_show', methods=['GET'])
def image_show():
    equipment_id = request.args.get('equipment_id', None)
    if request.args.get('thumbnail') == '1':
        return task_roi_thumbnail(equipment_id, request.args.get('stream_type'))
    img_type = request.args.get('type', 0)
    img_resolution = request.args.get('img_resolution', None)
    result = get_image_from_equipment(equipment_id, img_type, img_resolution, request.args.get('stream_type'))
    return jsonify(result)


@model_view.route('/algorithm_upload', methods=['POST'])
def algorithm_upload():
    """
    算法组包上传接口
"""
    uploaded_file = request.files.get('files')
    algorithm_status = request.form.get('algorithm_status')
    algorithm_ps = request.form.get('algorithm_ps')

    if not uploaded_file or not uploaded_file.filename.casefold().endswith('.zip'):
        return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})

    result = handle_algorithm_upload_group(uploaded_file, algorithm_status, algorithm_ps)
    return result


@model_view.route('/algorithm_upload_sub', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_upload_sub():
    """
    算法子包上传接口
    """
    uploaded_file = request.files.get('files')
    algorithm_status = request.form.get('algorithm_status')
    algorithm_ps = request.form.get('algorithm_ps')

    if not uploaded_file or not uploaded_file.filename.casefold().endswith('.zip'):
        return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})

    result = handle_algorithm_upload_single(uploaded_file, algorithm_status, algorithm_ps)
    return result


# 算法管理配置添加接口
@model_view.route('/algorithm_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_add():
    try:
        result = add_algorithm_config(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@model_view.route('/algorithm_add_models', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_add_models():
    try:
        result = add_algorithm_config_models(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@model_view.route('/algorithm_update_models', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_update_models():
    try:
        result = update_algorithm_config_models(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法管理配置校验名称接口
@model_view.route('/config_name_check', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def config_name_check():
    conf_name = request.json.get('conf_name', None)
    conf_data = db.session.query(Algorithm_config).filter(Algorithm_config.conf_name == conf_name).first()
    if conf_data:
        return jsonify({'code': 400, 'msg': '算法配置名称重复，请重新命名！'})
    else:
        return jsonify({'code': 200, 'msg': '配置名称可用'})


# 算法管理配置修改接口
@model_view.route('/algorithm_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_update():
    try:
        result = update_algorithm_config(request.form or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法模型运行状态接口
@model_view.route('/algorithm_status', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_status():
    try:
        result = algorithm_status_service()
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法配置数据返回接口--与单一详情
@model_view.route('/algorithm_data_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_show():
    try:
        runtime_ids = request.args.get('runtime_ids')
        if runtime_ids is not None:
            return jsonify(algorithm_task_runtime(runtime_ids))
        if request.args.get('count_only') == '1':
            result, status = people_count_editor(request.args.get('conf_id'), request.args.get('data_id'))
            return jsonify(result), status
        params = {
            'conf_id': request.args.get('conf_id'),
            'data_id': request.args.get('data_id'),
            'algorithm_name': request.args.get('algorithm_name'),
            'start_time': request.args.get('start_time'),
            'end_time': request.args.get('end_time'),
            'Mine_id': request.args.get('Mine_id'),
            'conf_name': request.args.get('conf_name'),
            'algorithm_library_id': request.args.get('algorithm_library_id'),
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = algorithm_data_show_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法配置历史记录数据返回接口单一详情
@model_view.route('/algorithm_history_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_history_show():
    history_id = request.args.get('history_id')
    if not history_id:
        return jsonify({'code': 400, 'msg': '无history_id'})
    try:
        result = algorithm_history_show_service(history_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法配置数据删除接口
@model_view.route('/algorithm_data_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_delete():
    try:
        id_payload = request.json.get('id', None)
        result = algorithm_data_delete_service(id_payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})


# 算法预警--------sqlalchemy--------分页结果展示接口
@model_view.route('/algorithm_result_sqlalchemy', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_result_sqlalchemy():
    try:
        params = {
            'id': request.args.get('id', None),
            'mine_id': request.args.get('mine_id', None),
            'equipment_id': request.args.get('equipment_id', None),
            'start_time': request.args.get('start_time'),
            'end_time': request.args.get('end_time'),
            'type': request.args.get('type', None),
            'algorithm_id': request.args.get('algorithm_id', None),
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = algorithm_result_sqlalchemy_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法预警--------sql自写分页--------结果展示接口
@model_view.route('/algorithm_result', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_result():
    try:
        params = {
            'id': request.args.get('id'),
            'start_time': request.args.get('start_time', None),
            'end_time': request.args.get('end_time', None),
            'type': request.args.get('type', None),
            'algorithm_id': request.args.get('algorithm_id', None),
            'Algorithm_config_id': request.args.get('Algorithm_config_id', None),
            'mine_id': request.args.get('mine_id', None),
            'equipment_id': request.args.get('equipment_id', None),
            'keyword': request.args.get('keyword', None),
            'template_id': request.args.get('template_id', None),
            'template_type_id': request.args.get('template_type_id', None),
            'approval_status': request.args.get('approval_status', None),
            'disposal_status': request.args.get('disposal_status', None),
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = algorithm_result_service(params)
        response = make_response(jsonify(result))
        response.set_cookie('my_cookie', 'cookie_value', samesite='None', secure=True)
        return response
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@model_view.route('/algorithm_result_manage', methods=['POST'])
@jwt_required_with_refresh
def algorithm_result_manage():
    try:
        payload = {
            'id': request.json.get('id', None),
            'approval_status': request.json.get('approval_status', None),
            'disposal_status': request.json.get('disposal_status', None),
            'approval_opinion': request.json.get('approval_opinion', None),
            'disposal_opinion': request.json.get('disposal_opinion', None),
            'disposal_time': request.json.get('disposal_time', None),
        }
        result = algorithm_result_manage_service(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'数据库操作失败: {str(e)}'})


#  每个监控点下算法各占比例
@model_view.route('/algorithm_ratio', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_ratio():
    try:
        params = {
            'mine_id': request.args.get('mine_id', None),
            'equipment_id': request.args.get('equipment_id', None),
            'template_type_id': request.args.get('template_type_id', None),
            'type': request.args.get('type', None),
            'start_time': request.args.get('start_time'),
            'end_time': request.args.get('end_time'),
        }
        result = algorithm_ratio_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 实时视频展示返回
@model_view.route('/video_show', methods=['POST', 'GET'])
# @jwt_required()
@jwt_required_with_refresh
def video_show():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=3, type=int)
        result = video_show_service(page, per_page)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法仓数据展示编写
@model_view.route('/algorithm_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data():
    try:
        params = {
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
            'algorithm_file_name': request.args.get('algorithm_file_name'),
            'algorithm_name': request.args.get('algorithm_name'),
            'algorithm_status': request.args.get('algorithm_status'),
            'algorithm_trade_type': request.args.get('algorithm_trade_type'),
        }
        result = algorithm_data_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法配置历史记录展示
@model_view.route('/algorithm_config_history', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_config_history():
    try:
        params = {
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
            'id': request.args.get('id'),
        }
        result = algorithm_config_history_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法仓状态修改
@model_view.route('/algorithm_data_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_update():
    try:
        params = {
            'id': request.form.get('id'),
            'status': request.form.get('status'),
        }
        result = algorithm_data_update_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 监控点算法配置运行状态
@model_view.route('/algorithm_conf_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_conf_update():
    try:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict) and payload.get('operation') == 'adjust_people_count':
            result, status = people_count_editor(payload.get('id'), correction=payload)
            return jsonify(result), status
        params = {
            'id': request.form.get('id'),
            'status': request.form.get('status'),
        }
        result = algorithm_conf_update_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@model_view.route('/algorithm_conf_batch_update', methods=['POST'])
@jwt_required_with_refresh
def algorithm_conf_batch_update():
    try:
        payload = request.get_json(silent=True) if request.is_json else None
        return jsonify(algorithm_conf_batch_update_service(payload))
    except Exception:
        return jsonify({'code': 500, 'msg': '批量状态更新失败，请刷新后重试'})


# 录像机设备同步接口######版本更新后#######
# @model_view.route('/VCR_data_sync', methods=['POST'])
# # @jwt_required()
# # @jwt_required_with_refresh
# def VCR_data_sync():
#     vcr_type = request.form.get('vcr_type')  # 厂商类型
#     vcr_way = request.form.get('vcr_way')  # 接入方式
#     vcr_name = request.form.get('vcr_name')  # 录像机名称
#     username = request.form.get('username')  # 录像机用户
#     password = request.form.get('password')  # 录像机密码
#     ip = request.form.get('ip')  # 录像机ip
#     port = request.form.get('port')  # 录像机端口
#     Mine_id = request.form.get('Mine_id')  # 矿id
#
#     # 调用service层方法处理录像机同步操作
#     result = EquipmentService.vcr_data_sync(vcr_type, vcr_way, vcr_name, username, password, ip, port, Mine_id)
#     return jsonify(result)
# 录像机设备同步接口######版本更新前#######
# 录像机设备同步接口
@model_view.route('/VCR_data_sync', methods=['POST'])
# @jwt_required()
# @jwt_required_with_refresh
def VCR_data_sync():

    vcr_type = request.form.get('vcr_type') # 厂商类型
    vcr_way = request.form.get('vcr_way')   # 接入方式
    vcr_name = request.form.get('vcr_name') # 录像机名称
    username = request.form.get('username') # 录像机用户
    password = request.form.get('password') # 录像机密码
    ip = request.form.get('ip') # 录像机ip
    port = request.form.get('port') #录像机端口
    Mine_id = request.form.get('Mine_id') # 矿id

    vcr_type = (configs.manufacturer_type[int(vcr_type)-1])['value'] if vcr_type else 1  # 厂商类型
    vcr_way = (configs.vcr_way[int(vcr_way)-1])['value'] if  vcr_way else 1  # 接入方式

    params = [vcr_type,vcr_way,vcr_name,username,password,port,Mine_id,ip]

    if not all(params):
        return jsonify({'code': 400, 'msg': '录像机同步有未填写项！'})


    # 先查询当前录像机是否存在，
    vcr_data = db.session.query(Equipment).filter(Equipment.equipment_ip == ip).first()
    # 如果存在则返回，录像机设备信息已经存在
    if vcr_data:
        return jsonify({'code':400,'msg':'录像机设备信息已经存在,同步失败！'})

    # 调用方法获取录像机同步数据  数据格式为 [{},{}]
    # vcr_data_info = VCR_data_info(username,password,ip,port)
    # print(username,password,ip,port,type(username),type(password),type(ip),type(port))
    # print(vcr_data_info,'错误错误')
    # # 当返回值为列表的时候说明参数错误，请求超时
    # if vcr_data_info == []:
    #     return jsonify({'code':400,'msg':'录像机设备信息不存在,请输入正确参数！'})

    # 返回值有值说明正确进行同步操作,

    # 写入录像机同步表
    # VCR_data_data = VCR_data(
    #     vcr_type = vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
    #     vcr_way = vcr_way if vcr_way  in ['私有SDK','Onvif','GB28181'] else None,
    #     vcr_name = vcr_name,
    #     vcr_ip = ip,
    #     vcr_username = username,
    #     vcr_password = password,
    #     vcr_port = port,
    #     Mine_id = Mine_id,
    #     # vcr_status = db.Column(db.String(50), comment='录像机同步状态 1 同步完成 2 同步未完成' )
    #     online = 1,
    #     type = 1
    # )
    # db.session.add(VCR_data_data)
    # db.session.commit()

    # 判断私有sdk接入
    if vcr_type == '海康' and  vcr_way == '私有SDK':
        try:
            vcr_data_info = hik_channels(username, password, ip, port, strict=True)
        except InventoryUnavailable as exc:
            return jsonify({'code': 400, 'msg': str(exc)})
        if not vcr_data_info:
            return jsonify({'code': 400, 'msg': '录像机通道目录为空，请确认录像机已添加通道且当前账号可查看'})
        VCR_data_data = VCR_data(
            vcr_type=vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
            vcr_way=vcr_way if vcr_way in ['私有SDK', 'Onvif', 'GB28181'] else None,
            vcr_name=vcr_name,
            vcr_ip=ip,
            vcr_username=username,
            vcr_password=password,
            vcr_port=port,
            Mine_id=Mine_id,
            # vcr_status = db.Column(db.String(50), comment='录像机同步状态 1 同步完成 2 同步未完成' )
            online=1,
            type=1
        )
        db.session.add(VCR_data_data)
        db.session.flush()
        equipment_data = Equipment(
            equipment_type='录像机',
            manufacturer_type='海康',
            equipment_name=vcr_name,
            equipment_ip=ip,
            equipment_uname=username,
            equipment_password=password,
            Mine_id=int(Mine_id) if Mine_id else None,
            online=1,
            VCR_data_id=VCR_data_data.id,
        )
        db.session.add(equipment_data)
        db.session.flush()
        # 获取对应子集数据的  默认通道 code 数据
        children_list = vcr_data_info
        new_channels = []

        for i in children_list:
            # 添加录像机子设备
            # 父类设备为 parent_id

            child_equipment_data = Equipment(
                equipment_type=equipment_data.equipment_type if equipment_data.equipment_type else None,
                manufacturer_type=equipment_data.manufacturer_type if equipment_data.manufacturer_type else None,
                equipment_name=i['name'] if i.get('name') else None,
                equipment_ip=i['ip_address'] if i.get('ip_address') is not None else None,
                equipment_uname=i.get('username') if i.get('username') else None,
                equipment_password=equipment_data.equipment_password if equipment_data.equipment_password else None,
                equipment_aisles=i.get('id') if i.get('id') else None,
                Mine_id=int(equipment_data.Mine_id) if equipment_data.Mine_id else None,
                parent_id=int(equipment_data.id) if equipment_data.id else None,
                code=str(i.get('id')) + '01',
                VCR_data_id = VCR_data_data.id,
                online=online_value(i['online']) if i.get('online') is not None else None,
                equipment_width_height=(
                    (i.get('videoResolutionWidth', '') + 'x' + i.get('videoResolutionHeight', ''))
                    if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                ),
                equipment_codetype=(
                    'H265' if i.get('videoCodecType') == 'H.265'
                    else 'H264' if i.get('videoCodecType') == 'H.264'
                    else None
                ),

                equipment_constantBitRate=i.get('constantBitRate', ''),
                equipment_maxFrameRate = i.get('maxFrameRate', '')

            )

            db.session.add(child_equipment_data)
            new_channels.append(child_equipment_data)
        VCR_data_data.vcr_status = 1
        db.session.commit()
        for channel in new_channels:
            try:
                create_zlk_data_for_equipment(channel)
            except Exception as exc:
                db.session.rollback()
                print('录像机通道转发未建立（{}）'.format(type(exc).__name__))
        return jsonify({'code': 200, 'msg': '录像机同步成功，已导入 {} 个通道'.format(len(new_channels))})
    elif vcr_type == '宇视' and  vcr_way == '私有SDK':
        print('宇视接入')
        # ----------同步的时候录像机父类设备写入----------
        # 添加录像机父设备
        ysvcr_data_info = YSVCR_data_info(username, password, ip, port)
        # 当返回值为列表的时候说明参数错误，请求超时
        if ysvcr_data_info == []:
            return jsonify({'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'})
        VCR_data_data = VCR_data(
            vcr_type=vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
            vcr_way=vcr_way if vcr_way in ['私有SDK', 'Onvif', 'GB28181'] else None,
            vcr_name=vcr_name,
            vcr_ip=ip,
            vcr_username=username,
            vcr_password=password,
            vcr_port=port,
            Mine_id=Mine_id,
            # vcr_status = db.Column(db.String(50), comment='录像机同步状态 1 同步完成 2 同步未完成' )
            online=1,
            type=1
        )
        db.session.add(VCR_data_data)
        db.session.commit()
        equipment_data = Equipment(
            equipment_type='录像机',
            manufacturer_type='宇视',
            equipment_name=vcr_name,
            equipment_ip=ip,
            equipment_uname=username,
            equipment_password=password,
            Mine_id=int(Mine_id) if Mine_id else None,
            online=1,
            VCR_data_id=VCR_data_data.id,
        )
        db.session.add(equipment_data)
        db.session.commit()
        # 获取对应子集数据的  默认通道 code 数据
        children_list = ysvcr_data_info

        for i in children_list:
            # 添加录像机子设备
            # 父类设备为 parent_id
            child_equipment_data = Equipment(
                equipment_type=equipment_data.equipment_type if equipment_data.equipment_type else None,
                # manufacturer_type=equipment_data.manufacturer_type if equipment_data.manufacturer_type else None,
                manufacturer_type=YSNVR_manufacturer_type.get(i.get('Manufacturer'), None) if i.get('Manufacturer') else None,
                equipment_name=i['name'] if i.get('name') else None,
                equipment_ip=i['ip_address'] if i.get('ip_address') is not None else None,
                equipment_uname=equipment_data.equipment_uname if equipment_data.equipment_uname else None,
                equipment_password=equipment_data.equipment_password if equipment_data.equipment_password else None,
                equipment_aisles=i.get('id') if i.get('id') else None,
                Mine_id=int(equipment_data.Mine_id) if equipment_data.Mine_id else None,
                parent_id=int(equipment_data.id) if equipment_data.id else None,
                code=str(i.get('id')) + '01',
                VCR_data_id = VCR_data_data.id,
                online = i.get('online'),
                equipment_width_height=(
                    (str(i.get('videoResolutionWidth', '')) + 'x' + str(i.get('videoResolutionHeight', '')))
                    if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                ),
                equipment_codetype=(
                    'H265' if i.get('videoCodecType') == 'H.265'
                    else 'H264' if i.get('videoCodecType') == 'H.264'
                    else i.get('videoCodecType') if i.get('videoCodecType') in ['MJPEG', 'H.264', 'H.265']
                    else None
                ),

                equipment_constantBitRate=i.get('constantBitRate', ''),
                equipment_maxFrameRate = i.get('maxFrameRate', '')

            )

            db.session.add(child_equipment_data)
            db.session.commit()
            # 为同步的摄像头创建流媒体数据
            create_zlk_data_for_equipment(child_equipment_data)

    elif vcr_type == '大华' and  vcr_way == 'Onvif':
        print('大华接入')
        # ----------同步的时候录像机父类设备写入----------
        # 添加录像机父设备
        dahua_data_info = Dahua_data_info(username, password, ip, port)
        print(dahua_data_info, '错误错误')
        # 当返回值为列表的时候说明参数错误，请求超时
        if dahua_data_info == []:
            return jsonify({'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'})
        VCR_data_data = VCR_data(
            vcr_type=vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
            vcr_way=vcr_way if vcr_way in ['私有SDK', 'Onvif', 'GB28181'] else None,
            vcr_name=vcr_name,
            vcr_ip=ip,
            vcr_username=username,
            vcr_password=password,
            vcr_port=port,
            Mine_id=Mine_id,
            # vcr_status = db.Column(db.String(50), comment='录像机同步状态 1 同步完成 2 同步未完成' )
            online=1,
            type=1
        )
        db.session.add(VCR_data_data)
        db.session.commit()
        equipment_data = Equipment(
            equipment_type='录像机',
            manufacturer_type='大华',
            equipment_name=vcr_name,
            equipment_ip=ip,
            equipment_uname=username,
            equipment_password=password,
            Mine_id=int(Mine_id) if Mine_id else None,
            online=1,
            VCR_data_id=VCR_data_data.id,
        )
        db.session.add(equipment_data)
        db.session.commit()
        # 获取对应子集数据的  默认通道 code 数据
        children_list = dahua_data_info

        for i in children_list:
            # 添加录像机子设备
            # 父类设备为 parent_id

            child_equipment_data = Equipment(
                equipment_type=equipment_data.equipment_type if equipment_data.equipment_type else None,
                manufacturer_type=equipment_data.manufacturer_type if equipment_data.manufacturer_type else None,
                equipment_name=i['name'] if i.get('name') else None,
                equipment_ip=i['ip_address'] if i.get('ip_address') is not None else None,
                equipment_uname=equipment_data.equipment_uname if equipment_data.equipment_uname else None,
                equipment_password=equipment_data.equipment_password if equipment_data.equipment_password else None,
                equipment_aisles=int(i.get('id'))+1 if i.get('id') is not None else None,
                Mine_id=int(equipment_data.Mine_id) if equipment_data.Mine_id else None,
                parent_id=int(equipment_data.id) if equipment_data.id else None,
                code=str(i.get('id')) + '01',
                VCR_data_id = VCR_data_data.id,
                online = 1,
                equipment_width_height=(
                    str(i.get('videoResolutionWidth', '')) + 'x' + str(i.get('videoResolutionHeight', ''))
                    if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                ),
                equipment_codetype=(
                    'H265' if i.get('videoCodecType') == 'H.265'
                    else 'H264' if i.get('videoCodecType') == 'H.264'
                    else None
                ),

                equipment_constantBitRate=i.get('constantBitRate', ''),
                equipment_maxFrameRate = i.get('maxFrameRate', ''),
                Onvif_rtsp_url = i.get('main_stream_uri', ''),
            )

            db.session.add(child_equipment_data)
            db.session.commit()
            # 为同步的摄像头创建流媒体数据
            create_zlk_data_for_equipment(child_equipment_data)
    else :
        return jsonify({'code': 400, 'msg': '录像机设备信息同步失败！'})


    VCR_data_data.vcr_status=1
    db.session.commit()

    return jsonify({'code':200,'msg':'录像机设备信息同步成功！'})


# CVR设备同步接口
@model_view.route('/CVR_data_sync', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def CVR_data_sync():
    vcr_type = request.form.get('vcr_type')  # 厂商类型
    vcr_way = request.form.get('vcr_way')  # 接入方式
    vcr_name = request.form.get('vcr_name')  # 录像机名称
    username = request.form.get('username')  # 录像机用户
    password = request.form.get('password')  # 录像机密码
    ip = request.form.get('ip')  # 录像机ip
    port = request.form.get('port')  # 录像机端口
    Mine_id = request.form.get('Mine_id')  # 矿id

    vcr_type = (configs.manufacturer_type[int(vcr_type) - 1])['value'] if vcr_type else 1  # 厂商类型
    vcr_way = (configs.vcr_way[int(vcr_way) - 1])['value'] if vcr_way else 1  # 接入方式

    # 调用service层方法处理CVR同步操作
    result = EquipmentService.cvr_data_sync(vcr_type, vcr_way, vcr_name, username, password, ip, port, Mine_id)
    return jsonify(result)


# 手动刷新录像机同步
@model_view.route('/manual_sync', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def manual_sync():
    result = EquipmentService.manual_sync()
    return jsonify(result)


# 录像机设备修改及详情接口
@model_view.route('/VCR_data_update', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def VCR_data_update():
    # 接受类型 当为1的时候为详情  2的时候为修改
    type_st = request.args.get('type_st')

    # 录像机id
    id = request.args.get('id')

    # 当为2的时候为修改
    if int(type_st) == 2:
        vcr_type = request.args.get('vcr_type')  # 厂商类型
        vcr_way = request.args.get('vcr_way')  # 接入方式
        vcr_name = request.args.get('vcr_name')  # 录像机名称
        username = request.args.get('username')  # 录像机用户
        password = request.args.get('password')  # 录像机密码
        ip = request.args.get('ip')  # 录像机ip
        port = request.args.get('port')  # 录像机端口
        Mine_id = request.args.get('Mine_id')  # 矿id
    else:
        vcr_type = None
        vcr_way = None
        vcr_name = None
        username = None
        password = None
        ip = None
        port = None
        Mine_id = None

    # 调用服务层处理
    result = EquipmentService.vcr_data_update(type_st, id, vcr_type, vcr_way, vcr_name, username, password, ip, port, Mine_id)

    return jsonify(result)


# 录像机设备展示接口 (1. 全部， 2.录像机信息及录像机下方子设备信息)
@model_view.route('/VCR_data_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def VCR_data_show():
    if request.args.get('scope') == 'status':
        if request.args.get('type_st') == '2':
            recorder_id = request.args.get('id', type=int)
            if not recorder_id or not 1 <= recorder_id <= 2147483647:
                return jsonify({'code': 400, 'msg': '录像机 ID 无效'})
            return _online_status_view(Equipment, (Equipment.VCR_data_id == recorder_id,
                                                  Equipment.parent_id.isnot(None)))
        return _online_status_view(VCR_data)
    # 1全部  2 查询录像机信息对应id录像机及子设备信息
    type_st = request.args.get('type_st', None)
    id = request.args.get('id', None)

    # 第几页
    page = request.args.get('page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=1000, type=int)
    # 1 录像机   2 CVR
    type = request.args.get('type', None)

    # 调用服务层处理
    result = EquipmentService.vcr_data_show(type_st, id, page, per_page, type)

    return jsonify(result)


# 录像机设备删除接口  （删除相关下方子设备-算法配置-算法结果）
@model_view.route('/VCR_data_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def VCR_data_delete():
    # 录像机id
    id = request.form.get('id', None)

    # 调用服务层处理
    result = EquipmentService.vcr_data_delete(id)

    return jsonify(result)


# 算法仓数据删除接口
@model_view.route('/algorithm_library_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_library_delete():
    try:
        payload = request.get_json(silent=True) or {}
        result = algorithm_library_delete_service(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})



# 字典类型表新增
@model_view.route('/dict_type_add', methods=['POST'])
@jwt_required()
def dict_type_add():
    try:
        params = {
            'type_name': request.form.get('type_name', None),
            'type_code': request.form.get('type_code', None),
            'description': request.form.get('description', None),
            'enable': request.form.get('enable', None),
        }
        result = dict_type_add_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 字典类型表修改
@model_view.route('/dict_type_update', methods=['POST'])
# @jwt_required()
def dict_type_update():
    try:
        params = {
            'id': request.form.get('id', None),
            'type_name': request.form.get('type_name', None),
            'type_code': request.form.get('type_code', None),
            'description': request.form.get('description', None),
            'enable': request.form.get('enable', None),
        }
        result = dict_type_update_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 字典类型表删除
@model_view.route('dict_type_del', methods=['POST'])
@jwt_required()
def dict_type_del():
    try:
        result = dict_type_del_service(request.form)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 字典类型表展示
@model_view.route('dict_type_show', methods=['GET'])
@jwt_required()
def dict_type_show():
    try:
        params = {
            'dict_name': request.args.get('dict_name'),
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = dict_type_show_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


#  字典数据表新增
@model_view.route('/dict_data_add', methods=['POST'])
@jwt_required()
def dict_data_add():
    try:
        params = {
            'data_label': request.form.get('data_label', None),
            'data_value': request.form.get('data_value', None),
            'type_code': request.form.get('type_code', None),
            'is_default': request.form.get('is_default', 0),
            'enable': request.form.get('enable', None),
            'remark': request.form.get('remark', None),
        }
        result = dict_data_add_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


#  字典数据表修改
@model_view.route('/dict_data_update', methods=['POST'])
@jwt_required()
def dict_data_update():
    try:
        params = {
            'id': request.form.get('id', None),
            'data_label': request.form.get('data_label', None),
            'data_value': request.form.get('data_value', None),
            'is_default': request.form.get('is_default', 0),
            'enable': request.form.get('enable', None),
            'remark': request.form.get('remark', None),
        }
        result = dict_data_update_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


#  字典数据表删除
@model_view.route('/dict_data_del', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def dict_data_del():
    try:
        params = {
            'id': request.form.get('id', None),
        }
        result = dict_data_del_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


#  字典数据表展示
@model_view.route('/dict_data_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def dict_data_show():
    try:
        params = {
            'type_code': request.args.get('type_code'),
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = dict_data_show_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 报警列表数据删除
@model_view.route('/alg_result_delete', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def alg_result_delete():
    try:
        params = {
            'id_list': request.args.get('id_list', None),
        }
        result = algorithm_result_delete_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})


# 煤矿信息管理配置接口
@model_view.route('/mine_insert', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def mine_insert():
    try:
        payload = {
            'mine_name': strip_whitespace(request.json.get('mine_name', None)),
            'mine_code': strip_whitespace(request.json.get('mine_code', None)),
        }
        result = mine_insert_service(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'煤矿信息添加失败: {str(e)}'})


# 煤矿信息管理删除接口
@model_view.route('/mine_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def mine_delete():
    try:
        payload = {
            'id': request.json.get('id', None),
        }
        result = mine_delete_service(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'煤矿信息删除失败: {str(e)}'})


# 煤矿信息管理修改接口
@model_view.route('/mine_update', methods=['POST'])  # ✅ 改为 POST 方法
# @jwt_required()
@jwt_required_with_refresh
def mine_update():
    try:
        payload = {
            'id': request.json.get('id', None),
            'mine_name': request.json.get('mine_name', None),
            'mine_code': request.json.get('mine_code', None),
        }
        result = mine_update_service(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 煤矿信息详情展示接口
@model_view.route('/mine_detail', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def mine_detail():
    try:
        params = {
            'id': request.args.get('id'),
        }
        result = mine_detail_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 煤矿信息管理展示接口
@model_view.route('/mine_show', methods=['GET'])
# @jwt_required()
def mine_show():
    try:
        params = {
            'page': request.args.get('page', default=1, type=int),
            'per_page': request.args.get('per_page', default=15, type=int),
        }
        result = mine_show_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 监控点设备搜素
@model_view.route('/equipment_info', methods=['GET'])
# @jwt_required()
def em_info():
    try:
        params = {
            'type': request.args.get('type'),
            'name': request.args.get('name'),
        }
        result = equipment_info_service(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})



@model_view.route('/version_show', methods=['GET'])
def version_show():
    try:
        result = version_show_service()
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response, 200 if result.get('code') == 200 else 503
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})

@model_view.route('/algo_result_pop', methods=['GET'])
def algo_result_pop():
    """
    算法结果弹窗接口
    逻辑已迁移至 service 层
    """
    # 获取前端传递的关闭指令参数
    close_signal = request.args.get('close_signal', None)

    try:
        # 调用业务逻辑层
        alarm_list = fetch_alarm_results(close_signal=close_signal)

        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': alarm_list
        })
    except Exception as e:
        # 建议添加全局异常捕获或日志记录
        return jsonify({
            'code': 500,
            'msg': f'服务器内部错误: {str(e)}',
            'data': []
        })

# native-camera-ip-endpoint-v1
@model_view.route('/sync_aicam_ip', methods=['POST'])
@jwt_required_with_refresh
def sync_aicam_ip():
    """Report the available IP maintenance action without changing devices."""
    count = db.session.query(Equipment.id).filter(
        Equipment.equipment_type.in_(('AI单光摄像头', 'AI双光摄像头'))).count()
    data = {'total': count, 'synced': 0}
    if count == 0:
        return jsonify({'code': 200, 'msg': '暂无AI摄像头需要同步', 'data': data})
    return jsonify({
        'code': 400,
        'msg': '当前版本未提供AI摄像头自动IP同步，请通过设备编辑维护IP。',
        'data': data})

# algorithm-first-routes-v1
from service.algorithm_first_backend import register_routes as _register_algorithm_first_routes
_register_algorithm_first_routes(model_view, jwt_required_with_refresh)
