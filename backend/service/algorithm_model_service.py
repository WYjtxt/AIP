# native-model-bootstrap-target-v1
# native-alarm-detail-analysis-v1
# native-model-input-contracts-v1
from service.model_input_contracts import upload_model_with_contract
from service.algorithm_config_safety import (literal_data, alarm_interval, model_roi,
    ConfigurationConflict, delete_library_records)
from service.resource_admission import guard as resource_admission_guard, batch_guard as resource_admission_batch_guard
from service.algorithm_package_validation import (AlgorithmPackageError, read_uploaded_zip,
    open_package_zip, inspect_algorithm_package, inspect_algorithm_group,
    require_matching_devices, require_server_package, require_camera_package,
    canonical_algorithm_zip, same_model_slot, package_upgrade_analysis_types,
    split_algorithm_filename_fields, FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME,
    LEGACY_PERSON_COUNT_NAME)
from service.algorithm_snapshot_service import capture_snapshot_with_recorder_fallback
from service.algorithm_snapshot_capture import capture_config_snapshot
from service.algorithm_stream_selection import prepare_stream_type, selected_snapshot_url, stream_options, snapshot_identity
from service.algorithm_stream_source import normalize_stream_type
from service.person_count_contract import normalize_count_config, normalize_count_models
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
from sqlalchemy import and_, case, func, update, select, text, cast, Integer, or_
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
from data.algorithm_model_data import  *
import config.configs as configs

def get_algorithm_type_selection(algorithm_library_id):
    """处理算法类型选择逻辑"""
    if not algorithm_library_id:
        return {'code': 400, 'msg': '缺少算法ID参数'}

    model_type_data, model_data, template_small_data, algorithm_data,algorithm_child_data= fetch_algorithm_type_data(algorithm_library_id)

    # 区域类型判断逻辑
    def func_area(data, data_small):
        if data in ('基础检测类', '智能衍生类', '数量统计类'):
            return '空区域'
        if data in ('深度适配类', '级联聚析类'):
            if data_small == '设备运行时人员入侵':
                return '检测区域'
            if data_small == '行车不行人':
                return '屏蔽区域'
        return '空区域'

    result = {
        'algorithm_data': algorithm_data,
        'model_type_data': model_type_data,
        'model_data': model_data,
        'template_small_data': template_small_data,
        'algorithm_child_data': algorithm_child_data,
        'show_status': func_area(model_type_data[0]['model_type_name'], template_small_data[0]['template_small_name']) if model_type_data and template_small_data else '空区域'
    }

    return {'code': 200, 'data': result}

def get_algorithm_type_selection_aicam(algorithm_library_id):
    """处理算法类型选择逻辑"""
    if not algorithm_library_id:
        return {'code': 400, 'msg': '缺少算法ID参数'}

    model_type_data, model_data, template_small_data, algorithm_data,algorithm_child_data= fetch_algorithm_type_data_aicam(algorithm_library_id)

    # 区域类型判断逻辑
    def func_area(data, data_small):
        if data in ('基础检测类', '智能衍生类', '数量统计类'):
            return '空区域'
        if data in ('深度适配类', '级联聚析类'):
            if data_small == '设备运行时人员入侵':
                return '检测区域'
            if data_small == '行车不行人':
                return '屏蔽区域'
        return '空区域'

    result = {
        'algorithm_data': algorithm_data,
        'model_type_data': model_type_data,
        'model_data': model_data,
        'template_small_data': template_small_data,
        'algorithm_child_data': algorithm_child_data,
        'show_status': func_area(model_type_data[0]['model_type_name'], template_small_data[0]['template_small_name']) if model_type_data and template_small_data else '空区域'
    }

    return {'code': 200, 'data': result}


def get_image_from_equipment(equipment_id, img_type, img_resolution, stream_type=None):
    """处理图像获取逻辑"""
    if not equipment_id:
        return {'code': 400, 'msg': '缺少设备ID参数'}

    equipment_data = fetch_equipment_image_data(equipment_id)
    if not equipment_data:
        return {'code': 400, 'msg': '设备不存在'}

    child_types = ('录像机', '视频中心存储', '特殊摄像头', 'AI双光摄像头')
    if equipment_data.equipment_type in child_types and not equipment_data.parent_id:
        return {'code': 400, 'msg': '请选择录像机下的摄像机通道'}

    try:
        choice = normalize_stream_type(stream_type)
        rtsp, mp4 = ((selected_snapshot_url(equipment_id, choice), None) if choice
                     else generate_rtsp_url(equipment_data))
        if choice and equipment_data.equipment_type in ('摄像头', '录像机'):
            bound = db.session.query(Zlk_data).join(
                Equipment, Equipment.zlk_dat_id == Zlk_data.id
            ).filter(Equipment.id == equipment_data.id).first()
            # Reuse only the registered relay for the exact selected profile.
            if (bound and str(bound.equipment_id) == str(equipment_data.id)
                    and bound.cameras_rtsp == rtsp and bound.zlk_rtsp):
                rtsp, mp4 = bound.zlk_rtsp, bound.zlk_mp4
    except ValueError as e:
        return {'code': 400, 'msg': str(e)}
    if not rtsp and not mp4 and equipment_data.equipment_type in child_types[1:]:
        # 有效子设备缺少流媒体关联时，使用同一设备的配置重新创建并绑定。
        from service.equipment_model_service import create_zlk_data_for_equipment
        selected = db.session.query(Equipment).filter(Equipment.id == equipment_data.id).first()
        if selected and not selected.zlk_dat_id:
            create_zlk_data_for_equipment(selected)
            rtsp, mp4 = generate_rtsp_url(equipment_data)
    if not rtsp and not mp4 and equipment_data.equipment_type != '录像机':
        return {'code': 400, 'msg': '所选摄像机通道无法获取视频流，请检查设备在线状态和码流配置'}
    try:
        snapshot_key = snapshot_identity(equipment_data.id, choice)
        # Explicit inputs always sample their native size, ignoring stale client/cache dimensions.
        result = capture_snapshot_with_recorder_fallback(
            equipment_data.id, choice, rtsp, mp4, snapshot_key,
            1 if choice else int(img_type), None if choice else img_resolution,
            capture_config_snapshot)
    except Exception:
        result = {'code': 400, 'msg': '无法获取到图像，请检查视频来源和连接状态'}

    if isinstance(result, dict):
        result['stream_type'] = choice
        if choice:
            result.pop('z', None)  # Legacy helper error diagnostics can contain a credentialed source URL.
    return result


def _verified_stream_source(selected):
    """Resolve only an approved same-IP/same-channel camera alias for capture."""
    if selected is None:
        return selected
    import configparser
    cfg = configparser.RawConfigParser()
    cfg.read('/data/AIGO/platform_start/backend/config.ini')
    value = cfg.get('VerifiedStreamSources', str(selected.id), fallback='')
    fields = [v.strip() for v in value.split(',')]
    if len(fields) != 3 or not fields[0].isdigit() or not fields[2].isdigit():
        return selected
    source_id, expected_ip, aisle = fields
    source = db.session.query(Equipment).filter(Equipment.id == int(source_id)).first()
    if (source and str(selected.equipment_ip) == expected_ip
            and str(source.equipment_ip) == expected_ip
            and str(selected.equipment_aisles) == aisle
            and str(source.equipment_aisles) == aisle and source.zlk_dat_id):
        return source
    return selected


def generate_rtsp_url(equipment_data):
    rtsp = ''
    mp4 = ''
    # 以所选设备ID读取既有绑定，避免同IP或相同通道编号误取其它设备。
    selected = db.session.query(Equipment).filter(Equipment.id == equipment_data.id).first()
    if equipment_data.equipment_type != '安防平台':
        selected = _verified_stream_source(selected)
    if (equipment_data.equipment_type in ('录像机', '视频中心存储', '特殊摄像头', 'AI双光摄像头')
            and selected and selected.zlk_dat_id):
        stream = db.session.query(Zlk_data).filter(Zlk_data.id == selected.zlk_dat_id).first()
        if stream and (stream.zlk_rtsp or stream.zlk_mp4):
            return stream.zlk_rtsp or '', stream.zlk_mp4 or ''
    # 判断摄像头类型获取rtsp流
    if equipment_data.equipment_type == '摄像头'or equipment_data.equipment_type == 'AI单光摄像头':
        rtsp_mp4_data = get_camera_rtsp(equipment_data.equipment_ip)
        if rtsp_mp4_data:
            rtsp = rtsp_mp4_data['rtsp']
            mp4 = rtsp_mp4_data['mp4']
        # rtsp = 'rtsp://{}:{}@{}'.format(equipment_data.equipment_uname, urllib.parse.quote(equipment_data.equipment_password), equipment_data.equipment_ip)
    elif equipment_data.equipment_type == '录像机':
        rtsp_mp4_data = get_children_rtsp(equipment_data.parent_id, equipment_data.code, 1,
                                          equipment_data.equipment_aisles)
        print(rtsp_mp4_data,equipment_data.code)
        if rtsp_mp4_data:
            rtsp = rtsp_mp4_data['rtsp']
            mp4 = rtsp_mp4_data['mp4']
    elif equipment_data.equipment_type == '视频中心存储':
        rtsp_mp4_data = get_children_rtsp(equipment_data.parent_id, equipment_data.code, 1)
        if rtsp_mp4_data:
            rtsp = rtsp_mp4_data['rtsp']
            mp4 = rtsp_mp4_data['mp4']
    elif equipment_data.equipment_type == '特殊摄像头':
        rtsp_mp4_data = get_children_rtsp(equipment_data.parent_id, equipment_data.code, 2)
        if rtsp_mp4_data:
            rtsp = rtsp_mp4_data['rtsp']
            mp4 = rtsp_mp4_data['mp4']
    elif equipment_data.equipment_type == 'AI双光摄像头':
        rtsp_mp4_data = get_children_rtsp(equipment_data.parent_id, equipment_data.code, 2)
        if rtsp_mp4_data:
            rtsp = rtsp_mp4_data['rtsp']
            mp4 = rtsp_mp4_data['mp4']
    elif equipment_data.equipment_type == '浙江双视热成像':
        rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(equipment_data.equipment_uname,
                                                      urllib.parse.quote(equipment_data.equipment_password),
                                                      equipment_data.equipment_ip)
    elif equipment_data.equipment_type == '安防平台':
        # native_hik_stream integration
        from service.algorithm_stream_selection import hik_snapshot_url
        rtsp = hik_snapshot_url(selected)
    elif equipment_data.equipment_type == '紫光华智':
        rtsp = equipment_data.Ziguang_ape_rtsp_url

    return rtsp,mp4

def _person_count_template(template_id):
    if not template_id:
        return None
    return db.session.query(Model_template_config).filter(Model_template_config.id == template_id).first()


@resource_admission_guard('create')
def add_algorithm_config(payload):
    try:
        payload = normalize_count_config(payload, _person_count_template)
        conf_name = payload.get('conf_name')
        Algorithm_library_id = payload.get('Algorithm_library_id')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id')
        stream_type = prepare_stream_type(payload, Equipment_id)
        conf_area = payload.get('conf_area')
        status = payload.get('status')
        test_type_id = payload.get('test_type_id')
        shield_status = payload.get('shield_status')
        tem_conf_area = payload.get('tem_conf_area')
        tem_frames = payload.get('tem_frames')
        confidence = payload.get('confidence')
        draw_type = payload.get('draw_type')
        interval_time = alarm_interval(payload.get('interval_time'))
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
        #人员计数进出人数
        Entering_num = payload.get('Entering_num')
        Exiting_num = payload.get('Exiting_num')
        all_Entering_num = payload.get('all_Entering_num')
        all_Exiting_num = payload.get('all_Exiting_num')
        cross_line_area = payload.get('cross_line_area')
        base_params = [conf_name, Algorithm_library_id, Mine_id, Equipment_id, test_type_id, resource_id,
                       model_template_config_id, computing_id, model_template_type_id]
        if not all(base_params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        if get_algorithm_config_by_name(conf_name):
            return {'code': 404, 'msg': '算法配置名称重复，请重新命名！'}

        if get_algorithm_config_by_equipment_and_library(Equipment_id, Algorithm_library_id):
            return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}

        if not get_algorithm_library_by_id(Algorithm_library_id):
            return {'code': 400, 'msg': '算法库id不存在'}

        _ = get_mine_by_id(Mine_id)

        resresource_data = get_resource_usage_by_id(resource_id)
        if resresource_data:
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
                'stream_type': stream_type,
                'run_time': run_time,
                # 人员计数进出人数
                'Entering_num': Entering_num,
                'Exiting_num': Exiting_num,
                'all_Entering_num': all_Entering_num,
                'all_Exiting_num': all_Exiting_num,
                'cross_line_area':cross_line_area
            }
            config_obj = insert_algorithm_config(fields)
            insert_algorithm_config_history_from_config(config_obj, '添加')

        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except ValueError as e:
        db.session.rollback()
        return {'code': 400, 'msg': str(e)}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def _editor_selected_options(detail, serialized):
    library_id = serialized['Algorithm_library_id']
    if library_id == detail.Algorithm_library_id:
        algorithm = {'id': library_id, 'algorithm_name': serialized['algorithm_name'],
                     'algorithm_version': detail.algorithm_version}
    else:
        current = editor_algorithm_identity(library_id) if library_id else None
        algorithm = {'id': current.id, 'algorithm_name': extract_chinese(current.algorithm_name),
                     'algorithm_version': current.algorithm_version} if current else None
    return {
        'mine': {'id': detail.Mine_id, 'mine_name': detail.mine_name},
        'equipment_path': editor_equipment_path(detail.Equipment_id, detail.equipment_name,
                                                detail.equipment_type, detail.editor_equipment_parent_id, detail.Mine_id),
        'algorithm': algorithm,
        'alarm_level': next((dict(option) for option in configs.type_status
                             if str(option['id']) == str(serialized['res_type'])), None),
    }


