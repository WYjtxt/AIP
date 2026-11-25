"""Complete reference snapshots, validated under short InnoDB shared locks.

Parsing is prepared outside write-blocking locks. Every batch then locks and
compares ALL alarm rows, including gaps, using per-row SHA-256 fingerprints.
New rows, out-of-order commits and UPDATEs are parsed before any unlink. A
truncated scan never authorizes deletion. No unvalidated snapshot is reused.
"""
import hashlib
import json
import re
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import func, literal, select, text

from service.alarm_retention_files import MEDIA_FIELDS, MEDIA_EXTENSIONS, MediaResolver, media_references


def _legacy_needles(name):
    escaped_json = ''.join('\\u%04x' % ord(char) if ord(char) <= 65535
                           else json.dumps(char)[1:-1] for char in name)
    escaped_percent = ''.join('%%%02X' % byte for byte in name.encode('utf-8'))
    return {name, quote(name), quote(name, safe=''), json.dumps(name)[1:-1],
            ascii(name)[1:-1], escaped_json, escaped_percent}


class ReferenceMatcher:
    def __init__(self, paths, resolver=None):
        self.paths = set(paths)
        self.needles = {}
        for path in self.paths:
            for needle in _legacy_needles(Path(path).name):
                self.needles.setdefault(needle.lower(), set()).add(path)
        self.pattern = re.compile('|'.join(re.escape(value) for value in self.needles), re.I) if self.needles else None

    def ambiguous(self, raw, shared):
        if not isinstance(raw, str) or self.pattern is None or not self.pattern.search(raw):
            return
        lowered = raw.lower()
        # Alternatives alone hide overlapping names. Preserve the old guard's
        # conservative behavior for every matching malformed/foreign reference.
        for needle, paths in self.needles.items():
            if needle in lowered:
                shared.update(paths)


class _PreparedResolver(MediaResolver):
    """Memoize only a preparation's repeated references and parent link checks.

    Actual candidates are still revalidated by MediaResolver.unlink using fresh
    descriptors, root inode, regular-file fingerprint and O_NOFOLLOW at deletion.
    Unknown references remain conservative; cached parsing never permits links.
    """
    def __init__(self, resolver):
        self.mappings = resolver.mappings
        self.roots = resolver.roots
        self.root_signatures = resolver.root_signatures
        self._references = {}
        self._links = {}

    def resolve(self, value):
        if not isinstance(value, str):
            return None
        if value not in self._references:
            self._references[value] = super().resolve(value)
        return self._references[value]

    def _candidate(self, root, relative):
        import os
        if '\x00' in relative or (os.name == 'posix' and '\\' in relative):
            return None
        parts = Path(relative).parts
        if not parts or Path(relative).is_absolute() or '..' in parts:
            return None
        candidate = root.joinpath(*parts)
        if candidate.suffix.lower() not in MEDIA_EXTENSIONS:
            return None
        try:
            candidate.relative_to(root)
            for component in (candidate, *candidate.parents):
                if component == root:
                    break
                if component not in self._links:
                    self._links[component] = component.is_symlink()
                if self._links[component]:
                    return None
        except (ValueError, OSError):
            return None
        return str(candidate)


def _columns(table):
    return [table.c.id] + [table.c[name] for name in MEDIA_FIELDS if name in table.c]


def _mysql_hash(table):
    # Length framing distinguishes NULL, empty strings, delimiters and arbitrary
    # media text. Both preparation and validation are computed by the same DB,
    # avoiding client/server charset transformations in the comparison.
    framed = [func.coalesce(func.concat(func.octet_length(table.c[name]), literal(':'), table.c[name]),
                            literal('-:')) for name in MEDIA_FIELDS if name in table.c]
    return func.sha2(func.concat(*framed), 256).label('_retention_row_hash')


def _raw_fingerprint(row):
    if '_retention_row_hash' in row:
        return row['_retention_row_hash']
    raw = [row.get(name) for name in MEDIA_FIELDS]
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


class ReferenceSnapshot:
    def __init__(self, resolver):
        self.resolver = _PreparedResolver(resolver)
        self.rows = {}
        self.references = Counter()
        self.ambiguous = Counter()
        self.complete = False
        self.preparation_seconds = 0.0

    def discard(self, row_id):
        previous = self.rows.pop(row_id, None)
        if previous is not None:
            for collection, values in ((self.references, previous[1]), (self.ambiguous, previous[2])):
                for value in values:
                    collection[value] -= 1
                    if collection[value] <= 0:
                        del collection[value]

    def store(self, row, deadline):
        references, ambiguous = set(), set()
        for field in MEDIA_FIELDS:
            raw = row.get(field)
            values = list(media_references({field: raw}))
            if not values and isinstance(raw, str) and raw:
                ambiguous.add(raw)
            for value in values:
                if time.monotonic() >= deadline:
                    return False
                resolved = self.resolver.resolve(value)
                if resolved is None:
                    ambiguous.add(value)
                else:
                    references.add(resolved)
        self.discard(row['id'])
        self.rows[row['id']] = (_raw_fingerprint(row), references, ambiguous)
        self.references.update(references)
        self.ambiguous.update(ambiguous)
        return True

    def shared(self, paths):
        matcher = ReferenceMatcher(paths)
        result = matcher.paths.intersection(self.references)
        for value in self.ambiguous:
            matcher.ambiguous(value, result)
        return result


