"""Recorder inventories retain channel identity when status/metadata is missing."""
import re
import xml.etree.ElementTree as ET
import requests
from requests.auth import HTTPDigestAuth


class InventoryUnavailable(ValueError):
    pass


def channel_key(value):
    value = str(value).strip() if value is not None else ''
    return str(int(value)) if value.isdigit() else None


def inventory_keys(items):
    if not isinstance(items, (list, tuple)) or not items:
        return None
    keys = [channel_key(item.get('id')) if isinstance(item, dict) else None for item in items]
    if None in keys or len(set(keys)) != len(keys):
        return None
    return set(keys)


def channel_code(item):
    value = ''.join(char for char in str(item.get('channelName') or '') if ord(char) >= 32 and ord(char) != 127).strip()
    return value or (channel_key(item.get('id')) or '') + '01'


def channel_name(value, channel, previous=None):
    value = ''.join(char for char in str(value or '') if ord(char) >= 32 and ord(char) != 127).strip()
    placeholder = not value or re.fullmatch(r'Channel\s*\d+', value, flags=re.I)
    if placeholder and previous:
        return previous
    return value or 'Channel ' + str(channel)


def online_value(value, previous=1):
    if value is None or value == '':
        return previous if previous in (0, 1) else 1
    if isinstance(value, bool):
        return int(value)
    return 1 if str(value).strip().lower() in ('1', 'true', 'online', 'yes') else 0


def _tag(element):
    return element.tag.rsplit('}', 1)[-1]


def _child(element, name):
    return next((node for node in element if _tag(node) == name), None)


def _text(element, name, default=None):
    if element is None:
        return default
    child = _child(element, name)
    return child.text.strip() if child is not None and child.text is not None else default


def _root(xml, expected):
    root = ET.fromstring(xml)
    if _tag(root) not in expected:
        raise InventoryUnavailable('录像机通道目录格式不符合 ISAPI 规范，请核对接入方式')
    return root


def parse_hik_inventory(xml):
    root = _root(xml, ('InputProxyChannelList',))
    records = []
    for node in root:
        if _tag(node) != 'InputProxyChannel':
            continue
        channel = channel_key(_text(node, 'id'))
        if channel is None or channel == '0':
            raise InventoryUnavailable('录像机通道目录含有无效通道号，未导入设备')
        descriptor = _child(node, 'sourceInputPortDescriptor')
        address = _text(descriptor, 'ipAddress') or _text(descriptor, 'hostName') or _text(descriptor, 'deviceID') or ''
        records.append(dict(id=channel, name=channel_name(_text(node, 'name'), channel),
                            ip_address=address, username=_text(descriptor, 'userName', ''),
                            managePortNo=_text(descriptor, 'managePortNo', ''), online=None))
    if records and inventory_keys(records) is None:
        raise InventoryUnavailable('录像机通道目录含有重复通道号，未导入设备')
    return records


def merge_hik_inventory(inventory_xml, status_xml=None, streams_xml=None, sip_xml=None):
    records = parse_hik_inventory(inventory_xml)
    by_id = {row['id']: row for row in records}
    if status_xml:
        try:
            root = _root(status_xml, ('InputProxyChannelStatusList',))
            for node in root:
                row = by_id.get(channel_key(_text(node, 'id')))
                if row is not None:
                    value = _text(node, 'online')
                    if value is not None: row['online'] = value
        except (ET.ParseError, InventoryUnavailable, LookupError):
            pass
    if streams_xml:
        try:
            root = _root(streams_xml, ('StreamingChannelList',))
            for node in root:
                video = _child(node, 'Video')
                stream = _text(node, 'id', '')
                channel = channel_key(_text(video, 'dynVideoInputChannelID') or (str(int(stream) // 100) if stream.isdigit() else ''))
                if stream.isdigit() and int(stream) % 100 != 1:
                    continue
                row = by_id.get(channel)
                if row is None: continue
                row['channelName'] = _text(node, 'channelName') or (channel + '01')
                for field in ('videoCodecType', 'videoResolutionWidth', 'videoResolutionHeight', 'constantBitRate'):
                    value = _text(video, field)
                    if value is not None: row[field] = value
                rate = _text(video, 'maxFrameRate')
                if rate is not None:
                    try: row['maxFrameRate'] = str(int(float(rate) / 100)) if float(rate) else '30'
                    except ValueError: pass
        except (ET.ParseError, InventoryUnavailable, LookupError):
            pass
    if sip_xml:
        try:
            root = ET.fromstring(sip_xml)
            for node in root.iter():
                if _tag(node) != 'VideoInput': continue
                row = by_id.get(channel_key(_text(node, 'id')))
                value = _text(node, 'videoInputID')
                if row is not None and value: row['GB28181_code'] = value
        except (ET.ParseError, LookupError):
            pass
    for row in records:
        row['channelName'] = channel_code(row)
    return records


def hik_channels(username, password, ip, port, strict=False):
    try:
        port = int(port or 80)
        if not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, TypeError):
        if strict:
            raise InventoryUnavailable('录像机端口无效，请输入 1 到 65535 之间的端口')
        return None
    origin = 'http://{}:{}'.format(ip, port)
    auth = HTTPDigestAuth(username, password)

    def fetch(path, mandatory=False):
        limit = 4 * 1024 * 1024
        try:
            with requests.get(origin + path, auth=auth, timeout=(4, 12 if mandatory else 3),
                              allow_redirects=False, stream=True) as response:
                status = response.status_code
                if status != 200:
                    if not mandatory:
                        return None
                    reasons = {401: '认证失败，请核对录像机账号和密码', 403: '访问被拒绝，请检查账号读取通道目录的权限',
                               404: '接口不存在，请核对厂商、接入方式及 HTTP 管理端口',
                               301: '接口发生重定向，请核对录像机的 HTTP 管理端口',
                               302: '接口发生重定向，请核对录像机的 HTTP 管理端口'}
                    raise InventoryUnavailable('录像机通道目录{}（HTTP {}）'.format(reasons.get(status, '请求失败'), status))
                body = bytearray()
                for piece in response.iter_content(65536):
                    body.extend(piece)
                    if len(body) > limit:
                        if mandatory:
                            raise InventoryUnavailable('录像机通道目录响应过大，未导入设备')
                        return None
                return bytes(body)
        except requests.Timeout:
            if mandatory:
                raise InventoryUnavailable('读取录像机通道目录超时，请检查地址、端口和网络') from None
        except requests.RequestException:
            if mandatory:
                raise InventoryUnavailable('无法连接录像机通道目录，请检查地址、HTTP 管理端口和网络') from None
        return None

    try:
        inventory = fetch('/ISAPI/ContentMgmt/InputProxy/channels', mandatory=True)
        if not parse_hik_inventory(inventory):
            return []
        status = fetch('/ISAPI/ContentMgmt/InputProxy/channels/status')
        streams = fetch('/ISAPI/Streaming/channels')
        if streams:
            try:
                _root(streams, ('StreamingChannelList',))
            except (ET.ParseError, InventoryUnavailable, LookupError):
                streams = None
        if not streams:
            streams = fetch('/ISAPI/ContentMgmt/StreamingProxy/channels')
        return merge_hik_inventory(inventory, status, streams, fetch('/ISAPI/System/Network/SIP/1/SIPInfo'))
    except InventoryUnavailable:
        if strict:
            raise
    except (ET.ParseError, ValueError, LookupError):
        if strict:
            raise InventoryUnavailable('录像机返回了无效的通道目录，请核对 ISAPI 接口与管理端口') from None
    print('录像机通道清单未完整获取，本轮保留现有设备')
    return None
