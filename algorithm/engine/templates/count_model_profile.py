"""Model-specific validation of measured crossings on a drawn counting line."""
from collections import deque
import logging
import re
import numpy as np


def count_model_profile(analysis_type, model_path):
    names = {'头肩': 'head_shoulder', '全身': 'full_body'}
    explicit = re.fullmatch(r'人数统计[\s_-]*(头肩|全身)', str(analysis_type or '').strip())
    # Use the selected model's filename, never the task name or its directories.
    filename = re.split(r'[/\\]', str(model_path or ''))[-1]
    types = set(re.findall(r'(?:^|[_-])人数统计[\s_-]*(头肩|全身)(?=[_.-]|$)', filename))
    if explicit:
        types.add(explicit.group(1))
    if len(types) == 1:
        return names[types.pop()]
    if types:
        logging.warning('[counting] 模型文件与解析类型的头肩/全身标记有冲突，使用原实测过线规则')
    return 'legacy'


class FullBodyCrossing:
    """Confirm a measured bottom-edge crossing using translation or perspective change."""

    def __init__(self, geometry):
        self.geometry = geometry
        self.box_edges = deque(maxlen=8)
        self.last_segment = None
        self.last_event = None
        self.furthest_top = 0.0

    def reset(self):
        self.geometry.reset()
        self.box_edges.clear()
        self.last_segment = self.last_event = None

    def observe_box(self, line, foot, margin, bbox, image=None):
        top = (foot[0], bbox[1])
        sample = (top, foot, bbox[2] - bbox[0])
        previous, origin, _ = self.box_edges[-1] if self.box_edges else sample
        self.box_edges.append(sample)
        if self.last_segment is not None:
            # Returning around an end can lead to another valid same-direction pass.
            _, along = self.last_segment.position(foot)
            if along < 0 or along > self.last_segment.length:
                self.last_segment = self.last_event = None
            else:
                last_sign = line.enter_cross_sign if self.last_event == 'enter' else -line.enter_cross_sign
                top_distance, _ = self.last_segment.position(top)
                self.furthest_top = max(self.furthest_top, last_sign * top_distance)
        event = self.geometry.observe(line, foot, margin)
        if event is None:
            return None
        sign = line.enter_cross_sign if event == 'enter' else -line.enter_cross_sign
        segment = self._crossed_leg(line.gate_segments, origin, foot, sign)
        if segment is None or (segment is self.last_segment and event == self.last_event):
            return None
        # Measure normal displacement, not speed along the gate. The rectangle
        # top need not cross the line. It corroborates motion of the box bottom.
        top_distance = sign * segment.position(top)[0]
        immediate = top_distance - sign * segment.position(previous)[0]
        first_top, first_foot, _ = self.box_edges[0]
        approach = top_distance - sign * segment.position(first_top)[0]
        foot_step = sign * (segment.position(foot)[0] - segment.position(origin)[0])
        measured_approach = sign * (segment.position(foot)[0] - segment.position(first_foot)[0])
        deformation = abs(foot_step - immediate)
        # A small rigid translation can be a genuine immediate U-turn. A box
        # that changes height abruptly needs independent motion in its upper edge.
        translating = immediate > 0 and deformation <= max(1., abs(foot_step) * .25)
        smooth_approach = (approach > 0 and measured_approach >= margin
                           and deformation <= margin)
        top_support = (translating or smooth_approach or max(immediate, approach) >= .5)
        if deformation > margin and immediate < -2.0 and approach < deformation * .5:
            top_support = False
        if self.last_segment is segment and not translating and self.furthest_top + top_distance < margin:
            top_support = False
        if not top_support and not self._perspective_motion(segment, sign):
            return None
        self.last_segment, self.last_event = segment, event
        self.furthest_top = top_distance
        return event

    def _perspective_motion(self, segment, sign):
        # Near the camera, the box can grow upwards while its lower edge moves
        # down. Check that width independently corroborates the height change
        # over the approach and the actual crossing step. A one-frame resize
        # or an extending leg supplies no such approach.
        if len(self.box_edges) < 3:
            return False
        a, b, c = self.box_edges[-3], self.box_edges[-2], self.box_edges[-1]
        if (b[2] - a[2]) * (c[2] - b[2]) <= 0:
            return False
        for before, after in ((a, b), (b, c)):
            top, foot, width = before
            new_top, new_foot, new_width = after
            height = foot[1] - top[1]
            height_change = (new_foot[1] - new_top[1]) - height
            if width <= 0 or height <= 0 or abs(new_width - width) < 1:
                return False
            scaled_change = height * (new_width - width) / width
            # Compare relative changes in both dimensions. Cropping a lower
            # leg can sharply change height with essentially the same width.
            if not .5 <= height_change / scaled_change <= 2.0:
                return False
            measured = segment.position(new_foot)[0] - segment.position(foot)[0]
            upper_motion = segment.position(new_top)[0] - segment.position(top)[0]
            if min(sign * measured, sign * (upper_motion + segment.ux * scaled_change)) <= 0:
                return False
        return True

    @staticmethod
    def _crossed_leg(segments, origin, foot, sign):
        if len(segments) == 1:
            return segments[0]
        # At a polyline corner only use a normal for a segment this measured
        # step actually crossed. Prefer the last such crossing along the step.
        last_fraction, crossed = -1.0, None
        for leg in segments:
            a, u = leg.position(origin)
            b, v = leg.position(foot)
            if sign * a <= 0 < sign * b:
                fraction = a / (a - b)
                if fraction > last_fraction and leg.contains(u + fraction * (v - u)):
                    last_fraction, crossed = fraction, leg
        return crossed


