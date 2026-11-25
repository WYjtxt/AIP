from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from data.video_data import *
import urllib.parse
import ast
import json

def parse_time_to_standard_format(time_str):

    if not time_str:
        return ""

    # 移除所有非数字字符（包括 't', 'T', '-', ':', '.' 等）
    cleaned_time = re.sub(r'[^0-9]', '', time_str)
    # 验证长度是否为 14 位（YYYYMMDDHHMMSS）
    if len(cleaned_time) == 14:
        # 格式化为 2026_03_29_17_39_25 格式
        return f"{cleaned_time[0:4]}_{cleaned_time[4:6]}_{cleaned_time[6:8]}_{cleaned_time[8:10]}_{cleaned_time[10:12]}_{cleaned_time[12:14]}"
    elif len(cleaned_time) < 14:
        # 如果长度不足 14 位，可能是格式不对，返回原清理后的值
        return cleaned_time
    else:
        # 如果长度超过 14 位，取前 14 位并格式化
        cleaned_time = cleaned_time[:14]
        return f"{cleaned_time[0:4]}_{cleaned_time[4:6]}_{cleaned_time[6:8]}_{cleaned_time[8:10]}_{cleaned_time[10:12]}_{cleaned_time[12:14]}"


def generate_rtsp_url(em_data, video_status, start_time=None, end_time=None):
    # 定义一个安全的quote方法，失败时返回原字符串
    def safe_quote(s):
        try:
            return urllib.parse.quote(str(s)) if s is not None else ""
        except:
            return str(s) if s is not None else ""

    if em_data.equipment_type == '紫光华智':
        return em_data.Ziguang_ape_rtsp_url
    if em_data.equipment_type == '安防平台':
        if video_status == '1':
            from service.algorithm_stream_selection import hik_snapshot_url
            try:
                return hik_snapshot_url(em_data)
            except ValueError:
                return None
        elif video_status == '2':
            hik_api = get_hik_platform_api()
            return hik_api.get_camera_playback_url(
                index_codes=em_data.Hik_indexCode,
                beginTime=convert_time_format(start_time),
                endTime=convert_time_format(end_time)
            )
    # if em_data.equipment_type == 'AI双光摄像头'or'AI单光摄像头':
    #     if em_data.id == 495:
    #         url = "rtsp://192.168.113.36:554/Streaming/tracks/601starttime={}z&endtime={}z".format(
    #             start_time,
    #             end_time,
    #         )
    #     else:
    #         url = "rtsp://192.168.113.36:554/Streaming/tracks/701starttime={}z&endtime={}z".format(
    #             start_time,
    #             end_time,
    #         )
    #     return url
    par = None
    if em_data.VCR_data_id and em_data.parent_id:
        par = get_parent_equipment_by_id(em_data.parent_id)
    is_history = (video_status != '1')
    if is_history:
        if not par:
            return ""
        if par.manufacturer_type == '海康':
            try:
                url = "rtsp://{}:{}@{}:554/Streaming/tracks/{}starttime={}z&endtime={}z".format(
                    safe_quote(em_data.equipment_uname),
                    safe_quote(em_data.equipment_password),
                    safe_quote(par.equipment_ip),
                    safe_quote(em_data.code),
                    start_time,
                    end_time,
                )
            except:
                url = "rtsp://{}:{}@{}:554/Streaming/tracks/{}starttime={}z&endtime={}z".format(
                    em_data.equipment_uname,
                    em_data.equipment_password,
                    par.equipment_ip,
                    em_data.code,
                    start_time,
                    end_time,
                )
            return url
        if par.manufacturer_type == '宇视':
            try:
                url = "rtsp://{}:{}@{}:554/c{}/b{}/e{}/replay/s1".format(
                    safe_quote(em_data.equipment_uname),
                    safe_quote(em_data.equipment_password),
                    safe_quote(par.equipment_ip),
                    safe_quote(em_data.equipment_aisles),
                    start_time,
                    end_time
                )
            except:
                url = "rtsp://{}:{}@{}:554/c{}/b{}/e{}/replay/s1".format(
                    em_data.equipment_uname,
                    em_data.equipment_password,
                    par.equipment_ip,
                    em_data.equipment_aisles,
                    start_time,
                    end_time
                )
            return url
        if par.manufacturer_type == '大华':
            try:
                start_time_formatted = parse_time_to_standard_format(start_time)
                end_time_formatted = parse_time_to_standard_format(end_time)
                url = "rtsp://{}:{}@{}:554/cam/playback?channel={}&subtype=0&starttime={}&endtime={}".format(
                    safe_quote(em_data.equipment_uname),
                    safe_quote(em_data.equipment_password),
                    safe_quote(par.equipment_ip),
                    safe_quote(em_data.equipment_aisles),
                    start_time_formatted,
                    end_time_formatted
                )
            except:
                start_time_formatted = parse_time_to_standard_format(start_time)
                end_time_formatted = parse_time_to_standard_format(end_time)
                url = "rtsp://{}:{}@{}:554/cam/playback?channel={}&subtype=0&starttime={}&endtime={}".format(
                    em_data.equipment_uname,
                    em_data.equipment_password,
                    par.equipment_ip,
                    em_data.equipment_aisles,
                    start_time_formatted,
                    end_time_formatted
                )
            return url
        return ""
    if par:
        if par.manufacturer_type == '海康':
            try:
                url = "rtsp://{}:{}@{}:554/Streaming/Unicast/Channels/{}".format(
                    safe_quote(em_data.equipment_uname),
                    safe_quote(em_data.equipment_password),
                    safe_quote(par.equipment_ip),
                    safe_quote(em_data.code),
                )
            except:
                url = "rtsp://{}:{}@{}:554/Streaming/Unicast/Channels/{}".format(
                    em_data.equipment_uname,
                    em_data.equipment_password,
                    par.equipment_ip,
                    em_data.code,
                )
            return url
        if par.manufacturer_type == '宇视':
            try:
                url = "rtsp://{}:{}@{}:554/unicast/c{}/s1/live".format(
                    safe_quote(em_data.equipment_uname),
                    safe_quote(em_data.equipment_password),
                    safe_quote(par.equipment_ip),
                    safe_quote(em_data.equipment_aisles),
                )
            except:
                url = "rtsp://{}:{}@{}:554/unicast/c{}/s1/live".format(
                    em_data.equipment_uname,
                    em_data.equipment_password,
                    par.equipment_ip,
                    em_data.equipment_aisles,
                )
            return url
        if par.manufacturer_type == '大华':
            onvif_rtsp = em_data.Onvif_rtsp_url
            if onvif_rtsp and onvif_rtsp.startswith('rtsp://'):
                return "rtsp://{}:{}@{}".format(par.equipment_uname, par.equipment_password, onvif_rtsp[7:])

    # 最后兜底地址
    try:
        return "rtsp://{}:{}@{}".format(
            safe_quote(em_data.equipment_uname),
            safe_quote(em_data.equipment_password),
            safe_quote(em_data.equipment_ip),
        )
    except:
        return "rtsp://{}:{}@{}".format(
            em_data.equipment_uname,
            em_data.equipment_password,
            em_data.equipment_ip,
        )

