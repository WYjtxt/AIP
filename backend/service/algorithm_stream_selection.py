"""Configuration-level stream selection; no camera/proxy/task mutations."""
from urllib.parse import quote, urlsplit

from data.exts import db
from model.algorithm import Algorithm_config
from model.equipment import Equipment, VCR_data, Hik_security_platform_info, Hik_security_platform_up_area
from model.extra import Zlk_data
from service.algorithm_stream_source import normalize_stream_type, infer_stream_type, select_stream_url, recover_direct_camera_url


def _source_equipment(equipment_id):
    selected = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
    if selected is None:
        raise ValueError('监控点不存在')
    # The server already has verified same-camera aliases. Reuse that read-only
    # validation for explicit stream snapshots and direct-camera source lookup.
    from service import algorithm_model_service
    verifier = getattr(algorithm_model_service, '_verified_stream_source', None)
    source = (verifier(selected) if verifier else selected) or selected
    if source.id != selected.id:
        bound = (db.session.query(Zlk_data).filter(Zlk_data.id == source.zlk_dat_id).first()
                 if getattr(source, 'zlk_dat_id', None) else None)
        try:
            proxy = urlsplit(str(getattr(bound, 'zlk_rtsp', None) or ''))
            valid = (bound and str(getattr(bound, 'equipment_id', None)) == str(source.id)
                     and proxy.scheme in ('rtsp', 'rtsps') and proxy.hostname
                     and proxy.path.startswith('/openUrl/') and proxy.username is None)
        except ValueError:
            valid = False
        if not valid:
            source = selected
    return selected, source


def _native_url(equipment_id):
    selected, source = _source_equipment(equipment_id)
    if getattr(source, 'zlk_dat_id', None):
        stream = db.session.query(Zlk_data).filter(Zlk_data.id == source.zlk_dat_id).first()
        if (stream and str(getattr(stream, 'equipment_id', None)) == str(source.id)
                and getattr(stream, 'cameras_rtsp', None)):
            if infer_stream_type(stream.cameras_rtsp):
                return stream.cameras_rtsp
            # Original IPC registration saved a bare root URI. Only recover a
            # known direct-camera family on that exact registered host and port.
            return recover_direct_camera_url(stream.cameras_rtsp, {
                key: getattr(source, key, None) for key in
                ('equipment_type', 'manufacturer_type', 'equipment_ip', 'equipment_port')})
    # Match the existing inference loader's source metadata, including NVR
    # account/channel ownership. This fallback never rewrites a ZLK proxy path.
    is_nvr = str(selected.equipment_type) == '录像机'
    vcr = (db.session.query(VCR_data).filter(VCR_data.id == selected.VCR_data_id).first()
           if is_nvr and selected.VCR_data_id else None)
    manufacturer = (getattr(vcr, 'vcr_type', None) or selected.manufacturer_type)
    host = getattr(vcr, 'vcr_ip', None) or selected.equipment_ip
    user = getattr(vcr, 'vcr_username', None) or selected.equipment_uname or ''
    password = getattr(vcr, 'vcr_password', None) or selected.equipment_password or ''
    if not host or str(selected.equipment_type) not in ('录像机', '摄像头', '特殊摄像头'):
        raise ValueError('该视频来源不支持已确认的主/子码流切换，请沿用原地址')
    port = 554 if is_nvr else selected.equipment_port or 554
    auth = '{}:{}@'.format(quote(str(user), safe=''), quote(str(password), safe='')) if user else ''
    authority = '[{}]'.format(host) if ':' in str(host) else str(host)
    base = 'rtsp://{}{}:{}'.format(auth, authority, port)
    aisle = int(selected.equipment_aisles or 0)
    if manufacturer == '海康':
        code = str(selected.code or '')
        channel = code if is_nvr and code.isdigit() else '{}01'.format(aisle or 1) if is_nvr else '101'
        return base + '/Streaming/Channels/' + channel
    if manufacturer == '宇视':
        return base + '/unicast/c{}/s0/live'.format(aisle or 1) if is_nvr else base + '/video1'
    if manufacturer == '大华':
        return base + '/cam/realmonitor?channel={}&subtype=0'.format(aisle or 1 if is_nvr else 1)
    raise ValueError('该视频来源不支持已确认的主/子码流切换，请沿用原地址')


def selected_snapshot_url(equipment_id, stream_type):
    choice = normalize_stream_type(stream_type)
    if choice is None:
        return None
    selected = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
    if selected and str(getattr(selected, 'equipment_type', None)) == '安防平台':
        return hik_snapshot_url(selected, choice)
    return select_stream_url(_native_url(equipment_id), choice)


# native_hik_stream integration
def hik_snapshot_url(selected, choice=None):
    from service.algorithm_platform_source import (HikSnapshotUrl, resolve_hik_platform_url,
                                                   stable_hik_fallback)
    if selected is None:
        raise ValueError('监控点不存在')
    try:
        url = resolve_hik_platform_url(_hik_platform_config(selected),
                                       selected.Hik_indexCode, choice or 'main')
    except ValueError:
        fallback = stable_hik_fallback(getattr(selected, 'Hik_rtsp_url', None))
        if choice is not None or not fallback:
            raise
        url = fallback
    return HikSnapshotUrl(url)


