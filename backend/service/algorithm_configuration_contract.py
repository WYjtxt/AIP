"""Contracts for the installed stream scheduler and its per-task callbacks."""
import hashlib
import json
import time
from pathlib import Path

try:
    from .count_algorithm_family import is_count_model_name
except ImportError:
    from count_algorithm_family import is_count_model_name

KINDS = {'人员尾随': 'tailgating', '唯一性尾随': 'tailgating',
         '违规跨越': 'crossing', '唯一性违规跨越': 'crossing'}

def field(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)

def runtime_issue(template, advanced=False):
    name = str(field(template, 'model_name', '') or '').strip()
    type_id = str(field(template, 'model_template_config_type_id', ''))
    # SITE_PATCH_GATE_WIZARD_V1: legacy gate template enabled for 新增算法配置 wizard
    # SITE_PATCH_GATE_WIZARD_V2: legacy gate templates enabled for 新增算法配置 wizard
    if type_id == '4' and name in ('闸机尾随', '跨越闸机'):
        return ''
    if type_id == '1':
        return ''
    if type_id == '3' and is_count_model_name(name):
        return ''
    if type_id == '4' and name in KINDS:
        return '当前算能平台尚未提供人员尾随、违规跨越的 BM1684X INT8 模型'
    if type_id == '4' and name == '领导换班':
        return ('{}不支持旧高级多模型组合，请在新增配置中选择多个算法，为同一摄像机创建独立任务'.format(name)
                if advanced else '')
    return '{}尚未接入当前服务器的运行模板，不能按通用检测启动'.format(name or '所选模板')

def observed_runtime(config, reports, kind=None, state_root=None, now=None):
    """Enablement is not proof of healthy inference. Reads never start tasks."""
    result = dict(runtime_healthy=None, runtime_state='starting', runtime_message='正在等待画面、推理和输出状态')
    if str(field(config, 'status')) not in ('1', '运行'):
        result.update(runtime_state='stopped', runtime_message='任务已停止')
        return result
    if str(field(config, 'conf_status', '1')) != '1':
        result.update(runtime_message='配置已保存，正在等待运行进程应用')
        return result
    report = reports.get(str(field(config, 'id'))) or {}
    if not report or str(report.get('model_status')) != str(field(config, 'model_status')):
        return result
    result.update(runtime_state=report.get('state') or 'starting',
                  runtime_message=report.get('reason_text') or result['runtime_message'])
    if not report.get('healthy'):
        if str(report.get('model_status')) == '3' or report.get('state') in ('startup_timeout', 'output_timeout'):
            result['runtime_healthy'] = False
        return result
    if kind:
        root = Path(state_root or '/data/AIGO/platform_start/platform_ops/state/uniqueness')
        now = time.time() if now is None else now
        try:
            health = json.loads((root / ('health-%s.json' % field(config, 'id'))).read_text(encoding='utf-8'))
            cfg = json.loads((root / ('config-%s.json' % field(config, 'id'))).read_text(encoding='utf-8'))
            digest = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
            current = (health.get('generation') == report.get('generation') and bool(health.get('generation'))
                       and health.get('config_hash') == digest and health.get('kind') == kind
                       and health.get('conf_id') == field(config, 'id')
                       and 0 <= now - float(health.get('updated', 0)) <= 15)
            if not current:
                raise ValueError('stale health')
            if health.get('status') in ('startup_failed', 'error'):
                result.update(runtime_healthy=False, runtime_state='startup_failed',
                              runtime_message='专用算法处理失败，请检查模型或运行日志（%s）' % health.get('error', '处理异常'))
                return result
            if (health.get('status') != 'running' or health.get('frames', 0) < 1
                    or not 0 <= now - float(health.get('last_frame', 0)) <= 15):
                raise ValueError('no recent algorithm result')
        except (OSError, ValueError, TypeError, KeyError):
            result.update(runtime_state='starting', runtime_message='视频流程已运行，正在等待专用算法处理结果')
            return result
    result.update(runtime_healthy=True, runtime_state='healthy',
                  runtime_message=report.get('reason_text') or '画面、算法推理和输出均正常')
    return result
