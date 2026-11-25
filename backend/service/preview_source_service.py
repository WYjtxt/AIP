# native-hik-platform-preview-v1
# native-onvif-bound-preview-v1
"""Prepare only the selected enabled recorder channel using saved server data."""
import hashlib
import logging
import re
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlsplit, urlunsplit

import redis
import requests
from requests.auth import HTTPDigestAuth
from sqlalchemy import or_

from config.zlk_conf import ZLK_HOST, ZLK_PORT, ZLK_SECRET
from data.exts import db
from model.equipment import Equipment, VCR_data
from model.extra import Zlk_data
from service.preview_compat_service import CompatError, _device_id, _redis, _RELEASE_LOCK
from service.preview_urls import media_base_url, playback_urls

logger = logging.getLogger(__name__)
PREFIX = 'preview_source:v1:'


def _registered_source(equipment, parent):
    if (not parent or parent.user_status not in ('1', None)
            or not parent.equipment_ip or not parent.equipment_uname
            or not parent.equipment_password):
        raise CompatError(409, '录像机接入信息不完整或已禁用，请检查设备配置')
    vendor = parent.manufacturer_type
    code = str(equipment.code or '')
    if vendor == '大华' and equipment.Onvif_rtsp_url:
        parsed = urlsplit(equipment.Onvif_rtsp_url)
        if parsed.scheme != 'rtsp' or parsed.hostname != parent.equipment_ip:
            raise CompatError(409, '录像机 Onvif 地址不匹配，请重新同步设备')
        host = parsed.hostname
        authority = '{}:{}@{}:{}'.format(quote(parent.equipment_uname, safe=''),
            quote(parent.equipment_password, safe=''), host, parsed.port or 554)
        return urlunsplit(('rtsp', authority, parsed.path, parsed.query, ''))
    channel = equipment.equipment_aisles
    if type(channel) is not int or channel < 1:
        raise CompatError(409, '录像机通道号无效，请重新同步设备')
    if vendor == '海康':
        if not re.fullmatch(r'[1-9][0-9]{2,7}', code) or int(code[:-2]) != channel:
            raise CompatError(409, '录像机通道配置不一致，请重新同步设备')
        path = '/Streaming/Unicast/Channels/' + code
    elif vendor == '宇视':
        path = '/unicast/c{}/s1/live'.format(channel)
    else:
        raise CompatError(409, '该录像机通道尚未提供可用的取流地址，请检查接入配置')
    host = str(parent.equipment_ip).strip('[]')
    host = '[{}]'.format(host) if ':' in host else host
    return 'rtsp://{}:{}@{}:554{}'.format(quote(parent.equipment_uname, safe=''),
        quote(parent.equipment_password, safe=''), host, path)