def _hik_platform_config(selected):
    area = db.session.query(Hik_security_platform_up_area).filter(
        Hik_security_platform_up_area.id == selected.Hik_id).first() if selected.Hik_id else None
    platform_id = getattr(area, 'hik_info_id', None)
    platform = db.session.query(Hik_security_platform_info).filter(
        Hik_security_platform_info.id == platform_id).first() if platform_id else None
    values = {key: getattr(platform, key, None) for key in
              ('hik_host', 'hik_port', 'hik_appKey', 'hik_appSecret', 'hik_artemis')}
    if not selected.Hik_indexCode or not all(values[key] for key in
                                             ('hik_host', 'hik_appKey', 'hik_appSecret')):
        raise ValueError('安防平台接入信息不完整，请同步监控点并检查平台授权')
    return values


def snapshot_identity(equipment_id, stream_type):
    choice = normalize_stream_type(stream_type)
    return '{}_{}'.format(equipment_id, choice) if choice else equipment_id


def stream_options(equipment_id):
    selected = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
    if selected and str(getattr(selected, 'equipment_type', None)) == '安防平台':
        try:
            _hik_platform_config(selected)
            return {'current_source_stream_type': None, 'recommended_stream_type': 'main',
                    'stream_source_kind': 'hik_platform_api',
                    'stream_type_options': [{'value': 'main', 'label': '主码流'},
                                            {'value': 'sub', 'label': '子码流'}]}
        except ValueError as exc:
            return {'current_source_stream_type': None, 'recommended_stream_type': None,
                    'stream_source_kind': 'hik_platform_api', 'stream_type_options': [],
                    'stream_capability_reason': str(exc)}
    try:
        current = infer_stream_type(_native_url(equipment_id))
    except (ValueError, TypeError):
        current = None
    supported = current is not None
    kind = 'native_rtsp' if supported else 'unconfirmed'
    capability_source = _source_equipment(equipment_id)[1] if supported and selected else None
    if capability_source and str(getattr(capability_source, 'equipment_type', None)) in ('摄像头', '特殊摄像头') and getattr(capability_source, 'zlk_dat_id', None):
        bound = db.session.query(Zlk_data).filter(Zlk_data.id == capability_source.zlk_dat_id).first()
        if bound and str(getattr(bound, 'equipment_id', None)) == str(capability_source.id) and not infer_stream_type(getattr(bound, 'cameras_rtsp', None)):
            current = None  # A bare URI does not identify the old default mode.
            kind = 'direct_camera_standard'
    reason = ('ONVIF 接入目前只有一个取流地址，未取得可确认的主/子码流配置' if
              selected and getattr(selected, 'Onvif_rtsp_url', None) else
              '此来源尚未提供可确认的主/子码流地址或接口，当前输入地址保持不变')
    return {'current_source_stream_type': current,
            'stream_source_kind': kind,
            'stream_capability_reason': '' if supported else reason,
            'recommended_stream_type': 'main' if supported else None,
            'stream_type_options': ([{'value': 'main', 'label': '主码流'},
                                     {'value': 'sub', 'label': '子码流'}] if supported else [])
                                  + [{'value': 'legacy', 'label': '沿用原地址'}]}


def _validate_shared_output_choice(equipment_id, choice, config_id=None):
    # Publishing is keyed by equipment ID. Different input URLs would create
    # separate decoder workers competing for the same output stream. Treat
    # legacy and explicit selection as different even when their frames look
    # similar: the legacy source can be a forwarding proxy with a different URL.
    query = db.session.query(Algorithm_config.id, Algorithm_config.stream_type).filter(
        Algorithm_config.Equipment_id == equipment_id, Algorithm_config.status == '1')
    if config_id:
        query = query.filter(Algorithm_config.id != config_id)
    for row in query.all():
        if normalize_stream_type(row.stream_type) != choice:
            raise ValueError('该监控点已有运行配置使用其他输入码流，请保持同源，避免分析推流冲突')


def prepare_stream_type(payload, equipment_id, config_id=None, models=None):
    """Omitted edit fields keep existing selection; explicit null means legacy."""
    old = (db.session.query(Algorithm_config).filter(Algorithm_config.id == config_id).first()
           if config_id else None)
    candidates = [m['stream_type'] for m in models or [] if 'stream_type' in m]
    if 'stream_type' in payload:
        choice = normalize_stream_type(payload.get('stream_type'))
    elif candidates:
        choice = normalize_stream_type(candidates[0])
    elif old is not None:
        choice = normalize_stream_type(getattr(old, 'stream_type', None))
    else:
        choice = None  # Omitted new choices conservatively keep the existing input.
    if any(normalize_stream_type(value) != choice for value in candidates):
        raise ValueError('同一配置的多个算法模型必须使用相同码流')
    if choice is not None:
        selected_snapshot_url(equipment_id, choice)  # Reject unsupported sources before writes.
    _validate_shared_output_choice(equipment_id, choice, config_id)
    return choice
