"""Own a fixed, on-demand Hikvision preview proxy for each saved point."""
from contextlib import contextmanager
import hashlib
import json
import logging
import time
import uuid
from urllib.parse import urlsplit


APP = 'openUrl'
VHOST = '__defaultVhost__'
STARTUP_GRACE = 20
FAILURE_COOLDOWN = 60
LOCK_SECONDS = 120
STATE_PREFIX = 'preview_hik:v1:'
_RENEW_LOCK = """if redis.call('get',KEYS[1]) == ARGV[1] then
return redis.call('expire',KEYS[1],ARGV[2]) end return 0"""
logger = logging.getLogger(__name__)


class PreviewError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _stream(equipment_id):
    return 'preview_hik_' + str(equipment_id)


def _proxy_key(equipment_id):
    return VHOST + '/' + APP + '/' + _stream(equipment_id)


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _config_identity(snapshot):
    return _digest(json.dumps([snapshot['parent'], snapshot['area'], snapshot['index'],
                               snapshot['platform']], sort_keys=True, ensure_ascii=True))


def _pending():
    return {'code': 202, 'msg': '正在准备安防平台视频', 'retry_after_ms': 1000}


def _success(equipment_id):
    return {'code': 200, 'msg': '安防平台视频转发已就绪',
            'data': {'id': equipment_id, 'source_mode': 'hik-platform'}}


def _owns(detail, state, equipment_id):
    if not detail or not state or detail.get('key') != _proxy_key(equipment_id):
        return False
    source = detail.get('source')
    return isinstance(source, str) and _digest(source) == state.get('source')


def _may_have_readers(detail, has_media):
    readers = detail.get('readers')
    return readers > 0 if readers is not None else has_media


def prepare_hik_preview(equipment_id, _runtime=None):
    """Share one proxy, and keep an unknown or unrelated stream untouched."""
    try:
        service = _runtime or _Runtime()
        with service.lock(equipment_id):
            expected = service.snapshot(equipment_id)
            identity = _config_identity(expected)
            state = service.load(equipment_id)
            ready, occupied, detail = service.observe(equipment_id)
            owned = _owns(detail, state, equipment_id)
            if (detail and not owned) or (occupied and not owned):
                raise PreviewError(409, '安防平台预览名称被其他转发占用，请检查流媒体配置')
            if owned and state.get('config') == identity:
                if ready:
                    service.bind(equipment_id, expected)
                    return _success(equipment_id)
            if state and state.get('config') == identity:
                elapsed = time.time() - state.get('started', 0)
                if elapsed < STARTUP_GRACE:
                    return _pending()
                if elapsed < STARTUP_GRACE + FAILURE_COOLDOWN:
                    raise PreviewError(503, '安防平台视频准备超时，请检查设备在线状态和取流服务，稍后重试')
            if owned and _may_have_readers(detail, occupied):
                raise PreviewError(409, '原安防平台转发仍在使用，请稍后重试')

            # Resolve before stopping a stale proxy. A denied or unavailable
            # upstream must not destroy any still recoverable local source.
            source = service.resolve(expected)
            if service.snapshot(equipment_id) != expected:
                raise PreviewError(409, '监控点配置已变更，请刷新后重试')
            now_ready, now_occupied, current = service.observe(equipment_id)
            if current:
                if not _owns(current, state, equipment_id):
                    raise PreviewError(409, '安防平台转发归属已变更，请稍后重试')
                if now_ready and state.get('config') == identity:
                    service.bind(equipment_id, expected)
                    return _success(equipment_id)
                if _may_have_readers(current, now_occupied):
                    raise PreviewError(409, '原安防平台转发仍在使用，请稍后重试')
                service.remove(equipment_id)
            elif now_occupied:
                raise PreviewError(409, '安防平台预览名称被其他转发占用，请检查流媒体配置')

            # A successful ZLM call can outlive a timed-out HTTP request.
            # Keep a fingerprint so the next request can adopt only that source.
            state = {'config': identity, 'source': _digest(source), 'started': time.time()}
            service.save(equipment_id, state)
            service.add(equipment_id, source)
            ready, occupied, detail = service.observe(equipment_id)
            if not ready:
                return _pending()
            if not _owns(detail, state, equipment_id):
                raise PreviewError(409, '安防平台转发归属无法确认，请稍后重试')
            service.bind(equipment_id, expected)
            return _success(equipment_id)
    except PreviewError as error:
        if error.code == 202:
            return _pending()
        return {'code': error.code, 'msg': error.message}
    except Exception:
        # Exceptions from Redis, the database or ZLM can include source URLs.
        logger.warning('安防平台预览转发准备失败')
        return {'code': 503, 'msg': '安防平台转发暂不可用，请稍后重试'}


