# native-diagnosis-status-v1
from data.scheduler_task_data import SchedulerTaskData
from tool.VQD import *
from config.configs import *
import config.configs as configs # 导入模型字段
import json
import ast
from service.equipment_model_service import delete_zlk_data_for_equipment, create_zlk_data_for_equipment
from datetime import datetime, timedelta, date
from config.configs import SSH_Func
from data.zlmediakit_data import ZLMediaKitData
from flask import Blueprint, jsonify, request, current_app
from socket import AF_INET, SOCK_STREAM, socket
class SchedulerTaskService:
    # 定时任务相关业务逻辑
    @staticmethod
    def add_task(name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status):
        """
        添加定时任务
        """
        try:
            # 验证必要参数
            if not name or not interval_seconds:
                return False, '缺少必要的参数'

            # 创建新任务
            new_task = SchedulerTaskData.create_task(
                name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status
            )

            return True, new_task
        except Exception as e:
            return False, f'添加任务失败: {str(e)}'

    @staticmethod
    def update_task(task_id, name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status):
        """
        更新定时任务
        """
        try:
            # 验证任务是否存在
            task = SchedulerTaskData.get_task_by_id(task_id)
            if not task:
                return False, '任务不存在'

            # 更新任务
            updated_task = SchedulerTaskData.update_task(
                task_id, name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status
            )

            return True, updated_task
        except Exception as e:
            return False, f'更新任务失败: {str(e)}'

    @staticmethod
    def delete_task(task_id):
        """
        删除定时任务
        """
        try:
            # 解析任务ID列表
            if isinstance(task_id, str):
                task_ids = eval(task_id)
                if not isinstance(task_ids, list):
                    return False, 'id不为所传参数校验标准'
            else:
                return False, 'id不为所传参数校验标准'

            # 批量删除任务
            for id in task_ids:
                task = SchedulerTaskData.get_task_by_id(id)
                if not task:
                    return False, '任务不存在'
                SchedulerTaskData.delete_task(id)

            return True, '任务已删除'
        except Exception as e:
            return False, f'删除任务失败: {str(e)}'

    @staticmethod
    def get_tasks(page=1, per_page=15, name=None, time_type=None, scheduled_status=None):
        """
        获取定时任务列表
        """
        try:
            pagination = SchedulerTaskData.get_all_tasks(page, per_page, name, time_type, scheduled_status)

            # 转换为字典列表
            res_data = [{
                'id': i.id,
                'name': i.name,
                'interval_seconds': i.interval_seconds,
                'next_run_time': i.next_run_time,
                'create_time': (i.create_time).strftime("%Y-%m-%d %H:%M:%S"),
                'time_type': i.time_type,
                'rtsp_list': i.rtsp_list,
                'diagnosis_type_list': i.diagnosis_type_list,
                'scheduled_concent': i.scheduled_concent,
                'scheduled_status': '启用' if str(i.scheduled_status) == '1' else '禁用',
            } for i in pagination.items]

            response_data = {
                'total_items': pagination.total,
                'total_pages': pagination.pages,
                'current_page': pagination.page,
                'per_page': per_page,
                'data': res_data,
            }

            return True, response_data
        except Exception as e:
            return False, f'获取任务列表失败: {str(e)}'

    @staticmethod
    def get_task_detail(task_id):
        """
        获取定时任务详情
        """
        try:
            task = SchedulerTaskData.get_task_by_id(task_id)
            if not task:
                return False, '该数据不存在'

            res_data = {
                'id': task.id,
                'name': task.name,
                'interval_seconds': task.interval_seconds,
                'next_run_time': task.next_run_time,
                'create_time': (task.create_time).strftime("%Y-%m-%d %H:%M:%S"),
                'time_type': task.time_type,
                'rtsp_list': json.loads(task.rtsp_list) if task.rtsp_list else [],
                'diagnosis_type_list': json.loads(task.diagnosis_type_list) if task.diagnosis_type_list else [],
                'scheduled_concent': task.scheduled_concent,
                'scheduled_status': '启用' if str(task.scheduled_status) == '1' else '禁用',
            }

            return True, res_data
        except Exception as e:
            return False, f'获取任务详情失败: {str(e)}'

    # 诊断数据相关业务逻辑
    @staticmethod
    def perform_diagnostic_task(data):
        """
        执行诊断任务
        """
        try:
            # 调用数据层方法处理诊断数据
            success, message = SchedulerTaskData.perform_diagnostic_task(data)
            if success:
                return True, '诊断数据上传完成！'
            else:
                return False, message
        except Exception as e:
            return False, f'执行诊断任务失败: {str(e)}'

    # 设备数据处理业务逻辑
    @staticmethod
    def replace_null_with_none(data):
        """
        递归遍历 JSON，将 null 替换为 None
        """
        if isinstance(data, dict):  # 处理字典
            return {key: SchedulerTaskService.replace_null_with_none(value) for key, value in data.items()}
        elif isinstance(data, list):  # 处理列表
            return [SchedulerTaskService.replace_null_with_none(item) for item in data]
        elif data is None:  # 处理 null（JSON 的 null -> Python 的 None）
            return None
        else:
            return data  # 其他数据类型直接返回

    @staticmethod
    def flatten_equipment_data(tree_data):
        """
        将设备树数据转换为扁平化列表
        """
        try:
            # 先替换 null -> None
            tree_data = SchedulerTaskService.replace_null_with_none(tree_data)

            flat_list = []

            def extract_info(node, parent_ip=None, parent_name=None):
                """
                递归提取设备信息
                """
                if node.get('equipment_type') == '录像机' and node.get("rtsp"):
                    flat_list.append({
                        "id": node["id"],
                        "ip": node["equipment_ip"],
                        "name": node["equipment_name"],
                        "parent_ip": node.get("parent_id"),
                        "rtsp": node.get("rtsp", ""),
                        "parent_name": parent_name,
                    })
                if node.get('equipment_type') == '视频中心存储' and node.get("rtsp"):
                    flat_list.append({
                        "id": node["id"],
                        "ip": node["equipment_ip"],
                        "name": node["equipment_name"],
                        "parent_ip": node.get("parent_id"),
                        "rtsp": node.get("rtsp", ""),
                        "parent_name": parent_name,
                    })
                if node.get('equipment_type') == '摄像头':
                    flat_list.append({
                        "id": node["id"],
                        "ip": node["equipment_ip"],
                        "name": node["equipment_name"],
                        "parent_ip": parent_ip,
                        "rtsp": f'rtsp://{node.get("equipment_uname")}:{node.get("equipment_password")}@{node.get("equipment_ip")}',
                        "parent_name": '摄像头',
                    })

                if node.get('equipment_type') == '安防平台' and node.get("rtsp"):
                    flat_list.append({
                        "id": node["id"],
                        "ip": node["equipment_ip"],
                        "name": node["equipment_name"],
                        "parent_ip": node.get('parent_id'),
                        "rtsp": node.get("rtsp", ""),
                        "parent_name": parent_name,
                    })

                # 递归处理子设备
                for child in node.get("children", []):
                    extract_info(child, node["equipment_ip"], node["equipment_name"])

            # 遍历根节点
            for root in tree_data:
                extract_info(root)

            return True, flat_list
        except Exception as e:
            return False, f'扁平化设备数据失败: {str(e)}'

    # 任务运行相关业务逻辑
    @staticmethod
    def run_task(task_id, task_name, task_interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status):
        """
        运行诊断任务
        """
        try:
            # 扁平化转换设备数据
            tree_data = json.loads(rtsp_list)
            success, flat_result = SchedulerTaskService.flatten_equipment_data(tree_data)
            if not success:
                return False, flat_result

            try:
                diagnosis_types = json.loads(diagnosis_type_list)
            except (ValueError, TypeError):
                diagnosis_types = ast.literal_eval(diagnosis_type_list)
            # 运行诊断
            res = VQD.run(
                flat_result, 
                diagnosis_types,
                configs.sftp_path, 
                configs.Box_ip, 
                configs.sftp_port, 
                configs.Box_user, 
                configs.Box_password
            )
            # The dispatcher owns the application context before any DB work.
            success, message = SchedulerTaskService.perform_diagnostic_task(res)
            if not success:
                return False, message

            return True, '诊断任务执行成功！'
        except Exception as e:
            return False, f'运行任务时发生异常: {str(e)}'

    @staticmethod
    def update_camera_online_status_task():
        try:
            cameras = SchedulerTaskData.get_independent_cameras()
            if not cameras:
                return True, '摄像头不存在！'
            status_by_id = {}
            for camera in cameras:
                pinger = Pinger(target_host=camera.equipment_ip)
                delay = pinger.ping_once()
                status_by_id[camera.id] = 1 if delay is not None else 0
            ok = SchedulerTaskData.set_cameras_online_status(status_by_id)
            if ok:
                return True, '摄像头设备状态更新完成！'
            return False, '数据库操作失败'
        except Exception as e:
            return False, f'更新失败: {str(e)}'

    @staticmethod
    def update_vcr_equipment_task():
        try:
            result = {'deleted': 0, 'created': 0, 'failed': []}
            vcr_list = SchedulerTaskData.get_vcr_list_by_type(1)
            if not vcr_list:
                return True, '暂无录像机数据'
            for vcr in vcr_list:
                try:
                    pinger = Pinger(target_host=vcr.vcr_ip)
                    delay = pinger.ping_once()
                    if delay is None:
                        eqs = SchedulerTaskData.get_equipments_by_vcr(vcr.id)
                        for eq in eqs:
                            try:
                                if eq.zlk_dat_id:
                                    result['deleted'] += delete_zlk_data_for_equipment(eq.id)
                                    SchedulerTaskData.update_equipment_fields(eq.id, {'zlk_dat_id': None})
                            except Exception as e:
                                result['failed'].append(f"删除设备 {eq.id} 流媒体失败: {str(e)}")
                        SchedulerTaskData.set_vcr_online(vcr.id, 0)
                        for eq in eqs:
                            SchedulerTaskData.update_equipment_fields(eq.id, {'online': 0})
                    else:
                        SchedulerTaskData.set_vcr_online(vcr.id, 1)
                        SchedulerTaskData.set_equipments_online_by_vcr_parent(vcr.id, 1)
                        parent_eq = SchedulerTaskData.get_parent_equipment_by_vcr(vcr.id)
                        if not parent_eq:
                            result['failed'].append(f"录像机 {vcr.vcr_ip} 未找到父设备")
                            continue
                        try:
                            # 只有当设备没有 zlk_dat_id 时才创建
                            if not parent_eq.zlk_dat_id:
                                zlk_data_id = create_zlk_data_for_equipment(parent_eq)
                                if zlk_data_id:
                                    SchedulerTaskData.update_equipment_fields(parent_eq.id, {'zlk_dat_id': zlk_data_id})
                                    result['created'] += 1
                        except Exception as e:
                            result['failed'].append(f"创建父设备流媒体失败: {str(e)}")
                        manufacturer_type = parent_eq.manufacturer_type
                        if manufacturer_type == '海康':
                            external_list = VCR_data_info(vcr.vcr_username, vcr.vcr_password, vcr.vcr_ip, vcr.vcr_port)
                            if not external_list:
                                result['failed'].append(f'录像机 {vcr.vcr_ip} 数据不存在或账密错误！')
                                continue
                            external_ips = [i.get('ip_address') for i in external_list]
                            db_children = SchedulerTaskData.get_child_equipments_by_vcr(vcr.id)
                            for child in db_children:
                                if child.equipment_ip not in external_ips:
                                    try:
                                        if child.zlk_dat_id:
                                            delete_zlk_data_for_equipment(child.id)
                                            result['deleted'] += 1
                                        SchedulerTaskData.delete_equipment_by_id(child.id)
                                    except Exception as e:
                                        result['failed'].append(f"删除海康设备 {child.id} 失败: {str(e)}")
                            db_children_dict = {d.equipment_ip: d for d in db_children}
                            for i in external_list:
                                try:
                                    ip_address = i['ip_address']
                                    name = i['name']
                                    channelName = i.get('channelName', '')
                                    online = 1 if i['online'] == 'true' else 0
                                    width_height = f"{i.get('videoResolutionWidth', '')}x{i.get('videoResolutionHeight', '')}" if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                                    videoCodecType = 'H265' if i.get('videoCodecType') == 'H.265' else 'H264' if i.get('videoCodecType') == 'H.264' else None
                                    constantBitRate = i.get('constantBitRate', '')
                                    maxFrameRate = i.get('maxFrameRate', '')
                                    if ip_address in db_children_dict:
                                        db_device = db_children_dict[ip_address]
                                        SchedulerTaskData.update_equipment_fields(db_device.id, {
                                            'equipment_name': name,
                                            'online': online,
                                            'equipment_ip': ip_address,
                                            'equipment_aisles': i['id'],
                                            'code': channelName,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                        })
                                        if online:
                                            # 只有当设备没有 zlk_dat_id 时才创建
                                            if not db_device.zlk_dat_id:
                                                zlk_id = create_zlk_data_for_equipment(db_device)
                                                if zlk_id:
                                                    SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': zlk_id})
                                                    result['created'] += 1
                                        else:
                                            if db_device.zlk_dat_id:
                                                delete_zlk_data_for_equipment(db_device.id)
                                                SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': None})
                                                result['deleted'] += 1
                                    else:
                                        new_device = SchedulerTaskData.add_equipment({
                                            'VCR_data_id': vcr.id,
                                            'parent_id': parent_eq.id,
                                            'equipment_aisles': i['id'],
                                            'equipment_name': name,
                                            'equipment_ip': ip_address,
                                            'online': online,
                                            'code': channelName,
                                            'equipment_type': '录像机',
                                            'manufacturer_type': '海康',
                                            'equipment_uname': vcr.vcr_username,
                                            'equipment_password': vcr.vcr_password,
                                            'user_status': '1',
                                            'create_time': datetime.now(),
                                            'Mine_id': vcr.Mine_id,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                        })
                                        if new_device and online:
                                            zlk_id = create_zlk_data_for_equipment(new_device)
                                            if zlk_id:
                                                SchedulerTaskData.update_equipment_fields(new_device.id, {'zlk_dat_id': zlk_id})
                                                result['created'] += 1
                                except Exception as e:
                                    result['failed'].append(f"处理海康设备 {i.get('ip_address')} 失败: {str(e)}")
                        elif manufacturer_type == '宇视':
                            external_list = YSVCR_data_info(vcr.vcr_username, vcr.vcr_password, vcr.vcr_ip, vcr.vcr_port)
                            if not external_list:
                                result['failed'].append(f'录像机 {vcr.vcr_ip} 数据不存在或账密错误！')
                                continue
                            external_ips = [i.get('ip_address').strip() for i in external_list if i.get('ip_address')]
                            db_children = SchedulerTaskData.get_child_equipments_by_vcr(vcr.id)
                            for child in db_children:
                                if child.equipment_ip not in external_ips:
                                    try:
                                        if child.zlk_dat_id:
                                            delete_zlk_data_for_equipment(child.id)
                                            result['deleted'] += 1
                                        SchedulerTaskData.delete_equipment_by_id(child.id)
                                    except Exception as e:
                                        result['failed'].append(f"删除宇视设备 {child.id} 失败: {str(e)}")
                            db_children_dict = {d.equipment_ip: d for d in db_children}
                            for i in external_list:
                                try:
                                    ip_address = i['ip_address'].strip() if i.get('ip_address') else ''
                                    if not ip_address:
                                        continue
                                    name = i['name']
                                    channelName = i.get('channelName', '')
                                    online = i['online']
                                    width_height = f"{i.get('videoResolutionWidth', '')}x{i.get('videoResolutionHeight', '')}" if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                                    videoCodecType = 'H265' if i.get('videoCodecType') == 'H.265' else 'H264' if i.get('videoCodecType') == 'H.264' else i.get('videoCodecType') if i.get('videoCodecType') in ['MJPEG', 'H.264', 'H.265'] else None
                                    constantBitRate = i.get('constantBitRate', '')
                                    maxFrameRate = i.get('maxFrameRate', '')
                                    code = str(i.get('id')) + '01'
                                    if ip_address in db_children_dict:
                                        db_device = db_children_dict[ip_address]
                                        SchedulerTaskData.update_equipment_fields(db_device.id, {
                                            'equipment_name': name,
                                            'online': online,
                                            'equipment_ip': ip_address,
                                            'equipment_aisles': i['id'],
                                            'code': code,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                        })
                                        if online:
                                            # 只有当设备没有 zlk_dat_id 时才创建
                                            if not db_device.zlk_dat_id:
                                                zlk_id = create_zlk_data_for_equipment(db_device)
                                                if zlk_id:
                                                    SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': zlk_id})
                                                    result['created'] += 1
                                        else:
                                            if db_device.zlk_dat_id:
                                                delete_zlk_data_for_equipment(db_device.id)
                                                SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': None})
                                                result['deleted'] += 1
                                    else:
                                        if SchedulerTaskData.find_equipment_by_ip(ip_address):
                                            continue
                                        new_device = SchedulerTaskData.add_equipment({
                                            'VCR_data_id': vcr.id,
                                            'parent_id': parent_eq.id,
                                            'equipment_aisles': i['id'],
                                            'equipment_name': name,
                                            'equipment_ip': ip_address,
                                            'online': online,
                                            'code': code,
                                            'equipment_type': '录像机',
                                            'manufacturer_type': YSNVR_manufacturer_type.get(i.get('Manufacturer'), None) if i.get('Manufacturer') else None,
                                            'equipment_uname': vcr.vcr_username,
                                            'equipment_password': vcr.vcr_password,
                                            'user_status': '1',
                                            'create_time': datetime.now(),
                                            'Mine_id': vcr.Mine_id,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                        })
                                        if new_device and online:
                                            zlk_id = create_zlk_data_for_equipment(new_device)
                                            if zlk_id:
                                                SchedulerTaskData.update_equipment_fields(new_device.id, {'zlk_dat_id': zlk_id})
                                                result['created'] += 1
                                except Exception as e:
                                    result['failed'].append(f"处理宇视设备 {i.get('ip_address')} 失败: {str(e)}")
                        elif manufacturer_type == '大华':
                            external_list = Dahua_data_info(vcr.vcr_username, vcr.vcr_password, vcr.vcr_ip, vcr.vcr_port)
                            if not external_list:
                                result['failed'].append(f'录像机 {vcr.vcr_ip} 数据不存在或账密错误！')
                                continue
                            external_names = [i.get('name') for i in external_list]
                            db_children = SchedulerTaskData.get_child_equipments_by_vcr(vcr.id)
                            for child in db_children:
                                if child.equipment_name not in external_names:
                                    try:
                                        if child.zlk_dat_id:
                                            delete_zlk_data_for_equipment(child.id)
                                            result['deleted'] += 1
                                        SchedulerTaskData.delete_equipment_by_id(child.id)
                                    except Exception as e:
                                        result['failed'].append(f"删除大华设备 {child.id} 失败: {str(e)}")
                            db_children_dict = {d.equipment_name: d for d in db_children}
                            for i in external_list:
                                try:
                                    ip_address = i.get('ip_address', '').strip()
                                    name = i['name']
                                    online = i.get('online', 1)
                                    width_height = f"{str(i.get('videoResolutionWidth', ''))}x{str(i.get('videoResolutionHeight', ''))}" if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                                    videoCodecType = 'H265' if i.get('videoCodecType') == 'H.265' else 'H264' if i.get('videoCodecType') == 'H.264' else i.get('videoCodecType') if i.get('videoCodecType') in ['MJPEG', 'H.264', 'H.265'] else None
                                    constantBitRate = i.get('constantBitRate', '')
                                    maxFrameRate = i.get('maxFrameRate', '')
                                    Onvif_rtsp_url = i.get('main_stream_uri', '')
                                    code = str(i.get('id')) + '01'
                                    aisles = int(i['id']) + 1 if i.get('id') and str(i.get('id')).isdigit() else None
                                    if name in db_children_dict:
                                        db_device = db_children_dict[name]
                                        SchedulerTaskData.update_equipment_fields(db_device.id, {
                                            'equipment_name': name,
                                            'online': online,
                                            'equipment_ip': ip_address,
                                            'equipment_aisles': aisles,
                                            'code': code,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                            'Onvif_rtsp_url': Onvif_rtsp_url,
                                        })
                                        if online:
                                            # 只有当设备没有 zlk_dat_id 时才创建
                                            if not db_device.zlk_dat_id:
                                                zlk_id = create_zlk_data_for_equipment(db_device)
                                                if zlk_id:
                                                    SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': zlk_id})
                                                    result['created'] += 1
                                        else:
                                            if db_device.zlk_dat_id:
                                                delete_zlk_data_for_equipment(db_device.id)
                                                SchedulerTaskData.update_equipment_fields(db_device.id, {'zlk_dat_id': None})
                                                result['deleted'] += 1
                                    else:
                                        if SchedulerTaskData.find_equipment_by_name(name):
                                            continue
                                        new_device = SchedulerTaskData.add_equipment({
                                            'VCR_data_id': vcr.id,
                                            'parent_id': parent_eq.id,
                                            'equipment_aisles': aisles,
                                            'equipment_name': name,
                                            'equipment_ip': ip_address,
                                            'online': online,
                                            'code': code,
                                            'equipment_type': '录像机',
                                            'manufacturer_type': '大华',
                                            'equipment_uname': vcr.vcr_username,
                                            'equipment_password': vcr.vcr_password,
                                            'user_status': '1',
                                            'create_time': datetime.now(),
                                            'Mine_id': vcr.Mine_id,
                                            'equipment_width_height': width_height,
                                            'equipment_codetype': videoCodecType,
                                            'equipment_constantBitRate': constantBitRate,
                                            'equipment_maxFrameRate': maxFrameRate,
                                            'Onvif_rtsp_url': Onvif_rtsp_url,
                                        })
                                        if new_device and online:
                                            zlk_id = create_zlk_data_for_equipment(new_device)
                                            if zlk_id:
                                                SchedulerTaskData.update_equipment_fields(new_device.id, {'zlk_dat_id': zlk_id})
                                                result['created'] += 1
                                except Exception as e:
                                    result['failed'].append(f"处理大华设备 {i.get('name')} 失败: {str(e)}")
                        else:
                            result['failed'].append(f"录像机 {vcr.vcr_ip} 厂商类型 {manufacturer_type} 不支持")
                except Exception as e:
                    result['failed'].append(f"处理录像机 {getattr(vcr, 'vcr_ip', '')} 失败: {str(e)}")
            summary = f"同步任务完成: 创建 {result['created']} 个, 删除 {result['deleted']} 个, 失败 {len(result['failed'])} 个"
            return True, summary if not result['failed'] else summary + "（详见日志）"
        except Exception as e:
            return False, f'录像机同步任务失败: {str(e)}'

    @staticmethod
    def update_cvr_equipment_task():
        try:
            vcr_list = SchedulerTaskData.get_vcr_list_by_type(2)
            if not vcr_list:
                return True, 'CVR设备不存在！'
            for vcr in vcr_list:
                parent_eq = SchedulerTaskData.get_parent_equipment_by_vcr(vcr.id)
                external_list = CVR_data_info(vcr.vcr_username, vcr.vcr_password, vcr.vcr_ip, vcr.vcr_port)
                if not external_list:
                    pinger = Pinger(target_host=vcr.vcr_ip)
                    delay = pinger.ping_once()
                    if delay is None:
                        eqs = SchedulerTaskData.get_equipments_by_vcr(vcr.id)
                        for eq in eqs:
                            SchedulerTaskData.update_equipment_fields(eq.id, {'online': 0})
                        SchedulerTaskData.set_vcr_online(vcr.id, 0)
                    continue
                SchedulerTaskData.set_equipments_online_by_vcr_parent(vcr.id, 1)
                SchedulerTaskData.set_vcr_online(vcr.id, 1)
                external_ips = [i.get('ip_address') for i in external_list]
                children = SchedulerTaskData.get_child_equipments_by_vcr(vcr.id)
                for child in children:
                    if child.equipment_ip not in external_ips:
                        SchedulerTaskData.delete_equipment_by_id(child.id)
                children_dict = {d.equipment_ip: d for d in children}
                for i in external_list:
                    ip_address = i['ip_address']
                    name = i['name']
                    channel_id = i['id']
                    channelName = i.get('channelName', '')
                    online = 1 if i['online'] == 'true' else 0
                    width_height = (
                        f"{i.get('videoResolutionWidth', '')}x{i.get('videoResolutionHeight', '')}"
                        if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                    )
                    videoCodecType = (
                        'H265' if i.get('videoCodecType') == 'H.265'
                        else 'H264' if i.get('videoCodecType') == 'H.264'
                        else None
                    )
                    constantBitRate = i.get('constantBitRate', '')
                    maxFrameRate = i.get('maxFrameRate', '')
                    if ip_address in children_dict:
                        db_device = children_dict[ip_address]
                        SchedulerTaskData.update_equipment_fields(db_device.id, {
                            'equipment_name': name,
                            'online': online,
                            'equipment_ip': ip_address,
                            'equipment_aisles': channel_id,
                            'code': channelName,
                            'equipment_width_height': width_height,
                            'equipment_codetype': videoCodecType,
                            'equipment_constantBitRate': constantBitRate,
                            'equipment_maxFrameRate': maxFrameRate,
                        })
                    else:
                        if not parent_eq:
                            continue
                        new_device = SchedulerTaskData.add_equipment({
                            'VCR_data_id': vcr.id,
                            'parent_id': parent_eq.id,
                            'equipment_aisles': channel_id,
                            'equipment_name': name,
                            'equipment_ip': ip_address,
                            'online': online,
                            'code': channelName,
                            'equipment_type': '视频中心存储',
                            'manufacturer_type': '海康',
                            'equipment_uname': vcr.vcr_username,
                            'equipment_password': vcr.vcr_password,
                            'user_status': '1',
                            'create_time': datetime.now(),
                            'Mine_id': vcr.Mine_id,
                            'equipment_width_height': width_height,
                            'equipment_codetype': videoCodecType,
                            'equipment_constantBitRate': constantBitRate,
                            'equipment_maxFrameRate': maxFrameRate
                        })
            return True, 'CVR设备定时同步更新成功!'
        except Exception as e:
            return False, f'CVR同步任务失败: {str(e)}'

    @staticmethod
    def monitor_algorithm_status_task():
        # IP reachability is not model/video health. Do not overwrite a real
        # runtime fault if this legacy callback is invoked manually.
        return True, '算法状态由运行时视频健康监测更新'

    @staticmethod
    def algo_config_defense_task():
        try:
            configs_list = SchedulerTaskData.get_all_algorithm_configs()
            if not configs_list:
                return True, '暂无布防配置'
            current_time = datetime.now()
            for item in configs_list:
                if item.defense_time_start is not None and item.defense_time_end is not None:
                    today = date.today()
                    start_time = datetime.strptime(f"{today} {item.defense_time_start}", '%Y-%m-%d %H:%M:%S')
                    end_time = datetime.strptime(f"{today} {item.defense_time_end}", '%Y-%m-%d %H:%M:%S')
                    status_value = '1' if start_time <= current_time <= end_time else '2'
                    SchedulerTaskData.update_algorithm_status(item.id, status_value)
            return True, '算法布防状态更新完成'
        except Exception as e:
            return False, f'算法布防检测失败: {str(e)}'

    @staticmethod
    def log_cleanup_task():
        try:
            from common.logging_policy import maintain_log_files
            from service.log_retention_service import cleanup_database_logs
            maintain_log_files()
            result = cleanup_database_logs()
            if result['ok']:
                count = sum(item['expired'] + item['excess'] for item in result['tables'].values())
                suffix = '；积压记录将在后续周期继续清理' if result['pending'] else ''
                return True, '日志清理完成，共删除 {} 条{}'.format(count, suffix)
            return False, '日志清理失败'
        except Exception as e:
            return False, f'日志清理任务失败: {str(e)}'

    @staticmethod
    def algorithm_result_delete_task():
        try:
            algorithm_ids = SchedulerTaskData.get_algorithm_delete_ids()
            count_old = SchedulerTaskData.delete_algorithm_results_by_library_ids(algorithm_ids) if algorithm_ids else 0
            config_ids = SchedulerTaskData.get_all_algorithm_config_ids()
            count_new = SchedulerTaskData.delete_results_where_config_id_not_in(config_ids) if config_ids else 0
            return True, f'已删除 {count_old} 条报警数据（已删除算法对应记录）；已删除 {count_new} 条报警数据（配置表中不存在的记录）'
        except Exception as e:
            return False, f'报警记录删除任务失败: {str(e)}'

    @staticmethod
    def zlk_stream_check_task():
        from service.stream_recovery_monitor import run_bound_stream_recovery
        try:
            activations = SchedulerTaskData.get_active_activations()
            active = activations[0] if activations else None
            enabled = active is not None
            if active and active.activate_valid_until:
                enabled = datetime.now() <= datetime.strptime(active.activate_valid_until, '%Y-%m-%d')
            # Licensing pauses new recovery; it never restarts healthy ZLK.
            # Only the helper owns the per-device and scheduler file locks.
            return run_bound_stream_recovery(enabled=enabled)
        except Exception:
            return False, '流媒体自动恢复状态未确认，请检查内部状态'

    @staticmethod
    def algo_config_expiry_task():
        try:
            activations = SchedulerTaskData.get_active_activations()
            if not activations:
                return True, '未找到有效激活信息'
            current_time = datetime.now()
            updated = False
            for i in activations:
                if i.activate_valid_until:
                    valid_until = datetime.strptime(i.activate_valid_until, '%Y-%m-%d')
                    if current_time > valid_until:
                        SchedulerTaskData.set_all_algorithm_configs_status(2)
                        updated = True
            return True, '算法配置状态已更新为过期' if updated else '算法配置状态未更新'
        except Exception as e:
            return False, f'算法配置有效期任务失败: {str(e)}'

    @staticmethod
    def get_enabled_scheduled_tasks():
        try:
            tasks = SchedulerTaskData.list_all_scheduled_tasks()
            if not tasks:
                return True, []
            tasks_data = [{
                'id': i.id,
                'name': i.name,
                'interval_seconds': int(i.interval_seconds) if i.interval_seconds else 0,
                'time_type': i.time_type,
                'rtsp_list': i.rtsp_list,
                'diagnosis_type_list': i.diagnosis_type_list,
                'scheduled_concent': i.scheduled_concent,
                'scheduled_status': int(i.scheduled_status) if i.scheduled_status is not None else 0,
            } for i in tasks]
            enabled = [t for t in tasks_data if t['scheduled_status'] == 1]
            return True, enabled
        except Exception as e:
            return False, f'获取启用任务列表失败: {str(e)}'

    @staticmethod
    def computing_equipment_status_task():
        try:
            computing_info = db.session.query(Computing_equipment).all()
            if not computing_info:
                return True, '暂无设备信息'
            for item in computing_info:
                ssh_client = SSH_Func(item.computing_ip, item.computing_user, item.computing_password)
                ssh, status = ssh_client.connect_ssh()
                db.session.query(Computing_equipment).filter(
                    Computing_equipment.computing_ip == ssh_client.ssh_host
                ).update({'computing_status': status})
                db.session.commit()
                if ssh:
                    ssh.close()
            return True, '算力设备状态更新完成'
        except Exception as e:
            return False, f'算力设备状态任务失败: {str(e)}'

    @staticmethod
    def alarm_voice_broadcast_task():
        """
        报警信息语音播报定时任务
        查询最新的报警信息，根据设备IP找到关联的alarm_device_ip，通过TCP发送语音播报指令
        支持多个报警同时并发播报，且不会重复播报已处理过的报警
        同一设备短时间多条报警时，只播报最新的一条
        """
        try:
            # 初始化Redis客户端（用于记录已播报的报警ID）
            redis_client = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, db=6)
            broadcasted_ids_key = "broadcasted_alarm_ids"

            # 获取Redis中已播报过的ID列表
            broadcasted_ids_raw = redis_client.smembers(broadcasted_ids_key)
            broadcasted_ids = [int(id.decode()) for id in broadcasted_ids_raw] if broadcasted_ids_raw else []

            # 获取最近5分钟内的最新报警记录（排除已播报过的）
            cutoff_time = datetime.now() - timedelta(minutes=5)

            if broadcasted_ids:
                query_filter = and_(
                    Algorithm_result.res_time >= cutoff_time,
                    ~Algorithm_result.id.in_(broadcasted_ids)
                )
            else:
                query_filter = Algorithm_result.res_time >= cutoff_time

            # 先查询所有符合条件的报警
            all_alarms = db.session.query(Algorithm_result).filter(query_filter)\
                .order_by(Algorithm_result.res_time.desc()).all()

            if not all_alarms:
                return True, '暂无最新未播报报警信息'

            # 按设备分组，每个设备只取最新的一条报警
            equipment_latest_map = {}
            for alarm in all_alarms:
                equip_id = alarm.Equipment_id
                if equip_id not in equipment_latest_map:
                    equipment_latest_map[equip_id] = alarm
                # 因为已经按时间降序排列，第一个就是最新的

            latest_alarms = list(equipment_latest_map.values())

            threads = []
            new_broadcasted_ids = []

            # 为每个设备的最新报警创建独立的播报线程
            for alarm in latest_alarms:
                try:
                    # 根据Equipment_id查找设备信息
                    equipment = db.session.query(Equipment).filter(
                        Equipment.id == alarm.Equipment_id
                    ).first()

                    if not equipment or not equipment.alarm_device_ip:
                        print(f"设备ID {alarm.Equipment_id} 不存在或未配置alarm_device_ip")
                        continue

                    alarm_device_ip = equipment.alarm_device_ip
                    warning_message = alarm.warning_message

                    if not warning_message:
                        print(f"报警ID {alarm.id} 没有warning_message")
                        continue

                    # 记录待播报的ID
                    new_broadcasted_ids.append(alarm.id)

                    # 创建线程进行并发播报
                    thread = threading.Thread(
                        target=SchedulerTaskService.send_voice_broadcast,
                        args=(alarm_device_ip, warning_message),
                        kwargs={'volume': 1, 'speed': 5, 'tone': 5, 'voice_type': 3},
                        daemon=True
                    )
                    threads.append(thread)
                    thread.start()

                except Exception as e:
                    print(f"处理报警ID {alarm.id} 时出错: {str(e)}")

            # 等待所有线程完成（设置超时时间避免无限等待）
            for thread in threads:
                thread.join(timeout=10)  # 每个线程最多等待10秒

            # 将本次播报的ID存入Redis，设置过期时间为8小时
            if new_broadcasted_ids:
                pipe = redis_client.pipeline()
                for alarm_id in new_broadcasted_ids:
                    pipe.sadd(broadcasted_ids_key, alarm_id)
                pipe.expire(broadcasted_ids_key, 8 * 3600)
                pipe.execute()
                print(f"语音播报已记录 {len(new_broadcasted_ids)} 条报警到Redis: {new_broadcasted_ids}")

            result_msg = f"语音播报完成: 成功 {len(threads)} 条"
            return True, result_msg

        except Exception as e:
            return False, f'报警语音播报任务失败: {str(e)}'

    @staticmethod
    def send_voice_broadcast(alarm_device_ip, message, port=12345,
                             volume=1, speed=5, tone=5, voice_type=3):
        """
        通过TCP连接语音控制器发送语音播报指令（高级模式）

        参数:
            alarm_device_ip: 语音控制器IP地址
            message: 要播报的文字内容
            port: TCP端口号，默认6000
            volume: 音量 1-10档，默认7（较大音量，适合报警场景）
            speed: 语速 1-10档，默认5（正常语速）
            tone: 语调 1-10档，默认5（正常语调）
            voice_type: 发音人 3晓玲(女) 51尹小坚(男) 52易小强(男) 53田蓓蓓(女) 54唐老鸭 55小燕子，默认3

        返回:
            bool: 是否成功发送
        """
        tcp_cli_sock = None
        try:
            # 创建TCP客户端套接字
            tcp_cli_sock = socket(AF_INET, SOCK_STREAM)
            tcp_cli_sock.settimeout(5)  # 设置5秒超时

            # 连接语音控制器
            addr = (alarm_device_ip, port)
            tcp_cli_sock.connect(addr)

            # 构造带参数的语音文本
            # [m发音人][s语速][t语调][v音量]
            voice_text = f"[m{voice_type}][s{speed}][t{tone}][v{volume}]{message}"

            # 计算文本长度（GBK编码的字节数）
            text_length = len(voice_text.encode('gbk'))

            # 构造TTS语音播报指令（高级模式）
            # AT+TTS1=通道,模式,高级功能,拼音识别,文本长度
            voice_command = f"AT+TTS1=1,0,1,1,{text_length}\r\n{voice_text}"

            # 发送指令（使用gbk编码，与demo保持一致）
            tcp_cli_sock.send(voice_command.encode('gbk'))

            # 接收设备应答
            recv_data = tcp_cli_sock.recv(1024)
            response = recv_data.decode('gbk')

            print(f"语音控制器({alarm_device_ip})应答: {response}")

            # 关闭连接
            tcp_cli_sock.close()

            # 检查应答是否包含成功标识
            if 'DEVONLINE' in response or 'OK' in response or 'ok' in response or '+' in response:
                return True
            else:
                print(f"设备应答异常: {response}")
                return False

        except Exception as e:
            print(f"发送语音播报到 {alarm_device_ip}:{port} 失败: {str(e)}")
            if tcp_cli_sock:
                try:
                    tcp_cli_sock.close()
                except:
                    pass
            return False
