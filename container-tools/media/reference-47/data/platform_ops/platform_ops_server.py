"""Loopback-only privileged maintenance facade. Browser access uses platform JWT."""
import hmac
import json
import os
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', '/data/platform_ops/state'))
CONFIG = Path(os.environ.get('PLATFORM_OPS_SERVER_CONFIG', '/data/platform_ops/server.json'))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass  # URLs and request payloads may contain configuration information.

    def reply(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)
        if self.command == 'POST' and not self.path.endswith('/chunk') and status != 403:
            record = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'method': self.command,
                      'path': urlsplit(self.path).path, 'actor': unquote(self.headers.get('X-Platform-Actor', 'unknown'))[:80],
                      'status': status, 'code': body.get('code')}
            try:
                with (STATE / 'audit.jsonl').open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            except OSError:
                pass

    def execute(self):
        self.close_connection = True
        self.connection.settimeout(45)
        supplied = self.headers.get('X-Platform-Ops-Key', '')
        expected = self.server.ops_key
        if not supplied or not hmac.compare_digest(supplied, expected):
            self.reply(403, {'code': 403, 'msg': '维护服务认证失败'})
            return
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 5 * 1024 * 1024:
                raise ValueError('请求内容过大')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('请求未传输完整')
            if path.startswith('/upgrade/uploads/') and path.endswith('/chunk'):
                import upgrade_operations
                status, result = upgrade_operations.upload_chunk(
                    path.split('/')[3], self.headers.get('X-Upload-Offset'), raw)
            else:
                body = json.loads(raw.decode('utf-8')) if raw else {}
                if not isinstance(body, dict):
                    raise ValueError('请求必须为JSON对象')
                if path == '/health':
                    status, result = 200, {'code': 200, 'data': {'service': 'platform-ops', 'version': '20261020'}}
                elif path.startswith('/push/'):
                    import push_operations
                    status, result = push_operations.dispatch(self.command, self.path, body)
                elif path == '/storage' or path.startswith('/storage/'):
                    import storage_operations
                    lock = None
                    try:
                        if self.command == 'POST':
                            import upgrade_operations
                            lock = upgrade_operations.acquire()
                        status, result = storage_operations.dispatch(self.command, path, body)
                    finally:
                        if lock:
                            lock.close()
                elif path.startswith('/upgrade/'):
                    import upgrade_operations
                    status, result = upgrade_operations.dispatch(self.command, path, body)
                else:
                    status, result = 404, {'code': 404, 'msg': '维护操作不存在'}
            self.reply(status, result)
        except (ValueError, KeyError) as exc:
            self.reply(400, {'code': 400, 'msg': str(exc)[:300]})
        except Exception:
            self.reply(500, {'code': 500, 'msg': '维护操作失败，请查看维护服务记录'})

    do_GET = execute
    do_POST = execute


def main():
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    settings = json.loads(CONFIG.read_text())
    key = settings['key']
    if not isinstance(key, str) or len(key) < 48:
        raise RuntimeError('Invalid maintenance key')
    import upgrade_operations
    upgrade_operations.recover_interrupted_jobs()
    server = ThreadingHTTPServer(('127.0.0.1', 9011), Handler)
    server.ops_key = key
    server.serve_forever()


if __name__ == '__main__':
    main()
