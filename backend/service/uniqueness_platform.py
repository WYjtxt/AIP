"""Authenticated per-task calibration for the installed uniqueness algorithms."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from functools import wraps
from flask import g, jsonify, request
from data.exts import db
from model.algorithm import Algorithm_config, Algorithm_library
from common.platform_access import has_menu_permission

ROOT = Path('/data/AIGO/platform_start/platform_algorithm_start')
STATE = Path('/data/AIGO/platform_start/platform_ops/state/uniqueness')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from templates.passage_config import validate

KINDS = {'人员尾随': 'tailgating', '违规跨越': 'crossing', '唯一性尾随': 'tailgating', '唯一性违规跨越': 'crossing'}

def calibration_start_guard(function):
    @wraps(function)
    def guarded(payload):
        if hasattr(payload, 'get') and str(payload.get('status')) in ('1', '运行'):
            try:
                value = payload.get('id')
                if str(value).isdigit():
                    task = db.session.query(Algorithm_config).filter_by(id=int(value)).first()
                    if task is not None:
                        require_ready(task)
            except (ValueError, OSError) as error:
                db.session.rollback()
                return {'code': 400, 'msg': str(error)}
        return function(payload)
    return guarded

def kind_for(task):
    library = db.session.query(Algorithm_library).filter_by(id=task.Algorithm_library_id).first()
    return KINDS.get(library.model_name) if library else None

def path_for(task):
    return STATE / ('config-%d.json' % task.id)

def revision(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'new'

def defaults(task, kind):
    return dict(schema_version=1, kind=kind, equipment_id=task.Equipment_id,
                lane_id='lane-%s' % task.Equipment_id, direction='forward', calibrated=False,
                passage_confirmation='gate',crossing_confirmation='obstacle',
                test_mode=True, authorization_mode='video_only', max_fps=20, max_track_gap=.7,
                zone_hits=2, message_delay=1., session_gap=3., action_frames=2, action_duration=.1, support_posture_enabled=False, pose_confidence=.55, detection_confidence=.5,
                entry=[[0,0],[.3,0],[.3,1],[0,1]], gate=[[.3,0],[.7,0],[.7,1],[.3,1]],
                exit=[[.7,0],[1,0],[1,1],[.7,1]], obstacle=[[.3,0],[.7,0],[.7,1],[.3,1]])

def require_ready(task):
    kind = kind_for(task)
    if not kind:
        return
    path = path_for(task)
    if not path.exists():
        raise ValueError('请先在任务配置页完成唯一性检测区域标定并保存')
    cfg = validate(json.loads(path.read_text(encoding='utf-8')), kind)
    if not cfg['calibrated']:
        raise ValueError('唯一性检测尚未完成现场区域标定，不能启动')
    if cfg.get('equipment_id') != task.Equipment_id:
        raise ValueError('摄像机已变化，请重新标定并保存唯一性检测配置')

def read_task(task):
    kind = kind_for(task)
    if not kind:
        raise ValueError('此任务不是唯一性检测算法')
    path = path_for(task)
    cfg = json.loads(path.read_text(encoding='utf-8')) if path.exists() else defaults(task, kind)
    changed = cfg.get('equipment_id') not in (None, task.Equipment_id)
    if changed:
        cfg = defaults(task, kind)
    cfg['equipment_id'] = task.Equipment_id
    health_path = STATE / ('health-%d.json' % task.id)
    health = {}
    if health_path.exists():
        try:
            health = json.loads(health_path.read_text(encoding='utf-8'))
            health['stale'] = time.time() - health.get('updated', 0) > 15
        except (ValueError, OSError):
            pass
    return dict(conf_id=task.id, equipment_id=task.Equipment_id, name=task.conf_name,
                status=str(task.status), model_status=task.model_status, kind=kind,
                configuration=cfg, revision=revision(path), camera_changed=changed, health=health)

def save_task(task, payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('configuration'), dict):
        raise ValueError('配置内容无效')
    if str(task.status) != '2' or task.model_status != 4:
        raise ValueError('请先停止任务并等待停止完成，再修改区域和参数')
    if payload.get('equipment_id') != task.Equipment_id:
        raise ValueError('摄像机已变化，请先保存普通配置，再重新打开本页')
    path = path_for(task)
    if payload.get('revision') != revision(path):
        raise ValueError('配置已被修改，请重新载入后编辑')
    kind = kind_for(task)
    if not kind:
        raise ValueError('此任务不是唯一性检测算法')
    cfg = dict(payload['configuration'])
    cfg['equipment_id'] = task.Equipment_id
    cfg = validate(cfg, kind)
    STATE.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = STATE / ('config-%d.before-%d.json' % (task.id, time.time_ns()))
        backup.write_bytes(path.read_bytes())
    tmp = path.with_suffix('.saving-%d' % os.getpid())
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(str(tmp), str(path))
    return read_task(task)

def register_routes(blueprint, auth):
    @auth
    def calibration(conf_id):
        try:
            user = getattr(g, 'platform_user', None)
            action = 'u' if request.method == 'POST' else 'r'
            if user is None or not has_menu_permission(user.id, 'sfgl', action):
                return jsonify(code=403, msg='当前账号没有算法配置权限'), 403
            if request.content_length and request.content_length > 32768:
                return jsonify(code=413, msg='配置内容过大'), 413
            query = db.session.query(Algorithm_config).filter_by(id=conf_id)
            task = query.with_for_update().first() if request.method == 'POST' else query.first()
            if task is None:
                return jsonify(code=404, msg='任务不存在'), 404
            result = save_task(task, request.get_json(silent=True)) if request.method == 'POST' else read_task(task)
            db.session.rollback()  # Files are atomic; release the task row lock.
            return jsonify(code=200, data=result)
        except (ValueError, TypeError) as error:
            db.session.rollback()
            return jsonify(code=400, msg=str(error)), 400
        except Exception:
            db.session.rollback()
            return jsonify(code=500, msg='唯一性配置读取或保存失败，请检查服务日志'), 500
    blueprint.add_url_rule('/uniqueness/tasks/<int:conf_id>', 'uniqueness_calibration', calibration, methods=['GET','POST'])