# def real_time_video(rtmp_server_ip, em_id_str, width, height, frame_r, baud_b, stream_data_flag,
#                     video_status, start_time, end_time, model_id, algorithm_name, det_type,algorithm_test_type):
#     params = [rtmp_server_ip, em_id_str, width, height, frame_r, baud_b, stream_data_flag]
#     if not all(params):
#         return {'code': 400, 'msg': '设备数据有未填写项'}
#     model_path = get_model(model_id, algorithm_name)
#     # if not model_path:
#     #     return {'code': 400, 'msg': '该模型不存在!'}
#     data_list = []
#     parsed_em_id = safe_eval(em_id_str)
#     if parsed_em_id is None:
#         return {'code': 400, 'msg': '设备不存在或已变更!'}
#     random_letters = ''.join(random.choices(string.ascii_letters, k=5))
#
#     filter_cnames = []
#     if algorithm_test_type and isinstance(algorithm_test_type, list) and len(algorithm_test_type) > 0:
#         test_type_ids = [int(id) for id in algorithm_test_type if str(id).isdigit()]
#         if test_type_ids:
#             test_types = db.session.query(Algorithm_test_type.test_type_cname).filter(
#                 Algorithm_test_type.id.in_(test_type_ids)
#             ).all()
#             filter_cnames = [item.test_type_cname for item in test_types]
#
#     for i in parsed_em_id:
#         em_data = get_equipment_by_id(i)
#         if not em_data:
#             return {'code': 400, 'msg': '设备不存在或已变更!'}
#         rtsp_url = generate_rtsp_url(em_data, video_status, start_time, end_time)
#         if not rtsp_url:
#             return {'code': 400, 'msg': '无法生成有效的 RTSP 流 URL!'}
#         ip_address = extract_ip_from_rtsp(rtsp_url)
#         try:
#             pinger = Pinger(target_host=ip_address)
#             delay = pinger.ping_once()
#             if delay is None:
#                 return {'code': 400, 'msg': '当前监控点不在线!'}
#         except Exception:
#             return {'code': 400, 'msg': '当前监控点不在线!'}
#         item = {
#             "rtsp_url": rtsp_url,
#             "rtmp_server_ip": rtmp_server_ip,
#             "width": width,
#             "height": height,
#             "frame_r": frame_r,
#             "baud_b": baud_b,
#             "stream_data_flag": stream_data_flag,
#             # "model_path": model_path.algorithm_path,
#             "det_type": det_type,
#             "filter_cnames": filter_cnames
#         }
#         data_list.append(item)
#     for index, item in enumerate(data_list, start=1):
#         item['id'] = index
#         item['random_letters'] = random_letters
#         item['flv_url'] = f'http://{rtmp_server_ip}:8085/live/stream{random_letters}.live.mp4'
#     set_video_data_list(data_list)
#     set_stream_data_flag(1, db_index=3)
#     return {'code': 200, 'msg': '推流成功', 'flv_data': data_list}