def algorithm_data_show_service(params):
    try:
        r = Redis(Redis_ip, Redis_port, 'list')
        conf_id = params.get('conf_id')
        data_id = params.get('data_id')
        if conf_id:
            algorithm_res = fetch_algorithm_config_detail(conf_id)
            if algorithm_res:
                snapshot = ''
                if algorithm_res.Equipment_id:
                    identity = snapshot_identity(algorithm_res.Equipment_id, getattr(algorithm_res, 'stream_type', None))
                    snapshot = r.get_string('em_{}'.format(identity))
                preview = '/static/' + str(os.path.basename(snapshot)) if snapshot else ''
                if data_id == '0' or data_id is None:
                    algorithm_data = {
                        'id': algorithm_res.id,
                        'image': preview,
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
                        'stream_type': getattr(algorithm_res, 'stream_type', None),
                        'resource_id': algorithm_res.resource_id if algorithm_res.resource_id else 0,
                        'defense_time_start': algorithm_res.defense_time_start if algorithm_res.defense_time_start else '',
                        'defense_time_end': algorithm_res.defense_time_end if algorithm_res.defense_time_end else '',
                        'model_template_config_id': algorithm_res.model_template_config_id if algorithm_res.model_template_config_id else '',
                        'template_list_area': algorithm_res.template_list_area if algorithm_res.template_list_area else '',
                        'image_count': algorithm_res.image_count if algorithm_res.image_count else '',
                        'template_small_id': algorithm_res.template_small_id if algorithm_res.template_small_id else '',
                        'count_time': algorithm_res.count_time if algorithm_res.count_time else 0,
                        'res_type': algorithm_res.res_type if algorithm_res.res_type else 1,
                        'template_data': literal_data(algorithm_res.template_data) if algorithm_res.template_data else '',
                        'label_list': literal_data(algorithm_res.label_list) if algorithm_res.label_list else [],
                        'amp': algorithm_res.amp,
                        'alg_select_type': algorithm_res.alg_select_type,
                        'model_two_data': json.loads(algorithm_res.model_two_data),
                        'model_two_type': algorithm_res.model_two_type,
                        'priority': algorithm_res.priority,
                        'run_time': algorithm_res.run_time,
                        'multimodels_type': algorithm_res.multimodels_type,
                        'Entering_num': algorithm_res.Entering_num,
                        'Exiting_num': algorithm_res.Exiting_num,
                        'all_Entering_num': algorithm_res.all_Entering_num,
                        'all_Exiting_num': algorithm_res.all_Exiting_num,
                        'cross_line_area': algorithm_res.cross_line_area,
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
                        'image': preview,
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
                        'stream_type': getattr(algorithm_res, 'stream_type', None),
                        'resource_id': data_resouce.get('resource_id', 0),
                        'defense_time_start': data_resouce.get('defense_time_start', ''),
                        'defense_time_end': data_resouce.get('defense_time_end', ''),
                        'model_template_config_id': data_resouce.get('model_template_config_id', ''),
                        'template_list_area': data_resouce.get('template_list_area', ''),
                        'image_count': data_resouce.get('image_count', ''),
                        'template_small_id': data_resouce.get('template_small_id', ''),
                        'count_time': algorithm_res.count_time,
                        'res_type': data_resouce.get('res_type', 1),
                        'label_list': literal_data(data_resouce.get('label_list', '[]')),
                        'amp': data_resouce.get('amp', ''),
                        'alg_select_type': data_resouce.get('alg_select_type', ''),
                        'model_two_data': data_resouce.get('model_two_data', '[]'),
                        'model_two_type': data_resouce.get('model_two_type', ''),
                        'priority': data_resouce.get('priority', ''),
                        'run_time': data_resouce.get('run_time', ''),
                        'multimodels_type': algorithm_res.multimodels_type,
                        'Entering_num': algorithm_res.Entering_num,
                        'Exiting_num': algorithm_res.Exiting_num,
                        'all_Entering_num': algorithm_res.all_Entering_num,
                        'all_Exiting_num': algorithm_res.all_Exiting_num,
                        'cross_line_area': data_resouce.get('cross_line_area', ''),
                    }
                algorithm_data['editor_selected_options'] = _editor_selected_options(algorithm_res, algorithm_data)
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
                filters.append(Algorithm_config.Mine_id == Mine_id)
            if conf_name:
                filters.append(Algorithm_config.conf_name.ilike(f"%{conf_name}%"))
            if algorithm_name:
                filters.append(Algorithm_library.algorithm_name == algorithm_name)
            if start_time and end_time:
                filters.append(Algorithm_config.conf_time.between(time_to_gmt_format(start_time), time_to_gmt_format(end_time)))
            if len(filters) >= 2:
                query_filter = and_(*filters)
            else:
                query_filter = filters[0] if filters else None
            # SQLAlchemy expressions must never be converted to bool.
            algorithm_res = fetch_algorithm_configs(query_filter)
            algorithm_data = []
            filtered_items = []
            if algorithm_library_id:
                target_alg_id = int(algorithm_library_id)
                for item in algorithm_res:
                    if str(item.Algorithm_library_id) == str(target_alg_id):
                        filtered_items.append(item)
                        continue
                    if item.model_algo_data_ori:
                        try:
                            model_algo_data = literal_data(item.model_algo_data_ori)
                            if isinstance(model_algo_data, list):
                                for model_item in model_algo_data:
                                    if isinstance(model_item, dict) and str(model_item.get('Algorithm_library_id')) == str(target_alg_id):
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
                    'image': ('/static/' + str(os.path.basename(r.get_string('em_{}'.format(snapshot_identity(i.Equipment_id, getattr(i, 'stream_type', None))))))) if i.Equipment_id and r.get_string('em_{}'.format(snapshot_identity(i.Equipment_id, getattr(i, 'stream_type', None)))) else '',
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
                    'stream_type': getattr(i, 'stream_type', None),
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
                    'template_data': literal_data(i.template_data) if i.template_data else '',
                    'label_list': literal_data(i.label_list) if i.label_list else [],
                    'amp': i.amp,
                    'alg_select_type': i.alg_select_type,
                    'model_two_data': json.loads(i.model_two_data),
                    'model_two_type': i.model_two_type,
                    'priority': i.priority,
                    'run_time': i.run_time,
                    'multimodels_type': i.multimodels_type,
                    'Entering_num': i.Entering_num,
                    'Exiting_num': i.Exiting_num,
                    'all_Entering_num': i.all_Entering_num,
                    'all_Exiting_num': i.all_Exiting_num,
                    'cross_line_area': i.cross_line_area if i.cross_line_area else '',
                }
                if i.multimodels_type == 1:
                    try:
                        model_algo_data_ori = literal_data(i.model_algo_data_ori) if i.model_algo_data_ori else []
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
                                'template_data': literal_data(i.template_data) if i.template_data else [],
                                'test_type_id': i.test_type_id if i.test_type_id else '',
                                'label_list': literal_data(i.label_list) if i.label_list else [],
                                'amp': i.amp if i.amp else '',
                                'alg_select_type': i.alg_select_type if i.alg_select_type else '',
                                'model_two_data': json.loads(i.model_two_data) if i.model_two_data else [],
                                'model_two_type': i.model_two_type if i.model_two_type else '',
                                'res_type': i.res_type if i.res_type else '',
                                'model_template_config_id': i.model_template_config_id if i.model_template_config_id else '',
                                'template_small_id': i.template_small_id if i.template_small_id else '',
                                'stream_type': getattr(i, 'stream_type', None),
                    'resource_id': i.resource_id if i.resource_id else '',
                                'model_template_type_id': i.model_template_type_id if i.model_template_type_id else '',
                                'computing_id': i.computing_id if i.computing_id else '',
                                'cross_line_area': i.cross_line_area if i.cross_line_area else ''
                            }
                            merged_data = {
                                'Mine_id': i.Mine_id,
                                'conf_name': i.conf_name,
                                'equipment_name': i.Equipment_id,
                                'model_data': [first_model_data]
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

def algorithm_history_show_service(history_id):
    try:
        if not history_id:
            return {'code': 400, 'msg': '无history_id'}
        r = Redis(Redis_ip, Redis_port, 'list')
        res = fetch_algorithm_history_detail(history_id)
        if not res:
            return {'code': 400, 'datalist': [], 'msg': '未有该配置的详情信息'}
        data = {
            'id': res.id,
            'image': ('/static/' + str(os.path.basename(r.get_string('em_{}'.format(res.Equipment_id))))
                      if res.Equipment_id and r.get_string('em_{}'.format(res.Equipment_id)) else ''),
            'Algorithm_library_id': res.Algorithm_library_id,
            'algorithm_name': res.algorithm_name,
            'Mine_id': res.Mine_id,
            'mine_name': res.mine_name,
            'Equipment_id': res.Equipment_id,
            'equipment_name': res.equipment_name,
            'equipment_type': res.equipment_type,
            'equipment_code': res.code,
            'conf_name': res.conf_name if res.conf_name else '',
            'conf_object': res.conf_object if res.conf_object else '',
            'conf_time': (res.conf_time).strftime("%Y-%m-%d %H:%M:%S"),
            'conf_area': res.conf_area if res.conf_area else '',
            'test_type_id': res.test_type_id if res.test_type_id else '',
            'status': configs.status[int(res.status) - 1]['value'],
            'shield_status,': res.shield_status,
            'tem_conf_area': res.tem_conf_area,
            'tem_frames': res.tem_frames,
            'draw_type': res.draw_type,
            'confidence': res.confidence,
            'interval_time': res.interval_time,
            'img_resolution': res.conf_img_resolution,
            'duration_time': res.duration_time,
            'image_draw_type': res.image_draw_type,
            'update_time': (res.update_time).strftime("%Y-%m-%d %H:%M:%S") if res.update_time else '',
            'Algorithm_config_ps': res.Algorithm_config_ps,
            'operation_type': res.operation_type,
            'scene_typename': res.scene_typename if res.scene_typename else '',
            'sensitivity': res.sensitivity if res.sensitivity else 0,
            'defense_time_start': res.defense_time_start if res.defense_time_start else '',
            'defense_time_end': res.defense_time_end if res.defense_time_end else '',
            'model_template_config_id': res.model_template_config_id if res.model_template_config_id else '',
            'template_list_area': res.template_list_area if res.template_list_area else '',
            'image_count': res.image_count if res.image_count else '',
            'template_small_id': res.template_small_id if res.template_small_id else '',
            'count_time': res.count_time if res.count_time else 0,
            'res_type': res.res_type if res.res_type else 1,
        }
        return {'code': 200, 'datalist': data, 'msg': '查询成功'}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_data_delete_service(id_payload):
    try:
        id_list = id_payload if isinstance(id_payload, list) else None
        if not id_list:
            return {'code': 400, 'msg': '缺少设备id参数'}
        ids = [item['id'] for item in id_list]
        configs_to_delete = fetch_algorithm_configs_by_ids(ids)
        if not configs_to_delete:
            return {'code': 404, 'msg': '未找到相关配置'}
        for conf in configs_to_delete:
            insert_algorithm_config_history_from_config(conf, '删除')
        delete_algorithm_configs_by_ids(ids)
        return {'code': 200, 'msg': '删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'删除失败: {str(e)}'}

def _full_body_library_ids():
    rows = db.session.query(Algorithm_library.id).filter(
        Algorithm_library.analysis_type == FULL_BODY_COUNT_NAME).all()
    return {row[0] for row in rows}


def _result_algorithm_name(row, full_body_ids):
    if row.template_type_id == 3 and row.Algorithm_library_id in full_body_ids:
        return FULL_BODY_COUNT_NAME
    return row.algorithm_name


def algorithm_result_service(params):
    try:
        id = params.get('id')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        type_sta = params.get('type')
        algorithm_id = params.get('algorithm_id')
        conf_id = params.get('Algorithm_config_id')
        mine_id = params.get('mine_id')
        equipment_id = params.get('equipment_id')
        keyword = params.get('keyword')
        template_id = params.get('template_id')
        template_type_id = params.get('template_type_id')
        approval_status = params.get('approval_status')
        disposal_status = params.get('disposal_status')
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        filters = []
        if not end_time:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if start_time and end_time:
            filters.append(Algorithm_result.res_time.between(time_to_gmt_format(start_time), time_to_gmt_format(end_time)))
        if type_sta:
            filters.append(Algorithm_result.res_type == type_sta)
        if conf_id:
            filters.append(Algorithm_result.Algorithm_config_id == conf_id)
        if algorithm_id:
            library = db.session.query(Algorithm_library).filter(Algorithm_library.id == algorithm_id).first()
            if library is None:
                filters.append(Algorithm_result.id < 0)
            else:
                # The installed package ID is authoritative. Legacy rows without
                # an ID can match a real name, never a shared placeholder like 00.
                names = {library.algorithm_name, library.model_name, library.analysis_type}
                names = [name for name in names if name and not str(name).isdigit()]
                filters.append(or_(Algorithm_result.Algorithm_library_id == library.id,
                    and_(Algorithm_result.Algorithm_library_id.is_(None),
                         Algorithm_result.algorithm_name.in_(names))))
        if mine_id:
            filters.append(Algorithm_result.Mine_id == mine_id)
        if id:
            filters.append(Algorithm_result.id == id)
        if template_id:
            filters.append(Algorithm_result.template_id == template_id)
        if template_type_id:
            filters.append(Algorithm_result.template_type_id == template_type_id)
        else:
            filters.append(Algorithm_result.template_type_id != 3)
        if approval_status not in (None, ""):
            filters.append(Algorithm_result.approval_status == approval_status)
        if disposal_status not in (None, ""):
            filters.append(Algorithm_result.disposal_status == disposal_status)
        if equipment_id:
            parent = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            children = db.session.query(Equipment).filter(Equipment.parent_id == parent.id).first()
            if not children:
                equipment_name = db.session.query(Equipment.equipment_name).filter(Equipment.id == equipment_id).first()
                filters.append(Algorithm_result.equipment_name == equipment_name[0])
                # filters.append(Algorithm_result.Equipment_id == equipment_id)

            # 如果有子类数据取录像机下边子类数据
            else:
                filters.append(Algorithm_result.Equipment_parent_id == equipment_id)
        if keyword:
            like_pattern = '%{}%'.format(keyword)
            filters.append(or_(Algorithm_result.equipment_name.like(like_pattern),
                               Algorithm_result.mine_name.like(like_pattern),
                               Algorithm_result.conf_name.like(like_pattern),
                               Algorithm_result.algorithm_name.like(like_pattern),
                               Algorithm_result.warning_message.like(like_pattern)))
        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else True

        total_count = fetch_algorithm_result_total_count(query_filter)
        equipment_types = fetch_equipment_types_distinct()
        algorithm_info = fetch_algorithm_result_page(query_filter, per_page, page)
        algorithm_data = []
        full_body_ids = _full_body_library_ids() if algorithm_info else set()
        for i in algorithm_info:
            display_algorithm_name = _result_algorithm_name(i, full_body_ids)
            # 处理uwb_id，从['51fe0800', '4dfe0800']格式中提取名称
            uwb_names = []
            if i.uwb_id:
                try:
                    # 将字符串格式的列表转换为实际列表
                    uwb_id_list = ast.literal_eval(i.uwb_id) if isinstance(i.uwb_id, str) and i.uwb_id.startswith(
                        '[') else [i.uwb_id]
                    if isinstance(uwb_id_list, list):
                        # 查询每个uwb_id对应的名称
                        for uid in uwb_id_list:
                            uwb_record = db.session.query(Uwb_data.uwb_name).filter(Uwb_data.uwb_id == uid).first()
                            if uwb_record:
                                uwb_names.append(uwb_record.uwb_name)
                            else:
                                uwb_names.append(uid)  # 如果找不到名称，使用原始ID
                    else:
                        # 单个uwb_id的情况
                        uwb_record = db.session.query(Uwb_data.uwb_name).filter(Uwb_data.uwb_id == i.uwb_id).first()
                        if uwb_record:
                            uwb_names.append(uwb_record.uwb_name)
                        else:
                            uwb_names.append(i.uwb_id)
                except:
                    # 解析失败时，使用原始值
                    uwb_names = [i.uwb_id] if i.uwb_id else []

            # 格式化数据
            algorithm_data.append({
                'Algorithm_result_id': i.Algorithm_result_id,
                'res_time': i.res_time.strftime("%Y-%m-%d %H:%M:%S") if i.res_time else None,
                'Mine_id': i.Mine_id,
                'mine_name': i.mine_name,
                'Equipment_id': i.Equipment_id,
                'equipment_name': i.equipment_name,
                'equipment_type': i.equipment_type,
                'conf_id': i.Algorithm_config_id,
                'conf_name': display_algorithm_name,
                # 'conf_name': extract_chinese(i.algorithm_name),
                'res_type': configs.type_status[int(i.res_type) - 1]['value'] if i.res_type else None,
                'res_image': i.res_image,
                'res_video': i.res_video,
                'warning_video': i.warning_video,
                'res_frame_skip': i.res_frame_skip,
                'ori_images_list': str([url.replace('#', '%23') for url in ast.literal_eval(i.ori_images_list)]),
                'carousel_images_list': str([url.replace('#', '%23') for url in ast.literal_eval(
                    i.carousel_images_list)]) if i.carousel_images_list else None,
                # 'carousel_images_list': i.carousel_images_list,
                'result_count': i.result_count,
                'result_count_time': i.result_count_time.strftime("%Y-%m-%d %H:%M:%S") if i.result_count_time else None,
                # 'algorithm_name': extract_chinese(i.algorithm_name),
                'algorithm_name': display_algorithm_name,
                'model_name': i.model_name,
                'model_type': i.model_type,
                'model_type_name': i.model_type_name,
                'model_type_id': i.model_type_id,
                'img_resolution': i.conf_img_resolution,
                'Entering_num': i.Entering_num,
                'Exiting_num': i.Exiting_num,
                'approval_status': i.approval_status,
                'disposal_status': i.disposal_status,
                'approval_opinion': i.approval_opinion,
                'disposal_opinion': i.disposal_opinion,
                'disposal_time': i.disposal_time.strftime("%Y-%m-%d %H:%M:%S") if i.disposal_time else None,
                'uwb_id': ', '.join(uwb_names) if uwb_names else None,
                # 'uwb_name': ', '.join(uwb_names) if uwb_names else None
                'warning_message':i.warning_message if i.warning_message else None,

            })
        # print(algorithm_data, )
        # 构造响应数据
        response_data = {
            'total_items': total_count,
            'total_pages': total_count // per_page + (1 if total_count % per_page > 0 else 0),
            'current_page': page,
            'per_page': per_page,
            'data': algorithm_data,
            'equipment_types': equipment_types
        }
        return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_status_service():
    try:
        equipment_algorithm_list = fetch_equipment_algorithm_status_list()
        equipment_algorithm_dict_list = convert_folder_to_dict_list(
            equipment_algorithm_list,
            ['Equipment_id', 'status', 'equipment_ip', 'online', 'algorithm_status', 'id']
        )
        for item in equipment_algorithm_dict_list:
            if item['status'] == '1' and item['online'] == 1:
                update_algorithm_status_by_id(item['id'], 1)
                item['algorithm_status'] = 1
            else:
                update_algorithm_status_by_id(item['id'], 2)
                item['algorithm_status'] = 2
        return equipment_algorithm_dict_list
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_result_manage_service(payload):
    try:
        id = payload.get('id')
        if not id:
            return {'code': 400, 'msg': '缺少必要参数：id'}
        algorithm_result = get_algorithm_result_by_id(id)
        if not algorithm_result:
            return {'code': 400, 'msg': '未找到对应的算法结果记录'}
        update_fields = {
            'approval_status': payload.get('approval_status', None),
            'disposal_status': payload.get('disposal_status', None),
            'approval_opinion': payload.get('approval_opinion', None),
            'disposal_opinion': payload.get('disposal_opinion', None),
            'disposal_time': payload.get('disposal_time', None),
        }
        update_algorithm_result_fields(id, update_fields)
        return {'code': 200, 'msg': '算法结果记录更新成功'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'数据库操作失败: {str(e)}'}

def algorithm_ratio_service(params):
    mine_id = params.get('mine_id')
    equipment_id = params.get('equipment_id')
    template_type_id = params.get('template_type_id')
    type_sta = params.get('type')
    start_time = params.get('start_time')
    end_time = params.get('end_time')
    filters = []
    # 如果存在算法名称参数，将其加入过滤条件
    if mine_id:
        filters.append(Algorithm_config.Mine_id == mine_id)

    if equipment_id:
        print('摄像头id')

        # 判断 如果是父类 取父类下边数据
        parent_id = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
        # 查找父类下边是否有 子类数据
        children = db.session.query(Equipment).filter(Equipment.parent_id == parent_id.id).first()
        # 如果没有子类数据取摄像头
        if not children:
            filters.append(Equipment.id == equipment_id)

        # 如果有子类数据取录像机下边子类数据
        else:
            filters.append(Equipment.parent_id == equipment_id)

    # 如果存在开始时间和结束时间参数，加入过滤条件
    if start_time and end_time:
        # 查询在开始时间跟结束时间之内
        filters.append(
            Algorithm_result.res_time.between(time_to_gmt_format(start_time), time_to_gmt_format(end_time)))
    # 报警状态
    if type_sta:
        filters.append(Algorithm_result.res_type == type_sta)
    # 模版大类筛选
    if template_type_id:
        filters.append(Algorithm_result.template_type_id == template_type_id)
    else:
        filters.append(Algorithm_result.template_type_id != 3)
    # 如果有两个条件，使用 and 连接；如果只有一个条件，不使用 and

    query_filter = and_(*filters) if len(filters) >= 2 else (filters[0] if filters else None)

    display_algorithm_name = Algorithm_result.algorithm_name
    full_body_ids = _full_body_library_ids()
    if full_body_ids:
        is_full_body = and_(Algorithm_result.template_type_id == 3,
                            Algorithm_result.Algorithm_library_id.in_(full_body_ids))
        display_algorithm_name = case((is_full_body, FULL_BODY_COUNT_NAME), else_=display_algorithm_name)
    base_query = db.session.query(
        display_algorithm_name.label('algorithm_name'),
        func.count(Algorithm_result.id).label('cnt')
    )

    # 如果有过滤条件，应用过滤条件
    if query_filter is not None:
        base_query = base_query.filter(query_filter)

    # 按算法名称分组统计
    stat_list = base_query.group_by(display_algorithm_name).all()

    # 生成前端饼图数据（过滤空的算法名称）
    algorithm_data = []
    for row in stat_list:
        try:
            algo_name = row.algorithm_name
            chinese_name = new_extract_chinese(algo_name)
            if not algo_name:  # 过滤空算法名称
                continue
            algorithm_data.append({
                'name': chinese_name,
                'value': row.cnt,
            })
        except Exception as e:
            # 捕获单个数据的异常，打印日志并继续处理下一个
            print(f"处理算法数据失败，行数据：{row}，异常：{str(e)}")
            continue

    return {'code': 200, 'msg': '查询成功', 'data_list': algorithm_data}

def new_extract_chinese(text):
    """
    按下划线分割，有下划线则取第二个元素，无下划线返回原字符串
    适配：纯中文（无下划线）/xxx_中文（有下划线）场景
    """
    if not text:  # 处理空字符串/None的边界情况
        return ""
    if text in (FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME):
        return text
    parts = split_algorithm_filename_fields(text)
    # 分割后元素数量>=2，取第二个；否则返回原字符串（避免索引越界）
    return parts[1] if len(parts) >= 2 else text

def video_show_service(page, per_page):
    try:
        equipment_info = fetch_video_show_equipments(page, per_page)
        equipment_data = []
        for i in equipment_info.items:
            rtsp = ''
            if i.equipment_type == '摄像头':
                rtsp = 'rtsp://{}:{}@{}'.format(i.equipment_uname, i.equipment_password, i.equipment_ip)
            elif i.equipment_type == '录像机':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1, None)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
            elif i.equipment_type == '视频中心存储':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1, None)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
            elif i.equipment_type == '特殊摄像头':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 2, None)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data['rtsp']
            elif i.equipment_type == '浙江双视热成像':
                rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(i.equipment_uname, i.equipment_password, i.equipment_ip)
            elif i.equipment_type == '安防平台':
                rtsp = i.Hik_rtsp_url
            dict_res = {
                'equipment_id': i.id,
                'equipment_name': i.equipment_name,
                'mine_id': i.Mine_id,
                'equipment_ip': rtsp,
                'ip': i.equipment_ip,
                'uname': i.equipment_uname,
                'password': i.equipment_password,
                'data_now_result': datainfo(i.id, 2),
                'data_old_result': datainfo(i.id, 1),
                'data_res': datainfo(i.id, 2) + datainfo(i.id, 1),
            }
            equipment_data.append(dict_res)
        response_data = {
            'total_items': equipment_info.total,
            'total_pages': equipment_info.pages,
            'current_page': equipment_info.page,
            'per_page': per_page,
            'data': equipment_data,
        }
        return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_data_service(params):
    try:
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        algorithm_file_name = params.get('algorithm_file_name')
        algorithm_name = params.get('algorithm_name')
        algorithm_status = params.get('algorithm_status')
        algorithm_trade_type = params.get('algorithm_trade_type')
        filters = []
        if algorithm_file_name:
            filters.append(Algorithm_library.algorithm_file_name.ilike(f"%{algorithm_file_name}%"))
        if algorithm_name:
            filters.append(Algorithm_library.algorithm_name.ilike(f"%{algorithm_name}%"))
        if algorithm_status:
            filters.append(Algorithm_library.algorithm_status == int(algorithm_status))
        if algorithm_trade_type:
            filters.append(Algorithm_library.algorithm_trade_type == int(algorithm_trade_type))
        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else None
        algorithm_data = fetch_algorithm_library_paginated(query_filter, page, per_page)
        algorithm_info = [{
            'id': i.id,
            'algorithm_file_name': i.algorithm_file_name,
            'algorithm_name': extract_chinese(i.algorithm_name),
            'algorithm_type': configs.algorithm_type[int(i.algorithm_type) - 1]['value'],
            'algorithm_version': i.algorithm_version,
            'algorithm_status': configs.status[int(i.algorithm_status) - 1]['value'],
            'algorithm_trade_type': i.algorithm_trade_type,
            'create_time': (i.create_time).strftime("%Y-%m-%d %H:%M:%S"),
            'algorithm_ps': i.algorithm_ps
        } for i in algorithm_data.items]
        response_data = {
            'total_items': algorithm_data.total,
            'total_pages': algorithm_data.pages,
            'current_page': algorithm_data.page,
            'per_page': per_page,
            'data': algorithm_info,
        }
        return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_config_history_service(params):
    try:
        r = Redis(Redis_ip, Redis_port, 'list')
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        config_id = params.get('id')
        if config_id:
            algorithm_res = fetch_algorithm_config_history_paginated(config_id, page, per_page)
        else:
            algorithm_res = fetch_algorithm_config_history_all_paginated(page, per_page)
        algorithm_data = [{
            'id': i.id,
            'image': ('/static/' + str(os.path.basename(r.get_string('em_{}'.format(snapshot_identity(i.Equipment_id, getattr(i, 'stream_type', None))))))
                      if i.Equipment_id and r.get_string('em_{}'.format(snapshot_identity(i.Equipment_id, getattr(i, 'stream_type', None))))
                      else ''),
            'Algorithm_library_id': i.Algorithm_library_id,
            'algorithm_name': i.algorithm_name,
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
            'Algorithm_config_ps': i.Algorithm_config_ps,
            'operation_type': i.operation_type,
            'scene_typename': i.scene_typename if i.scene_typename else '',
            'sensitivity': i.sensitivity if i.sensitivity else 0,
            'defense_time_start': i.defense_time_start if i.defense_time_start else '',
            'defense_time_end': i.defense_time_end if i.defense_time_end else '',
            'model_template_config_id': i.model_template_config_id if i.model_template_config_id else '',
            'template_list_area': i.template_list_area if i.template_list_area else '',
            'image_count': i.image_count if i.image_count else '',
            'template_small_id': i.template_small_id if i.template_small_id else '',
            'count_time': i.count_time if i.count_time else 0,
            'res_type': i.res_type if i.res_type else 1,
        } for i in algorithm_res.items]
        response_data = {
            'total_items': algorithm_res.total,
            'total_pages': algorithm_res.pages,
            'current_page': algorithm_res.page,
            'per_page': per_page,
            'data': algorithm_data,
        }
        if config_id and algorithm_res.total == 0:
            return {'code': 400, 'data_list': [], 'msg': '未有该配置的详情信息'}
        return {'code': 200, 'data_list': response_data, 'msg': '查询成功'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_data_update_service(params):
    try:
        library_id = params.get('id')
        status = params.get('status')
        if not library_id:
            return {'code': 400, 'msg': '缺少必要参数：id'}
        if isinstance(library_id, bool) or not str(library_id).isdigit() or int(library_id) < 1:
            return {'code': 400, 'msg': '算法ID无效'}
        status_value = {'运行': 1, '停止': 2, '1': 1, '2': 2}.get(str(status))
        if status_value is None:
            return {'code': 400, 'msg': '状态必须为运行或停止'}
        data = db.session.query(Algorithm_library).filter(
            Algorithm_library.id == int(library_id)).with_for_update().first()
        if data is None:
            return {'code': 404, 'msg': '算法不存在'}
        data.algorithm_status = status_value
        if status_value == 2:
            configs = db.session.query(Algorithm_config).filter(
                Algorithm_config.Algorithm_library_id == data.id).all()
            for conf in configs:
                # An already confirmed stop must remain confirmed on a retry.
                if str(conf.status) != '2' or conf.model_status != 4:
                    conf.model_status = 2
                conf.status = 2
                conf.conf_status = 0
        db.session.commit()
        return {'code': 200, 'msg': '修改成功'}
    except Exception:
        db.session.rollback()
        return {'code': 500, 'msg': '算法状态更新失败，请稍后重试'}

@resource_admission_guard('start')
def algorithm_conf_update_service(params):
    try:
        config_id = params.get('id')
        status_value = {'运行': 1, '停止': 2, '1': 1, '2': 2}.get(str(params.get('status')))
        if isinstance(config_id, bool) or not str(config_id).isdigit() or int(config_id) < 1:
            return {'code': 400, 'msg': '任务ID无效'}
        if status_value is None:
            return {'code': 400, 'msg': '状态必须为运行或停止'}
        data = db.session.query(Algorithm_config).filter(
            Algorithm_config.id == int(config_id)).first()
        if data is None:
            return {'code': 404, 'msg': '算法配置不存在'}
        if status_value == 1:
            # Serialize enable with library stop, which locks this same row.
            library = db.session.query(Algorithm_library).filter(
                Algorithm_library.id == data.Algorithm_library_id).with_for_update().first()
            if library is None or str(library.algorithm_status) != '1':
                db.session.rollback()
                return {'code': 409, 'msg': '算法包已停止或不存在，请先启用算法包'}
            prepare_stream_type({'stream_type': getattr(data, 'stream_type', None)},
                                data.Equipment_id, config_id=data.id)
            data.status = 1
            data.conf_status = 0
            data.model_status = 2
        else:
            # The worker writes 4 only after the previous process has exited.
            if str(data.status) != '2' or data.model_status != 4:
                data.model_status = 2
            data.status = 2
            data.conf_status = 0
        db.session.commit()
        return {'code': 200, 'msg': '修改成功'}
    except ValueError as error:
        db.session.rollback()
        return {'code': 400, 'msg': str(error)}
    except Exception:
        db.session.rollback()
        return {'code': 500, 'msg': '算法配置状态更新失败，请稍后重试'}


@resource_admission_batch_guard
def algorithm_conf_batch_update_service(payload):
    # Validate the whole request before the first independently committed item.
    if not isinstance(payload, dict):
        return {'code': 400, 'msg': '请提交包含 ids 和 status 的 JSON 对象'}
    ids = payload.get('ids')
    status = payload.get('status')
    if not isinstance(ids, list) or not ids:
        return {'code': 400, 'msg': '请选择需要批量操作的任务，ids 必须为非空数组'}
    if len(ids) > 100:
        return {'code': 400, 'msg': '每次最多批量操作 100 个任务，请分批提交'}
    if any(type(config_id) is not int or not 1 <= config_id <= 2147483647 for config_id in ids):
        return {'code': 400, 'msg': '任务 ID 必须为有效正整数'}
    if status not in ('运行', '停止'):
        return {'code': 400, 'msg': '批量状态必须为运行或停止'}
    unique_ids = list(dict.fromkeys(ids))
    results = []
    for config_id in unique_ids:
        try:
            current = db.session.query(Algorithm_config).filter(
                Algorithm_config.id == config_id).first()
            desired_status = '1' if status == '运行' else '2'
            if current is not None and str(current.status) == desired_status:
                # A repeated desired state must not restart healthy/pending
                # work, or erase an in-flight/confirmed stop acknowledgement.
                try:
                    if desired_status == '1':
                        library = db.session.query(Algorithm_library).filter(
                            Algorithm_library.id == current.Algorithm_library_id).with_for_update().first()
                        if library is None or str(library.algorithm_status) != '1':
                            outcome = {'code': 409, 'msg': '算法包已停止或不存在，请先启用算法包；任务状态保持不变'}
                        else:
                            prepare_stream_type({'stream_type': getattr(current, 'stream_type', None)},
                                                current.Equipment_id, config_id=current.id)
                            outcome = {'code': 200, 'msg': '任务已设置运行，保持现有状态与配置处理进度'}
                    else:
                        outcome = {'code': 200, 'msg': '任务已设置停止，保持现有状态与停止确认进度'}
                except ValueError as error:
                    outcome = {'code': 400, 'msg': str(error)}
                # This branch performs no writes; release its read/row locks.
                db.session.rollback()
            else:
                outcome = algorithm_conf_update_service({'id': config_id, 'status': status})
            if not isinstance(outcome, dict):
                raise RuntimeError('Unexpected single-task outcome')
            code = outcome.get('code')
            if type(code) is not int or not 100 <= code <= 599:
                code = 500
            message = outcome.get('msg')
            if not isinstance(message, str) or not message:
                message = '该任务状态更新失败，请刷新后重试'
            success = code == 200
        except Exception:
            code, success = 500, False
            message = '该任务状态更新失败，请刷新后重试'
        if not success:
            # Single-task validation failures can leave a read transaction open;
            # rollback also isolates a broken DB transaction before the next ID.
            try:
                db.session.rollback()
            except Exception:
                try:
                    db.session.remove()
                except Exception:
                    pass
        results.append({'id': config_id, 'success': success, 'code': code, 'msg': message})
    succeeded = sum(item['success'] for item in results)
    failed = len(results) - succeeded
    code = 200 if not failed else 207 if succeeded else 400
    message = ('已处理 %s 项%s请求' % (succeeded, status) if not failed else
               '已处理 %s 项%s请求，%s 项未成功，请查看逐项结果' % (succeeded, status, failed))
    return {'code': code, 'msg': message,
            'data': {'total': len(results), 'succeeded': succeeded, 'failed': failed,
                     'results': results}}

# def algorithm_library_delete_service(payload):
#     try:
#         ids = payload.get('id', None)
#         # 参数构建判断是否为空
#         params = [ids]
#
#         # 如果参数未获取到
#         if not all(params):
#             return jsonify({'code': 400, 'msg': '缺少删除设备id参数'})
#
#         # 当存在ids
#         if ids:
#             # 删除算法id
#             main_algorithms = db.session.query(Algorithm_library).filter(Algorithm_library.id.in_(ids)).all()
#
#             # 获取主算法的analysis_type值
#             main_analysis_types = [algo.analysis_type for algo in main_algorithms if algo.analysis_type]
#
#             # 查找子算法：analysis_type与ids中任一算法相同，且algorithm_child等于2
#             child_algorithms = []
#             if main_analysis_types:
#                 child_algorithms = db.session.query(Algorithm_library).filter(
#                     Algorithm_library.analysis_type.in_(main_analysis_types),
#                     Algorithm_library.algorithm_child == 2
#                 ).all()
#
#                 # 获取子算法的ids
#                 child_ids = [child_algo.id for child_algo in child_algorithms]
#             else:
#                 child_ids = []
#             db.session.query(Algorithm_library).filter(Algorithm_library.id.in_(ids)).delete()
#             if child_ids:
#                 db.session.query(Algorithm_library).filter(Algorithm_library.id.in_(child_ids)).delete()
#
#             # # 查找算法id
#             # res = db.session.query(Algorithm_library.id).filter(Algorithm_library.id == id).first()
#
#             # 根据算法id查找是否有配置id，如果存在配置id进行删除， 算法结果删除
#             conf_id = db.session.query(Algorithm_config.id).filter(Algorithm_config.Algorithm_library_id.in_(ids)).all()
#             conf_ids = [i[0] for i in conf_id]
#
#             # 删除算法配置id
#             db.session.query(Algorithm_config).filter(Algorithm_config.id.in_(conf_ids)).delete()
#
#             # # 根据算法配置id删除算法结果id
#             # db.session.query(Algorithm_result).filter(Algorithm_result.Algorithm_config_id.in_(conf_ids)).delete()
#             for id in ids:
#                 delete_record = Algorithm_result_delete(algorithm_id=id)
#                 db.session.add(delete_record)
#
#             # 提交
#             db.session.commit()
#         return {'code': 200, 'msg': '删除成功'}
#     except Exception as e:
#         db.session.rollback()
#         return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


def algorithm_library_delete_service(payload):
    if not isinstance(payload, dict):
        return {'code': 400, 'msg': '请提交算法包 ID 数组'}
    try:
        result = delete_library_records(db.session, Algorithm_library, Algorithm_config,
                                        Algorithm_result_delete, payload.get('id'))
    except ConfigurationConflict as error:
        return {'code': 409, 'msg': str(error)}
    except ValueError as error:
        return {'code': 400, 'msg': str(error)}
    except Exception:
        db.session.rollback()
        return {'code': 500, 'msg': '算法包删除失败，数据库与模型文件已保留'}
    # Remote cleanup is outside the database transaction. A failed commit must
    # never destroy a model still referenced by the retained records.
    pending_files = 0
    try:
        hosts = db.session.query(Computing_equipment).all()
        for path in result.pop('file_paths'):
            for host in hosts:
                try:
                    outcome = SSH_Func(host.computing_ip, host.computing_user,
                                       host.computing_password).delete_remote_file(path)
                    if outcome not in ('删除成功', '文件不存在'):
                        pending_files += 1
                except Exception:
                    pending_files += 1
    except Exception:
        db.session.rollback()
        result.pop('file_paths', None)
        pending_files += 1
    result['pending_file_cleanup'] = pending_files
    message = '删除成功' if not pending_files else '算法包和关联任务已删除，部分远端模型文件未清理，请检查算力设备连接'
    return {'code': 200, 'msg': message, 'data': result}


def dict_type_add_service(params):
    try:
        type_name = params.get('type_name')
        type_code = params.get('type_code')
        description = params.get('description')
        enable = params.get('enable')
        if not all([type_name, type_code, enable]):
            return {'code': 400, 'msg': '字典类型有未填写项'}
        existing = dict_type_exists(type_code)
        if existing:
            return {'code': 400, 'msg': '字典类型标识已存在'}
        add_dict_type(type_name, type_code, description, enable)
        return {'code': 200, 'msg': '字典类型添加完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_type_update_service(params):
    try:
        id = params.get('id')
        type_name = params.get('type_name')
        type_code = params.get('type_code')
        description = params.get('description')
        enable = params.get('enable')
        if not all([id, type_name, type_code]):
            return {'code': 400, 'msg': '字典类型有未填写项'}
        dict_type_obj = db.session.query(DictType).filter(DictType.id == id).first()
        if not dict_type_obj:
            return {'code': 400, 'msg': '字典类型不存在'}
        old_type_code = dict_type_obj.type_code
        update_dict_data_type_code(old_type_code, type_code)
        update_dict_type(id, {
            'type_name': type_name,
            'type_code': type_code,
            'description': description,
            'enable': enable if enable else '1'
        })
        return {'code': 200, 'msg': '字典类型修改完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_type_del_service(form):
    try:
        id_list = form.getlist('id')
        ids = [i for i in id_list]
        if not ids:
            return {'code': 400, 'msg': '缺少字典类型id'}
        codes = fetch_type_codes_by_type_ids(ids)
        if codes:
            delete_dict_data_by_type_codes(codes)
        delete_dict_types_by_ids(ids)
        return {'code': 200, 'msg': '字典类型删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_type_show_service(params):
    try:
        dict_name = params.get('dict_name')
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        if dict_name:
            type_res = paginate_dict_types_by_name(dict_name, page, per_page)
            if type_res and type_res.total > 0:
                type_data = [{
                    'id': i.id,
                    'type_name': i.type_name,
                    'type_code': i.type_code,
                    'description': i.description if i.description else '',
                    'enable': i.enable if i.enable else '1',
                    'create_time': (i.create_time).strftime("%Y-%m-%d %H:%M:%S") if i.create_time else '',
                    'update_time': (i.update_time).strftime("%Y-%m-%d %H:%M:%S") if i.update_time else '',
                } for i in type_res.items]
                response_data = {
                    'total_items': type_res.total,
                    'total_pages': type_res.pages,
                    'current_page': type_res.page,
                    'per_page': per_page,
                    'data': type_data,
                }
                return {'code': 200, 'data_list': response_data, 'msg': '查询成功'}
            else:
                return {'code': 400, 'data_list': [], 'msg': '未有该字典类型的详情信息'}
        else:
            type_res = paginate_dict_types(page, per_page)
            type_data = [{
                'id': i.id,
                'type_name': i.type_name,
                'type_code': i.type_code,
                'description': i.description if i.description else '',
                'enable': i.enable if i.enable else '1',
                'create_time': (i.create_time).strftime("%Y-%m-%d %H:%M:%S") if i.create_time else '',
                'update_time': (i.update_time).strftime("%Y-%m-%d %H:%M:%S") if i.update_time else '',
            } for i in type_res.items]
            response_data = {
                'total_items': type_res.total,
                'total_pages': type_res.pages,
                'current_page': type_res.page,
                'per_page': per_page,
                'data': type_data,
            }
            return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_data_add_service(params):
    try:
        data_label = params.get('data_label')
        data_value = params.get('data_value')
        type_code = params.get('type_code')
        is_default = params.get('is_default', 0)
        enable = params.get('enable')
        remark = params.get('remark')
        if not all([data_label, data_value, type_code]):
            return {'code': 400, 'msg': '字典数据有未填写项'}
        max_data_id = fetch_max_data_id_for_type(type_code)
        if max_data_id:
            max_data_id = max_data_id + 1
        add_dict_data(data_label, data_value, type_code, is_default, enable, remark, max_data_id if max_data_id else None)
        return {'code': 200, 'msg': '字典数据添加完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_data_update_service(params):
    try:
        id = params.get('id')
        data_label = params.get('data_label')
        data_value = params.get('data_value')
        is_default = params.get('is_default', 0)
        enable = params.get('enable')
        remark = params.get('remark')
        if not all([data_label, data_value, enable]):
            return {'code': 400, 'msg': '字典数据有未填写项'}
        obj = get_dict_data_by_id(id)
        if not obj:
            return {'code': 400, 'msg': '字典数据不存在'}
        update_dict_data_fields(id, {
            'data_label': data_label if data_label else obj.data_label,
            'data_value': data_value if data_value else obj.data_value,
            'is_default': is_default if is_default else obj.is_default,
            'enable': enable if enable else obj.enable,
            'remark': remark if remark else obj.remark
        })
        return {'code': 200, 'msg': '字典数据修改完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_data_del_service(params):
    try:
        id_raw = params.get('id')
        ids = [int(i) for i in id_raw.split(',') if str(i).isdigit()] if id_raw else []
        if not ids:
            return {'code': 400, 'msg': '缺少字典数据id'}
        delete_dict_data_by_ids(ids)
        return {'code': 200, 'msg': '字典数据删除成功'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def dict_data_show_service(params):
    try:
        type_code = params.get('type_code')
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        data_res = paginate_dict_data_by_type_code(type_code, page, per_page)
        if data_res and data_res.total > 0:
            dict_data = [{
                'id': i.id,
                'data_label': i.data_label,
                'data_value': i.data_value,
                'type_code': i.type_code,
                'is_default': i.is_default,
                'enable': i.enable if i.enable else '1',
                'remark': i.remark if i.remark else '',
            } for i in data_res.items]
            response_data = {
                'total_items': data_res.total,
                'total_pages': data_res.pages,
                'current_page': data_res.page,
                'per_page': per_page,
                'data': dict_data,
            }
            return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
        else:
            return {'code': 400, 'msg': '字典数据不存在'}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def algorithm_result_delete_service(params):
    try:
        raw = params.get('id_list')
        if raw is None:
            return {'code': 400, 'msg': '缺少报警列表id参数'}
        ids = []
        if isinstance(raw, list):
            ids = raw
        else:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    ids = parsed
                else:
                    ids = [int(i) for i in str(raw).split(',') if str(i).strip().isdigit()]
            except Exception:
                ids = [int(i) for i in str(raw).split(',') if str(i).strip().isdigit()]
        ids = list({int(i) for i in ids if str(i).isdigit()})
        if not ids:
            return {'code': 400, 'msg': '缺少报警列表id参数'}
        count = fetch_algorithm_results_count_by_ids(ids)
        if count == 0:
            return {'code': 404, 'msg': '未找到相关配置'}
        delete_algorithm_results_by_ids(ids)
        return {'code': 200, 'msg': '删除报警数据完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'删除失败: {str(e)}'}

def mine_insert_service(payload):
    try:
        mine_name = strip_whitespace(payload.get('mine_name', None))
        mine_code = strip_whitespace(payload.get('mine_code', None))
        if not all([mine_name, mine_code]):
            return {'code': 400, 'msg': '设备数据有未填写项'}
        exists = fetch_mine_by_name(mine_name)
        if exists:
            return {'code': 400, 'msg': '当前名称已经存在'}
        insert_mine(mine_name, mine_code)
        return {'code': 200, 'msg': '煤矿信息添加完成！'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'煤矿信息添加失败: {str(e)}'}

def mine_delete_service(payload):
    try:
        raw_id = payload.get('id', None)
        try:
            mine_id = int(strip_whitespace(raw_id))
        except Exception:
            return {'code': 400, 'msg': '煤矿 ID 不合法！'}
        if not mine_id:
            return {'code': 400, 'msg': '煤矿 ID 不能为空！'}
        mine_data = get_mine_by_id(mine_id)
        if not mine_data:
            return {'code': 400, 'msg': '煤矿信息不存在！'}
        delete_mine_by_id(mine_id)
        return {'code': 200, 'msg': '煤矿信息删除成功！'}
    except SQLAlchemyError as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'煤矿信息删除失败: {str(e)}'}

def mine_update_service(payload):
    try:
        mine_id = strip_whitespace(payload.get('id', None))
        mine_name = strip_whitespace(payload.get('mine_name', None))
        mine_code = strip_whitespace(payload.get('mine_code', None))
        if not mine_id:
            return {'code': 400, 'msg': '煤矿 ID 未填写'}
        detail = get_mine_by_id(mine_id)
        if not detail:
            return {'code': 404, 'msg': '煤矿信息不存在'}
        if mine_name is None and mine_code is None:
            return {'code': 400, 'msg': '未提供任何修改内容'}
        if mine_name:
            existing_mine = db.session.query(Mine).filter(Mine.mine_name == mine_name, Mine.id != mine_id).first()
            if existing_mine:
                return {'code': 400, 'msg': '煤矿名称已存在'}
        if mine_code:
            existing_code = db.session.query(Mine).filter(Mine.mine_code == mine_code, Mine.id != mine_id).first()
            if existing_code:
                return {'code': 400, 'msg': '煤矿编码已存在'}
        update_fields = {}
        if mine_name:
            update_fields['mine_name'] = mine_name
        if mine_code:
            update_fields['mine_code'] = mine_code
        update_mine_fields(mine_id, update_fields)
        return {'code': 200, 'msg': '修改成功'}
    except SQLAlchemyError as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'数据库错误: {str(e)}'}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器错误: {str(e)}'}

def mine_detail_service(params):
    try:
        mine_id = params.get('id')
        if not mine_id:
            return {'code': 400, 'msg': '煤矿ID未填写'}
        detail = fetch_mine_detail_by_id(mine_id)
        if not detail:
            return {'code': 404, 'msg': '煤矿信息不存在'}
        data = {
            'id': detail.id,
            'mine_name': detail.mine_name,
            'mine_code': detail.mine_code,
        }
        return {'code': 200, 'data': data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器错误: {str(e)}'}

def mine_show_service(params):
    try:
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        pagination = paginate_mines(page, per_page)
        data_list = [{
            'id': item.id,
            'mine_name': item.mine_name,
            'mine_code': item.mine_code,
        } for item in pagination.items]
        response = {
            'code': 200,
            'data': data_list,
            'pagination': {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }
        }
        return {'code': 200, 'data': response}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器错误: {str(e)}'}

def equipment_info_service(params):
    try:
        equip_type_flag = params.get('type')
        name = params.get('name')
        results = fetch_equipment_search(equip_type_flag, name)
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
        } for i in results]
        return {'code': 200, 'msg': '查询成功', 'data': equipment_list}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器错误: {str(e)}'}

def version_show_service():
    # The running backend image is authoritative; database records can be stale.
    from common.image_version import backend_version_response
    return backend_version_response()


def algorithm_result_sqlalchemy_service(params):
    try:
        id = params.get('id')
        mine_id = params.get('mine_id')
        equipment_id = params.get('equipment_id')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        type_sta = params.get('type')
        algorithm_id = params.get('algorithm_id')
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 15))
        filters = []
        if mine_id:
            filters.append(Algorithm_config.Mine_id == mine_id)
        if equipment_id:
            parent_id = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            children = db.session.query(Equipment).filter(Equipment.parent_id == parent_id.id).first() if parent_id else None
            if not children:
                filters.append(Equipment.id == equipment_id)
            else:
                filters.append(Equipment.parent_id == equipment_id)
        if start_time and end_time:
            filters.append(Algorithm_result.res_time.between(time_to_gmt_format(start_time), time_to_gmt_format(end_time)))
        if type_sta:
            filters.append(Algorithm_result.res_type == type_sta)
        if algorithm_id:
            filters.append(Algorithm_library.id == algorithm_id)
        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else None
        if id:
            algorithm_info = fetch_algorithm_result_sqlalchemy_paginated_by_id(id, page, per_page)
        else:
            if query_filter is not None:
                algorithm_info = fetch_algorithm_result_sqlalchemy_paginated(query_filter, page, per_page)
            else:
                algorithm_info = fetch_algorithm_result_sqlalchemy_paginated_no_filter(page, per_page)
        algorithm_data = [{
            'Algorithm_result_id': i.Algorithm_result_id,
            'res_time': i.res_time.strftime("%Y-%m-%d %H:%M:%S"),
            'Mine_id': i.Mine_id,
            'mine_name': i.mine_name,
            'Equipment_id': i.Equipment_id,
            'equipment_name': i.equipment_name,
            'conf_id': i.Algorithm_config_id,
            'conf_name': i.conf_name,
            'res_type': configs.type_status[int(i.res_type) - 1]['value'],
            'res_image': i.res_image,
            'res_video': i.res_video,
            'res_frame_skip': i.res_frame_skip,
            'algorithm_name': i.algorithm_name,
            'img_resolution': i.conf_img_resolution,
        } for i in algorithm_info.items]
        response_data = {
            'total_items': algorithm_info.total,
            'total_pages': algorithm_info.pages,
            'current_page': algorithm_info.page,
            'per_page': per_page,
            'data': algorithm_data,
        }
        return {'code': 200, 'msg': '查询成功', 'data_list': response_data}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}
        
@resource_admission_guard('create')
def add_algorithm_config_models(payload):
    try:
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id') or payload.get('equipment_name')
        model_data = payload.get('model_data', [])
        if not all([conf_name, Mine_id, Equipment_id]) or not model_data:
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        model_data = normalize_count_models(model_data, _person_count_template)
        first_model = model_data[0]
        stream_type = prepare_stream_type(payload, Equipment_id, models=model_data)
        Algorithm_library_id = first_model.get('Algorithm_library_id')
        conf_area = first_model.get('conf_area')
        status = first_model.get('status')
        test_type_id = first_model.get('test_type_id')
        shield_status = first_model.get('shield_status')
        tem_conf_area = first_model.get('tem_conf_area')
        tem_frames = first_model.get('tem_frames')
        confidence = first_model.get('confidence')
        draw_type = first_model.get('draw_type')
        interval_time = alarm_interval(first_model.get('interval_time'))
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
        image_count = first_model.get('image_count')
        template_small_id = first_model.get('template_small_id')
        count_time = first_model.get('count_time', 0)
        res_type = first_model.get('res_type')
        computing_id = first_model.get('computing_id')
        template_data = first_model.get('template_data')
        label_list = first_model.get('label_list')
        model_template_type_id = first_model.get('model_template_type_id')
        amp = first_model.get('amp', 10)
        alg_select_type = first_model.get('alg_select_type', 3)
        model_two_type = first_model.get('model_two_type')
        model_two_data = first_model.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = first_model.get('priority')
        run_time = first_model.get('run_time')
        cross_line_area = first_model.get('cross_line_area')
        if get_algorithm_config_by_name(conf_name):
            return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        if get_algorithm_config_by_equipment_and_library(Equipment_id, Algorithm_library_id):
            return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        if not get_algorithm_library_by_id(Algorithm_library_id):
            return {'code': 400, 'msg': '算法库id不存在'}
        _ = get_mine_by_id(Mine_id)
        resresource_data = get_resource_usage_by_id(resource_id)
        if resresource_data:
            extra_models_data = []
            for i in range(1, len(model_data)):
                model = model_data[i]
                algorithm_info = get_algorithm_library_by_id(model.get('Algorithm_library_id'))
                resource_info = get_resource_usage_by_id(model.get('resource_id'))
                extra_model_data = {
                    'Algorithm_library_id': model.get('Algorithm_library_id'),
                    'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                    'cross_line_area': model.get('cross_line_area'),
                    'template_config_type_id': model.get('template_config_type_id'),
                    'template_id': model.get('template_id'),
                    'template_name': model.get('template_name', ''),
                    'template_small_name': algorithm_info.template_small_name if algorithm_info else '',
                    'conf_img_resolution': model.get('img_resolution') or img_resolution,
                    'sensitivity': model.get('sensitivity') if model.get('sensitivity') is not None else sensitivity,
                    'conf_area': convert_data_format(model_roi(model.get('conf_area', []))),
                    'confidence': model.get('confidence', ''),
                    'interval_time': alarm_interval(model.get('interval_time')),
                    'duration_time': model.get('duration_time', 0),
                    'dev_id': resource_info.dev_id if resource_info else 0,
                    'res_type': model.get('res_type', 1),
                    'algorithm_type_list': str(algorithm_info.algorithm_type_list) if algorithm_info else '',
                    'label_list': model.get('label_list', [])
                }
                extra_models_data.append(extra_model_data)
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
                'stream_type': stream_type,
                'run_time': run_time,
                'cross_line_area': cross_line_area,
                'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
                'model_algo_data_ori': json.dumps(model_data[1:], ensure_ascii=False) if len(model_data) > 1 else '',
                'multimodels_type': 1
            }
            config_obj = insert_algorithm_config(fields)
            insert_algorithm_config_history_from_config(config_obj, '添加')
        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except ValueError as e:
        db.session.rollback()
        return {'code': 400, 'msg': str(e)}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

@resource_admission_guard('update')
def update_algorithm_config_models(payload):
    try:
        id = payload.get('id')
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('equipment_name') or payload.get('Equipment_id')
        model_data = payload.get('model_data')
        if not model_data:
            return {'code': 400, 'msg': '缺少算法模型参数'}
        model_data = normalize_count_models(model_data, _person_count_template)
        first_model = model_data[0]
        stream_type = prepare_stream_type(payload, Equipment_id, config_id=payload.get('id'), models=model_data)
        Algorithm_library_id = first_model.get('Algorithm_library_id')
        conf_area = first_model.get('conf_area')
        test_type_id = first_model.get('test_type_id')
        shield_status = first_model.get('shield_status')
        tem_conf_area = first_model.get('tem_conf_area')
        tem_frames = first_model.get('tem_frames')
        confidence = first_model.get('confidence')
        draw_type = first_model.get('draw_type')
        interval_time = alarm_interval(first_model.get('interval_time'))
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
        model_two_data = first_model.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = first_model.get('priority')
        run_time = first_model.get('run_time')
        cross_line_area = first_model.get('cross_line_area')
        params = [id, conf_name, Mine_id, Equipment_id]
        if not all(params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        resource_data = get_resource_usage_by_id(resource_id)
        if resource_data:
            extra_models_data = []
            for i in range(1, len(model_data)):
                model = model_data[i]
                algorithm_info = get_algorithm_library_by_id(model.get('Algorithm_library_id'))
                resource_info = get_resource_usage_by_id(model.get('resource_id'))
                conf_area_data = convert_data_format(model_roi(model.get('conf_area', [])))
                extra_model_data = {
                    'Algorithm_library_id': model.get('Algorithm_library_id'),
                    'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                    'cross_line_area': model.get('cross_line_area'),
                    'template_config_type_id': model.get('template_config_type_id'),
                    'template_id': model.get('template_id'),
                    'template_name': model.get('template_name', ''),
                    'template_small_name': algorithm_info.template_small_name if algorithm_info else '',
                    'conf_img_resolution': model.get('img_resolution') or img_resolution,
                    'sensitivity': model.get('sensitivity') if model.get('sensitivity') is not None else sensitivity,
                    'conf_area': conf_area_data,
                    'confidence': model.get('confidence', ''),
                    'interval_time': alarm_interval(model.get('interval_time')),
                    'duration_time': model.get('duration_time', 0),
                    'dev_id': resource_info.dev_id if resource_info else 0,
                    'res_type': model.get('res_type', 1),
                    'algorithm_type_list': algorithm_info.algorithm_type_list if algorithm_info else '',
                    'label_list': model.get('label_list', [])
                }
                extra_models_data.append(extra_model_data)
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
                'interval_time': interval_time,
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
                'priority': priority,
                'stream_type': stream_type,
                'run_time': run_time,
                'cross_line_area': cross_line_area,
                'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
                'model_algo_data_ori': json.dumps(model_data[1:], ensure_ascii=False) if len(model_data) > 1 else ''
            }
            if resource_id_old == resource_id:
                conf_fields.update(model_status=2, model_template_type_id=model_template_type_id)
            update_algorithm_config_fields(id, conf_fields)
            return {'code': 200, 'msg': '算法配置数据修改完成'}
        else:
            return {'code': 400, 'msg': '算力资源信息不存在!'}
    except ValueError as e:
        db.session.rollback()
        return {'code': 400, 'msg': str(e)}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

@resource_admission_guard('update')
def update_algorithm_config(payload):
    try:
        payload = normalize_count_config(payload, _person_count_template)
        id = payload.get('id')
        conf_name = payload.get('conf_name')
        Algorithm_library_id = payload.get('Algorithm_library_id')
        Mine_id = payload.get('Mine_id')
        Equipment_id = payload.get('Equipment_id')
        stream_type = prepare_stream_type(payload, Equipment_id, config_id=payload.get('id'))
        conf_area = payload.get('conf_area')
        test_type_id = payload.get('test_type_id')
        shield_status = payload.get('shield_status')
        tem_conf_area = payload.get('tem_conf_area')
        tem_frames = payload.get('tem_frames')
        confidence = payload.get('confidence')
        draw_type = payload.get('draw_type')
        interval_time = alarm_interval(payload.get('interval_time'))
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
        Entering_num = payload.get('Entering_num')
        Exiting_num = payload.get('Exiting_num')
        all_Entering_num = payload.get('all_Entering_num')
        all_Exiting_num = payload.get('all_Exiting_num')
        cross_line_area = payload.get('cross_line_area')
        params = [id, conf_name, Algorithm_library_id, Mine_id, Equipment_id, conf_area, test_type_id, resource_id, model_template_config_id]
        if not all(params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}
        resource_data = get_resource_usage_by_id(resource_id)
        if resource_data:
            if resource_id_old == resource_id:
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
                    'interval_time': interval_time,
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
                    'template_data': template_data,
                    'label_list': str(label_list),
                    'model_status': 2,
                    'model_template_type_id': model_template_type_id,
                    'amp': amp,
                    'alg_select_type': alg_select_type,
                    'model_two_data': model_two_data,
                    'model_two_type': model_two_type,
                    'priority': priority,
                    'stream_type': stream_type,
                'run_time': run_time,
                    'Entering_num': Entering_num,
                    'Exiting_num': Exiting_num,
                    'all_Entering_num': all_Entering_num,
                    'all_Exiting_num': all_Exiting_num,
                    'cross_line_area': cross_line_area
                }
                update_algorithm_config_fields(id, updated_fields)
                conf_obj = db.session.query(Algorithm_config).filter(Algorithm_config.id == id).first()
                if conf_obj:
                    insert_algorithm_config_history_from_config(conf_obj, '修改')
                return {'code': 200, 'msg': '算法配置数据修改完成'}
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
                'interval_time': interval_time,
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
                'template_data': template_data,
                'res_type': res_type if res_type else 1,
                'label_list': str(label_list) if label_list else str([]),
                'amp': amp,
                'alg_select_type': alg_select_type,
                'model_two_data': model_two_data,
                'model_two_type': model_two_type,
                'priority': priority,
                'stream_type': stream_type,
                'run_time': run_time,
                'Entering_num': Entering_num,
                'Exiting_num': Exiting_num,
                'all_Entering_num': all_Entering_num,
                'all_Exiting_num': all_Exiting_num,
                'cross_line_area': cross_line_area
            }
            update_algorithm_config_fields(id, conf_fields)
            conf_obj = db.session.query(Algorithm_config).filter(Algorithm_config.id == id).first()
            if conf_obj:
                insert_algorithm_config_history_from_config(conf_obj, '修改')
            return {'code': 200, 'msg': '算法配置数据修改完成'}
        else:
            return {'code': 400, 'msg': '算力资源信息不存在!'}
    except ValueError as e:
        db.session.rollback()
        return {'code': 400, 'msg': str(e)}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def handle_algorithm_upload_group(uploaded_file, algorithm_status, algorithm_ps):
    """
    处理算法组包上传逻辑
    """

    def upload_to_multiple_servers(SSH_list, file_content, algorithm_filename):
        """
        上传文件到多个服务器
        :param SSH_list: 包含多个 SSH 对象的列表
        :param file_content: 文件内容
        :param algorithm_filename: 文件名
        :return: 所有服务器的上传路径或错误信息
        """
        upload_results = []

        for i in SSH_list:
            try:
                # 上传文件到服务器
                res = i.upload_send_file(file_content, algorithm_filename)
                if res in ['无法上传文件', '上传中断，请稍后重试','服务器连接异常']:
                    upload_results.append('无法上传文件')
                else:
                    upload_results.append(res)
            except Exception as e:
                upload_results.append('无法上传文件')

        return upload_results

    # 查找设备的所有信息
    computing_info = db.session.query(Computing_equipment).filter(
        Computing_equipment.server_type == 1
    ).all()

    # 创建多个 SSH 实例，表示要上传的服务器-
    SSH_list = []  # Build connections only for explicitly compatible devices after package validation.

    try:
        if str(algorithm_status) not in ('1', '2'):
            raise AlgorithmPackageError('算法启用状态必须是运行或停止')
        algorithm_status = str(algorithm_status)
        content = read_uploaded_zip(uploaded_file)

        if uploaded_file and uploaded_file.filename.casefold().endswith('.zip'):
            results = []
            # 读取压缩包内容
            with open_package_zip(content) as main_zip_ref:
                resource_rows = db.session.query(Resource_usage.computing_id, Resource_usage.dev_get_target).all()
                resources = [{'computing_id': row.computing_id, 'dev_get_target': row.dev_get_target} for row in resource_rows]
                packages = inspect_algorithm_group(main_zip_ref)
                for package in packages.values():
                    require_server_package(package)
                package_devices = {key: require_matching_devices(package, resources, [item.id for item in computing_info])
                                   for key, package in packages.items()}
                # 遍历主压缩包中的所有子压缩包
                for sub_zip_name in packages:
                    if sub_zip_name in packages:
                        # 读取子压缩包
                        result_entry = {  # 初始化单个子压缩包的结果
                            'sub_zip_name': sub_zip_name,
                            'code': 200,
                            'msg': '处理成功',
                            'data': None
                        }
                        with main_zip_ref.open(sub_zip_name) as sub_zip_file:
                            sub_zip_content = sub_zip_file.read()
                            with zipfile.ZipFile(io.BytesIO(sub_zip_content), 'r') as sub_zip_ref:
                                package = packages[sub_zip_name]
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
                                    matched_devices = package_devices[sub_zip_name]
                                    SSH_list = [SSH_Func(item.computing_ip, item.computing_user, item.computing_password)
                                                for item in computing_info if str(item.id) in matched_devices]

                                    trade_type_id = db.session.query(Dict_data.data_id).filter(
                                        func.lower(Dict_data.data_value) == trade).first()
                                    if trade_type_id is None:
                                        result_entry.update(code=400, msg="未找到该厂商，需在厂商编码表中添加")
                                        results.append(result_entry)
                                        continue
                                        # return jsonify({'code': 400, 'msg': '未找到该厂商，需在厂商编码表中添加'})

                                    model_type_name_id = db.session.query(Model_template_config_type.id).filter(
                                        Model_template_config_type.model_type_name == model_type_name).first()
                                    if model_type_name_id is None:
                                        result_entry.update(code=400, msg="未找到该模型大类，需在模型大类表中添加")
                                        results.append(result_entry)
                                        continue
                                        # return jsonify({'code': 400, 'msg': '未找到该模型大类，需在模型大类表中添加'})

                                    model_name_id = next(((row.id,) for row in compatible_model_templates(model_name, analysis_type, model_type_name_id[0])), None)
                                    if model_name_id is None:
                                        result_entry.update(code=400, msg="未找到该模型模板，需在模型名称表中添加")
                                        results.append(result_entry)
                                        continue
                                        # return jsonify({'code': 400, 'msg': '未找到该模型模板，需在模型名称表中添加'})

                                    model_small_name_id = _package_small_template_id(package, model_type_name_id[0])
                                    if model_small_name_id is None:
                                        result_entry.update(code=400, msg="未找到该模型小类，需在模型小类表中添加")
                                        results.append(result_entry)
                                        continue
                                        # return jsonify({'code': 400, 'msg': '未找到该模型小类，需在模型小类表中添加'})

                                    # 提取文件内容
                                    with sub_zip_ref.open(algorithm_filename_old) as file_in_zip:
                                        extracted_file_content = file_in_zip.read()

                                        # 检查算法名称是否重复
                                    name_repeat = db.session.query(Algorithm_library).filter(
                                        Algorithm_library.algorithm_file_name == algorithm_filename,
                                        Algorithm_library.algorithm_name == filename
                                    ).first()
                                    if name_repeat:
                                        result_entry.update(code=400, msg="该算法名称已存在")
                                        results.append(result_entry)
                                        continue
                                        # return jsonify({'code': 400, 'msg': '该算法名称已存在'})

                                    # 上传提取的文件
                                    # 调用上传函数，将文件上传到多个服务器
                                    res = upload_model_with_contract(upload_to_multiple_servers, SSH_list,
                                        extracted_file_content, algorithm_filename, sub_zip_ref, algorithm_filename_old)

                                    if '无法上传文件' not in res and '上传中断，请稍后重试' not in res and '服务器连接异常' not in res:
                                        analysis_type_repeat = _matching_algorithm_slot(package)
                                        if analysis_type_repeat:
                                            # 删除旧算法文件
                                            old_algorithm_path = analysis_type_repeat.algorithm_path
                                            if old_algorithm_path and old_algorithm_path != str(res[0]):
                                                # 遍历所有服务器，删除旧文件
                                                for i in SSH_list:
                                                    try:
                                                        delete_result = i.delete_remote_file(old_algorithm_path)
                                                        print(f'子压缩包 {sub_zip_name}: 删除旧算法文件 {old_algorithm_path}: {delete_result}')
                                                    except Exception as e:
                                                        print(f'子压缩包 {sub_zip_name}: 删除旧文件时发生错误: {e}')
                                            update_data = {
                                                'algorithm_file_name': algorithm_filename,
                                                'algorithm_name': filename,
                                                'analysis_type': analysis_type,
                                                'algorithm_type': algorithm_type,
                                                'algorithm_type_list': str(algorithm_type_list),
                                                'algorithm_status': algorithm_status,
                                                'algorithm_version': algorithm_version,
                                                'algorithm_path': str(res[0]),
                                                'algorithm_trade_type': trade_type_id[0],
                                                'algorithm_ps': algorithm_ps,
                                                'model_type_name': model_type_name,
                                                'model_name': model_name,
                                                'template_small_name': template_small_name,
                                                'create_time': db.func.current_timestamp()
                                            }

                                            # 批量设置属性
                                            for field, value in update_data.items():
                                                setattr(analysis_type_repeat, field, value)
                                            # 同步算法检测标签
                                            existing_labels = db.session.query(Algorithm_test_type).filter(
                                                Algorithm_test_type.Algorithm_library_id == analysis_type_repeat.id
                                            ).all()

                                            # 构建现有标签的字典，key为 (test_type_ename, test_type_cname)
                                            existing_label_map = {}
                                            for label in existing_labels:
                                                key = (label.test_type_ename, label.test_type_cname)
                                                existing_label_map[key] = label

                                            # 构建新标签的集合
                                            new_label_set = set()
                                            for label in labels:
                                                new_label_set.add((label['lable'], label['name']))

                                            # 找出需要删除的标签（在数据库中存在但在新包中不存在）
                                            labels_to_delete = []
                                            for key, label_obj in existing_label_map.items():
                                                if key not in new_label_set:
                                                    labels_to_delete.append(label_obj)

                                            # 找出需要新增的标签（在新包中存在但在数据库中不存在）
                                            labels_to_add = []
                                            for label in labels:
                                                key = (label['lable'], label['name'])
                                                if key not in existing_label_map:
                                                    labels_to_add.append(label)

                                            # 执行删除操作
                                            for label_obj in labels_to_delete:
                                                db.session.delete(label_obj)

                                            # 执行新增操作
                                            for label in labels_to_add:
                                                algorithm_test_type_res = Algorithm_test_type(
                                                    test_type_ename=label['lable'],
                                                    test_type_cname=label['name'],
                                                    Algorithm_library_id=analysis_type_repeat.id
                                                )
                                                db.session.add(algorithm_test_type_res)
                                            db.session.commit()
                                            result_entry.update(msg="升级成功")
                                            result_entry['data'] = {
                                                'algorithm_type_list': analysis_type_repeat.algorithm_type_list,
                                                'algorithm_type': analysis_type_repeat.algorithm_type,
                                                'algorithm_trade_type': analysis_type_repeat.algorithm_trade_type,
                                                'algorithm_version': analysis_type_repeat.algorithm_version,
                                                'filename': analysis_type_repeat.algorithm_name
                                            }
                                            results.append(result_entry)
                                            print(f'子压缩包 {sub_zip_name} 升级完成')
                                        else:
                                            config_data = Algorithm_library(
                                                algorithm_file_name=algorithm_filename,
                                                algorithm_name=filename,
                                                algorithm_type=algorithm_type,
                                                algorithm_type_list=str(algorithm_type_list),
                                                algorithm_status=algorithm_status,
                                                algorithm_version=algorithm_version,
                                                algorithm_path=str(res[0])  ,
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
                                            db.session.commit()

                                            # 将算法检测列表写入检测类型表
                                            for label in labels:
                                                algorithm_test_type_res = Algorithm_test_type(
                                                    test_type_ename=label['lable'],
                                                    test_type_cname=label['name'],
                                                    Algorithm_library_id=config_data.id
                                                )
                                                db.session.add(algorithm_test_type_res)
                                            db.session.commit()
                                            result_entry.update(msg="上传成功")
                                            result_entry['data'] = {
                                                'algorithm_type_list': config_data.algorithm_type_list,
                                                'algorithm_type': config_data.algorithm_type,
                                                'algorithm_trade_type': config_data.algorithm_trade_type,
                                                'algorithm_version': config_data.algorithm_version,
                                                'filename': config_data.algorithm_name
                                            }
                                            results.append(result_entry)
                                    else:
                                        return jsonify({'code': 400, 'msg': '服务器连接异常，请检查算力设备并重新上传！'})
                                else:
                                    return jsonify(
                                        {'code': 400, 'msg': f'子压缩包 {sub_zip_name} 中没有找到兼容的模型文件'})
                succeeded = sum(item.get('code') == 200 for item in results)
                return jsonify({'code': 200 if succeeded else 400,
                                'msg': '算法组包处理完成：成功 %s，失败 %s' % (succeeded, len(results) - succeeded),
                                'data': results})
        else:
            return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})
    except AlgorithmPackageError as error:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': str(error)})
    except (zipfile.BadZipFile, OSError, RuntimeError):
        db.session.rollback()
        return jsonify({'code': 400, 'msg': '无法读取算法压缩包，请检查文件是否损坏'})
    except Exception:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '算法上传失败，请联系管理员检查服务日志'})

