from data.model_views_data import ModelViewsData
from datetime import datetime
from config.configs import *

class ModelViewsService:
    # 设备相关业务逻辑
    @staticmethod
    def get_equipment_by_vcr_id(vcr_id):
        """
        根据录像机ID获取监控点列表
        """
        try:
            em_list = ModelViewsData.get_equipment_by_vcr_id(vcr_id)
            # 序列化
            data = convert_folder_to_dict_list(em_list, ['id', 'equipment_name', 'VCR_data_id', 'equipment_ip'])
            return True, data
        except Exception as e:
            return False, f'获取监控点列表失败: {str(e)}'

    @staticmethod
    def get_all_equipment():
        """
        获取所有设备信息
        """
        try:
            equipment_data = ModelViewsData.get_all_equipment()
            equipment_list = []

            for i in equipment_data:
                # 判断摄像头类型获取rtsp流
                rtsp = ''
                if i.equipment_type == '摄像头':
                    rtsp = 'rtsp://{}:{}@{}'.format(i.equipment_uname, i.equipment_password, i.equipment_ip)
                elif i.equipment_type == '录像机':
                    rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1)
                    if rtsp_mp4_data:
                        rtsp = rtsp_mp4_data['rtsp']
                elif i.equipment_type == '视频中心存储':
                    rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 1)
                    if rtsp_mp4_data:
                        rtsp = rtsp_mp4_data['rtsp']
                elif i.equipment_type == '特殊摄像头':
                    rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 2)
                    if rtsp_mp4_data:
                        rtsp = rtsp_mp4_data['rtsp']
                elif i.equipment_type == 'AI双光摄像头':
                    rtsp_mp4_data = get_children_rtsp(i.parent_id, i.code, 2)
                    if rtsp_mp4_data:
                        rtsp = rtsp_mp4_data['rtsp']
                elif i.equipment_type == '浙江双视热成像':
                    rtsp = 'rtsp://{}:{}@{}:554/live/chn0'.format(i.equipment_uname, i.equipment_password, i.equipment_ip)
                elif i.equipment_type == '安防平台':
                    rtsp = i.Hik_rtsp_url
                elif i.equipment_type == '紫光华智':
                    rtsp = i.Ziguang_ape_rtsp_url

                dict_res = {
                    'id': i.id, 
                    'equipment_name': i.equipment_name, 
                    'equipment_type': i.equipment_type,
                    'rtsp': rtsp
                }
                equipment_list.append(dict_res)

            # 使用列表推导式筛选设备类型为“录像机”的记录 取录像机的 ID
            vcr_ids = [i['id'] for i in equipment_list if i['equipment_type'] == '录像机'
                      or i['equipment_type'] == '特殊摄像头' or i['equipment_type'] == '安防平台' 
                      or i['equipment_type'] == '紫光华智' or i['equipment_type'] == '视频中心存储'
                       or i['equipment_type'] == 'AI双光摄像头']
            # 调用方法数据构造
            equipment_list = children_data(equipment_list, vcr_ids)

            return True, equipment_list
        except Exception as e:
            return False, f'获取设备列表失败: {str(e)}'

    # 诊断数据相关业务逻辑
    @staticmethod
    def get_diagnosis_data(page, per_page, first_vcr_id=None, second_vcr_id=None, diagnosis_type=None, start_time=None, end_time=None):
        """
        获取诊断数据列表（支持分页和筛选）
        """
        try:
            # 转换时间格式
            gmt_start_time = time_to_gmt_format(start_time) if start_time else None
            gmt_end_time = time_to_gmt_format(end_time) if end_time else None

            res = ModelViewsData.get_diagnosis_data(
                page, per_page, first_vcr_id, second_vcr_id, diagnosis_type, gmt_start_time, gmt_end_time
            )

            # 构造返回数据
            res_data = [{
                'id': i.id,
                'equipment_id': i.equipment_id,
                'equipment_ip': i.equipment_ip,
                'equipment_name': i.equipment_name,
                'vcr_ip': i.vcr_ip,
                'vcr_name': i.parent_name,
                'diagnosis_type': i.diagnosis_type,
                'db101': i.db101, 'db102': i.db102, 'db103': i.db103,
                'db104': i.db104, 'db105': i.db105, 'db106': i.db106,
                'db107': i.db107, 'db108': i.db108, 'db109': i.db109,
                'db110': i.db110, 'db111': i.db111, 'db112': i.db112,
                'db113': i.db113, 'db114': i.db114, 'db115': i.db115, 'db116': i.db116,
                'diagnosis_pic': i.diagnosis_pic,
                'diagnosis_reason': i.diagnosis_reason or '',
                'diagnosis_time':i.diagnosis_time.strftime("%Y-%m-%d %H:%M:%S"),
                'create_time': (i.create_time).strftime("%Y-%m-%d %H:%M:%S"),
            } for i in res.items]

            response_data = {
                'total_items': res.total,
                'total_pages': res.pages,
                'current_page': res.page,
                'per_page': per_page,
                'data': res_data,
            }

            return True, response_data
        except Exception as e:
            return False, f'获取诊断数据失败: {str(e)}'

    # 监测点离线信息相关业务逻辑
    @staticmethod
    def get_monitor_point_offline():
        """
        获取监测点离线信息
        """
        try:
            equipmentInfo = ModelViewsData.get_equipment_status()
            resultList = convert_folder_to_dict_list(equipmentInfo, ['id', 'equipment_ip', 'online', 'duration_time'])
            getDevRunStatus(resultList)

            for item_i in resultList:
                # 获取当前监测点的最后一条离线信息
                off_newInfo = ModelViewsData.get_last_offline_info(item_i['id'])
                if item_i['online'] == 2:
                    # 如果查询结果为空，就新增一条离线信息，否则就更新最后一条离线信息的离线结束时间，并更新离线持续时间
                    if off_newInfo is None:
                        # 离线设备的信息
                        ModelViewsData.create_offline_info(item_i['id'], item_i['equipment_ip'])
                    if off_newInfo is not None:
                        # 计算离线持续时间
                        offline_durationTime = (datetime.now() - off_newInfo.offline_start_time).seconds
                        days = offline_durationTime // (24 * 3600)
                        hours = (offline_durationTime % (24 * 3600)) // 3600
                        minutes = (offline_durationTime % 3600) // 60
                        seconds = offline_durationTime % 60
                        duration_time = f"{days}天{hours}时{minutes}分{seconds}秒"
                        
                        # 更新设备离线持续时间
                        ModelViewsData.update_equipment_duration_time(item_i['id'], duration_time)
                else:
                    if off_newInfo is not None:
                        # 计算离线持续时间
                        offline_end_time = datetime.now()
                        offline_durationTime = (offline_end_time - off_newInfo.offline_start_time).seconds
                        days = offline_durationTime // (24 * 3600)
                        hours = (offline_durationTime % (24 * 3600)) // 3600
                        minutes = (offline_durationTime % 3600) // 60
                        seconds = offline_durationTime % 60
                        offline_keep_time = f"{days}天{hours}时{minutes}分{seconds}秒"
                        
                        # 更新离线信息
                        ModelViewsData.update_offline_info(off_newInfo.id, offline_end_time, offline_keep_time)

            return True, '监测点离线数据写入成功'
        except Exception as e:
            return False, f'获取监测点离线信息失败: {str(e)}'
