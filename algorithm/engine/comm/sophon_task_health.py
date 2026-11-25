"""Share fresh task observations from Sophon workers with the platform backend."""

import json
import logging
import os
from pathlib import Path
import threading
import time


ROOT = Path('/data/AIGO/platform_runtime_health')
LOG = logging.getLogger(__name__)
MAX_AGE = 12
STATUS_TEXT = {
    'healthy': '已取得新画面和推理结果，编码器已接收输出',
    'starting': '正在等待画面、推理和输出状态',
    'startup_timeout': '尚未取得近期推理和输出，请检查视频流和算法日志',
    'output_timeout': '推理仍在更新，编码器未确认近期视频输出',
}


def _write(path, payload):
    pending = path.with_suffix('.pending')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        pending.replace(path)
    except OSError:
        LOG.exception('Cannot write Sophon runtime status')


class WorkerHealth:
    def __init__(self, generation, models, push_required=True):
        self.generation = generation
        self.tasks = tuple(model.get('platform_conf_id') for model in models)
        self.path = ROOT / 'sophon' / (generation + '.json') if generation else None
        self.inference = {}
        self.lock = threading.Lock()
        self.updated = 0
        self.push_required = push_required
        self.encoder_time = 0

    def processed(self, index, frame_time):
        if self.path is not None and self.tasks[index] is not None:
            with self.lock:
                self.inference[index] = frame_time
                self._flush()

    def output(self, frame_time):
        if self.path is None:
            return
        with self.lock:
            self.encoder_time = frame_time
            self._flush()

    def _flush(self):
        now = time.time()
        if now - self.updated < 0.5:
            return
        self.updated = now
        # Independent timestamps also cover an intentionally disabled or stalled encoder.
        observed = {self.tasks[index]: when for index, when in self.inference.items()}
        _write(self.path, {'pid': os.getpid(), 'updated_at': now, 'frame_time': self.encoder_time,
                           'push_required': self.push_required, 'tasks': observed})


def _observation(record, now):
    path = ROOT / 'sophon' / (record['generation'] + '.json')
    try:
        if not record['proc'].is_alive() or path.stat().st_size > 256 * 1024:
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['pid'] == record['proc'].pid and 0 <= now - data.get('updated_at', data['frame_time']) <= MAX_AGE:
            return data
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return {}


def publish(groups, pool):
    now = time.time()
    reports = []
    for stream, rows in groups.items():
        record = pool.get(stream)
        if record is None:
            continue
        observed = _observation(record, now)
        for row in rows:
            conf_id = str(row['Conf_id'])
            if conf_id not in record['task_ids']:
                continue
            inference = observed.get('tasks', {}).get(conf_id, 0)
            inference_fresh = 0 <= now - inference <= MAX_AGE
            encoder_fresh = 0 <= now - observed.get('frame_time', 0) <= MAX_AGE
            push_required = observed.get('push_required', bool(record['sig'][0]))
            healthy = inference_fresh and (not push_required or encoder_fresh)
            expired = time.monotonic() - record['started_at'] > 60
            state = 'healthy' if healthy else 'startup_timeout' if expired else 'starting'
            if not healthy and expired and inference_fresh:
                state = 'output_timeout'
            reason = '已取得近期推理结果，本任务未启用分析推流' if healthy and not push_required else STATUS_TEXT[state]
            reports.append(dict(conf_id=int(conf_id), state=state, healthy=healthy, model_status=1,
                                worker_pid=record['proc'].pid, generation=record['generation'],
                                inference_fresh=inference_fresh, encoder_fresh=encoder_fresh,
                                push_required=push_required, reason_text=reason))
    _write(ROOT / 'health.json', {'epoch': now, 'tasks': reports})


def retire(record):
    try:
        (ROOT / 'sophon' / (record['generation'] + '.json')).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        LOG.exception('Cannot retire Sophon runtime status')
