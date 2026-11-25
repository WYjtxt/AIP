import random
import string
import json
from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
import requests
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from apps.scheduler_task import flatten_equipment_data
import configparser


def load_config(config_path):
    """加载配置文件"""
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    return config


config_path = "config.ini"
config = load_config(config_path)

# ZLK配置
ZLK_HOST = config['ZLK']['ZLK_HOST']  # ZLK服务器IP地址
ZLK_PORT = config['ZLK']['ZLK_PORT']  # ZLK服务器端口号
ZLK_SECRET = config['ZLK']['ZLK_SECRET']  # ZLK服务器密钥
SE_RTMP = f"rtmp://{ZLK_HOST}:1935"  # RTMP协议地址
SE_VIDEO = f"http://{ZLK_HOST}:8085"  # HTTP视频服务地址
SE_RTSP = f"rtsp://{ZLK_HOST}:8554"  # RTSP协议地址

# 设置日志
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# 构建数据库连接字符串（同步版本）
DATABASE_URL = f"mysql+pymysql://{urllib.parse.quote(DB_USER)}:{urllib.parse.quote(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 创建同步 SQLAlchemy 引擎和会话
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_size=10,          # 连接池大小
    max_overflow=20,       # 超出pool_size后最多可创建的连接数
    pool_reset_on_return='rollback'  # 连接返回池时重置
)
SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


def generate_mixed_id(length=40):
    """
    生成随机ID
    """
    if length < 3:
        raise ValueError("长度至少为3，才能保证包含大小写字母和数字")
    upper = random.choice(string.ascii_uppercase)
    lower = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    others = random.choices(string.ascii_letters + string.digits, k=length - 3)
    combined = [upper, lower, digit] + others
    random.shuffle(combined)
    return ''.join(combined)


def del_stream_proxy(key):
    """
    同步删除流代理（只删除ZLMediaKit中的流，不操作数据库）
    """
    if not key:
        return {'code': 400, 'msg': '缺少必要参数 key'}

    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/delStreamProxy"
    params = {
        'secret': ZLK_SECRET,
        'key': key,
    }

    try:
        response = requests.get(api, params=params, timeout=2)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式非 JSON'}

        # 检查删除结果
        if zlk_info.get('code') == 0 and zlk_info.get('data', {}).get('flag'):
            # 删除成功
            return {'code': 200, 'msg': '关闭流成功！'}
        else:
            msg = zlk_info.get('msg', '关闭流失败')
            return {'code': 400, 'msg': msg}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器异常：{str(e)}'}