def handle_algorithm_upload_single(uploaded_file, algorithm_status, algorithm_ps, computing_ids=None):
    """
    处理算法子包上传逻辑
    """
    def upload_to_multiple_servers(SSH_list, file_content, algorithm_filename):
        """
        上传文件到多个服务器
        :param SSH_list: 包含多个 SSH 对象的列表
        :param file_content: 文件内容
        :param algorithm_filename: 文件名
        :return: 所有服务器的上传路径或错误信息
        """
        upload_results = []

        for i in SSH_list:
            try:
                # 上传文件到服务器
                res = i.upload_send_file(file_content, algorithm_filename)
                if res in ['无法上传文件', '上传中断，请稍后重试','服务器连接异常']:
                    upload_results.append('无法上传文件')
                else:
                    upload_results.append(res)
            except Exception as e:
                upload_results.append('无法上传文件')

        return upload_results

    # 参数

    # 查找设备的所有信息
    computing_query = db.session.query(Computing_equipment).filter(
        Computing_equipment.server_type == 1
    )
    if computing_ids is not None:
        computing_query = computing_query.filter(Computing_equipment.id.in_(computing_ids))
    computing_info = computing_query.all()

    # 创建多个 SSH 实例，表示要上传的服务器
    SSH_list = []  # Build connections only for explicitly compatible devices after package validation.

    try:
        if str(algorithm_status) not in ('1', '2'):
            raise AlgorithmPackageError('算法启用状态必须是运行或停止')
        algorithm_status = str(algorithm_status)
        content = read_uploaded_zip(uploaded_file)

        if uploaded_file and uploaded_file.filename.casefold().endswith('.zip'):

            # 读取压缩包内容
            with open_package_zip(content) as zip_ref:
                resource_rows = db.session.query(Resource_usage.computing_id, Resource_usage.dev_get_target).all()
                resources = [{'computing_id': row.computing_id, 'dev_get_target': row.dev_get_target} for row in resource_rows]
                package = inspect_algorithm_package(zip_ref)
                require_server_package(package)
                matched_devices = require_matching_devices(package, resources, [item.id for item in computing_info])
                # Package and hardware were validated before any SFTP operation.
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
                                for item in computing_info if str(item.id) in matched_devices]

                    trade_type_id = db.session.query(Dict_data.data_id).filter(
                        func.lower(Dict_data.data_value) == trade).first()
                    if trade_type_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该厂商，需在厂商编码表中添加'})

                    model_type_name_id = db.session.query(Model_template_config_type.id).filter(
                        Model_template_config_type.model_type_name == model_type_name).first()
                    if model_type_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型大类，需在模型大类表中添加'})

                    model_name_id = next(((row.id,) for row in compatible_model_templates(model_name, analysis_type, model_type_name_id[0])), None)
                    if model_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型模板，需在模型名称表中添加'})

                    model_small_name_id = _package_small_template_id(package, model_type_name_id[0])
                    if model_small_name_id is None:
                        return jsonify({'code': 400, 'msg': '未找到该模型小类，需在模型小类表中添加'})

                    # 提取文件内容
                    with zip_ref.open(algorithm_filename_old) as file_in_zip:
                        extracted_file_content = file_in_zip.read()

                        # 检查算法名称是否重复
                    name_repeat = db.session.query(Algorithm_library).filter(
                        Algorithm_library.algorithm_file_name == algorithm_filename,
                        Algorithm_library.algorithm_name == filename
                    ).first()
                    if name_repeat:
                        return jsonify({'code': 400, 'msg': '该算法名称已存在'})

                    # 上传提取的文件
                    # 调用上传函数，将文件上传到多个服务器
                    res = upload_model_with_contract(upload_to_multiple_servers, SSH_list,
                        extracted_file_content, algorithm_filename, zip_ref, algorithm_filename_old)
                    if '无法上传文件' not in res and '上传中断，请稍后重试' not in res and '服务器连接异常' not in res:
                        # 数据库操作

                        # analysis_type_repeat = db.session.query(Algorithm_library).filter(
                        #     Algorithm_library.analysis_type == analysis_type
                        # ).first()
                        # algorithm_child_repeat = db.session.query(Algorithm_library).filter(
                        #     Algorithm_library.algorithm_child == alg_child
                        # ).first()
                        analysis_type_repeat = _matching_algorithm_slot(package)

                        if analysis_type_repeat:
                            # 删除旧算法文件
                            old_algorithm_path = analysis_type_repeat.algorithm_path
                            if old_algorithm_path and old_algorithm_path != str(res[0]):
                                # 遍历所有服务器，删除旧文件
                                for i in SSH_list:
                                    try:
                                        delete_result = i.delete_remote_file(old_algorithm_path)
                                        print(f'删除旧算法文件 {old_algorithm_path}: {delete_result}')
                                    except Exception as e:
                                        print(f'删除旧文件时发生错误: {e}')
                            update_data = {
                                'algorithm_file_name': algorithm_filename,
                                'algorithm_name': filename,
                                'analysis_type': analysis_type,
                                'algorithm_type': algorithm_type,
                                'algorithm_type_list' : str(algorithm_type_list),
                                'algorithm_status': algorithm_status,
                                'algorithm_version': algorithm_version,
                                'algorithm_path': str(res[0]),
                                'algorithm_trade_type': trade_type_id[0],
                                'algorithm_ps': algorithm_ps,
                                'model_type_name': model_type_name,
                                'model_name': model_name,
                                'template_small_name': template_small_name,
                                'create_time': db.func.current_timestamp()
                                }

                            # 批量设置属性
                            for field, value in update_data.items():
                                setattr(analysis_type_repeat, field, value)

                            # db.session.query(Algorithm_test_type).filter(
                            #     Algorithm_test_type.Algorithm_library_id == analysis_type_repeat.id
                            # ).delete()
                            # 将算法检测列表写入检测类型表
                            # for label in labels:
                            #     algorithm_test_type_res = Algorithm_test_type(
                            #         test_type_ename=label['lable'],
                            #         test_type_cname=label['name'],
                            #         Algorithm_library_id=analysis_type_repeat.id
                            #     )
                            #     db.session.add(algorithm_test_type_res)
                            # 同步算法检测标签
                            existing_labels = db.session.query(Algorithm_test_type).filter(
                                Algorithm_test_type.Algorithm_library_id == analysis_type_repeat.id
                            ).all()

                            # 构建现有标签的字典，key为 (test_type_ename, test_type_cname)
                            existing_label_map = {}
                            for label in existing_labels:
                                key = (label.test_type_ename, label.test_type_cname)
                                existing_label_map[key] = label

                            # 构建新标签的集合
                            new_label_set = set()
                            for label in labels:
                                new_label_set.add((label['lable'], label['name']))

                            # 找出需要删除的标签（在数据库中存在但在新包中不存在）
                            labels_to_delete = []
                            for key, label_obj in existing_label_map.items():
                                if key not in new_label_set:
                                    labels_to_delete.append(label_obj)

                            # 找出需要新增的标签（在新包中存在但在数据库中不存在）
                            labels_to_add = []
                            for label in labels:
                                key = (label['lable'], label['name'])
                                if key not in existing_label_map:
                                    labels_to_add.append(label)

                            # 执行删除操作
                            for label_obj in labels_to_delete:
                                db.session.delete(label_obj)

                            # 执行新增操作
                            for label in labels_to_add:
                                algorithm_test_type_res = Algorithm_test_type(
                                    test_type_ename=label['lable'],
                                    test_type_cname=label['name'],
                                    Algorithm_library_id=analysis_type_repeat.id
                                )
                                db.session.add(algorithm_test_type_res)
                            db.session.commit()

                            response_data = {
                                'algorithm_type_list': analysis_type_repeat.algorithm_type_list,
                                'algorithm_type': analysis_type_repeat.algorithm_type,
                                'algorithm_trade_type': analysis_type_repeat.algorithm_trade_type,
                                'algorithm_version': analysis_type_repeat.algorithm_version,
                                'filename': analysis_type_repeat.algorithm_name
                            }

                            result = {'code': 200, 'msg': '算法升级完成', 'data': response_data}
                            return jsonify(result)

                        else:
                            config_data = Algorithm_library(
                                    algorithm_file_name=algorithm_filename,
                                    algorithm_name=filename,
                                    algorithm_type=algorithm_type,
                                    algorithm_type_list=str(algorithm_type_list),
                                    algorithm_status=algorithm_status,
                                    algorithm_version=algorithm_version,
                                    algorithm_path=str(res[0]),
                                    algorithm_trade_type=trade_type_id[0],
                                    algorithm_ps=algorithm_ps,
                                    model_type_name=model_type_name,
                                    model_name=model_name,
                                    template_small_name=template_small_name,
                                    algorithm_parent=alg_parent if alg_parent else 1,
                                    algorithm_child=alg_child if alg_child else 1,
                                    analysis_type = analysis_type
                            )
                            db.session.add(config_data)
                            db.session.commit()

                            # 将算法检测列表写入检测类型表
                            for label in labels:
                                algorithm_test_type_res = Algorithm_test_type(
                                    test_type_ename=label['lable'],
                                    test_type_cname=label['name'],
                                    Algorithm_library_id=config_data.id
                                )
                                db.session.add(algorithm_test_type_res)
                            db.session.commit()

                            response_data = {
                                    'algorithm_type_list': config_data.algorithm_type_list,
                                    'algorithm_type': config_data.algorithm_type,
                                    'algorithm_trade_type': config_data.algorithm_trade_type,
                                    'algorithm_version': config_data.algorithm_version,
                                    'filename': config_data.algorithm_name
                            }

                            result = {'code': 200, 'msg': '算法添加完成', 'data': response_data}
                            return jsonify(result)
                    else:
                        return jsonify({'code': 400, 'msg': '服务器连接异常，请检查算力设备并重新上传！'})
                else:
                    return jsonify({'code': 400, 'msg': '压缩包内没有找到兼容的模型文件'})
        else:
            return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})
    except AlgorithmPackageError as error:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': str(error)})
    except (zipfile.BadZipFile, OSError, RuntimeError):
        db.session.rollback()
        return jsonify({'code': 400, 'msg': '无法读取算法压缩包，请检查文件是否损坏'})
    except Exception:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '算法上传失败，请联系管理员检查服务日志'})


