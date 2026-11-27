"""Bounded, shared recovery for saved recorder and direct-camera bindings.

No ORM rows are queued. Every attempt reloads intent and uses the existing
per-device/CAS recovery helper. Redis contains only identifiers and hashes;
public status and logs use an explicit field allowlist.
"""
import contextlib
import hashlib
import json
import logging
import time
import uuid

from service.media_stream_index import index_media_streams, media_stream_rows

PREFIX = 'bound_recovery:v1:'
STATE_KEY = PREFIX + 'states'
SUMMARY_KEY = PREFIX + 'summary'
AUTH_KEY = PREFIX + 'auth_paused'
SEED_KEY = PREFIX + 'maintenance_seeded'
DISPATCH_LOCK = PREFIX + 'dispatch'
MAX_ATTEMPTS = 2
ROUND_BUDGET = 45
STALL_SECONDS = 120
BASE_RETRY = 120
MAX_RETRY = 900
logger = logging.getLogger(__name__)

PUBLIC_FIELDS = ('equipment_id', 'binding_id', 'app', 'stream', 'state', 'reason',
    'failures', 'attempts', 'last_attempt_at', 'last_observed_at', 'last_transition_at',
    'next_retry_at', 'no_video_since', 'last_video_progress_at', 'source_status')
STATES = frozenset(('healthy', 'observing_video', 'waiting_video', 'proxy_connecting',
    'recovering', 'backoff', 'source_auth_paused', 'needs_attention', 'inactive'))
REASONS = frozenset(('video_progressing', 'waiting_video_progress', 'proxy_observing',
    'proxy_stalled', 'video_not_advancing', 'proxy_evidence_missing', 'reader_evidence_missing',
    'proxy_has_readers', 'proxy_identity_changed', 'source_auth_failed', 'account_maintenance',
    'source_unavailable', 'direct_source_unavailable', 'registered_source_mismatch',
    'source_video_present', 'configuration_changed', 'mapping_unconfirmed',
    'proxy_add_failed', 'proxy_remove_unconfirmed', 'proxy_changed_after_remove',
    'waiting_video', 'video_present', 'proxy_connecting', 'recovery_failed',
    'service_unavailable', 'lock_busy', 'not_eligible', 'attempt_reserved',
    'reconciliation_required', 'state_invalid'))


def _number(value):
    return type(value) in (int, float) and value >= 0 and value < 1e15


def _public(record):
    result = {key: record[key] for key in PUBLIC_FIELDS if key in record}
    if result.get('state') not in STATES:
        result['state'] = 'needs_attention'
    if result.get('reason') not in REASONS:
        result['reason'] = 'recovery_failed'
    return result


def _auth_token(snapshot):
    # Status toggles do not release an authentication block. Only source,
    # binding identity or saved access/mapping settings changing can do so.
    equipment, binding = snapshot['equipment'], snapshot['binding']
    value = dict(binding={name: binding.get(name) for name in ('id', 'source', 'owner', 'app', 'live')},
        equipment={name: equipment.get(name) for name in ('id', 'ip', 'port', 'username', 'password', 'channel', 'code', 'onvif')},
        parent={name: (snapshot.get('parent') or {}).get(name) for name in ('id', 'ip', 'username', 'password', 'vcr_id')},
        vcr=snapshot.get('vcr'))
    if equipment.get('type') == '摄像头' and equipment.get('parent_id') is None:
        value['camera'] = dict(vendor=equipment.get('vendor'), vcr_id=equipment.get('vcr_id'),
                               source=snapshot.get('registered_camera_source'))
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def _new_record(snapshot, now):
    equipment, binding = snapshot['equipment'], snapshot['binding']
    return dict(equipment_id=equipment['id'], binding_id=binding['id'], app=binding['app'],
        stream=binding['live'], state='observing_video', reason='waiting_video_progress',
        failures=0, attempts=0, next_retry_at=0, last_transition_at=now,
        auth_token=_auth_token(snapshot))


