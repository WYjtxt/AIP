"""Apply the receiver's alarm type codes to the existing insertAI wire field."""

import json
from urllib.parse import urlsplit


_INSERT_AI_PATH = '/alarmEvent/insertAI'
_TYPE_CODES = {
    '计数': 26,
    '人员计数': 26,
    '绕行': 27,
    '违规绕行': 27,
    '闸机绕行': 27,
    '人员绕行': 27,
    '尾随': 28,
    '闸机尾随': 28,
    '人员尾随': 28,
    '唯一性尾随': 28,
    '跨越': 29,
    '违规跨越': 29,
    '闸机跨越': 29,
    '唯一性违规跨越': 29,
    '视频质量': 30,
    '视频质量监测': 30,
    '视频质量诊断': 30,
}
_QUALITY_CASES = frozenset(str(code).zfill(4) for code in range(1, 10))


def rewrite_insert_ai_type_code(raw, payload, target_url):
    """Translate the template IDs in the HTTP body at dispatch time."""
    if urlsplit(target_url).path.rstrip('/') != _INSERT_AI_PATH or not isinstance(payload, dict):
        return raw

    quality_case = payload.get('analysis_case')
    name = payload.get('alarmTypeName')
    name = name.strip() if isinstance(name, str) else ''
    # A quality event can carry the library name of the counting task it monitors.
    # 视频质量诊断类报警：推送 templateId=30, templateTypeId=4
    if isinstance(quality_case, str) and quality_case.strip() in _QUALITY_CASES:
        code = 30
        type_code = 4
    elif '人数统计' in name:
        code = 26
        type_code = None
    else:
        code = _TYPE_CODES.get(name)
        type_code = None

    updates = {}
    if code is not None and not (type(payload.get('templateId')) is int and payload['templateId'] == code):
        updates['templateId'] = code
    if type_code is not None and payload.get('templateTypeId') != type_code:
        updates['templateTypeId'] = type_code
    if not updates:
        return raw
    return json.dumps(dict(payload, **updates), ensure_ascii=False, separators=(',', ':'), allow_nan=False)
