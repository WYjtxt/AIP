"""Durable per-configuration people counts; no video or database dependencies.

The state directory belongs to the host, outside code and alarm retention paths.
SQLite FULL transactions make an individual crossing and its daily boundary one
atomic record.  Display names and camera addresses are deliberately not keys.
"""

import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

from templates import count_session_journal
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")
DEFAULT_DIRECTORY = "/data/AIGO/platform_counts"
_STATE_NAME = re.compile(r"conf_([1-9][0-9]*)\.sqlite3\Z")
MAX_CORRECTION = 2_147_483_647


class CountConflict(ValueError):
    def __init__(self, state):
        super().__init__('累计人数已更新，请核对最新读数')
        self.state = state

# The supervisor runs count maintenance in threads and forks stream workers.
# Keep its SQLite calls out of the fork boundary so a child never inherits a
# native SQLite mutex held by a supervisor thread that no longer exists.
_SQLITE_FORK_LOCK = threading.Lock()
if hasattr(os, "register_at_fork"):
    os.register_at_fork(before=_SQLITE_FORK_LOCK.acquire,
                        after_in_parent=_SQLITE_FORK_LOCK.release,
                        after_in_child=_SQLITE_FORK_LOCK.release)


@contextmanager
def _sqlite_connection(path, timeout, uri=False):
    with _SQLITE_FORK_LOCK:
        connection = sqlite3.connect(path, timeout=timeout, uri=uri)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()


def state_directory(directory=None):
    return Path(directory or os.environ.get("PLATFORM_COUNT_STATE_DIR") or DEFAULT_DIRECTORY)


def latest_boundary(now=None):
    """Most recent 23:59:00 in Beijing, independent of host timezone/DST."""
    current = datetime.now(BEIJING) if now is None else now
    if current.tzinfo is None:
        raise ValueError("People count clocks must have an explicit timezone")
    current = current.astimezone(BEIJING)
    boundary = current.replace(hour=23, minute=59, second=0, microsecond=0)
    if boundary > current:
        boundary -= timedelta(days=1)
    return boundary.isoformat()


def _number(value):
    if value is None or value == "":
        return 0
    result = int(value)
    if result < 0:
        raise ValueError("People counts cannot be negative")
    return result


def _validate_boundary(value):
    parsed = datetime.fromisoformat(value)
    if (parsed.tzinfo is None or parsed.utcoffset() != timedelta(hours=8) or
            (parsed.hour, parsed.minute, parsed.second, parsed.microsecond) != (23, 59, 0, 0) or
            parsed.isoformat() != value):
        raise ValueError("People count boundary is invalid; manual recovery required")
    return value


