#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按环境变量对平台配置文件做 IP / 口令替换（幂等，可重复执行）。"""
import glob
import os
import re

IP = os.environ.get('TARGET_IP', '')
DB_ROOT = os.environ.get('MYSQL_ROOT_PASS', '')
DB_ADMIN = os.environ.get('MYSQL_ADMIN_PASS', '')
BOX_PASS = os.environ.get('BOX_PASS', '')
OLD_IP = '192.168.113.100'

IP_FILES = [
    '/data/Config_files/config.ini',
    '/data/Config_files/config.js',
    '/data/platform_gateway/default.conf',
    '/data/platform_gateway/tls/server.cnf',
    '/data/config_dispatch/gateway/nginx.conf',
    '/data/config_dispatch/gateway/proxy.conf',
    '/data/config_dispatch/security-settings.json',
    '/data/model_algorithm_package/Conf_files.py',
    '/data/model_algorithm_package/model_ai.py',
    '/data/model_algorithm_package/Huawei_resource.py',
    '/data/model_algorithm_package/kafka_consumer.py',
    '/data/platform_algorithm_start/config/ApiConfig.ini',
    '/data/platform_algorithm_start/config/common.py',
    '/opt/nginx/conf/nginx.conf',
    '/data/Config_files/secure-transport.js',
]


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def replace_literal(path, old, new):
    if not old or not new or not os.path.isfile(path):
        return False
    text = read(path)
    if old not in text:
        return False
    write(path, text.replace(old, new))
    return True


def replace_lines(path, rules):
    if not os.path.isfile(path):
        return False
    text = read(path)
    new = text
    for pattern, repl in rules:
        new = re.sub(pattern, lambda match: repl, new, flags=re.MULTILINE)
    if new != text:
        write(path, new)
        return True
    return False


def main():
    if not IP:
        raise SystemExit('TARGET_IP missing')
    changed = set()

    # 1) 目标 IP 替换
    for p in IP_FILES:
        if os.environ.get('PRESERVE_SITE_CONFIG') == '1' and p in (
                '/data/Config_files/config.ini', '/data/Config_files/config.js',
                '/data/platform_algorithm_start/config/ApiConfig.ini',
                '/data/config_dispatch/security-settings.json'):
            continue
        if replace_literal(p, OLD_IP, IP):
            changed.add(p)

    # 2) INI 口令
    if replace_lines('/data/Config_files/config.ini', [
            (r'^DB_PASSWORD\s*=.*$', 'DB_PASSWORD = ' + DB_ROOT),
            (r'^Box_password\s*=.*$', 'Box_password = ' + BOX_PASS)]):
        changed.add('/data/Config_files/config.ini')
    if replace_lines('/data/platform_algorithm_start/config/ApiConfig.ini', [
            (r'^db_password=.*$', 'db_password=' + DB_ROOT)]):
        changed.add('/data/platform_algorithm_start/config/ApiConfig.ini')

    # 3) Python 配置
    if replace_lines('/data/model_algorithm_package/Conf_files.py', [
            (r'^DB_PASSWORD\s*=\s*.*$', 'DB_PASSWORD = ' + repr(DB_ROOT)),
            (r'^Box_password\s*=\s*.*$', 'Box_password = ' + repr(BOX_PASS))]):
        changed.add('/data/model_algorithm_package/Conf_files.py')
    # 4) 兜底替换（其余脚本中残留的旧口令）
    for path in set(IP_FILES + glob.glob('/data/model_algorithm_package/*.py')):
        if not os.path.isfile(path):
            continue
        if os.environ.get('PRESERVE_SITE_CONFIG') == '1' and path in ('/data/Config_files/config.ini', '/data/Config_files/config.js', '/data/platform_algorithm_start/config/ApiConfig.ini', '/data/config_dispatch/security-settings.json'):
            continue
        text = read(path)
        for placeholder, value in (('__ONECLICK_DB_PASSWORD__', DB_ROOT), ('__ONECLICK_BOX_PASSWORD__', BOX_PASS)):
            if path.endswith('.py'):
                text = text.replace(repr(placeholder), repr(value)).replace('"' + placeholder + '"', repr(value))
            else:
                text = text.replace(placeholder, value)
        write(path, text)
    # 5) 前端主机白名单
    host_line = "var HOSTS = ['192.168.110.47', '127.0.0.1', 'localhost'];"
    new_host_line = "var HOSTS = ['" + IP + "', '192.168.110.47', '127.0.0.1', 'localhost'];"
    if replace_literal('/data/Config_files/secure-transport.js', host_line, new_host_line):
        changed.add('/data/Config_files/secure-transport.js')

    # 6) 权限
    os.system('chmod 644 /data/Config_files/config.ini /data/Config_files/config.js /data/Config_files/nginx.conf /data/Config_files/zlk/config.ini 2>/dev/null')
    os.system('chmod 600 /data/Config_files/platform-security.json /data/config_dispatch/security-settings.json 2>/dev/null')
    os.system('chmod 644 /data/Config_files/secure-transport.js 2>/dev/null')
    print('APPLIED_CONFIG_FILES=' + ','.join(sorted(changed)))
    print('CONFIG_DONE')


if __name__ == '__main__':
    main()