def _proxy_api(method, **params):
    params['secret'] = ZLK_SECRET
    try:
        response = requests.post(media_base_url(ZLK_HOST, ZLK_PORT) + '/index/api/' + method,
                                 data=params, timeout=(2, 12), allow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or type(result.get('code')) is not int:
            raise ValueError()
        return result
    except (requests.RequestException, ValueError, TypeError):
        raise CompatError(503, '通道转发准备超时或流媒体服务不可用，请稍后重试')


def _registered_direct_source(equipment, parent, timeout=(2, 4)):
    """Confirm the live recorder channel mapping before bypassing its failed relay."""
    if (parent.manufacturer_type != '海康' or not equipment.equipment_ip
            or equipment.equipment_ip == parent.equipment_ip
            or not equipment.equipment_uname or not equipment.equipment_password):
        raise CompatError(409, '录像机取流失败，且该通道未配置可验证的摄像头直连信息')
    vcr = db.session.query(VCR_data).get(parent.VCR_data_id) if parent.VCR_data_id else None
    if not vcr or vcr.vcr_ip != parent.equipment_ip:
        raise CompatError(409, '录像机通道来源无法核对，请重新同步设备')
    try:
        response = requests.get('http://{}:{}/ISAPI/ContentMgmt/InputProxy/channels/{}'.format(
            vcr.vcr_ip, vcr.vcr_port or 80, equipment.equipment_aisles),
            auth=HTTPDigestAuth(vcr.vcr_username, vcr.vcr_password),
            timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        for element in root.iter():
            element.tag = element.tag.split('}')[-1]
        if (root.findtext('id') != str(equipment.equipment_aisles)
                or root.findtext('.//ipAddress') != equipment.equipment_ip):
            raise CompatError(409, '录像机通道与摄像头地址已变更，请重新同步后播放')
        source_channel = int(root.findtext('.//srcInputPort'))
        if not 1 <= source_channel <= 99999:
            raise ValueError()
        suffix = 2 if str(equipment.code).endswith('02') else 1
        host = equipment.equipment_ip
        host = '[{}]'.format(host) if ':' in host else host
        return 'rtsp://{}:{}@{}:{}/Streaming/Channels/{}'.format(
            quote(equipment.equipment_uname, safe=''), quote(equipment.equipment_password, safe=''),
            host, equipment.equipment_port or 554, source_channel * 100 + suffix)
    except (requests.RequestException, ET.ParseError, ValueError, TypeError) as exc:
        error = CompatError(409, '录像机取流失败，无法验证摄像头直连来源，请稍后重试')
        # Internal metadata only. Existing HTTP response code/message stay the
        # same, while background recovery can stop retrying rejected accounts.
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status in (401, 403):
            error.source_status = status
        raise error


def _existing_proxy_matches(key, stream, source):
    from service.bound_preview_recovery import _canonical_source, _proxy_detail, RecoveryError
    proxies = _proxy_api('listStreamProxy')
    if proxies.get('code') != 0:
        raise CompatError(503, '无法核对已有转发，请稍后重试')
    try:
        detail = _proxy_detail(proxies.get('data'), [], 'openUrl', stream)
        if not detail or detail.get('key') != key:
            return False
        return _canonical_source(detail.get('source')) == _canonical_source(source)
    except RecoveryError:
        return False


def prepare_recorder_channel(equipment_id):
    client, token, lock_key = None, None, None
    created_key, committed = None, False
    try:
        equipment_id = _device_id(equipment_id)
        # Delegate before acquiring the shared per-device Redis lock. The
        # recovery helper owns both that lock and the scheduler recovery lock.
        existing = db.session.query(Equipment.zlk_dat_id, Equipment.equipment_type).filter(
            Equipment.id == equipment_id).first()
        if existing and existing[1] == '安防平台':
            db.session.rollback()
            from service.hik_preview_service import prepare_hik_preview
            return prepare_hik_preview(equipment_id)
        if existing and existing[0]:
            db.session.rollback()
            from service.bound_preview_recovery import recover_bound_preview
            return recover_bound_preview(equipment_id, recheck_recorder=True)
        client = _redis()
        lock_key, token = PREFIX + 'lock:' + str(equipment_id), uuid.uuid4().hex
        if not client.set(lock_key, token, nx=True, ex=90):
            token = None
            return {'code': 202, 'msg': '正在建立通道转发', 'retry_after_ms': 1000}
        equipment = db.session.query(Equipment).filter(
            Equipment.id == equipment_id,
            or_(Equipment.user_status == '1', Equipment.user_status.is_(None))).first()
        if equipment is None:
            raise CompatError(404, '该监控点不存在或已禁用')
        if equipment.zlk_dat_id:
            binding = db.session.query(Zlk_data).get(equipment.zlk_dat_id)
            if not binding or str(binding.equipment_id) != str(equipment_id):
                raise CompatError(409, '该设备流媒体关联不一致，请检查流媒体管理')
            return {'code': 202, 'msg': '通道关联刚更新，正在核对视频转发', 'retry_after_ms': 1000}
        if (not equipment.parent_id or equipment.equipment_type not in
                ('录像机', '特殊摄像头', '视频中心存储')):
            raise CompatError(409, '该设备未配置转发，请检查设备接入')
        # An explicit play request verifies the registered source even when the
        # last inventory poll saw an outage. Inventory owns the online flag.
        parent = db.session.query(Equipment).get(equipment.parent_id)
        source = _registered_source(equipment, parent)
        original_source = source
        original_channel = (equipment.parent_id, equipment.code, equipment.equipment_aisles)
        original_camera = (equipment.equipment_ip, equipment.equipment_uname, equipment.equipment_password)
        source_mode = 'recorder'
        fingerprint = hashlib.sha256(source.encode()).hexdigest()
        stream = 'preview_nvr_{}_{}'.format(equipment_id, fingerprint[:12])
        key = '__defaultVhost__/openUrl/' + stream
        result = _proxy_api('addStreamProxy', vhost='__defaultVhost__', app='openUrl',
            stream=stream, url=source, rtp_type=0, timeout_sec=8, retry_count=3,
            enable_rtsp=1, enable_rtmp=1, enable_fmp4=1, enable_hls=0,
            enable_hls_fmp4=0, enable_ts=0, enable_mp4=0)
        if result['code'] != 0 and re.search(r'\b(?:500|5XX)\b', str(result.get('msg') or ''), re.I):
            # A failed add does not establish ownership of any existing proxy.
            # The failed request has bounded retries. It is safe to try the
            # distinct, verified camera stream without closing another reader.
            source = _registered_direct_source(equipment, parent)
            source_mode = 'camera-direct'
            fingerprint = hashlib.sha256(source.encode()).hexdigest()
            stream = 'preview_ipc_{}_{}'.format(equipment_id, fingerprint[:12])
            key = '__defaultVhost__/openUrl/' + stream
            result = _proxy_api('addStreamProxy', vhost='__defaultVhost__', app='openUrl',
                stream=stream, url=source, rtp_type=0, timeout_sec=8, retry_count=3,
                enable_rtsp=1, enable_rtmp=1, enable_fmp4=1, enable_hls=0,
                enable_hls_fmp4=0, enable_ts=0, enable_mp4=0)
        if result['code'] != 0:
            message = str(result.get('msg') or '')
            if '401' in message or 'Unauthorized' in message:
                raise CompatError(409, '视频来源拒绝取流认证，请检查设备账密及通道权限')
            if 'already exist' not in message.lower() or not _existing_proxy_matches(key, stream, source):
                raise CompatError(409, '该通道取流失败，请检查录像机通道配置和连接状态')
            # Restore the verified binding even when the proxy is reconnecting.
            # The play endpoint independently checks that its video is ready.
        elif (result.get('data') or {}).get('key') != key:
            raise CompatError(503, '通道转发关联异常，请稍后重试')
        else:
            created_key = key
        # Lock only the final binding transaction; do not hold a DB lock during network I/O.
        db.session.expire_all()
        current = db.session.query(Equipment).filter(Equipment.id == equipment_id).with_for_update().first()
        if (not current or current.user_status not in ('1', None)
                or (current.parent_id, current.code, current.equipment_aisles) != original_channel
                or _registered_source(current, db.session.query(Equipment).get(current.parent_id)) != original_source
                or (current.equipment_ip, current.equipment_uname, current.equipment_password) != original_camera):
            db.session.rollback()
            raise CompatError(409, '该通道配置已变更，请刷新后重试')
        if current.zlk_dat_id:
            winner = db.session.query(Zlk_data).get(current.zlk_dat_id)
            if (winner and winner.zlk_app == 'openUrl' and winner.zlk_live == stream
                    and str(winner.equipment_id) == str(equipment_id)):
                # Another database writer adopted this exact successful proxy.
                # Its live binding owns the proxy now, so cleanup must keep it.
                committed = True
            db.session.rollback()
            return {'code': 200, 'msg': '通道转发已由设备同步建立',
                    'data': {'id': equipment_id, 'source_mode': source_mode if committed else 'recorder'}}
        # A recorder refresh may have cleared only the equipment's foreign key.
        # Relink the same row without duplicating it or overwriting manual flags.
        previous = db.session.query(Zlk_data).filter(
            Zlk_data.zlk_app == 'openUrl', Zlk_data.zlk_live == stream).all()
        if previous:
            committed = True  # A matching stream identity is already in use.
            saved = previous[0]
            if (len(previous) != 1 or str(saved.equipment_id) != str(equipment_id)
                    or saved.cameras_rtsp != source or saved.zlk_key != key
                    or db.session.query(Equipment.id).filter(Equipment.zlk_dat_id == saved.id,
                                                           Equipment.id != equipment_id).first()):
                raise CompatError(409, '已有转发归属无法核对，请检查流媒体管理')
            current.zlk_dat_id = saved.id
            db.session.commit()
            return {'code': 200, 'msg': '已恢复原通道关联',
                    'data': {'id': equipment_id, 'source_mode': source_mode}}
        urls = playback_urls(media_base_url(ZLK_HOST, ZLK_PORT), 'openUrl', stream)
        binding = Zlk_data(cameras_name=(current.equipment_name or '')[:50], cameras_rtsp=source,
            equipment_id=str(equipment_id), equipment_ip=current.equipment_ip,
            zlk_app='openUrl', zlk_live=stream, zlk_key=key,
            zlk_mp4=urls['mp4'], zlk_rtsp='rtsp://{}:8554/openUrl/{}'.format(ZLK_HOST, stream),
            zlk_rtmp='rtmp://{}:1935/openUrl/{}'.format(ZLK_HOST, stream))
        db.session.add(binding)
        db.session.flush()
        current.zlk_dat_id = binding.id
        db.session.commit()
        committed = True
        return {'code': 200, 'msg': '通道转发已建立',
                'data': {'id': equipment_id, 'source_mode': source_mode}}
    except CompatError as exc:
        db.session.rollback()
        return {'code': exc.code, 'msg': exc.message}
    except redis.RedisError:
        db.session.rollback()
        return {'code': 503, 'msg': '通道转发协调服务暂不可用，请稍后重试'}
    except Exception:
        db.session.rollback()
        logger.warning('录像机通道转发准备失败')
        return {'code': 503, 'msg': '通道转发准备失败，请稍后重试'}
    finally:
        if created_key and not committed:
            # A concurrent device sync/config change won the binding; discard only
            # the new unbound proxy created by this call, preserving its chosen stream.
            try:
                _proxy_api('delStreamProxy', key=created_key)
            except CompatError:
                pass
        if client is not None and token:
            try:
                client.eval(_RELEASE_LOCK, 1, lock_key, token)
            except redis.RedisError:
                pass
