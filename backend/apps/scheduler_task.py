# native-diagnosis-configuration-v1
import ast
import json
import logging
import re

from flask import Blueprint, jsonify, request, has_app_context
from config.configs import *
from service.scheduler_task_service import SchedulerTaskService
from service.diagnosis_scheduler import normalize_status, interval_delta


scheduler_task = Blueprint('scheduler_task', __name__)
logger = logging.getLogger(__name__)


def perform_diagnostic_task(data):
    success, message = SchedulerTaskService.perform_diagnostic_task(data)
    if success:
        print('诊断数据上传完成！')
    else:
        print(message)


def replace_null_with_none(data):
    return SchedulerTaskService.replace_null_with_none(data)


def flatten_equipment_data(tree_data):
    success, result = SchedulerTaskService.flatten_equipment_data(tree_data)
    if success:
        return result
    print(result)
    return []


def run_task(task_id, task_name, task_interval_seconds, time_type, rtsp_list,
             diagnosis_type_list, scheduled_concent, scheduled_status):
    """Compatibility entry point for older jobs; never log camera credentials."""
    args = (task_id, task_name, task_interval_seconds, time_type, rtsp_list,
            diagnosis_type_list, scheduled_concent, scheduled_status)
    try:
        if has_app_context():
            success, message = SchedulerTaskService.run_task(*args)
        else:
            from main import app
            with app.app_context():
                success, message = SchedulerTaskService.run_task(*args)
    except Exception:
        logger.error('诊断任务 %s 执行失败', task_id)
        return False, '诊断任务执行失败'
    if success:
        logger.info('诊断任务 %s 执行成功', task_id)
    else:
        logger.warning('诊断任务 %s 执行失败', task_id)
    return success, message


def _positive_integer(value, field):
    if isinstance(value, bool):
        raise ValueError(field + '必须为正整数')
    text = str(value).strip() if value is not None else ''
    if not re.fullmatch(r'[0-9]+', text):
        raise ValueError(field + '必须为正整数')
    number = int(text)
    if number <= 0:
        raise ValueError(field + '必须为正整数')
    return number


def _nonempty_list(value, field, allow_literal=False):
    try:
        result = json.loads(value)
    except (ValueError, TypeError):
        if not allow_literal:
            raise ValueError(field + '必须为非空JSON数组')
        try:
            result = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError):
            raise ValueError(field + '必须为非空数组')
    if not isinstance(result, list) or not result:
        raise ValueError(field + '必须为非空数组')
    return result


def _task_parameters():
    name = (request.form.get('name') or '').strip()
    if not name:
        raise ValueError('任务名称不能为空')
    interval = _positive_integer(request.form.get('interval_seconds'), '时间间隔')
    time_type = (request.form.get('time_type') or '').strip()
    if time_type not in ('seconds', 'minutes', 'hours', 'days', 'weeks'):
        raise ValueError('时间类型错误')
    interval_delta(interval, time_type)
    status = normalize_status(request.form.get('scheduled_status'))
    sources = _nonempty_list(request.form.get('rtsp_list'), '诊断视频源')
    diagnosis_types = _nonempty_list(
        request.form.get('diagnosis_type_list'), '诊断项目', allow_literal=True)
    return (name, interval, time_type,
            json.dumps(sources, ensure_ascii=False),
            json.dumps(diagnosis_types, ensure_ascii=False),
            request.form.get('scheduled_concent', ''), status)


def _invalid_input(error):
    return jsonify({'code': 400, 'msg': str(error)}), 400


@scheduler_task.route('/add_task', methods=['POST'])
@jwt_required_with_refresh
def add_task():
    try:
        values = _task_parameters()
    except (ValueError, TypeError, OverflowError) as error:
        return _invalid_input(error)
    success, result = SchedulerTaskService.add_task(*values)
    if not success:
        return jsonify({'code': 400, 'msg': result})
    # All workers observe the saved configuration through the shared DB tick.
    return jsonify({'code': 200, 'msg': '任务已添加', 'task_id': result.id})


@scheduler_task.route('/update_task', methods=['POST'])
@jwt_required_with_refresh
def update_task():
    try:
        task_id = _positive_integer(request.form.get('id'), '任务id')
        values = _task_parameters()
    except (ValueError, TypeError, OverflowError) as error:
        return _invalid_input(error)
    # The existing data layer accepts the Chinese labels when updating status.
    values = values[:-1] + ('启用' if values[-1] == 1 else '禁用',)
    success, result = SchedulerTaskService.update_task(task_id, *values)
    if not success:
        return jsonify({'msg': result, 'code': 404})
    return jsonify({'msg': '任务已更新', 'code': 200})


@scheduler_task.route('/delete_task', methods=['POST'])
@jwt_required_with_refresh
def delete_task():
    try:
        submitted_ids = _nonempty_list(
            request.form.get('id'), '任务id', allow_literal=True)
        task_ids = [_positive_integer(value, '任务id') for value in submitted_ids]
        # Only canonical integers reach the legacy service parser.
        canonical_ids = json.dumps(list(dict.fromkeys(task_ids)))
    except (ValueError, TypeError, OverflowError) as error:
        return _invalid_input(error)
    success, message = SchedulerTaskService.delete_task(canonical_ids)
    if not success:
        return jsonify({'msg': message, 'code': 400})
    return jsonify({'msg': message, 'code': 200})


@scheduler_task.route('/show_task', methods=['GET'])
@jwt_required_with_refresh
def show_task():
    name = request.args.get('name')
    time_type = request.args.get('time_type')
    scheduled_status = request.args.get('scheduled_status')
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=15, type=int)
    success, result = SchedulerTaskService.get_tasks(
        page, per_page, name, time_type, scheduled_status)
    if success:
        return jsonify({'code': 200, 'msg': '查询成功', 'data': result})
    return jsonify({'code': 400, 'msg': result})


@scheduler_task.route('/task_detail', methods=['GET'])
@jwt_required_with_refresh
def task_detail():
    task_id = request.args.get('id')
    success, result = SchedulerTaskService.get_task_detail(task_id)
    if success:
        return jsonify({'code': 200, 'msg': '查询成功', 'data': result})
    return jsonify({'code': 400, 'msg': result})
