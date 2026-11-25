"""Bounded alarm retention with transactional media retries and explicit storage roots.

Only settings and expired t_algorithm_result rows are changed. Camera/algorithm
configuration, source streams and callback parameters are outside this service.
"""
import hashlib
import json
import logging
import os
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import MetaData, Table, and_, delete, func, inspect, insert, or_, select, text, update

from data.exts import db
from model.storage_retention import AlarmMediaDeletion, StorageRetentionSettings
from service.alarm_retention_files import MEDIA_FIELDS, MediaResolver, media_references
from service.alarm_retention_references import guarded_reference_batch, prepare_reference_snapshot
from service.storage_disk_service import storage_disk_settings

DEFAULT_DAYS = 180
MIN_DAYS, MAX_DAYS = 1, 3650
CLEANUP_INTERVAL_MINUTES = 60
CLEANUP_BACKLOG_INTERVAL_MINUTES = 1
REFERENCE_BATCH_SIZE = 64
_LOCAL_LOCK = threading.Lock()
_SCHEMA_LOCK = threading.Lock()
_ALARM_TABLES = {}
_SCHEMA_ENGINES = set()
LOGGER = logging.getLogger(__name__)
CONFIG_PATH = str(Path(__file__).resolve().parents[1] / 'config' / 'storage-retention.json')


def _config():
    path = os.environ.get('SEAL_STORAGE_RETENTION_CONFIG', CONFIG_PATH)
    try:
        with open(path, encoding='utf-8') as handle:
            config = json.load(handle)
        if not isinstance(config, dict):
            raise ValueError()
        from service.alarm_directory_config import merge_retention
        return merge_retention(config)
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _resolver(config=None):
    try:
        return MediaResolver(_config() if config is None else config)
    except (OSError, TypeError, ValueError):
        # An absent mount or malformed whitelist must disable deletion, not expand it.
        return MediaResolver({})


def _ensure_tables():
    engine = db.engine
    if engine in _SCHEMA_ENGINES:
        return
    with _SCHEMA_LOCK:
        for model in (StorageRetentionSettings, AlarmMediaDeletion):
            try:
                model.__table__.create(engine, checkfirst=True)
            except Exception:
                # Another prefork worker can create this same small table first.
                if not inspect(engine).has_table(model.__tablename__):
                    raise
        _SCHEMA_ENGINES.add(engine)


def _alarm_table():
    # The deployed callback schema also has warning_video, absent from older source.
    engine = db.engine
    if engine not in _ALARM_TABLES:
        _ALARM_TABLES[engine] = Table('t_algorithm_result', MetaData(), autoload_with=engine)
    return _ALARM_TABLES[engine]


@contextmanager
def _manager_lock():
    """MySQL advisory lock coordinates all web workers and maintenance invocations."""
    if db.engine.dialect.name == 'mysql':
        with db.engine.connect() as connection:
            acquired = connection.execute(text("SELECT GET_LOCK('seal_alarm_retention_v1', 0)")).scalar() == 1
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT RELEASE_LOCK('seal_alarm_retention_v1')"))
    else:
        acquired = _LOCAL_LOCK.acquire(False)
        try:
            yield acquired
        finally:
            if acquired:
                _LOCAL_LOCK.release()


def _settings_row():
    _ensure_tables()
    table = StorageRetentionSettings.__table__
    with db.engine.connect() as connection:
        row = connection.execute(select(table).where(table.c.id == 1)).mappings().first()
    if row is None:
        with _manager_lock() as acquired:
            if acquired:
                with db.engine.begin() as connection:
                    if connection.execute(select(table.c.id).where(table.c.id == 1)).first() is None:
                        connection.execute(insert(table).values(id=1, alarm_retention_days=DEFAULT_DAYS,
                                                                updated_at=datetime.now()))
        with db.engine.connect() as connection:
            row = connection.execute(select(table).where(table.c.id == 1)).mappings().first()
    return dict(row) if row is not None else {'alarm_retention_days': DEFAULT_DAYS}


def _previous_cleanup(row):
    try:
        previous = json.loads(row.get('last_cleanup') or '{}')
        return previous if isinstance(previous, dict) else {}
    except (ValueError, TypeError):
        return {}


