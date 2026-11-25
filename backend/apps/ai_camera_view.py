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
from config.zlk_conf import del_stream_proxy, add_stream_proxy
from apps.scheduler_task import flatten_equipment_data
import json
import random
import string
import asyncio
from sqlalchemy.exc import SQLAlchemyError
from service.algorithm_model_service import *
from service.ai_camera_service import *
from service.model_template_conf_service import *
from sqlalchemy import desc, func
from service.equipment_model_service import EquipmentService
import config.configs as configs
from service.scheduler_task_service import SchedulerTaskService,create_zlk_data_for_equipment,delete_zlk_data_for_equipment


# 创建蓝图，对应的register目录
ai_camera_view = Blueprint('ai_camera_view', __name__)

# 单设备数据详情展示接口
@ai_camera_view.route('/equipment_one_info', methods=['GET'])
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
    return jsonify({'code': 200, 'msg': '查询成功', 'data': equipment_info})

@ai_camera_view.route('/equipment_alogrithm_info', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def equipment_alogrithm_info():
    # 查找所传当前设备id
    equipment_id = request.args.get('equipment_id', None)

    if not equipment_id:
        return jsonify({'code': 400, 'msg': '请提供设备ID'})

    try:
        equipment_info=db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if equipment_info.parent_id is None:
            # 查询该设备在AlgorithmLibrary2Camera表中关联的所有算法
            algorithm_rows = db.session.query(
                Algorithm_library_3588.id,
                Algorithm_library_3588.algorithm_name,
                Algorithm_library_3588.algorithm_file_name,
                Algorithm_library_3588.algorithm_type,
                Algorithm_library_3588.algorithm_path,
                Algorithm_library_3588.model_type_name
            ).join(
                AlgorithmLibrary2Camera,
                Algorithm_library_3588.id == AlgorithmLibrary2Camera.algorithm_libary_id
            ).filter(
                AlgorithmLibrary2Camera.equipment_id == equipment_id
            ).all()

            # 组装数据
            algorithm_list = [{
                'id': i.id,
                'algorithm_name': extract_chinese(i.algorithm_name),
                'algorithm_file_name': i.algorithm_file_name,
                'algorithm_type': i.algorithm_type,
                'algorithm_path': i.algorithm_path,
                'model_type_name': i.model_type_name
            } for i in algorithm_rows]

            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': algorithm_list,
                'total': len(algorithm_list)
            })
        else:
            equipment_info1 = db.session.query(Equipment).filter(Equipment.id == equipment_info.parent_id).first()
            # 查询该设备在AlgorithmLibrary2Camera表中关联的所有算法
            algorithm_rows = db.session.query(
                Algorithm_library_3588.id,
                Algorithm_library_3588.algorithm_name,
                Algorithm_library_3588.algorithm_file_name,
                Algorithm_library_3588.algorithm_type,
                Algorithm_library_3588.algorithm_path,
                Algorithm_library_3588.model_type_name
            ).join(
                AlgorithmLibrary2Camera,
                Algorithm_library_3588.id == AlgorithmLibrary2Camera.algorithm_libary_id
            ).filter(
                AlgorithmLibrary2Camera.equipment_id == equipment_info1.id
            ).all()

            # 组装数据
            algorithm_list = [{
                'id': i.id,
                'algorithm_name': extract_chinese(i.algorithm_name),
                'algorithm_file_name': i.algorithm_file_name,
                'algorithm_type': i.algorithm_type,
                'algorithm_path': i.algorithm_path,
                'model_type_name': i.model_type_name
            } for i in algorithm_rows]

            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': algorithm_list,
                'total': len(algorithm_list)
            })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})

# 选择算法，返回算法对应检测类型
@ai_camera_view.route('/Algorithm_type_select', methods=['GET'])
def Algorithm_type_select_aicam():
    algorithm_library_id = request.args.get('id', None)
    result = get_algorithm_type_selection_aicam(algorithm_library_id)
    return jsonify(result)