def add_stream_proxy(url, url_name=None, enable_rtsp=None,
                     enable_hls=None, enable_hls_fmp4=None, enable_rtmp=None,
                     enable_ts=None, enable_fmp4=None):
    """
    同步添加流代理
    """
    if not url:
        return {'code': 400, 'msg': '缺少参数：url'}

    # 确保参数是布尔类型
    def ensure_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'on', 'yes')
        return bool(value)

    enable_rtsp = ensure_bool(enable_rtsp)
    enable_hls = ensure_bool(enable_hls)
    enable_hls_fmp4 = ensure_bool(enable_hls_fmp4)
    enable_rtmp = ensure_bool(enable_rtmp)
    enable_ts = ensure_bool(enable_ts)
    enable_fmp4 = ensure_bool(enable_fmp4)

    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/addStreamProxy"

    try:
        # 先查询是否已存在该流地址
        with SessionLocal() as session:
            result = session.execute(
                select(Zlk_data).where(Zlk_data.cameras_rtsp == str(url))
            )
            existing = result.scalars().first()  # 使用first()而不是scalar_one_or_none()

            # 确定要使用的stream ID
            if existing:
                # ----- 已存在记录：更新协议（增量，不关闭已有协议）-----
                stream = existing.zlk_live

                # 获取已启用的协议状态（根据数据库字段是否非空）
                old_hls = bool(existing.zlk_hls)
                old_hls_fmp4 = bool(existing.zlk_hls_fmp4)
                old_rtmp = bool(existing.zlk_rtmp)
                old_rtsp = bool(existing.zlk_rtsp)
                old_ts = bool(existing.zlk_ts)
                old_fmp4 = bool(existing.zlk_mp4)

                # 合并：原有协议始终保留，新请求的协议开启
                final_hls = old_hls or enable_hls
                final_hls_fmp4 = old_hls_fmp4 or enable_hls_fmp4
                final_rtmp = old_rtmp or enable_rtmp
                final_rtsp = old_rtsp or enable_rtsp
                final_ts = old_ts or enable_ts
                final_fmp4 = old_fmp4 or enable_fmp4

                # 如果没有需要新增的协议，直接返回成功（无需调用ZLMediaKit）
                need_update = (enable_hls and not old_hls) or \
                              (enable_hls_fmp4 and not old_hls_fmp4) or \
                              (enable_rtmp and not old_rtmp) or \
                              (enable_rtsp and not old_rtsp) or \
                              (enable_ts and not old_ts) or \
                              (enable_fmp4 and not old_fmp4)

                if not need_update:
                    return {
                        'code': 200,
                        'msg': '所有请求的协议已存在，无需更新',
                        'data': {'zlk_id': existing.id, 'key': existing.zlk_key}
                    }

                # 调用 ZLMediaKit 更新流代理（使用合并后的协议参数）
                params = {
                    'secret': str(ZLK_SECRET),
                    'vhost': str(ZLK_HOST),
                    'app': 'openUrl',
                    'stream': str(stream),
                    'url': str(url),
                    'enable_rtsp': '1' if final_rtsp else '0',
                    'enable_hls': '1' if final_hls else '0',
                    'enable_hls_fmp4': '1' if final_hls_fmp4 else '0',
                    'enable_rtmp': '1' if final_rtmp else '0',
                    'enable_ts': '1' if final_ts else '0',
                    'enable_fmp4': '1' if final_fmp4 else '0',
                }

                # 向ZLMediaKit发送添加流请求（只针对新协议）
                response = requests.get(api, params=params, timeout=3)
                try:
                    zlk_info = response.json()
                except Exception:
                    return {'code': 400, 'msg': 'ZLMediaKit 响应非 JSON 格式'}

                if zlk_info.get('code') == 0:
                    # 更新数据库：只设置新增的协议URL，原有协议URL保留
                    if url_name:
                        existing.cameras_name = str(url_name)

                    if enable_hls and not old_hls:
                        existing.zlk_hls = f"http://{ZLK_HOST}:8085/openUrl/{stream}/hls.m3u8"
                    if enable_hls_fmp4 and not old_hls_fmp4:
                        existing.zlk_hls_fmp4 = f"http://{ZLK_HOST}:8085/openUrl/{stream}/hls.fmp4.m3u8"
                    if enable_rtmp and not old_rtmp:
                        existing.zlk_rtmp = f"rtmp://{ZLK_HOST}:1935/openUrl/{stream}"
                    if enable_rtsp and not old_rtsp:
                        existing.zlk_rtsp = f"rtsp://{ZLK_HOST}:8554/openUrl/{stream}"
                    if enable_ts and not old_ts:
                        existing.zlk_ts = f"http://{ZLK_HOST}:8085/openUrl/{stream}.live.ts"
                    if enable_fmp4 and not old_fmp4:
                        existing.zlk_mp4 = f"http://{ZLK_HOST}:8085/openUrl/{stream}.live.mp4"

                    # 注意：如果 ZLMediaKit 返回了新的 key（更新后可能变化），需同步更新
                    new_key = zlk_info.get('data', {}).get('key')
                    if new_key and new_key != existing.zlk_key:
                        existing.zlk_key = str(new_key)

                    session.commit()
                    session.refresh(existing)

                    return {
                        'code': 200,
                        'msg': '协议更新成功',
                        'data': {'zlk_id': existing.id, 'key': existing.zlk_key}
                    }
                else:
                    # 如果 ZLMediaKit 返回错误，检查是否是流已存在导致的冲突
                    error_msg = zlk_info.get('msg', '更新流失败')
                    # 某些版本可能返回 "stream already exist" 或类似信息
                    if "already exist" in error_msg.lower() or "exist" in error_msg.lower():
                        # 可选：尝试先关闭流再添加（需要实现 close_stream 逻辑）
                        # 为简化，此处直接返回错误，提示用户手动处理
                        return {
                            'code': 400,
                            'msg': f'流已存在且无法更新，请先删除原流再试。ZLMediaKit错误：{error_msg}',
                            'data': zlk_info.get('data', {})
                        }
                    else:
                        return {
                            'code': 400,
                            'msg': error_msg,
                            'data': zlk_info.get('data', {})
                        }

            else:
                # 如果数据库中不存在该流，则创建新的流
                stream = generate_mixed_id()

                params = {
                    'secret': str(ZLK_SECRET),
                    'vhost': str(ZLK_HOST),
                    'app': 'openUrl',
                    'stream': str(stream),
                    'url': str(url),
                    'enable_rtsp': '1' if enable_rtsp else '0',
                    'enable_hls': '1' if enable_hls else '0',
                    'enable_hls_fmp4': '1' if enable_hls_fmp4 else '0',
                    'enable_rtmp': '1' if enable_rtmp else '0',
                    'enable_ts': '1' if enable_ts else '0',
                    'enable_fmp4': '1' if enable_fmp4 else '0',
                }

                response = requests.get(api, params=params, timeout=3)
                try:
                    zlk_info = response.json()
                except Exception:
                    return {'code': 400, 'msg': 'ZLMediaKit 响应非 JSON 格式'}

                if zlk_info.get('code') == 0 and zlk_info.get('data', {}).get('key'):
                    # 保存到数据库 - 只保存启用的协议
                    stream_data = Zlk_data(
                        cameras_name=str(url_name) if url_name else None,
                        cameras_rtsp=str(url),
                        zlk_app='openUrl',
                        zlk_live=str(stream),
                        zlk_key=str(zlk_info['data']['key'])
                    )

                    # 只有启用的协议才设置对应的URL
                    if enable_hls:
                        stream_data.zlk_hls = f"http://{ZLK_HOST}:8085/openUrl/{stream}/hls.m3u8"
                    if enable_hls_fmp4:
                        stream_data.zlk_hls_fmp4 = f"http://{ZLK_HOST}:8085/openUrl/{stream}/hls.fmp4.m3u8"
                    if enable_rtmp:
                        stream_data.zlk_rtmp = f"rtmp://{ZLK_HOST}:1935/openUrl/{stream}"
                    if enable_rtsp:
                        stream_data.zlk_rtsp = f"rtsp://{ZLK_HOST}:8554/openUrl/{stream}"
                    if enable_ts:
                        stream_data.zlk_ts = f"http://{ZLK_HOST}:8085/openUrl/{stream}.live.ts"
                    if enable_fmp4:
                        stream_data.zlk_mp4 = f"http://{ZLK_HOST}:8085/openUrl/{stream}.live.mp4"

                    session.add(stream_data)
                    session.commit()
                    session.refresh(stream_data)

                    return {
                        'code': 200,
                        'msg': '拉流代理添加成功',
                        'data': {
                            'zlk_id': stream_data.id,
                            'key': stream_data.zlk_key
                        }
                    }
                else:
                    return {
                        'code': 400,
                        'msg': str(zlk_info.get('msg', '添加流失败！')),
                        'data': zlk_info.get('data', {})
                    }

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器异常：{str(e)}'}