def _package_small_template_id(package, model_type_id):
    templates = db.session.query(Model_template_small.id)
    name = package.words[4]
    if (str(model_type_id) == '3' and name == FULL_BODY_COUNT_NAME
            and LEGACY_PERSON_COUNT_NAME in package_upgrade_analysis_types(package)):
        templates = templates.filter(Model_template_small.model_template_config_type_id == model_type_id)
        for candidate_name in (name, LEGACY_PERSON_COUNT_NAME):
            row = templates.filter(Model_template_small.template_small_name == candidate_name).first()
            if row is not None:
                return row
        return None
    return templates.filter(Model_template_small.template_small_name == name).first()


def _matching_algorithm_slot(package):
    for analysis_type in package_upgrade_analysis_types(package):
        candidates = db.session.query(Algorithm_library).filter(
            Algorithm_library.analysis_type == analysis_type).order_by(Algorithm_library.id).all()
        matched = next((row for row in candidates if same_model_slot(row.algorithm_file_name, package)), None)
        if matched is not None:
            return matched
    return None


def parse_algorithm_filename(filename, mine_name):
    """
    解析算法文件名，提取关键字段
    """
    try:
        words = list(split_algorithm_filename_fields(filename.replace('.bmodel', '')))
        words[0] = mine_name
        return {
            'filename': '_'.join(words),
            'analysis_type': words[1],
            'version': words[9],
            'trade': words[7],
            'chip_type': words[8],
            'model_type_name': words[2],
            'model_name': words[3],
            'template_small_name': words[4],
            'alg_parent' : words[10],
            'alg_child' : words[11],
        }
    except Exception:
        return None