def _orphan_scan_complete(row, config, resolver):
    roots = _orphan_roots(config, resolver)
    if not roots:
        return True
    try:
        state = json.loads(row.get('orphan_scan_state') or '{}')
        return (state.get('roots') == [str(root) for root in roots]
                and state.get('root_index') == 0 and state.get('stack') == [])
    except (ValueError, TypeError, AttributeError):
        return False


def _next_interval(previous):
    return (CLEANUP_BACKLOG_INTERVAL_MINUTES if previous.get('continuation_required')
            else CLEANUP_INTERVAL_MINUTES)


def _scheduled_due(row, now, continuation=None):
    previous = _previous_cleanup(row)
    try:
        completed = datetime.fromisoformat(previous['completed_at'])
        # A retention setting change starts a new check, independent of the old
        # run's chosen age. Never mutate the saved number of retention days here.
        if previous.get('alarm_retention_days') != row['alarm_retention_days']:
            return True
        interval = (CLEANUP_BACKLOG_INTERVAL_MINUTES if continuation
                    else _next_interval(previous))
        return now >= completed + timedelta(minutes=interval)
    except (KeyError, ValueError, TypeError):
        return True


def retention_settings(days=None):
    _ensure_tables()
    if days is not None:
        if type(days) is not int or not MIN_DAYS <= days <= MAX_DAYS:
            return {'code': 400, 'msg': '报警保留期限必须是1–3650天的整数'}
        with _manager_lock() as acquired:
            if not acquired:
                return {'code': 409, 'msg': '正在清理报警数据，请稍后保存'}
            table = StorageRetentionSettings.__table__
            with db.engine.begin() as connection:
                if connection.execute(select(table.c.id).where(table.c.id == 1)).first() is None:
                    connection.execute(insert(table).values(id=1, alarm_retention_days=days, updated_at=datetime.now()))
                else:
                    connection.execute(update(table).where(table.c.id == 1).values(
                        alarm_retention_days=days, updated_at=datetime.now()))
    row = _settings_row()
    config = _config()
    resolver = _resolver(config)
    previous = _previous_cleanup(row)
    with db.engine.connect() as connection:
        queue = AlarmMediaDeletion.__table__
        pending = connection.execute(select(func.count()).select_from(queue)).scalar()
        unchecked = connection.execute(select(func.count()).select_from(queue)
                                       .where(queue.c.checked_at.is_(None))).scalar()
    scan_complete = _orphan_scan_complete(row, config, resolver)
    continuation = bool(unchecked or not scan_complete or previous.get('remaining_expired_records', 0))
    data = {'alarm_retention_days': row['alarm_retention_days'],
            'cleanup_interval_minutes': CLEANUP_INTERVAL_MINUTES,
            'cleanup_backlog_interval_minutes': CLEANUP_BACKLOG_INTERVAL_MINUTES,
            'continuation_required': continuation,
            'next_check_minutes': CLEANUP_BACKLOG_INTERVAL_MINUTES if continuation else CLEANUP_INTERVAL_MINUTES,
            'last_cleanup': previous, 'pending_media_files': pending,
            'unchecked_media_files': unchecked, 'orphan_scan_complete': scan_complete,
            'media_roots_configured': len(resolver.roots),
            'orphan_scan_roots': len(_orphan_roots(config, resolver))}
    data.update(storage_disk_settings(config.get('disk_path', '/')))
    return {'code': 200, 'msg': '保存成功' if days is not None else '查询成功', 'data': data}


def _paths(rows, resolver):
    result, unmanaged = {}, 0
    for row in rows:
        for reference in media_references(row):
            path = resolver.resolve(reference)
            if path is None:
                unmanaged += 1
            elif path not in result:
                result[path] = resolver.fingerprint(path)
    return result, unmanaged


