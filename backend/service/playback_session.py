"""Ownership for the existing single temporary-replay worker in Redis DB 3.

Persistent AI tasks and archived files do not use this protocol. A second
browser cannot replace or stop the current replay. The worker acknowledges
termination before the slot is released.
"""
import json
import re
import time

SESSION_KEY = 'ai-monitor:temporary-playback:v1'
HEARTBEAT_KEY = SESSION_KEY + ':worker'
CANCEL_PREFIX = SESSION_KEY + ':closed:'
LEASE_SECONDS = 90

_INSPECT = r'''
local function reply(code, msg) return cjson.encode({code=code,msg=msg}) end
if redis.call('exists',KEYS[5]) == 1 then return reply(410,'此回放会话已取消或结束，请重新打开') end
if redis.call('exists',KEYS[4]) == 0 then return reply(503,'临时回放服务未就绪，可查看已有存档录像或报警图片') end
local old = redis.call('get',KEYS[1])
if old then
  local ok,state = pcall(cjson.decode,old)
  if not ok then return reply(503,'回放会话状态异常，请联系管理员核查') end
  if state.token == ARGV[1] and state.owner == ARGV[2] then
    if state.status == 'running' and tonumber(state.expires_at) > tonumber(ARGV[3]) then return cjson.encode(state.reply) end
    if state.status == 'pending' then return reply(202,'正在准备临时回放') end
    return reply(410,'此回放会话正在结束，请重新打开')
  end
  if state.status == 'stopping' then return reply(202,'上一段回放正在停止') end
  return reply(409,'临时回放正在被另一页面使用，请等待该页面结束回放')
end
local flag = redis.call('get',KEYS[3])
if flag == '1' or flag == '2' or flag == '3' then return reply(202,'上一段回放正在清理，请稍后重试') end
'''
_DISPATCH = _INSPECT + r'''
redis.call('set',KEYS[1],ARGV[4])
redis.call('set',KEYS[2],ARGV[5])
redis.call('set',KEYS[3],'1')
return reply(202,'正在准备临时回放')
'''

_STOP = r'''
local raw = redis.call('get',KEYS[1])
if not raw then
  redis.call('set',KEYS[3],ARGV[1], 'EX', 180)
  return 0
end
local ok,state = pcall(cjson.decode,raw)
if not ok then return -2 end
if state.token ~= ARGV[1] then
  redis.call('set',KEYS[3],ARGV[1], 'EX', 180)
  return -1
end
if state.owner ~= ARGV[2] then return -1 end
redis.call('set',KEYS[3],ARGV[1], 'EX', 180)
state.status = 'stopping'
redis.call('set',KEYS[1],cjson.encode(state))
redis.call('set',KEYS[2],'3')
return 1
'''

_KEEPALIVE = r'''
local raw = redis.call('get',KEYS[1])
if not raw then return 0 end
local ok,state = pcall(cjson.decode,raw)
if not ok then return 0 end
if state.token ~= ARGV[1] or state.owner ~= ARGV[2] then return 0 end
if (state.status ~= 'running' and state.status ~= 'pending') or tonumber(state.expires_at) <= tonumber(ARGV[3]) then return 0 end
state.expires_at = tonumber(ARGV[4])
redis.call('set',KEYS[1],cjson.encode(state))
return 1
'''


def _credentials(token, owner):
    return (isinstance(token, str) and re.fullmatch(r'[a-f0-9]{64}', token)
            and isinstance(owner, str) and bool(owner.strip()))


def _client():
    from data.video_data import get_redis
    return get_redis(3)


def inspect_temporary_playback(token, owner):
    """Read existing state before camera/DB work; dispatch repeats it atomically."""
    if not _credentials(token, owner):
        return {'code': 409, 'msg': '此页面缺少有效回放会话，请刷新平台后重新打开'}
    try:
        value = _client().eval(_INSPECT + "return reply(201,'ready')", 5,
                               SESSION_KEY, 'video_data_list', 'stream_data_flag',
                               HEARTBEAT_KEY, CANCEL_PREFIX + token, token, owner, time.time())
        result = json.loads(value)
        return None if result['code'] == 201 else result
    except Exception:
        return {'code': 503, 'msg': '临时回放协调服务暂不可用，请稍后重试'}


def dispatch_temporary_playback(data_list, token, owner):
    if not _credentials(token, owner):
        return {'code': 409, 'msg': '此页面缺少有效回放会话，请刷新平台后重新打开'}
    reply = {'code': 200, 'msg': '回放服务已启动', 'flv_data': data_list,
             'session_token': token, 'lease_seconds': LEASE_SECONDS}
    state = {'token': token, 'owner': owner, 'status': 'pending',
             'expires_at': time.time() + LEASE_SECONDS, 'reply': reply}
    try:
        value = _client().eval(_DISPATCH, 5, SESSION_KEY, 'video_data_list',
                               'stream_data_flag', HEARTBEAT_KEY, CANCEL_PREFIX + token,
                               token, owner, time.time(), json.dumps(state), str(data_list))
        return json.loads(value)
    except Exception:
        return {'code': 503, 'msg': '临时回放协调服务暂不可用，请稍后重试'}


def stop_temporary_playback(token, owner):
    if not _credentials(token, owner):
        return {'code': 409, 'msg': '未提供有效的回放会话，未停止任何视频'}
    try:
        result = _client().eval(_STOP, 3, SESSION_KEY, 'stream_data_flag',
                                CANCEL_PREFIX + token, token, owner)
        if result < 0:
            return {'code': 409, 'msg': '此页面不持有当前回放，未停止其他页面的视频'}
        return {'code': 200, 'msg': '本页面回放已关闭', 'video_type': '视频分析停止'}
    except Exception:
        return {'code': 503, 'msg': '回放关闭请求未确认，请稍后重试'}


def keep_temporary_playback(token, owner):
    if not _credentials(token, owner):
        return {'code': 410, 'msg': '回放会话无效或已结束'}
    try:
        now = time.time()
        active = _client().eval(_KEEPALIVE, 1, SESSION_KEY, token, owner, now,
                                now + LEASE_SECONDS)
        return {'code': 200 if active else 410, 'msg': '回放中' if active else '回放会话已结束'}
    except Exception:
        return {'code': 503, 'msg': '回放续期暂不可用'}