def _set_state(record, state, reason, now, **values):
    previous = (record.get('state'), record.get('reason'))
    record.update(values)
    record.update(state=state, reason=reason, last_observed_at=now)
    if previous != (state, reason):
        record['last_transition_at'] = now
        logger.info('bound_stream_recovery %s', json.dumps(_public(record), sort_keys=True, ensure_ascii=False))


def _media_evidence(rows):
    candidates = []
    for row in rows:
        counters, video = [], False
        for track in row.get('tracks') or []:
            if not isinstance(track, dict) or str(track.get('codec_type')) != '0':
                continue
            if track.get('ready') is False or ('frames' in track and (type(track['frames']) is not int or track['frames'] <= 0)):
                continue
            video = True
            if type(track.get('frames')) is int and track['frames'] >= 0:
                counters.append(track['frames'])
        if video:
            schema = str(row.get('schema') or '')
            stamp = row.get('createStamp')
            origin = row.get('originSock') if isinstance(row.get('originSock'), dict) else {}
            identifier = origin.get('identifier')
            generation = None
            if _number(stamp) or (isinstance(identifier, str) and identifier):
                generation = hashlib.sha256(repr((schema, stamp, identifier, row.get('originType'))).encode('utf-8')).hexdigest()
            rank = {'fmp4': 0, 'rtmp': 1, 'rtsp': 2, 'hls': 3, 'ts': 4}.get(schema, 9)
            candidates.append((rank, schema, generation, max(counters) if counters else None))
    if not candidates:
        return {'video': False, 'frames': None, 'generation': None}
    # Compare one stable protocol/session; replicated protocol counters are not
    # interchangeable proof of frame progress.
    chosen = min(candidates, key=lambda value: (value[0], value[1], value[2] or ''))
    return {'video': True, 'frames': chosen[3], 'generation': chosen[2]}


def _observe_video(record, evidence, now):
    if not evidence['video']:
        record.pop('frames', None)
        record.pop('frame_sample_at', None)
        record.pop('media_generation', None)
        record.setdefault('no_video_since', now)
        return False
    record.pop('no_video_since', None)
    generation = evidence.get('generation')
    if generation is None:
        _set_state(record, 'needs_attention', 'waiting_video_progress', now, next_retry_at=0)
        return True
    if generation != record.get('media_generation'):
        record['media_generation'] = generation
        record.pop('frames', None)
        record.pop('last_video_progress_at', None)
        record['frame_sample_at'] = now
    previous, frames = record.get('frames'), evidence['frames']
    if frames is None:
        _set_state(record, 'needs_attention', 'waiting_video_progress', now, next_retry_at=0)
        return True  # Never disturb a published video whose counters are absent.
    if type(previous) is int and frames > previous:
        record['last_video_progress_at'] = now
        record['auth_blocked'] = False
        _set_state(record, 'healthy', 'video_progressing', now,
                   failures=0, next_retry_at=0, source_status=None)
    elif previous is None or frames < previous:
        # New/reset counters need a second observation, never a fabricated pass.
        record['frame_sample_at'] = now
        _set_state(record, 'waiting_video' if record.get('state') == 'waiting_video' else 'observing_video',
                   'waiting_video_progress', now, next_retry_at=0)
    elif now - record.get('last_video_progress_at', record.get('frame_sample_at', now)) >= STALL_SECONDS:
        _set_state(record, 'needs_attention', 'video_not_advancing', now, next_retry_at=0)
    else:
        _set_state(record, 'waiting_video' if record.get('state') == 'waiting_video' else 'observing_video',
                   'waiting_video_progress', now, next_retry_at=0)
    record['frames'] = frames
    return True


