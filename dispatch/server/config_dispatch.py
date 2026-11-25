#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置信息派发工具（单文件 Web 服务，仅用标准库）

功能：
  1. 自动探测本机可用 IP（排除 127.0.0.1，标注默认路由网卡）
  2. 自动寻找 Config_files / model_algorithm_package / bingxing_model 三处目录
  3. 读取各文件当前值填入表单，可一次性批量改写 IP / 数据库 / Redis / Kafka / ZLK
  4. zlk/config.ini 的 secret 可随机生成，并同步到所有引用它的文件
  5. 写入前自动备份；支持「预览变更」先看 diff

安全约定：
  - 保留每个文件原有的编码（UTF-8 / GBK）与换行符，只替换值本身
  - [VerifiedStreamSources] 等非本机字段不动
  - 任何写入前先整目录备份到 CFGP_BACKUP
"""
import base64
import difflib
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION = '1.0.1'
PORT = int(os.environ.get('CFGP_PORT', '8899'))
BACKUP_ROOT = Path(os.environ.get('CFGP_BACKUP', '/data/AIGO/platform_start/cfgp_backups'))
AUTH_TOKEN = os.environ.get('CFGP_TOKEN', '').strip()
SEARCH_ROOTS = [p for p in os.environ.get(
    'CFGP_ROOTS', '/data/AIGO/platform_start /opt /home /srv /mnt /root /usr/local').split() if p]
MAX_DEPTH = 7

# --------------------------------------------------------------------------
# 目标文件登记：文件夹类型 -> 文件相对路径与处理方式
# --------------------------------------------------------------------------
DIR_KINDS = {
    'Config_files': [
        ('app_ini', 'config.ini', '应用配置 config.ini'),
        ('config_js', 'config.js', '前端配置 config.js'),
        ('zlk_ini', os.path.join('zlk', 'config.ini'), 'ZLMediaKit zlk/config.ini'),
    ],
    'model_algorithm_package': [
        ('conf_files', 'Conf_files.py', 'Conf_files.py'),
        ('model_ai', 'model_ai.py', 'model_ai.py'),
        ('huawei_resource', 'Huawei_resource.py', 'Huawei_resource.py'),
        ('kafka_consumer', 'kafka_consumer.py', 'kafka_consumer.py'),
    ],
    'bingxing_model': [
        ('api_ini', os.path.join('config', 'ApiConfig.ini'), 'config/ApiConfig.ini'),
    ],
}

DIR_KINDS['platform_algorithm_start'] = DIR_KINDS['bingxing_model']

# 逻辑字段 -> 中文标签（表单用）
# 注意：primary_ip 不在这里 —— 它由第 1 节的「主 IP」输入框单独承载，
#       重复列出会出现两个输入框各显示一个值、联动只更新一个的困惑。
FIELDS = [
    ('db_host', '数据库 IP', 'MySQL 主机'),
    ('db_port', '数据库端口', ''),
    ('db_user', '数据库用户', ''),
    ('db_password', '数据库密码', ''),
    ('db_name', '数据库名', ''),
    ('redis_ip', 'Redis IP', ''),
    ('redis_port', 'Redis 端口', ''),
    ('redis_password', 'Redis 密码', ''),
    ('kafka_ip', 'Kafka IP', ''),
    ('kafka_port', 'Kafka 端口', ''),
    ('zlk_ip', 'ZLK IP', '流媒体服务地址'),
    ('zlk_port', 'ZLK 端口', ''),
    ('zlk_secret', 'ZLK secret', '三处文件必须一致，可随机生成'),
    ('box_ip', '算力盒子 IP', ''),
    ('box_user', '盒子用户', ''),
    ('box_password', '盒子密码', ''),
    ('upload_ip', '上传服务 IP', ''),
    ('upload_port', '上传服务端口', ''),
    ('stream_push_ip', '推流目标 IP', ''),
    # aifz_ip 必须在这里，否则表单不提交该字段，
    # config.ini 的 [aicam] remote_ip / AIFZ_HOST 永远改不到
    ('aifz_ip', 'AIFZ IP', 'config.ini [aicam] remote_ip / AIFZ_HOST'),
    ('platform_port', '平台端口', 'config.ini [aicam] remote_port'),
    ('aifz_port', 'AIFZ 端口', 'config.ini [aicam] AIFZ_PORT'),
]

# 指向本机的 IP 类字段：这些在「跟随主 IP」时应当一起变
IP_LIKE_FIELDS = ('db_host', 'redis_ip', 'kafka_ip', 'zlk_ip', 'box_ip',
                  'upload_ip', 'stream_push_ip', 'aifz_ip')

# INI 类文件：kind -> [(逻辑字段, section, key)]
INI_SCHEMA = {
    'app_ini': [
        ('db_host', 'database', 'DB_HOST'), ('db_user', 'database', 'DB_USER'),
        ('db_port', 'database', 'DB_PORT'), ('db_password', 'database', 'DB_PASSWORD'),
        ('db_name', 'database', 'DB_NAME'),
        ('redis_ip', 'redis', 'Redis_ip'), ('redis_port', 'redis', 'Redis_port'),
        ('redis_password', 'redis', 'Redis_password'),
        ('box_ip', 'box_ip', 'Box_ip'), ('box_user', 'box_ip', 'Box_user'),
        ('box_password', 'box_ip', 'Box_password'),
        ('zlk_ip', 'ZLK', 'ZLK_HOST'), ('zlk_port', 'ZLK', 'ZLK_PORT'),
        ('zlk_secret', 'ZLK', 'ZLK_SECRET'),
        ('aifz_ip', 'aicam', 'remote_ip'), ('platform_port', 'aicam', 'remote_port'),
        ('aifz_ip', 'aicam', 'AIFZ_HOST'), ('aifz_port', 'aicam', 'AIFZ_PORT'),
    ],
    'zlk_ini': [('zlk_secret', 'api', 'secret')],
    'api_ini': [
        ('db_host', 'ipconfig', 'db_host'), ('db_user', 'ipconfig', 'db_user'),
        ('db_port', 'ipconfig', 'db_port'), ('db_password', 'ipconfig', 'db_password'),
        ('db_name', 'ipconfig', 'db_name'),
        ('kafka_ip', 'ipconfig', 'kafka_ip'), ('kafka_port', 'ipconfig', 'kafka_port'),
        ('primary_ip', 'ipconfig', 'localhost_ip'),
        ('upload_ip', 'ipconfig', 'upload_ip'), ('upload_port', 'ipconfig', 'upload_port'),
        ('stream_push_ip', 'ipconfig', 'stream_push_ip'),
    ],
}
# app_ini 里 remote_ip 与 AIFZ_HOST 都取 aifz_ip（同一值写两处），已在上面列出
# 永不改写的 section
SKIP_SECTIONS = {'VerifiedStreamSources'}

# 需要重启的服务（改完后提示 / 可选执行）
RESTART_HINT = {
    'app_ini': ['重启平台服务（docker 容器 seal_system / seal_system_vue）'],
    'config_js': ['浏览器强刷即可（config.js 是前端脚本）'],
    'zlk_ini': ['docker restart zlk'],
    'conf_files': ['systemctl restart model_start'],
    'model_ai': ['systemctl restart model_start'],
    'huawei_resource': ['systemctl restart Huawei_resource（若独立运行）'],
    'kafka_consumer': ['systemctl restart kafka_consumer'],
    'api_ini': ['systemctl restart model_start'],
}


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def detect_ips():
    """返回 [{iface, ip, primary, note}]，排除回环。"""
    out = []
    try:
        raw = subprocess.run(['ip', '-4', '-o', 'addr', 'show'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=10).stdout.decode('utf-8', 'replace')
        for line in raw.splitlines():
            m = re.match(r'\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', line)
            if not m:
                continue
            iface, ip = m.group(1), m.group(2)
            if ip.startswith('127.'):
                continue
            out.append({'iface': iface, 'ip': ip, 'prefix': int(m.group(3))})
    except Exception:
        pass
    if not out:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if not ip.startswith('127.'):
                out.append({'iface': '?', 'ip': ip, 'prefix': 0})
        except Exception:
            pass
    # 默认路由网卡
    default_iface = ''
    try:
        route = subprocess.run(['ip', 'route', 'show', 'default'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=10).stdout.decode('utf-8', 'replace')
        m = re.search(r'dev\s+(\S+)', route)
        if m:
            default_iface = m.group(1)
    except Exception:
        pass
    for item in out:
        item['primary'] = (item['iface'] == default_iface)
        if re.match(r'^(docker|br-|veth|virbr)', item['iface']):
            item['note'] = '容器网卡'
        elif item['primary']:
            item['note'] = '默认路由网卡'
        else:
            item['note'] = ''
    out.sort(key=lambda x: (not x['primary'], x['iface']))
    return out


def read_text(path):
    """按原编码读取，返回 (文本, 编码)。"""
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode('utf-8-sig'), 'utf-8-sig'
    for enc in ('utf-8', 'gbk', 'gb18030', 'latin-1'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1'), 'latin-1'


def write_text(path, text, encoding):
    """按原编码写回；utf-8-sig 会自动补 BOM。保留权限与属主，时间戳更新为当前。"""
    data = text.encode(encoding)
    tmp = path.with_name(path.name + '.cfgp-tmp')
    with open(tmp, 'wb') as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        shutil.copymode(path, tmp)
    except OSError:
        pass
    try:
        st = path.stat()
        os.chown(tmp, st.st_uid, st.st_gid)
    except (OSError, AttributeError):
        pass
    os.replace(tmp, path)


_DISCOVER_CACHE = {'ts': 0.0, 'data': None}
_CACHE_TTL = 60.0
PRUNE_DIRS = {'__pycache__', 'node_modules', '.git', 'proc', 'sys', 'dev',
              'results', 'snapshots', 'videos', 'log', 'logs', 'venv', '.venv',
              'backups', '.validation', 'datasets', 'output', 'model'}


def discover(force=False):
    """寻找三类目录（60 秒缓存，避免每次刷新页面都全盘遍历）。"""
    now = time.time()
    if not force and _DISCOVER_CACHE['data'] is not None and now - _DISCOVER_CACHE['ts'] < _CACHE_TTL:
        return _DISCOVER_CACHE['data']
    found = []
    seen = set()
    for root in SEARCH_ROOTS:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        base_depth = len(root_path.parts)
        for dirpath, dirnames, _ in os.walk(root_path):
            cur = Path(dirpath)
            if len(cur.parts) - base_depth > MAX_DEPTH:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames
                           if d not in PRUNE_DIRS and not d.startswith('.')]
            name = cur.name
            if name not in DIR_KINDS:
                continue
            key = str(cur.resolve())
            if key in seen:
                continue
            seen.add(key)
            files = []
            for fkey, rel, label in DIR_KINDS[name]:
                fpath = cur / rel
                files.append({'key': fkey, 'rel': rel, 'label': label,
                              'path': str(fpath), 'exists': fpath.is_file()})
            found.append({'kind': name, 'path': str(cur), 'files': files})
    order = {'Config_files': 0, 'model_algorithm_package': 1, 'bingxing_model': 2}
    found.sort(key=lambda x: (order.get(x['kind'], 9), x['path']))
    _DISCOVER_CACHE['ts'] = now
    _DISCOVER_CACHE['data'] = found
    return found


# --------------------------------------------------------------------------
# INI 值替换（保留原格式与换行）
# --------------------------------------------------------------------------
def ini_get(text, section, key):
    cur = None
    for line in re.split(r'(?<=\n)', text):
        body = line.rstrip('\r\n')
        m = re.match(r'^\s*\[(.+?)\]\s*$', body)
        if m:
            cur = m.group(1).strip()
            continue
        if cur != section:
            continue
        if body.lstrip().startswith(('#', ';')):
            continue
        m2 = re.match(r'^\s*' + re.escape(key) + r'\s*[=:]\s*(.*?)\s*$', body)
        if m2:
            return m2.group(1)
    return None


def ini_set(text, section, key, value):
    """只替换值的部分，其余字节保持不变。返回 (新文本, 是否改动)。"""
    if section in SKIP_SECTIONS:
        return text, False
    out, cur, changed = [], None, False
    for line in re.split(r'(?<=\n)', text):
        eol = ''
        body = line
        if body.endswith('\r\n'):
            body, eol = body[:-2], '\r\n'
        elif body.endswith('\n'):
            body, eol = body[:-1], '\n'
        m = re.match(r'^\s*\[(.+?)\]\s*$', body)
        if m:
            cur = m.group(1).strip()
            out.append(line)
            continue
        if cur == section and not body.lstrip().startswith(('#', ';')):
            m2 = re.match(r'^(\s*' + re.escape(key) + r'\s*[=:])(\s*)(.*?)(\s*)$', body)
            if m2 and m2.group(3) != str(value):
                sep = m2.group(2)
                # 原值为空且原作者用 'key = value' 风格时，补一个空格，避免写成 'key =value'
                if not sep and not m2.group(3) and ' =' in m2.group(1) and str(value) != '':
                    sep = ' '
                body = m2.group(1) + sep + str(value) + m2.group(4)
                changed = True
        out.append(body + eol)
    return ''.join(out), changed


# --------------------------------------------------------------------------
# 各类型文件的 读/写
# --------------------------------------------------------------------------
def extract(path, kind):
    """从文件里抽出当前值，返回 {逻辑字段: 值}。"""
    text, _ = read_text(path)
    vals = {}
    if kind in INI_SCHEMA:
        for field, section, key in INI_SCHEMA[kind]:
            v = ini_get(text, section, key)
            if v is not None:
                vals.setdefault(field, v)
        return vals
    if kind == 'config_js':
        m = re.search(r"let\s+ip\s*=\s*'([^']*)'", text)
        if m:
            vals['primary_ip'] = m.group(1)
        return vals
    if kind == 'conf_files':
        for field, var in (('db_host', 'DB_HOST'), ('db_user', 'DB_USER'),
                           ('db_password', 'DB_PASSWORD'), ('db_name', 'DB_NAME'),
                           ('redis_port', 'Redis_port'), ('redis_password', 'Redis_password'),
                           ('box_ip', 'Box_ip'), ('box_user', 'Box_user'),
                           ('box_password', 'Box_password'), ('kafka_ip', 'KAFKA_HOST'),
                           ('zlk_ip', 'ZLK_HOST'), ('zlk_port', 'ZLK_PORT'),
                           ('zlk_secret', 'ZLK_SECRET')):
            m = re.search(r'^\s*' + var + r'\s*=\s*["\']([^"\']*)["\']', text, re.M)
            if m:
                vals.setdefault(field, m.group(1))
        return vals
    if kind == 'model_ai':
        from model_ai_config import extract_model_ai
        parsed = extract_model_ai(text)
        parsed['primary_ip'] = parsed.pop('linux_ip')
        return parsed
    if kind == 'huawei_resource':
        m = re.search(r"host\s*=\s*'([^']*)'", text)
        if m:
            vals['db_host'] = m.group(1)
        return vals
    if kind == 'kafka_consumer':
        for field, var in (('kafka_ip', 'KAFKA_HOST'), ('primary_ip', 'ZDZH_HOST'), ('db_host', 'DB_HOST')):
            m = re.search(r'^\s*' + var + r"\s*=\s*['\"]([^'\"]*)['\"]", text, re.M)
            if m:
                vals.setdefault(field, m.group(1))
        return vals
    return vals


def apply_values(text, kind, values):
    """把 values 写进文本，返回 (新文本, 改动数, 改动明细)。"""
    changes = []

    def note(section, key, old, new):
        if old != new:
            changes.append({'section': section, 'key': key, 'old': old, 'new': new})

    if kind in INI_SCHEMA:
        for field, section, key in INI_SCHEMA[kind]:
            if field not in values or values[field] is None:
                continue
            old = ini_get(text, section, key)
            if old is None:
                continue
            text, ch = ini_set(text, section, key, values[field])
            if ch:
                note(section, key, old, values[field])
        return text, len(changes), changes

    if kind == 'config_js':
        if values.get('primary_ip'):
            # 分号可能被原正则漏掉，导致出现 ';;'；这里连分号一起匹配
            pat = re.compile(r"let\s+ip\s*=\s*'[^']*'\s*;?")
            m = pat.search(text)
            if m:
                old = (re.search(r"'([^']*)'", m.group(0)) or [None, ''])[1]
                text = pat.sub("let ip = '%s';" % values['primary_ip'], text, count=1)
                note('js', 'let ip', old, values['primary_ip'])
        return text, len(changes), changes

    if kind == 'conf_files':
        pairs = [('db_host', 'DB_HOST'), ('db_user', 'DB_USER'), ('db_password', 'DB_PASSWORD'),
                 ('db_name', 'DB_NAME'), ('redis_port', 'Redis_port'), ('redis_password', 'Redis_password'),
                 ('box_ip', 'Box_ip'), ('box_user', 'Box_user'), ('box_password', 'Box_password'),
                 ('kafka_ip', 'KAFKA_HOST'), ('zlk_ip', 'ZLK_HOST'), ('zlk_port', 'ZLK_PORT'),
                 ('zlk_secret', 'ZLK_SECRET')]
        for field, var in pairs:
            if field not in values or values.get(field) is None:
                continue
            pat = re.compile(r'^(\s*' + var + r'\s*=\s*)(["\'])(.*?)(\2)', re.M)
            m = pat.search(text)
            if not m:
                continue
            old = m.group(3)
            if old == str(values[field]):
                continue
            # re.sub 用函数替换时，反斜杠不做转义解析，直接写入即可
            text = pat.sub(lambda mm: mm.group(1) + mm.group(2) + str(values[field]) + mm.group(4),
                           text, count=1)
            note('py', var, old, values[field])
        return text, len(changes), changes

    if kind == 'model_ai':
        from model_ai_config import apply_model_ai
        model_values = dict(values)
        if 'primary_ip' in model_values:
            model_values['linux_ip'] = model_values.pop('primary_ip')
        return apply_model_ai(text, model_values)

    if kind == 'huawei_resource':
        if values.get('db_host'):
            pat = re.compile(r"(\bhost\s*=\s*')([^']*)(')")
            m = pat.search(text)
            if m and m.group(2) != str(values['db_host']):
                text = pat.sub(lambda mm: mm.group(1) + str(values['db_host']) + mm.group(3), text, count=1)
                note('py', 'host', m.group(2), values['db_host'])
        return text, len(changes), changes

    if kind == 'kafka_consumer':
        for field, var in (('kafka_ip', 'KAFKA_HOST'), ('primary_ip', 'ZDZH_HOST'), ('db_host', 'DB_HOST')):
            if field not in values or values.get(field) is None:
                continue
            pat = re.compile(r'^(\s*' + var + r'\s*=\s*)(["\'])(.*?)(\2)', re.M)
            m = pat.search(text)
            if not m or m.group(3) == str(values[field]):
                continue
            text = pat.sub(lambda mm: mm.group(1) + mm.group(2) + str(values[field]) + mm.group(4), text, count=1)
            note('py', var, m.group(3), values[field])
        return text, len(changes), changes

    return text, 0, []


# --------------------------------------------------------------------------
# 备份
# --------------------------------------------------------------------------
def backup(paths):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    root = BACKUP_ROOT / stamp
    manifest = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        rel = str(p).lstrip('/').replace('/', '__')
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        manifest.append({'src': str(p), 'bak': str(dest)})
    root.mkdir(parents=True, exist_ok=True)
    (root / 'manifest.json').write_text(
        json.dumps({'time': stamp, 'files': manifest}, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(root), manifest


# --------------------------------------------------------------------------
# 业务：构建状态 / 预览 / 应用
# --------------------------------------------------------------------------
def build_state():
    dirs = discover()
    ips = detect_ips()
    defaults = {}
    # 用最先出现的那份「现网」值作为表单初值
    priority = ['app_ini', 'api_ini', 'conf_files', 'model_ai', 'kafka_consumer', 'huawei_resource']
    all_files = [f for d in dirs for f in d['files'] if f['exists']]
    for want in priority:
        for f in all_files:
            if f['key'] != want:
                continue
            try:
                for k, v in extract(Path(f['path']), f['key']).items():
                    if v not in (None, '') and k not in defaults:
                        defaults[k] = v
            except Exception:
                pass
    # 主 IP 兜底
    if 'primary_ip' not in defaults and ips:
        defaults['primary_ip'] = ips[0]['ip']
    for key in ('db_host', 'redis_ip', 'kafka_ip', 'zlk_ip', 'box_ip',
                'upload_ip', 'stream_push_ip', 'aifz_ip'):
        if key not in defaults and defaults.get('primary_ip'):
            defaults[key] = defaults['primary_ip']
    # 文件清单（含元信息）
    for d in dirs:
        for f in d['files']:
            p = Path(f['path'])
            if not p.parent.is_dir():
                f['writable'] = False
            elif p.is_file():
                f['writable'] = os.access(str(p.parent), os.W_OK) and os.access(str(p), os.R_OK)
            else:
                f['writable'] = os.access(str(p.parent), os.W_OK)
            if p.is_file():
                try:
                    _, enc = read_text(p)
                    f['encoding'] = enc
                    f['size'] = p.stat().st_size
                    f['mtime'] = datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    f['encoding'] = '?'
            else:
                f['encoding'] = '-'
    return {
        'version': VERSION,
        'host': socket.gethostname(),
        'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ips': ips,
        'dirs': dirs,
        'defaults': defaults,
        'fields': [{'key': k, 'label': l, 'hint': h} for k, l, h in FIELDS],
        'restart_hint': RESTART_HINT,
        'backup_root': str(BACKUP_ROOT),
        'auth_required': bool(AUTH_TOKEN),
    }


def selected_files(payload):
    """根据 payload 里勾选的路径返回 [(kind, path)]。"""
    wanted = set(payload.get('files') or [])
    out = []
    for d in discover():
        for f in d['files']:
            if f['path'] in wanted and f['exists']:
                out.append((f['key'], Path(f['path'])))
    return out


def fill_ip_defaults(values):
    """兜底：请求里整个缺失的 IP 类字段，默认跟随主 IP。

    只补「键不存在」的，不动调用方显式传空串的字段。
    这样即使前端漏了某个输入框，配置文件里对应字段也不会被漏改。
    """
    if values.get('primary_ip'):
        for k in IP_LIKE_FIELDS:
            if k not in values:
                values[k] = values['primary_ip']
    return values


def guard_blank(values, current):
    """安全阀：表单传空串、但文件里原本有值 → 视为「该字段没填」而不是「要清空」。

    批量改配置的场景下，空值覆盖非空值几乎总是误操作（表单没回填、接口没返回、
    用户漏看），一旦写进去就是生产事故。这里保留原值，并把被跳过的字段报出来，
    保证不静默。想真正清空某个字段，把该字段从请求里去掉即可（同样不写）。
    """
    eff, skipped = dict(values), []
    for k, v in list(eff.items()):
        if v == '' and current.get(k):
            eff[k] = current[k]
            skipped.append({'key': k, 'kept': current[k]})
    return eff, skipped


def compute(payload):
    values = payload.get('values') or {}
    if values.get('zlk_secret') == '__RANDOM__':
        values['zlk_secret'] = secrets.token_hex(16)
    fill_ip_defaults(values)
    results = []
    for kind, path in selected_files(payload):
        text, enc = read_text(path)
        try:
            current = extract(path, kind)
        except Exception:
            current = {}
        eff, skipped = guard_blank(values, current)
        new_text, count, changes = apply_values(text, kind, eff)
        diff = ''
        if count:
            diff = '\n'.join(list(difflib.unified_diff(
                text.splitlines(), new_text.splitlines(),
                fromfile=str(path), tofile=str(path) + ' (新)',
                lineterm='', n=1))[:400])
        results.append({'kind': kind, 'path': str(path), 'encoding': enc,
                        'changed': count, 'changes': changes, 'diff': diff,
                        'skipped': skipped,
                        '_new': new_text if count else None})
    return values, results


def do_apply(payload):
    values, results = compute(payload)
    todo = [(r, Path(r['path'])) for r in results if r['changed']]
    if not todo:
        return {'ok': True, 'applied': 0, 'results': results, 'note': '没有需要改动的文件'}
    backup_dir, manifest = backup([p for _, p in todo])
    written = []
    for r, path in todo:
        text, enc = read_text(path)
        write_text(path, r['_new'], enc)
        back, _ = read_text(path)
        written.append({'path': str(path), 'changed': r['changed'],
                        'encoding': enc, 'verified': back == r['_new']})
    for r in results:
        r.pop('_new', None)
    return {'ok': True, 'applied': len(written), 'written': written,
            'backup': backup_dir, 'results': results}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="dispatch-ui-ready-marker" content="20261016-model-fields">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>配置信息派发工具</title>
<style>:root {
  --page: #f2f5fa;
  --surface: #ffffff;
  --text: #1e293b;
  --muted: #64748b;
  --subtle: #94a3b8;
  --border: #e2e8f0;
  --blue: #2563eb;
  --blue-dark: #1d4ed8;
  --blue-soft: #eff6ff;
  --green: #15803d;
  --radius: 12px;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-bottom: 120px; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text);
  font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
}
button, input, select { font: inherit; }
button { touch-action: manipulation; }
button, input, select { -webkit-tap-highlight-color: transparent; }
button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible {
  outline: 3px solid #bfdbfe;
  outline-offset: 2px;
}
button:disabled { cursor: not-allowed; opacity: .5; }

.app-header, header {
  min-height: 80px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px max(28px, calc((100vw - 1284px) / 2));
  background: var(--surface);
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
.brand { display: flex; align-items: center; gap: 12px; margin-right: auto; }
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: var(--blue);
  color: #fff;
  font-size: 21px;
  font-weight: 700;
}
.brand-mark svg { display: block; width: 23px; height: 23px; }
.app-header h1, header h1 { margin: 0; font-size: 18px; line-height: 1.4; font-weight: 650; letter-spacing: .2px; }
.brand-subtitle { margin-top: 2px; color: var(--muted); font-size: 11px; letter-spacing: .7px; }
.tag, header .tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
#host { color: #475569; }
#clock { font-variant-numeric: tabular-nums; }
.wrap { max-width: 1340px; margin: 30px auto 0; padding: 0 28px 132px; }
.workspace-hero { display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 27px; }
.eyebrow { margin: 0 0 7px; color: var(--blue); font-size: 11px; font-weight: 700; letter-spacing: 1.8px; }
.hero-title { margin: 0; color: #0f172a; font-size: 29px; font-weight: 650; line-height: 1.45; letter-spacing: -.5px; }
.hero-copy { margin: 8px 0 0; max-width: 800px; color: var(--muted); font-size: 13px; line-height: 1.8; }
.workspace-layout { display: grid; grid-template-columns: minmax(0, 1fr) 264px; align-items: start; gap: 24px; }
.workspace-main, .workspace-aside { min-width: 0; }
.workspace-aside { position: sticky; top: 24px; }

.card, .overview-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.card { padding: 24px; margin-bottom: 22px; }
.card:last-child { margin-bottom: 0; }
.card h2 { margin: 0 0 16px; padding: 0; border: 0; font-size: 16px; line-height: 1.5; font-weight: 650; }
.section-heading { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 21px; }
.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--blue-soft);
  color: var(--blue);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}
.section-heading .section-title, .section-title { margin: 1px 0 3px; padding: 0; border: 0; font-size: 16px; line-height: 1.55; font-weight: 650; }
.section-description { margin: 3px 0 0; color: var(--muted); font-size: 12px; line-height: 1.7; }
.grid, .field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px 20px; }
.fields-groups, #fields.fields-groups { display: block; }
.field-group { padding: 20px; margin-top: 16px; border: 1px solid #e6ecf3; border-radius: 9px; background: #f8fafc; }
.field-group:first-child { margin-top: 0; }
.field-group-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 3px 16px; margin-bottom: 17px; }
.field-group-title { margin: 0; color: #334155; font-size: 13px; font-weight: 650; }
.field-group-description { margin: 0; color: var(--muted); font-size: 11px; }
.field-control { min-width: 0; }
label { display: block; margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 500; }
input:not([type="checkbox"]):not([type="radio"]), select {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 9px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #fff;
  color: var(--text);
  font-size: 13px;
  line-height: 22px;
  transition: border-color .15s, box-shadow .15s;
}
input::placeholder { color: #94a3b8; opacity: 1; }
input:not([type="checkbox"]):not([type="radio"]):hover, select:hover { border-color: #94a3b8; }
input:not([type="checkbox"]):not([type="radio"]):focus, select:focus { border-color: var(--blue); box-shadow: 0 0 0 3px #dbeafe; outline: none; }
input[readonly] { color: #64748b; background: #f1f5f9; }
input[type="checkbox"], input[type="radio"] { width: 16px; height: 16px; margin: 0; accent-color: var(--blue); cursor: pointer; vertical-align: middle; }
input[type="checkbox"]:disabled, input[type="radio"]:disabled { cursor: not-allowed; }
.input-shell { position: relative; }
.input-shell input { padding-right: 64px !important; }
.secret-toggle { position: absolute; top: 5px; right: 5px; display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-width: 42px; height: 32px; padding: 0 8px; border: 0; border-radius: 5px; background: #f1f5f9; color: #64748b; font-size: 11px; cursor: pointer; }
.secret-toggle:hover { background: #e2e8f0; color: #334155; }
.secret-toggle svg { width: 16px; height: 16px; }
.hint { margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.65; overflow-wrap: anywhere; }
.ips { display: flex; flex-wrap: wrap; gap: 9px; margin-bottom: 19px; }
.ipbtn { display: inline-flex; align-items: center; min-height: 36px; padding: 7px 12px; border: 1px solid #dbe3ed; border-radius: 7px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; transition: border-color .15s, background .15s; }
.ipbtn:hover { border-color: #93b4f5; background: #f8fbff; }
.ipbtn.on { border-color: #93b4f5; background: var(--blue-soft); color: var(--blue-dark); font-weight: 600; }
.operation-tools, .btns { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; margin-top: 16px; }
.operation-tools { padding-top: 17px; border-top: 1px solid #e8edf4; }
button.act { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 39px; padding: 9px 15px; border: 1px solid transparent; border-radius: 7px; font-size: 12px; line-height: 1.5; font-weight: 600; cursor: pointer; transition: background .15s, border-color .15s; }
button.act svg { width: 16px; height: 16px; flex-shrink: 0; }
button.act.b1 { border-color: #cbd5e1; background: #fff; color: #334155; }
button.act.b1:hover:not(:disabled) { background: #f8fafc; border-color: #94a3b8; }
button.act.b2 { border-color: #dbe3ed; background: #fff; color: #475569; }
button.act.b2:hover:not(:disabled) { background: var(--blue-soft); border-color: #bfdbfe; color: var(--blue-dark); }
button.act.b3 { border-color: var(--blue); background: var(--blue); color: #fff; }
button.act.b3:hover:not(:disabled) { border-color: var(--blue-dark); background: var(--blue-dark); }
button.act:disabled { opacity: .5; cursor: not-allowed; }

.overview-card { padding: 21px 20px; margin-bottom: 18px; }
.overview-heading { display: flex; align-items: center; gap: 8px; margin: 0 0 17px; color: #334155; font-size: 13px; font-weight: 650; }
.overview-heading svg { width: 17px; height: 17px; color: var(--blue); }
.overview-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.overview-stat { padding: 14px 10px; border: 1px solid #e8edf4; border-radius: 8px; background: #f8fafc; text-align: center; }
.overview-number { display: block; color: #0f172a; font-size: 26px; line-height: 1.25; font-weight: 650; font-variant-numeric: tabular-nums; }
.overview-label { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; }
.workflow-list { display: flex; flex-direction: column; gap: 18px; padding: 0; margin: 0; list-style: none; }
.workflow-item { display: flex; align-items: flex-start; gap: 10px; }
.workflow-index { display: inline-flex; flex: 0 0 23px; align-items: center; justify-content: center; width: 23px; height: 23px; border-radius: 50%; background: #eff6ff; color: #3b6ccd; font-size: 11px; font-weight: 600; }
.workflow-content { min-width: 0; color: var(--muted); font-size: 11px; line-height: 1.7; }
.workflow-content strong { display: block; margin-bottom: 3px; color: #475569; font-size: 12px; font-weight: 600; }
.overview-card .hint { margin-top: 12px; font-size: 11px; }
.overview-card code { overflow-wrap: anywhere; }

.dir, .file-group-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 5px 9px; margin: 20px 0 10px; color: #334155; font-size: 12px; font-weight: 650; }
.dir:first-child, .file-group-heading:first-child { margin-top: 0; }
.dir small, .file-group-heading small { color: var(--muted); font-size: 11px; font-weight: 400; overflow-wrap: anywhere; }
.file-table-wrap { width: 100%; overflow-x: auto; border: 1px solid #e4eaf2; border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
.file-table-wrap table { min-width: 640px; }
th, td { padding: 12px 11px; text-align: left; border-bottom: 1px solid #edf1f6; vertical-align: middle; }
th { background: #f8fafc; color: #64748b; font-size: 11px; font-weight: 550; white-space: nowrap; }
td { color: #475569; }
tr:last-child td { border-bottom: 0; }
tbody tr:hover td { background: #fafcff; }
td .hint { margin-top: 3px; font-size: 10px; line-height: 1.55; }
td > .fchk { display: block; }
td:first-child { padding-left: 14px; }
th:first-child { padding-left: 14px; }
.chip { display: inline-flex; align-items: center; padding: 2px 7px; margin-left: 0; border-radius: 4px; background: #edf2f7; color: #64748b; font-size: 10px; line-height: 1.6; white-space: nowrap; }
.chip.gbk { background: #fff3e5; color: #a05a10; }
.status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border-radius: 4px; font-size: 10px; line-height: 1.6; white-space: nowrap; }
.status-badge::before { content: ""; flex: 0 0 5px; width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.status-badge.writable { background: #edf9f0; color: #2f8150; }
.status-badge.readonly { background: #fff7e6; color: #9a6a13; }
.status-badge.missing { background: #f1f5f9; color: #94a3b8; }
.legacy-badge { display: inline-flex; padding: 1px 6px; border: 1px solid #e8d8b7; border-radius: 4px; background: #fffbf2; color: #9a7a39; font-size: 10px; font-weight: 400; white-space: nowrap; }
.file-legacy td { background: #fcfcfd; color: #94a3b8; }
.file-legacy td .hint { color: #94a3b8; }

.result-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; min-height: 165px; padding: 25px 20px; border: 1px dashed #d9e3ef; border-radius: 9px; background: #fbfcfe; color: #94a3b8; font-size: 12px; text-align: center; }
.result-placeholder strong { color: #64748b; font-size: 13px; font-weight: 500; }
.result-icon { display: flex; align-items: center; justify-content: center; width: 39px; height: 39px; margin-bottom: 3px; border-radius: 10px; background: #eff4fa; color: #8ea4bf; font-size: 21px; }
.result-icon svg { width: 21px; height: 21px; }
#out { min-width: 0; }
#out > .card { padding: 18px; margin-top: 14px; border-radius: 8px; }
#out .card h2 { font-size: 12px; overflow-wrap: anywhere; }
#out table { display: block; overflow-x: auto; }
#out code { overflow-wrap: anywhere; word-break: break-word; }
.msg { padding: 11px 14px; margin-bottom: 14px; border: 1px solid transparent; border-radius: 7px; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.ok { border-color: #bfe3cc; background: #f0faf3; color: #237447; }
.err { border-color: #f2c8c8; background: #fff2f2; color: #b34141; }
.warn { border-color: #eddbb0; background: #fffbef; color: #8b691f; }
code { padding: 2px 5px; border-radius: 4px; background: #f1f5f9; color: #526379; font: 11px/1.6 Consolas, "SFMono-Regular", monospace; }
pre { max-height: 480px; overflow: auto; margin: 14px 0 0; padding: 16px; border: 1px solid #27364b; border-radius: 7px; background: #172337; color: #dbe7f4; font: 11px/1.8 Consolas, "SFMono-Regular", monospace; white-space: pre-wrap; overflow-wrap: anywhere; }

.action-dock { position: fixed; left: 0; right: 0; bottom: 0; z-index: 50; background: #fff; border-top: 1px solid #dce4ee; box-shadow: 0 -3px 14px rgba(30, 41, 59, .035); }
.action-dock-inner { display: flex; align-items: center; justify-content: space-between; gap: 20px; max-width: 1340px; min-height: 82px; margin: 0 auto; padding: 15px 28px; }
.action-summary { min-width: 0; color: var(--muted); font-size: 11px; line-height: 1.6; }
.action-summary strong { color: #334155; font-size: 13px; font-weight: 600; }
.action-summary .hint { margin-top: 3px; font-size: 10px; }
.action-buttons { display: flex; align-items: center; flex: 0 0 auto; gap: 10px; }
.action-buttons button.act { min-width: 130px; min-height: 42px; padding: 10px 19px; font-size: 13px; }

@media (min-width: 1400px) {
  .field-grid { column-gap: 22px; }
}
@media (max-width: 1100px) {
  .workspace-layout { grid-template-columns: minmax(0, 1fr) 238px; gap: 20px; }
  .wrap { padding-left: 22px; padding-right: 22px; }
  .card { padding: 21px; }
  .overview-card { padding: 18px 16px; }
  .field-group { padding: 17px; }
  .field-grid { gap: 16px; }
}
@media (max-width: 1024px) {
  .workspace-layout { grid-template-columns: minmax(0, 1fr); }
  .workspace-aside { display: none; }
  .app-header, header { padding: 15px 24px; }
  .wrap { max-width: 960px; margin-top: 26px; padding-left: 24px; padding-right: 24px; }
  .card { padding: 24px; }
  .field-group { padding: 20px; }
  .action-dock-inner { padding-left: 24px; padding-right: 24px; }
}
@media (max-width: 640px) {
  html { scroll-padding-bottom: 154px; }
  .app-header, header { min-height: 78px; gap: 7px; padding: 14px 16px; }
  .brand { width: 100%; gap: 10px; margin-bottom: 5px; }
  .brand-mark { flex-basis: 36px; width: 36px; height: 36px; border-radius: 9px; }
  .app-header h1, header h1 { font-size: 17px; }
  .brand-subtitle { font-size: 10px; }
  .tag, header .tag { padding: 3px 7px; font-size: 10px; }
  .wrap { margin-top: 23px; padding: 0 14px 166px; }
  .workspace-hero { margin-bottom: 20px; padding: 0 3px; }
  .eyebrow { font-size: 10px; letter-spacing: 1.3px; }
  .hero-title { font-size: 24px; }
  .hero-copy { margin-top: 7px; font-size: 12px; }
  .card { padding: 19px 16px; margin-bottom: 17px; border-radius: 10px; }
  .section-heading { gap: 10px; margin-bottom: 18px; }
  .step-number { flex-basis: 27px; width: 27px; height: 27px; border-radius: 7px; font-size: 12px; }
  .section-heading .section-title, .section-title { font-size: 15px; }
  .section-description { font-size: 11px; }
  .grid, .field-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .field-group { padding: 16px 13px; margin-top: 13px; }
  .field-group-heading { align-items: flex-start; flex-direction: column; gap: 3px; margin-bottom: 15px; }
  .field-group-description { font-size: 10px; }
  .ips { gap: 7px; margin-bottom: 17px; }
  .ipbtn { width: 100%; justify-content: flex-start; font-size: 11px; line-height: 1.7; text-align: left; }
  .hint { font-size: 10px; }
  .operation-tools, .btns { gap: 8px; }
  button.act { padding: 8px 11px; font-size: 11px; }
  .operation-tools button.act { flex: 1 1 auto; }
  .dir, .file-group-heading { gap: 4px 7px; font-size: 11px; }
  .dir small, .file-group-heading small { width: 100%; font-size: 10px; }
  .action-dock-inner { align-items: stretch; flex-direction: column; gap: 9px; min-height: 114px; padding: 11px 16px max(12px, env(safe-area-inset-bottom)); }
  .action-summary { font-size: 10px; }
  .action-summary strong { font-size: 12px; }
  .action-summary .hint { margin-top: 1px; font-size: 9px; }
  .action-buttons { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); gap: 9px; }
  .action-buttons button.act { width: 100%; min-width: 0; min-height: 42px; padding: 9px 11px; font-size: 12px; }
  .result-placeholder { min-height: 148px; padding: 20px 12px; font-size: 11px; }
  #out > .card { padding: 14px 11px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  button, input, select { transition: none !important; }
}
</style></head><body>
<header class="app-header">
  <div class="brand"><span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 6h16M4 12h16M4 18h16"/><rect x="7" y="3" width="4" height="6" rx="1.3" fill="currentColor" stroke="none"/><rect x="14" y="9" width="4" height="6" rx="1.3" fill="currentColor" stroke="none"/><rect x="8" y="15" width="4" height="6" rx="1.3" fill="currentColor" stroke="none"/></svg></span><div><h1>配置信息派发工具</h1><div class="brand-subtitle">监管平台 · 配置管理</div></div></div>
  <span class="tag" id="connection-label">正在连接</span>
  <span class="tag" id="host">-</span><span class="tag" id="ver">-</span><span class="tag" id="clock">-</span>
</header>
<div class="wrap">
  <div class="workspace-hero"><p class="eyebrow">部署配置</p><h2 class="hero-title">服务配置与文件派发</h2><p class="hero-copy">集中设置服务地址、连接参数和目标文件。先预览变更，再应用并自动备份。</p></div>
  <div id="topmsg" role="status" aria-live="polite"></div>
  <div class="workspace-layout"><main class="workspace-main">
    <section class="card" id="network-section">
      <div class="section-heading"><span class="step-number">01</span><div><h2 class="section-title">主机网络</h2><p class="section-description">选择本机业务 IP，设置服务地址的联动方式。</p></div></div>
      <div class="ips" id="ips"></div>
      <div class="grid"><div><label for="primary_ip">主 IP（linux_ip）</label><input id="primary_ip" placeholder="192.168.x.x" oninput="onPrimaryInput()"><div class="hint">写入 model_ai.py 的 linux_ip；算力设备 IP（box_ip）可单独填写。</div></div>
      <div><label for="follow_all">地址联动</label><label class="follow-control" style="display:flex;align-items:center;gap:9px;min-height:42px;margin:0"><input type="checkbox" id="follow_all" onchange="onPrimaryInput()">所有服务 IP 跟随主 IP</label><div class="hint">现有地址不一致时默认关闭。服务分布在多台主机时，保持关闭并分别填写。</div></div></div>
    </section>
    <section class="card" id="config-section">
      <div class="section-heading"><span class="step-number">02</span><div><h2 class="section-title">服务连接配置</h2><p class="section-description">已从现网文件读取当前值，按服务分组调整。</p></div></div>
      <div id="fields" class="fields-groups"></div>
      <div class="operation-tools"><button type="button" class="act b2" onclick="genSecret()">随机生成 ZLK secret</button><button type="button" class="act b2" onclick="syncPrimary()">统一所有服务 IP</button></div>
      <p class="hint">“统一所有服务 IP”会将数据库、算力设备等服务地址全部改为主 IP；不同主机部署时，请分别填写。</p>
      <p class="hint">ZLK secret 同步到 <code>config.ini [ZLK]</code>、<code>zlk/config.ini [api]</code> 和 <code>Conf_files.py</code>，请保持一致。</p>
    </section>
    <section class="card" id="file-section">
      <div class="section-heading"><span class="step-number">03</span><div><h2 class="section-title">选择目标文件</h2><p class="section-description">按目录查看配置文件，确认本次需要修改的目标。</p></div></div>
      <div id="files"></div><div class="btns"><button type="button" class="act b2" onclick="selAll(true)">全选</button><button type="button" class="act b2" onclick="selAll(false)">全不选</button></div>
    </section>
    <section class="card" id="result-section">
      <div class="section-heading"><span class="step-number">04</span><div><h2 class="section-title">变更预览与执行结果</h2><p class="section-description">逐项核对差异，应用后在这里查看写入与备份结果。</p></div></div>
      <div id="out" role="status" aria-live="polite"><div class="result-placeholder"><span class="result-icon" aria-hidden="true">≡</span><strong>尚未生成变更预览</strong><span>完成配置后，点击下方“预览变更”查看差异。</span></div></div>
    </section>
  </main><aside class="workspace-aside" aria-label="配置概览">
    <section class="overview-card"><h2 class="overview-heading">本次配置概览</h2><div class="overview-stats"><div class="overview-stat"><strong class="overview-number" id="field-count">—</strong><span class="overview-label">配置字段</span></div><div class="overview-stat"><strong class="overview-number" id="selected-count">—</strong><span class="overview-label">已选文件</span></div></div><p class="hint">主 IP<br><code id="summary-ip">正在读取</code></p><p class="hint">可用文件 <span id="available-count">—</span> 个</p></section>
    <section class="overview-card"><h2 class="overview-heading">操作步骤</h2><ol class="workflow-list"><li class="workflow-item"><span class="workflow-index">1</span><div class="workflow-content"><strong>确认主机地址</strong>选择业务网卡，检查联动设置。</div></li><li class="workflow-item"><span class="workflow-index">2</span><div class="workflow-content"><strong>调整服务参数</strong>核对地址、端口与账号信息。</div></li><li class="workflow-item"><span class="workflow-index">3</span><div class="workflow-content"><strong>选择活动配置</strong>当前部署以 /data/AIGO/platform_start 目录为准。</div></li><li class="workflow-item"><span class="workflow-index">4</span><div class="workflow-content"><strong>预览后应用</strong>确认差异，写入前自动备份。</div></li></ol></section>
    <section class="overview-card"><h2 class="overview-heading">配置备份</h2><p class="hint" id="bkhint">正在读取备份路径</p><p class="hint">保留备份路径，便于核对或恢复本次修改。</p></section>
  </aside></div>
</div>
<div class="action-dock"><div class="action-dock-inner"><div class="action-summary"><strong>已选择 <span id="dock-count">—</span> 个目标文件</strong><div class="hint">共 <span id="dock-total">—</span> 个可用文件 · 先核对变更，再应用配置</div></div><div class="action-buttons"><button type="button" class="act b1" id="btnPreview" onclick="go('preview')">预览变更</button><button type="button" class="act b3" id="btnApply" onclick="go('apply')">应用（自动备份）</button></div></div></div>
<script>
var STATE = null;

function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

function tick(){
  var d=new Date();
  function p(n){return (n<10?'0':'')+n;}
  $('clock').textContent=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
}

function load(){
  fetch('api/state').then(function(r){return r.json();}).then(function(s){
    STATE=s;
    $('ver').textContent='v'+s.version;
    $('host').textContent=s.host;
    $('bkhint').textContent='备份目录：'+s.backup_root;
    var ips=$('ips'); ips.innerHTML='';
    s.ips.forEach(function(it){
      var b=document.createElement('button');
      b.className='ipbtn'+(it.primary?' on':'');
      b.textContent=it.ip+'  ('+it.iface+(it.note?', '+it.note:'')+')';
      b.onclick=function(){
        $('primary_ip').value=it.ip;
        onPrimaryInput();
        [].forEach.call(document.querySelectorAll('.ipbtn'),function(x){x.classList.remove('on');});
        b.classList.add('on');
      };
      ips.appendChild(b);
    });
    var f=$('fields'); f.innerHTML='';
    s.fields.forEach(function(fd){
      var wrap=document.createElement('div');
      var lab=document.createElement('label');
      lab.textContent=fd.label;
      var inp=document.createElement('input');
      inp.id='f_'+fd.key; inp.dataset.key=fd.key;
      if(fd.key==='zlk_secret'){ inp.readOnly=true; inp.style.background='#f7fafc'; }
      inp.value=s.defaults[fd.key]||'';
      inp.placeholder=fd.hint||'';
      wrap.appendChild(lab); wrap.appendChild(inp);
      if(fd.hint){var h=document.createElement('div');h.className='hint';h.textContent=fd.hint;wrap.appendChild(h);}
      f.appendChild(wrap);
    });
    $('primary_ip').value=s.defaults['primary_ip']||'';
    initializeAddressFollowing();
    var box=$('files'); box.innerHTML='';
    s.dirs.forEach(function(d){
      var div=document.createElement('div'); div.className='dir';
      div.innerHTML='<span>'+esc(d.kind)+'</span> <small>'+esc(d.path)+'</small>';
      box.appendChild(div);
      var t=document.createElement('table');
      t.innerHTML='<tr><th style="width:34px"></th><th>文件</th><th style="width:110px">编码</th><th style="width:150px">修改时间</th><th style="width:80px">状态</th></tr>';
      d.files.forEach(function(fl){
        var tr=document.createElement('tr');
        var enc=fl.encoding||'-';
        var chip='<span class="chip'+(enc.toLowerCase().indexOf('gbk')>=0?' gbk':'')+'">'+esc(enc)+'</span>';
        tr.innerHTML='<td><input type="checkbox" class="fchk" data-exists="'+(fl.exists?'1':'0')+'" value="'+esc(fl.path)+'"'+(fl.exists?' checked':' disabled')+'></td>'+
          '<td>'+esc(fl.label)+'<div class="hint">'+esc(fl.path)+'</div></td>'+
          '<td>'+chip+'</td>'+
          '<td class="hint">'+esc(fl.mtime||'-')+'</td>'+
          '<td>'+(fl.exists?(fl.writable?'可写':'只读'):'不存在')+'</td>';
        t.appendChild(tr);
      });
      box.appendChild(t);
    });
  });
}

function genSecret(){
  fetch('api/secret').then(function(r){return r.json();}).then(function(d){
    $('f_zlk_secret').value=d.secret;
  });
}

var IP_FIELDS = ['db_host','redis_ip','kafka_ip','zlk_ip','box_ip','upload_ip','stream_push_ip','aifz_ip'];

// 主 IP 改动时实时联动：勾选「跟随」则所有 IP 字段一起变
// dispatch-independent-addresses-20261016
// Existing different addresses stay independent until the operator opts in.
function initializeAddressFollowing(){
  var ip=$('primary_ip').value.trim();
  $('follow_all').checked=!!ip && IP_FIELDS.every(function(k){
    var input=$('f_'+k);
    return !input || input.value.trim()===ip;
  });
}

function onPrimaryInput(){
  var ip=$('primary_ip').value.trim();
  if(!$('follow_all').checked || !ip) return;
  IP_FIELDS.forEach(function(k){
    var el=$('f_'+k);
    if(el) el.value=ip;
  });
}

function syncPrimary(){
  var ip=$('primary_ip').value.trim();
  if(!ip) return;
  $('follow_all').checked=true;
  onPrimaryInput();
}

function values(){
  var v={};
  [].forEach.call(document.querySelectorAll('#fields input'),function(i){ v[i.dataset.key]=i.value; });
  v['primary_ip']=$('primary_ip').value.trim();
  return v;
}

function selected(){
  return [].slice.call(document.querySelectorAll('.fchk:checked')).map(function(c){return c.value;});
}

function selAll(on){
  [].forEach.call(document.querySelectorAll('.fchk'),function(c){
    if(c.dataset.exists==='1'){ c.checked=on; }
  });
}

function go(action){
  var files=selected();
  if(!files.length){ $('topmsg').innerHTML='<div class="msg warn">请先勾选要修改的文件</div>'; return; }
  [].forEach.call(document.querySelectorAll('.fchk'),function(c){ if(c.dataset.exists==='1')c.disabled=true; });
  $('btnPreview').disabled=true; $('btnApply').disabled=true;
  $('out').innerHTML='<div class="msg warn">正在处理…</div>';
  fetch('api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({values:values(),files:files})})
  .then(function(r){return r.json();})
  .then(function(d){
    if(!d.ok){ $('out').innerHTML='<div class="msg err">'+esc(d.error||'失败')+'</div>'; return; }
    var html='';
    if(action==='apply'){
      html+='<div class="msg ok">已写入 '+d.applied+' 个文件'+(d.note?'（'+esc(d.note)+'）':'')+
            (d.backup?' · 备份：<code>'+esc(d.backup)+'</code>':'')+'</div>';
    } else {
      var total=d.results.reduce(function(a,b){return a+b.changed;},0);
      html+='<div class="msg '+(total?'ok':'warn')+'">预览：共 '+total+' 处变更'+(total?'':'（当前值与文件一致）')+'</div>';
    }
    var skipTotal=d.results.reduce(function(a,b){return a+((b.skipped&&b.skipped.length)||0);},0);
    if(skipTotal){
      html+='<div class="msg warn">有 '+skipTotal+' 个字段表单为空但文件里原本有值，已<b>保留原值不改</b>（空值不覆盖非空值）。'+
            '确实要清空的话，请直接改文件。</div>';
    }
    d.results.forEach(function(r){
      var sk=(r.skipped&&r.skipped.length)||0;
      if(!r.changed && !sk) return;
      html+='<div class="card"><h2>'+esc(r.path)+' <span class="chip">'+r.changed+' 处</span>'+
            (sk?' <span class="chip" style="background:#fff8e6;color:#8a6100">跳过 '+sk+' 项</span>':'')+'</h2>';
      if(r.changed){
        html+='<table><tr><th style="width:110px">位置</th><th>字段</th><th>原值</th><th>新值</th></tr>';
        r.changes.forEach(function(c){
          html+='<tr><td class="hint">'+esc(c.section)+'</td><td>'+esc(c.key)+'</td><td><code>'+esc(c.old)+'</code></td><td><code>'+esc(c.new)+'</code></td></tr>';
        });
        html+='</table>';
        if(r.diff){ html+='<pre>'+esc(r.diff)+'</pre>'; }
      }
      if(sk){
        html+='<table><tr><th style="width:110px">位置</th><th>字段</th><th>表单值</th><th>处理</th></tr>';
        r.skipped.forEach(function(s){
          html+='<tr><td class="hint">—</td><td>'+esc(s.key)+'</td><td><code>（空）</code></td>'+
                '<td>保留原值 <code>'+esc(s.kept)+'</code></td></tr>';
        });
        html+='</table>';
      }
      html+='</div>';
    });
    $('out').innerHTML=html;
  })
  .catch(function(e){ $('out').innerHTML='<div class="msg err">请求失败：'+esc(e.message)+'</div>'; })
  .finally(function(){
    [].forEach.call(document.querySelectorAll('.fchk'),function(c){
      if(c.dataset.exists==='1'){ c.disabled=false; }
    });
    $('btnPreview').disabled=false; $('btnApply').disabled=false;
  });
}

load(); tick(); setInterval(tick,1000);

/* 内联 onclick/oninput 只能访问全局作用域，这里把需要被 HTML 调用的函数挂到 window 上，
   否则点击「预览/应用/随机 secret/全选」会报 ReferenceError。 */
window.genSecret = genSecret;
window.syncPrimary = syncPrimary;
window.selAll = selAll;
window.go = go;
window.onPrimaryInput = onPrimaryInput;
</script><script>/* Presentation enhancements. Existing values(), selected(), go() and API calls remain unchanged. */
(function () {
  'use strict';
  const GROUPS = [
    ['数据库', 'MySQL 连接与账号', ['db_host','db_port','db_user','db_password','db_name']],
    ['缓存与消息', 'Redis 与 Kafka 服务', ['redis_ip','redis_port','redis_password','kafka_ip','kafka_port']],
    ['流媒体服务', 'ZLMediaKit 地址与密钥', ['zlk_ip','zlk_port','zlk_secret']],
    ['算力设备', '算力设备连接信息', ['box_ip','box_user','box_password']],
    ['平台与上传', '平台接口、报警上传与分析服务', ['upload_ip','upload_port','stream_push_ip','aifz_ip','platform_port','aifz_port','primary_ip']]
  ];
  const FIELD_LABELS = {box_ip:'算力设备 IP（box_ip）', box_user:'用户', box_password:'密码'};
  const FIELD_HINTS = {box_ip:'写入 model_ai.py 的 box_ip；可与主 IP（linux_ip）不同。'};
  function el(tag, cls, text) {
    const node=document.createElement(tag);
    if(cls) node.className=cls;
    if(text!==undefined) node.textContent=text;
    return node;
  }
  function updateSummary() {
    const boxes=Array.from(document.querySelectorAll('.fchk'));
    const picked=boxes.filter(c=>c.checked).length;
    const available=boxes.filter(c=>c.dataset.exists==='1').length;
    document.getElementById('selected-count').textContent=String(picked);
    document.getElementById('available-count').textContent=String(available);
    document.getElementById('dock-count').textContent=String(picked);
    document.getElementById('dock-total').textContent=String(available);
    const primary=document.getElementById('primary_ip').value.trim();
    document.getElementById('summary-ip').textContent=primary || '尚未填写';
  }
  function prepareField(wrapper) {
    wrapper.classList.add('field-control');
    const input=wrapper.querySelector('input'), label=wrapper.querySelector('label');
    if(!input) return;
    if(label) {
      label.htmlFor=input.id;
      if(FIELD_LABELS[input.dataset.key]) label.textContent=FIELD_LABELS[input.dataset.key];
    }
    if(FIELD_HINTS[input.dataset.key]) {
      let hint=wrapper.querySelector('.hint');
      if(!hint) {hint=el('div','hint');wrapper.appendChild(hint);}
      hint.textContent=FIELD_HINTS[input.dataset.key];
    }
    input.autocomplete='off';
    if(/password|secret/.test(input.dataset.key||'')) {
      input.type='password';
      const shell=el('div','input-shell');
      input.parentNode.insertBefore(shell,input);shell.appendChild(input);
      const toggle=el('button','secret-toggle','显示');
      toggle.type='button';
      toggle.setAttribute('aria-label','显示'+(label?label.textContent:'内容'));
      toggle.setAttribute('aria-pressed','false');
      toggle.addEventListener('click',function(){
        const show=input.type==='password';
        input.type=show?'text':'password';
        toggle.textContent=show?'隐藏':'显示';
        toggle.setAttribute('aria-label',(show?'隐藏':'显示')+(label?label.textContent:'内容'));
        toggle.setAttribute('aria-pressed',String(show));
      });
      shell.appendChild(toggle);
    }
  }
  function decorateFiles() {
    const host=document.getElementById('files');
    Array.from(host.querySelectorAll(':scope > table')).forEach(function(table){
      const wrap=el('div','file-table-wrap');
      table.parentNode.insertBefore(wrap,table);wrap.appendChild(table);
      const heading=wrap.previousElementSibling;
      const directory=heading&&heading.querySelector('small');
      const legacy=directory&&directory.textContent.trim().startsWith('/opt/');
      if(heading) heading.classList.add('file-group-heading');
      if(legacy) {
        heading.appendChild(el('span','legacy-badge','历史配置目录'));
        wrap.classList.add('file-legacy');
      }
      table.querySelectorAll('tr').forEach(function(row){
        const cell=row.querySelector('td:last-child');
        if(!cell) return;
        const status=cell.textContent.trim();
        cell.textContent='';
        cell.appendChild(el('span','status-badge '+(status==='可写'?'writable':status==='只读'?'readonly':'missing'),status));
        const checkbox=row.querySelector('.fchk'), path=row.querySelector('td:nth-child(2) .hint');
        if(checkbox&&path) checkbox.setAttribute('aria-label','选择 '+path.textContent);
      });
    });
  }
  function enhance() {
    const fields=document.getElementById('fields');
    const existing=Array.from(fields.children);
    const byKey=new Map();
    existing.forEach(function(w){
      const input=w.querySelector('input');
      if(input) byKey.set(input.dataset.key,w);
    });
    fields.className='fields-groups';
    GROUPS.forEach(function(group){
      const present=group[2].filter(k=>byKey.has(k));
      if(!present.length) return;
      const section=el('section','field-group');
      const heading=el('div','field-group-heading');
      heading.appendChild(el('h3','field-group-title',group[0]));
      heading.appendChild(el('span','field-group-description',group[1]));
      const grid=el('div','field-grid');
      section.appendChild(heading);section.appendChild(grid);fields.appendChild(section);
      present.forEach(function(key){
        const wrapper=byKey.get(key);prepareField(wrapper);grid.appendChild(wrapper);byKey.delete(key);
      });
    });
    // Forward-compatible presentation for fields added by the existing backend.
    if(byKey.size) {
      const section=el('section','field-group');
      section.appendChild(el('h3','field-group-title','其他配置'));
      const grid=el('div','field-grid');section.appendChild(grid);fields.appendChild(section);
      byKey.forEach(function(w){prepareField(w);grid.appendChild(w);});
    }
    decorateFiles();
    document.getElementById('field-count').textContent=String(existing.length);
    document.getElementById('connection-label').textContent='已连接服务';
    document.documentElement.dataset.dispatchUi='ready';
    updateSummary();
  }
  const observer=new MutationObserver(function(){
    if(document.getElementById('fields').querySelector('input') && window.STATE) {
      observer.disconnect();enhance();
    }
  });
  observer.observe(document.getElementById('fields'),{childList:true});
  if(document.getElementById('fields').querySelector('input') && window.STATE) {
    observer.disconnect();enhance();
  }
  document.addEventListener('change',updateSummary);
  document.addEventListener('input',updateSummary);
  document.addEventListener('click',function(){requestAnimationFrame(updateSummary);});
})();

</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = 'cfg-dispatch/' + VERSION

    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s\n' % (datetime.now().strftime('%H:%M:%S'), fmt % args))

    def _auth_ok(self):
        if not AUTH_TOKEN:
            return True
        token = ''
        url = urlparse(self.path)
        if 'token=' in (url.query or ''):
            token = url.query.split('token=', 1)[1].split('&')[0]
        if not token:
            token = self.headers.get('X-Cfgp-Token', '')
        return token == AUTH_TOKEN

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text):
        body = text.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._html(PAGE)
            return
        if path == '/api/secret':
            self._json({'secret': secrets.token_hex(16)})
            return
        if not self._auth_ok():
            self._json({'ok': False, 'error': '未授权'}, 401)
            return
        if path == '/api/state':
            try:
                self._json(build_state())
            except Exception as exc:
                self._json({'ok': False, 'error': str(exc)}, 500)
            return
        self._json({'ok': False, 'error': 'not found'}, 404)

    def do_POST(self):
        if not self._auth_ok():
            self._json({'ok': False, 'error': '未授权'}, 401)
            return
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b'{}'
        try:
            payload = json.loads(raw.decode('utf-8'))
        except Exception as exc:
            self._json({'ok': False, 'error': '请求体解析失败: %s' % exc}, 400)
            return
        try:
            if path == '/api/preview':
                values, results = compute(payload)
                for r in results:
                    r.pop('_new', None)
                self._json({'ok': True, 'results': results})
            elif path == '/api/apply':
                self._json(do_apply(payload))
            else:
                self._json({'ok': False, 'error': 'not found'}, 404)
        except Exception as exc:
            import traceback
            self._json({'ok': False, 'error': '%s: %s' % (type(exc).__name__, exc),
                        'trace': traceback.format_exc()[-1200:]}, 500)


def main():
    try:
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print('  警告: 备份目录 %s 创建失败 (%s)，应用前的备份将失败' % (BACKUP_ROOT, exc), flush=True)
    ips = detect_ips()
    print('配置信息派发工具 v%s' % VERSION, flush=True)
    print('  监听: http://0.0.0.0:%d' % PORT, flush=True)
    for it in ips:
        print('  可用: http://%s:%d  (%s%s)' % (it['ip'], PORT, it['iface'],
              ', 默认路由' if it['primary'] else ''), flush=True)
    print('  备份目录: %s' % BACKUP_ROOT, flush=True)
    if AUTH_TOKEN:
        print('  已启用 token 校验', flush=True)
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    raise SystemExit('Use config-dispatch.service and the HTTPS gateway; legacy HTTP entry is disabled')
