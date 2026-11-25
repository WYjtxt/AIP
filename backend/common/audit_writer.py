"""Per-application bounded audit queue; workers never read Flask request state."""
import atexit
import json
import logging
import queue
import re
import threading
import time

from common.log_payload import bounded_text

logger = logging.getLogger(__name__)
_PRIVATE = re.compile(r'password|passwd|secret|token|authorization|credential', re.I)


def audit_text(value, limit=4096):
    def redact(item):
        if isinstance(item, dict):
            return {str(k): '[redacted]' if _PRIVATE.search(str(k)) else redact(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [redact(v) for v in item]
        return item
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(redact(value), ensure_ascii=False, default=str)
    return bounded_text(value, limit) or ''


class AuditWriter:
    def __init__(self, persist, queue_size=2000, batch_size=50, flush_interval=.1):
        self.persist = persist
        self.queue = queue.Queue(maxsize=queue_size)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.stats = {'queued': 0, 'written': 0, 'commits': 0, 'sync_fallback': 0, 'failed': 0}

    def start(self):
        self.thread = threading.Thread(target=self._run, name='platform-audit-writer', daemon=True)
        self.thread.start()
        atexit.register(self.close)
        return self

    def enqueue(self, item):
        item = dict(item)
        try:
            self.queue.put_nowait(item)
            with self.lock:
                self.stats['queued'] += 1
        except queue.Full:
            with self.lock:
                self.stats['sync_fallback'] += 1
            self._write([item])

    def _write(self, rows):
        for attempt in range(2):
            try:
                self.persist(rows)
                with self.lock:
                    self.stats['written'] += len(rows)
                    self.stats['commits'] += 1
                return
            except Exception as error:
                if not attempt:
                    time.sleep(.05)
                    continue
                with self.lock:
                    self.stats['failed'] += len(rows)
                logger.warning('Audit write failed for %s rows: %s', len(rows), type(error).__name__)

    def _run(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                first = self.queue.get(timeout=.1)
            except queue.Empty:
                continue
            rows = [first]
            deadline = time.monotonic() + self.flush_interval
            while len(rows) < self.batch_size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    rows.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break
            try:
                self._write(rows)
            finally:
                for _ in rows:
                    self.queue.task_done()

    def flush(self, timeout=5):
        deadline = time.monotonic() + timeout
        with self.queue.all_tasks_done:
            while self.queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.queue.all_tasks_done.wait(remaining)
        return True

    def close(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
