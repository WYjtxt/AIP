# native-recorder-sync-v2
from common.nvr_sync_runtime import (channel_key as _nvr_channel_key, inventory_keys as _nvr_inventory_keys,
    channel_name as _nvr_channel_name, channel_code as _nvr_channel_code, online_value as _nvr_online_value)
# native-recorder-channel-identity-v1
from service.recorder_binding_identity import channel_key
from data.equipment_model_data import EquipmentData
from config.configs import children_list_get_code
from model.admin import db
from config.configs import *
import config.configs as configs  # 导入模型字段
from config.zlk_conf import *
from service.algorithm_model_service import *

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value



def _get_rtsp_url_by_equipment_type(equipment_data):
    """
    根据设备类型获取RTSP流地址
    返回: RTSP URL字符串，如果无法获取则返回None
    """
    equipment_type = equipment_data.equipment_type

    # 摄像头类型：直接使用IP、用户名、密码构建RTSP地址
    if equipment_type == '摄像头':
        if equipment_data.equipment_ip and equipment_data.equipment_uname and equipment_data.equipment_password:
            if equipment_data.manufacturer_type == '宇视':
                from urllib.parse import quote
                return 'rtsp://{}:{}@{}:554/media/video1'.format(
                    quote(str(equipment_data.equipment_uname), safe=''),
                    quote(str(equipment_data.equipment_password), safe=''),
                    equipment_data.equipment_ip)
            elif equipment_data.manufacturer_type == '艾斯卡普':
                return f'rtsp://{equipment_data.equipment_uname}:{equipment_data.equipment_password}@{equipment_data.equipment_ip}/stream1'
            elif equipment_data.manufacturer_type == '海康':
                from urllib.parse import quote
                return 'rtsp://{}:{}@{}:554/Streaming/Channels/101'.format(
                    quote(str(equipment_data.equipment_uname), safe=''),
                    quote(str(equipment_data.equipment_password), safe=''),
                    equipment_data.equipment_ip)
            elif equipment_data.manufacturer_type == '大华':
                from urllib.parse import quote
                return 'rtsp://{}:{}@{}:554/cam/realmonitor?channel=1&subtype=0'.format(
                    quote(str(equipment_data.equipment_uname), safe=''),
                    quote(str(equipment_data.equipment_password), safe=''),
                    equipment_data.equipment_ip)
            else:
                return f'rtsp://{equipment_data.equipment_uname}:{equipment_data.equipment_password}@{equipment_data.equipment_ip}'
    # 录像机类型：通过父设备和通道号获取RTSP地址
    if equipment_type == 'AI单光摄像头':
        if equipment_data.equipment_ip and equipment_data.equipment_uname and equipment_data.equipment_password:
            return f'rtsp://{equipment_data.equipment_ip}:8554/stream11'

    elif equipment_type == '录像机':
        if equipment_data.parent_id and equipment_data.code:
            return get_children_rtsp_new(equipment_data.parent_id, equipment_data.code, 1,
                                         equipment_data.equipment_aisles)

    # 视频中心存储类型
    elif equipment_type == '视频中心存储':
        if equipment_data.parent_id and equipment_data.code:
            return get_children_rtsp_new(equipment_data.parent_id, equipment_data.code, 1)

    # 特殊摄像头类型
    elif equipment_type == '特殊摄像头':
        if equipment_data.parent_id and equipment_data.code:
            return get_children_rtsp_new(equipment_data.parent_id, equipment_data.code, 2)
    elif equipment_type == 'AI双光摄像头':
        if equipment_data.parent_id and equipment_data.code:
            return get_children_rtsp_new(equipment_data.parent_id, equipment_data.code, 2)
    # 浙江双视热成像类型
    elif equipment_type == '浙江双视热成像':
        if equipment_data.equipment_ip and equipment_data.equipment_uname and equipment_data.equipment_password:
            return f'rtsp://{equipment_data.equipment_uname}:{equipment_data.equipment_password}@{equipment_data.equipment_ip}:554/live/chn0'

    # 安防平台类型
    elif equipment_type == '安防平台':
        if hasattr(equipment_data, 'Hik_rtsp_url') and equipment_data.Hik_rtsp_url:
            return equipment_data.Hik_rtsp_url

    # 紫光华智类型
    elif equipment_type == '紫光华智':
        if hasattr(equipment_data, 'Ziguang_ape_rtsp_url') and equipment_data.Ziguang_ape_rtsp_url:
            return equipment_data.Ziguang_ape_rtsp_url

    return None


# 获取视频为录像机子集或者特殊摄像头的返回格式  参数为  父级id  子集通道code
def _uniview_selected_channel_url(stored_url, ip, channel, user, password):
    """Honor a saved stream only for this recorder and physical channel."""
    from urllib.parse import quote, urlsplit
    try:
        if not isinstance(stored_url, str) or any(c.isspace() for c in stored_url):
            return None
        if not str(channel).isdigit() or int(channel) < 1:
            return None
        parsed = urlsplit(stored_url)
        paths = ('/unicast/c{}/s0/live'.format(int(channel)),
                 '/unicast/c{}/s1/live'.format(int(channel)))
        if (parsed.scheme != 'rtsp' or parsed.hostname != str(ip) or
                parsed.port not in (None, 554) or parsed.username is not None or
                parsed.password is not None or parsed.query or parsed.fragment or
                parsed.path not in paths or '?' in stored_url or '#' in stored_url):
            return None
        return 'rtsp://{}:{}@{}:554{}'.format(
            quote(str(user), safe=''), quote(str(password), safe=''), ip, parsed.path)
    except (TypeError, ValueError):
        return None


def get_children_rtsp_new(id, code, type, equipment_aisles=None):
    # 检查 id 是否为 None 或者数据库中不存在对应的记录
    if id is None:
        return None

    parent_data = db.session.query(Equipment).filter(Equipment.id == id).first()

    # 检查 parent_data 是否存在
    if parent_data is None:
        return None

    # 检查 parent_data.VCR_data_id 是否存在再查询 vcr_data
    if parent_data.VCR_data_id is not None:
        vcr_data = db.session.query(VCR_data).filter(VCR_data.id == parent_data.VCR_data_id).first()
    else:
        vcr_data = None

    user = parent_data.equipment_uname
    password = parent_data.equipment_password
    ip = parent_data.equipment_ip

    if parent_data.manufacturer_type == '海康':
        if type == 1:
            result = 'rtsp://{}:{}@{}:554/Streaming/Unicast/Channels/{}'.format(user, password, ip, code)
        else:
            result = 'rtsp://{}:{}@{}:554/Streaming/Channels/{}'.format(user, password, ip, code)
    elif parent_data.manufacturer_type == '宇视':
        child_device = db.session.query(Equipment).filter(
            Equipment.parent_id == id,
            Equipment.equipment_aisles == equipment_aisles,
            Equipment.code == str(code)
        ).first()
        selected_url = getattr(child_device, 'Onvif_rtsp_url', None)
        if selected_url:
            result = _uniview_selected_channel_url(
                selected_url, ip, equipment_aisles, user, password)
        else:
            result = 'rtsp://{}:{}@{}:554/unicast/c{}/s1/live'.format(user, password, ip, equipment_aisles)
    elif parent_data.manufacturer_type == '阳光三极':
        if code == '101':
            result = 'rtsp://{}:8554/stream11'.format(ip)
        elif code == '201':
            result = 'rtsp://{}:8554/stream21'.format(ip)
    elif parent_data.manufacturer_type == '大华' and vcr_data and vcr_data.vcr_way == 'Onvif':
        # 查找子设备中对应的通道，使用其Onvif_rtsp_url
        child_device = db.session.query(Equipment).filter(
            Equipment.parent_id == id,
            Equipment.equipment_aisles == equipment_aisles
        ).first()

        if child_device and child_device.Onvif_rtsp_url:
            # 在URL中添加用户名和密码
            onvif_rtsp = child_device.Onvif_rtsp_url
            if onvif_rtsp.startswith('rtsp://'):
                # 在RTSP协议后添加认证信息
                result = 'rtsp://{}:{}@{}'.format(user, password, onvif_rtsp[7:])
            else:
                result = None
        else:
            result = None
    else:
        result = None
    return result


def _extract_stream_from_key(zlk_key):
    """
    从zlk_key中提取stream ID
    zlk_key格式: vhost/app/stream 例如: camera.example/openUrl/stream-id
    返回: stream ID
    """
    if not zlk_key:
        return None
    # 按 '/' 分割，取最后一部分作为 stream ID
    parts = str(zlk_key).split('/')
    if len(parts) >= 3:
        return parts[-1]  # 返回最后一部分（stream ID）
    return None


def _link_equipment_to_zlk_data(equipment_data, rtsp, equipment_name, zlk_key=None):
    """
    兜底用 ZLK 关联逻辑
    - 不覆盖已有绑定
    - 不做激进反查
    """
    if not zlk_key:
        print("[关联失败] 缺少 zlk_key")
        return False

    # 已有关联直接返回
    if equipment_data.zlk_dat_id:
        print(
            f"[跳过] 设备 {equipment_data.id} "
            f"已绑定 zlk_dat_id={equipment_data.zlk_dat_id}"
        )
        return True

    try:
        stream_id = _extract_stream_from_key(zlk_key)
        if not stream_id:
            print("[关联失败] 无法解析 stream_id")
            return False

        # 只按 stream_id 查（避免 rtsp / name 不稳定）
        zlk_data = db.session.query(Zlk_data).filter(
            Zlk_data.zlk_live == str(stream_id)
        ).order_by(Zlk_data.id.desc()).first()

        if not zlk_data:
            print(
                f"[关联失败] 未找到 Zlk_data(stream={stream_id})"
            )
            return False
        # 关键逻辑：从设备表获取IP，为Zlk_data赋值（无需异步方法传递）
        equipment_ip = equipment_data.equipment_ip
        if equipment_ip and not zlk_data.equipment_ip:
            zlk_data.equipment_ip = equipment_ip
            db.session.add(zlk_data)  # 提交更新
            db.session.commit()  # 同步版本需要显式提交
            print(f"[兜底赋值成功] Zlk_data(ID:{zlk_data.id}) 已填充equipment_ip={equipment_ip}")

        # 二次保护：不覆盖已有绑定
        if equipment_data.zlk_dat_id and equipment_data.zlk_dat_id != zlk_data.id:
            print(
                f"[跳过覆盖] 设备 {equipment_data.id} "
                f"已有 zlk_dat_id={equipment_data.zlk_dat_id}"
            )
            return False

        equipment_data.zlk_dat_id = zlk_data.id
        db.session.commit()
        print(
            f"[兜底成功] 设备 {equipment_name}(ID:{equipment_data.id}) "
            f"→ Zlk_data(ID:{zlk_data.id})"
        )
        return True

    except Exception as e:
        print(
            f"[异常] 设备 {equipment_data.id} 兜底关联异常: {str(e)}"
        )
        db.session.rollback()  # 异常时回滚
        return False




