from data.zlmediakit_data import ZLMediaKitData
from config.zlk_conf import *
import json


def check_stream_access(activate_key, stream_key):
    """
    检查激活码是否有权限访问指定的流
    """
    # 检查激活信息
    activate_info = Activate_info.query.filter_by(activate_key=activate_key).first()

    if not activate_info:
        return False

    # 检查是否激活
    if activate_info.activate_status != '1':
        return False

    # 检查是否过期
    if activate_info.activate_valid_until:
        from datetime import datetime
        valid_until = datetime.strptime(activate_info.activate_valid_until, '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() > valid_until:
            return False

    # 如果激活码有效，允许访问所有流（也可以根据需要添加更细粒度的权限控制）
    return True

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'on', 'yes')
    return bool(value)


def _safe_stream_close_error(error):
    import re
    message = str(error or '关闭流媒体失败')
    message = re.sub(r'(?i)(?:https?|rtsps?)(?:://|%3a%2f%2f)[^\s\'"<>]+',
                     '<流地址已隐藏>', message)
    message = re.sub(r'(?i)(\b(?:secret|password|authorization)\b[\'\"]?\s*[=:]\s*[\'\"]?)[^&\s,\'"}]+',
                     r'\1<已隐藏>', message)
    return message[:400]


def _stream_close_ids(value):
    """Validate the complete selection before any close operation."""
    if isinstance(value, str):
        value = value.strip()
        if value.startswith('['):
            value = json.loads(value)
        else:
            value = value.split(',')
    elif type(value) is int:
        value = [value]
    if not isinstance(value, list) or not value or len(value) > 1000:
        raise ValueError('ids必须是1至1000个正整数ID')
    ids = []
    for item in value:
        if isinstance(item, str):
            item = item.strip()
            if not item or not item.isascii() or not item.isdigit():
                raise ValueError('ids必须全部为正整数ID')
            item = int(item)
        if type(item) is not int or not 1 <= item <= 2147483647:
            raise ValueError('ids必须全部为正整数ID')
        if item not in ids:
            ids.append(item)
    return ids


def _close_one_stream(stream_id, _services=None):
    """Serialize a complete user close with recovery; never guess an owner."""
    from service.bound_preview_recovery import RecoveryError, _signature
    services = None
    try:
        services = _services or _StreamCloseRuntime()
        expected = services.snapshot(stream_id)
        if expected is None:
            return {'id': stream_id, 'code': 404, 'msg': '流不存在或已关闭'}
        # The initial DB read is rolled back before waiting for recovery locks.
        # Inside them, refresh and lock rows; old queues cannot resurrect a
        # stream after this complete close commits.
        with services.locks(expected['device_owner']):
            current = services.snapshot(stream_id, locked=True, expected_owner=expected['device_owner'])
            if current is None:
                return {'id': stream_id, 'code': 404, 'msg': '流不存在或已关闭'}
            if _signature(current) != _signature(expected):
                return {'id': stream_id, 'code': 409, 'msg': '流配置或设备绑定已变化，请刷新后重试'}
            result = services.close(current['key'])
            if isinstance(result, dict) and result.get('code') == 200:
                services.delete_current()
                return {'id': stream_id, 'code': 200, 'msg': '关闭成功'}
            result = result if isinstance(result, dict) else {}
            return {'id': stream_id, 'code': result.get('code', 500),
                    'msg': _safe_stream_close_error(result.get('msg'))}
    except RecoveryError as exc:
        if exc.reason == 'lock_busy' or exc.code == 202:
            return {'id': stream_id, 'code': 409, 'msg': '该流正在恢复或关闭，请稍后重试',
                    'retry_after_ms': 1000}
        return {'id': stream_id, 'code': exc.code, 'msg': exc.message}
    except Exception as exc:
        return {'id': stream_id, 'code': 500, 'msg': '关闭异常：' + _safe_stream_close_error(exc)}
    finally:
        if services is not None:
            try:
                services.rollback()
            except Exception:
                pass


class _StreamCloseRuntime:
    def __init__(self):
        from service.bound_preview_recovery import _Runtime
        self.runtime = _Runtime()
        self.current = None

    def locks(self, owner):
        # Unbound/analysis records cannot be healed as recorder bindings, but
        # still serialize through the same file lock before deleting a proxy.
        return self.runtime.locks(owner) if owner is not None else self.runtime.global_lock()

    def snapshot(self, stream_id, locked=False, expected_owner=None):
        from service.bound_preview_recovery import RecoveryError, _identity, URL_FIELDS
        session, equipment, binding = self.runtime.db.session, self.runtime.Equipment, self.runtime.Binding
        session.rollback()
        try:
            if locked and expected_owner is not None:
                # Same row order as recovery's CAS: Equipment before Binding.
                session.query(equipment).filter(equipment.id == expected_owner).with_for_update().first()
            query = session.query(binding).filter(binding.id == stream_id)
            row = (query.with_for_update() if locked else query).first()
            if row is None:
                return None
            owners = session.query(equipment.id).filter(equipment.zlk_dat_id == row.id)
            owners = (owners.with_for_update() if locked else owners).all()
            owner = None
            if owners:
                if len(owners) != 1:
                    raise RecoveryError(409, '设备绑定归属不唯一，请核对后关闭', 'configuration_changed')
                owner = _identity(owners[0][0])
                if str(row.equipment_id) != str(owner):
                    raise RecoveryError(409, '设备绑定归属不一致，请核对后关闭', 'configuration_changed')
            result = dict(id=row.id, device_owner=owner, owner=row.equipment_id,
                key=row.zlk_key, app=row.zlk_app, live=row.zlk_live, source=row.cameras_rtsp,
                urls={field: getattr(row, field, None) for field in URL_FIELDS})
            if locked:
                self.current = row
            return result
        finally:
            if not locked:
                session.rollback()

    close = staticmethod(del_stream_proxy)

    def delete_current(self):
        ZLMediaKitData.delete_stream(self.current)

    def rollback(self):
        self.runtime.db.session.rollback()


