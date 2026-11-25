"""Recover a count's real frames and annotations before exposing its alarm."""
import json
import logging
import os
from pathlib import Path
import queue
import threading
import time

import cv2
import numpy as np

from templates import alarm_directory, alarm_video
from templates.count_alarm_outbox import count_alarm_payload
from templates.count_session_journal import session_info
from config import common as cm


def _jpeg(frame):
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 91])
    if not ok:
        raise OSError('Failed to encode count evidence')
    return encoded.tobytes()


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix('.part')
    with scratch.open('wb') as f:
        f.write(data)
    os.replace(str(scratch), str(path))


def _primitive(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


class CountSessionMedia:
    def __init__(self, ctx, outbox, stop, render_alarm, render_scene, snapshot):
        self.ctx = ctx
        self.replica = ctx.count_replica
        self.state = self.replica.state
        self.outbox, self.stop = outbox, stop
        self.render_alarm, self.render_scene, self.snapshot = render_alarm, render_scene, snapshot
        self.root = self.state.path.parent / ('media_conf_%d' % self.state.conf_id)
        self.previous = None
        self.current = None
        self.next_sample = 0.
        self.spool = queue.Queue(2)
        self.spool_counts = {}
        self.spool_cond = threading.Condition()
        self.spool_active = threading.Event()
        self.wake = threading.Event()
        self.replica.capture = self.capture
        self.replica.wake = self.wake

    def capture(self, tracker, events, stamp, first):
        frame = self.current
        snap = self.snapshot()
        active = {t.track_id: t for t in tracker.active_tracks}
        groups = {}
        for tid, box, direction in events:
            if tid in active:
                image, visible_snap, ts = frame, snap, stamp
                rule = getattr(active[tid], 'measured_crossing', None)
                kind = getattr(rule, 'evidence_kind', 'observed')
            else:
                visible = self.ctx.last_visible.get(tid)
                if visible is None:
                    raise RuntimeError('Missing measured count evidence for track %s' % tid)
                image, visible_snap, ts = visible
                kind = 'last_visible'
            if ts not in groups:
                groups[ts] = (image, visible_snap, [])
            groups[ts][2].append((list(map(int, box)),direction,kind))
        frames = []
        if self.previous is not None:
            ts, image, previous_snap = self.previous
            if image.shape == frame.shape and ts < stamp:
                frames.append((ts, _jpeg(image), self.metadata(previous_snap, [])))
        for ts,(image, visible_snap, marks) in groups.items():
            frames.append((ts, _jpeg(image), self.metadata(visible_snap, marks)))
        if stamp not in groups:
            # The separate boarding rule may settle after its last visible
            # observation. Preserve both true frames with their own timestamps.
            frames.append((stamp, _jpeg(frame), self.metadata(snap, [])))
        return frames

    def metadata(self, snap, marks):
        return {'snap':json.loads(json.dumps(snap, default=_primitive)), 'marks':marks,
                'upload':self.ctx.upload_meta, 'directory':str(self.ctx.output_img_dir)}

    def observed(self, stamp, has_detections, crossed):
        """Bound memory to one previous frame, with sparse real video during open sessions."""
        sid = self.replica.session_id
        snap = self.snapshot()
        self.ctx.last_snap = snap
        if not has_detections and sid is None and not self.ctx.boarding:
            self.previous = None
            return
        if self.ctx.boarding:
            tracked = {t.track_id for t in self.ctx.tracker.tracks}
            for t in self.ctx.last_visible.keys() - tracked:
                del self.ctx.last_visible[t]
        due = sid and not crossed and stamp >= self.next_sample and self.spool_active.is_set()
        # Snapshot only once if both the next crossing and the auxiliary video
        # writer need this frame. The preview renderer can mutate the input later.
        if has_detections or due:
            frame = self.current.copy()
            self.previous = (stamp, frame, snap)
            if self.ctx.boarding:
                for t in self.ctx.tracker.active_tracks:
                    if t.region_origin and t.region_state and t.region_origin != t.region_state:
                        self.ctx.last_visible[t.track_id] = self.previous[1], snap, stamp
        else:
            self.previous = None
        if due:
            self.next_sample = stamp + .095
            with self.spool_cond:
                try:
                    self.spool.put_nowait((sid, stamp, frame, snap))
                except queue.Full:
                    return
                self.spool_counts[sid] = self.spool_counts.get(sid, 0) + 1

    def _spool_frames(self):
        self.spool_active.set()
        while not self.stop.is_set() or not self.spool.empty():
            try:
                sid, stamp, frame, snap = self.spool.get(timeout=.25)
            except queue.Empty:
                continue
            try:
                path = self.root / sid / ('%d.jpg' % round(stamp * 1000000))
                _write(path, _jpeg(self.render_scene(frame, snap)))
            except Exception:
                logging.exception('[counting] 备用录像帧写入失败 %s', path)
            finally:
                with self.spool_cond:
                    self.spool_counts[sid] -= 1
                    if not self.spool_counts[sid]:
                        del self.spool_counts[sid]
                        self.spool_cond.notify_all()
                self.spool.task_done()

    def _outputs(self, row):
        sid = row['id']
        context = self.root / sid
        frames = {}
        if context.is_dir():
            frames.update((int(p.stem)/1e6,p) for p in context.glob('*.jpg') if p.stem.isdecimal())
        alarms, originals, images = [], [], []
        for fid in self.state.alarm_frame_ids(sid):
            stamp, raw, encoded = self.state.alarm_frame(fid)
            meta = json.loads(encoded)
            snap = meta['snap']
            snap['regions'] = [np.asarray(p, dtype=np.int32) for p in snap['regions']]
            if meta['marks']:
                snap.update(total_enter_all=meta['entered'],total_exit_all=meta['exited'])
            decoded = cv2.imdecode(np.frombuffer(raw,np.uint8), cv2.IMREAD_COLOR)
            if decoded is None: raise ValueError('Unreadable count evidence')
            resolved = Path(meta['directory'])
            shared = '%s_%06d' % (sid,len(alarms)+1)
            if meta['marks']:
                original = resolved / ('original_'+shared+'.jpg')
                _write(original, raw)
            for box,direction,kind in meta['marks']:
                stem = '%s_%06d' % (sid,len(alarms)+1)
                marked = resolved / ('alarm_'+stem+'.jpg')
                snap.update(capture_timestamp=stamp, evidence_kind=kind)
                _write(marked, _jpeg(self.render_alarm(decoded, snap, box, direction)))
                alarms.append(alarm_directory.media_url(str(marked),cm.localhost_ip,cm.upload_port))
                originals.append(alarm_directory.media_url(str(original),cm.localhost_ip,cm.upload_port))
                images.append((marked.name,stamp,kind))
            scene = context / ('evidence_%s.jpg' % fid)
            _write(scene, _jpeg(self.render_scene(decoded, snap)))
            frames[stamp] = scene
        if not frames or not images:
            raise RuntimeError('Persisted count session has no recoverable frames')
        if len(images) != row['entered'] + row['exited']:
            raise ValueError('Count journal and per-person images disagree')
        info = session_info(row)
        payload = count_alarm_payload(meta['upload'], info, managed=True)
        direction = '0102' if row['entered'] and row['exited'] else '02' if row['exited'] else '01'
        video = alarm_video.save_count_recording(sid,payload['conf_name'],row['started'],row['ended'],
                                                 direction,images,frames)
        payload.update(carousel_images_list=alarms, ori_images_list=originals, warning_video=video)
        return payload

    def deliver(self, row):
        sid = row['id']
        with self.spool_cond:
            self.spool_cond.wait_for(lambda: sid not in self.spool_counts)
        payload = self._outputs(row)
        self.outbox.stage_ready(sid,payload)
        self.replica.mark_staged(sid)
        directory = self.root/sid
        try:
            for file in directory.iterdir():
                if file.is_file(): file.unlink()
            directory.rmdir()
        except OSError:
            logging.warning('[counting] 备用录像临时目录未清理 %s', directory)

    def run(self):
        threading.Thread(target=self._spool_frames, daemon=True, name='count_video_spool').start()
        retry = {}
        while not self.stop.is_set():
            try:
                for row in self.state.unstaged_alarm_sessions():
                    sid = row['id']
                    if retry.get(sid,0)>time.monotonic(): continue
                    try:
                        self.deliver(row)
                        retry.pop(sid,None)
                    except Exception:
                        retry[sid] = time.monotonic()+5
                        logging.exception('[counting] 报警证据仍在本地，稍后重试 %s',sid)
            except Exception:
                logging.exception('[counting] 无法读取待归档会话')
            self.wake.wait(1)
            self.wake.clear()
