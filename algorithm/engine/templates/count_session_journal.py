"""Persist managed alarm sessions in the cumulative count transaction."""
from datetime import datetime
import json
import math
import re


_ID = re.compile(r'[a-f0-9]{32}\Z')


def initialize(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS count_alarm_sessions (
        id TEXT PRIMARY KEY, boundary TEXT NOT NULL,
        started REAL NOT NULL, last_event REAL NOT NULL, ended REAL NOT NULL,
        entered INTEGER NOT NULL, exited INTEGER NOT NULL,
        total_entered INTEGER NOT NULL, total_exited INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('open','sealed','staged'))
    )''')
    connection.execute('''CREATE TABLE IF NOT EXISTS count_alarm_crossings (
        sequence INTEGER PRIMARY KEY,
        batch_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
        session_id TEXT NOT NULL, occurred REAL NOT NULL,
        entered INTEGER NOT NULL, exited INTEGER NOT NULL,
        total_entered INTEGER NOT NULL, total_exited INTEGER NOT NULL,
        UNIQUE(batch_id, ordinal)
    )''')
    connection.execute('''CREATE INDEX IF NOT EXISTS count_alarm_session_order
        ON count_alarm_sessions(status, boundary, started)''')
    connection.execute('''CREATE INDEX IF NOT EXISTS count_alarm_crossing_session
        ON count_alarm_crossings(session_id)''')
    connection.execute('''CREATE TABLE IF NOT EXISTS count_alarm_frames(
        id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, occurred REAL NOT NULL,
        jpeg BLOB NOT NULL, metadata TEXT NOT NULL)''')
    connection.execute('CREATE INDEX IF NOT EXISTS count_alarm_frame_session ON count_alarm_frames(session_id,id)')
    connection.execute('''CREATE TRIGGER IF NOT EXISTS seal_previous_count_alarm_day
        BEFORE UPDATE OF boundary ON counter WHEN NEW.boundary > OLD.boundary
        BEGIN
            UPDATE count_alarm_sessions SET status='sealed',
                total_entered=OLD.entered, total_exited=OLD.exited
            WHERE boundary=OLD.boundary AND status='open';
            DELETE FROM count_alarm_crossings WHERE session_id IN (
                SELECT id FROM count_alarm_sessions WHERE status='staged' AND boundary<NEW.boundary
            );
            DELETE FROM count_alarm_sessions WHERE status='staged' AND boundary<NEW.boundary;
        END''')


def record(connection, batch_id, boundary, session, enter_delta, exit_delta, entered, exited):
    session_id, started, occurred, ended, directions = session[:5]
    if (not isinstance(session_id, str) or not _ID.fullmatch(session_id)
            or not all(math.isfinite(stamp) for stamp in (started, occurred, ended))
            or occurred < started or ended < started
            or (directions.count('enter'), directions.count('exit')) != (enter_delta, exit_delta)
            or len(directions) != enter_delta + exit_delta):
        raise ValueError('Invalid managed people-count session crossing')
    previous = connection.execute('SELECT boundary,status FROM count_alarm_sessions WHERE id=?',
                                  (session_id,)).fetchone()
    if previous is None:
        connection.execute('''INSERT INTO count_alarm_sessions VALUES
            (?,?,?,?,?,?,?,?,?,'open')''',
            (session_id, boundary, started, occurred, ended, enter_delta, exit_delta, entered, exited))
    elif previous['boundary'] == boundary and previous['status'] == 'open':
        connection.execute('''UPDATE count_alarm_sessions SET
            last_event=max(last_event,?), ended=max(ended,?), entered=entered+?, exited=exited+?,
            total_entered=?, total_exited=? WHERE id=?''',
            (occurred, ended, enter_delta, exit_delta, entered, exited, session_id))
    else:
        raise ValueError('Managed people-count session is already sealed or has a different day')
    running_entered, running_exited = entered - enter_delta, exited - exit_delta
    rows = []
    for ordinal, direction in enumerate(directions):
        enter, leave = int(direction == 'enter'), int(direction == 'exit')
        running_entered += enter
        running_exited += leave
        rows.append((batch_id, ordinal, session_id, occurred, enter, leave, running_entered, running_exited))
    connection.executemany('''INSERT INTO count_alarm_crossings
        (batch_id,ordinal,session_id,occurred,entered,exited,total_entered,total_exited)
        VALUES (?,?,?,?,?,?,?,?)''', rows)
    if len(session) > 5:
        for stamp, jpeg, metadata in session[5]:
            metadata = dict(metadata, entered=entered, exited=exited)
            connection.execute('''INSERT INTO count_alarm_frames(session_id,occurred,jpeg,metadata)
                VALUES(?,?,?,?)''',(session_id, stamp, jpeg, json.dumps(metadata,ensure_ascii=False)))


def seal(connection, session_id=None, ended=None):
    sql = "UPDATE count_alarm_sessions SET status='sealed', ended=max(started,coalesce(?,ended)) WHERE status='open' "
    values = (ended,)
    if session_id is not None:
        sql += 'AND id=?'
        values += (session_id,)
    connection.execute(sql, values)
    if session_id is None:
        return
    return connection.execute('SELECT * FROM count_alarm_sessions WHERE id=?', (session_id,)).fetchone()


def unstaged(connection):
    rows = connection.execute("SELECT * FROM count_alarm_sessions WHERE status='sealed' ORDER BY started,id")
    return [dict(row) for row in rows]


def acknowledge(connection, session_id):
    connection.execute("UPDATE count_alarm_sessions SET status='staged' WHERE id=? AND status='sealed'",
                       (session_id,))
    connection.execute('DELETE FROM count_alarm_frames WHERE session_id=?', (session_id,))


def session_info(row):
    return dict(
        start_time=datetime.fromtimestamp(row['started']),
        end_time=datetime.fromtimestamp(row['ended']),
        enter_count=row['entered'], exit_count=row['exited'],
        total_enter_all=row['total_entered'], total_exit_all=row['total_exited'],
    )