class _Runtime:
    def __init__(self):
        from data.exts import db
        from model.equipment import Equipment
        from model.extra import Zlk_data
        from service import preview_source_service as recorder
        self.db = db
        self.equipment = Equipment
        self.binding = Zlk_data
        self.recorder = recorder
        self.client = recorder._redis()
        self.lock_owner = None

    @contextmanager
    def lock(self, equipment_id):
        key = self.recorder.PREFIX + 'lock:' + str(equipment_id)
        token = uuid.uuid4().hex
        if not self.client.set(key, token, nx=True, ex=LOCK_SECONDS):
            raise PreviewError(202, _pending()['msg'])
        self.lock_owner = (key, token)
        try:
            yield
        finally:
            self.lock_owner = None
            try:
                self.client.eval(self.recorder._RELEASE_LOCK, 1, key, token)
            except Exception:
                pass

    def _check_lock(self):
        if not self.lock_owner:
            raise PreviewError(202, _pending()['msg'])
        key, token = self.lock_owner
        if self.client.eval(_RENEW_LOCK, 1, key, token, LOCK_SECONDS) != 1:
            raise PreviewError(202, _pending()['msg'])

    def load(self, equipment_id):
        raw = self.client.get(STATE_PREFIX + str(equipment_id))
        try:
            state = json.loads(raw) if raw else None
            if isinstance(state, dict) and isinstance(state.get('started'), (int, float)):
                return state
        except (ValueError, TypeError):
            pass
        return None

    def save(self, equipment_id, state):
        self._check_lock()
        self.client.set(STATE_PREFIX + str(equipment_id), json.dumps(state))

    def _registered(self, equipment_id, lock=False):
        from service.algorithm_stream_selection import _hik_platform_config
        query = self.db.session.query(self.equipment).filter(self.equipment.id == equipment_id)
        equipment = (query.with_for_update() if lock else query).first()
        if not equipment or equipment.user_status not in ('1', None):
            raise PreviewError(404, '该监控点不存在或已禁用')
        if (equipment.equipment_type != '安防平台' or equipment.manufacturer_type != '海康'
                or not equipment.parent_id or not equipment.Hik_id or not equipment.Hik_indexCode):
            raise PreviewError(409, '该监控点缺少有效的海康安防平台接入信息')
        try:
            platform = _hik_platform_config(equipment)
        except ValueError:
            raise PreviewError(409, '安防平台配置不完整，请同步监控点并检查平台授权') from None

        binding = None
        if equipment.zlk_dat_id:
            query = self.db.session.query(self.binding).filter(self.binding.id == equipment.zlk_dat_id)
            binding = (query.with_for_update() if lock else query).first()
            if (not binding or str(binding.equipment_id) != str(equipment_id)
                    or binding.zlk_app != APP or binding.zlk_live != _stream(equipment_id)
                    or binding.zlk_key != _proxy_key(equipment_id)):
                raise PreviewError(409, '该监控点已有其他转发绑定，请检查流媒体配置')
        expected = {'parent': equipment.parent_id, 'area': equipment.Hik_id,
                    'index': equipment.Hik_indexCode, 'platform': platform,
                    'binding_id': equipment.zlk_dat_id}
        return equipment, binding, expected

    def snapshot(self, equipment_id):
        try:
            return self._registered(equipment_id)[2]
        finally:
            self.db.session.rollback()

    def bind(self, equipment_id, expected):
        from config.zlk_conf import ZLK_HOST, ZLK_PORT
        from service.preview_urls import media_base_url, playback_urls
        self._check_lock()
        try:
            equipment, binding, current = self._registered(equipment_id, lock=True)
            if current != expected:
                raise PreviewError(409, '监控点配置或转发关联已变更，请刷新后重试')
            if binding is not None:
                self.db.session.rollback()
                return
            stream = _stream(equipment_id)
            urls = playback_urls(media_base_url(ZLK_HOST, ZLK_PORT), APP, stream)
            host = str(ZLK_HOST).strip('[]')
            host = '[{}]'.format(host) if ':' in host else host
            binding = self.binding(cameras_name=(equipment.equipment_name or '')[:50],
                equipment_id=str(equipment_id), equipment_ip=equipment.equipment_ip,
                zlk_app=APP, zlk_live=stream, zlk_key=_proxy_key(equipment_id),
                zlk_mp4=urls['mp4'], zlk_rtsp='rtsp://{}:8554/{}/{}'.format(host, APP, stream),
                zlk_rtmp='rtmp://{}:1935/{}/{}'.format(host, APP, stream))
            self.db.session.add(binding)
            self.db.session.flush()
            equipment.zlk_dat_id = binding.id
            self.db.session.commit()
        except Exception:
            self.db.session.rollback()
            raise

    def resolve(self, expected):
        from service.algorithm_platform_source import resolve_hik_platform_url
        try:
            from tool.hik_gateway import hik_online_states
            online = hik_online_states(expected['platform'])
            if online is not None and online.get(expected['index']) is False:
                raise PreviewError(409, '设备离线，请检查摄像机供电与网络')
            source = resolve_hik_platform_url(expected['platform'], expected['index'],
                                              stream_type='main', force_refresh=True)
            uri = urlsplit(source)
            if uri.scheme != 'rtsp' or not uri.hostname:
                raise ValueError()
            return source
        except (ValueError, TypeError):
            raise PreviewError(409, '海康安防平台未提供可用视频，请检查服务和授权') from None

    def observe(self, equipment_id):
        from service.bound_preview_recovery import _has_video, _proxy_detail
        stream = _stream(equipment_id)
        media = self.recorder._proxy_api('getMediaList', vhost=VHOST, app=APP, stream=stream)
        rows = media.get('data')
        if media.get('code') != 0 or (rows is not None and not isinstance(rows, list)):
            raise PreviewError(503, '无法确认安防平台媒体状态，请稍后重试')
        matching = [row for row in rows or [] if isinstance(row, dict)
                    and row.get('vhost', VHOST) == VHOST
                    and (row.get('app'), row.get('stream')) == (APP, stream)]
        proxies = self.recorder._proxy_api('listStreamProxy')
        if proxies.get('code') != 0:
            raise PreviewError(503, '无法确认安防平台代理状态，请稍后重试')
        detail = _proxy_detail(proxies.get('data'), matching, APP, stream)
        ready = _has_video([row for row in matching if row.get('schema') == 'fmp4'], APP, stream)
        return ready, bool(matching), detail

    def remove(self, equipment_id):
        self._check_lock()
        result = self.recorder._proxy_api('delStreamProxy', key=_proxy_key(equipment_id))
        if result.get('code') != 0 or (result.get('data') or {}).get('flag') is False:
            raise PreviewError(503, '旧安防平台转发未能关闭，请稍后重试')

    def add(self, equipment_id, source):
        self._check_lock()
        result = self.recorder._proxy_api('addStreamProxy', vhost=VHOST, app=APP,
            stream=_stream(equipment_id), url=source, rtp_type=0, timeout_sec=8, retry_count=3,
            enable_rtsp=1, enable_rtmp=1, enable_fmp4=1, enable_hls=0,
            enable_hls_fmp4=0, enable_ts=0, enable_mp4=0)
        if result.get('code') != 0:
            raise PreviewError(409, '安防平台视频连接失败，请稍后重试')
        if (result.get('data') or {}).get('key') != _proxy_key(equipment_id):
            raise PreviewError(503, '安防平台转发关联异常，请稍后重试')
