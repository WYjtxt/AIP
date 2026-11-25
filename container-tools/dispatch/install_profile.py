"""Exact supported OS/hardware profiles and read-only runtime validation."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess

PROFILES = ('openeuler22.03-sp4-aarch64-ascend310p3', 'ubuntu20.04-x86_64-sc7')


def os_values(path='/etc/os-release'):
    result = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        key, sep, value = line.partition('=')
        if sep and re.fullmatch(r'[A-Z_]+', key):
            parts = shlex.split(value)
            result[key] = parts[0] if len(parts) == 1 else ''
    return result


def select_profile(values, arch, requested='auto'):
    if values.get('ID', '').lower() == 'openeuler' and values.get('VERSION_ID') == '22.03' and \
            re.search(r'(?:LTS[- ]?)?SP4\b', values.get('VERSION', ''), re.I) and arch == 'aarch64':
        selected = PROFILES[0]
    elif values.get('ID', '').lower() == 'ubuntu' and values.get('VERSION_ID') == '20.04' and arch == 'x86_64':
        selected = PROFILES[1]
    else:
        raise ValueError('全量安装仅支持 openEuler 22.03 LTS-SP4/aarch64 或 Ubuntu 20.04/x86_64；检测为 %s %s %s' %
                         (values.get('ID'), values.get('VERSION'), arch))
    if requested not in ('auto', selected):
        raise ValueError('指定安装配置与服务器系统/架构不匹配：' + requested)
    return selected


def pci_devices(root='/sys/bus/pci/devices'):
    records = []
    for path in sorted(Path(root).glob('*')):
        try:
            vendor = (path / 'vendor').read_text().strip().lower().replace('0x', '', 1)
            device = (path / 'device').read_text().strip().lower().replace('0x', '', 1)
        except OSError:
            continue
        records.append({'address': path.name, 'vendor': vendor, 'device': device,
                        'driver': (path / 'driver').resolve().name if (path / 'driver').exists() else ''})
    return records


def validate_sc7_devices(records, expected=3):
    chips = [r for r in records if (r['vendor'], r['device']) == ('1f1c', '1686')]
    if len(chips) != expected:
        raise ValueError('SC7 预期 %d 颗 BM1684X（PCI 1f1c:1686），实际 %d；检查 PCIe、供电和 BIOS，未安装/清理平台' % (expected, len(chips)))
    return chips


def run(argv, timeout=45):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, timeout=timeout)
    if result.returncode:
        raise ValueError('%s 失败：%s' % (argv[0], result.stdout[-3000:]))
    return result.stdout


def check_driver(profile, expected=3):
    if profile == PROFILES[1]:
        chips = validate_sc7_devices(pci_devices(), expected)
        if any(p['driver'] != 'bmsophon' for p in chips):
            raise ValueError('BM1684X PCIe 设备尚未全部绑定 bmsophon 驱动')
        nodes = [p for p in Path('/dev').glob('bm-sophon[0-9]*')
                 if re.fullmatch(r'bm-sophon\d+', p.name) and stat.S_ISCHR(p.stat().st_mode)]
        if len(nodes) != expected:
            raise ValueError('SC7 字符设备数量不匹配：%d，预期 %d' % (len(nodes), expected))
        tool = shutil.which('bm-smi') or '/opt/sophon/libsophon-current/bin/bm-smi'
        output = run([tool, '--start_dev=0', '--last_dev=%d' % (expected - 1), '--text_format', '--noloop'])
        if not re.search(r'1684[Xx]|1684x', output) or re.search(r'(?i)\b(fault|error|failed)\b', output):
            raise ValueError('bm-smi 未返回正常 BM1684X 设备信息：' + output[-2000:])
        ctypes.CDLL('/opt/sophon/libsophon-current/lib/libbmlib.so')
        module = run(['modinfo', '-F', 'vermagic', 'bmsophon']).split()[0]
        if module != platform.release():
            raise ValueError('bmsophon 模块与运行内核不匹配')
        return {'profile': profile, 'kernel': platform.release(), 'devices': chips, 'driver': 'passed'}
    output = run(['npu-smi', 'info'])
    if not re.search(r'310[Pp]', output) or re.search(r'(?i)\b(fault|error|failed)\b', output):
        raise ValueError('npu-smi 未返回正常 310P 设备信息：' + output[-2000:])
    if 'OK' not in output:
        raise ValueError('npu-smi 未报告 Health=OK')
    return {'profile': profile, 'kernel': platform.release(), 'driver': 'passed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default=os.environ.get('INSTALL_PROFILE', 'auto'))
    parser.add_argument('--expected-chips', type=int, default=int(os.environ.get('SOPHGO_EXPECTED_CHIPS', '3')))
    parser.add_argument('--driver', action='store_true')
    parser.add_argument('--shell-env', action='store_true')
    args = parser.parse_args()
    profile = select_profile(os_values(), platform.machine(), args.profile)
    if args.driver:
        print(json.dumps(check_driver(profile, args.expected_chips), ensure_ascii=False))
    else:
        records = pci_devices()
        if profile == PROFILES[1]:
            validate_sc7_devices(records, args.expected_chips)
        elif not any(r['vendor'] == '19e5' and r['device'] in ('d500', 'd501') for r in records):
            raise ValueError('未检测到昇腾 310P PCIe 设备，停止自动安装；请先检查 lspci -nn')
        values = {'INSTALL_PROFILE': profile, 'RUNNING_KERNEL': platform.release()}
        if args.shell_env:
            for name, value in values.items():
                print('export %s=%s' % (name, shlex.quote(value)))
        else:
            print(json.dumps(values))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit('[FAIL] ' + str(exc))