def get_media_list(key=None, schema=None, camera_name=None):
    """
    同步获取流列表
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getMediaList"
    params = {'secret': ZLK_SECRET}
    if schema:
        params['schema'] = schema

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': '响应内容不是合法 JSON'}

        if zlk_info.get('code') == 0 and zlk_info.get('data'):
            # 创建数据库会话
            with SessionLocal() as db_session:
                query = select(Zlk_data)
                if camera_name:
                    query = query.where(Zlk_data.cameras_name.like(f"%{camera_name}%"))

                result = db_session.execute(query)
                db_streams = result.scalars().all()

                # 创建一个以zlk_live为键的字典，方便查找
                db_stream_dict = {stream.zlk_live: stream for stream in db_streams}

                # 用于存储筛选后的结果
                filtered_data = []

                # 为每个流添加数据库信息
                for stream_data in zlk_info['data']:
                    # 从ZLMediaKit返回的数据中获取stream字段
                    stream_key = stream_data.get('stream')

                    # 检查是否能找到匹配的数据库记录
                    if stream_key and stream_key in db_stream_dict:
                        db_stream = db_stream_dict[stream_key]
                        stream_data['id'] = db_stream.id
                        stream_data['cameras_name'] = db_stream.cameras_name if db_stream.cameras_name else None
                        stream_data['create_date'] = db_stream.create_date.strftime(
                            '%Y-%m-%d %H:%M:%S') if db_stream.create_date else None

                        # 根据协议类型设置stream_url
                        schema_type = stream_data.get('schema', '')
                        if schema_type == 'rtsp':
                            stream_data['stream_url'] = db_stream.zlk_rtsp
                        elif schema_type == 'rtmp':
                            stream_data['stream_url'] = db_stream.zlk_rtmp
                        elif schema_type == 'hls':
                            stream_data['stream_url'] = db_stream.zlk_hls
                        elif schema_type == 'hls.fmp4':
                            stream_data['stream_url'] = db_stream.zlk_hls_fmp4
                        elif schema_type == 'ts':
                            stream_data['stream_url'] = db_stream.zlk_ts
                        elif schema_type == 'fmp4':
                            stream_data['stream_url'] = db_stream.zlk_mp4
                        elif schema_type == 'flv':
                            stream_data['stream_url'] = db_stream.zlk_flv
                        else:
                            stream_data['stream_url'] = None

                        # 如果提供了摄像头名称筛选条件，只添加匹配的流
                        if camera_name:
                            if db_stream.cameras_name and camera_name.lower() in db_stream.cameras_name.lower():
                                filtered_data.append(stream_data)
                        else:
                            # 如果没有筛选条件，添加所有匹配的流
                            filtered_data.append(stream_data)
                    else:
                        # 如果找不到对应的数据库记录，仍然显示ZLMediaKit的信息，但数据库相关字段为空
                        stream_data['id'] = None
                        stream_data['cameras_name'] = None
                        stream_data['stream_url'] = None
                        stream_data['create_date'] = None

                        # 只有在没有筛选条件时才添加没有匹配记录的流
                        if not camera_name:
                            filtered_data.append(stream_data)

            return {'code': 200, 'data': filtered_data}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 响应失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器异常：{str(e)}'}


def get_media_player_list(schema='rtmp', vhost='__defaultVhost__', app=None, stream=None):
    """
    同步获取某个流的观看者列表
    """
    if not app or not stream:
        return {'code': 400, 'msg': '参数不完整，必须提供 app 和 stream'}

    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getMediaPlayerList"
    params = {
        'secret': ZLK_SECRET,
        'schema': schema,
        'vhost': vhost,
        'app': app,
        'stream': stream
    }

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应内容不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 响应失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'未知错误：{str(e)}'}


def list_stream_proxy():
    """
    同步获取拉流代理列表
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/listStreamProxy"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        response.raise_for_status()
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器异常：{str(e)}'}