def _shared(path, resolver, exclude_ids=()):
    """Fresh transaction checks all aliases in retained rows, including callback inserts."""
    table = _alarm_table()
    name = Path(path).name
    # JSON defaults to ensure_ascii=True; Python lists can also contain escaped
    # Unicode. The broad SQL prefilter must include these stored representations
    # before the parser resolves and compares the exact canonical local path.
    escaped_json = ''.join('\\u%04x' % ord(char) if ord(char) <= 65535 else json.dumps(char)[1:-1]
                           for char in name)
    escaped_percent = ''.join('%%%02X' % byte for byte in name.encode('utf-8'))
    needles = {name, quote(name), quote(name, safe=''), json.dumps(name)[1:-1],
               ascii(name)[1:-1], escaped_json, escaped_percent}
    predicates = []
    columns = [table.c[name] for name in MEDIA_FIELDS if name in table.c]
    for column in columns:
        for needle in needles:
            escaped = needle.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            predicates.append(column.like('%' + escaped + '%', escape='\\'))
    condition = or_(*predicates)
    if exclude_ids:
        condition = and_(condition, ~table.c.id.in_(exclude_ids))
    with db.engine.connect() as connection:
        candidates = connection.execute(select(*columns).where(condition)).mappings().all()
    for row in candidates:
        for field, raw in row.items():
            references = list(media_references({field: raw}))
            for reference in references:
                resolved = resolver.resolve(reference)
                if resolved == path:
                    return True
                if resolved is None and any(needle.lower() in reference.lower() for needle in needles):
                    return True  # Ambiguous retained references must never authorize deletion.
            if not references and isinstance(raw, str) and any(needle.lower() in raw.lower() for needle in needles):
                return True  # Malformed legacy lists are kept conservatively until row expiry.
    return False


def _enqueue(connection, paths, now):
    table = AlarmMediaDeletion.__table__
    entries = [(hashlib.sha256(path.encode('utf-8')).hexdigest(), path, fingerprint)
               for path, fingerprint in paths.items()]
    for offset in range(0, len(entries), 500):
        batch = entries[offset:offset + 500]
        existing = {item[0] for item in connection.execute(
            select(table.c.path_hash).where(table.c.path_hash.in_([entry[0] for entry in batch])))}
        inserts = []
        for key, path, fingerprint in batch:
            if key in existing:
                continue
            size, mtime = fingerprint if fingerprint is not None else (None, None)
            inserts.append({'path_hash': key, 'path': path, 'file_size': size,
                            'file_mtime_ns': mtime, 'created_at': now})
        if inserts:
            connection.execute(insert(table), inserts)


def queue_and_delete_alarm_records(ids):
    """Shared helper for legacy manual/config deletion; media still waits for its age limit.

    Callers may retain their current row-deletion behavior without losing media
    ownership. A saved media retry is never unlinked before the configured cutoff.
    """
    valid_ids = sorted({int(value) for value in ids if str(value).isdigit() and int(value) > 0})
    if not valid_ids:
        return 0
    _ensure_tables()
    _settings_row()
    resolver = _resolver()
    if not resolver.roots:
        raise ValueError('alarm media storage is unavailable')
    table = _alarm_table()
    fields = [table.c.id] + [table.c[name] for name in MEDIA_FIELDS if name in table.c]
    deleted = 0
    with _manager_lock() as acquired:
        if not acquired:
            raise RuntimeError('alarm retention is busy')
        for offset in range(0, len(valid_ids), 500):
            batch = valid_ids[offset:offset + 500]
            with db.engine.begin() as connection:
                rows = connection.execute(select(*fields).where(table.c.id.in_(batch))
                                          .with_for_update()).mappings().all()
                paths, _ = _paths(rows, resolver)
                _enqueue(connection, paths, datetime.now())
                connection.execute(delete(table).where(table.c.id.in_([row['id'] for row in rows])))
                deleted += len(rows)
    return deleted


def _orphan_roots(config, resolver):
    result = []
    for value in config.get('orphan_roots', []):
        candidate = MediaResolver._root(value)
        if candidate is None:
            continue
        for root in resolver.roots:
            try:
                candidate.relative_to(root)
                # Explicit child subdirectories only; do not scan all algorithm results.
                if candidate != root and candidate not in result:
                    result.append(candidate)
            except ValueError:
                pass
    return result