class FullBodyLineSearch:
    """Propose bounded current-frame detector crops from recent near-line observations."""

    def __init__(self, points, resolution):
        self.points = points
        self.resolution = resolution
        self.history = deque(maxlen=3)
        self.stamp = None
        self.shape = None

    @staticmethod
    def overlap(a, b):
        width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
        height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        common = width * height
        union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - common
        return common / max(1, union)

    def crops(self, width, height, primary, stamp):
        if self.shape != (width, height) or self.stamp is None or not 0 < stamp - self.stamp <= .5:
            self.history.clear()
        self.stamp, self.shape = stamp, (width, height)
        scale = np.array([width, height]) / (self.resolution or (width, height))
        line = np.asarray(self.points, dtype=float) * scale
        candidates = []
        for boxes in reversed(self.history):
            for x, y, r, b in boxes:
                foot = np.array([(x+r)/2, b])
                distance = float('inf')
                for start, end in zip(line, line[1:]):
                    axis = end - start
                    ratio = np.clip(np.dot(foot - start, axis) / max(1., np.dot(axis, axis)), 0., 1.)
                    distance = min(distance, np.linalg.norm(foot - start - ratio * axis))
                if distance > max(24, .65*(b-y)):
                    continue
                size = min(width, height, max(224, round((b-y)*1.65/32)*32))
                cx, cy = (x+r)//2, (y+b)//2
                if any(abs(px-cx)<.12*size and abs(py-cy)<.12*size for px,py,_ in candidates):
                    continue
                candidates.append((cx, cy, size))
                if len(candidates) == 2:
                    break
            if len(candidates) == 2:
                break
        self.history.append([row[2] for row in primary])
        return [(max(0,min(width-size,cx-size//2)), max(0,min(height-size,cy-size//2)), size)
                for cx,cy,size in candidates]

    def combine(self, primary, proposals):
        def same_upper_body(a, b):
            # A cropped torso and a full box can share a head but have low IoU.
            width = min(a[2]-a[0], b[2]-b[0])
            height = min(a[3]-a[1], b[3]-b[1])
            if width <= 0 or height <= 0:
                return False
            if abs((a[0]+a[2]) - (b[0]+b[2])) > .24*width or abs(a[1]-b[1]) > .08*height:
                return False
            common = max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0, min(a[3],b[3])-max(a[1],b[1]))
            return common >= .90*min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))

        result = []
        for row in sorted(primary, key=lambda item: -float(item[1])):
            if not any(same_upper_body(row[2], p[2]) for p in result if p[0] == row[0]):
                result.append(row)
        for row in sorted(proposals, key=lambda item: -float(item[1])):
            if any(self.overlap(row[2], p[2]) > .23 for p in primary if p[0] == row[0]):
                continue
            if all(self.overlap(row[2], p[2]) <= .45 and not same_upper_body(row[2], p[2])
                   for p in result if p[0] == row[0]):
                result.append(row)
        return result

    def detect(self, image, primary, stamp, infer):
        height, width = image.shape[:2]
        proposals = []
        for x, y, size in self.crops(width, height, primary, stamp):
            region = image[y:y+size, x:x+size]
            for label, score, box in infer(region):
                left, top, right, bottom = box
                if left <= 1 or top <= 1 or right >= size-1 or bottom >= size-1:
                    continue
                proposals.append([label, score, [x+left, y+top, x+right, y+bottom]])
        return self.combine(primary, proposals)