def _observe_proxy(record, detail, token, now):
    if not detail:
        record.pop('proxy_token', None)
        record.pop('proxy_first_seen_at', None)
        record.pop('proxy_observations', None)
        return None
    if not token:
        _set_state(record, 'needs_attention', 'proxy_evidence_missing', now, next_retry_at=0)
        return False
    if token != record.get('proxy_token'):
        record.update(proxy_token=token, proxy_first_seen_at=now, proxy_observations=1)
    else:
        record['proxy_observations'] = record.get('proxy_observations', 0) + 1
    if detail.get('readers') != 0:
        reason = 'proxy_has_readers' if type(detail.get('readers')) is int else 'reader_evidence_missing'
        _set_state(record, 'needs_attention', reason, now, next_retry_at=0)
        return False
    if now - record['proxy_first_seen_at'] < STALL_SECONDS or record['proxy_observations'] < 2:
        if record.get('state') not in ('source_auth_paused', 'backoff'):
            _set_state(record, 'proxy_connecting', 'proxy_observing', now)
        return False
    return dict(proxy_token=token, first_seen_at=record['proxy_first_seen_at'],
                observations=record['proxy_observations'])


def run_bound_stream_recovery(enabled=True, pause_reason=None, _services=None):
    """APScheduler-compatible (success, message); never propagates raw errors."""
    services = _services
    try:
        services = services or _MonitorRuntime()
        with services.dispatch_lock() as acquired:
            if not acquired:
                return True, '流媒体自动恢复正在执行，本轮跳过'
            now, started = services.now(), services.monotonic()
            if not enabled:
                services.save_summary(dict(checked_at=now, paused=True, reason=pause_reason or 'activation_unavailable'))
                return False, '流媒体自动恢复已暂停，请检查平台激活状态'
            snapshots = services.candidates()
            observed_media, proxies = services.observe()
            media = index_media_streams(observed_media)
            records = services.load_states()
            if not isinstance(records, dict):
                raise ValueError('invalid state')
            active, attempts, counts = set(), 0, {}
            # Persisted retry deadlines provide fairness across workers/rounds.
            snapshots.sort(key=lambda item: (records.get(str(item['equipment']['id']), {}).get('last_attempt_at', 0), item['equipment']['id']))
            for snapshot in snapshots:
                equipment_id = snapshot['equipment']['id']
                identity = str(equipment_id)
                active.add(identity)
                auth = _auth_token(snapshot)
                record = records.get(identity)
                if (not isinstance(record, dict) or record.get('binding_id') != snapshot['binding']['id']
                        or record.get('auth_token') != auth):
                    record = _new_record(snapshot, now)
                record['last_observed_at'] = now
                binding = snapshot['binding']
                matching_media = media_stream_rows(media, binding['app'], binding['live']) or []
                if record.get('reconciliation_required'):
                    detail = services.proxy_detail(proxies, matching_media, binding['app'], binding['live'])
                    expected = services.proxy_token(dict(key=binding['key'], source=binding['source']))
                    if detail is not None and (not expected or services.proxy_token(detail) != expected):
                        _set_state(record, 'needs_attention', 'reconciliation_required', now)
                        services.save_state(identity, record)
                        records[identity] = record
                        continue
                    if detail is not None:
                        record.pop('reconciliation_required', None)
                evidence = _media_evidence(matching_media)
                if _observe_video(record, evidence, now):
                    record.pop('proxy_token', None)
                    record.pop('proxy_first_seen_at', None)
                    record.pop('proxy_observations', None)
                elif record.get('auth_blocked'):
                    # Observe published media, but do not retry rejected accounts.
                    _set_state(record, 'source_auth_paused', record.get('auth_reason', 'source_auth_failed'), now, next_retry_at=0)
                else:
                    detail = services.proxy_detail(proxies, matching_media, binding['app'], binding['live'])
                    stalled = _observe_proxy(record, detail, services.proxy_token(detail), now)
                    ready = detail is None or isinstance(stalled, dict)
                    due = now >= record.get('next_retry_at', 0)
                    budget = attempts < MAX_ATTEMPTS and services.monotonic() - started < ROUND_BUDGET
                    if ready and due and budget:
                        attempts += 1
                        record.update(attempts=record.get('attempts', 0) + 1, last_attempt_at=now,
                                      next_retry_at=now + BASE_RETRY)
                        _set_state(record, 'recovering', 'attempt_reserved', now)
                        # Reserve before any source probe or proxy mutation. A
                        # Redis failure aborts the round, failing closed.
                        services.save_state(identity, record)
                        response = services.recover(equipment_id, stalled if isinstance(stalled, dict) else None)
                        result_time = services.now()
                        reason = response.get('reason', 'recovery_failed')
                        if reason not in REASONS:
                            reason = 'recovery_failed'
                        data = response.get('data') or {}
                        if reason == 'source_auth_failed':
                            _set_state(record, 'source_auth_paused', reason, result_time,
                                next_retry_at=0, source_status=response.get('source_status'),
                                auth_blocked=True, auth_reason=reason)
                        elif response.get('code') == 202 and data.get('changed') is True:
                            _set_state(record, 'waiting_video', 'waiting_video', result_time,
                                next_retry_at=result_time + BASE_RETRY, failures=0, reconciliation_required=False)
                            # Source/key changed through CAS; retain audit state
                            # across that intentional change until video advances.
                            latest = services.current_snapshot(equipment_id)
                            record['auth_token'] = _auth_token(latest)
                            record.pop('frames', None)
                            record.pop('frame_sample_at', None)
                            record.pop('proxy_token', None)
                        elif response.get('code') == 200 or (response.get('code') == 202 and not data.get('requires_reconciliation')):
                            _set_state(record, 'waiting_video', 'waiting_video_progress', result_time,
                                next_retry_at=result_time + BASE_RETRY)
                        else:
                            failures = min(30, record.get('failures', 0) + 1)
                            delay = min(MAX_RETRY, BASE_RETRY * (2 ** min(failures - 1, 4)))
                            state = 'needs_attention' if data.get('requires_reconciliation') else 'backoff'
                            if data.get('requires_reconciliation'):
                                reason = 'reconciliation_required'
                            _set_state(record, state, reason, result_time, failures=failures,
                                next_retry_at=result_time + delay, source_status=response.get('source_status'),
                                reconciliation_required=bool(data.get('requires_reconciliation')))
                services.save_state(identity, record)
                records[identity] = record
            for identity, record in records.items():
                if identity not in active and isinstance(record, dict):
                    _set_state(record, 'inactive', 'not_eligible', now, next_retry_at=0)
                    services.save_state(identity, record)
                if isinstance(record, dict):
                    counts[record.get('state', 'needs_attention')] = counts.get(record.get('state', 'needs_attention'), 0) + 1
            summary = dict(checked_at=services.now(), paused=False, attempted=attempts,
                           eligible=len(snapshots), counts=counts, budget_seconds=ROUND_BUDGET)
            services.save_summary(summary)
            return True, '流媒体自动恢复：检查 {} 路，尝试 {} 路；状态已记录'.format(len(snapshots), attempts)
    except Exception:
        # Exception text can contain RTSP/Redis credentials. Fixed event only.
        logger.warning('bound_stream_recovery {"state":"needs_attention","reason":"service_unavailable"}')
        if services is not None:
            try:
                services.save_summary(dict(checked_at=services.now(), paused=False, observation_failed=True))
            except Exception:
                pass
        return False, '流媒体自动恢复暂未完成，请检查内部恢复状态'