def _scan_orphans(config, resolver, cutoff_timestamp, deadline, max_files=10000):
    """Persist a DFS cursor; old files deleted manually in the UI are also reclaimed."""
    roots = _orphan_roots(config, resolver)
    if not roots:
        return 0
    table = StorageRetentionSettings.__table__
    with db.engine.connect() as connection:
        encoded = connection.execute(select(table.c.orphan_scan_state).where(table.c.id == 1)).scalar()
    try:
        state = json.loads(encoded or '{}')
        stack = state.get('stack', [])
        root_index = int(state.get('root_index', 0))
        if state.get('roots') != [str(root) for root in roots] or not 0 <= root_index < len(roots):
            stack, root_index = [], 0
    except (TypeError, ValueError):
        stack, root_index = [], 0
    if not stack:
        stack = [{'path': str(roots[root_index]), 'phase': 'files', 'after': ''}]
    scanned, paths = 0, {}
    while stack and scanned < max_files and time.monotonic() < deadline:
        frame = stack[-1]
        directory = Path(frame['path'])
        try:
            directory.relative_to(roots[root_index])
            if directory.is_symlink() or directory.resolve() != directory:
                raise ValueError()
            names = sorted(os.listdir(str(directory)))
        except (OSError, ValueError):
            stack.pop()
            continue
        advanced = False
        for name in names:
            if name <= frame['after']:
                continue
            frame['after'] = name
            candidate = directory / name
            if candidate.is_symlink():
                continue
            if frame['phase'] == 'files' and candidate.is_file():
                scanned += 1
                path = resolver.resolve(str(candidate))
                if path:
                    fingerprint = resolver.fingerprint(path)
                    if fingerprint and fingerprint[1] / 1000000000.0 < cutoff_timestamp:
                        paths[path] = fingerprint
                if scanned >= max_files or time.monotonic() >= deadline:
                    advanced = True
                    break
            elif frame['phase'] == 'dirs' and candidate.is_dir():
                stack.append({'path': str(candidate), 'phase': 'files', 'after': ''})
                advanced = True
                break
        if advanced:
            continue
        if frame['phase'] == 'files':
            frame['phase'], frame['after'] = 'dirs', ''
        else:
            stack.pop()
        if not stack:
            root_index += 1
            if root_index >= len(roots):
                root_index = 0
                break  # A complete pass; start a fresh pass at the next invocation.
            stack.append({'path': str(roots[root_index]), 'phase': 'files', 'after': ''})
    state = {'roots': [str(root) for root in roots], 'stack': stack, 'root_index': root_index}
    with db.engine.begin() as connection:
        _enqueue(connection, paths, datetime.now())
        connection.execute(update(table).where(table.c.id == 1).values(orphan_scan_state=json.dumps(state)))
    return scanned


def _process_media_queue(queued, resolver, cutoff_timestamp, deadline, now, summary):
    """Lock and check a small batch, unlink inside its guard, then persist retries."""
    queue = AlarmMediaDeletion.__table__
    table = _alarm_table()
    if not queued or time.monotonic() >= deadline:
        return
    prepared = prepare_reference_snapshot(db.engine, table, resolver, deadline)
    summary['reference_preparation_seconds'] = round(prepared.preparation_seconds, 4)
    if not prepared.complete:
        summary['incomplete_reference_batches'] += 1
        summary['deferred_files'] += min(len(queued), REFERENCE_BATCH_SIZE)
        return
    for offset in range(0, len(queued), REFERENCE_BATCH_SIZE):
        if time.monotonic() >= deadline:
            break
        batch = queued[offset:offset + REFERENCE_BATCH_SIZE]
        outcomes = []
        with guarded_reference_batch(db.engine, table, [item['path'] for item in batch],
                                     resolver, deadline, prepared=prepared) as guard:
            summary['reference_batches'] += 1
            summary['reference_rows_scanned'] += guard['rows_scanned']
            if not guard['complete']:
                summary['incomplete_reference_batches'] += 1
                summary['deferred_files'] += len(batch)
            else:
                for item in batch:
                    if time.monotonic() >= guard['delete_deadline']:
                        break
                    if item['path'] in guard['shared']:
                        outcome, freed = 'shared', 0
                    else:
                        outcome, freed = resolver.unlink(item['path'], item['file_size'],
                                                         item['file_mtime_ns'], cutoff_timestamp)
                    outcomes.append((item, outcome, freed))
        summary['max_reference_lock_seconds'] = round(max(summary['max_reference_lock_seconds'],
                                                          guard['hold_seconds']), 4)
        if not guard['complete']:
            break  # A bounded incomplete snapshot never authorizes any unlink.
        if not outcomes:
            break
        # All shared locks are released before queue writes. A lost queue commit
        # is safe: retrying an already unlinked path produces 'missing'.
        with db.engine.begin() as connection:
            for item, outcome, freed in outcomes:
                if outcome in ('deleted', 'missing', 'changed'):
                    connection.execute(delete(queue).where(queue.c.path_hash == item['path_hash']))
                else:
                    connection.execute(update(queue).where(queue.c.path_hash == item['path_hash'])
                                       .values(checked_at=now))
                summary['queue_checked_files'] += 1
                if outcome == 'deleted':
                    summary['deleted_media_files'] += 1
                    summary['freed_media_bytes'] += freed
                elif outcome == 'shared':
                    summary['shared_files'] += 1
                    summary['deferred_files'] += 1
                elif outcome == 'recent':
                    summary['recent_files'] += 1
                    summary['deferred_files'] += 1
                elif outcome == 'error':
                    summary['errors'] += 1
                    summary['deferred_files'] += 1
                elif outcome == 'changed':
                    summary['replaced_files'] += 1
                    summary['deferred_files'] += 1
                elif outcome != 'missing':
                    summary['deferred_files'] += 1


