"""Fold tracker increments and active-session receipts into the same ledger."""
from collections import deque
import logging
import sqlite3
import time
import uuid

from templates.count_state import CountState
from templates.count_session_journal import session_info


class CountReplica:
    def __init__(self, conf_id, entered, exited, directory=None, now=None):
        self.state = CountState(conf_id, entered, exited, timeout=0.15, directory=directory, now=now)
        self.pending = deque()
        self.next_poll = 0.0
        self.next_retry = 0.0
        self.session_id = None
        self.boundary = self.state.event_boundary()
        self.discontinuity = 0
        self.capture = None
        self.wake = None
        # The supervisor replaces workers per configuration. Open rows from the
        # preceding generation retain their original time, count and evidence.
        self._retry(self.state.seal_open_sessions)

    @staticmethod
    def totals(tracker):
        return tracker.total_enter_all, tracker.total_exit_all

    def _sync(self, tracker, force=False):
        now = time.monotonic()
        if not force and now < self.next_retry:
            return
        try:
            snapshot = None
            while self.pending:
                snapshot = self.state.crossings(*self.pending[0])
                self.pending.popleft()
            if snapshot is None:
                snapshot = self.state.snapshot()
            tracker.total_enter_all, tracker.total_exit_all = snapshot['entered'], snapshot['exited']
            self.next_poll = now + 0.5
            self.next_retry = 0.0
        except (OSError, sqlite3.Error):
            if force:
                raise
            self.next_retry = now + 0.5
            logging.warning('[counting] task %s totals write delayed; retrying', self.state.conf_id, exc_info=True)

    def _retry(self, operation, *args, **kwargs):
        delay = 0.1
        while True:
            try:
                return operation(*args, **kwargs)
            except (OSError, sqlite3.Error):
                logging.warning('[counting] task %s session persistence delayed; retrying', self.state.conf_id,
                                exc_info=True)
                time.sleep(delay)
                delay = min(3.0, delay * 2)

    def before_frame(self, tracker):
        boundary = self.state.event_boundary()
        if boundary > self.boundary:
            self.close_discontinuity(tracker)
            tracker._reset_session()
            tracker.cross_events.clear()
            self.boundary = boundary
        if time.monotonic() >= self.next_poll:
            self._sync(tracker)
        return self.totals(tracker), boundary, len(tracker.cross_events)

    def after_frame(self, tracker, before):
        totals, boundary, existing_events = before
        entered, exited = self.totals(tracker)
        delta = entered - totals[0], exited - totals[1]
        if any(delta):
            first = self.session_id is None
            if first:
                self.session_id = uuid.uuid4().hex
            directions = tuple(event[2] for event in tracker.cross_events[existing_events:])
            started = tracker.first_cross_ts
            occurred = tracker.last_cross_ts
            frames = self.capture(tracker, tracker.cross_events[existing_events:], occurred, first) if self.capture else ()
            session = (self.session_id, started, occurred, occurred, directions, frames)
            self.pending.append((*delta, uuid.uuid4().hex, boundary, session))
            # Keep the count, per-person marks and the irreplaceable measured
            # frames in the same FULL transaction before exposing the new totals.
            self._retry(self._sync, tracker, force=True)

    def seal(self, tracker, ended=None):
        if self.session_id is None:
            return None
        if self.pending:
            self._retry(self._sync, tracker, force=True)
        row = self._retry(self.state.seal_alarm_session, self.session_id, ended)
        self.session_id = None
        if row is None:
            # A delayed crossing from a prior daily boundary was not applied.
            return None
        if self.wake is not None:
            self.wake.set()
        return dict(session_info(row), alarm_event_id=row['id'])

    def close_discontinuity(self, tracker):
        self.seal(tracker)
        self.discontinuity += 1

    def mark_staged(self, event_id):
        self._retry(self.state.mark_alarm_staged, event_id)
