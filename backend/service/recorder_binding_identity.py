"""Identify recorder channels and stream owners without using a shared IP."""


def channel_key(value):
    text = str(value).strip() if value is not None else ''
    return str(int(text)) if text.isdigit() else text


def plan_binding_complements(devices, sources):
    """Return (device ID, source ID) pairs only for explicit, unclaimed owners."""
    claimed = {item.zlk_dat_id for item in devices if item.zlk_dat_id is not None}
    by_owner = {}
    for source in sorted(sources, key=lambda item: item.id, reverse=True):
        owner = channel_key(source.equipment_id)
        if owner and source.id not in claimed:
            by_owner.setdefault(owner, source.id)
    result = []
    for device in devices:
        if device.zlk_dat_id is not None:
            continue
        source_id = by_owner.get(channel_key(device.id))
        if source_id is not None and source_id not in claimed:
            result.append((device.id, source_id))
            claimed.add(source_id)
    return result