def type_select_service(params):
    try:
        mine_id = params.get('mine_id')
        type_param = params.get('type')

        filter_basic = True if type_param == '1' else False
        algorithm_rows = fetch_algorithm_library_basic(type_param)
        algorithm_list = [{
            'id': i.id,
            'algorithm_name': extract_chinese(i.algorithm_name),
            'algorithm_file_name': i.algorithm_file_name,
            'algorithm_type': i.algorithm_type,
            'algorithm_path': i.algorithm_path,
            'model_type_name': i.model_type_name
        } for i in algorithm_rows]

        cascade_rows = fetch_algorithm_library_cascade(type_param)
        algorithm_list_five = [{
            'id': i.id,
            'algorithm_name': extract_chinese(i.algorithm_name),
            'algorithm_file_name': i.algorithm_file_name,
            'algorithm_type': i.algorithm_type,
            'algorithm_path': i.algorithm_path
        } for i in cascade_rows]

        conf_rows = fetch_algorithm_configs_joined(type_param)
        algorithm_conf = [{'id': i.id, 'conf_name': i.conf_name, 'algorithm_path': i.algorithm_path} for i in conf_rows]

        dict_data = convert_folder_to_dict_list(list_dict_data_rows(), ['id', 'data_label', 'data_value', 'type_code', 'enable', 'remark'])
        dict_type = convert_folder_to_dict_list(list_dict_type_rows(), ['id', 'type_name', 'type_code', 'description', 'enable'])
        diagnosis_type_result = convert_folder_to_dict_list(list_diagnosis_type_rows(), ['id', 'name', 'prewarn', 'warn'])

        model_type_template_data_list = []
        model_types = list_model_template_types(type_param)
        for t in model_types:
            template_model_data = convert_folder_to_dict_list(
                list_model_templates_by_type(t.id,type_param),
                ['id', 'model_name', 'model_type', 'model_template_config_type_id', 'model_conf_list', 'created_at', 'updated_at', 'image', 'content']
            )
            model_type_template_data_list.append({
                'id': t.id,
                'model_type_name': t.model_type_name,
                'model_type_content': t.model_type_content,
                'created_at': t.created_at,
                'updated_at': t.updated_at,
                'template_model_data_list': template_model_data,
            })

        model_template = convert_folder_to_dict_list(
            list_model_template_all(type_param),
            ['id', 'model_name', 'model_type', 'image', 'content']
        )

        mine_rows = list_mines_rows()
        mine_list = [{'id': i.id, 'mine_name': i.mine_name} for i in mine_rows]

        if mine_id:
            equipment_rows = list_equipment_root_by_mine(mine_id,type_param)
        else:
            equipment_rows = list_equipment_root_all(type_param)

        equipment_list = []
        for i in equipment_rows:
            rtsp = ''
            if i.equipment_type == '摄像头' or i.equipment_type == 'AI单光摄像头':
                rtsp_mp4_data = get_camera_rtsp(i.equipment_ip)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data.get('rtsp')
            elif i.equipment_type == '录像机':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1, i.equipment_aisles)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data.get('rtsp')
            elif i.equipment_type == '视频中心存储':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data.get('rtsp')
            elif i.equipment_type == '特殊摄像头':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 2)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data.get('rtsp')
            elif i.equipment_type == 'AI双光摄像头':
                rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 2)
                if rtsp_mp4_data:
                    rtsp = rtsp_mp4_data.get('rtsp')
            elif i.equipment_type == '浙江双视热成像':
                rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(i.equipment_uname, i.equipment_password, i.equipment_ip)
            elif i.equipment_type == '安防平台':
                rtsp = i.Hik_rtsp_url
            elif i.equipment_type == '紫光华智':
                rtsp = i.Ziguang_ape_rtsp_url
            equipment_list.append({'id': i.id, 'equipment_name': i.equipment_name, 'equipment_type': i.equipment_type, 'rtsp': rtsp})

        vcr_ids = [it['id'] for it in equipment_list if it['equipment_type'] in ['录像机', '特殊摄像头', '安防平台', '紫光华智', '视频中心存储', 'AI双光摄像头']]
        equipment_list = children_data(equipment_list, vcr_ids)

        if mine_id:
            return {
                'code': 200,
                'msg': '筛选数据',
                'mine_list': mine_list,
                'mine_list_name': '矿数据返回列表',
                'equipment_list': equipment_list,
                'equipment_list_name': '监控点数据返回列表',
                'algorithm_list': algorithm_list,
                'algorithm_list_five': algorithm_list_five,
                'algorithm_list_five_name': '级联模板算法返回列表',
                'algorithm_list_name': '算法数据返回列表',
                'algorithm_conf_list': algorithm_conf,
                'algorithm_conf_list_name': '算法配置返回列表',
                'type_list': configs.type_status,
                'type_list_name': '预警数据返回列表',
                'equipment_type': configs.equipment_type,
                'equipment_type_name': '设备类型数据返回列表',
                'manufacturer_type': configs.manufacturer_type,
                'manufacturer_type_name': '厂商类型数据返回列表',
                'equipment_codetype': configs.equipment_codetype,
                'equipment_codetype_name': '码流类型数据返回列表',
                'vcr_way': configs.vcr_way,
                'vcr_name': '接入方式数据返回列表',
                'dict_data': dict_data,
                'dict_data_name': '字段数据列表',
                'diagnosis_type_result': diagnosis_type_result,
                'diagnosis_type_result_name': '诊断类型列表返回',
                'model_template_name': '模板类型返回列表',
                'model_template': model_template,
                'model_type_template_name': '模板类型大类返回列表',
                'model_type_template': model_type_template_data_list,
            }
        else:
            return {
                'code': 200,
                'msg': '筛选数据',
                'mine_list': mine_list,
                'mine_list_name': '矿数据返回列表',
                'equipment_list': equipment_list,
                'equipment_list_name': '监控点数据返回列表',
                'algorithm_list': algorithm_list,
                'algorithm_list_name': '算法数据返回列表',
                'algorithm_list_five': algorithm_list_five,
                'algorithm_list_five_name': '级联模板算法返回列表',
                'algorithm_conf_list': algorithm_conf,
                'algorithm_conf_list_name': '算法配置返回列表',
                'type_list': configs.type_status,
                'type_list_name': '预警数据返回列表',
                'equipment_type': configs.equipment_type,
                'equipment_type_name': '设备类型数据返回列表',
                'manufacturer_type': configs.manufacturer_type,
                'manufacturer_type_name': '厂商类型数据返回列表',
                'equipment_codetype': configs.equipment_codetype,
                'equipment_codetype_name': '码流类型数据返回列表',
                'vcr_way': configs.vcr_way,
                'vcr_name': '接入方式数据返回列表',
                'dict_data': dict_data,
                'dict_data_name': '字典数据列表',
                'diagnosis_type_result': diagnosis_type_result,
                'diagnosis_type_result_name': '诊断类型列表返回',
                'model_template_name': '模板类型返回列表',
                'model_template': model_template,
                'model_type_template_name': '模板类型大类返回列表',
                'model_type_template': model_type_template_data_list,
            }
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