def get_bound_recovery_status(_services=None):
    """Read-only, sanitized status for an existing administrator endpoint."""
    try:
        services = _services or _MonitorRuntime()
        records = services.load_states()
        summary = services.load_summary()
        now = services.now()
        checked_at = summary.get('checked_at') if isinstance(summary, dict) else None
        if (not isinstance(summary, dict) or not _number(now)
                or (summary and (not _number(checked_at) or checked_at > now + 5 or now - checked_at > 180))):
            return dict(code=503, msg='流媒体恢复状态可能已过期，请稍后重试')
        devices, counts = [], {}
        for snapshot in sorted(services.candidates(), key=lambda item: item['equipment']['id']):
            equipment_id = snapshot['equipment']['id']
            record = records.get(str(equipment_id))
            if (not isinstance(record, dict) or record.get('binding_id') != snapshot['binding']['id']
                    or record.get('auth_token') != _auth_token(snapshot)):
                record = _new_record(snapshot, services.now())
            safe = _public(record)
            state, reason = safe['state'], safe['reason']
            if not summary and state == 'healthy':
                state, reason = 'observing_video', 'waiting_video_progress'
            if summary.get('observation_failed') and not record.get('auth_blocked'):
                state, reason = 'needs_attention', 'service_unavailable'
            name = snapshot.get('display_name') or '设备 {}'.format(equipment_id)
            name = ''.join(char for char in str(name)[:128] if ord(char) >= 32)
            devices.append(dict(id=equipment_id, name=name, state=state, reason=reason,
                last_attempt=safe.get('last_attempt_at'), next_retry=safe.get('next_retry_at') or None,
                failures=safe.get('failures', 0)))
            counts[state] = counts.get(state, 0) + 1
        return dict(code=200, data=dict(enabled=not bool(summary.get('paused')),
            checked_at=summary.get('checked_at'), summary=counts, devices=devices))
    except Exception:
        return dict(code=503, msg='无法读取流媒体自动恢复状态')


