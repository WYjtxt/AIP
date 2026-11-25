"""Display current lifecycle without interpreting initialization as failure."""
import functools
import json
import time
from pathlib import Path


def read_report_snapshot(path='/data/AIGO/platform_runtime_health/health.json', now=None):
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            return None
        data = json.loads(raw)
        epoch = float(data['epoch'])
        age = (time.time() if now is None else now) - epoch
        if not 0 <= age <= 20:
            return None
        return epoch, {str(row['conf_id']): row for row in data['tasks']}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_reports(path='/data/AIGO/platform_runtime_health/health.json', now=None):
    snapshot = read_report_snapshot(path, now)
    return snapshot[1] if snapshot else {}


def decorate_row(row, reports, kind=None, output_states=None):
    row.update(runtime_state=None, runtime_reason=None)
    # Stop requests always take precedence over a previous worker's telemetry.
    if str(row.get('status')) not in ('1', '运行'):
        return row
    from service.algorithm_configuration_contract import observed_runtime
    report = reports.get(str(row.get('id'))) or {}
    stored = str(row.get('model_status'))
    if stored == '3' and not report:
        row.update(runtime_state='error', runtime_reason='调度器报告异常，尚无新的任务心跳')
        return row
    observed = observed_runtime(row, reports, kind)
    healthy = observed['runtime_healthy']
    state, message = observed['runtime_state'], observed['runtime_message']
    if not report and stored == '1':
        state, message = 'health_unknown', '尚未收到该任务的近期推理心跳'
    if healthy is True and report.get('push_required', True):
        output = 'unknown' if output_states is None else output_states.get(str(row.get('Equipment_id')), 'offline')
        if output == 'unknown':
            healthy, state, message = None, 'output_unknown', '推理正常，流媒体服务暂未返回分析推流状态'
        elif output != 'online':
            healthy, state = False, 'output_offline'
            message = '推理正常，分析推流尚无可用的视频轨' if output == 'no_video' else '推理正常，分析推流未在流媒体服务注册'
    row.update(runtime_state=state, runtime_reason=message,
               model_status=1 if healthy is True else 3 if healthy is False else 2)
    return row


def with_runtime_status(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        result = function(*args, **kwargs)
        if not isinstance(result, dict) or result.get('code') != 200:
            return result
        reports = read_reports()
        from service.algorithm_configuration_contract import KINDS
        from data.exts import db
        from model.algorithm import Algorithm_library
        kinds = {str(library.id): KINDS.get(library.model_name)
                 for library in db.session.query(Algorithm_library).all()}
        page = result.get('data_list') or {}
        rows = list(page.get('data', [])) if isinstance(page, dict) else []
        detail = result.get('datalist')
        if isinstance(detail, dict):
            rows.append(detail)
        output_states = None
        required = {str(row.get('Equipment_id')) for row in rows
                    if str(row.get('status')) in ('1', '运行') and
                    (reports.get(str(row.get('id'))) or {}).get('healthy') is True and
                    reports[str(row.get('id'))].get('push_required', True)}
        if required:
            from service.analysis_preview_service import ANALYSIS_APP, _matching_media, analysis_output_state
            from service.preview_service import _media_snapshot
            snapshot = _media_snapshot(app=ANALYSIS_APP)
            if snapshot is not None:
                output_states = {equipment: analysis_output_state(_matching_media(snapshot, equipment))
                                 for equipment in required}
        for row in rows:
            decorate_row(row, reports, kinds.get(str(row.get('Algorithm_library_id'))), output_states)
        return result
    return wrapped
