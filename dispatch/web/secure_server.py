#!/usr/bin/env python3
"""Authenticated dispatch gateway. Production access is only through local TLS nginx."""
import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from security_auth import AuthStore, AuthError
from security_config import SecurityConfig, ConfigError


def load_legacy(path):
    spec=importlib.util.spec_from_file_location('dispatch_legacy',str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # platform-site-banner-v1
    master = Path(path).parent.parent / 'Config_files/platform-site.json'
    if master.is_file():
        notice = ('<div style="padding:12px;background:#eef5ff;color:#123f79">'
                  '统一网络配置已启用：IP 地址由 Config_files/platform-site.json 管理。'
                  '请到主平台“系统管理 → 统一IP配置”预览并应用。'
                  '本页仍可维护密码等其他配置。</div>')
        module.PAGE = module.PAGE.replace('<body>', '<body>' + notice, 1)
    return module


class DispatchServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=32
    allow_reuse_address=True

    def __init__(self,address,legacy,store,config,origin,assets,secure=True):
        super().__init__(address,Handler)
        self.auth=store
        self.config=config
        self.origin=origin.rstrip('/')
        self.host=urlparse(self.origin).netloc
        self.secure=secure
        self.assets=Path(assets)
        self.page=legacy.PAGE
        self.pre={}
        self.pre_attempts={}
        self.pre_lock=threading.RLock()
        self.capacity=threading.BoundedSemaphore(24)
        self.session_cookie='__Host-cfgp_session' if secure else 'cfgp_session'
        self.pre_cookie='__Host-cfgp_pre' if secure else 'cfgp_pre'

    def process_request(self,request,address):
        if not self.capacity.acquire(blocking=False):
            try:request.sendall(b'HTTP/1.0 503 Busy\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:request.close()
            return
        try:super().process_request(request,address)
        except Exception:
            self.capacity.release()
            raise

    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.capacity.release()


class Handler(BaseHTTPRequestHandler):
    server_version='ConfigDispatch/2.0'
    sys_version=''
    protocol_version='HTTP/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(12)

    def log_message(self,*args):
        # Deliberately omit URLs, query strings, headers and bodies from request logs.
        pass

    def _cookie(self,name):
        try:
            value=SimpleCookie(self.headers.get('Cookie','')).get(name)
            return value.value if value else ''
        except Exception:return ''

    def _set_cookie(self,name,value,max_age):
        return '%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict%s' % (name,value,max_age,'; Secure' if self.server.secure else '')

    def _send(self,body,code=200,content_type='application/json; charset=utf-8',headers=None):
        if isinstance(body,dict):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
        elif isinstance(body,str):body=body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        for key,value in headers or []:self.send_header(key,value)
        self.end_headers()
        self.wfile.write(body)

    def _html(self,page):
        nonce=secrets.token_urlsafe(24)
        page=re.sub(r'<(script|style)(?=[\s>])',lambda m:'<'+m[1]+' nonce="'+nonce+'"',page)
        policy="default-src 'none'; script-src 'self' 'nonce-%s'; script-src-attr 'none'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'" % nonce
        self._send(page,content_type='text/html; charset=utf-8',headers=[('Content-Security-Policy',policy)])

    def _boundary(self):
        if self.headers.get('Host','')!=self.server.host:
            raise AuthError('请求地址不匹配',400)
        if self.server.secure and (self.client_address[0]!='127.0.0.1' or self.headers.get('X-Forwarded-Proto')!='https'):
            raise AuthError('请通过 HTTPS 入口访问',403)

    def _ip(self):
        raw=self.headers.get('X-Real-IP','') if self.server.secure else self.client_address[0]
        try:return str(ipaddress.ip_address(raw))
        except ValueError:raise AuthError('请求来源无效',400)

    def _session(self,role=None):
        session=self.server.auth.get_session(self._cookie(self.server.session_cookie))
        if not session:raise AuthError('登录已失效，请重新登录',401)
        if role=='admin' and session['role']!='admin':raise AuthError('此操作需要管理员权限',403)
        if role=='write' and session['role'] not in ('admin','operator'):raise AuthError('只读账号不能修改配置',403)
        return session

    def _origin(self):
        if self.headers.get('Origin')!=self.server.origin:
            raise AuthError('请求来源校验失败',403)

    def _csrf(self,session):
        import hmac
        self._origin()
        supplied=self.headers.get('X-CSRF-Token','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',supplied) or not hmac.compare_digest(supplied,session['csrf']):
            raise AuthError('请求校验失败，请刷新页面',403)

    def _preauth(self):
        self._origin()
        token=self._cookie(self.server.pre_cookie)
        with self.server.pre_lock:
            entry=self.server.pre.get(hashlib.sha256(token.encode()).hexdigest())
            if not entry or entry['expires']<time.time() or entry['ip']!=self._ip():
                raise AuthError('登录页面已失效，请刷新',403)
            self._csrf(entry)
            now=time.time()
            ip=self._ip()
            self.server.pre_attempts={k:[t for t in v if now-t<900] for k,v in self.server.pre_attempts.items() if any(now-t<900 for t in v)}
            attempts=self.server.pre_attempts.setdefault(ip,[])
            if len(attempts)>=30:raise AuthError('请求过于频繁，请稍后重试',429)
            attempts.append(now)

    def _body(self):
        if self.headers.get('Transfer-Encoding') or self.headers.get_content_type()!='application/json':
            raise AuthError('仅接受 JSON 请求',415)
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:raise AuthError('请求长度无效',400)
        if not 0<length<=65536:raise AuthError('请求体过大或为空',413)
        try:
            value=json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError,UnicodeError):raise AuthError('请求体格式错误',400)

    def _error(self,error):
        if isinstance(error,(AuthError,ConfigError)):
            self._send({'ok':False,'error':str(error)},error.status)
        else:
            self._send({'ok':False,'error':'服务处理失败，请联系管理员查看审计记录'},500)

    def do_GET(self):
        try:
            path=urlparse(self.path).path
            if path=='/healthz' and self.client_address[0]=='127.0.0.1':
                self._send({'ok':True,'version':'2.0.0'})
                return
            self._boundary()
            if path=='/login':
                self._html((self.server.assets/'login.html').read_text(encoding='utf-8'))
                return
            if path=='/api/auth/status':
                with self.server.pre_lock:
                    now=time.time()
                    self.server.pre={k:v for k,v in self.server.pre.items() if v['expires']>now}
                    token=self._cookie(self.server.pre_cookie)
                    key=hashlib.sha256(token.encode()).hexdigest()
                    entry=self.server.pre.get(key)
                    ip=self._ip()
                    if not entry or entry['ip']!=ip:
                        if sum(item['ip']==ip for item in self.server.pre.values())>=32:
                            raise AuthError('此来源的登录请求过于频繁，请稍后重试',429)
                        if len(self.server.pre)>=2048:
                            self.server.pre.pop(min(self.server.pre,key=lambda k:self.server.pre[k]['expires']))
                        token=secrets.token_urlsafe(32)
                        entry={'csrf':secrets.token_urlsafe(32),'expires':now+900,'ip':ip}
                        self.server.pre[hashlib.sha256(token.encode()).hexdigest()]=entry
                self._send({'initialized':self.server.auth.status(),'csrf':entry['csrf']},headers=[('Set-Cookie',self._set_cookie(self.server.pre_cookie,token,900))])
                return
            if path in ('/assets/security-ui.js','/assets/security-ui.css'):
                file=self.server.assets/path.rsplit('/',1)[1]
                self._send(file.read_bytes(),content_type='text/javascript; charset=utf-8' if file.suffix=='.js' else 'text/css; charset=utf-8')
                return
            if path in ('/','/index.html'):
                try:self._session()
                except AuthError:
                    self._send(b'',302,headers=[('Location','/login')])
                    return
                page=self.server.page
                page=page.replace('</head>','<link rel="stylesheet" href="/assets/security-ui.css"></head>')
                page=page.replace('<script>','<script src="/assets/security-ui.js"></script><script>',1)
                page=re.sub(r' on(click|input|change)="([^"]*)"',lambda m:' data-dispatch-'+m[1]+'="'+m[2]+'"',page)
                wiring='''document.addEventListener('DOMContentLoaded',function(){
document.querySelectorAll('[data-dispatch-click]').forEach(function(el){el.addEventListener('click',function(){var a=el.dataset.dispatchClick;var f={"genSecret()":function(){window.genSecret();},"syncPrimary()":function(){window.syncPrimary();},"selAll(true)":function(){window.selAll(true);},"selAll(false)":function(){window.selAll(false);},"go('preview')":function(){window.go('preview');},"go('apply')":function(){window.go('apply');}};if(f[a])f[a]();});});
document.querySelectorAll('[data-dispatch-input]').forEach(function(el){el.addEventListener('input',function(){window.onPrimaryInput();});});
document.querySelectorAll('[data-dispatch-change]').forEach(function(el){el.addEventListener('change',function(){window.onPrimaryInput();});});
});'''
                page=page.replace('</body>','<script>'+wiring+'</script></body>')
                self._html(page)
                return
            session=self._session('admin' if path in ('/api/users','/api/audit') else None)
            if path=='/api/auth/me':
                self._send({k:session[k] for k in ('username','role','csrf')})
            elif path=='/api/state':
                state=self.server.config.state()
                state['version']='2.0.0'
                self._send(state)
            elif path=='/api/users':self._send({'users':self.server.auth.list_users()})
            elif path=='/api/audit':self._send({'events':self.server.auth.recent_audit(100)})
            else:self._send({'ok':False,'error':'接口不存在'},404)
        except Exception as error:self._error(error)

    def do_POST(self):
        path=urlparse(self.path).path
        session=None
        try:
            self._boundary()
            if path in ('/api/auth/login','/api/auth/bootstrap'):
                self._preauth()
                payload=self._body()
                if path.endswith('/bootstrap'):
                    if payload.get('username')!='admin':raise AuthError('首位管理员用户名为 admin',400)
                    self.server.auth.bootstrap(payload.get('token'),payload.get('username'),payload.get('password'))
                token,info=self.server.auth.login(payload.get('username'),payload.get('password'),self._ip())
                # Re-login always discards this browser's previous session.
                old=self._cookie(self.server.session_cookie)
                if old:self.server.auth.logout(old)
                headers=[('Set-Cookie',self._set_cookie(self.server.session_cookie,token,8*3600)),('Set-Cookie',self._set_cookie(self.server.pre_cookie,'',0))]
                self._send({'ok':True,'username':info['username'],'role':info['role']},headers=headers)
                return
            role='admin' if path=='/api/users' else 'write' if path in ('/api/preview','/api/apply') else None
            session=self._session(role)
            self._csrf(session)
            payload=self._body()
            if path=='/api/auth/logout':
                self.server.auth.logout(self._cookie(self.server.session_cookie))
                self._send({'ok':True},headers=[('Set-Cookie',self._set_cookie(self.server.session_cookie,'',0))])
            elif path=='/api/auth/password':
                self.server.auth.change_password(session,payload.get('old_password'),payload.get('new_password'))
                self._send({'ok':True},headers=[('Set-Cookie',self._set_cookie(self.server.session_cookie,'',0))])
            elif path=='/api/users':
                self.server.auth.save_user(session,payload.get('username'),payload.get('role'),payload.get('password') or None,payload.get('disabled',False))
                self._send({'ok':True})
            elif path=='/api/preview':
                result=self.server.config.preview(payload,session['id'])
                self.server.auth.audit(session,self._ip(),'preview',{'files':[r['path'] for r in result['results']],'changed':sum(r['changed'] for r in result['results'])})
                self._send(result)
            elif path=='/api/apply':
                self.server.auth.audit(session,self._ip(),'apply_started',{'status':'started'})
                result=self.server.config.apply(payload,session['id'])
                try:self.server.auth.audit(session,self._ip(),'apply',{'files':[r['path'] for r in result.get('results',[])],'applied':result.get('applied',0),'backup':result.get('backup')})
                except Exception:
                    result['audit_warning']=True
                    result['note']='配置操作已完成，但结果审计保存失败，请联系管理员核查'
                self._send(result)
            else:self._send({'ok':False,'error':'接口不存在'},404)
        except Exception as error:
            if session and path in ('/api/preview','/api/apply'):
                try:self.server.auth.audit(session,self._ip(),'operation_rejected',{'operation':path.rsplit('/',1)[-1],'status':getattr(error,'status',500)})
                except Exception:pass
            self._error(error)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--settings',type=Path,required=True)
    parser.add_argument('--http-test',action='store_true')
    args=parser.parse_args()
    settings=json.loads(args.settings.read_text(encoding='utf-8'))
    os.umask(0o077)
    here=Path(__file__).resolve().parent
    legacy=load_legacy(settings.get('legacy',here/'config_dispatch.py'))
    auth=AuthStore(settings['auth_db'])
    config=SecurityConfig(legacy,settings['allowed_paths'],Path(settings['backup_root']),data_root=Path(settings.get('data_root','/data/AIGO/platform_start')),strict_permissions=settings.get('strict_permissions',True))
    server=DispatchServer(('127.0.0.1',int(settings.get('port',18999))),legacy,auth,config,settings['origin'],here,secure=not args.http_test)
    try:server.serve_forever(poll_interval=.5)
    finally:server.server_close()


if __name__=='__main__':main()