def seed_auth_pause(equipment_id, reason='account_maintenance', expected_auth_token=None, _services=None):
    """One-time deployment seed; no source probes, credentials or DB writes.

    The persistent seed marker prevents restarts from reseeding an account the
    user subsequently repaired. Deployment may pass its prechecked fingerprint
    to reject changes occurring before the first seed as well.
    """
    try:
        from service.bound_preview_recovery import _identity, _validate
        equipment_id = _identity(equipment_id)
        if reason not in ('account_maintenance', 'source_auth_failed'):
            return dict(code=400, msg='维护暂停原因无效')
        services = _services or _MonitorRuntime()
        first = services.current_snapshot(equipment_id)
        _validate(first)
        token = _auth_token(first)
        if expected_auth_token is not None and token != expected_auth_token:
            return dict(code=409, msg='接入配置已变化，未设置维护暂停')
        second = services.current_snapshot(equipment_id)
        if _auth_token(second) != token:
            return dict(code=409, msg='接入配置已变化，未设置维护暂停')
        record = _new_record(second, services.now())
        record.update(state='source_auth_paused', reason=reason, next_retry_at=0,
                      auth_blocked=True, auth_reason=reason, last_observed_at=services.now())
        created = services.seed_pause(str(equipment_id), record)
        if created:
            logger.info('bound_stream_recovery %s', json.dumps(_public(record), sort_keys=True, ensure_ascii=False))
        return dict(code=200, data=dict(id=equipment_id, created=bool(created)))
    except Exception:
        return dict(code=503, msg='无法设置维护暂停')


