"""Persist settled PersonCount sessions before preparing media or sending Kafka."""

from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid


LOGGER = logging.getLogger(__name__)
DEFAULT_DIRECTORY = '/data/AIGO/platform_counts'
MEDIA_TIMEOUT = 300
_EVENT_ID = re.compile(r'[0-9a-f]{32}\Z')


def count_alarm_payload(meta, session, managed=False):
    started = session['start_time'].strftime('%Y-%m-%d %H:%M:%S')
    finished = session['end_time'].strftime('%Y-%m-%d %H:%M:%S')
    entered = session['enter_count']
    exited = session['exit_count']
    total_entered = session.get('total_enter_all', entered)
    total_exited = session.get('total_exit_all', exited)
    payload = dict(
        Algorithm_conf_id=meta.get('conf_id'), res_type=meta.get('res_type'),
        Equipment_id=meta.get('Equipment_id'), carousel_images_list=[], ori_images_list=[],
        result_count=0, warning_message='总进入%d人，总离开%d人' % (total_entered, total_exited),
        Entering_num=entered, Exiting_num=exited, all_Entering_num=total_entered,
        all_Exiting_num=total_exited, result_count_time=started, start_time=started, res_time=finished,
        template_type_id=meta.get('template_config_type_id'), template_id=meta.get('template_id'),
        conf_name=meta.get('conf_name'), equipment_name=meta.get('equipment_name'),
        equipment_ip=meta.get('equipment_ip'), Algorithm_library_id=meta.get('Algorithm_library_id'),
        Mine_id=meta.get('Mine_id'), mine_code=meta.get('mine_code'), warning_video=session.get('warning_video'),
    )
    if managed:
        payload['count_state_managed'] = True
    return payload


class CountAlarmOutbox:
    def __init__(self, conf_id, directory=None):
        self.conf_id = int(conf_id)
        if self.conf_id < 0:
            raise ValueError('人数统计报警需要有效的任务 ID')
        directory = Path(directory or os.environ.get('PLATFORM_COUNT_STATE_DIR') or DEFAULT_DIRECTORY)
        directory.mkdir(mode=0o750, parents=True, exist_ok=True)
        self.path = directory / ('alarms_conf_%d.sqlite3' % self.conf_id)
        if self.path.is_symlink():
            raise ValueError('人数统计报警发件箱不能是符号链接')
        self._changed = threading.Event()
        with self._connection() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS alarms (
                seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, staged REAL NOT NULL,
                ready INTEGER NOT NULL CHECK(ready IN (0,1)), payload TEXT NOT NULL
            )''')
            connection.execute('''CREATE TABLE IF NOT EXISTS staged_alarm_ids (
                event_id TEXT PRIMARY KEY
            )''')
            connection.execute('INSERT OR IGNORE INTO staged_alarm_ids SELECT event_id FROM alarms')
            connection.execute('''CREATE TABLE IF NOT EXISTS last_alarm (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL
            )''')

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(str(self.path), timeout=5)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                yield connection
        finally:
            connection.close()

    def _write(self, operation, event_id, **values):
        delay = 1
        while True:
            try:
                result = operation(event_id, **values)
                self._changed.set()
                return result
            except sqlite3.OperationalError as error:
                LOGGER.error('[人数统计上报] 本地持久化失败，保留当前会话并等待重试 任务=%s 会话=%s 错误=%s',
                             self.conf_id, event_id, error)
                time.sleep(delay)
                delay = min(30, delay * 2)

    def stage(self, payload, event_id=None):
        event_id = event_id or uuid.uuid4().hex
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError('人数统计报警会话 ID 无效')
        data = json.dumps(dict(payload, alarm_event_id=event_id), ensure_ascii=False, allow_nan=False)
        self._write(self._insert, event_id, data=data)
        return event_id

    def stage_ready(self, event_id, payload):
        """Publish the completed evidence atomically, including on recovery."""
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError('Invalid alarm event ID')
        data = json.dumps(dict(payload, alarm_event_id=event_id), ensure_ascii=False, allow_nan=False)
        self._write(self._insert, event_id, data=data, ready=1)

    def _insert(self, event_id, data, ready=0):
        with self._connection() as connection:
            inserted = connection.execute('INSERT OR IGNORE INTO staged_alarm_ids VALUES(?)', (event_id,))
            if inserted.rowcount == 1:
                connection.execute('INSERT INTO alarms(event_id,staged,ready,payload) VALUES(?,?,?,?)',
                                   (event_id, time.time(), ready, data))
                connection.execute('INSERT OR REPLACE INTO last_alarm(singleton,payload) VALUES(1,?)', (data,))

    def last_staged(self):
        """Legacy counting workers can initialize from the last settled session."""
        with self._connection() as connection:
            row = connection.execute('SELECT payload FROM last_alarm WHERE singleton=1').fetchone()
        return json.loads(row[0]) if row else None

    def complete(self, event_id, **media):
        self._write(self._complete, event_id, media=media)

    def _complete(self, event_id, media):
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM alarms WHERE event_id=? AND ready=0', (event_id,)).fetchone()
            if row is None:
                return False
            payload = json.loads(row[0])
            payload.update(media)
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            connection.execute('UPDATE alarms SET ready=1,payload=? WHERE event_id=?', (data, event_id))
            return True

    def _next(self):
        with self._connection() as connection:
            return connection.execute('SELECT event_id,staged,ready,payload FROM alarms ORDER BY seq LIMIT 1').fetchone()

    def _acknowledge(self, event_id):
        with self._connection() as connection:
            result = connection.execute('DELETE FROM alarms WHERE event_id=?', (event_id,))
            return result.rowcount == 1

    def run(self, stop_event, sender, on_sent=None):
        if sender is None:
            LOGGER.error('[人数统计上报] 上报组件不可用，待发送会话保留在本地 任务=%s', self.conf_id)
            return
        delay = 1
        while not stop_event.is_set():
            try:
                pending = self._next()
            except sqlite3.OperationalError as error:
                LOGGER.error('[人数统计上报] 无法读取待发送会话 任务=%s 错误=%s', self.conf_id, error)
                stop_event.wait(delay)
                delay = min(30, delay * 2)
                continue
            if pending is None or (not pending[2] and time.time() - pending[1] < MEDIA_TIMEOUT):
                self._changed.wait(1)
                self._changed.clear()
                continue
            event_id, _, ready, data = pending
            if not ready:
                if self._write(self._complete, event_id, media={}):
                    LOGGER.warning('[人数统计上报] 图片准备超时，先补发统计 任务=%s 会话=%s', self.conf_id, event_id)
                continue
            payload = json.loads(data)
            try:
                sender(**payload)
            except Exception:
                LOGGER.exception('[人数统计上报] Kafka 确认失败，%s 秒后重试 任务=%s 会话=%s',
                                 delay, self.conf_id, event_id)
                stop_event.wait(delay)
                delay = min(30, delay * 2)
                continue
            delay = 1
            if self._write(self._acknowledge, event_id):
                LOGGER.info('[人数统计上报] Kafka 已确认 任务=%s 会话=%s 进入=%s 离开=%s',
                            self.conf_id, event_id, payload['Entering_num'], payload['Exiting_num'])
                if on_sent:
                    try:
                        on_sent(payload)
                    except Exception:
                        LOGGER.exception('[人数统计上报] 后续核验失败 任务=%s 会话=%s', self.conf_id, event_id)
