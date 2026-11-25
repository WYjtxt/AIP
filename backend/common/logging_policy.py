"""Bounded application logs, including a separate seven-day polling log.

Each write opens the file under a process-shared lock. This avoids keeping an
unlinked log open after rotation and works when several WSGI workers are used.
"""
import contextlib
import contextvars
import functools
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path


_POLLING = contextvars.ContextVar('seal_polling_log', default=False)
_LOCAL_LOCK = threading.RLock()
_ARCHIVE_PATTERN = re.compile(r'^(.+\.log)\.(\d{8})-(\d+)-(\d+)$')
_DATE_FORMAT = '%Y-%m-%d'


def _bounded_env(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (ValueError, TypeError):
        value = default
    return max(minimum, min(maximum, value))


@contextlib.contextmanager
def polling_context():
    token = _POLLING.set(True)
    try:
        yield
    finally:
        _POLLING.reset(token)


def polling_job(function):
    """Wrap a scheduler callback so its print/log output uses polling.log."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        with polling_context():
            return function(*args, **kwargs)
    return wrapped


@contextlib.contextmanager
def _file_lock(path):
    with _LOCAL_LOCK:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(fd, 'r+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                stream.close()


class PollingFilter(logging.Filter):
    def __init__(self, polling):
        super().__init__()
        self.polling = polling

    def filter(self, record):
        return bool(getattr(record, 'polling', _POLLING.get())) == self.polling


class BoundedFileHandler(logging.Handler):
    """Daily and size rotation with an archive-count and maximum-age bound.

    Archives use the date of their first entry, so removing an archive whose
    start date is older than the cutoff never keeps expired polling entries.
    This may discard the remainder of that oldest day slightly early.
    """
    def __init__(self, filename, max_bytes, backup_count, retention_days=7):
        super().__init__()
        self.path = Path(filename).absolute()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(128, int(max_bytes))
        self.backup_count = max(0, int(backup_count))
        self.retention_days = max(1, min(7, int(retention_days)))
        self.lock_path = self.path.with_name(self.path.name + '.lock')

    def _first_date(self):
        with self.path.open('rb') as stream:
            prefix = stream.read(10).decode('ascii', errors='ignore')
        try:
            return datetime.strptime(prefix, _DATE_FORMAT)
        except ValueError:
            return datetime.fromtimestamp(self.path.stat().st_mtime).replace(
                hour=0, minute=0, second=0, microsecond=0)

    def _archives(self):
        rows = []
        for item in self.path.parent.iterdir():
            match = _ARCHIVE_PATTERN.fullmatch(item.name)
            if not match or match.group(1) != self.path.name:
                continue
            if item.is_symlink() or not item.is_file():
                continue
            try:
                start = datetime.strptime(match.group(2), '%Y%m%d')
                rows.append((int(match.group(3)), start, item))
            except (ValueError, OSError):
                continue
        return sorted(rows, key=lambda row: row[0], reverse=True)

    def _prune(self, now):
        cutoff = now - timedelta(days=self.retention_days)
        for index, (_, first_date, item) in enumerate(self._archives()):
            if index >= self.backup_count or first_date < cutoff:
                try:
                    item.unlink()
                except FileNotFoundError:
                    pass

    def _rotate(self, first_date):
        suffix = '{}-{}-{}'.format(first_date.strftime('%Y%m%d'), time.time_ns(), os.getpid())
        self.path.replace(self.path.with_name(self.path.name + '.' + suffix))

    def _maintain_locked(self, now, incoming_bytes=0):
        if self.path.is_symlink():
            raise OSError('Refusing to write a symlink as a platform log')
        if self.path.exists() and self.path.stat().st_size:
            first_date = self._first_date()
            if first_date.date() != now.date() or self.path.stat().st_size + incoming_bytes > self.max_bytes:
                self._rotate(first_date)
        self._prune(now)

    def maintain(self, now=None):
        """Prune even an inactive polling log from the maintenance scheduler."""
        with _file_lock(self.lock_path):
            self._maintain_locked(now or datetime.now())

    def emit(self, record):
        try:
            payload = (self.format(record) + '\n').encode('utf-8', errors='replace')
            # A single huge traceback/request must not bypass the file limit.
            budget = min(16384, self.max_bytes)
            if len(payload) > budget:
                marker = b' ... [truncated]\n'
                payload = payload[:budget - len(marker)].decode('utf-8', errors='ignore').encode('utf-8') + marker
            with _file_lock(self.lock_path):
                self._maintain_locked(datetime.fromtimestamp(record.created), len(payload))
                flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
                if hasattr(os, 'O_NOFOLLOW'):
                    flags |= os.O_NOFOLLOW
                fd = os.open(str(self.path), flags, 0o600)
                with os.fdopen(fd, 'ab') as stream:
                    stream.write(payload)
        except Exception:
            self.handleError(record)

    def handleError(self, record):
        # The default logging implementation writes to sys.stderr, which this
        # application redirects back to logging. A full disk would recurse.
        try:
            sys.__stderr__.write('Platform file log write failed; check disk space and permissions.\n')
        except Exception:
            pass


class StdoutToLogger:
    """Line-based print bridge with a bounded partial-line buffer per thread."""
    encoding = 'utf-8'

    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self._local = threading.local()

    def write(self, value):
        if not value:
            return 0
        buffer = getattr(self._local, 'buffer', '') + value
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            if line.strip():
                self.logger.log(self.level, line.rstrip())
        if len(buffer) > 16384:
            self.logger.log(self.level, buffer[:16384] + ' ... [truncated]')
            buffer = ''
        self._local.buffer = buffer
        return len(value)

    def flush(self):
        buffer = getattr(self._local, 'buffer', '')
        if buffer.strip():
            self.logger.log(self.level, buffer.rstrip())
        self._local.buffer = ''

    def isatty(self):
        return False


def configure_logging(log_dir=None, console=None):
    """Replace only root logging configuration; keep third-party loggers intact."""
    log_dir = Path(log_dir or Path(__file__).resolve().parents[1] / 'logs')
    app_mb = _bounded_env('SEAL_APP_LOG_MAX_MB', 20, 1, 50)
    polling_mb = _bounded_env('SEAL_POLLING_LOG_MAX_MB', 10, 1, 20)
    app_backups = _bounded_env('SEAL_APP_LOG_BACKUPS', 5, 1, 7)
    polling_backups = _bounded_env('SEAL_POLLING_LOG_BACKUPS', 7, 1, 7)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handlers = [
        BoundedFileHandler(log_dir / 'app.log', app_mb * 1024 * 1024, app_backups),
        BoundedFileHandler(log_dir / 'polling.log', polling_mb * 1024 * 1024, polling_backups),
    ]
    handlers[0].addFilter(PollingFilter(False))
    handlers[1].addFilter(PollingFilter(True))
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.maintain()
    stream_handler = logging.StreamHandler(console if console is not None else sys.__stdout__)
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)
    root = logging.getLogger()
    for old in list(root.handlers):
        root.removeHandler(old)
        old.close()
    root.setLevel(logging.INFO)
    for handler in handlers:
        root.addHandler(handler)
    # Console remains the original stream, avoiding redirection recursion.
    sys.stdout = StdoutToLogger(logging.getLogger('stdout'), logging.INFO)
    sys.stderr = StdoutToLogger(logging.getLogger('stderr'), logging.WARNING)
    return handlers[:2]


def maintain_log_files():
    for handler in list(logging.getLogger().handlers):
        if isinstance(handler, BoundedFileHandler):
            handler.maintain()