class _MonitorRuntime:
    def __init__(self):
        from service.bound_preview_recovery import (
            _Runtime, _validate, _detail_for_proxy_matches, _index_proxies, _proxy_token, recover_bound_preview,
        )
        self.runtime, self.validate = _Runtime(), _validate
        self._index_proxies, self._detail_for_proxy_matches = _index_proxies, _detail_for_proxy_matches
        self.proxy_token = _proxy_token
        self.recover_function = recover_bound_preview
        self.client = self.runtime.source._redis()

    now = staticmethod(time.time)
    monotonic = staticmethod(time.monotonic)

    @contextlib.contextmanager
    def dispatch_lock(self):
        token = uuid.uuid4().hex
        acquired = self.client.set(DISPATCH_LOCK, token, nx=True, ex=300)
        try:
            yield bool(acquired)
        finally:
            if acquired:
                try:
                    self.client.eval(self.runtime.source._RELEASE_LOCK, 1, DISPATCH_LOCK, token)
                except Exception:
                    pass

    def candidates(self):
        from sqlalchemy import and_, or_
        from sqlalchemy.orm import aliased
        from service.bound_preview_recovery import RecoveryError
        equipment, binding, session = self.runtime.Equipment, self.runtime.Binding, self.runtime.db.session
        parent, vcr = aliased(equipment), self.runtime.VCR
        try:
            # Start a fresh read transaction, including on MySQL REPEATABLE
            # READ; identity-map refresh alone cannot end an older snapshot.
            session.rollback()
            # Load one consistent observation without per-device SQL. Refresh
            # any already-loaded rows; queue only copied snapshot dictionaries.
            records = session.query(equipment, binding, parent, vcr).select_from(equipment).join(
                binding, binding.id == equipment.zlk_dat_id).outerjoin(
                parent, parent.id == equipment.parent_id).outerjoin(
                vcr, vcr.id == parent.VCR_data_id).filter(
                or_(equipment.user_status == '1', equipment.user_status.is_(None)),
                equipment.online == 1,
                or_(and_(equipment.parent_id.isnot(None),
                         equipment.equipment_type.in_(('录像机', '特殊摄像头', '视频中心存储'))),
                    and_(equipment.parent_id.is_(None), equipment.equipment_type == '摄像头',
                         equipment.VCR_data_id.is_(None))),
                binding.zlk_app == 'openUrl').populate_existing().all()
            result = []
            for device, saved_binding, recorder, saved_vcr in records:
                # Match _records' truthiness checks, including legacy zero IDs.
                direct_camera = (device.equipment_type == '摄像头' and device.parent_id is None
                                 and device.VCR_data_id is None)
                if not device.zlk_dat_id or (not direct_camera and (not device.parent_id or recorder is None)):
                    continue
                try:
                    current = self.runtime._snapshot((device, saved_binding, recorder,
                        saved_vcr if recorder and recorder.VCR_data_id else None))
                    self.validate(current)
                    current['display_name'] = device.equipment_name
                    result.append(current)
                except (RecoveryError, self.runtime.source.CompatError):
                    # Missing/disabled/rebound/incomplete records never queue work.
                    continue
            return result
        finally:
            session.rollback()

    def current_snapshot(self, equipment_id):
        return self.runtime.snapshot(equipment_id)

    def observe(self):
        media = self.runtime.source._proxy_api('getMediaList')
        proxies = self.runtime.source._proxy_api('listStreamProxy')
        if (media.get('code') != 0 or not isinstance(media.get('data') or [], list)
                or proxies.get('code') != 0):
            raise ValueError('media unavailable')
        # Validate identity structure before any mutation, including empty lists.
        self.runtime.identities(proxies.get('data'))
        return media.get('data') or [], self._index_proxies(proxies.get('data'))

    def proxy_detail(self, proxies, media, app, live):
        return self._detail_for_proxy_matches(proxies.get((app, live), []), media)

    def recover(self, equipment_id, stalled):
        return self.recover_function(equipment_id, _services=self.runtime, _stalled=stalled)

    def load_states(self):
        result = {}
        stored = self.client.hgetall(STATE_KEY)
        stored.update(self.client.hgetall(AUTH_KEY))
        for key, value in stored.items():
            key = key.decode('ascii') if isinstance(key, bytes) else str(key)
            if not key.isascii() or not key.isdigit():
                raise ValueError('invalid state id')
            record = json.loads(value)
            if not isinstance(record, dict):
                raise ValueError('invalid state')
            result[key] = record
        return result

    def save_state(self, identity, record):
        payload = json.dumps(record, separators=(',', ':'), ensure_ascii=False)
        if record.get('auth_blocked'):
            # Authentication refusal survives the ordinary 24h state TTL.
            self.client.hset(AUTH_KEY, identity, payload)
        else:
            self.client.hdel(AUTH_KEY, identity)
        self.client.hset(STATE_KEY, identity, payload)
        self.client.expire(STATE_KEY, 86400)

    def save_summary(self, summary):
        self.client.set(SUMMARY_KEY, json.dumps(summary, separators=(',', ':')), ex=86400)

    def load_summary(self):
        raw = self.client.get(SUMMARY_KEY)
        return json.loads(raw) if raw else {}

    def seed_pause(self, identity, record):
        script = """
        if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then return 0 end
        redis.call('HSET', KEYS[1], ARGV[1], '1')
        if redis.call('HEXISTS', KEYS[2], ARGV[1]) == 1 then return 0 end
        redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
        redis.call('HSET', KEYS[3], ARGV[1], ARGV[2])
        redis.call('EXPIRE', KEYS[3], 86400)
        return 1
        """
        return self.client.eval(script, 3, SEED_KEY, AUTH_KEY, STATE_KEY, identity,
                                json.dumps(record, separators=(',', ':'), ensure_ascii=False))
