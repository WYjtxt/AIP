"""Routes called by the authenticated host operations bridge."""
import logging
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
import uuid

import push_outbox as outbox


def dispatch(method, path, body=None):
    parsed = urlsplit(path)
    path = parsed.path
    try:
        if method == 'GET' and path == '/push/status':
            return 200, {'code': 200, 'msg': '', 'data': outbox.snapshot()}
        match = re.fullmatch(r'/push/deliveries/([1-9][0-9]{0,18})', path)
        if method == 'GET' and match:
            query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=4)
            if set(query) - {'before_attempt_id', 'limit'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('详情查询参数不正确')
            before = query.get('before_attempt_id', [None])[0]
            if before is not None:
                if not re.fullmatch(r'[1-9][0-9]{0,18}', before):
                    raise ValueError('历史记录游标必须为正整数')
                before = int(before)
            limit = query.get('limit', ['10'])[0]
            if not re.fullmatch(r'[1-9][0-9]?', limit):
                raise ValueError('每页尝试记录数量必须为 1 至 10 的整数')
            data = outbox.delivery_details(int(match[1]), before, int(limit))
            return 200, {'code': 200, 'msg': '', 'data': data}
        if method == 'POST' and path == '/push/settings':
            data = outbox.save_settings(body)
            return 200, {'code': 200, 'msg': '推送配置已保存，新消息使用当前配置', 'data': data}
        if method == 'POST' and path == '/push/retry':
            data = outbox.retry_failed(body)
            return 200, {'code': 200, 'msg': '失败记录已按当前地址和鉴权重新排队', 'data': data}
        if method == 'POST' and path == '/push/delete':
            data = outbox.delete_failed(body)
            return 200, {'code': 200, 'msg': '所选推送记录已处理', 'data': data}
        if method == 'POST' and path == '/push/test':
            if body not in ({}, None):
                raise ValueError('测试推送只使用已保存的配置')
            snapshot = outbox.snapshot()
            if not snapshot['settings']['enabled']:
                raise ValueError('请先启用推送并保存配置，再发送测试数据')
            if not snapshot['worker']['healthy']:
                raise ValueError('发送服务未就绪，请先检查服务状态')
            event_key = 'test:' + uuid.uuid4().hex
            payload = {'platform_test': True, 'eventType': 'platform.push.test',
                       'alarmTypeName': '平台数据推送测试', 'deviceName': '平台测试',
                       'alarmTime': time.strftime('%Y-%m-%d %H:%M:%S'), 'testId': event_key}
            data = outbox.enqueue(payload, event_key, 'test')
            return 200, {'code': 200, 'msg': '测试数据已进入发送队列，请查看发送记录', 'data': data}
        return 404, {'code': 404, 'msg': '接口不存在'}
    except outbox.Conflict as exc:
        return 409, {'code': 409, 'msg': str(exc)}
    except outbox.NotFound as exc:
        return 404, {'code': 404, 'msg': str(exc)}
    except ValueError as exc:
        return 400, {'code': 400, 'msg': str(exc)}
    except outbox.OutboxError as exc:
        return 507, {'code': 507, 'msg': str(exc)}
    except (sqlite3.Error, OSError) as exc:
        logging.error('Push operation storage failure (%s)', type(exc).__name__)
        return 503, {'code': 503, 'msg': '推送存储不可用，请检查磁盘和发送服务'}