def get_server_config():
    """
    同步获取服务器配置
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getServerConfig"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def restart_server():
    """
    同步重启服务器
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/restartServer"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('msg')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def get_work_threads_load():
    """
    同步获取各后台 epoll(或 select)线程负载以及延时
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getWorkThreadsLoad"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception as e:
            return {'code': 400, 'msg': f'ZLMediaKit 响应格式不是合法 JSON: {str(e)}'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data', {})}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}
    except requests.exceptions.ConnectionError:
        return {'code': 400, 'msg': '服务器不在线！无法连接到服务器'}
    except requests.exceptions.RequestException as e:
        return {'code': 400, 'msg': f'服务器不在线！请求错误：{str(e)}'}
    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def get_statistic():
    """
    同步获取主要对象个数统计，主要用于分析内存性能
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getStatistic"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def getAllSession():
    """
    获取tcp连接（同步版本）
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getAllSession"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def kick_session(id=None):
    """
    同步关闭指定的会话连接
    """
    if not id:
        return {'code': 400, 'msg': '参数不完整，必须提供 id'}

    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/kick_session"
    params = {
        'secret': ZLK_SECRET,
        'id': id,
    }

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应内容不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'msg': '成功关闭观看者'}
        else:
            return {'code': 400, 'msg': 'ZLMediaKit 响应失败'}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'未知错误：{str(e)}'}


def get_version():
    """
    同步获取版本信息 如分支，commit id, 编译时间
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/version"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        try:
            zlk_info = response.json()
        except Exception:
            return {'code': 400, 'msg': 'ZLMediaKit 响应格式不是合法 JSON'}

        if zlk_info.get('code') == 0:
            return {'code': 200, 'data': zlk_info.get('data')}
        else:
            return {'code': 400, 'msg': zlk_info.get('msg', 'ZLMediaKit 接口返回失败')}

    except requests.exceptions.Timeout:
        return {'code': 400, 'msg': '服务器不在线（请求超时）！'}

    except Exception as e:
        return {'code': 500, 'msg': f'服务器内部异常：{str(e)}'}


