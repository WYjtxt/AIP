"""Single supervised sender; web workers only enqueue and read status."""
from http.client import HTTPException
import json
import logging
import os
import signal
import socket
import ssl
import time
from urllib import error, request
import uuid

import push_outbox as outbox
from push_token_auth import TokenManager, TokenError

TOKENS = TokenManager()


class WorkerLock:
    def __init__(self):
        self.handle = None

    def __enter__(self):
        outbox.STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.handle = open(outbox.STATE_DIR / 'push-worker.lock', 'a+b')
        if os.name == 'nt':
            import msvcrt
            self.handle.seek(0)
            if not self.handle.read(1):
                self.handle.write(b'0')
                self.handle.flush()
            self.handle.seek(0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self.handle.close()
                raise RuntimeError('已有推送进程持有发送锁')
        else:
            import fcntl
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.handle.close()
                raise RuntimeError('已有推送进程持有发送锁')
        return self

    def __exit__(self, *args):
        if self.handle and not self.handle.closed:
            self.handle.close()


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _deliver_once(item):
    headers = outbox.request_headers(item, private=True)
    payload = outbox.prepared_request(item)
    req = request.Request(outbox.validate_target(item['target_url']), data=payload, headers=headers, method='POST')
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    item['receipt'] = {}
    private_auth = dict(item.get('auth') or {}, _runtime_secrets=item.get('_runtime_secrets', []))

    def capture(response):
        # Read one extra byte to distinguish a complete body from a bounded sample.
        # Even HTTPError responses can carry a useful, receiver-provided rejection reason.
        item['receipt'] = outbox.safe_receipt(response.headers, b'', private_auth)
        try:
            raw = response.read(outbox.MAX_RECEIPT_BYTES + 1)
            item['receipt'] = outbox.safe_receipt(response.headers, raw, private_auth)
        except (TimeoutError, OSError, HTTPException) as exc:
            partial = getattr(exc, 'partial', b'')
            item['receipt'] = outbox.safe_receipt(response.headers, partial if isinstance(partial, bytes) else b'',
                                                  private_auth, truncated=True)
            item['receipt']['capture_error'] = '接收端已返回状态码，但回执正文读取未完成；请核对接收端记录'

    try:
        with opener.open(req, timeout=item['timeout_seconds']) as response:
            status = response.status
            capture(response)
            # Some receivers return HTTP 200 for explicit authorization errors.
            # Recognize only these unambiguous refusal codes; arbitrary business
            # response formats still require the receiver's own confirmation.
            if 200 <= status < 300:
                try:
                    body = json.loads(item['receipt'].get('response_body', ''))
                except (ValueError, TypeError):
                    body = None
                if isinstance(body, dict) and str(body.get('code')) in ('401', '403'):
                    return status, '接收端拒绝报警（业务码 ' + str(body['code']) + '），请检查接收接口权限和推送鉴权配置', False
            return status, None if 200 <= status < 300 else '接收端返回 HTTP ' + str(status), status >= 500
    except error.HTTPError as exc:
        code = exc.code
        try:
            capture(exc)
        finally:
            exc.close()
        text = '接收端重定向已阻止' if 300 <= code < 400 else '接收端返回 HTTP ' + str(code)
        return code, text, code in (408, 425, 429) or code >= 500
    except (TimeoutError, socket.timeout):
        return None, '接收端请求超时', True
    except error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            message = '接收端 HTTPS 证书校验失败' if isinstance(exc.reason, ssl.SSLCertVerificationError) else '接收端 HTTPS 握手失败，请核对 HTTP/HTTPS 协议和 TLS 配置'
            return None, message, False
        return None, '无法连接接收端，请检查地址、端口及服务状态', True
    except ssl.SSLError:
        return None, '接收端 HTTPS 证书校验失败', False
    except (OSError, HTTPException):
        return None, '接收端连接中断，接收结果未知；重试时使用相同消息去重标识', True


def deliver(item):
    auth = item.get('auth') or {}
    automatic = auth.get('auth_mode') == 'auto_token'
    if automatic:
        try:
            item['_auto_token_value'] = TOKENS.get(auth, item['timeout_seconds'])
            item['_runtime_secrets'] = TOKENS.secrets(auth)
        except TokenError as exc:
            return None, str(exc), exc.retryable
    status, failure, retryable = _deliver_once(item)
    if automatic and failure and int(item.get('token_refreshes', 0)) < 1:
        try: body = json.loads(item.get('receipt', {}).get('response_body', ''))
        except (ValueError, TypeError): body = None
        if status == 401 or (isinstance(body, dict) and str(body.get('code')) == '401'):
            TOKENS.invalidate(auth, item['_auto_token_value'])
            item['_token_refresh_requested'] = True
            return status, '接收端报告 Token 失效，正在自动更新后重试（最多一次）', True
    return status, failure, retryable


def run(stop=None):
    stop = stop or (lambda: False)
    owner = uuid.uuid4().hex
    with WorkerLock():
        outbox.recover_abandoned(owner)
        last_prune = 0
        while not stop():
            try:
                outbox.worker_heartbeat(owner)
                item = outbox.claim_next(owner)
                if item:
                    status, failure, retryable = deliver(item)
                    outbox.finish_attempt(owner, item, status, failure, retryable)
                    outbox.worker_heartbeat(owner)
                else:
                    time.sleep(1)
                if time.monotonic() - last_prune > 3600:
                    outbox.prune_sent()
                    last_prune = time.monotonic()
            except Exception as exc:
                # A crash is safer than continuing with an unrecorded result. systemd restarts,
                # then recovery retries the durable row with the same idempotency key.
                logging.error('Push sender stopped safely (%s)', type(exc).__name__)
                try:
                    outbox.worker_heartbeat(owner, '发送进程异常，服务正在恢复')
                except Exception:
                    pass
                raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    stopping = [False]
    def handle_stop(*args):
        stopping[0] = True
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    run(lambda: stopping[0])