# 算法管理配置添加接口
@ai_camera_view.route('/algorithm_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_add():
    try:
        result = add_algorithm_config_aicam(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@ai_camera_view.route('/algorithm_add_models', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_add_models():
    try:
        result = add_algorithm_config_models_aicam(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@ai_camera_view.route('/algorithm_update_models', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_update_models():
    try:
        result = update_algorithm_config_models_aicam(request.json or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法管理配置校验名称接口
@ai_camera_view.route('/config_name_check', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def config_name_check():
    conf_name = request.json.get('conf_name', None)
    equipment_id = request.json.get('equipment_id', None)
    conf_data = db.session.query(Algorithm_config_3588).filter(
        Algorithm_config_3588.conf_name == conf_name,
        Algorithm_config_3588.Equipment_id == equipment_id
    ).first()
    if conf_data:
        return jsonify({'code': 400, 'msg': '算法配置名称重复，请重新命名！'})
    else:
        return jsonify({'code': 200, 'msg': '配置名称可用'})


# 算法管理配置修改接口
@ai_camera_view.route('/algorithm_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_update():
    try:
        result = update_algorithm_config_aicam(request.form or {})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法模型运行状态接口
@ai_camera_view.route('/algorithm_status', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_status():
    try:
        result = algorithm_status_service()
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法配置数据返回接口--与单一详情
@ai_camera_view.route('/algorithm_data_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_show():
    try:
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
        result = algorithm_data_show_service_aicam(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})

# 监控点算法配置运行状态
@ai_camera_view.route('/algorithm_conf_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_conf_update():
    try:
        params = {
            'id': request.form.get('id'),
            'status': request.form.get('status'),
            'camera_config_id':request.form.get('camera_config_id')
        }
        result = algorithm_conf_update_service_aicam(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})

# 算法配置数据删除接口
@ai_camera_view.route('/algorithm_data_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_delete():
    try:
        id_payload = request.json.get('id', None)
        result = algorithm_data_delete_service_aicam(id_payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})

@ai_camera_view.route('/algorithm_upload_aicam', methods=['POST'])
def algorithm_upload():
    """
    算法组包上传接口
"""
    uploaded_file = request.files.get('files')
    algorithm_status = request.form.get('algorithm_status')
    algorithm_ps = request.form.get('algorithm_ps')

    if not uploaded_file or not uploaded_file.filename.casefold().endswith('.zip'):
        return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})

    result = handle_algorithm_upload_group_aicam(uploaded_file, algorithm_status, algorithm_ps)
    return result


@ai_camera_view.route('/algorithm_upload_sub_aicam', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_upload_sub_aicam():
    """
    算法子包上传接口
    """
    uploaded_file = request.files.get('files')
    algorithm_status = request.form.get('algorithm_status')
    algorithm_ps = request.form.get('algorithm_ps')
    # equipment_ids = request.form.get('equipment_ids')

    if not uploaded_file or not uploaded_file.filename.casefold().endswith('.zip'):
        return jsonify({'code': 400, 'msg': '文件格式不正确，请导入zip格式压缩包'})

    # result = handle_algorithm_upload_single_aicam(uploaded_file, algorithm_status, algorithm_ps,equipment_ids)
    result = handle_algorithm_upload_single_aicam(uploaded_file, algorithm_status, algorithm_ps)
    return result
@ai_camera_view.route('/algorithm_deploy_aicam', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_deploy_aicam():
    """
    算法下发接口（调用摄像头API部署到设备）
    """
    try:
        payload = request.get_json(silent=True) or {}
        algorithm_libary_id = payload.get('algorithm_libary_id')
        equipment_ids = payload.get('equipment_ids')

        if not algorithm_libary_id:
            return jsonify({'code': 400, 'msg': '请提供算法ID'})

        result = deploy_algorithm_to_cameras(algorithm_libary_id, equipment_ids)
        return result
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})

# 算法仓数据展示编写
@ai_camera_view.route('/algorithm_data_aicam', methods=['GET'])
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
        result = algorithm_data_service_aicam(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})




# 算法仓状态修改
@ai_camera_view.route('/algorithm_data_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_data_update():
    try:
        params = {
            'id': request.form.get('id'),
            'status': request.form.get('status'),
        }
        result = algorithm_data_update_service_aicam(params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


# 算法仓数据删除接口
@ai_camera_view.route('/algorithm_library_delete_aicam', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def algorithm_library_delete():
    try:
        payload = request.get_json(silent=True) or {}
        result = algorithm_library_delete_service_aicam(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})




@ai_camera_view.route('/model_template_small_show_aicam', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_small_show_aicam():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    model_template_type_id = request.args.get('model_template_type_id', type=int)  # 模板大类id

    # 调用服务层方法获取算法类型模板小类列表
    success, result = ModelTemplateConfService.get_model_template_small_list_aicam(page, per_page, model_template_type_id)

    if success:
        return jsonify({'code': 200, 'data': {'code': 200, 'data': result['data'], 'pagination': result['pagination']}})
    else:
        return jsonify({'code': 400, 'msg': result})


# 大类下方小类详情（算法模板管理）
@ai_camera_view.route('/model_small_detail_aicam', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_small_detail_aicam():
    """
    算法类型模板表单详情接口
    参数:
        id (str): 模板ID
    返回:
        JSON响应: 模板详情数据或错误消息
    """

    # 获取模板id
    id = request.args.get('id')

    # 参数校验
    if not id:
        return jsonify({'code': 400, 'msg': '模板ID未填写'})

    # 调用服务层方法获取算法类型模板小类详情
    success, result = ModelTemplateConfService.get_model_template_small_detail_aicam(id)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


@ai_camera_view.route('/algorithm_result_callback', methods=['POST'])
def algorithm_result_callback():
    """
    算法报警数据回传接口
    接收JSON格式的报警数据并入库到Algorithm_result表
    返回:
        JSON响应: 处理结果
    """
    try:
        # 获取JSON数据
        data = request.get_json()
        print(data,'算法报警数据回传接口接收的数据')
        if not data:
            return jsonify({'code': 400, 'msg': '请提供JSON格式的报警数据'})

        # 解析res_time
        res_time_str = data.get('res_time')
        if res_time_str:
            try:
                res_time = datetime.strptime(res_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    res_time = datetime.strptime(res_time_str, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    res_time = datetime.now()
        else:
            res_time = datetime.now()

        # Mine_id默认为1
        mine_id = data.get('Mine_id', 1)

        # 查询mine_name
        mine_info = db.session.query(Mine).filter(Mine.id == mine_id).first()
        mine_name = mine_info.mine_name if mine_info else None

        # 解析Equipment_ip并查询设备信息
        res_type = data.get('res_type')
        equipment_ip = data.get('equipment_ip')
        equipment_id = None
        equipment_parent_id = None
        equipment_name = None
        equipment_type = None

        if equipment_ip:
            equipment_info = db.session.query(Equipment).filter(
                Equipment.equipment_ip == equipment_ip
            ).first()

            if equipment_info:
                print(equipment_info.equipment_name,'12321312')
                equipment_id = equipment_info.id
                equipment_parent_id = equipment_info.parent_id
                equipment_name = equipment_info.equipment_name
                equipment_type = equipment_info.equipment_type
            else:
                return jsonify({
                    'code': 400,
                    'msg': f'该设备不存在'
                })
        # 解析carousel_images_list和ori_images_list
        carousel_images_list = data.get('carousel_images_list')
        ori_images_list = data.get('ori_images_list')
        if carousel_images_list is None:
            carousel_images_list = []

        if ori_images_list is None:
            ori_images_list = []
        # 如果传入的是列表，转换为JSON字符串存储
        if isinstance(carousel_images_list, list):
            carousel_images_list = json.dumps(carousel_images_list, ensure_ascii=False)

        if isinstance(ori_images_list, list):
            ori_images_list = json.dumps(ori_images_list, ensure_ascii=False)
        uwbData = data.get('uwbData')
        print(uwbData, 'uwbData')
        uwb_id_list = []

        # 如果 uwbData 是字符串，先解析为 Python 对象
        if isinstance(uwbData, str):
            try:
                uwbData = json.loads(uwbData)
            except (json.JSONDecodeError, TypeError):
                uwbData = []

        # 现在检查是否为列表并提取 card_id
        if isinstance(uwbData, list):
            uwb_id_list = [item['card_id'] for item in uwbData if isinstance(item, dict) and 'card_id' in item]

        uwb_id_str = json.dumps(uwb_id_list, ensure_ascii=False)


        # 解析其他字段
        template_type_id = data.get('template_type_id')
        template_id = data.get('template_id')
        conf_name = data.get('conf_name')
        algorithm_name = data.get('algorithm_name')
        Exiting_num = data.get('Exiting_num')
        Entering_num = data.get('Entering_num')
        algorithm_idcard = data.get('algorithm_idcard',None)
        warning_message = data.get('warning_message')
        # 创建Algorithm_result记录
        if algorithm_name == '领导换班' and algorithm_idcard:
            for item in lingdaohuanban_result:
                if item['id'] == str(algorithm_idcard):
                    warning_message = item['value']
                    break

        algorithm_result = Algorithm_result(
            result_count_time=data.get('start_time') if data.get('start_time') else None,
            res_time=res_time_str,
            Mine_id=mine_id,
            mine_name=mine_name,
            Equipment_id=equipment_id,
            Equipment_parent_id=equipment_parent_id,
            equipment_name=equipment_name,
            equipment_type=equipment_type,
            carousel_images_list=carousel_images_list,
            ori_images_list=ori_images_list,
            template_type_id=template_type_id,
            template_id=template_id,
            conf_name=conf_name,
            algorithm_name=algorithm_name,
            res_type = res_type,
            Exiting_num = Exiting_num,
            Entering_num = Entering_num,
            uwb_id = uwb_id_str,
            warning_message = warning_message
        )

        # 入库
        db.session.add(algorithm_result)
        db.session.commit()
        # 入库成功后，立即触发语音播报（异步执行，不阻塞接口响应）
        try:
            from service.scheduler_task_service import SchedulerTaskService

            # 检查设备是否配置了语音控制器IP
            if equipment_id and equipment_info and equipment_info.alarm_device_ip:
                res_type_value = int(res_type) if res_type else 999

                # 使用Redis进行快速去重检查
                redis_client_broadcast = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, db=6)
                broadcast_lock_key = f"broadcast_lock_{equipment_id}"

                # 尝试获取播报锁（5秒内同一设备只能播报一次）
                lock_acquired = redis_client_broadcast.set(broadcast_lock_key, str(res_type_value), nx=True, ex=5)

                if lock_acquired:
                    # 成功获取锁，立即播报
                    broadcast_thread = threading.Thread(
                        target=SchedulerTaskService.send_voice_broadcast,
                        args=(equipment_info.alarm_device_ip, warning_message),
                        # kwargs={'volume': 1, 'speed': 5, 'tone': 5, 'voice_type': 3},
                        daemon=True
                    )
                    broadcast_thread.start()
                    print(
                        f"已启动语音播报线程: 设备={equipment_name}, 报警={warning_message}, res_type={res_type_value}")
                else:
                    # 未获取到锁，说明5秒内已有播报
                    existing_res_type = int(redis_client_broadcast.get(broadcast_lock_key).decode())

                    if res_type_value < existing_res_type:
                        # 新报警优先级更高，强制覆盖并播报
                        redis_client_broadcast.setex(broadcast_lock_key, 5, str(res_type_value))

                        broadcast_thread = threading.Thread(
                            target=SchedulerTaskService.send_voice_broadcast,
                            args=(equipment_info.alarm_device_ip, warning_message),
                            # kwargs={'volume': 1, 'speed': 5, 'tone': 5, 'voice_type': 3},
                            daemon=True
                        )
                        broadcast_thread.start()
                        print(
                            f"高优先级报警覆盖播报: 设备={equipment_name}, 原res_type={existing_res_type}, 新res_type={res_type_value}")
                    else:
                        # 优先级相同或更低，跳过播报
                        print(
                            f"设备 {equipment_name} 5秒内已有播报(res_type={existing_res_type})，当前res_type={res_type_value}，跳过")
            else:
                print(f"设备ID {equipment_id} 未配置alarm_device_ip，跳过语音播报")
        except Exception as broadcast_error:
            # 播报失败不影响入库成功，仅记录日志
            print(f"语音播报启动失败: {str(broadcast_error)}")

        return jsonify({
            'code': 200,
            'msg': '报警数据入库成功',
            'data': {
                'id': algorithm_result.id
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'服务器内部错误: {str(e)}'
        })


# 主系统接收回调
@ai_camera_view.route('/model_status_callback', methods=['POST'])
def model_status_callback():
    try:
        data = request.get_json()
        camera_config_id = data.get('conf_id')
        conf_name = data.get('conf_name')
        model_status = data.get('model_status')
        equipment_ip = data.get('equipment_ip')

        if not equipment_ip or not camera_config_id:
            return jsonify({'code': 400, 'msg': '缺少必要参数: equipment_ip 或 camera_config_id'})
        config = db.session.query(Algorithm_config_3588).join(
            Equipment,
            and_(
                Equipment.equipment_ip == equipment_ip,
                Algorithm_config_3588.Equipment_id == Equipment.id
            )
        ).filter(
            Algorithm_config_3588.camera_config_id == camera_config_id
        ).first()


        if config:
            if model_status == 1:
                config.model_status = model_status
                config.conf_status = 1
            else:
                config.model_status = model_status
                db.session.commit()

            return jsonify({
                'code': 200,
                'msg': '同步成功',
            })
        else:
            return jsonify({
                'code': 400,
                'msg':'未同步成功'
            })
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': str(e)})

# 主系统接收回调
@ai_camera_view.route('/algorithm_config_add_callback', methods=['POST'])
def algorithm_config_callback():
    try:
        data = request.get_json()
        camera_config_id = data.get('id')
        conf_name = data.get('conf_name')
        equipment_ip = data.get('local_ip')
        Mine_id = data.get('Mine_id',1)
        Algorithm_library_id = data.get('Algorithm_library_id')
        Equipment_id = data.get('Equipment_id')
        conf_area = data.get('conf_area')
        status = data.get('status')
        test_type_id = data.get('test_type_id')
        shield_status = data.get('shield_status')
        tem_conf_area = data.get('tem_conf_area')
        tem_frames = data.get('tem_frames')
        confidence = data.get('confidence')
        draw_type = data.get('draw_type')
        interval_time = data.get('interval_time', 0)
        img_resolution = data.get('conf_img_resolution')
        duration_time = data.get('duration_time', 0)
        image_draw_type = data.get('image_draw_type', 1)
        Algorithm_config_ps = data.get('Algorithm_config_ps')
        scene_typename = data.get('scene_typename')
        sensitivity = data.get('sensitivity')
        resource_id = None
        defense_time_start = data.get('defense_time_start')
        defense_time_end = data.get('defense_time_end')
        model_template_config_id = data.get('model_template_config_id')
        template_list_area = data.get('template_list_area')
        image_count = data.get('image_count')
        template_small_id = data.get('template_small_id')
        count_time = data.get('count_time', 0)
        res_type = data.get('res_type')
        # computing_id = data.get('computing_id')
        template_data = data.get('template_data')
        label_list = data.get('label_list')
        model_template_type_id = data.get('model_template_type_id')
        amp = data.get('amp', 10)
        alg_select_type = data.get('alg_select_type', 3)
        model_two_type = data.get('model_two_type',0)
        model_two_data = data.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = data.get('priority')
        run_time = data.get('run_time')
        uwb_distance=data.get('uwb_distance')
        cross_line_area = data.get('cross_line_area')
        Entering_num = data.get('Entering_num')
        Exiting_num = data.get('Exiting_num')
        all_Entering_num = data.get('all_Entering_num')
        all_Exiting_num = data.get('all_Exiting_num')

        base_params = [conf_name, Algorithm_library_id, Equipment_id,
                       model_template_config_id, model_template_type_id,equipment_ip]
        if not all(base_params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        # if get_algorithm_config_by_name_aicam(conf_name, Equipment_id):
        #     return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        #
        # if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
        #     return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        #
        # if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
        #     return {'code': 400, 'msg': '算法库id不存在'}

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
            return {'code': 400, 'msg': '未找到指定的设备'}

        # 根据传入的Algorithm_library_id（作为algorithm_camera_id）和Equipment_id查询关联表
        algo_camera_relation = db.session.query(AlgorithmLibrary2Camera).filter(
            and_(
                AlgorithmLibrary2Camera.algorithm_camera_id == Algorithm_library_id,
                AlgorithmLibrary2Camera.equipment_id == equipment.id
            )
        ).first()

        if not algo_camera_relation:
            return {'code': 400, 'msg': '未找到算法与摄像头的关联配置'}

        # 根据computing_resource_id查询算力设备信息
        computing_info = db.session.query(Computing_equipment).filter(
            Computing_equipment.id == algo_camera_relation.computing_resource_id
        ).first()

        # 根据algorithm_libary_id查询算法库信息
        algo_info = db.session.query(Algorithm_library_3588).filter(
            Algorithm_library_3588.id == algo_camera_relation.algorithm_libary_id
        ).first()

        if not algo_info:
            return {'code': 400, 'msg': '未找到对应的算法库信息'}
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
            'model_two_data': model_two_data,
            'priority': priority,
            'run_time': run_time,
            'camera_config_id':camera_config_id,
            'uwb_distance':uwb_distance,
            'cross_line_area':cross_line_area,
            'Entering_num' : Entering_num,
            'Exiting_num' : Exiting_num,
            'all_Entering_num' : all_Entering_num,
            'all_Exiting_num' : all_Exiting_num
        }
        config_obj = insert_algorithm_config_aicam(fields)
        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': str(e)})


@ai_camera_view.route('/algorithm_config_update_callback', methods=['POST'])
def algorithm_update_callback():
    try:
        data = request.get_json()
        camera_config_id = data.get('id')
        conf_name = data.get('conf_name')
        equipment_ip = data.get('local_ip')
        Mine_id = data.get('Mine_id',1)
        Algorithm_library_id = data.get('Algorithm_library_id')
        Equipment_id = data.get('Equipment_id')
        conf_area = data.get('conf_area')
        status = data.get('status')
        test_type_id = data.get('test_type_id')
        shield_status = data.get('shield_status')
        tem_conf_area = data.get('tem_conf_area')
        tem_frames = data.get('tem_frames')
        confidence = data.get('confidence')
        draw_type = data.get('draw_type')
        interval_time = data.get('interval_time', 0)
        img_resolution = data.get('conf_img_resolution')
        duration_time = data.get('duration_time', 0)
        image_draw_type = data.get('image_draw_type', 1)
        Algorithm_config_ps = data.get('Algorithm_config_ps')
        scene_typename = data.get('scene_typename')
        sensitivity = data.get('sensitivity')
        resource_id = None
        defense_time_start = data.get('defense_time_start')
        defense_time_end = data.get('defense_time_end')
        model_template_config_id = data.get('model_template_config_id')
        template_list_area = data.get('template_list_area')
        image_count = data.get('image_count')
        template_small_id = data.get('template_small_id')
        count_time = data.get('count_time', 0)
        res_type = data.get('res_type')
        # computing_id = data.get('computing_id')
        template_data = data.get('template_data')
        label_list = data.get('label_list')
        model_template_type_id = data.get('model_template_type_id')
        amp = data.get('amp', 10)
        alg_select_type = data.get('alg_select_type', 3)
        model_two_type = data.get('model_two_type',0)
        model_two_data = data.get('model_two_data', '{"model_path":"模型路径","algorithm_type_list":[],"label_list":[],"confidence":"置信度"}')
        priority = data.get('priority')
        run_time = data.get('run_time')
        uwb_distance=data.get('uwb_distance')
        cross_line_area = data.get('cross_line_area')
        Entering_num = data.get('Entering_num')
        Exiting_num = data.get('Exiting_num')
        all_Entering_num = data.get('all_Entering_num')
        all_Exiting_num = data.get('all_Exiting_num')
        base_params = [conf_name, Algorithm_library_id, Equipment_id,
                       model_template_config_id, model_template_type_id,equipment_ip]
        if not all(base_params):
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        # if get_algorithm_config_by_name_aicam(conf_name, Equipment_id):
        #     return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        #
        # if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
        #     return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        #
        # if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
        #     return {'code': 400, 'msg': '算法库id不存在'}

        _ = get_mine_by_id(Mine_id)

        # 根据设备ID查询设备IP
        equipment = db.session.query(Equipment).filter(
            Equipment.equipment_ip == equipment_ip
        ).first()
        if int(Equipment_id) == 1:
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
            return {'code': 400, 'msg': '未找到指定的设备'}

        # 根据传入的Algorithm_library_id（作为algorithm_camera_id）和Equipment_id查询关联表
        algo_camera_relation = db.session.query(AlgorithmLibrary2Camera).filter(
            and_(
                AlgorithmLibrary2Camera.algorithm_camera_id == Algorithm_library_id,
                AlgorithmLibrary2Camera.equipment_id == equipment.id
            )
        ).first()

        if not algo_camera_relation:
            return {'code': 400, 'msg': '未找到算法与摄像头的关联配置'}

        # 根据computing_resource_id查询算力设备信息
        computing_info = db.session.query(Computing_equipment).filter(
            Computing_equipment.id == algo_camera_relation.computing_resource_id
        ).first()

        # 根据algorithm_libary_id查询算法库信息
        algo_info = db.session.query(Algorithm_library_3588).filter(
            Algorithm_library_3588.id == algo_camera_relation.algorithm_libary_id
        ).first()

        if not algo_info:
            return {'code': 400, 'msg': '未找到对应的算法库信息'}
        id = db.session.query(Algorithm_config_3588).filter(
            Algorithm_config_3588.camera_config_id == camera_config_id,
            Algorithm_config_3588.Equipment_id == equ_id.id
        ).first()

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
            'model_two_data': model_two_data,
            'priority': priority,
            'run_time': run_time,
            'camera_config_id':camera_config_id,
            'uwb_distance':uwb_distance,
            'cross_line_area':cross_line_area,
            'Entering_num': Entering_num,
            'Exiting_num': Exiting_num,
            'all_Entering_num': all_Entering_num,
            'all_Exiting_num': all_Exiting_num
        }
        update_algorithm_config_fields_aicam(id.id, fields)
        return {'code': 200, 'msg': '算法配置数据修改完成'}

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({'code': 500, 'msg': str(e)})


@ai_camera_view.route('/algorithm_config_del_callback', methods=['POST'])
def algorithm_del_callback():
    try:
        data = request.get_json()
        id_payload = data.get('id')
        equipment_ip = data.get('local_ip')
        id_list = id_payload if isinstance(id_payload, list) else None
        if not id_list:
            return {'code': 400, 'msg': '缺少配置id参数'}
        ids = [item for item in id_list]
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
            Algorithm_config_3588.camera_config_id.in_(ids),
            Equipment.equipment_ip == equipment_ip
        ).all()

        if not configs_to_delete:
            return {'code': 404, 'msg': '未找到相关配置'}
        # 提取查到的所有配置的主键 ID
        config_ids = [config.id for config in configs_to_delete]

        # 使用 delete().where() 语法根据 ID 列表进行批量删除
        deleted_count = db.session.execute(
            db.delete(Algorithm_config_3588).where(Algorithm_config_3588.id.in_(config_ids))
        ).rowcount

        # 提交事务，真正执行数据库的删除操作
        db.session.commit()

        return {'code': 200, 'msg': f'成功删除 {deleted_count} 条配置信息'}
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': str(e)})


@ai_camera_view.route('/config_statusup_callback', methods=['POST'])
def config_statusup_callback():
    try:
        data = request.get_json()
        cam_conf_id = data.get('id')
        status = data.get('status')
        equipment_ip = data.get('local_ip')
        if not cam_conf_id:
            return {'code': 400, 'msg': '缺少配置id参数'}
        data = db.session.query(Algorithm_config_3588).join(
            Equipment,
            and_(
                Equipment.equipment_ip == equipment_ip,
                Algorithm_config_3588.Equipment_id == Equipment.id
            )
        ).filter(
            Algorithm_config_3588.camera_config_id == cam_conf_id
        ).first()

        if not data:
            return {'code': 400, 'msg': '未找到指定的配置'}

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
            'msg': '修改成功'
        }
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}


# 主系统接收回调
@ai_camera_view.route('/algorithm_config_add_models_callback', methods=['POST'])
def algorithm_config_models_callback():
    try:
        payload = request.json
        equipment_ip = payload.get('local_ip')
        camera_config_id = payload.get('id')
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id', 1) or 1
        Equipment_id = payload.get('Equipment_id')
        model_data = payload.get('model_data', [])
        uwb_distance = payload.get('uwb_distance')
        if not all([conf_name, Equipment_id]) or not model_data:
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        equipment = db.session.query(Equipment).filter(
            Equipment.equipment_ip == equipment_ip
        ).first()
        if Equipment_id == 1:
            equ_id = db.session.query(Equipment).filter(
                Equipment.code == '101',
                Equipment.equipment_ip == equipment_ip,
            ).first()
        else:

            equ_id = db.session.query(Equipment).filter(
                Equipment.code == '201',
                Equipment.equipment_ip == equipment_ip,
            ).first()
        if not equipment and not equ_id:
            return {'code': 400, 'msg': '未找到指定的设备'}

        #处理模型数据
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
                return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

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
        # if get_algorithm_config_by_name_aicam(conf_name,Equipment_id):
        #     return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        # if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
        #     return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        # if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
        #     return {'code': 400, 'msg': '算法库id不存在'}
        _ = get_mine_by_id(Mine_id)

        #额外model数据
        extra_models_data = []
        for i in range(1, len(model_data_camera)):
            model = model_data_camera[i]
            print(model,type(model),model.get('conf_area', []),type(model.get('conf_area', [])),'222222222222222')
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
            'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
            'model_algo_data_ori': json.dumps(model_data_camera[1:], ensure_ascii=False) if len(model_data) > 1 else '',
            'multimodels_type': 1,
            'camera_config_id': camera_config_id,
            'uwb_distance': uwb_distance
        }
        insert_algorithm_config_aicam(fields)

        return {'code': 200, 'msg': '算法配置数据添加完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

# 主系统接收回调
@ai_camera_view.route('/algorithm_config_update_models_callback', methods=['POST'])
def algorithm_config_update_models_callback():
    try:
        payload = request.json
        equipment_ip = payload.get('local_ip')
        camera_config_id = payload.get('id')
        conf_name = payload.get('conf_name')
        Mine_id = payload.get('Mine_id', 1) or 1
        Equipment_id = payload.get('Equipment_id')
        model_data = payload.get('model_data', [])
        uwb_distance = payload.get('uwb_distance')
        if not all([conf_name, Equipment_id]) or not model_data:
            return {'code': 400, 'msg': '算法配置数据有未填写项'}

        equipment = db.session.query(Equipment).filter(
            Equipment.equipment_ip == equipment_ip
        ).first()
        if Equipment_id == 1:
            equ_id = db.session.query(Equipment).filter(
                Equipment.code == '101',
                Equipment.equipment_ip == equipment_ip,
            ).first()
        else:

            equ_id = db.session.query(Equipment).filter(
                Equipment.code == '201',
                Equipment.equipment_ip == equipment_ip,
            ).first()
        if not equipment and not equ_id:
            return {'code': 400, 'msg': '未找到指定的设备'}
        conf_id = db.session.query(Algorithm_config_3588).filter(
            Algorithm_config_3588.camera_config_id == camera_config_id,
            Algorithm_config_3588.Equipment_id == equ_id.id
        ).first()
        #处理模型数据
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
                return {'code': 400, 'msg': '关联记录中未保存摄像头算法ID'}

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
        # if get_algorithm_config_by_name_aicam(conf_name,Equipment_id):
        #     return {'code': 400, 'msg': '算法配置名称重复，请重新命名！'}
        # if get_algorithm_config_by_equipment_and_library_aicam(Equipment_id, Algorithm_library_id):
        #     return {'code': 400, 'msg': '该监控点下已存在该算法配置，请重新设置！'}
        # if not get_algorithm_library_by_id_aicam(Algorithm_library_id):
        #     return {'code': 400, 'msg': '算法库id不存在'}
        _ = get_mine_by_id(Mine_id)

        #额外model数据
        extra_models_data = []
        for i in range(1, len(model_data_camera)):
            model = model_data_camera[i]
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
            print(model,type(model),model.get('conf_area', []),type(model.get('conf_area', [])),'1111111111111111111')
            extra_model_data = {
                'Algorithm_library_id': model.get('Algorithm_library_id'),
                'algorithm_path': algorithm_info.algorithm_path if algorithm_info else '',
                'conf_area': conf_area_data,
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
            # 'status': status,
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
            # 'resource_id': resource_id,
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
            # 'model_two_type': model_two_type,
            # 'model_two_data': model_two_data,
            'priority': priority,
            'run_time': run_time,
            'model_algo_data': json.dumps(extra_models_data, ensure_ascii=False) if extra_models_data else '',
            'model_algo_data_ori': json.dumps(model_data_camera[1:], ensure_ascii=False) if len(model_data) > 1 else '',
            'multimodels_type': 1,
            'camera_config_id': camera_config_id,
            'uwb_distance': uwb_distance
        }
        update_algorithm_config_fields_aicam(conf_id.id, fields)

        return {'code': 200, 'msg': '算法配置数据修改完成'}
    except Exception as e:
        db.session.rollback()
        return {'code': 500, 'msg': f'服务器内部错误: {str(e)}'}

# 算法管理配置添加接口
@ai_camera_view.route('/algorithm_sync_aicam', methods=['POST'])
# @jwt_required()
# @jwt_required_with_refresh
def sync_aicam():
    try:
        equipment_id = request.json.get('equipment_id', None)
        result = algorithm_sync_aicam(equipment_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'})


@ai_camera_view.route('/image_calibration', methods=['POST'])
def image_calibration():
    try:
        point_data = request.json.get('point_data', None)
        result = image_calibration_service(point_data)
        return jsonify(result), result.get('code', 200)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500
