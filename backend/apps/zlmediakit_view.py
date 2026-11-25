from flask import Blueprint, request, jsonify
from service.zlmediakit_service import ZLMediaKitService

# 创建蓝图
zlmediakit_view = Blueprint('zlmediakit_view', __name__)

@zlmediakit_view.route('/addStreamProxy', methods=['POST'])
def add_stream():
    """
    添加一个新的流（推流）
    """
    rtsp_list = request.form.get('rtsp_list')
    equipment_name = request.form.get('equipment_name')
    enable_rtsp = request.form.get('enable_rtsp', False)
    enable_hls = request.form.get('enable_hls', False)
    enable_hls_fmp4 = request.form.get('enable_hls_fmp4', False)
    enable_rtmp = request.form.get('enable_rtmp', False)
    enable_ts = request.form.get('enable_ts', False)
    enable_fmp4 = request.form.get('enable_fmp4', False)

    result = ZLMediaKitService.add_stream(
        rtsp_list=rtsp_list,
        equipment_name=equipment_name,
        enable_rtsp=enable_rtsp,
        enable_hls=enable_hls,
        enable_hls_fmp4=enable_hls_fmp4,
        enable_rtmp=enable_rtmp,
        enable_ts=enable_ts,
        enable_fmp4=enable_fmp4
    )
    return jsonify(result)

@zlmediakit_view.route('/stream/play/<stream_key>', methods=['GET'])
def play_stream(stream_key):
    """
    播放流媒体（带有效期验证）
    """
    activate_key = request.args.get('activate_key')
    result = ZLMediaKitService.play_stream(activate_key=activate_key, stream_key=stream_key)
    return jsonify(result)

@zlmediakit_view.route('/delStreamProxy', methods=['POST'])
def delete_stream():
    """Close selected streams from JSON or form data."""
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'code': 400, 'msg': '请求JSON必须是包含ids的对象'})
        ids_str = payload.get('ids')
    else:
        ids_str = request.form.get('ids')
    result = ZLMediaKitService.delete_stream(ids_str=ids_str)
    return jsonify(result)

@zlmediakit_view.route('/stream/list', methods=['GET'])
def list_streams():
    """
    列出所有流媒体
    """
    result = ZLMediaKitService.list_streams()
    return jsonify(result)

@zlmediakit_view.route('/getMediaList', methods=['POST'])
def get_media_list_route():
    """
    获取流列表，可选筛选参数
    """
    key = request.form.get('key')
    schema = request.form.get('schema')
    camera_name = request.form.get('camera_name')

    result = ZLMediaKitService.get_media_list(key=key, schema=schema, camera_name=camera_name)
    return jsonify(result)

@zlmediakit_view.route('/getMediaPlayerList', methods=['POST'])
def get_media_player_list_route():
    """
    获取某个流的观看者列表
    """
    schema = request.form.get('schema', 'rtmp')
    vhost = request.form.get('vhost', '__defaultVhost__')
    app = request.form.get('app')
    id = request.form.get('id')

    if not app:
        return jsonify({'code': 400, 'msg': '参数不完整，必须提供 app 和 stream'})

    result = ZLMediaKitService.get_media_player_list(schema=schema, vhost=vhost, app=app, id=id)
    return jsonify(result)

@zlmediakit_view.route('/listStreamProxy', methods=['POST'])
def list_stream_proxy_route():
    """
    获取拉流代理列表
    """
    result = ZLMediaKitService.list_stream_proxy()
    return jsonify(result)

@zlmediakit_view.route('/getServerConfig', methods=['POST'])
def get_server_config_route():
    """
    获取服务器配置
    """
    result = ZLMediaKitService.get_server_config()
    return jsonify(result)

@zlmediakit_view.route('/restartServer', methods=['POST'])
def restart_server_route():
    """
    重启服务器
    """
    result = ZLMediaKitService.restart_server()
    return jsonify(result)

@zlmediakit_view.route('/getWorkThreadsLoad', methods=['POST'])
def get_work_threads_load_route():
    """
    获取各后台 epoll(或 select)线程负载以及延时
    """
    result = ZLMediaKitService.get_work_threads_load()
    return jsonify(result)

@zlmediakit_view.route('/getStatistic', methods=['POST'])
def get_statistic_route():
    """
    获取主要对象个数统计，主要用于分析内存性能
    """
    result = ZLMediaKitService.get_statistic()
    return jsonify(result)

@zlmediakit_view.route('/getAllSession', methods=['POST'])
def getAllSession_route():
    """
    获取版本信息 如分支，commit id, 编译时间
    """
    result = ZLMediaKitService.get_all_session()
    return jsonify(result)

@zlmediakit_view.route('/kick_session', methods=['POST'])
def kick_session_route():
    """
    踢出会话
    """
    id = request.form.get('id')
    if not id:
        return jsonify({'code': 400, 'msg': '参数不完整，必须提供id'})

    result = ZLMediaKitService.kick_session(id=id)
    return jsonify(result)

@zlmediakit_view.route('/version', methods=['POST'])
def get_version_route():
    """
    获取版本信息 如分支，commit id, 编译时间
    """
    result = ZLMediaKitService.get_version()
    return jsonify(result)


@zlmediakit_view.route('/recovery/status', methods=['GET'])
def recovery_status_route():
    """Read sanitized saved recovery status; never triggers a recovery attempt."""
    try:
        from service.stream_recovery_monitor import get_bound_recovery_status
        result = get_bound_recovery_status()
        if not isinstance(result, dict) or result.get('code') != 200:
            return jsonify({'code': 503, 'msg': '暂时无法读取后台恢复状态，请稍后刷新'}), 503
        return jsonify(result)
    except Exception:
        return jsonify({'code': 503, 'msg': '暂时无法读取后台恢复状态，请稍后刷新'}), 503