def _safe_stream_failure(error):
    """Keep a useful failure reason while removing source credentials."""
    import re
    message = str(error or '流媒体创建或设备绑定失败，请检查后台日志。')
    message = re.sub(r'(?i)(?:https?|rtsps?)(?:://|%3a%2f%2f)[^\s\'"<>]+',
                     '<流地址已隐藏>', message)
    message = re.sub(r'(?i)(\b(?:secret|password|authorization)\b[\'\"]?\s*[=:]\s*[\'\"]?)[^&\s,\'"}]+',
                     r'\1<已隐藏>', message)
    if re.search(r'\b401\b|\bunauthorized\b', message, re.I):
        return 'RTSP认证失败，请检查设备账号、密码及访问权限（401 Unauthorized）。'
    if re.search(r'\b(?:SETUP|DESCRIBE|PLAY)\s*:\s*503\b|503\s+ServerUnavailable', message, re.I):
        return '摄像头RTSP服务暂不可用（503）：设备拒绝建立视频会话，请检查取流会话资源和设备状态。'
    if re.search(r'\bend of file\b|\beof\b|invalid data found when processing input', message, re.I):
        return 'RTSP响应无效或连接被对端关闭（EOF），请检查摄像头取流服务、连接数限制及访问策略。'
    if 'connection refused' in message.lower():
        return 'RTSP连接被拒绝，请核对设备类型、服务及端口。若为AI单光摄像头，请选择对应设备类型（8554/stream11）；码流类型按设备实际编码选择H264或H265。'
    if '请求超时' in message or re.search(r'timed?\s*out|timeout', message, re.I):
        return '连接流媒体或摄像头超时，请检查服务、网络及RTSP地址。'
    if re.search(r'\b404\b|not found', message, re.I):
        return 'RTSP地址或通道不存在，请核对流地址和通道（404 Not Found）。'
    if re.search(r'\b461\b|unsupported transport', message, re.I):
        return '摄像头不支持当前RTSP传输方式，请检查设备协议配置（461 Unsupported Transport）。'
    return message[:400]


def _set_stream_failure(failure_details, error):
    if failure_details is not None:
        failure_details['msg'] = _safe_stream_failure(error)


def create_zlk_data_for_equipment(equipment_data, failure_details=None):
    """
    为设备创建 ZLK 流媒体并绑定关系
    优先使用 add_stream_proxy 返回的 zlk_id
    仅在兜底情况下才走旧的反查逻辑

    Args:
        equipment_data: 设备数据对象，需包含 id/equipment_name/equipment_ip 等属性

    Returns:
        str/None: 成功返回绑定的 zlk_dat_id，失败返回 None
    """
    # 提取核心字段，减少重复属性访问
    from config.zlk_conf import  add_stream_proxy
    equipment_id = equipment_data.id
    equipment_name = equipment_data.equipment_name
    equipment_ip = equipment_data.equipment_ip
    # 获取RTSP流信息
    rtsp_url = _get_rtsp_url_by_equipment_type(equipment_data)
    if not rtsp_url:
        _set_stream_failure(failure_details, '无法生成设备RTSP地址，请检查设备类型及连接参数。')
        print(f"[跳过] 设备 {equipment_name}(ID:{equipment_id}) 无法获取 RTSP 流地址")
        return None

    try:
        # 调用同步版本的add_stream_proxy（移除异步事件循环）
        result = add_stream_proxy(
            url=rtsp_url,
            url_name=equipment_name,
            enable_rtsp=True,
            enable_fmp4=True
        )

        # 部分宇视通道仅提供主码流，子码流失败时尝试同一通道的主码流。
        if (not result or result.get('code') != 200) and '/s1/live' in rtsp_url:
            parent = db.session.query(Equipment).filter(Equipment.id == equipment_data.parent_id).first()
            if parent and parent.manufacturer_type == '宇视':
                result = add_stream_proxy(
                    url=rtsp_url.replace('/s1/live', '/s0/live'),
                    url_name=equipment_name,
                    enable_rtsp=True,
                    enable_fmp4=True
                )

        # 校验接口返回结果
        if not result or result.get('code') != 200:
            error_msg = result.get('msg') if isinstance(result, dict) else '流媒体接口无返回结果'
            _set_stream_failure(failure_details, error_msg)
            print(f"[失败] 设备 {equipment_name}(ID:{equipment_id}) 创建流失败: {_safe_stream_failure(error_msg)}")

            # 检查是否为401 Unauthorized错误
            if '401 Unauthorized' in _safe_stream_failure(error_msg):
                return "401_UNAUTHORIZED"

            return None

        data = result.get('data', {})
        zlk_data_id = data.get('zlk_id')

        # 优先使用zlk_id直接绑定（主逻辑）
        if zlk_data_id:
            zlk_id_result = _handle_zlk_id_binding(
                equipment_data, zlk_data_id, equipment_ip, equipment_id
            )
            return zlk_id_result

        # 兜底逻辑：使用key关联（兼容旧逻辑）
        zlk_key = data.get('key')
        if not zlk_key:
            print(f"[异常] 设备 {equipment_id} 接口返回无 zlk_id/key，无法关联ZLK")
            return None

        print(f"[兜底] 设备 {equipment_name}(ID:{equipment_id}) 使用旧逻辑关联 ZLK")
        if _link_equipment_to_zlk_data(equipment_data, rtsp_url, equipment_name, zlk_key):
            db.session.refresh(equipment_data)
            return equipment_data.zlk_dat_id

        print(f"[失败] 设备 {equipment_id} 兜底关联ZLK失败")
        return None

    except Exception as e:
        # 新增全局异常捕获，避免程序崩溃
        _set_stream_failure(failure_details, str(e))
        print(f"[异常] 设备 {equipment_name}(ID:{equipment_id}) 创建ZLK流时发生错误: {_safe_stream_failure(e)}")
        db.session.rollback()  # 异常时回滚数据库操作
        return None


def _handle_zlk_id_binding(equipment_data, zlk_data_id, equipment_ip, equipment_id):
    """
    处理通过zlk_id直接绑定设备的逻辑

    Args:
        equipment_data: 设备数据对象
        zlk_data_id: ZLK数据ID
        equipment_ip: 设备IP地址
        equipment_id: 设备ID

    Returns:
        str/None: 绑定成功返回zlk_data_id，否则返回None
    """
    equipment_name = equipment_data.equipment_name

    # 检查是否已有绑定且不覆盖
    if equipment_data.zlk_dat_id and equipment_data.zlk_dat_id != zlk_data_id:
        print(f"[跳过覆盖] 设备 {equipment_id} 已有 zlk_dat_id={equipment_data.zlk_dat_id}")
        return equipment_data.zlk_dat_id

    try:
        # 绑定设备与ZLK ID
        equipment_data.zlk_dat_id = zlk_data_id
        db.session.commit()  # 同步版本显式提交
        print(f"[成功] 设备 {equipment_name}(ID:{equipment_id}) 直接绑定 Zlk_data(ID:{zlk_data_id})")

        # 更新ZLK数据的设备IP和ID
        zlk_data = db.session.query(Zlk_data).filter(Zlk_data.id == zlk_data_id).first()
        if zlk_data:
            update_fields = []
            if equipment_ip and not zlk_data.equipment_ip:
                zlk_data.equipment_ip = equipment_ip
                update_fields.append(f"equipment_ip={equipment_ip}")
            if equipment_id and not zlk_data.equipment_id:
                zlk_data.equipment_id = equipment_id
                update_fields.append(f"equipment_id={equipment_id}")

            # 有字段更新才提交，减少数据库操作
            if update_fields:
                db.session.add(zlk_data)
                db.session.commit()  # 同步版本显式提交
                print(f"[赋值成功] Zlk_data(ID:{zlk_data.id}) 已填充: {', '.join(update_fields)}")

        return zlk_data_id

    except Exception as e:
        print(f"[失败] 设备 {equipment_id} 绑定Zlk_data(ID:{zlk_data_id}) 失败: {str(e)}")
        db.session.rollback()
        return None


def delete_zlk_data_for_equipment(equipment_id):
    """
    删除设备关联的 Zlk_data 记录，包括调用ZLK接口删除流和同步删除数据库记录
    参数:
        equipment_id: 设备ID（可以是单个ID或ID列表）
    返回: 删除的设备数量
    """
    # 支持单个ID或ID列表
    from config.zlk_conf import del_stream_proxy
    if isinstance(equipment_id, (list, tuple)):
        equipment_ids = equipment_id
    else:
        equipment_ids = [equipment_id]

    deleted_count = 0

    for eq_id in equipment_ids:
        try:
            equipment = db.session.query(Equipment).filter_by(id=eq_id).first()
            if not equipment or not equipment.zlk_dat_id:
                continue

            # 获取zlk_data记录
            zlk_data = db.session.query(Zlk_data).filter_by(id=equipment.zlk_dat_id).first()
            if not zlk_data:
                # 如果Zlk_data记录不存在，只清除关联
                equipment.zlk_dat_id = None
                db.session.commit()
                continue

            # 调用ZLK接口删除流
            if zlk_data.zlk_key:
                try:
                    # 直接调用同步版del_stream_proxy函数
                    result = del_stream_proxy(zlk_data.zlk_key)
                    if result.get('code') == 200:
                        print(f"设备 {equipment.equipment_name} (ID: {eq_id}) ZLK流删除成功: {zlk_data.zlk_key}")
                    else:
                        print(f"设备 {equipment.equipment_name} (ID: {eq_id}) ZLK流删除失败: {result.get('msg', '未知错误')}")
                except Exception as e:
                    print(f"设备 {equipment.equipment_name} (ID: {eq_id}) 调用ZLK删除接口时出错: {str(e)}")

            # 解除双向关联
            equipment.zlk_dat_id = None
            db.session.delete(zlk_data)
            db.session.commit()

            deleted_count += 1
            print(f"设备 {equipment.equipment_name} (ID: {eq_id}) 流媒体数据删除成功")

        except Exception as e:
            print(f"删除设备 {eq_id} 的流媒体数据时发生异常: {str(e)}")
            db.session.rollback()

    return deleted_count


