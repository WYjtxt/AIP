#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read hardware identity and validate the existing Huawei driver account."""
import argparse
import json
from pathlib import Path
import re
import shlex
import stat
import subprocess

HUAWEI_USER = 'HwHiAiUser'
# SC5/BM1684 and SC7/BM1684X; avoid matching Sophgo CPU/root-complex IDs.
SOPHGO_PCI_IDS = frozenset((('1e30', '1684'), ('1f1c', '1686')))


def _read(path):
    try:
        return path.read_text('utf-8', errors='replace').strip()
    except (OSError, ValueError):
        return ''


def detect_profile(os_release='/etc/os-release', pci_root='/sys/bus/pci/devices', dev_root='/dev'):
    values = {}
    for line in _read(Path(os_release)).splitlines():
        key, separator, value = line.partition('=')
        if separator and key == 'ID':
            try:
                parsed = shlex.split(value)
                values[key] = parsed[0] if len(parsed) == 1 else ''
            except ValueError:
                pass
    evidence = []
    try:
        devices = sorted(Path(pci_root).iterdir())
    except OSError:
        devices = []
    for device in devices:
        vendor = _read(device / 'vendor').lower()
        if vendor.startswith('0x'):
            vendor = vendor[2:]
        identifier = _read(device / 'device').lower()
        if identifier.startswith('0x'):
            identifier = identifier[2:]
        if (vendor, identifier) in SOPHGO_PCI_IDS:
            evidence.append('PCI %s %s:%s' % (device.name, vendor, identifier))
    try:
        nodes = sorted(Path(dev_root).iterdir())
    except OSError:
        nodes = []
    for node in nodes:
        if re.fullmatch(r'bm-sophon\d+', node.name):
            try:
                if stat.S_ISCHR(node.stat().st_mode):
                    evidence.append('device ' + node.name)
            except OSError:
                pass
    os_id = values.get('ID', '').lower()
    return {'os_id': os_id, 'is_openeuler': os_id == 'openeuler',
            'has_sophgo': bool(evidence), 'sophgo_evidence': evidence}


def _run(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=15)


def check_huawei_user(profile=None, runner=None):
    profile = detect_profile() if profile is None else profile
    if profile['has_sophgo']:
        return {'status': 'skipped', 'reason': 'sophgo', 'message': '检测到算能卡，跳过华为运行用户验证'}
    if not profile['is_openeuler']:
        return {'status': 'skipped', 'reason': 'not_openeuler', 'message': '非 openEuler，跳过此华为运行用户验证'}
    runner = runner or _run
    try:
        user = runner(['getent', 'passwd', HUAWEI_USER])
        if user.returncode:
            return {'status': 'failed', 'reason': 'user_missing', 'message':
                    '缺少运行用户 HwHiAiUser；请先创建用户及同名组并执行 passwd HwHiAiUser，再重试。已有账号和密码不会自动修改。'}
        fields = user.stdout.strip().split(':')
        if len(fields) != 7 or fields[0] != HUAWEI_USER:
            raise ValueError('invalid_user_entry')
        uid, gid = int(fields[2]), int(fields[3])
        if uid <= 0 or gid <= 0:
            return {'status': 'failed', 'reason': 'privileged_identity', 'message':
                    'HwHiAiUser 必须使用独立的非 root 用户和用户组'}
        shell = fields[6].strip()
        if not shell or shell.rsplit('/', 1)[-1] in ('nologin', 'false'):
            return {'status': 'failed', 'reason': 'login_disabled', 'message':
                    'HwHiAiUser 的登录 shell 不可用；请按华为驱动要求由管理员确认运行用户配置'}
        group = runner(['getent', 'group', HUAWEI_USER])
        if group.returncode:
            return {'status': 'failed', 'reason': 'group_missing', 'message':
                    '缺少同名运行组 HwHiAiUser；请先补齐运行组，再重试'}
        group_fields = group.stdout.strip().split(':')
        if len(group_fields) != 4 or group_fields[0] != HUAWEI_USER:
            raise ValueError('invalid_group_entry')
        group_id = int(group_fields[2])
        membership = runner(['id', '-G', HUAWEI_USER])
        if group_id <= 0 or membership.returncode or str(group_id) not in membership.stdout.split():
            return {'status': 'failed', 'reason': 'group_membership', 'message':
                    'HwHiAiUser 未加入同名运行组，请由管理员核对用户组配置'}
        # Query status only. Never read shadow hashes, ask for a password, or
        # reset credentials of an existing account during deployment.
        password = runner(['passwd', '-S', HUAWEI_USER])
        status_fields = password.stdout.split()
        if password.returncode or len(status_fields) < 2 or status_fields[0] != HUAWEI_USER:
            return {'status': 'failed', 'reason': 'password_status_unavailable', 'message':
                    '无法读取 HwHiAiUser 密码状态；请在 root 终端检查 passwd -S HwHiAiUser'}
        if status_fields[1] not in ('P', 'PS'):
            return {'status': 'failed', 'reason': 'password_not_ready', 'message':
                    'HwHiAiUser 密码尚未设置或账号已锁定；请在 root 终端单独执行 passwd HwHiAiUser 后重试'}
        return {'status': 'passed', 'reason': 'ready', 'uid': uid, 'gid': gid,
                'message': 'HwHiAiUser 用户、运行组及密码状态检查通过；保留现有密码'}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'status': 'failed', 'reason': 'account_check_unavailable', 'message':
                '无法完成 HwHiAiUser 用户验证；请检查 getent、id、passwd 命令及 root 权限'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--probe-json', action='store_true')
    action.add_argument('--shell-env', action='store_true')
    action.add_argument('--check-huawei-user', action='store_true')
    args = parser.parse_args(argv)
    profile = detect_profile()
    if args.probe_json:
        print(json.dumps(profile, ensure_ascii=True))
    elif args.shell_env:
        for key, value in (('PROFILE_OS_ID', profile['os_id']),
                           ('IS_OPENEULER', '1' if profile['is_openeuler'] else '0'),
                           ('HAS_SOPHGO', '1' if profile['has_sophgo'] else '0'),
                           ('SOPHGO_EVIDENCE', '; '.join(profile['sophgo_evidence']))):
            print('export %s=%s' % (key, shlex.quote(value)))
    else:
        result = check_huawei_user(profile)
        print('[%s] %s' % ('FAIL' if result['status'] == 'failed' else ' OK ', result['message']))
        return 1 if result['status'] == 'failed' else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
