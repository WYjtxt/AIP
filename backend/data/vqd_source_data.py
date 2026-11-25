"""Batch the source lookups without changing video-quality detection behavior."""
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from decimal import Decimal, InvalidOperation


def _source(equipment, binding):
    # Reuse only a relay associated with this exact device; never create proxies.
    if binding and str(getattr(binding, 'equipment_id', '')) == str(equipment.id):
        relay = getattr(binding, 'zlk_rtsp', '') or ''
        if relay:
            from urllib.parse import urlsplit
            try:
                parsed = urlsplit(relay)
                if parsed.scheme in ('rtsp', 'rtsps') and parsed.hostname and parsed.path.startswith('/openUrl/'):
                    return relay
            except ValueError:
                pass
    if binding and binding.cameras_rtsp:
        return binding.cameras_rtsp
    return (equipment.Hik_rtsp_url or equipment.Ziguang_ape_rtsp_url
            or equipment.Onvif_rtsp_url or '')


def video_stream_data():
    pairs = db.session.query(Equipment, Zlk_data).outerjoin(
        Zlk_data, Zlk_data.id == Equipment.zlk_dat_id).order_by(Equipment.id).all()
    data = []
    for equipment, binding in pairs:
        source = _source(equipment, binding)
        if source:
            data.append({'id': equipment.id, 'ip': equipment.equipment_ip or '',
                         'name': equipment.equipment_name or '',
                         'parent_ip': equipment.parent_id or '',
                         'rtsp': source, 'parent_name': ''})
    return data


def refresh_video_sources(items):
    # Original code accepts numeric JSON IDs and numeric strings; missing/false
    # IDs and unregistered items retain the caller's original values.
    def key(value):
        if not value:
            return None
        try:
            number = Decimal(int(value)) if isinstance(value, bool) else Decimal(str(value).strip())
            return int(number) if number.is_finite() and number == number.to_integral_value() else None
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            return None
    ids = {key(item.get('id')) for item in items}
    ids.discard(None)
    pairs = (db.session.query(Equipment, Zlk_data).outerjoin(
        Zlk_data, Zlk_data.id == Equipment.zlk_dat_id).filter(Equipment.id.in_(ids)).all()
             if ids else [])
    sources = {equipment.id: _source(equipment, binding) for equipment, binding in pairs}
    for item in items:
        source = sources.get(key(item.get('id')))
        if source:
            item['rtsp'] = source
    return items