class EquipmentService:
    """设备服务类"""

    @staticmethod
    def process_equipment_type(equipment_type):
        """
        处理设备类型
        :param equipment_type: 设备类型ID
        :return: 设备类型名称
        """
        return (configs.equipment_type[int(equipment_type) - 1])['value'] if equipment_type else 1

    @staticmethod
    def process_manufacturer_type(manufacturer_type):
        """
        处理厂商类型
        :param manufacturer_type: 厂商类型ID
        :return: 厂商类型名称
        """
        return (configs.manufacturer_type[int(manufacturer_type) - 1])['value'] if manufacturer_type else 1

    @staticmethod
    def process_equipment_codetype(equipment_codetype):
        """
        处理码流类型
        :param equipment_codetype: 码流类型ID
        :return: 码流类型名称
        """
        return (configs.equipment_codetype[int(equipment_codetype) - 1])['value'] if equipment_codetype else 1

    @staticmethod
    def equipment_create_service(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                                 equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                                 children_list, uwb_ip=None,alarm_device_ip = None):
        """service层：设备创建业务逻辑处理"""
        try:
            # 参数转换
            equipment_type = (configs.equipment_type[int(equipment_type) - 1])['value'] if equipment_type else 1
            manufacturer_type = (configs.manufacturer_type[int(manufacturer_type) - 1])[
                'value'] if manufacturer_type else 1
            equipment_codetype = (configs.equipment_codetype[int(equipment_codetype) - 1])[
                'value'] if equipment_codetype else 1

            # 艾斯卡普摄像仪（添加uwb数据）
            uwb_ip_value = uwb_ip if (manufacturer_type == '艾斯卡普' and uwb_ip) else None

            # 参数校验
            params = [equipment_type, equipment_name, equipment_ip, equipment_uname, equipment_password, Mine_id]
            if not all(params):
                return {'code': 400, 'msg': '设备数据有未填写项'}

            # 查询设备是否存在
            equipment_result = EquipmentData.check_equipment_exists(equipment_ip)
            if equipment_result:
                if equipment_type == '摄像头' and getattr(equipment_result, 'parent_id', None):
                    existing_parent = EquipmentData.get_equipment_by_id(equipment_result.parent_id)
                    if existing_parent and existing_parent.equipment_type == '录像机':
                        source_name = '{} → {}'.format(
                            existing_parent.equipment_name or existing_parent.equipment_ip,
                            equipment_result.equipment_name or equipment_result.equipment_ip)
                        return {'code': 400, 'msg': '该IP已通过录像机通道接入（{}），无需重复添加。摄像头直连需先确认RTSP可用。'.format(source_name)}
                return {'code': 400, 'msg': '设备已经存在'}

            # 处理录像机类型
            if equipment_type == '录像机':
                return EquipmentService._handle_vcr_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                            equipment_uname, equipment_password, equipment_aisles, equipment_codetype,
                                            Mine_id, flower_frames, children_list)

            # 处理特殊摄像头类型
            elif equipment_type == '特殊摄像头':
                return EquipmentService._handle_special_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                                       equipment_uname, equipment_password, equipment_aisles,
                                                       equipment_codetype, Mine_id, flower_frames, children_list)

            # 处理普通摄像头类型
            elif equipment_type == '摄像头':
                return EquipmentService._handle_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                               equipment_uname, equipment_password, equipment_aisles,
                                               equipment_codetype, Mine_id, flower_frames, uwb_ip_value,alarm_device_ip)
            elif equipment_type == 'AI单光摄像头':
                return EquipmentService._handle_ai_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                               equipment_uname, equipment_password, equipment_aisles,
                                               equipment_codetype, Mine_id, flower_frames, uwb_ip_value,alarm_device_ip)
            elif equipment_type == 'AI双光摄像头':
                return EquipmentService._handle_ai_dual_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                                       equipment_uname, equipment_password, equipment_aisles,
                                                       equipment_codetype, Mine_id, flower_frames, children_list,alarm_device_ip)
            # 处理浙江双视热成像类型
            elif equipment_type == '浙江双视热成像':
                return EquipmentService._handle_zjss_thermal_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                                     equipment_uname, equipment_password, equipment_aisles,
                                                     equipment_codetype, Mine_id, flower_frames, uwb_ip_value)

            else:
                return {'code': 400, 'msg': '不支持的设备类型'}

        except Exception as e:
            db.session.rollback()
            err_msg = f"设备创建失败：{str(e)}"
            print(err_msg)
            return {'code': 400, 'msg': err_msg}

    @staticmethod
    def _handle_vcr_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                             equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                             children_list):
        """service层：处理录像机设备创建"""
        # 添加录像机父设备
        equipment_data = EquipmentData.equipment_create_data(
            equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname, equipment_password,
            equipment_aisles, equipment_codetype, Mine_id, flower_frames
        )

        if children_list:
            children_list = children_list_get_code(children_list)
            for i in children_list:
                child_equipment_data = EquipmentData.equipment_create_data(
                    equipment_data.equipment_type, equipment_data.manufacturer_type, i['equipment_name'],
                    i['equipment_ip'],
                    equipment_data.equipment_uname, equipment_data.equipment_password, i.get('equipment_aisles'),
                    equipment_data.equipment_codetype, equipment_data.Mine_id, flower_frames,
                    parent_id=equipment_data.id,
                    code=i.get('code')
                )
                create_zlk_data_for_equipment(child_equipment_data)

        return {'code': 200, 'msg': '设备添加成功'}

    @staticmethod
    def _handle_special_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip,
                                        equipment_uname, equipment_password, equipment_aisles, equipment_codetype,
                                        Mine_id, flower_frames, children_list):
        """service层：处理特殊摄像头设备创建"""
        # 添加特殊摄像头父设备
        equipment_data = EquipmentData.equipment_create_data(
            equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname, equipment_password,
            equipment_aisles, equipment_codetype, Mine_id, flower_frames
        )
        create_zlk_data_for_equipment(equipment_data)

        if children_list:
            children_list = children_list_get_code(children_list)
            for i in children_list:
                child_equipment_data = EquipmentData.equipment_create_data(
                    equipment_data.equipment_type, equipment_data.manufacturer_type, equipment_data.equipment_name,
                    equipment_data.equipment_ip, equipment_data.equipment_uname, equipment_data.equipment_password,
                    i.get('equipment_aisles'), equipment_data.equipment_codetype, equipment_data.Mine_id, flower_frames,
                    parent_id=equipment_data.id, code=i.get('code')
                )
                create_zlk_data_for_equipment(child_equipment_data)

        return {'code': 200, 'msg': '设备添加成功'}

    @staticmethod
    def _handle_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                                equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                                uwb_ip_value,alarm_device_ip):
        """service层：处理普通摄像头设备创建"""
        pinger = Pinger(target_host=equipment_ip)
        delay = pinger.ping_once()
        # 更新设备在线状态
        if delay is None:
            return {'code': 400, 'msg': '设备不在线'}
        # 先创建设备但不提交
        equipment_data = Equipment(
            equipment_type=equipment_type if equipment_type in ['摄像头', '录像机', '特殊摄像头', '安防平台', '浙江双视热成像'] else None,
            manufacturer_type=manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视',
                                                                         '紫光华智', '艾斯卡普'] else None,
            equipment_name=equipment_name if equipment_name else None,
            equipment_ip=equipment_ip if equipment_ip is not None else None,
            equipment_uname=equipment_uname if equipment_uname else None,
            equipment_password=equipment_password if equipment_password else None,
            equipment_aisles=equipment_aisles if equipment_aisles else None,
            equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
            Mine_id=int(Mine_id) if Mine_id else None,
            flower_frames=flower_frames if flower_frames else None,
            uwb_ip=uwb_ip_value,
            online=1,
            alarm_device_ip=alarm_device_ip
        )
        db.session.add(equipment_data)
        db.session.flush()
        failure_details = {}
        zlk_bind_id = create_zlk_data_for_equipment(equipment_data, failure_details=failure_details)
        if not zlk_bind_id:
            detail = failure_details.get('msg') or _safe_stream_failure(None)
            raise Exception(f"摄像头[{equipment_name}]接入失败：{detail}")
        elif zlk_bind_id == "401_UNAUTHORIZED":
            raise Exception(f"摄像头[{equipment_name}]账号或密码错误。")
        db.session.commit()
        return {'code': 200, 'msg': '设备添加成功'}

    def _handle_ai_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                                equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                                uwb_ip_value,alarm_device_ip):
        """service层：处理普通摄像头设备创建"""
        pinger = Pinger(target_host=equipment_ip)
        delay = pinger.ping_once()
        # 更新设备在线状态
        if delay is None:
            return {'code': 400, 'msg': '设备不在线'}
        # 先创建设备但不提交
        equipment_data = Equipment(
            equipment_type=equipment_type if equipment_type in ['摄像头', '录像机', '特殊摄像头', '安防平台', '浙江双视热成像','AI单光摄像头'] else None,
            manufacturer_type=manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视',
                                                                         '紫光华智', '艾斯卡普', '阳光三极'] else None,
            equipment_name=equipment_name if equipment_name else None,
            equipment_ip=equipment_ip if equipment_ip is not None else None,
            equipment_uname=equipment_uname if equipment_uname else None,
            equipment_password=equipment_password if equipment_password else None,
            equipment_aisles=equipment_aisles if equipment_aisles else None,
            equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
            Mine_id=int(Mine_id) if Mine_id else None,
            flower_frames=flower_frames if flower_frames else None,
            uwb_ip=uwb_ip_value,
            online=1,
            alarm_device_ip=alarm_device_ip
        )
        db.session.add(equipment_data)
        db.session.flush()
        failure_details = {}
        zlk_bind_id = create_zlk_data_for_equipment(equipment_data, failure_details=failure_details)
        if not zlk_bind_id:
            detail = failure_details.get('msg') or _safe_stream_failure(None)
            raise Exception(f"摄像头[{equipment_name}]接入失败：{detail}")
        elif zlk_bind_id == "401_UNAUTHORIZED":
            raise Exception(f"摄像头[{equipment_name}]账号或密码错误。")
        # 往Computing_equipment表中写入一条记录

        prefix = 'YGSJ-'
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        computing_code = prefix + random_part

        computing_equipment = Computing_equipment(
            computing_ip=equipment_ip,
            computing_name=equipment_name,
            computing_code=computing_code,
            computing_user='root',
            computing_password=_required_site_value("AIP_COMPUTING_PASSWORD")
        )
        db.session.add(computing_equipment)
        db.session.commit()


        return {'code': 200, 'msg': '设备添加成功'}

    def _handle_ai_dual_camera_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                                equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                                uwb_ip_value,children_list=None,alarm_device_ip = None):
        # """service层：处理普通摄像头设备创建"""
        # pinger = Pinger(target_host=equipment_ip)
        # delay = pinger.ping_once()
        # # 更新设备在线状态
        # if delay is None:
        #     return {'code': 400, 'msg': '设备不在线'}
        # # 先创建设备但不提交
        # equipment_data = Equipment(
        #     equipment_type=equipment_type if equipment_type in ['摄像头', '录像机', '特殊摄像头', '安防平台', '浙江双视热成像','AI单光摄像头','AI双光摄像头'] else None,
        #     manufacturer_type=manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视',
        #                                                                  '紫光华智', '艾斯卡普'] else None,
        #     equipment_name=equipment_name if equipment_name else None,
        #     equipment_ip=equipment_ip if equipment_ip is not None else None,
        #     equipment_uname=equipment_uname if equipment_uname else None,
        #     equipment_password=equipment_password if equipment_password else None,
        #     equipment_aisles=equipment_aisles if equipment_aisles else None,
        #     equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
        #     Mine_id=int(Mine_id) if Mine_id else None,
        #     flower_frames=flower_frames if flower_frames else None,
        #     uwb_ip=uwb_ip_value,
        #     online=1
        # )
        # db.session.add(equipment_data)
        # db.session.flush()
        # zlk_bind_id = create_zlk_data_for_equipment(equipment_data)
        # if not zlk_bind_id:
        #     raise Exception(f"摄像头[{equipment_name}]rtsp请求占用数已达到最大。")
        # elif zlk_bind_id == "401_UNAUTHORIZED":
        #     raise Exception(f"摄像头[{equipment_name}]账号或密码错误。")
        # # 往Computing_equipment表中写入一条记录
        #
        # prefix = 'YGSJ-'
        # random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        # computing_code = prefix + random_part
        #
        # computing_equipment = Computing_equipment(
        #     computing_ip=equipment_ip,
        #     computing_name=equipment_name,
        #     computing_code=computing_code,
        #     computing_user='root',
        #     computing_password=_required_site_value("AIP_COMPUTING_PASSWORD")
        # )
        # db.session.add(computing_equipment)
        # db.session.commit()

        equipment_data = EquipmentData.equipment_create_data(
            equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname, equipment_password,
            None, equipment_codetype, Mine_id, flower_frames,alarm_device_ip=alarm_device_ip
        )
        child_equipment_data1 = EquipmentData.equipment_create_data(
            equipment_data.equipment_type, equipment_data.manufacturer_type, equipment_data.equipment_name,
            equipment_data.equipment_ip, equipment_data.equipment_uname, equipment_data.equipment_password,
            1, equipment_data.equipment_codetype, equipment_data.Mine_id,
            flower_frames,
            parent_id=equipment_data.id, code='101',alarm_device_ip=alarm_device_ip
        )
        create_zlk_data_for_equipment(child_equipment_data1)
        child_equipment_data2 = EquipmentData.equipment_create_data(
            equipment_data.equipment_type, equipment_data.manufacturer_type, equipment_data.equipment_name,
            equipment_data.equipment_ip, equipment_data.equipment_uname, equipment_data.equipment_password,
            2, equipment_data.equipment_codetype, equipment_data.Mine_id,
            flower_frames,
            parent_id=equipment_data.id, code='201',alarm_device_ip=alarm_device_ip
        )
        create_zlk_data_for_equipment(child_equipment_data2)
        prefix = 'YGSJ-'
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        computing_code = prefix + random_part

        computing_equipment = Computing_equipment(
            computing_ip=equipment_ip,
            computing_name=equipment_name,
            computing_code=computing_code,
            computing_user='root',
            computing_password=_required_site_value("AIP_COMPUTING_PASSWORD")
        )
        db.session.add(computing_equipment)
        db.session.commit()
        return {'code': 200, 'msg': '设备添加成功'}

    @staticmethod
    def _handle_zjss_thermal_creation(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                                      equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                                      uwb_ip_value):
        """service层：处理浙江双视热成像设备创建"""
        # 先创建设备但不提交
        equipment_data = Equipment(
            equipment_type=equipment_type if equipment_type in ['摄像头', '录像机', '特殊摄像头', '安防平台', '浙江双视热成像'] else None,
            manufacturer_type=manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视',
                                                                         '紫光华智', '艾斯卡普'] else None,
            equipment_name=equipment_name if equipment_name else None,
            equipment_ip=equipment_ip if equipment_ip is not None else None,
            equipment_uname=equipment_uname if equipment_uname else None,
            equipment_password=equipment_password if equipment_password else None,
            equipment_aisles=equipment_aisles if equipment_aisles else None,
            equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
            Mine_id=int(Mine_id) if Mine_id else None,
            flower_frames=flower_frames if flower_frames else None,
            uwb_ip=uwb_ip_value,
        )
        db.session.add(equipment_data)
        db.session.flush()
        failure_details = {}
        zlk_bind_id = create_zlk_data_for_equipment(equipment_data, failure_details=failure_details)
        if not zlk_bind_id:
            detail = failure_details.get('msg') or _safe_stream_failure(None)
            raise Exception(f"浙江双视热成像[{equipment_name}]接入失败：{detail}")
        elif zlk_bind_id == "401_UNAUTHORIZED":
            raise Exception(f"浙江双视热成像[{equipment_name}]账号或密码错误。")
        db.session.commit()
        return {'code': 200, 'msg': '设备添加成功'}

    @staticmethod
    def equipment_update(type_s, equipment_name, equipment_data=None):
        """
        设备修改接口
        :param type_s: 操作类型，1为查询，2为修改
        :param equipment_name: 设备ID或名称
        :param equipment_data: 设备数据
        :return: 结果
        """
        try:
            # 查询操作
            if int(type_s) == 1:
                return EquipmentService._process_equipment_query(equipment_name)
            # 修改操作
            else:
                return EquipmentService._process_equipment_modify(equipment_data)
        except Exception as e:
            print(f"设备更新操作出错: {str(e)}")
            return {'code': 500, 'msg': '设备更新操作失败'}

    @staticmethod
    def _process_equipment_query(equipment_id):
        """
        处理设备查询操作
        :param equipment_id: 设备ID
        :return: 查询结果
        """
        # 获取设备详情
        equipment_info = EquipmentData.get_equipment_detail(equipment_id)
        if not equipment_info:
            return {'code': 404, 'msg': '设备不存在'}

        # 构建设备信息列表
        equipment_list = {
            'id': equipment_info.id,
            'equipment_type': equipment_info.equipment_type,
            'equipment_type_num': EquipmentService.get_equipment_type(configs.equipment_type, equipment_info.equipment_type),
            'manufacturer_type': equipment_info.manufacturer_type,
            'flower_frames': equipment_info.flower_frames,
            'equipment_name': equipment_info.equipment_name,
            'equipment_ip': equipment_info.equipment_ip,
            'equipment_uname': equipment_info.equipment_uname,
            'equipment_password': equipment_info.equipment_password,
            'equipment_aisles': equipment_info.equipment_aisles,
            'equipment_codetype': equipment_info.equipment_codetype,
            'equipment_code': equipment_info.code,
            'user_status': equipment_info.user_status,
            'parent_id': equipment_info.parent_id,
            'Mine_id': equipment_info.Mine_id,
            'create_time': (equipment_info.create_time).strftime("%Y-%m-%d %H:%M:%S"),
            'uwb_ip': equipment_info.uwb_ip,
            'alarm_device_ip': equipment_info.alarm_device_ip,
        }

        return {'code': 200, 'data': equipment_list}

    @staticmethod
    def _process_equipment_modify(equipment_data):
        """
        处理设备修改操作
        :param equipment_data: 设备数据
        :return: 修改结果
        """
        # 提取设备ID和类型
        equipment_id = equipment_data.get('id')
        equipment_type = equipment_data.get('equipment_type')

        # 获取设备信息
        equipment = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            return {'code': 404, 'msg': '设备不存在'}

        # 处理设备类型、厂商类型和码流类型
        equipment_type = EquipmentService.process_equipment_type(equipment_type)
        manufacturer_type = EquipmentService.process_manufacturer_type(equipment_data.get('manufacturer_type'))
        equipment_codetype = EquipmentService.process_equipment_codetype(equipment_data.get('equipment_codetype'))

        # 构建设备更新数据
        update_data = {
            'equipment_type': equipment_type if equipment_type in ['摄像头', '录像机', '视频中心存储', '特殊摄像头',
                                                                   '安防平台', '浙江双视热成像', 'AI双光摄像头','AI单光摄像头'] else None,
            'manufacturer_type': manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视',
                                                                            '天地伟业', '三星', '浙江双视','艾斯卡普','阳光三极'] else None,
            'equipment_name': equipment_data.get('equipment_name'),
            'equipment_ip': equipment_data.get('equipment_ip'),
            'equipment_uname': equipment_data.get('equipment_uname'),
            'equipment_password': equipment_data.get('equipment_password'),
            'equipment_aisles': equipment_data.get('equipment_aisles'),
            'equipment_codetype': equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
            'Mine_id': equipment_data.get('Mine_id'),
            'flower_frames': equipment_data.get('flower_frames') if equipment_data.get('flower_frames') and equipment_data.get('flower_frames') != '0' else None,
            'uwb_ip' : equipment_data.get('uwb_ip', None), # 读卡器ip
            'alarm_device_ip' : equipment_data.get('alarm_device_ip', None)
        }

        # 当厂商类型为艾斯卡普时，保存uwb_ip；其他类型默认为None
        if manufacturer_type == '艾斯卡普':
            uwb_ip_value = equipment_data.get('uwb_ip') if equipment_data.get('uwb_ip') else None
        else:
            uwb_ip_value = None

        # 非特殊摄像头和浙江双视热成像的处理
        if equipment_type != '特殊摄像头' and equipment_type != '浙江双视热成像'and equipment_type != 'AI双光摄像头' and equipment_type != 'AI单光摄像头':
            # 更新设备信息
            updated_equipment = EquipmentData.update_equipment(equipment_id, update_data)
            if not updated_equipment:
                return {'code': 500, 'msg': '设备更新失败'}

            # 更新VCR数据
            if hasattr(updated_equipment, 'VCR_data_id') and updated_equipment.VCR_data_id:
                vcr_data = {
                    'vcr_type': manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视','艾斯卡普'] else None,
                    'vcr_name': equipment_data.get('equipment_name'),
                    'vcr_ip': equipment_data.get('equipment_ip'),
                    'vcr_username': equipment_data.get('equipment_uname'),
                    'vcr_password': equipment_data.get('equipment_password'),
                    'Mine_id': equipment_data.get('Mine_id'),
                    'uwb_ip': uwb_ip_value
                }
                EquipmentData.update_vcr_data(updated_equipment.VCR_data_id, vcr_data)

                # 更新子设备信息
                children_data = {
                    'manufacturer_type': manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视','艾斯卡普'] else None,
                    'Mine_id': equipment_data.get('Mine_id'),
                }
                EquipmentData.update_children_equipment(updated_equipment.VCR_data_id, children_data)

        # 特殊摄像头和浙江双视热成像的处理
        else:
            # 确定是父类还是子类
            if equipment.parent_id:
                # 不是父类，更新父类和所有子设备
                parent_id = equipment.parent_id
                EquipmentData.update_children_equipment_by_parent(parent_id, update_data)
            else:
                # 是父类，更新自身和所有子设备
                EquipmentData.update_children_equipment_by_parent(equipment.id, update_data)

        return {'code': 200, 'msg': '设备修改完成!'}

    @staticmethod
    def get_equipment_type(equipment_types, equipment_type):
        """
        获取设备类型编号
        :param equipment_types: 设备类型列表
        :param equipment_type: 设备类型
        :return: 设备类型编号
        """
        for i, item in enumerate(equipment_types):
            if item['value'] == equipment_type:
                return i + 1
        return 1

    @staticmethod
    def equipment_delete(equipment_id):
        """
        设备删除接口
        :param equipment_id: 设备ID列表
        :return: 删除结果
        """
        try:
            if not equipment_id:
                return {'code': 400, 'msg': '缺少设备id参数'}

            # 收集所有需要删除的设备ID（包括父设备和子设备）
            all_equipment_ids = EquipmentService._collect_equipment_ids(equipment_id)

            if not all_equipment_ids:
                return {'code': 400, 'msg': '没有有效的设备ID'}
            equipment_ips = []
            for equip_id in all_equipment_ids:
                equipment = db.session.query(Equipment).filter(Equipment.id == equip_id).first()
                if equipment and equipment.equipment_ip:
                    equipment_ips.append(equipment.equipment_ip)

            # 先删除所有设备的流媒体数据
            deleted_count = delete_zlk_data_for_equipment(all_equipment_ids)
            print(f"已删除 {deleted_count} 个设备的流媒体数据")

            # 然后删除设备记录
            EquipmentData.delete_equipment_records(equipment_id)

            # 删除对应的Computing_equipment数据
            if equipment_ips:
                from model.equipment import Computing_equipment
                deleted_computing_count = 0
                for ip in equipment_ips:
                    computing_equipment = db.session.query(Computing_equipment).filter(
                        Computing_equipment.computing_ip == ip
                    ).first()
                    if computing_equipment:
                        db.session.delete(computing_equipment)
                        deleted_computing_count += 1

                if deleted_computing_count > 0:
                    db.session.commit()
                    print(f"已删除 {deleted_computing_count} 个对应的算力设备记录")

            return {'code': 200, 'msg': '删除成功'}
        except Exception as e:
            print(f"设备删除操作出错: {str(e)}")
            return {'code': 500, 'msg': '设备删除操作失败'}

    @staticmethod
    def _collect_equipment_ids(equipment_id):
        """
        收集所有需要删除的设备ID（包括父设备和子设备）
        :param equipment_id: 设备ID列表
        :return: 所有需要删除的设备ID列表
        """
        all_equipment_ids = []

        for i in equipment_id:
            equipment_item_id = i.get('id') if isinstance(i, dict) else i

            if isinstance(i, dict) and i.get('children'):
                # 父设备有子设备的情况
                all_equipment_ids.append(equipment_item_id)
                # 收集所有子设备ID
                for child in i.get('children', []):
                    child_id = child.get('id') if isinstance(child, dict) else child
                    if child_id:
                        all_equipment_ids.append(child_id)
            else:
                # 单个设备或子设备
                if equipment_item_id:
                    all_equipment_ids.append(equipment_item_id)

        return all_equipment_ids

    @staticmethod
    def process_vcr_type(vcr_type):
        """
        处理录像机厂商类型
        :param vcr_type: 厂商类型ID
        :return: 厂商类型名称
        """
        return (configs.manufacturer_type[int(vcr_type) - 1])['value'] if vcr_type else 1

    @staticmethod
    def process_vcr_way(vcr_way):
        """
        处理录像机接入方式
        :param vcr_way: 接入方式ID
        :return: 接入方式名称
        """
        return (configs.vcr_way[int(vcr_way) - 1])['value'] if vcr_way else 1

    @staticmethod
    def vcr_data_sync(vcr_type, vcr_way, vcr_name, username, password, ip, port, mine_id):
        """
        录像机设备同步接口
        :param vcr_type: 厂商类型
        :param vcr_way: 接入方式
        :param vcr_name: 录像机名称
        :param username: 录像机用户
        :param password: 录像机密码
        :param ip: 录像机ip
        :param port: 录像机端口
        :param mine_id: 矿id
        :return: 同步结果
        """
        try:
            # 处理厂商类型和接入方式
            vcr_type = EquipmentService.process_vcr_type(vcr_type)
            vcr_way = EquipmentService.process_vcr_way(vcr_way)

            # 验证参数
            params = [vcr_type, vcr_way, vcr_name, username, password, port, mine_id, ip]
            if not all(params):
                return {'code': 400, 'msg': '录像机同步有未填写项！'}

            # 检查录像机是否已存在
            existing_vcr = EquipmentData.check_vcr_exists(ip)
            if existing_vcr:
                return {'code': 400, 'msg': '录像机设备信息已经存在,同步失败！'}

            # 获取子设备数据
            children_list = []
            if vcr_type == '海康' and vcr_way == '私有SDK':
                children_list = configs.VCR_data_info(username, password, ip, port)
            elif vcr_type == '宇视' and vcr_way == '私有SDK':
                children_list = configs.YSVCR_data_info(username, password, ip, port)
            elif vcr_type == '大华' and vcr_way == 'Onvif':
                children_list = configs.Dahua_data_info(username, password, ip, port)
            else:
                return {'code': 400, 'msg': '录像机设备信息同步失败！'}

            # 检查子设备数据
            if children_list == []:
                return {'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'}

            # 创建VCR数据
            vcr_data_id = EquipmentData.create_vcr_data(
                vcr_type=vcr_type,
                vcr_way=vcr_way,
                vcr_name=vcr_name,
                ip=ip,
                username=username,
                password=password,
                port=port,
                mine_id=mine_id
            )

            if not vcr_data_id:
                return {'code': 500, 'msg': '创建VCR数据失败'}

            # 创建父设备
            parent_equipment = EquipmentData.create_parent_equipment(
                equipment_type='录像机',
                manufacturer_type=vcr_type,
                equipment_name=vcr_name,
                equipment_ip=ip,
                equipment_uname=username,
                equipment_password=password,
                mine_id=mine_id,
                vcr_data_id=vcr_data_id
            )

            if not parent_equipment:
                return {'code': 500, 'msg': '创建父设备失败'}

            # 创建子设备
            for i in children_list:
                if vcr_type == '海康' and vcr_way == '私有SDK':
                    child_equipment_data = {
                        'equipment_type': parent_equipment.equipment_type if parent_equipment.equipment_type else None,
                        'manufacturer_type': parent_equipment.manufacturer_type if parent_equipment.manufacturer_type else None,
                        'equipment_name': i.get('name') if i.get('name') else None,
                        'equipment_ip': i.get('ip_address') if i.get('ip_address') is not None else None,
                        'equipment_uname': i.get('username') if i.get('username') else None,
                        'equipment_password': parent_equipment.equipment_password if parent_equipment.equipment_password else None,
                        'equipment_aisles': i.get('id') if i.get('id') else None,
                        'Mine_id': int(parent_equipment.Mine_id) if parent_equipment.Mine_id else None,
                        'parent_id': int(parent_equipment.id) if parent_equipment.id else None,
                        'code': str(i.get('id')) + '01',
                        'VCR_data_id': vcr_data_id,
                        'online': 1 if i.get('online') == 'true' else 2,
                        'equipment_width_height': (
                            (i.get('videoResolutionWidth', '') + 'x' + i.get('videoResolutionHeight', ''))
                            if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                        ),
                        'equipment_codetype': (
                            'H265' if i.get('videoCodecType') == 'H.265'
                            else 'H264' if i.get('videoCodecType') == 'H.264'
                            else None
                        ),
                        'equipment_constantBitRate': i.get('constantBitRate', ''),
                        'equipment_maxFrameRate': i.get('maxFrameRate', '')
                    }
                elif vcr_type == '宇视' and vcr_way == '私有SDK':
                    child_equipment_data = {
                        'equipment_type': parent_equipment.equipment_type if parent_equipment.equipment_type else None,
                        'manufacturer_type': configs.YSNVR_manufacturer_type.get(i.get('Manufacturer'), None) if i.get('Manufacturer') else None,
                        'equipment_name': i.get('name') if i.get('name') else None,
                        'equipment_ip': i.get('ip_address') if i.get('ip_address') is not None else None,
                        'equipment_uname': parent_equipment.equipment_uname if parent_equipment.equipment_uname else None,
                        'equipment_password': parent_equipment.equipment_password if parent_equipment.equipment_password else None,
                        'equipment_aisles': i.get('id') if i.get('id') else None,
                        'Mine_id': int(parent_equipment.Mine_id) if parent_equipment.Mine_id else None,
                        'parent_id': int(parent_equipment.id) if parent_equipment.id else None,
                        'code': str(i.get('id')) + '01',
                        'VCR_data_id': vcr_data_id,
                        'online': i.get('online'),
                        'equipment_width_height': (
                            (str(i.get('videoResolutionWidth', '')) + 'x' + str(i.get('videoResolutionHeight', '')))
                            if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                        ),
                        'equipment_codetype': (
                            'H265' if i.get('videoCodecType') == 'H.265'
                            else 'H264' if i.get('videoCodecType') == 'H.264'
                            else i.get('videoCodecType') if i.get('videoCodecType') in ['MJPEG', 'H.264', 'H.265']
                            else None
                        ),
                        'equipment_constantBitRate': i.get('constantBitRate', ''),
                        'equipment_maxFrameRate': i.get('maxFrameRate', '')
                    }
                elif vcr_type == '大华' and vcr_way == 'Onvif':
                    child_equipment_data = {
                        'equipment_type': parent_equipment.equipment_type if parent_equipment.equipment_type else None,
                        'manufacturer_type': parent_equipment.manufacturer_type if parent_equipment.manufacturer_type else None,
                        'equipment_name': i.get('name') if i.get('name') else None,
                        'equipment_ip': i.get('ip_address') if i.get('ip_address') is not None else None,
                        'equipment_uname': parent_equipment.equipment_uname if parent_equipment.equipment_uname else None,
                        'equipment_password': parent_equipment.equipment_password if parent_equipment.equipment_password else None,
                        'equipment_aisles': int(i.get('id')) + 1 if i.get('id') is not None else None,
                        'Mine_id': int(parent_equipment.Mine_id) if parent_equipment.Mine_id else None,
                        'parent_id': int(parent_equipment.id) if parent_equipment.id else None,
                        'code': str(i.get('id')) + '01',
                        'VCR_data_id': vcr_data_id,
                        'online': 1,
                        'equipment_width_height': (
                            str(i.get('videoResolutionWidth', '')) + 'x' + str(i.get('videoResolutionHeight', ''))
                            if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                        ),
                        'equipment_codetype': (
                            'H265' if i.get('videoCodecType') == 'H.265'
                            else 'H264' if i.get('videoCodecType') == 'H.264'
                            else None
                        ),
                        'equipment_constantBitRate': i.get('constantBitRate', ''),
                        'equipment_maxFrameRate': i.get('maxFrameRate', ''),
                        'Onvif_rtsp_url': i.get('main_stream_uri', '')
                    }
                else:
                    continue

                child_equipment = EquipmentData.create_equipment_from_dict(child_equipment_data)
                if child_equipment:
                    create_zlk_data_for_equipment(child_equipment)

            # 更新VCR同步状态
            EquipmentData.update_vcr_status(vcr_data_id, 1)

            return {'code': 200, 'msg': '录像机设备信息同步成功！'}
        except Exception as e:
            print(f"录像机同步操作出错: {str(e)}")
            return {'code': 500, 'msg': '同步失败'}

    @staticmethod
    def vcr_data_update(type_st, vcr_id, vcr_type=None, vcr_way=None, vcr_name=None, username=None, password=None, ip=None, port=None, mine_id=None):
        """
        录像机设备修改及详情接口
        :param type_st: 操作类型，1为详情，2为修改
        :param vcr_id: 录像机ID
        :param vcr_type: 厂商类型
        :param vcr_way: 接入方式
        :param vcr_name: 录像机名称
        :param username: 录像机用户
        :param password: 录像机密码
        :param ip: 录像机ip
        :param port: 录像机端口
        :param mine_id: 矿id
        :return: 操作结果
        """
        try:
            if int(type_st) == 1:
                # 获取录像机详情
                vcr_res = EquipmentData.get_vcr_data_by_id(vcr_id)
                if vcr_res:
                    dict_res = convert_to_dict(vcr_res, ['id', 'vcr_type', 'vcr_way', 'vcr_name', 'vcr_ip', 'vcr_username',
                                                         'vcr_password', 'vcr_port', 'Mine_id'])
                    return {'code': 200, 'msg': '查找成功！', 'data': dict_res}
                else:
                    return {'code': 400, 'msg': '未查找到数据！！', 'data': {}}
            elif int(type_st) == 2:
                # 处理厂商类型和接入方式
                vcr_type = EquipmentService.process_vcr_type(vcr_type) if vcr_type else 1
                vcr_way = EquipmentService.process_vcr_way(vcr_way) if vcr_way else 1
                if vcr_type == '海康' and vcr_way == '私有SDK':
                    print('海康接入')
                    # ----------同步的时候录像机父类设备写入----------
                    # 添加录像机父设备
                    # 调用方法获取录像机同步数据  数据格式为 [{},{}]
                    vcr_data_info = VCR_data_info(username, password, ip, port)
                    print(username, password, ip, port, type(username), type(password), type(ip), type(port))
                    print(vcr_data_info, '错误错误')
                    # 当返回值为列表的时候说明参数错误，请求超时
                    if vcr_data_info == []:
                        return {'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'}
                elif vcr_type == '宇视' and vcr_way == '私有SDK':
                    print('宇视接入')
                    # ----------同步的时候录像机父类设备写入----------
                    # 添加录像机父设备
                    ysvcr_data_info = YSVCR_data_info(username, password, ip, port)
                    print(username, password, ip, port, type(username), type(password), type(ip), type(port))
                    print(ysvcr_data_info, '错误错误')
                    # 当返回值为列表的时候说明参数错误，请求超时
                    if ysvcr_data_info == []:
                        return {'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'}
                elif vcr_type == '大华' and vcr_way == 'Onvif':
                    print('大华接入')
                    # ----------同步的时候录像机父类设备写入----------
                    # 添加录像机父设备
                    dahua_data_info = Dahua_data_info(username, password, ip, port)
                    print(username, password, ip, port, type(username), type(password), type(ip), type(port))
                    print(dahua_data_info, '错误错误')
                    # 当返回值为列表的时候说明参数错误，请求超时
                    if dahua_data_info == []:
                        return {'code': 400, 'msg': '录像机设备信息不存在,请输入正确参数！'}
                else:
                    return {'code': 400, 'msg': '录像机设备修改数据失败！'}
                # 检查录像机是否存在
                vcr_res = EquipmentData.get_vcr_data_by_id(vcr_id)
                if vcr_res:
                    # 准备VCR更新数据
                    vcr_update_data = {
                        'vcr_type': vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
                        'vcr_way': vcr_way if vcr_way in ['私有SDK', 'Onvif', 'GB28181'] else None,
                        'vcr_name': vcr_name,
                        'vcr_ip': ip,
                        'vcr_username': username,
                        'vcr_password': password,
                        'vcr_port': port,
                        'Mine_id': mine_id,
                    }

                    # 准备父设备更新数据
                    parent_equipment_data = {
                        'manufacturer_type': vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
                        'equipment_name': vcr_name,
                        'Mine_id': mine_id,
                    }

                    # 准备子设备更新数据
                    child_equipment_data = {
                        'manufacturer_type': vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
                        'Mine_id': mine_id,
                    }

                    # 执行更新
                    EquipmentData.update_vcr_data_by_id(vcr_id, vcr_update_data)
                    EquipmentData.update_equipment_by_vcr_id(vcr_id, parent_equipment_data, is_parent=True)
                    EquipmentData.update_equipment_by_vcr_id(vcr_id, child_equipment_data, is_parent=False)

                    return {'code': 200, 'msg': '更新完成，请手动同步！'}
                else:
                    return {'code': 400, 'msg': '更新数据不存在'}
            else:
                return {'code': 400, 'msg': '类型不存在'}
        except Exception as e:
            print(f"录像机更新操作出错: {str(e)}")
            return {'code': 500, 'msg': '操作失败'}

    @staticmethod
    def vcr_data_show(type_st, vcr_id=None, page=1, per_page=1000, vcr_type=None):
        """
        录像机设备展示接口
        :param type_st: 操作类型，1为全部，2为录像机及子设备信息
        :param vcr_id: 录像机ID
        :param page: 页码
        :param per_page: 每页条数
        :param vcr_type: VCR类型，1为录像机，2为CVR
        :return: 操作结果
        """
        try:
            if int(type_st) == 1:
                # 获取VCR数据列表
                vcrs_paginated = EquipmentData.get_vcr_data_list(vcr_type, page, per_page)
                if vcrs_paginated:
                    res = convert_folder_to_dict_list(vcrs_paginated.items,
                                                      ['id', 'vcr_type', 'vcr_way', 'vcr_name',
                                                       'vcr_ip', 'vcr_username', 'vcr_password',
                                                       'vcr_port', 'Mine_id', 'online'])
                    return {
                        'code': 200,
                        'msg': "查询成功",
                        'data': res,
                        'total': vcrs_paginated.total,
                        'page': vcrs_paginated.page,
                        'pages': vcrs_paginated.pages
                    }
                else:
                    return {'code': 400, 'msg': '获取数据失败'}
            elif int(type_st) == 2:
                # 获取VCR详情
                vcr_res = EquipmentData.get_vcr_data_with_children(vcr_id, vcr_type)
                if vcr_res:
                    res = convert_to_dict(vcr_res, ['id', 'vcr_type', 'vcr_way', 'vcr_name', 'vcr_ip',
                                                   'vcr_username', 'vcr_password', 'vcr_port', 'Mine_id'])

                    # 获取子设备列表
                    res_children = EquipmentData.get_children_equipment_by_vcr_id(vcr_id, page, per_page)
                    if res_children:
                        res_children_list = convert_folder_to_dict_list(res_children.items,
                                                                        ['id', 'equipment_type', 'manufacturer_type',
                                                                         'equipment_name',
                                                                         'equipment_ip', 'equipment_uname', 'equipment_password',
                                                                         'create_time', 'online'])
                        res['children'] = res_children_list
                        res['total'] = res_children.total
                        res['page'] = res_children.page
                        res['pages'] = res_children.pages
                    return {'code': 200, 'msg': "查询成功", 'data': res}
                else:
                    return {'code': 400, 'msg': '未查找到数据'}
            else:
                return {'code': 400, 'msg': '类型不存在'}
        except Exception as e:
            print(f"录像机展示操作出错: {str(e)}")
            return {'code': 500, 'msg': '操作失败'}

    @staticmethod
    def vcr_data_delete(vcr_id):
        """
        录像机设备删除接口
        :param vcr_id: 录像机ID
        :return: 操作结果
        """
        try:
            if not vcr_id:
                return {'code': 400, 'msg': '缺少录像机id参数'}

            # 获取设备ID列表
            em_ids = EquipmentData.get_equipment_ids_by_vcr_id(vcr_id)

            # 删除流媒体数据
            if em_ids:
                deleted_count = delete_zlk_data_for_equipment(em_ids)
                print(f"录像机 (ID: {vcr_id}) 下已删除 {deleted_count} 个设备的流媒体数据")

            # 删除算法配置和结果
            if em_ids:
                algorithm_config_res = EquipmentData.get_algorithm_config_ids_by_equipment_ids(em_ids)
                if algorithm_config_res:
                    EquipmentData.delete_algorithm_configs(algorithm_config_res)
                    # EquipmentData.delete_algorithm_results(algorithm_config_res)

            # 删除设备数据
            if em_ids:
                EquipmentData.delete_equipment_by_ids(em_ids)

            # 删除录像机数据
            EquipmentData.delete_vcr_data_by_id(vcr_id)

            return {'code': 200, 'msg': '删除成功'}
        except Exception as e:
            print(f"录像机删除操作出错: {str(e)}")
            return {'code': 500, 'msg': '操作失败'}

    @staticmethod
    def manual_sync(prepare_streams=True):
        """
        手动同步录像机设备信息
        :return: 同步结果
        """
        result = {
            'deleted': 0,
            'created': 0,
            'failed': [],
            '_prepare_streams': prepare_streams
        }

        try:
            vcr_list = EquipmentData.get_all_vcr_data()
            if not vcr_list:
                result.pop('_prepare_streams')
                return {'code': 200, 'msg': '无录像机设备需要同步', 'data': result}

            for vcr in vcr_list:
                if hasattr(vcr, 'type') and str(vcr.type) != '1':
                    continue
                try:
                    vcr_dict = convert_to_dict(vcr, ['id', 'vcr_ip', 'vcr_username', 'vcr_password', 'vcr_port', 'vcr_way', 'Mine_id'])
                    EquipmentService._process_vcr_sync(vcr_dict, result)
                except Exception as e:
                    result['failed'].append(f"处理录像机 {vcr.vcr_ip} 失败: {str(e)}")

            complement_count = EquipmentService._complement_zlk_dat_id(include_recorders=prepare_streams)
            result['complement_count'] = complement_count
            result.pop('_prepare_streams')
            result.pop('_channel_health_polled', None)

            return {'code': 200, 'msg': '同步完成', 'data': result}
        except Exception as e:
            print(f"手动同步操作出错: {str(e)}")
            return {'code': 500, 'msg': '同步失败'}

    @staticmethod
    def _process_vcr_sync(vcr_dict, result):
        """
        处理单个录像机同步
        :param vcr_dict: 录像机数据字典
        :param result: 结果字典
        """
        parent_equipment = EquipmentData.get_parent_equipment_by_vcr_id(vcr_dict['id'])
        if not parent_equipment:
            result['failed'].append('录像机 {} 未找到父设备'.format(vcr_dict['vcr_ip']))
            return
        manufacturer = parent_equipment.manufacturer_type
        external_data_list = EquipmentService._get_external_data_list(manufacturer, vcr_dict)
        if not external_data_list:
            EquipmentService._handle_empty_external_data(manufacturer, vcr_dict, result)
            return
        if manufacturer in ('海康', '宇视') and _nvr_inventory_keys(external_data_list) is None:
            result['failed'].append('录像机通道清单不完整，本轮保留现有设备')
            return
        result['_channel_health_polled'] = manufacturer == '海康' and vcr_dict.get('vcr_way') == '私有SDK'
        EquipmentService._sync_children_equipment(manufacturer, external_data_list, vcr_dict, parent_equipment, result)

    @staticmethod
    def _get_external_data_list(manufacturer, vcr_dict):
        """
        根据厂商类型获取外部设备列表
        :param manufacturer: 厂商类型
        :param vcr_dict: 录像机数据字典
        :return: 外部设备列表
        """
        if manufacturer == '海康':
            return VCR_data_info(vcr_dict['vcr_username'], vcr_dict['vcr_password'], vcr_dict['vcr_ip'], vcr_dict['vcr_port'])
        elif manufacturer == '宇视':
            return YSVCR_data_info(vcr_dict['vcr_username'], vcr_dict['vcr_password'], vcr_dict['vcr_ip'], vcr_dict['vcr_port'])
        elif manufacturer == '大华':
            return Dahua_data_info(vcr_dict['vcr_username'], vcr_dict['vcr_password'], vcr_dict['vcr_ip'], vcr_dict['vcr_port'])
        return []

    @staticmethod
    def _handle_empty_external_data(manufacturer, vcr_dict, result):
        result['failed'].append('录像机 {} 未返回完整通道清单，本轮保留现有设备'.format(vcr_dict['vcr_ip']))

    @staticmethod
    def _sync_children_equipment(manufacturer, external_data_list, vcr_dict, parent_equipment, result):
        if manufacturer in ('海康', '宇视') and _nvr_inventory_keys(external_data_list) is None:
            result['failed'].append('录像机通道清单不完整，本轮保留现有设备')
            return
        children = db.session.query(Equipment).filter_by(VCR_data_id=vcr_dict['id'], parent_id=parent_equipment.id)
        child_equipments = children.all()
        EquipmentService._delete_not_exists_equipment(manufacturer, external_data_list, child_equipments, result)
        # Removed ORM objects may be expired after commit. Requery surviving rows.
        child_equipments = children.all()
        EquipmentService._update_or_create_equipment(manufacturer, external_data_list, child_equipments, vcr_dict, parent_equipment, result)

    @staticmethod
    def _delete_not_exists_equipment(manufacturer, external_data_list, child_equipments, result):
        if manufacturer in ('海康', '宇视'):
            keys = _nvr_inventory_keys(external_data_list)
            if keys is None:
                result['failed'].append('录像机通道清单为空、不完整或包含重复通道，本轮不删除设备')
                return
            for equipment in child_equipments:
                key = _nvr_channel_key(equipment.equipment_aisles)
                if key is not None and key not in keys:
                    EquipmentService._delete_equipment_with_zlk(equipment, result)
        elif manufacturer == '大华' and external_data_list:
            names = {item.get('name') for item in external_data_list if item.get('name')}
            if len(names) != len(external_data_list):
                return
            for equipment in child_equipments:
                if equipment.equipment_name not in names:
                    EquipmentService._delete_equipment_with_zlk(equipment, result)

    @staticmethod
    def _delete_equipment_with_zlk(equipment, result):
        # Capture the forwarding row before ORM relationships can clear either side.
        equipment_id, zlk_id = equipment.id, equipment.zlk_dat_id
        try:
            forwarding = db.session.query(Zlk_data).filter_by(id=zlk_id).first() if zlk_id else None
            stream_key = forwarding.zlk_key if forwarding is not None else None
            equipment.zlk_dat_id = None
            db.session.flush()
            db.session.query(Equipment).filter(Equipment.id == equipment_id).delete(synchronize_session=False)
            db.session.flush()
            if zlk_id:
                db.session.query(Zlk_data).filter(Zlk_data.id == zlk_id).delete(synchronize_session=False)
            db.session.commit()
            result['deleted'] += 1
            if stream_key:
                from config.zlk_conf import del_stream_proxy
                response = del_stream_proxy(stream_key)
                if response.get('code') != 200:
                    result['failed'].append('设备 {} 已删除，流媒体服务需清理残留转发'.format(equipment_id))
        except Exception as exc:
            db.session.rollback()
            result['failed'].append('删除设备 {} 失败: {}'.format(equipment_id, type(exc).__name__))

    @staticmethod
    def _update_or_create_equipment(manufacturer, external_data_list, child_equipments, vcr_dict, parent_equipment, result):
        if manufacturer in ('海康', '宇视'):
            if _nvr_inventory_keys(external_data_list) is None:
                result['failed'].append('录像机通道清单不完整，本轮不更新设备')
                return
            equipment_dict = {_nvr_channel_key(item.equipment_aisles): item for item in child_equipments}
        else:
            equipment_dict = {item.equipment_name: item for item in child_equipments}
        for item in external_data_list:
            try:
                EquipmentService._process_single_equipment(manufacturer, item, equipment_dict, vcr_dict, parent_equipment, result)
            except Exception as exc:
                db.session.rollback()
                result['failed'].append('同步录像机通道 {} 失败: {}'.format(item.get('id'), type(exc).__name__))

    @staticmethod
    def _process_single_equipment(manufacturer, item, equipment_dict, vcr_dict, parent_equipment, result):
        ip_address = str(item.get('ip_address') or '').strip() if manufacturer != '大华' else ''
        key = _nvr_channel_key(item.get('id')) if manufacturer in ('海康', '宇视') else item.get('name', '')
        previous = equipment_dict.get(key)
        name = _nvr_channel_name(item.get('name'), item.get('id'), getattr(previous, 'equipment_name', None))
        online = _nvr_online_value(item.get('online'), getattr(previous, 'online', 1)) if manufacturer != '大华' else 1
        if previous is not None:
            EquipmentService._update_existing_equipment(manufacturer, item, equipment_dict, ip_address, name, online, result)
        else:
            parent_id_equipment = parent_equipment
            EquipmentService._create_new_equipment(manufacturer, item, vcr_dict, parent_equipment, ip_address, name, online, parent_id_equipment, result)

    @staticmethod
    def _update_existing_equipment(manufacturer, item, equipment_dict, ip_address, name, online, result):
        """
        更新已存在的设备
        :param manufacturer: 厂商类型
        :param item: 设备数据
        :param equipment_dict: 设备字典
        :param ip_address: 设备IP
        :param name: 设备名称
        :param online: 在线状态
        :param result: 结果字典
        """

        db_device = equipment_dict[_nvr_channel_key(item.get('id'))] if manufacturer != '大华' else equipment_dict[name]

        update_data = {
            'online': online,
            'equipment_name': name,
            'equipment_aisles': item.get('id'),
            'code': _nvr_channel_code(item),
            'equipment_width_height': f"{item.get('videoResolutionWidth', '')}x{item.get('videoResolutionHeight', '')}" if item.get('videoResolutionWidth') and item.get('videoResolutionHeight') else '',
            'equipment_codetype': 'H265' if item.get('videoCodecType') == 'H.265' else 'H264' if item.get('videoCodecType') == 'H.264' else None,
            'equipment_constantBitRate': item.get('constantBitRate', ''),
            'equipment_maxFrameRate': item.get('maxFrameRate', ''),
            'GB28181_code' : item.get('GB28181_code', None)
        }

        if manufacturer != '大华':
            if ip_address:
                update_data['equipment_ip'] = ip_address
            if not update_data['code']:
                update_data['code'] = db_device.code
            for field in ('equipment_width_height', 'equipment_codetype', 'equipment_constantBitRate', 'equipment_maxFrameRate', 'GB28181_code'):
                if update_data.get(field) in (None, ''):
                    update_data.pop(field, None)

        if manufacturer == '大华':
            update_data['Onvif_rtsp_url'] = item.get('main_stream_uri', '')

        if result.get('_channel_health_polled'):
            # Channel availability is updated from the dedicated vendor status request.
            update_data.pop('online', None)
        EquipmentData.update_equipment_by_id(db_device.id, update_data)

        if online and not db_device.zlk_dat_id and result.get('_prepare_streams', True):
            zlk_id = create_zlk_data_for_equipment(db_device)
            if zlk_id:
                EquipmentData.update_equipment_zlk_dat_id(db_device.id, zlk_id)
                EquipmentData.update_zlk_data_equipment(zlk_id, db_device)
                result['created'] += 1

    @staticmethod
    def _create_new_equipment(manufacturer, item, vcr_dict, parent_equipment, ip_address, name, online, parent_id_equipment, result):
        """
        创建新设备
        :param manufacturer: 厂商类型
        :param item: 设备数据
        :param vcr_dict: 录像机数据字典
        :param parent_equipment: 父设备对象
        :param ip_address: 设备IP
        :param name: 设备名称
        :param online: 在线状态
        :param parent_id_equipment: 父设备IP对应的设备
        :param result: 结果字典
        """
        exists = False
        if manufacturer in ['海康', '宇视']:
            exists = db.session.query(Equipment.id).filter(
                Equipment.parent_id == parent_equipment.id,
                Equipment.equipment_aisles == item.get('id')).first() is not None
        elif manufacturer == '大华' and parent_id_equipment:
            exists = EquipmentData.get_equipment_by_parent_id(parent_id_equipment.id) is not None

        if exists:
            return

        print(f"添加新设备: {item['name']}")

        equipment_data = {
            'VCR_data_id': vcr_dict['id'],
            'parent_id': parent_equipment.id,
            'equipment_aisles': item.get('id'),
            'equipment_name': name,
            'equipment_ip': ip_address,
            'online': online,
            'code': _nvr_channel_code(item),
            'equipment_type': '录像机',
            'manufacturer_type': YSNVR_manufacturer_type.get(item.get('Manufacturer'), None) if manufacturer == '宇视' else manufacturer,
            'equipment_uname': vcr_dict['vcr_username'],
            'equipment_password': vcr_dict['vcr_password'],
            'user_status': '1',
            'create_time': datetime.now(),
            'Mine_id': vcr_dict['Mine_id'],
            'equipment_width_height': f"{item.get('videoResolutionWidth', '')}x{item.get('videoResolutionHeight', '')}" if item.get('videoResolutionWidth') and item.get('videoResolutionHeight') else '',
            'equipment_codetype': 'H265' if item.get('videoCodecType') == 'H.265' else 'H264' if item.get('videoCodecType') == 'H.264' else None,
            'equipment_constantBitRate': item.get('constantBitRate', ''),
            'equipment_maxFrameRate': item.get('maxFrameRate', ''),
            'zlk_dat_id': None,
            'GB28181_code': item.get('GB28181_code', None)

        }

        if manufacturer == '大华':
            equipment_data['Onvif_rtsp_url'] = item.get('main_stream_uri', '')

        new_device = EquipmentData.create_equipment_from_dict(equipment_data)

        if new_device and online and result.get('_prepare_streams', True):
            zlk_id = create_zlk_data_for_equipment(new_device)
            if zlk_id:
                EquipmentData.update_equipment_zlk_dat_id(new_device.id, zlk_id)
                EquipmentData.update_zlk_data_equipment(zlk_id, new_device)
                result['created'] += 1

    @staticmethod
    def _complement_zlk_dat_id(include_recorders=True):
        """
        补全zlk_dat_id为空的设备关联
        :return: 补全成功数量
        """

        complement_count = 0
        try:
            empty_zlk_equipments = EquipmentData.get_empty_zlk_equipments()

            if not empty_zlk_equipments:
                print("无zlk_dat_id为空的设备，无需补全")
                return complement_count

            for eq in empty_zlk_equipments:
                try:
                    if eq.online == 1 and (include_recorders or eq.equipment_type != '录像机'):
                        zlk_id = create_zlk_data_for_equipment(eq)
                        if zlk_id:
                            EquipmentData.update_equipment_zlk_dat_id(eq.id, zlk_id)
                            EquipmentData.update_zlk_data_equipment(zlk_id, eq)
                            complement_count += 1
                            print(f"设备 {eq.id} zlk_dat_id补全成功")
                except Exception as e:
                    print(f"补全设备 {eq.id} zlk_dat_id失败: {str(e)}")

            print(f"zlk_dat_id补全逻辑执行完成，共成功补全 {complement_count} 个设备")
            return complement_count
        except Exception as e:
            print(f"zlk_dat_id补全逻辑整体异常: {str(e)}")
            return complement_count

    @staticmethod
    def cvr_data_sync(vcr_type, vcr_way, vcr_name, username, password, ip, port, Mine_id):
        """
        CVR设备同步接口
        :param vcr_type: 厂商类型
        :param vcr_way: 接入方式
        :param vcr_name: 录像机名称
        :param username: 录像机用户名
        :param password: 录像机密码
        :param ip: 录像机IP
        :param port: 录像机端口
        :param Mine_id: 矿ID
        :return: 同步结果
        """
        try:
            params = [vcr_type, vcr_way, vcr_name, username, password, port, Mine_id, ip]
            print(params)

            if not all(params):
                return {'code': 400, 'msg': 'CVR同步有未填写项！'}

            vcr_data = EquipmentData.get_equipment_by_ip(ip)
            if vcr_data:
                return {'code': 400, 'msg': 'CVR设备信息已经存在,同步失败！'}

            vcr_data_info = CVR_data_info(username, password, ip, port)
            print(username, password, ip, port, type(username), type(password), type(ip), type(port))
            print(vcr_data_info, '错误错误')

            if vcr_data_info == []:
                return {'code': 400, 'msg': 'CVR设备信息不存在,请输入正确参数！'}

            vcr_data = EquipmentData.create_vcr_data(vcr_type, vcr_way, vcr_name, ip, username, password, port, Mine_id)
            if not vcr_data:
                return {'code': 500, 'msg': '创建VCR数据失败'}

            if vcr_type == '海康' and vcr_way == '私有SDK':
                EquipmentService._process_hikvision_cvr_sync(vcr_data, vcr_name, ip, username, password, Mine_id, vcr_data_info)

            EquipmentData.update_vcr_status(vcr_data.id, 1)

            return {'code': 200, 'msg': 'CVR设备信息同步成功！'}
        except Exception as e:
            print(f"CVR同步操作出错: {str(e)}")
            return {'code': 500, 'msg': '操作失败'}

    @staticmethod
    def _process_hikvision_cvr_sync(vcr_data, vcr_name, ip, username, password, Mine_id, children_list):
        """
        处理海康CVR同步
        :param vcr_data: VCR数据对象
        :param vcr_name: 录像机名称
        :param ip: 录像机IP
        :param username: 用户名
        :param password: 密码
        :param Mine_id: 矿ID
        :param children_list: 子设备列表
        """
        print('海康接入')

        equipment_data = {
            'equipment_type': '视频中心存储',
            'manufacturer_type': '海康',
            'equipment_name': vcr_name,
            'equipment_ip': ip,
            'equipment_uname': username,
            'equipment_password': password,
            'Mine_id': int(Mine_id) if Mine_id else None,
            'online': 1,
            'VCR_data_id': vcr_data.id
        }

        parent_equipment = EquipmentData.create_equipment_from_dict(equipment_data)
        if not parent_equipment:
            return

        for i in children_list:
            print(i)

            child_equipment_data = {
                'equipment_type': parent_equipment.equipment_type if parent_equipment.equipment_type else None,
                'manufacturer_type': parent_equipment.manufacturer_type if parent_equipment.manufacturer_type else None,
                'equipment_name': i['name'] if i.get('name') else None,
                'equipment_ip': i['ip_address'] if i.get('ip_address') is not None else None,
                'equipment_uname': i.get('username') if i.get('username') else None,
                'equipment_password': parent_equipment.equipment_password if parent_equipment.equipment_password else None,
                'equipment_aisles': i.get('id') if i.get('id') else None,
                'Mine_id': int(parent_equipment.Mine_id) if parent_equipment.Mine_id else None,
                'parent_id': int(parent_equipment.id) if parent_equipment.id else None,
                'code': str(i.get('id')) + '01',
                'VCR_data_id': vcr_data.id,
                'online': 1 if i.get('online') == 'true' else 2,
                'equipment_width_height': (
                    (i.get('videoResolutionWidth', '') + 'x' + i.get('videoResolutionHeight', ''))
                    if i.get('videoResolutionWidth') and i.get('videoResolutionHeight') else ''
                ),
                'equipment_codetype': (
                    'H265' if i.get('videoCodecType') == 'H.265'
                    else 'H264' if i.get('videoCodecType') == 'H.264'
                    else None
                ),
                'equipment_constantBitRate': i.get('constantBitRate', ''),
                'equipment_maxFrameRate': i.get('maxFrameRate', '')
            }

            EquipmentData.create_equipment_from_dict(child_equipment_data)

