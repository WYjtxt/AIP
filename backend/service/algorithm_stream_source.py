"""Pure RTSP main/sub selection shared by snapshots and the inference loader.

Legacy selection preserves the complete original URL. Explicit selection only
rewrites documented camera URL families; forwarding/output URLs are not guessed.
Hikvision: channel*100+1/+2; Uniview NVR s0/s1; Dahua subtype 0/1.
"""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_stream_type(value):
    if value is None or value == '' or value == 'legacy':
        return None
    if value in ('main', 'sub'):
        return value
    raise ValueError('码流类型必须是主码流、子码流或沿用原地址')


def _stream_family(url):
    try:
        parsed = urlsplit(str(url or ''))
        if parsed.scheme not in ('rtsp', 'rtsps') or not parsed.hostname:
            return None, None, None
        path = parsed.path
        match = re.fullmatch(r'(/(?:ISAPI/)?Streaming/(?:Unicast/)?Channels/)([0-9]+)(/?)', path, re.I)
        if match and len(match.group(2)) >= 3 and int(match.group(2)[:-2]) > 0:
            suffix = match.group(2)[-2:]
            if suffix in ('01', '02'):
                return parsed, ('hik', match), 'main' if suffix == '01' else 'sub'
        match = re.fullmatch(r'(/unicast/c[0-9]+/s)([01])(/live/?)', path, re.I)
        if match:
            return parsed, ('unv_nvr', match), 'main' if match.group(2) == '0' else 'sub'
        match = re.fullmatch(r'(/(?:media/)?video)([12])(/?)', path, re.I)
        if match:
            return parsed, ('unv_ipc', match), 'main' if match.group(2) == '1' else 'sub'
        if path.lower() == '/cam/realmonitor':
            values = parse_qsl(parsed.query, keep_blank_values=True)
            channels = [v for k, v in values if k.lower() == 'channel']
            subtype = [v for k, v in values if k.lower() == 'subtype']
            if (len(channels) == len(subtype) == 1 and channels[0].isdigit()
                    and int(channels[0]) > 0 and subtype[0] in ('0', '1')):
                return parsed, ('dahua', values), 'main' if subtype[0] == '0' else 'sub'
    except (ValueError, TypeError):
        pass
    return None, None, None


def infer_stream_type(url):
    return _stream_family(url)[2]


def recover_direct_camera_url(url, metadata):
    """Expand a same-host bare IPC URI using its registered manufacturer.

    A root URI is produced by the original IPC registration code. Custom paths,
    opaque platform URLs, NVR channels, and foreign hosts are never inferred.
    Keep the bound authority (including escaped credentials and RTSP port).
    """
    try:
        parsed = urlsplit(str(url or ''))
        host = str(metadata.get('equipment_ip') or '').strip().strip('[]')
        port = int(metadata.get('equipment_port') or 554)
        actual_port = 554 if parsed.port is None else parsed.port
        valid = (str(metadata.get('equipment_type')) in ('摄像头', '特殊摄像头')
                 and parsed.scheme in ('rtsp', 'rtsps') and parsed.hostname
                 and parsed.hostname.lower() == host.lower()
                 and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                 and 1 <= port <= 65535 and actual_port == port)
        vendor = metadata.get('manufacturer_type')
        paths = {'海康': '/Streaming/Channels/101', '宇视': '/video1',
                 '大华': '/cam/realmonitor'}
        if valid and vendor in paths:
            return urlunsplit((parsed.scheme, parsed.netloc, paths[vendor],
                'channel=1&subtype=0' if vendor == '大华' else '', ''))
    except (ValueError, TypeError):
        pass
    raise ValueError('无法确认该来源的主/子码流地址，请检查接入配置或提供码流接口')


def select_stream_url(url, stream_type):
    choice = normalize_stream_type(stream_type)
    if choice is None:
        return url
    parsed, family, _ = _stream_family(url)
    if parsed is None:
        raise ValueError('该视频来源不支持已确认的主/子码流切换，请沿用原地址')
    kind, value = family
    if kind == 'hik':
        path = value.group(1) + value.group(2)[:-2] + ('01' if choice == 'main' else '02') + value.group(3)
        query = parsed.query
    elif kind in ('unv_nvr', 'unv_ipc'):
        index = ('0' if choice == 'main' else '1') if kind == 'unv_nvr' else ('1' if choice == 'main' else '2')
        path = value.group(1) + index + value.group(3)
        query = parsed.query
    else:
        path = parsed.path
        query = urlencode([(k, ('0' if choice == 'main' else '1') if k.lower() == 'subtype' else v)
                           for k, v in value])
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))