def fetch_stream_proxy_list_sync():
    """
    同步获取ZLMediaKit的拉流代理列表
    """
    api = f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/getMediaList"
    params = {'secret': ZLK_SECRET}

    try:
        response = requests.get(api, params=params, timeout=5)
        response.raise_for_status()
        json_data = response.json()
        if json_data.get("code") == 0:
            return json_data.get("data", [])
        else:
            # logger.warning(f"接口返回错误: {json_data.get('msg')}")
            print(f"接口返回错误: {json_data.get('msg')}")
            return []
    except Exception as e:
        # logger.error(f"请求异常: {e}")
        print(f"请求异常: {e}")
        return []


def stream_proxy_identities(data):
    """读取代理对象身份，兼容列表及 key->对象格式；正在重连的代理也保留。"""
    if data is None:
        return set()
    if isinstance(data, dict):
        if any(not isinstance(value, dict) for value in data.values()):
            raise ValueError('流媒体代理对象格式异常')
        data = [dict(value, key=key) for key, value in data.items()]
    if not isinstance(data, list):
        raise ValueError('流媒体代理列表格式异常')
    identities = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('流媒体代理对象格式异常')
        src = item.get('src') or {}
        app = src.get('app') or item.get('app')
        stream = src.get('stream') or item.get('stream')
        if not app or not stream:
            parts = str(item.get('key') or '').rsplit('/', 2)
            if len(parts) == 3:
                app, stream = parts[1:]
        if not app or not stream:
            raise ValueError('流媒体代理缺少身份信息')
        identities.add((app, stream))
    return identities


def add_stream_proxy_sync(cameras_rtsp, cameras_name, zlk_app, zlk_live,
                          enable_rtsp=None, enable_hls=None, enable_hls_fmp4=None,
                          enable_rtmp=None, enable_ts=None, enable_fmp4=None):
    """按原 app/stream 和协议恢复代理；不修改数据库中的播放地址或设备绑定。"""
    requested = [enable_rtsp, enable_hls, enable_hls_fmp4, enable_rtmp, enable_ts, enable_fmp4]
    session = None
    engine = None
    try:
        if any(value is None for value in requested):
            from model.extra import Zlk_data
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine
            from config.configs import DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME
            database_url = f"mysql+pymysql://{urllib.parse.quote(DB_USER)}:{urllib.parse.quote(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            engine = create_engine(database_url)
            session = sessionmaker(bind=engine)()
            camera = session.query(Zlk_data.zlk_rtsp, Zlk_data.zlk_hls,
                Zlk_data.zlk_hls_fmp4, Zlk_data.zlk_rtmp, Zlk_data.zlk_ts,
                Zlk_data.zlk_mp4).filter_by(cameras_rtsp=cameras_rtsp).first()
            requested = [bool(camera[i]) if value is None and camera else
                         False if value is None else value for i, value in enumerate(requested)]
        flags = dict(zip(['enable_rtsp', 'enable_hls', 'enable_hls_fmp4',
            'enable_rtmp', 'enable_ts', 'enable_fmp4'],
            ['1' if (v.strip().lower() in ('1', 'true', 'on', 'yes')
                     if isinstance(v, str) else bool(v)) else '0' for v in requested]))
        if not cameras_rtsp or not zlk_app or not zlk_live or not any(v == '1' for v in flags.values()):
            return False
        params = dict(secret=ZLK_SECRET, vhost=ZLK_HOST, app=zlk_app,
            stream=zlk_live, url=cameras_rtsp, **flags)
        response = requests.get(f"http://{ZLK_HOST}:{ZLK_PORT}/index/api/addStreamProxy",
            params=params, timeout=(3, 15))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get('code') != 0:
            print(f"恢复流代理失败: {cameras_name}（接口未确认成功）")
            return False
        print(f"恢复流代理成功: {cameras_name}")
        return True
    except Exception as exc:
        # 请求异常可能包含源地址或 secret，不输出原始异常文本。
        print(f"恢复流代理失败: {cameras_name}（{type(exc).__name__}）")
        return False
    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()