class CountState:
    def __init__(self, conf_id, initial_enter=0, initial_exit=0, directory=None, now=None, timeout=1):
        self.conf_id = int(conf_id)
        if self.conf_id <= 0 or str(self.conf_id) != str(conf_id):
            raise ValueError("A stable positive Conf_id is required for durable people counts")
        self.directory = state_directory(directory)
        self.directory.mkdir(mode=0o750, parents=True, exist_ok=True)
        self.path = self.directory / ("conf_%d.sqlite3" % self.conf_id)
        self.timeout = timeout
        if self.path.is_symlink():
            raise ValueError("People count state must be a regular file")
        existed = self.path.exists()
        self._clock = now or (lambda: datetime.now(BEIJING))
        # First deployment imports existing totals.  It does not infer a reset
        # from an absent legacy marker or from a changed defense start time.
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""CREATE TABLE IF NOT EXISTS counter (
                singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                conf_id INTEGER NOT NULL,
                boundary TEXT NOT NULL,
                entered INTEGER NOT NULL CHECK (entered>=0),
                exited INTEGER NOT NULL CHECK (exited>=0),
                revision INTEGER NOT NULL CHECK (revision>=1)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, boundary TEXT NOT NULL,
                applied INTEGER NOT NULL CHECK (applied IN (0,1)))""")
            count_session_journal.initialize(connection)
            row = connection.execute("SELECT conf_id FROM counter WHERE singleton=1").fetchone()
            if row is None:
                if existed:
                    raise ValueError("Existing people count state is incomplete; manual recovery required")
                connection.execute("""INSERT INTO counter VALUES (1, ?, ?, ?, ?, 1)""", (
                        self.conf_id, latest_boundary(self._clock()),
                        _number(initial_enter), _number(initial_exit)))
        self._last_boundary = self.snapshot()["boundary"]

    @contextmanager
    def _connection(self):
        with _sqlite_connection(str(self.path), timeout=self.timeout) as connection:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection

    def _change(self, enter_delta=0, exit_delta=0, event_id=None, occurred_boundary=None,
                correction=None, session=None):
        boundary = latest_boundary(self._clock())
        if occurred_boundary is not None:
            boundary = max(boundary, _validate_boundary(occurred_boundary))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM counter WHERE singleton=1").fetchone()
            if row is None or row["conf_id"] != self.conf_id:
                raise ValueError("People count state identity mismatch")
            entered, exited, revision = row["entered"], row["exited"], row["revision"]
            saved_boundary = _validate_boundary(row["boundary"])
            if boundary > saved_boundary:
                entered, exited = 0, 0
                saved_boundary = boundary
                revision += 1
                connection.execute("DELETE FROM events WHERE boundary < ?", (saved_boundary,))
            # A backwards clock never decreases the durable boundary, so it
            # cannot clear the same business day again after catching up.
            applied = False
            if event_id is not None:
                receipt = connection.execute("SELECT boundary,applied FROM events WHERE event_id=?",
                                             (event_id,)).fetchone()
                if receipt is None:
                    applied = occurred_boundary >= saved_boundary
                    if applied:
                        entered += _number(enter_delta)
                        exited += _number(exit_delta)
                        revision += 1
                        if session is not None:
                            count_session_journal.record(connection, event_id, occurred_boundary, session,
                                                         enter_delta, exit_delta, entered, exited)
                    connection.execute("INSERT INTO events VALUES (?,?,?)",
                                       (event_id, occurred_boundary, int(applied)))
                else:
                    applied = bool(receipt["applied"] and receipt["boundary"] >= saved_boundary)
            conflict = correction is not None and correction[0] != revision
            if correction is not None and not conflict:
                desired = correction[1:]
                if (entered, exited) != desired:
                    entered, exited = desired
                    revision += 1
            if revision != row["revision"]:
                connection.execute("""UPDATE counter
                    SET boundary=?, entered=?, exited=?, revision=? WHERE singleton=1""",
                    (saved_boundary, entered, exited, revision))
            result = {"conf_id": self.conf_id, "boundary": saved_boundary,
                      "entered": entered, "exited": exited, "revision": revision,
                      "event_applied": applied}
        self._last_boundary = saved_boundary
        if conflict:
            raise CountConflict(result)
        return result

    def snapshot(self):
        return self._change()

    def event_boundary(self):
        return max(self._last_boundary, latest_boundary(self._clock()))

    def crossing(self, direction, event_id=None, occurred_boundary=None):
        if direction not in ("enter", "exit"):
            raise ValueError("Unknown people count direction")
        event_id = event_id or uuid.uuid4().hex
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128:
            raise ValueError("A bounded event identity is required")
        return self.crossings(int(direction == "enter"), int(direction == "exit"), event_id,
                              occurred_boundary)

    def crossings(self, enter_delta, exit_delta, event_id, occurred_boundary=None, session=None):
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128:
            raise ValueError("A bounded event identity is required")
        if not (type(enter_delta) is int and type(exit_delta) is int and min(enter_delta, exit_delta) >= 0
                and enter_delta + exit_delta > 0):
            raise ValueError("A positive crossing batch is required")
        return self._change(enter_delta, exit_delta, event_id, occurred_boundary or self.event_boundary(),
                            session=session)

    def seal_alarm_session(self, session_id, ended=None):
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = count_session_journal.seal(connection, session_id, ended)
            return dict(row) if row is not None else None

    def seal_open_sessions(self):
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            count_session_journal.seal(connection)

    def unstaged_alarm_sessions(self):
        with self._connection() as connection:
            return count_session_journal.unstaged(connection)

    def mark_alarm_staged(self, session_id):
        with self._connection() as connection:
            count_session_journal.acknowledge(connection, session_id)

    def alarm_frame_ids(self, session_id):
        with self._connection() as connection:
            return [row[0] for row in connection.execute('SELECT id FROM count_alarm_frames WHERE session_id=? ORDER BY id', (session_id,))]

    def alarm_frame(self, frame_id):
        with self._connection() as connection:
            return tuple(connection.execute('SELECT occurred,jpeg,metadata FROM count_alarm_frames WHERE id=?', (frame_id,)).fetchone())

    def correct(self, expected_revision, entered, exited):
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('累计人数版本无效')
        if any(type(n) is not int or not 0 <= n <= MAX_CORRECTION for n in (entered, exited)):
            raise ValueError('进出人数必须是 0 到 2147483647 的整数')
        return self._change(correction=(expected_revision, entered, exited))


def _state_paths(directory):
    directory = state_directory(directory)
    if not directory.exists():
        return
    for path in sorted(directory.glob("conf_*.sqlite3")):
        match = _STATE_NAME.fullmatch(path.name)
        if match is not None and not path.is_symlink():
            yield path, int(match.group(1))


def read_state(path, conf_id):
    """Read committed state without creating/rotating it or waiting on MySQL."""
    with _sqlite_connection(path.resolve().as_uri() + "?mode=ro", timeout=1, uri=True) as connection:
        row = connection.execute("SELECT * FROM counter WHERE singleton=1").fetchone()
        if row is None or row["conf_id"] != conf_id:
            raise ValueError("People count state identity mismatch")
        _validate_boundary(row["boundary"])
        return dict(row)


def rotation_pass(directory=None, now=None):
    """Local-only daily maintenance, including stopped tasks, with no DB I/O."""
    for path, conf_id in _state_paths(directory):
        try:
            CountState(conf_id, directory=path.parent, now=now).snapshot()
        except Exception:
            logging.exception("[counting] Conf_id=%s local daily rotation failed; retrying", conf_id)


def maintenance_pass(sync_counts, directory=None, synced=None, now=None, force_after=30, rotate=True):
    """Rotate existing tasks even when they are stopped; retry failed DB writes.

    One supervisor thread is the database writer.  Video workers only commit
    local transactions.  Periodic refresh also repairs a late pre-upgrade Kafka
    message; new managed messages must not overwrite the durable totals.
    """
    synced = {} if synced is None else synced
    if rotate:
        rotation_pass(directory, now)
    for path, conf_id in _state_paths(directory):
        try:
            state = read_state(path, conf_id)
            prior = synced.get(conf_id)
            mono = time.monotonic()
            # Leave legacy NULL totals alone until the first real crossing,
            # explicit correction, or scheduled daily boundary.
            if state['revision'] > 1 and (prior is None or prior[0] != state["revision"] or mono - prior[1] >= force_after):
                sync_counts(state["entered"], state["exited"], conf_id)
                synced[conf_id] = (state["revision"], mono)
        except Exception:
            logging.exception("[counting] Conf_id=%s durable count/DB synchronization failed; retrying", conf_id)
    return synced


def initialize_tasks(rows, directory=None, now=None):
    """Import DB totals for current tasks, including stopped ones, only once."""
    for row in rows or ():
        CountState(row["conf_id"], row.get("all_Entering_num"), row.get("all_Exiting_num"),
                   directory=directory, now=now)


def start_maintenance(sync_counts, stop_event=None, directory=None, interval=1, baseline_loader=None, force_after=30):
    """Start in the supervisor, never on module import or in forked workers."""
    stop_event = stop_event or threading.Event()

    def local_work():
        while not stop_event.is_set():
            rotation_pass(directory)
            stop_event.wait(interval)

    def database_work():
        synced = {}
        next_baseline = 0
        while not stop_event.is_set():
            if baseline_loader is not None and time.monotonic() >= next_baseline:
                try:
                    initialize_tasks(baseline_loader(), directory=directory)
                    next_baseline = time.monotonic() + 30
                except Exception:
                    logging.exception("[counting] Count baseline initialization failed; retrying")
            maintenance_pass(sync_counts, directory=directory, synced=synced, rotate=False, force_after=force_after)
            stop_event.wait(interval)

    local_thread = threading.Thread(target=local_work, name="people_count_local_daily", daemon=True)
    db_thread = threading.Thread(target=database_work, name="people_count_database_mirror", daemon=True)
    local_thread.start()
    db_thread.start()
    return stop_event, (local_thread, db_thread)
