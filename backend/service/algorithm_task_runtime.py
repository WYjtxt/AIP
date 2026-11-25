"""Read status for the task IDs already on the current page."""

import re

from config import configs
from data.exts import db
from model.algorithm import Algorithm_config
from service.algorithm_runtime_status import with_runtime_status


_PAGE_LIMIT = 300
_ID = re.compile(r'[1-9][0-9]{0,9}\Z')
_DISPLAY_FIELDS = ('id', 'status', 'model_status', 'runtime_state', 'runtime_reason')


def _parse_ids(value):
    parts = value.split(',', _PAGE_LIMIT)
    if len(parts) > _PAGE_LIMIT or any(not _ID.fullmatch(part) for part in parts):
        raise ValueError('运行状态任务编号无效，单次最多查询 300 项')
    ids = tuple(dict.fromkeys(int(part) for part in parts))
    if any(ident > 2147483647 for ident in ids):
        raise ValueError('运行状态任务编号无效')
    return ids


@with_runtime_status
def _runtime_data(ids):
    task = Algorithm_config
    records = db.session.query(task.id, task.status, task.model_status, task.conf_status,
                               task.Equipment_id, task.Algorithm_library_id).filter(task.id.in_(ids)).all()
    rows = []
    for item in records:
        try:
            index = int(item.status) - 1
            status = configs.status[index]['value'] if index >= 0 else None
        except (TypeError, ValueError, IndexError):
            continue
        if status not in ('运行', '停止'):
            continue
        rows.append({'id': item.id, 'status': status, 'model_status': item.model_status or 1,
                     'conf_status': item.conf_status or '', 'Equipment_id': item.Equipment_id,
                     'Algorithm_library_id': item.Algorithm_library_id})
    return {'code': 200, 'data_list': {'data': rows}}


def algorithm_task_runtime(value):
    try:
        ids = _parse_ids(value)
    except ValueError as error:
        return {'code': 400, 'msg': str(error)}
    result = _runtime_data(ids)
    page = result['data_list']
    page['data'] = [{field: row.get(field) for field in _DISPLAY_FIELDS} for row in page['data']]
    return result