class VisualCrossing:
    """Verify the detector's measured crossing against the person's image on the same step."""

    def __init__(self, geometry, profile):
        self.geometry = geometry
        self.profile = profile
        self.previous = None
        self.last_pass = None
        self.approach = deque(maxlen=5)
        self.observation = None
        self.missing = False
        self.evidence_kind = 'observed'

    def reset(self):
        self.geometry.reset()
        self.previous = self.last_pass = None
        self.approach.clear()
        self.observation = None
        self.missing = False
        self.evidence_kind = 'observed'

    def mark_missing(self):
        if self.profile == 'full_body' and self.previous is not None:
            self.missing = True
        else:
            self.reset()

    def observe_sample(self, line, foot, margin, box, image, frame_no, stamp):
        last_clock = self.observation
        self.evidence_kind = 'observed'
        if not self.missing:
            self.observation = frame_no, stamp
            return self.observe_box(line, foot, margin, box, image)

        # The tracker calls here only after a unique re-identification. Establish
        # the new measured side even when the gap cannot support an inference.
        last, approach, last_pass = self.previous, tuple(self.approach), self.last_pass
        self.reset()
        self.last_pass = last_pass
        self.observation = frame_no, stamp
        self.observe_box(line, foot, margin, box, image)
        if last_clock is None or stamp is None or last_clock[1] is None:
            return None
        frames = frame_no - last_clock[0]
        if not (2 <= frames <= 9 and 0 < stamp - last_clock[1] <= .8):
            return None
        sample = self.previous[1]
        if len(approach) < 2 or last[1] is None or sample is None:
            return None
        return self._bridge(line, approach, last, foot, sample)

    def _bridge(self, line, approach, last, foot, sample):
        import cv2
        origin, before = last
        # Crops are normalized to the same dimensions. A similarity check
        # independent of the predicted position protects a returning identity.
        a, b = before[0][10:49, 9:39], sample[0][10:49, 9:39]
        scale = sample[2] / before[2]
        if min(a.std(), b.std()) < 6 or min(scale) < .55 or max(scale) > 1.8:
            return None
        if cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0] < .42:
            return None
        clear = max(4., min(14., before[2][1] * 64 * .04))
        crossings = []
        for leg in line.gate_segments:
            start, u = leg.position(origin)
            end, v = leg.position(foot)
            if start * end >= 0:
                continue
            fraction = start / (start - end)
            if leg.contains(u + fraction * (v - u)):
                crossings.append((leg, start, end, fraction))
        if len(crossings) != 1:
            return None
        leg, start, end, fraction = crossings[0]
        sign = 1 if end > 0 else -1
        history = [sign * leg.position(p)[0] for p in approach[:-1]]
        # A single jittery footpoint need not be monotone. Earlier observations
        # must establish the approach side and progress toward this specific leg.
        if max(history) >= 0 or sign * start - float(np.median(history)) < 1.:
            return None
        event = 'enter' if sign == line.enter_cross_sign else 'exit'
        if min(abs(start), abs(end)) < 1. or abs(end-start) < clear or self.last_pass == (leg, event):
            return None
        intersection = tuple(float(x + fraction * (y-x)) for x,y in zip(origin, foot))
        regions = getattr(line, 'count_regions', ())
        if regions and not any(cv2.pointPolygonTest(poly, intersection, False) >= 0 for poly in regions):
            return None
        if self._person_motion(before, sample, leg, sign):
            self.last_pass = leg, event
            self.evidence_kind = 'inferred_crossing'
            return event
        return None

    @staticmethod
    def _sample(image, box):
        import cv2
        if image is None:
            return None
        h, w = image.shape[:2]
        x, y, right, bottom = map(int, box)
        x, y = max(0, x), max(0, y)
        right, bottom = min(w, right), min(h, bottom)
        if right - x < 6 or bottom - y < 6:
            return None
        patch = cv2.resize(image[y:bottom, x:right], (48, 64), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        return gray, np.array([x, y]), np.array([(right-x)/48., (bottom-y)/64.])

    def _person_motion(self, before, after, leg, sign):
        import cv2
        a, origin, scale = before
        b, destination, new_scale = after
        mask = np.zeros_like(a)
        # Gate heads include helmets and shoulders. On full people the torso is
        # more reliable than a swinging foot, a handlebar or a clipped box edge.
        bottom = 57 if self.profile == 'head_shoulder' else 50
        mask[9:bottom, 9:39] = 255
        points = cv2.goodFeaturesToTrack(a, 32, .012, 3, mask=mask)
        if points is None or len(points) < 3:
            return False
        if self.profile == 'full_body':
            mask.fill(0)
            mask[51:62, 12:36] = 255
            lower_points = cv2.goodFeaturesToTrack(a, 18, .012, 2, mask=mask)
            if lower_points is not None:
                points = np.concatenate((points, lower_points))
        options = dict(winSize=(11, 11), maxLevel=2)
        nxt, valid, _ = cv2.calcOpticalFlowPyrLK(a, b, points, None, **options)
        if nxt is None:
            return False
        back, checked, _ = cv2.calcOpticalFlowPyrLK(b, a, nxt, None, **options)
        if back is None:
            return False
        pts, dest = points[:, 0], nxt[:, 0]
        good = (valid.ravel() != 0) & (checked.ravel() != 0)
        good &= np.max(np.abs(back[:, 0] - pts), axis=1) < 1.2
        good &= (dest[:, 0] >= 2) & (dest[:, 0] < 46) & (dest[:, 1] >= 2) & (dest[:, 1] < 62)
        if np.count_nonzero(good) < 3:
            return False
        pts, dest = pts[good], dest[good]
        deltas = destination - origin + (dest + .5)*new_scale - (pts + .5)*scale
        normal = sign * (leg.ux * deltas[:, 1] - leg.uy * deltas[:, 0])
        if self.profile == 'full_body':
            feet = (pts[:, 1] >= 51) & (dest[:, 1] > 42)
            if np.count_nonzero(feet) >= 2 and np.mean(np.linalg.norm(deltas[feet], axis=1) < .7) >= .65:
                return False
            torso = pts[:, 1] < 51
            pts, normal = pts[torso], normal[torso]
            if len(normal) < 3:
                return False
        # A rigid detector translation also moves its crop of a *stationary*
        # person; mapping features back to the original frame cancels that shift.
        # Near the lens upper and lower features can move in opposite directions.
        # Derive the normal motion at the lower edge from measured texture at
        # separated heights. Never let a single moving feature certify a pass.
        # A slow person can move less than one pixel while a loose detector
        # box moves several. Use agreement among independent texture points
        # rather than setting a speed floor proportional to that box jump.
        required = .5
        if self.profile == 'full_body':
            # A second rider's legs can extend a box while the first rider's
            # torso hardly moves. Uniform perspective scaling is common here.
            ratios = new_scale / scale
            if abs(ratios[1] - 1.) > .25 and abs(ratios[1] - ratios[0]) > .25:
                foot_step = destination - origin + (new_scale - scale) * (24, 64)
                distance = abs(leg.ux * foot_step[1] - leg.uy * foot_step[0])
                required = max(required, distance * .3)
        if np.median(normal) >= required and np.mean(normal > .25) >= .6:
            return True
        if self.profile != 'full_body':
            return False
        upper = pts[:, 1] < 26
        lower = pts[:, 1] >= 32
        if min(np.count_nonzero(upper), np.count_nonzero(lower)) < 3:
            return False
        hi, lo = np.median(normal[upper]), np.median(normal[lower])
        return lo >= required and lo > hi and np.median(normal) > -required

    def observe_box(self, line, foot, margin, box, image):
        last = self.previous
        sample = self._sample(image, box)
        if self.profile == 'full_body':
            self.approach.append(foot)
        self.previous = foot, sample
        if self.last_pass is not None:
            leg, _ = self.last_pass
            _, along = leg.position(foot)
            if along < 0 or along > leg.length:
                self.last_pass = None
        # Real image motion validates short immediate returns, including those
        # inside the old re-arm band. No pending event or future sample is used.
        event = self.geometry.observe(line, foot, 0.)
        if event is None or last is None or last[1] is None or sample is None:
            return None
        sign = line.enter_cross_sign if event == 'enter' else -line.enter_cross_sign
        leg = FullBodyCrossing._crossed_leg(line.gate_segments, last[0], foot, sign)
        if leg is None or self.last_pass == (leg, event):
            return None
        if self._person_motion(last[1], sample, leg, sign):
            self.last_pass = leg, event
            return event
        return None