class ZLMediaKitService:
    @staticmethod
    def add_stream(rtsp_list, equipment_name, enable_rtsp, enable_hls, enable_hls_fmp4, enable_rtmp, enable_ts, enable_fmp4):
        """
        添加流代理
        """
        flat_result = flatten_equipment_data(json.loads(rtsp_list))
        results = []
        success_count = 0
        fail_count = 0

        for data in flat_result:
            rtsp = data.get('rtsp')
            name = data.get('name')

            if not rtsp:
                results.append({
                    'equipment_name': name,
                    'rtsp': rtsp,
                    'code': 400,
                    'msg': '缺少RTSP地址'
                })
                return {'code': 400, 'msg': '缺少RTSP地址', 'data': results}

            try:
                result = add_stream_proxy(
                    url=rtsp,
                    url_name=name,
                    enable_rtsp=parse_bool(enable_rtsp),
                    enable_hls=parse_bool(enable_hls),
                    enable_hls_fmp4=parse_bool(enable_hls_fmp4),
                    enable_rtmp=parse_bool(enable_rtmp),
                    enable_ts=parse_bool(enable_ts),
                    enable_fmp4=parse_bool(enable_fmp4)
                )

                if result.get('code') != 200:
                    return result

                results.append({
                    'equipment_name': name,
                    'rtsp': rtsp,
                    'result': result
                })

                if result.get('code') == 200:
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                results.append({
                    'equipment_name': name,
                    'rtsp': rtsp,
                    'code': 500,
                    'msg': f'添加流代理时出错: {str(e)}'
                })
                fail_count += 1

        return {
            'code': 200,
            'msg': f'添加完成',
            'data': results
        }

    @staticmethod
    def play_stream(activate_key, stream_key):
        """
        播放流媒体
        """
        if not activate_key:
            return {'code': 401, 'msg': '未提供激活码'}

        if not check_stream_access(activate_key, stream_key):
            return {'code': 403, 'msg': '无权限访问该流媒体或激活码已过期'}

        stream = ZLMediaKitData.get_stream_by_key(stream_key)
        if not stream:
            return {'code': 404, 'msg': '流不存在'}

        return {
            'code': 200,
            'msg': '获取成功',
            'data': {
                'name': stream.cameras_name,
                'rtsp': stream.zlk_rtsp,
                'rtmp': stream.zlk_rtmp,
                'mp4': stream.zlk_mp4,
                'ts': stream.zlk_ts,
                'flv': stream.zlk_flv
            }
        }

    @staticmethod
    def delete_stream(ids_str):
        """Close selected proxies and return plain data to the API layer."""
        try:
            ids = _stream_close_ids(ids_str)
        except (ValueError, TypeError, OverflowError):
            return {'code': 400, 'msg': 'ids参数格式错误：请选择1至1000个有效的正整数ID'}

        results = []
        for stream_id in ids:
            results.append(_close_one_stream(stream_id))

        if len(results) == 1:
            return results[0]
        failed = sum(item['code'] != 200 for item in results)
        return {'code': 400 if failed else 200,
                'msg': '批量关闭完成：成功{}，失败{}'.format(len(results) - failed, failed),
                'data': results}

    @staticmethod
    def list_streams():
        """
        列出所有流媒体
        """
        streams = ZLMediaKitData.get_all_streams()
        result = []

        for stream in streams:
            result.append({
                'id': stream.id,
                'name': stream.cameras_name,
                'rtsp': stream.zlk_rtsp,
                'create_date': stream.create_date.isoformat() if stream.create_date else None,
                'update_date': stream.update_date.isoformat() if stream.update_date else None
            })

        return jsonify({
            'code': 200,
            'msg': '获取成功',
            'data': result
        })

    @staticmethod
    def get_media_list(key=None, schema=None, camera_name=None):
        """
        获取流列表，可选筛选参数
        """
        return get_media_list(key, schema, camera_name)

    @staticmethod
    def get_media_player_list(schema, vhost, app, id):
        """
        获取某个流的观看者列表
        """
        stream_info = ZLMediaKitData.get_stream_by_id(id)
        if not stream_info:
            return {'code': 404, 'msg': '流不存在'}
        stream = stream_info.zlk_live
        return get_media_player_list(schema, vhost, app, stream)

    @staticmethod
    def list_stream_proxy():
        """
        获取拉流代理列表
        """
        return list_stream_proxy()

    @staticmethod
    def get_server_config():
        """
        获取服务器配置
        """
        return get_server_config()

    @staticmethod
    def restart_server():
        """
        重启服务器
        """
        return restart_server()

    @staticmethod
    def get_work_threads_load():
        """
        获取各后台 epoll(或 select)线程负载以及延时
        """
        return get_work_threads_load()

    @staticmethod
    def get_statistic():
        """
        获取主要对象个数统计，主要用于分析内存性能
        """
        return get_statistic()

    @staticmethod
    def get_all_session():
        """
        获取版本信息 如分支，commit id, 编译时间
        """
        return getAllSession()

    @staticmethod
    def kick_session(id):
        """
        踢出会话
        """
        return kick_session(id)

    @staticmethod
    def get_version():
        """
        获取版本信息 如分支，commit id, 编译时间
        """
        return get_version()