def cleanup_alarm_data(dry_run=True, now=None, max_records=10000, max_files=5000,
                       budget_seconds=45, scheduled=False):
    _ensure_tables()
    _settings_row()  # Initialize defaults once; do not use this pre-lock snapshot.
    config = _config()
    resolver = _resolver(config)
    with _manager_lock() as acquired:
        if not acquired:
            return {'code': 409, 'msg': '报警清理正在运行，请稍后重试'}
        row = _settings_row()  # A concurrent successful settings save must govern this run.
        days = row['alarm_retention_days']
        if type(days) is not int or not MIN_DAYS <= days <= MAX_DAYS:
            return {'code': 503, 'msg': '报警保留期限配置异常，已停止清理'}
        run_clock = datetime.now() if now is None else now
        if scheduled and not dry_run:
            queue = AlarmMediaDeletion.__table__
            with db.engine.connect() as connection:
                unchecked = connection.execute(select(func.count()).select_from(queue)
                                               .where(queue.c.checked_at.is_(None))).scalar()
            continuation = bool(unchecked or not _orphan_scan_complete(row, config, resolver))
            if not _scheduled_due(row, run_clock, continuation):
                return {'code': 200, 'msg': '尚未到自动清理时间', 'data': {'skipped': True}}
        if now is None:
            # res_time is populated by MySQL CURRENT_TIMESTAMP; use the same DB clock.
            with db.engine.connect() as connection:
                now = connection.execute(select(func.current_timestamp())).scalar()
            cutoff_timestamp = time.time() - days * 86400
        else:
            cutoff_timestamp = (now - timedelta(days=days)).timestamp()
        cutoff = now - timedelta(days=days)
        if not resolver.roots:
            return {'code': 409, 'msg': '尚未配置或挂载报警媒体目录，已停止清理',
                    'data': {'dry_run': dry_run, 'cutoff': cutoff.isoformat(), 'expired_records': 0}}
        deadline = time.monotonic() + max(1, min(budget_seconds, 120))
        table = _alarm_table()
        fields = [table.c.id, table.c.res_time] + [table.c[name] for name in MEDIA_FIELDS if name in table.c]
        with db.engine.connect() as connection:
            expired = connection.execute(select(func.count()).select_from(table).where(table.c.res_time < cutoff)).scalar()
        summary = {'dry_run': dry_run, 'alarm_retention_days': days, 'cutoff': cutoff.isoformat(),
                   'expired_records': expired, 'scanned_records': 0, 'deleted_records': 0,
                   'media_files': 0, 'media_bytes': 0, 'deleted_media_files': 0,
                   'freed_media_bytes': 0, 'shared_files': 0, 'unmanaged_references': 0,
                   'deferred_files': 0, 'replaced_files': 0, 'errors': 0, 'orphan_scanned_files': 0,
                   'queue_checked_files': 0, 'recent_files': 0, 'reference_batches': 0,
                   'reference_rows_scanned': 0, 'incomplete_reference_batches': 0,
                   'max_reference_lock_seconds': 0.0, 'reference_preparation_seconds': 0.0,
                   'sample_limited': False, 'completed_at': now.isoformat()}
        if dry_run:
            with db.engine.connect() as connection:
                rows = connection.execute(select(*fields).where(table.c.res_time < cutoff).order_by(table.c.res_time, table.c.id)
                                          .limit(min(max_records, 500))).mappings().all()
            paths, unmanaged = _paths(rows, resolver)
            summary['scanned_records'], summary['unmanaged_references'] = len(rows), unmanaged
            summary['sample_limited'] = expired > len(rows)
            excluded = [item['id'] for item in rows]
            for path, fingerprint in paths.items():
                if time.monotonic() >= deadline:
                    summary['sample_limited'] = True
                    break
                if _shared(path, resolver, excluded):
                    summary['shared_files'] += 1
                elif fingerprint and fingerprint[1] / 1000000000.0 < cutoff_timestamp:
                    summary['media_files'] += 1
                    summary['media_bytes'] += fingerprint[0]
                else:
                    summary['deferred_files'] += 1
        else:
            record_deadline = min(deadline, time.monotonic() + max(1, min(budget_seconds, 120) / 4.0))
            while summary['deleted_records'] < max_records and time.monotonic() < record_deadline:
                with db.engine.begin() as connection:
                    rows = connection.execute(select(*fields).where(table.c.res_time < cutoff)
                                              .order_by(table.c.res_time, table.c.id)
                                              .limit(min(500, max_records - summary['deleted_records']))
                                              .with_for_update()).mappings().all()
                    if not rows:
                        break
                    paths, unmanaged = _paths(rows, resolver)
                    _enqueue(connection, paths, now)
                    connection.execute(delete(table).where(table.c.id.in_([item['id'] for item in rows]),
                                                            table.c.res_time < cutoff))
                    summary['deleted_records'] += len(rows)
                    summary['scanned_records'] += len(rows)
                    summary['unmanaged_references'] += unmanaged
            # Leave at least a portion of this bounded run for queue processing.
            if time.monotonic() < deadline:
                summary['orphan_scanned_files'] = _scan_orphans(config, resolver, cutoff_timestamp,
                                                               min(deadline, time.monotonic() + 5))
            queue = AlarmMediaDeletion.__table__
            with db.engine.connect() as connection:
                queued = connection.execute(select(queue).order_by(queue.c.checked_at, queue.c.created_at, queue.c.path_hash)
                                            .limit(max_files)).mappings().all()
            _process_media_queue(queued, resolver, cutoff_timestamp, deadline, now, summary)
            with db.engine.connect() as connection:
                summary['pending_media_files'] = connection.execute(select(func.count()).select_from(queue)).scalar()
                summary['unchecked_media_files'] = connection.execute(select(func.count()).select_from(queue)
                                                                      .where(queue.c.checked_at.is_(None))).scalar()
                remaining = connection.execute(select(func.count()).select_from(table).where(table.c.res_time < cutoff)).scalar()
                current_row = dict(connection.execute(select(StorageRetentionSettings.__table__)
                                                       .where(StorageRetentionSettings.__table__.c.id == 1)).mappings().first())
            summary['remaining_expired_records'] = remaining
            summary['orphan_scan_complete'] = _orphan_scan_complete(current_row, config, resolver)
            summary['continuation_required'] = bool(remaining or summary['unchecked_media_files']
                                                     or not summary['orphan_scan_complete']
                                                     or summary['replaced_files'])
            summary['next_check_minutes'] = (CLEANUP_BACKLOG_INTERVAL_MINUTES if summary['continuation_required']
                                             else CLEANUP_INTERVAL_MINUTES)
            summary['sample_limited'] = bool(summary['continuation_required'] or summary['pending_media_files'])
            settings = StorageRetentionSettings.__table__
            summary['completed_at'] = datetime.now().isoformat()
            with db.engine.begin() as connection:
                connection.execute(update(settings).where(settings.c.id == 1).values(last_cleanup=json.dumps(summary)))
        return {'code': 200, 'msg': '清理预估完成' if dry_run else '报警过期清理完成', 'data': summary}


def run_alarm_cleanup():
    """Scheduler entry point: no private media URLs or database exceptions in logs."""
    try:
        result = cleanup_alarm_data(dry_run=False, scheduled=True)
        if result['code'] == 200:
            data = result['data']
            if data.get('skipped'):
                return result
            LOGGER.info('Alarm retention: records=%s files=%s freed_bytes=%s errors=%s',
                        data['deleted_records'], data['deleted_media_files'], data['freed_media_bytes'], data['errors'])
        elif result['code'] != 409:
            LOGGER.warning('Alarm retention unavailable: code=%s', result['code'])
        return result
    except Exception as error:
        LOGGER.error('Alarm retention failed: %s', type(error).__name__)
        return {'code': 500, 'msg': '报警清理失败，原有媒体已保留待重试'}