def upload_to_multiple_servers(ssh_list, file_content, algorithm_filename):
    """
    上传文件到多个服务器
    """
    for ssh in ssh_list:
        try:
            res = ssh.upload_send_file(file_content, algorithm_filename)
            if res not in ['无法上传文件', '上传中断，请稍后重试']:
                return res
        except Exception:
            continue
    return '无法上传文件'

def save_algorithm_data(parsed_info, labels, algorithm_type, upload_result, algorithm_status, algorithm_ps):
    """
    保存算法数据到数据库
    """
    existing_record = db.session.query(Algorithm_library).filter(
        Algorithm_library.analysis_type == parsed_info['analysis_type']
    ).first()

    if existing_record:
        # 更新现有记录
        existing_record.algorithm_file_name = parsed_info['filename']
        existing_record.algorithm_type = algorithm_type
        existing_record.algorithm_path = upload_result
        existing_record.algorithm_status = algorithm_status
        existing_record.algorithm_ps = algorithm_ps
        db.session.commit()
    else:
        # 新增记录
        new_record = Algorithm_library(
            algorithm_file_name=parsed_info['filename'],
            algorithm_name=parsed_info['filename'],
            algorithm_type=algorithm_type,
            algorithm_path=upload_result,
            algorithm_status=algorithm_status,
            algorithm_ps=algorithm_ps,
            analysis_type=parsed_info['analysis_type']
        )
        db.session.add(new_record)
        db.session.commit()

        # 插入检测类型
        for label in labels:
            test_type = Algorithm_test_type(
                test_type_ename=label['lable'],
                test_type_cname=label['name'],
                Algorithm_library_id=new_record.id
            )
            db.session.add(test_type)
        db.session.commit()