def _parse_equipment_ids(value):
    """Validate exact device IDs without guessing aliases or evaluating code."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            # Keep old Python-list clients compatible without executable eval.
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError, TypeError):
                raise ValueError('监控点ID无效，请刷新报警列表后重试')
    else:
        parsed = value
    if not isinstance(parsed, list) or not parsed:
        raise ValueError('监控点ID无效，请刷新报警列表后重试')
    ids = []
    for item in parsed:
        if isinstance(item, str):
            item = item.strip()
            if not re.fullmatch(r'[0-9]{1,10}', item):
                raise ValueError('监控点ID无效，请刷新报警列表后重试')
            item = int(item)
        if type(item) is not int or item <= 0 or item > 2147483647:
            raise ValueError('监控点ID无效，请刷新报警列表后重试')
        ids.append(item)
    return ids


def real_time_video(rtmp_server_ip, id,em_id_str, width, height, frame_r, baud_b, stream_data_flag,
                    video_status, start_time, end_time, model_id, algorithm_name, det_type,algorithm_test_type,
                    session_token=None, session_owner=None):
    params = [rtmp_server_ip, em_id_str, width, height, frame_r, baud_b, stream_data_flag]
    if not all(params):
        return {'code': 400, 'msg': '设备数据有未填写项'}
    data_list = []
    try:
        parsed_em_id = _parse_equipment_ids(em_id_str)
    except ValueError as exc:
        return {'code': 400, 'msg': str(exc)}
    # All algorithm families can have event archives. Resolve by record ID
    # before consulting the optional temporary replay worker.
    det_type = str(det_type)
    archived_result = None
    if str(video_status) == '2' and id and det_type in ('0', '1', '4'):
        try:
            record_ids = _parse_equipment_ids([id])
        except ValueError:
            return {'code': 400, 'msg': '报警记录ID无效，请刷新列表后重试'}
        archived_result = get_result_video_by_id(record_ids[0])
        if archived_result is None:
            return {'code': 400, 'msg': '该报警记录不存在或已变更'}
        if getattr(archived_result, 'warning_video', None) or getattr(archived_result, 'res_video', None):
            det_type = '4'
        else:
            return {'code': 410, 'msg': '该报警未生成可用的事件存档视频，可查看报警图片；未替换为其它时段录像',
                    'media_status': 'unavailable'}
    if det_type not in ('3', '4'):
        from service.playback_session import inspect_temporary_playback
        existing = inspect_temporary_playback(session_token, session_owner)
        if existing is not None:
            return existing
    model_path = get_model(model_id, algorithm_name)
    # 3为人数统计实时分析
    if det_type == '3':
        for i in parsed_em_id:
            em_data = get_equipment_by_id(i)
            if not em_data:
                return {'code': 400, 'msg': '设备不存在或已变更!'}
            rtsp_url = em_data.person_count_url
            if not rtsp_url:
                return {'code': 400, 'msg': '未生成有效的 RTSP 流 URL!'}

            item = {
                "rtsp_url": rtsp_url,
                "rtmp_server_ip": rtmp_server_ip,
                "width": width,
                "height": height,
                "frame_r": frame_r,
                "baud_b": baud_b,
                "stream_data_flag": stream_data_flag,
                # "model_path": model_path.algorithm_path,
                "det_type": det_type,
                'flv_url': f'http://{rtmp_server_ip}:8085/stream/{em_data.id}.live.mp4'
            }
            data_list.append(item)
            return {'code': 200, 'msg': '推流成功', 'flv_data': data_list}
    # 4为人员计数报警视频分析回放本地视频
    elif det_type == '4':
        # Alarm archives belong to the historical record, not the current tree.
        # Never substitute a live stream or another camera's alarm video.
        try:
            record_ids = _parse_equipment_ids([id])
        except ValueError:
            return {'code': 400, 'msg': '报警记录ID无效，请刷新报警列表后重试'}
        if len(parsed_em_id) != 1:
            return {'code': 400, 'msg': '存档视频回放只能选择该报警所属的一个监控点'}
        result = archived_result or get_result_video_by_id(record_ids[0])
        if result is None:
            return {'code': 400, 'msg': '该报警记录不存在或已变更，请刷新报警列表后重试'}
        try:
            record_equipment_ids = _parse_equipment_ids([getattr(result, 'Equipment_id', None)])
        except ValueError:
            record_equipment_ids = None
        if record_equipment_ids != parsed_em_id:
            return {'code': 400, 'msg': '报警记录与所选监控点不一致，请刷新报警列表后重试'}
        warning_video = getattr(result, 'warning_video', None) or getattr(result, 'res_video', None)
        if not isinstance(warning_video, str) or not warning_video.strip():
            return {'code': 400, 'msg': '该报警记录没有可用的存档视频，可查看报警图片'}
        # The stored URL must retain the selected event's identity and timeline.
        # A missing/failed archive never falls through to a fresh re-analysis.
        from service.alarm_media_integrity import inspect_archive
        integrity = inspect_archive(result, warning_video, rtmp_server_ip)
        if integrity.get('code') != 200:
            return integrity
        item = {
            "rtsp_url": None,
            "rtmp_server_ip": rtmp_server_ip,
            "width": width,
            "height": height,
            "frame_r": frame_r,
            "baud_b": baud_b,
            "stream_data_flag": stream_data_flag,
            # "model_path": model_path.algorithm_path,
            "det_type": det_type,
            'flv_url': warning_video
        }
        data_list.append(item)
        return dict(integrity, code=200, playback_source='archive', flv_data=data_list,
                    alarm_record_id=record_ids[0], equipment_id=record_equipment_ids[0])
    else:
        random_letters = ''.join(random.choices(string.ascii_letters, k=5))

        filter_cnames = []
        if algorithm_test_type and isinstance(algorithm_test_type, list) and len(algorithm_test_type) > 0:
            test_type_ids = [int(id) for id in algorithm_test_type if str(id).isdigit()]
            if test_type_ids:
                test_types = db.session.query(Algorithm_test_type.test_type_cname).filter(
                    Algorithm_test_type.id.in_(test_type_ids)
                ).all()
                filter_cnames = [item.test_type_cname for item in test_types]

        for i in parsed_em_id:
            em_data = get_equipment_by_id(i)
            if not em_data:
                return {'code': 400, 'msg': '设备不存在或已变更!'}
            rtsp_url = generate_rtsp_url(em_data, video_status, start_time, end_time)
            if not rtsp_url:
                if str(video_status) == '2':
                    return {'code': 400, 'msg': '该监控点未配置可用的历史录像来源，无法进行视频回放；可查看报警图片'}
                return {'code': 400, 'msg': '无法生成有效的 RTSP 流 URL!'}
            ip_address = extract_ip_from_rtsp(rtsp_url)
            try:
                pinger = Pinger(target_host=ip_address)
                delay = pinger.ping_once()
                if delay is None:
                    return {'code': 400, 'msg': '当前监控点不在线!'}
            except Exception:
                return {'code': 400, 'msg': '当前监控点不在线!'}
            item = {
                "rtsp_url": rtsp_url,
                "rtmp_server_ip": rtmp_server_ip,
                "width": width,
                "height": height,
                "frame_r": frame_r,
                "baud_b": baud_b,
                "stream_data_flag": stream_data_flag,
                # "model_path": model_path.algorithm_path,
                "det_type": det_type,
                "filter_cnames": filter_cnames
            }
            data_list.append(item)
        for index, item in enumerate(data_list, start=1):
            item['id'] = index
            item['random_letters'] = random_letters
            item['flv_url'] = f'http://{rtmp_server_ip}:8085/live/stream{random_letters}.live.mp4'
        from service.playback_session import dispatch_temporary_playback
        return dispatch_temporary_playback(data_list, session_token, session_owner)
def real_time_video_status():
    video_type = get_video_type(3)
    if video_type == '1':
        return {'code': 200, 'video_type': video_type}
    return {'code': 201, 'video_type': '视频分析停止'}

def real_time_video_stop(session_token=None, session_owner=None):
    from service.playback_session import stop_temporary_playback
    return stop_temporary_playback(session_token, session_owner)

def alg_video_stop():
    set_stream_data_flag(3, db_index=4)
    return {'code': 200, 'video_type': '视频分析停止'}

def alg_conf_video(rtmp_server_ip, config_id, width, height, frame_r, baud_b, stream_data_flag):
    params = [rtmp_server_ip, config_id, width, height, frame_r, baud_b, stream_data_flag]
    if not all(params):
        return {'code': 400, 'msg': '设备数据有未填写项'}
    r_set(4, "config_id", config_id)
    r_set(4, "rtmp_server_ip", rtmp_server_ip)
    r_set(4, "width", width)
    r_set(4, "height", height)
    r_set(4, "frame_r", frame_r)
    r_set(4, "baud_b", baud_b)
    r_set(4, "stream_data_flag", stream_data_flag)
    r_set(4, "video_type", 3)
    return {'code': 200, 'message': '配置监控点检测进行中'}

def video_playback(equipment_id):
    equipment_data = db.session.query(Equipment).filter(Equipment.id == equipment_id, Equipment.parent_id != None).first()
    if not equipment_data:
        return {'code': 400, 'msg': '该监控点不存在！'}
    data_info = {}
    if equipment_data.equipment_type == '录像机' or equipment_data.equipment_type == '视频中心存储':
        equipment_parent_data = db.session.query(Equipment).filter(Equipment.id == equipment_data.parent_id).first()
        data_info = {
            'equipment_aisles': equipment_data.equipment_aisles,
            'equipment_ip': equipment_parent_data.equipment_ip,
            'equipment_uname': equipment_parent_data.equipment_uname,
            'equipment_password': equipment_parent_data.equipment_password,
        }
    return {'code': 200, 'data': data_info}

def start_forward_video(em_id):
    try:
        em_id_int = int(em_id)
    except (ValueError, TypeError):
        return {'code': 400, 'msg': '设备ID必须为数字', 'data': None}
    em_data = get_equipment_by_id(em_id_int)
    if not em_data:
        return {'code': 404, 'msg': '设备不存在!', 'data': None}
    if not em_data.zlk_dat_id:
        return {'code': 400, 'msg': '该设备未创建视频流（未关联ZLK视频资源）', 'data': None}
    zlk_data = get_zlk_data_by_id(em_data.zlk_dat_id)
    if not zlk_data:
        return {'code': 404, 'msg': '该设备关联的ZLK视频流数据不存在', 'data': None}
    response_data = {
        'zlk_hls': zlk_data.zlk_hls,
        'zlk_hls_fmp4': zlk_data.zlk_hls_fmp4,
        'zlk_mp4': zlk_data.zlk_mp4,
        'zlk_rtmp': zlk_data.zlk_rtmp,
        'zlk_rtsp': zlk_data.zlk_rtsp,
        'zlk_ts': zlk_data.zlk_ts,
        'zlk_flv': zlk_data.zlk_flv
    }
    return {'code': 200, 'msg': '视频流地址获取成功', 'data': response_data}

def stop_forward_video(em_id):
    if not em_id:
        return {'code': 400, 'msg': '设备ID不能为空'}
    r_delete(5, f'forward_stream:{em_id}')
    r_set(5, 'forward_stream_flag', '0')
    return {'code': 200, 'msg': '视频转发已停止'}