def prepare_reference_snapshot(engine, table, resolver, deadline):
    """One non-locking complete read, with no file or database mutations."""
    prepared = ReferenceSnapshot(resolver)
    started = time.monotonic()
    columns = _columns(table)
    if engine.dialect.name == 'mysql':
        columns.append(_mysql_hash(table))
    try:
        with engine.connect() as connection:
            cursor = connection.execution_options(stream_results=True).execute(
                select(*columns).order_by(table.c.id)).mappings()
            try:
                complete = True
                for row in cursor:
                    if time.monotonic() >= deadline or not prepared.store(row, deadline):
                        complete = False
                        break
                prepared.complete = complete and time.monotonic() < deadline
            finally:
                cursor.close()
    finally:
        prepared.preparation_seconds = time.monotonic() - started
    return prepared


@contextmanager
def guarded_reference_batch(engine, table, paths, resolver, deadline, max_hold_seconds=1.0, prepared=None):
    """Validate every row while holding InnoDB row+gap locks through unlink.

    Callers perform no DB writes until this context closes. Unsupported engines,
    failed/partial preparation, lock waits or incomplete validations fail closed.
    """
    guard = {'complete': False, 'shared': set(), 'rows_scanned': 0,
             'hold_seconds': 0.0, 'reason': None, 'delete_deadline': deadline}
    connection = transaction = cursor = None
    old_timeout = held_since = None
    yielded = False
    try:
        if prepared is None:
            prepared = prepare_reference_snapshot(engine, table, resolver, deadline)
        if not prepared.complete or time.monotonic() >= deadline:
            guard['reason'] = 'incomplete_preparation'
            yielded = True
            yield guard
            return
        connection = engine.connect()
        dialect = engine.dialect.name
        if dialect == 'mysql':
            connection = connection.execution_options(isolation_level='REPEATABLE READ')
        transaction = connection.begin()
        if dialect == 'mysql':
            storage_engine = connection.execute(text(
                'SELECT ENGINE FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name'), {'name': table.name}).scalar()
            if str(storage_engine).lower() != 'innodb':
                raise ValueError('reference table must use InnoDB')
            old_timeout = int(connection.execute(text('SELECT @@SESSION.innodb_lock_wait_timeout')).scalar())
            connection.execute(text('SET SESSION innodb_lock_wait_timeout = 1'))
            statement = select(table.c.id, _mysql_hash(table)).order_by(table.c.id).with_for_update(read=True)
        elif dialect == 'sqlite':
            connection.execute(text('BEGIN IMMEDIATE'))
            statement = select(*_columns(table)).order_by(table.c.id)
        else:
            raise ValueError('unsupported reference transaction')
        held_since = time.monotonic()
        batch_deadline = min(deadline, held_since + max(0.05, min(max_hold_seconds, 1.0)))
        guard['delete_deadline'] = batch_deadline
        cursor = connection.execution_options(stream_results=True).execute(statement).mappings()
        complete, seen, changed = True, set(), []
        for row in cursor:
            if time.monotonic() >= batch_deadline:
                complete = False
                break
            guard['rows_scanned'] += 1
            seen.add(row['id'])
            previous = prepared.rows.get(row['id'])
            if previous is None or previous[0] != _raw_fingerprint(row):
                if dialect == 'mysql':
                    changed.append(row['id'])
                elif not prepared.store(row, batch_deadline):
                    complete = False
                    break
        cursor.close()
        cursor = None
        if complete:
            for row_id in set(prepared.rows).difference(seen):
                prepared.discard(row_id)
            if changed:
                columns = _columns(table) + [_mysql_hash(table)]
                for offset in range(0, len(changed), 100):
                    rows = connection.execute(select(*columns).where(table.c.id.in_(changed[offset:offset + 100]))
                                              .with_for_update(read=True)).mappings().all()
                    for row in rows:
                        if not prepared.store(row, batch_deadline):
                            complete = False
                            break
                    if not complete:
                        break
        if complete and time.monotonic() < batch_deadline:
            guard['shared'] = prepared.shared(paths)
            guard['complete'] = time.monotonic() < batch_deadline
        if not guard['complete']:
            guard['reason'] = 'incomplete'
        yielded = True
        yield guard
    except Exception as error:
        if yielded:
            raise
        guard['reason'] = type(error).__name__
        yielded = True
        yield guard
    finally:
        if cursor is not None:
            cursor.close()
        if transaction is not None:
            transaction.rollback()
        if held_since is not None:
            guard['hold_seconds'] = time.monotonic() - held_since
        if connection is not None:
            try:
                if old_timeout is not None:
                    connection.execute(text('SET SESSION innodb_lock_wait_timeout = %d' % old_timeout))
                    connection.commit() if hasattr(connection, 'commit') else None
            finally:
                connection.close()