redis_client6 = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, db=6)


def fetch_alarm_results(close_signal=None):
    """
    获取报警结果的核心业务逻辑
    :param close_signal: 前端传递的关闭指令 ('true' 或其他)
    :return: 格式化后的报警列表
    """
    # 1. 时间计算
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=8)

    # 2. 获取 Redis 中已展示的 ID
    shown_ids_key = "shown_alarm_ids"
    shown_ids_raw = redis_client6.smembers(shown_ids_key)
    shown_ids = [int(id.decode()) for id in shown_ids_raw] if shown_ids_raw else []

    # 3. 调用数据层查询数据库
    alarm_results = get_unprocessed_alarms(start_time, end_time, shown_ids)

    # 4. 数据格式化 (DTO 转换)
    alarm_list = []
    for row in alarm_results:
        carousel_images = None
        if row.carousel_images_list:
            try:
                img_list = ast.literal_eval(row.carousel_images_list)
                carousel_images = img_list[0] if img_list else None
            except (ValueError, SyntaxError):
                carousel_images = None

        item = {
            'Algorithm_result_id': row.id,
            'equipment_name': row.equipment_name,
            'analysis_type': row.algorithm_name,
            'algorithm_name': row.warning_message if row.warning_message is not None else row.algorithm_name,
            'res_time': row.res_time.strftime('%Y-%m-%d %H:%M:%S'),
            'carousel_images_list': row.carousel_images_list,
            'carousel_images': carousel_images,
            'disposal_status': row.disposal_status,
            'disposal_time': row.disposal_time.strftime('%Y-%m-%d %H:%M:%S') if row.disposal_time else None,
            'disposal_opinion': row.disposal_opinion,
            'approval_status': row.approval_status,
            'approval_opinion': row.approval_opinion,
            'res_type': configs.type_status[int(row.res_type) - 1]['value'] if row.res_type else None,
            'warning_message': row.warning_message,
        }
        alarm_list.append(item)

    # 5. 处理关闭信号业务逻辑
    if close_signal == 'true':
        if alarm_results:
            # 将本次展示的记录 ID 加入缓存
            pipe = redis_client6.pipeline()
            for row in alarm_results:
                pipe.sadd(shown_ids_key, row.id)
            pipe.expire(shown_ids_key, 8 * 3600)  # 设置过期时间为 8 小时
            pipe.execute()

        # 关闭信号下，返回空列表（原逻辑）
        return []

    return alarm_list

# algorithm-first-legacy-guards-v1
import sys as _algorithm_first_sys
from service.algorithm_first_backend import install_creation_guards as _install_algorithm_first_guards
_install_algorithm_first_guards(_algorithm_first_sys.modules[__name__])

# count-template-family-v1

# alarm-calibration-presentation-v1
from service.alarm_presentation import with_passage_regions as _with_passage_regions
algorithm_data_show_service = _with_passage_regions(algorithm_data_show_service)
from service.algorithm_runtime_status import with_runtime_status as _with_runtime_status
algorithm_data_show_service = _with_runtime_status(algorithm_data_show_service)
