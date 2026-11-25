"""Database-backed diagnosis deadlines shared by every WSGI worker."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import logging


LOG = logging.getLogger(__name__)
LOCK_NAME = 'seal_system:video_diagnosis'
FIELDS = ('id', 'name', 'interval_seconds', 'time_type', 'rtsp_list',
          'diagnosis_type_list', 'scheduled_concent', 'scheduled_status',
          'next_run_time', 'create_time')
UNITS = {'seconds': 1, 'minutes': 60, 'hours': 3600,
         'days': 86400, 'weeks': 604800}


def normalize_status(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('任务状态无效')
    if value in (1, '1', '启用'):
        return 1
    if value in (0, '0', '禁用'):
        return 0
    raise ValueError('任务状态无效')


def interval_delta(value, time_type):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('时间间隔必须为正整数')
    try:
        amount = int(value)
    except (ValueError, TypeError):
        raise ValueError('时间间隔必须为正整数')
    if amount <= 0 or time_type not in UNITS:
        raise ValueError('时间间隔或时间类型无效')
    try:
        return timedelta(seconds=amount * UNITS[time_type])
    except OverflowError:
        raise ValueError('时间间隔过大')


def advance_due(due, now, step):
    """Coalesce missed intervals, keeping the original schedule anchor."""
    periods = max(0, (now - due) // step + 1)
    return due + periods * step


def _snapshot(task):
    if isinstance(task, dict):
        return {name: task.get(name) for name in FIELDS}
    return {name: getattr(task, name) for name in FIELDS}


class DatabaseStore:
    def __init__(self):
        from data.exts import db
        from model.admin import ScheduledTask
        self.db = db
        self.model = ScheduledTask

    @contextmanager
    def locked(self):
        # A dedicated physical DB connection owns the lock until diagnosis and
        # result replacement finish. Session commits must not release it.
        from sqlalchemy import text
        connection = self.db.engine.connect()
        acquired = False
        try:
            result = connection.execute(text('SELECT GET_LOCK(:name, 0)'),
                                        {'name': LOCK_NAME}).scalar()
            if result is None:
                raise RuntimeError('Diagnosis lock unavailable')
            acquired = result == 1
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(text('SELECT RELEASE_LOCK(:name)'),
                                       {'name': LOCK_NAME})
                except Exception:
                    # Do not return a still-locked physical connection to the pool.
                    connection.invalidate()
            connection.close()

    def enabled_ids(self):
        self.db.session.rollback()
        return [row.id for row in self.db.session.query(self.model.id).filter(
            self.model.scheduled_status == 1).order_by(self.model.id).all()]

    def load(self, task_id):
        # End the prior read snapshot so another worker's API changes are visible.
        self.db.session.rollback()
        return self.db.session.query(self.model).populate_existing().filter(
            self.model.id == task_id).first()

    def last_result(self, task):
        """Infer the first durable deadline for legacy plans only."""
        from model.algorithm import Diagnosis_data, Diagnosis_data_old
        from service.scheduler_task_service import SchedulerTaskService
        from sqlalchemy import func
        ok, sources = SchedulerTaskService.flatten_equipment_data(
            json.loads(task.rtsp_list))
        if not ok:
            raise ValueError('Invalid diagnosis sources')
        ids = [int(source['id']) for source in sources]
        if not ids:
            return None
        latest = []
        for model in (Diagnosis_data, Diagnosis_data_old):
            timestamp = self.db.session.query(func.max(model.create_time)).filter(
                model.equipment_id.in_(ids)).scalar()
            if timestamp is not None:
                latest.append(timestamp)
        return max(latest) if latest else None

    def save_due(self, task_id, expected, next_due):
        self.db.session.rollback()
        # An API edit during analysis wins over the old runner's checkpoint.
        fields = ('interval_seconds', 'time_type', 'rtsp_list',
                  'diagnosis_type_list', 'scheduled_status', 'next_run_time')
        filters = [self.model.id == task_id]
        filters.extend(getattr(self.model, name) == expected[name] for name in fields)
        try:
            changed = self.db.session.query(self.model).filter(*filters).update(
                {'next_run_time': next_due}, synchronize_session=False)
            self.db.session.commit()
            return changed == 1
        except Exception:
            self.db.session.rollback()
            raise


def _run_diagnosis(task):
    from service.scheduler_task_service import SchedulerTaskService
    return SchedulerTaskService.run_task(*[task[name] for name in FIELDS[:8]])


class DiagnosisScheduler:
    def __init__(self, app, store=None, clock=datetime.now, runner=None):
        self.app = app
        self.store = store if store is not None else DatabaseStore()
        self.clock = clock
        self.runner = runner if runner is not None else _run_diagnosis

    def tick(self):
        attempted = 0
        with self.app.app_context():
            try:
                with self.store.locked() as acquired:
                    if not acquired:
                        return 0
                    for task_id in self.store.enabled_ids():
                        try:
                            task = self.store.load(task_id)
                            if task is None:
                                continue
                            saved = _snapshot(task)
                            if normalize_status(saved['scheduled_status']) != 1:
                                continue
                            step = interval_delta(saved['interval_seconds'], saved['time_type'])
                            due = saved['next_run_time']
                            if due is None:
                                last = self.store.last_result(task)
                                due = last + step if last else saved['create_time'] or self.clock()
                                if not self.store.save_due(task_id, saved, due):
                                    continue
                                task = self.store.load(task_id)
                                if task is None:
                                    continue
                                saved = _snapshot(task)
                                # A simultaneous edit may have disabled/rescheduled the plan.
                                if normalize_status(saved['scheduled_status']) != 1:
                                    continue
                                due = saved['next_run_time']
                                step = interval_delta(saved['interval_seconds'], saved['time_type'])
                            if due is None or due > self.clock():
                                continue
                            attempted += 1
                            LOG.info('Diagnosis started task_id=%s due=%s', task_id, due)
                            try:
                                success, _message = self.runner(saved)
                            except Exception as error:
                                success = False
                                LOG.error('Diagnosis raised task_id=%s error_type=%s',
                                          task_id, type(error).__name__)
                            finished = self.clock()
                            next_due = (advance_due(due, finished, step) if success
                                        else finished + timedelta(seconds=60))
                            persisted = self.store.save_due(task_id, saved, next_due)
                            LOG.log(logging.INFO if success else logging.ERROR,
                                    'Diagnosis finished task_id=%s success=%s next_run_time=%s saved=%s',
                                    task_id, bool(success), next_due, persisted)
                        except Exception as error:
                            LOG.error('Diagnosis scheduling failed task_id=%s error_type=%s',
                                      task_id, type(error).__name__)
            except Exception as error:
                LOG.error('Diagnosis tick failed error_type=%s', type(error).__name__)
        return attempted


def register_diagnosis_scheduler(app, scheduler):
    diagnosis = DiagnosisScheduler(app)
    app.extensions['diagnosis_scheduler'] = diagnosis
    scheduler.add_job(id='diagnosis_dispatch', func=diagnosis.tick,
                      trigger='interval', seconds=15, next_run_time=datetime.now(),
                      max_instances=1, coalesce=True, misfire_grace_time=60,
                      replace_existing=True)
    return diagnosis
