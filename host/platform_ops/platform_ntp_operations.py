"""Manage the Linux host's existing systemd-timesyncd client."""

from datetime import datetime
import ipaddress
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import threading
import time


UNIT = 'systemd-timesyncd.service'
OTHER_UNITS = ('chrony.service', 'chronyd.service', 'ntp.service', 'ntpd.service', 'ntpsec.service')
DROP_IN = Path('/etc/systemd/timesyncd.conf.d/90-aiplatform-ntp.conf')
SYNC_MARKER = Path('/run/systemd/timesync/synchronized')
HOST_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z')
_LOCK = threading.RLock()
_NO_REQUEST = object()
_pending_marker = _NO_REQUEST


class NtpUnavailable(RuntimeError):
    pass


class NtpConfigNotLoaded(NtpUnavailable):
    pass


def command(*args, strict=False):
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=7)
    except (OSError, subprocess.TimeoutExpired):
        if strict:
            raise NtpUnavailable('主机校时服务暂不可用')
        return None
    if strict and result.returncode:
        raise NtpUnavailable('主机校时服务操作失败')
    return result


def properties(*args):
    result = command(*args)
    if result is None or result.returncode:
        return {}
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def normalize_server(value):
    if not isinstance(value, str):
        raise ValueError('NTP 服务器格式无效')
    value = value.strip()
    if not value:
        return ''
    if '%' not in value:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            pass
    labels = value[:-1].split('.') if value.endswith('.') else value.split('.')
    if len(value) > 253 or not all(HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError('请输入一个主机名、IPv4 或 IPv6 地址')
    if all(label.isdecimal() for label in labels):
        raise ValueError('NTP 服务器 IP 地址无效')
    return value.lower()


def drop_in_bytes():
    if DROP_IN.parent.is_symlink():
        raise NtpUnavailable('平台校时配置目录状态异常')
    try:
        info = DROP_IN.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
        raise NtpUnavailable('平台校时配置文件状态异常')
    return DROP_IN.read_bytes()


def prepare_drop_in_directory():
    directory = DROP_IN.parent
    try:
        directory.mkdir(mode=0o755)
    except FileExistsError:
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise NtpUnavailable('平台校时配置目录状态异常')
        # The first release created this directory under the bridge's 077
        # umask. Repair that exact layout without altering other drop-ins.
        if (info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o700
                and list(directory.iterdir()) == [DROP_IN] and drop_in_bytes() is not None):
            directory.chmod(0o755)
            return True
        return False
    # mkdir respects the bridge umask. The daemon runs as a separate user.
    directory.chmod(0o755)
    return True


def drop_in_content(server, interval=None):
    if not server and interval is None:
        return None
    lines = ['[Time]']
    if server:
        lines += ['NTP=', 'NTP=' + server]
    if interval is not None:
        lines.append('PollIntervalMaxSec=%d' % interval)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def store_drop_in(data):
    if data is None:
        if drop_in_bytes() is not None:
            DROP_IN.unlink()
        return
    prepare_drop_in_directory()
    scratch = None
    try:
        with tempfile.NamedTemporaryFile(dir=DROP_IN.parent, prefix='.aiplatform-ntp-', delete=False) as f:
            scratch = Path(f.name)
            os.fchmod(f.fileno(), 0o644)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        scratch.replace(DROP_IN)
    finally:
        if scratch is not None and scratch.exists():
            scratch.unlink()


def marker():
    try:
        info = SYNC_MARKER.stat()
    except OSError:
        return None
    return info.st_ino, info.st_mtime_ns


def local_time(timestamp=None):
    clock = datetime.now() if timestamp is None else datetime.fromtimestamp(timestamp)
    return clock.astimezone().isoformat(timespec='seconds')


def runtime():
    unit = properties('systemctl', 'show', UNIT, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'UnitFileState')
    others = command('systemctl', 'is-active', *OTHER_UNITS)
    has_other = others is not None and others.returncode == 0
    supported = unit.get('LoadState') == 'loaded' and unit.get('UnitFileState') not in ('masked', 'masked-runtime') and not has_other
    return supported, unit.get('ActiveState') == 'active', unit.get('UnitFileState') in ('enabled', 'enabled-runtime')


def saved_server():
    override = drop_in_bytes()
    if override is None:
        return ''
    return next((line[4:] for line in override.decode('utf-8').splitlines()
                 if line.startswith('NTP=') and line[4:]), '')


def saved_interval():
    override = drop_in_bytes()
    if override is None:
        return None
    for line in override.decode('utf-8').splitlines():
        if line.startswith('PollIntervalMaxSec=') and line[len('PollIntervalMaxSec='):].strip():
            try:
                return int(line.split('=', 1)[1].strip())
            except ValueError:
                return None
    return None


def timesync_status():
    return properties('timedatectl', 'show-timesync', '--all', '-p', 'SystemNTPServers',
                      '-p', 'ServerName', '-p', 'ServerAddress', '-p', 'PollIntervalUSec')


def server_key(value):
    value = value.strip().rstrip('.').lower()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


def source_loaded(server, sync):
    return server_key(server) in {server_key(candidate) for candidate in sync.get('SystemNTPServers', '').split()}


def wait_configured_source(server):
    if not server:
        return
    deadline = time.monotonic() + 5
    while True:
        if source_loaded(server, timesync_status()):
            return
        if time.monotonic() >= deadline:
            raise NtpConfigNotLoaded('主机校时服务未加载所选时间源，请检查校时配置')
        time.sleep(.25)


def status():
    global _pending_marker
    supported, running, autostart = runtime()
    kernel = properties('timedatectl', 'show', '-p', 'Timezone', '-p', 'NTPSynchronized')
    sync = timesync_status() if running else {}
    saved = saved_server()
    configured_loaded = source_loaded(saved, sync) if saved and running else None
    configured_selected = not saved or (configured_loaded and server_key(saved) in
                         {server_key(sync.get('ServerName', '')), server_key(sync.get('ServerAddress', ''))})
    received = marker()
    if _pending_marker is not _NO_REQUEST and received is not None and received != _pending_marker:
        _pending_marker = _NO_REQUEST
    synchronized = bool(supported and running and kernel.get('NTPSynchronized') == 'yes'
                        and configured_selected and _pending_marker is _NO_REQUEST)
    state = 'unavailable' if not supported else 'disabled' if not running else 'synchronized' if synchronized else 'pending'
    return {
        'supported': supported, 'provider': 'systemd-timesyncd' if supported else '',
        'enabled': running, 'auto_start': autostart, 'synchronized': synchronized,
        'server': saved, 'active_server': sync.get('ServerName') or sync.get('ServerAddress', ''),
        'interval': saved_interval(), 'poll_interval': sync.get('PollIntervalUSec', ''),
        'configured_server_loaded': configured_loaded,
        'host_time': local_time(), 'timezone': kernel.get('Timezone', ''),
        'last_sync': local_time(received[1] / 1e9) if received is not None else None, 'state': state,
    }


def change_unit(action, *flags):
    return command('systemctl', action, *flags, UNIT, strict=True)


def apply_config(server, enabled, interval=None):
    global _pending_marker
    supported, running, autostart = runtime()
    if not supported:
        raise NtpUnavailable('当前主机未使用可由平台管理的 systemd-timesyncd 服务')
    old = drop_in_bytes()
    new = drop_in_content(server, interval)
    previous_pending = _pending_marker
    changed = new != old
    restarted = False
    control_changed = enabled != running or enabled != autostart
    try:
        prepared = prepare_drop_in_directory() if server else False
        restarted = enabled and running and (changed or prepared or (server and not source_loaded(server, timesync_status())))
        if changed:
            store_drop_in(new)
        if enabled and (not running or restarted):
            _pending_marker = marker()
        if control_changed:
            change_unit('enable' if enabled else 'disable', '--now')
        if restarted:
            change_unit('restart')
        if enabled:
            wait_configured_source(server)
        else:
            _pending_marker = _NO_REQUEST
    except (OSError, NtpUnavailable) as failure:
        _pending_marker = previous_pending
        try:
            if changed:
                store_drop_in(old)
            if control_changed:
                change_unit('enable' if autostart else 'disable')
                change_unit('start' if running else 'stop')
            elif restarted:
                change_unit('restart')
        except (OSError, NtpUnavailable):
            raise NtpUnavailable('校时配置保存失败，主机服务恢复待确认') from failure
        if isinstance(failure, NtpConfigNotLoaded):
            raise NtpUnavailable('主机校时服务未加载所选时间源，已恢复原配置') from failure
        raise NtpUnavailable('校时配置保存失败，已恢复原配置') from failure


def request_sync():
    global _pending_marker
    supported, running, _ = runtime()
    if not supported or not running:
        raise NtpUnavailable('请先启用主机 NTP 校时')
    server = saved_server()
    if server:
        prepare_drop_in_directory()
    initial = marker()
    change_unit('restart')
    _pending_marker = initial
    wait_configured_source(server)


def dispatch(method, path, body):
    try:
        with _LOCK:
            if (method, path) == ('GET', '/ntp/status'):
                if body:
                    raise ValueError('状态查询不接收参数')
            elif (method, path) == ('POST', '/ntp/config'):
                if set(body) - {'server', 'enabled', 'interval'} or 'server' not in body or 'enabled' not in body:
                    raise ValueError('请提供 NTP 服务器和启用状态')
                if type(body['enabled']) is not bool:
                    raise ValueError('启用状态必须为布尔值')
                interval = body.get('interval')
                if interval is not None and (isinstance(interval, bool) or not isinstance(interval, int)
                                             or not 33 <= interval <= 604800):
                    raise ValueError('自动校时间隔需为 33 至 604800 秒的整数')
                apply_config(normalize_server(body['server']), body['enabled'], interval)
            elif (method, path) == ('POST', '/ntp/sync'):
                if body:
                    raise ValueError('立即校时使用已保存的服务器')
                request_sync()
            else:
                return 404, {'code': 404, 'msg': '校时操作不存在'}
            return 200, {'code': 200, 'data': status()}
    except ValueError as error:
        return 400, {'code': 400, 'msg': str(error)}
    except NtpUnavailable as error:
        return 503, {'code': 503, 'msg': str(error)}
    except OSError:
        return 503, {'code': 503, 'msg': '无法读取或保存主机校时配置'}
