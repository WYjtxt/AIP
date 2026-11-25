"""On-demand, shared H264 browser previews managed by ZLMediaKit.

Only the dedicated ``preview_compat`` output is owned here. Camera proxies,
camera encoding, algorithm inputs and task state are never modified. Redis
RESP2 coordinates all Gunicorn workers; failure to coordinate fails closed.
ZLK additionally deduplicates addFFmpegSource by the destination URL's MD5.
The dedicated ffmpeg.preview_compat.cmd template is installed by deployment.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid

import redis
import requests
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from config.configs import Redis_ip, Redis_port, Redis_password
from config.zlk_conf import ZLK_HOST, ZLK_PORT, ZLK_SECRET
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from model.preview_settings import PreviewSettings
from service.preview_service import _base_url
from service.preview_urls import media_base_url, playback_urls


logger = logging.getLogger(__name__)
APP = 'preview_compat'
COMMAND_KEY = 'ffmpeg.preview_compat.cmd'
LEASE_SECONDS = 90
MAX_LEASES_PER_DEVICE = 128
IDLE_SECONDS = 30
LOCK_SECONDS = 45
MIN_STREAMS, HARD_MAX_STREAMS = 1, 8
try:
    MAX_STREAMS = max(MIN_STREAMS, min(HARD_MAX_STREAMS,
                      int(os.environ.get('PREVIEW_COMPAT_MAX_STREAMS', '8'))))
except ValueError:
    MAX_STREAMS = HARD_MAX_STREAMS
PREFIX = 'preview_compat:v1:'
LOCK_KEY = PREFIX + 'manager_lock'
INDEX_KEY = PREFIX + 'devices'
LIMIT_KEY = PREFIX + 'max_streams'
_REDIS = None
_THREAD = None
_THREAD_GUARD = threading.Lock()
_RELEASE_LOCK = ("if redis.call('get',KEYS[1]) == ARGV[1] then "
                 "return redis.call('del',KEYS[1]) else return 0 end")
_LEASE_COMPARE_DELETE = ("if redis.call('hget',KEYS[1],ARGV[1]) == ARGV[2] then "
                         "return redis.call('hdel',KEYS[1],ARGV[1]) else return 0 end")
_LEASE_CHANGE = """
local raw = redis.call('hget',KEYS[1],ARGV[1])
if not raw then return 0 end
local ok, lease = pcall(cjson.decode,raw)
if not ok or tonumber(lease.expires or 0) <= tonumber(ARGV[3]) then return 0 end
if lease.owner ~= ARGV[2] then return -1 end
if ARGV[4] == 'release' then return redis.call('hdel',KEYS[1],ARGV[1]) end
lease.expires = tonumber(ARGV[5])
redis.call('hset',KEYS[1],ARGV[1],cjson.encode(lease))
redis.call('expire',KEYS[1],ARGV[6])
return 1
"""


class CompatError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


def _device_id(value):
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r'[0-9]{1,10}', value.strip()):
        result = int(value.strip())
    else:
        raise CompatError(400, '设备ID必须为正整数')
    if not 0 < result <= 2147483647:
        raise CompatError(400, '设备ID必须为正整数')
    return result


def _redis():
    global _REDIS
    if _REDIS is None:
        _REDIS = redis.Redis(host=Redis_ip, port=Redis_port,
                             password=Redis_password, db=0, protocol=2,
                             decode_responses=True, socket_connect_timeout=1,
                             socket_timeout=1)
    return _REDIS


def _api(method, **parameters):
    # Secret is in the POST body, never in browser URLs or exception messages.
    parameters['secret'] = ZLK_SECRET
    timeout = (1, 10) if method == 'addFFmpegSource' else (1, 3)
    try:
        response = requests.post(media_base_url(ZLK_HOST, ZLK_PORT)
                                 + '/index/api/' + method,
                                 data=parameters, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or type(result.get('code')) is not int or result['code'] != 0:
            raise ValueError()
        return result
    except (requests.RequestException, ValueError, TypeError):
        # ZLK errors may contain URLs, command lines or its API secret.
        raise CompatError(503, '兼容预览流媒体服务暂不可用，请稍后重试')


def _rows(result):
    data = result.get('data') or []
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise CompatError(503, '兼容预览流媒体状态异常，请稍后重试')
    return data


def _source(equipment_id):
    # Select only the exact binding, never source RTSP credentials or aliases.
    row = db.session.query(Equipment.id, Equipment.equipment_name,
                           Zlk_data.equipment_id.label('binding_owner'),
                           Zlk_data.zlk_app, Zlk_data.zlk_live).join(
        Zlk_data, Equipment.zlk_dat_id == Zlk_data.id).filter(
        Equipment.id == equipment_id,
        or_(Equipment.user_status == '1', Equipment.user_status.is_(None))).first()
    if row is None:
        raise CompatError(404, '该设备不存在、已禁用或未关联流媒体转发')
    if str(row.binding_owner) != str(row.id):
        raise CompatError(409, '该设备流媒体关联不一致，请检查流媒体管理')
    app = row.zlk_app or 'openUrl'
    stream = row.zlk_live
    if (app == APP or not isinstance(stream, str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', app)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', stream)):
        raise CompatError(409, '该设备未配置可用的流媒体转发')
    return row, app, stream


def _settings():
    config = _rows(_api('getServerConfig'))
    config = config[0] if config else {}
    template = config.get(COMMAND_KEY)
    # Refuse ZLK's fallback default command when the dedicated encoder is absent.
    if (not isinstance(template, str)
            or not re.search(r'-(?:c:v|vcodec)\s+libx264(?:\s|$)', template)
            or not re.search(r'(?:^|\s)-an(?:\s|$)', template) or 'yuv420p' not in template
            or str(config.get('protocol.enable_fmp4')) != '1'):
        raise CompatError(503, '平台尚未配置 H.264 兼容预览，请联系管理员')
    try:
        ports = [int(config[key]) for key in ('rtsp.port', 'rtmp.port')]
        if any(not 0 < port <= 65535 for port in ports):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise CompatError(503, '平台兼容预览端口配置无效')
    return ports


def _destination(equipment_id, ports):
    # FFmpeg runs inside ZLK's namespace; loopback never addresses the browser.
    return 'rtmp://127.0.0.1:{}/{}/{}'.format(ports[1], APP, equipment_id)


def _matching(media, app, stream):
    return [item for item in media
            if item.get('app') == app and item.get('stream') == str(stream)
            and item.get('vhost', '__defaultVhost__') == '__defaultVhost__']


def _ready(media, equipment_id):
    for item in _matching(media, APP, equipment_id):
        if item.get('schema') != 'fmp4':
            continue
        tracks = item.get('tracks') or []
        if any(track.get('codec_type') == 0 and track.get('ready') is True and
               str(track.get('codec_id_name', '')).upper() == 'H264'
               for track in tracks if isinstance(track, dict)):
            return True
    return False


def _gop(media, equipment_id):
    for item in _matching(media, APP, equipment_id):
        for track in item.get('tracks') or []:
            if isinstance(track, dict) and track.get('codec_type') == 0:
                interval = track.get('gop_interval_ms')
                if type(interval) in (int, float) and 0 < interval < 86400000:
                    return interval
    return None


def _readers(media, equipment_id):
    matching = _matching(media, APP, equipment_id)
    if not matching:
        return 0
    values = [item.get(key) for item in matching
              for key in ('totalReaderCount', 'readerCount')]
    values = [value for value in values if type(value) in (int, float) and value >= 0]
    # Unknown reader metadata must never cause a running preview to be stopped.
    return max(values) if values else None


def _state_key(equipment_id):
    return PREFIX + 'state:' + str(equipment_id)


def _leases_key(equipment_id):
    return PREFIX + 'leases:' + str(equipment_id)


def _state(client, equipment_id):
    try:
        value = json.loads(client.get(_state_key(equipment_id)) or '{}')
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _save_state(client, equipment_id, value):
    client.set(_state_key(equipment_id), json.dumps(value))
    client.sadd(INDEX_KEY, str(equipment_id))


def _live_leases(client, equipment_id, now):
    live = {}
    for token, encoded in client.hgetall(_leases_key(equipment_id)).items():
        try:
            item = json.loads(encoded)
            if isinstance(item, dict) and float(item.get('expires', 0)) > now:
                live[token] = item
                continue
        except (TypeError, ValueError):
            pass
        client.eval(_LEASE_COMPARE_DELETE, 1, _leases_key(equipment_id), token, encoded)
    return live


def _lease(client, equipment_id, owner):
    if len(_live_leases(client, equipment_id, time.time())) >= MAX_LEASES_PER_DEVICE:
        raise CompatError(429, '该设备兼容预览窗口已达到上限，请先关闭其他窗口')
    token = uuid.uuid4().hex
    client.hset(_leases_key(equipment_id), token,
                json.dumps({'owner': owner, 'expires': time.time() + LEASE_SECONDS}))
    client.expire(_leases_key(equipment_id), LEASE_SECONDS * 2)
    return token


def _pending():
    # No lease is allocated until the H264 output is confirmed ready.
    return {'code': 202, 'msg': '正在准备 H.264 兼容预览', 'retry_after_ms': 1000}


def _owned_sources(sources, ports):
    owned = {}
    pattern = re.compile(r'^rtmp://127\.0\.0\.1:{}/{}/([1-9][0-9]*)$'.format(ports[1], APP))
    for item in sources:
        destination = item.get('dst_url') or ''
        match = pattern.fullmatch(destination)
        if (match and item.get('key') == hashlib.md5(destination.encode()).hexdigest()
                and item.get('ffmpeg_cmd_key') == COMMAND_KEY):
            owned[int(match.group(1))] = item
    return owned


def _acquire(client):
    token = uuid.uuid4().hex
    return token if client.set(LOCK_KEY, token, nx=True, ex=LOCK_SECONDS) else None


def _unlock(client, token):
    try:
        client.eval(_RELEASE_LOCK, 1, LOCK_KEY, token)
    except redis.RedisError:
        pass  # TTL releases it without deleting a new worker's lock.


def _limit(client):
    # A fresh connection avoids a long-running camera-query transaction seeing
    # an old limit. MySQL is authoritative, so Redis restart cannot lose settings.
    with db.engine.connect() as connection:
        row = connection.execute(select(PreviewSettings.__table__.c.max_streams).where(
            PreviewSettings.__table__.c.id == 1)).first()
    saved = row[0] if row else None
    if saved is None:
        return MAX_STREAMS
    try:
        value = int(saved)
        if not MIN_STREAMS <= value <= HARD_MAX_STREAMS:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise CompatError(503, '兼容转码上限配置无效，请重新保存设置')


def compatibility_settings(limit=None):
    """One shared admission limit; lowering it never stops existing previews."""
    client, token = None, None
    try:
        client = _redis()
        if limit is not None:
            if type(limit) is not int or not MIN_STREAMS <= limit <= HARD_MAX_STREAMS:
                raise CompatError(400, '兼容转码最大路数必须是 1–8 的整数')
            token = _acquire(client)
            if token is None:
                raise CompatError(409, '转码任务正在更新，请稍后保存')
        current_limit = _limit(client) if limit is None else limit
        try:
            ports = _settings()
            used = len(_owned_sources(_rows(_api('listFFmpegSource')), ports))
        except CompatError:
            used = None  # The setting can still be read/saved while ZLK is unavailable.
        if limit is not None:
            table = PreviewSettings.__table__
            with db.engine.begin() as connection:
                exists = connection.execute(select(table.c.id).where(table.c.id == 1)).first()
                if exists:
                    connection.execute(table.update().where(table.c.id == 1).values(max_streams=limit))
                else:
                    connection.execute(table.insert().values(id=1, max_streams=limit))
            # Cached for inspection; admission always reads the durable database value.
            client.set(LIMIT_KEY, str(limit))
        return {'code': 200, 'msg': '已保存' if limit is not None else '获取成功',
                'data': {'max_streams': current_limit, 'min': MIN_STREAMS,
                         'max': HARD_MAX_STREAMS, 'active_streams': used}}
    except CompatError as exc:
        return {'code': exc.code, 'msg': exc.message}
    except redis.RedisError:
        return {'code': 503, 'msg': '兼容预览协调服务暂不可用，请稍后重试'}
    except SQLAlchemyError:
        return {'code': 503, 'msg': '兼容转码设置暂不可用，请稍后重试'}
    finally:
        if client is not None and token:
            _unlock(client, token)


def get_compatible_stream(equipment_id, owner):
    token = None
    client = None
    try:
        equipment_id = _device_id(equipment_id)
        row, app, stream = _source(equipment_id)
        client = _redis()
        token = _acquire(client)
        if token is None:
            return _pending()
        ports = _settings()
        media = _rows(_api('getMediaList'))
        if not any(item.get('schema') == 'rtsp' for item in _matching(media, app, stream)):
            raise CompatError(409, '原转发流当前不在线或未启用 RTSP，请检查流媒体管理')
        all_sources = _rows(_api('listFFmpegSource'))
        sources = _owned_sources(all_sources, ports)
        source_url = 'rtsp://127.0.0.1:{}/{}/{}'.format(ports[0], app, stream)
        destination = _destination(equipment_id, ports)
        source_hash = hashlib.sha256(source_url.encode()).hexdigest()
        state = _state(client, equipment_id)
        existing = sources.get(equipment_id)
        if not existing and any(item.get('dst_url') == destination for item in all_sources):
            raise CompatError(409, '兼容预览输出被其他流占用，请联系管理员')
        if existing and existing.get('src_url') != source_url:
            raise CompatError(409, '该监控点来源已变更，请关闭兼容预览后重试')
        if not existing:
            if _matching(media, APP, equipment_id):
                raise CompatError(409, '兼容预览输出被其他流占用，请联系管理员')
            limit = _limit(client)
            if len(sources) >= limit:
                raise CompatError(429, 'H.264 兼容转码已占用 {}/{} 路，请停止其他兼容窗口或在平台调高上限（最多 8 路）'.format(len(sources), limit))
            # Persist intent before the external call, so timeout/crash recovery
            # can adopt the one ZLK job with this deterministic destination.
            state = {'source_hash': source_hash, 'created': time.time(), 'key': None}
            _save_state(client, equipment_id, state)
            result = _api('addFFmpegSource', src_url=source_url, dst_url=destination,
                          timeout_ms=8000, enable_hls=0, enable_mp4=0,
                          ffmpeg_cmd_key=COMMAND_KEY)
            key = (result.get('data') or {}).get('key')
            if key != hashlib.md5(destination.encode()).hexdigest():
                raise CompatError(503, '兼容预览转码状态异常，请稍后重试')
            state['key'] = key
            _save_state(client, equipment_id, state)
            created = _owned_sources(_rows(_api('listFFmpegSource')), ports).get(equipment_id)
            if not created or created.get('src_url') != source_url:
                raise CompatError(409, '兼容预览输出关联异常，请联系管理员')
            media = _rows(_api('getMediaList'))
        else:
            state.setdefault('created', time.time())
            state.update(key=existing['key'], source_hash=source_hash)
            _save_state(client, equipment_id, state)
        if not _ready(media, equipment_id):
            return _pending()
        lease = _lease(client, equipment_id, owner)
        state['last_active'] = time.time()
        _save_state(client, equipment_id, state)
        urls = playback_urls(_base_url(), APP, str(equipment_id))
        data = {'id': equipment_id, 'name': row.equipment_name or '监控点 {}'.format(equipment_id),
                'codec': 'H264', 'online': True, 'available': True, 'reason': '',
                'keyframe_interval_ms': _gop(media, equipment_id), 'play_url': urls['mp4'],
                'urls': {'mp4': urls['mp4']}, 'lease_id': lease,
                'lease_ttl_seconds': LEASE_SECONDS}
        return {'code': 200, 'msg': 'H.264 兼容预览已就绪', 'data': data,
                'play_url': urls['mp4'], 'lease_id': lease, 'lease_ttl_seconds': LEASE_SECONDS}
    except CompatError as exc:
        return {'code': exc.code, 'msg': exc.message}
    except redis.RedisError:
        return {'code': 503, 'msg': '兼容预览协调服务暂不可用，请稍后重试'}
    except Exception:
        # Never log traceback/driver messages with connection credentials.
        logger.warning('兼容预览请求失败')
        return {'code': 503, 'msg': '兼容预览暂不可用，请稍后重试'}
    finally:
        if client is not None and token:
            _unlock(client, token)


def update_compat_lease(equipment_id, lease_id, owner, release=False):
    try:
        equipment_id = _device_id(equipment_id)
        if not isinstance(lease_id, str) or not re.fullmatch(r'[a-f0-9]{32}', lease_id):
            raise CompatError(400, '兼容预览租约无效')
        client = _redis()
        now = time.time()
        changed = client.eval(_LEASE_CHANGE, 1, _leases_key(equipment_id), lease_id,
                              owner, now, 'release' if release else 'renew',
                              now + LEASE_SECONDS, LEASE_SECONDS * 2)
        if changed == 0:
            return {'code': 200 if release else 410,
                    'msg': '已释放' if release else '兼容预览租约已到期，请重新播放'}
        if changed == -1:
            raise CompatError(403, '兼容预览租约不属于当前用户')
        return {'code': 200, 'msg': '已释放' if release else '已续期',
                'lease_ttl_seconds': LEASE_SECONDS}
    except CompatError as exc:
        return {'code': exc.code, 'msg': exc.message}
    except redis.RedisError:
        return {'code': 503, 'msg': '兼容预览协调服务暂不可用，请稍后重试'}


def reap_idle_compatible_streams():
    """Pure Redis/ZLK work: no Flask request context or database access."""
    client, token = None, None
    try:
        client = _redis()
        token = _acquire(client)
        if token is None:
            return 0
        ports = _settings()
        sources = _owned_sources(_rows(_api('listFFmpegSource')), ports)
        media = _rows(_api('getMediaList'))
        now, removed = time.time(), 0
        # At most four deletes per sweep keeps the global lock and HTTP work bounded.
        for equipment_id, source in sources.items():
            state = _state(client, equipment_id)
            if not state:
                _save_state(client, equipment_id, {'key': source['key'], 'created': now})
                continue  # Recover orphaned jobs with an initial reader grace period.
            if (_live_leases(client, equipment_id, now)
                    or now - state.get('last_active', state.get('created', now)) < IDLE_SECONDS):
                continue
            readers = _readers(media, equipment_id)
            if readers is None or readers > 0:
                continue
            _api('delFFmpegSource', key=source['key'])
            client.delete(_state_key(equipment_id), _leases_key(equipment_id))
            client.srem(INDEX_KEY, str(equipment_id))
            removed += 1
            if removed >= 4:
                break
        for raw_id in list(client.smembers(INDEX_KEY))[:100]:
            equipment_id = _device_id(raw_id)
            state = _state(client, equipment_id)
            if (equipment_id not in sources and not _live_leases(client, equipment_id, now)
                    and now - state.get('created', now) >= IDLE_SECONDS):
                client.delete(_state_key(equipment_id), _leases_key(equipment_id))
                client.srem(INDEX_KEY, raw_id)
        return removed
    except (CompatError, redis.RedisError, TypeError, ValueError):
        logger.warning('兼容预览回收暂不可用')
        return 0
    finally:
        if client is not None and token:
            _unlock(client, token)


def start_compat_reaper():
    global _THREAD
    with _THREAD_GUARD:
        if _THREAD is not None and _THREAD.is_alive():
            return
        def worker():
            while True:
                time.sleep(15)
                reap_idle_compatible_streams()
        _THREAD = threading.Thread(target=worker, name='preview-compat-reaper', daemon=True)
        _THREAD.start()
