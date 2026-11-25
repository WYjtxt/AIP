from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import func,exc
from tool.OpenApi_public_Class import HikVisionAPI
import service.video_service as video_service


# 创建蓝图，对应的register目录（激活操作视图）
video_view = Blueprint('video', __name__)


 

# 实时视频推流接口（视频分析）
@video_view.route('/real_time_video', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def real_time_video():
    rtmp_server_ip = DB_HOST
    id = strip_whitespace(request.args.get('Algorithm_result_id', None))
    em_id = strip_whitespace(request.args.get('em_id', None))
    width = strip_whitespace(request.args.get('width', 1920))
    height = strip_whitespace(request.args.get('height', 1080))
    frame_r = strip_whitespace(request.args.get('frame_r', 25))
    baud_b = strip_whitespace(request.args.get('baud_b', 2000))
    stream_data_flag = strip_whitespace(request.args.get('stream_data_flag', None))
    video_status = strip_whitespace(request.args.get('video_status', '1'))
    start_time = strip_whitespace(request.args.get('start_time', None))
    end_time = strip_whitespace(request.args.get('end_time', None))
    model_id = strip_whitespace(request.args.get('model_id', None))
    algorithm_name = strip_whitespace(request.args.get('algorithm_name', None))
    det_type = strip_whitespace(request.args.get('det_type', None))
    algorithm_test_type = strip_whitespace(request.args.getlist('algorithm_test_type[]'))
    res = video_service.real_time_video(rtmp_server_ip, id,em_id, width, height, frame_r, baud_b, stream_data_flag,
                                        video_status, start_time, end_time, model_id, algorithm_name, det_type,algorithm_test_type,
                                        session_token=request.args.get('session_token'), session_owner=get_jwt_identity())
    return jsonify(res)


# # 实时视频推流接口（视频分析）
# @video_view.route('/real_time_video', methods=['GET'])
# # @jwt_required()
# def real_time_video():
#     """
#     实时视频推流接口
#
#     参数:
#         model_path (str): 模型id
#         linux_ip (str): RTMP 服务器 IP 地址。
#         rtsp_url (str): RTSP 流媒体源地址。
#         width (str): 视频宽度。
#         height (str): 视频高度。
#         frame_r (str): 比特率。
#         baud_b (str): 帧率。
#         stream_data_flag (str): 运行标识   1运行  0 删除。
#         video_type (str): 运行标识   1 实时视频  2录像回放
#         start_time (str): 开始时间
#         end_time (str):   结束时间
#     """
#
#     # 视频分析列表
#     data_list=[]
#
#
#     rtmp_server_ip=DB_HOST
#     em_id = strip_whitespace(request.args.get('em_id',None) ) # 摄像头id
#     width = strip_whitespace(request.args.get('width',1920))  # 视频宽度
#     height = strip_whitespace(request.args.get('height',1080))  # 视频高度
#     frame_r = strip_whitespace(request.args.get('frame_r',1000))  # 比特率
#     baud_b = strip_whitespace(request.args.get('baud_b',25))  # 帧率
#     stream_data_flag = strip_whitespace(request.args.get('stream_data_flag',None))  # 运行标识  1运行  3 删除
#     video_status = strip_whitespace(request.args.get('video_status','1'))  # 运行标识   1 实时视频  2录像回放
#     start_time = strip_whitespace(request.args.get('start_time',None))  # 运行标识   开始时间
#     end_time = strip_whitespace(request.args.get('end_time',None))  # 运行标识   结束时间
#     model_id = strip_whitespace(request.args.get('model_id',None))  # 模型id
#
#     rtsp_url = ''
#     # 参数构建判断是否为空
#     params = [rtmp_server_ip, em_id, width, height, frame_r, baud_b, stream_data_flag,model_id]
#
#     if not all(params):
#         return jsonify({'code': 400, 'msg': '设备数据有未填写项'})
#
#     r3 = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, decode_responses=True, db=3)
#
#     # 获取模型路径
#     model_path = db.session.query(Algorithm_library).filter(Algorithm_library.id==model_id).first()
#     if not model_path:
#         return jsonify({'code': 400, 'msg': '该模型不存在!'})
#
#     # 获取摄像头信息
#     em_data = db.session.query(Equipment).filter(Equipment.id == em_id).first()
#     print(em_data,'111111')
#
#     if em_data:
#         if em_data.equipment_type == '安防平台':
#             rtsp_url = em_data.Hik_rtsp_url
#         else:
#
#             # 获取父设备信息（若存在）
#             par_id_ip = None
#             if em_data.VCR_data_id and em_data.parent_id:
#                 par_id_ip = db.session.query(Equipment).filter(Equipment.id == em_data.parent_id).first()
#
#             # 根据 video_status 生成对应 RTSP URL
#             is_history = (video_status != '1')
#             rtsp_url = get_rtsp_url(em_data, par_id_ip, is_history, start_time, end_time)
#
#             if not rtsp_url:
#                 return jsonify({'code': 400, 'msg': '无法生成有效的 RTSP 流 URL!'})
#
#             print("生成的 RTSP URL:", rtsp_url)
#
#             def extract_ip_from_rtsp(rtsp_url):
#                 """从 RTSP URL 中提取 IP 地址"""
#                 # 使用正则表达式匹配 IP 地址
#                 match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', rtsp_url)
#
#                 if match:
#                     return match.group(1)
#                 else:
#                     return None
#
#             try:
#                 # 提取ip
#                 ip_address = extract_ip_from_rtsp(rtsp_url)
#                 print("提取的 IP 地址:", ip_address)
#
#                 pinger = Pinger(target_host=ip_address)
#                 delay = pinger.ping_once()
#                 if delay == None:
#                     return jsonify({'code': 400, 'msg': '当前监控点不在线!'})
#             except Exception as e:
#                     return jsonify({'code': 400, 'msg': '当前监控点不在线!'})
#
#         # 定义一个字典来保存要设置的键值对
#         data_to_set = {
#             "rtsp_url": rtsp_url,
#             "rtmp_server_ip": rtmp_server_ip,
#             "width": width,
#             "height": height,
#             "frame_r": frame_r,
#             "baud_b": baud_b,
#             "stream_data_flag": stream_data_flag,
#             "model_path": model_path.algorithm_path,
#         }
#
#         data_list.append(data_to_set)
#
#         # 使用 r3 直接设置每个键值对
#         for key, value in data_to_set.items():
#             print(f"设置 {key} = {value} 到 r3")  # 打印设置内容
#             r3.set(key, value)
#
#         return jsonify({'code': 200,'msg':'推流成功','flv_url':'http://{}:8080/live/stream.flv'.format(rtmp_server_ip)})
#     else:
#         return jsonify({'code':400,'msg':'设备不存在!'})


# 实时视频状态检测（视频分析）
@video_view.route('/real_time_video_status', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def real_time_video_status():
    res = video_service.real_time_video_status()
    return jsonify(res)


# 实时视频停止推流（视频分析）
@video_view.route('/real_time_video_stop', methods=['GET', 'POST'])
# @jwt_required()
@jwt_required_with_refresh
def real_time_video_stop():
    body = request.get_json(silent=True) or {}
    res = video_service.real_time_video_stop(body.get('session_token') or request.args.get('session_token'), get_jwt_identity())
    return jsonify(res)


@video_view.route('/real_time_video_keepalive', methods=['POST'])
@jwt_required_with_refresh
def real_time_video_keepalive():
    from service.playback_session import keep_temporary_playback
    body = request.get_json(silent=True) or {}
    return jsonify(keep_temporary_playback(body.get('session_token'), get_jwt_identity()))


# 报警视频停止推流（视频分析）
@video_view.route('/alg_video_stop', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def alg_video_stop():
    res = video_service.alg_video_stop()
    return jsonify(res)



# 报警配置视频推送（视频分析）
@video_view.route('/alg_conf_video', methods=['GET'])
# @jwt_required()
def alg_conf_video():
    rtmp_server_ip = DB_HOST
    config_id = strip_whitespace(request.args.get('config_id', None))
    width = strip_whitespace(request.args.get('width', 1080))
    height = strip_whitespace(request.args.get('height', 1920))
    frame_r = strip_whitespace(request.args.get('frame_r', 1300))
    baud_b = strip_whitespace(request.args.get('baud_b', 6))
    stream_data_flag = strip_whitespace(request.args.get('stream_data_flag', 0))
    res = video_service.alg_conf_video(rtmp_server_ip, config_id, width, height, frame_r, baud_b, stream_data_flag)
    return jsonify(res)

# 报警配置视频状态检测（视频分析）
@video_view.route('/alg_status_video', methods=['GET'])
def alg_status_video():
    r3 = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, decode_responses=True, db=4)
    video_type = r3.get('video_type')
    if video_type == '1':
        return jsonify({'code': 200, 'video_type': video_type})
    elif video_type=='2':
        return jsonify({'code': 201, 'video_type': video_type})
    else:
        return jsonify({'code':203,'video_type':video_type})


# 报警列表监控点录像机ip，账密，通道号返回接口（视频分析）
@video_view.route('/video_playback', methods=['GET'])
def video_playback():
    equipment_id = strip_whitespace(request.args.get('id', None))
    res = video_service.video_playback(equipment_id)
    return jsonify(res)


@video_view.route('/start_forward_video', methods=['GET'])
def start_forward_video():
    em_id = strip_whitespace(request.args.get('em_id', None))
    res = video_service.start_forward_video(em_id)
    return jsonify(res)

@video_view.route('/stop_forward_video', methods=['GET'])
def stop_forward_video():
    em_id = strip_whitespace(request.args.get('em_id', None))
    res = video_service.stop_forward_video(em_id)
    return jsonify(res)

