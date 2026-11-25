"""Report the alarm interval independently of the recording's retained footage."""

from datetime import datetime
from collections import Counter
import math
from pathlib import Path
import re


_TOTALS = re.compile(r'总进入\s*([0-9]+)\s*人\s*[,，]\s*总离开\s*([0-9]+)\s*人')
_PICTURE_NAME = re.compile(r'alarm_[0-9a-f]{32}_[0-9]{6}\.jpg')
_SHORTFALL_TOLERANCE = 1.1  # Alarm row times are only precise to one second.
_MAX_BOX_HEADERS = 4096


def _nonnegative_count(value):
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and len(value) <= 18 and value.isascii() and value.isdecimal():
        return int(value)
    return None


def _alarm_time(value):
    try:
        if isinstance(value, str):
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if isinstance(value, datetime):
            return value.timestamp(), value.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OverflowError, OSError):
        pass
    return None, None


def _boxes(stream, start, stop):
    """Yield valid bounded ISO BMFF box contents without reading media payloads."""
    position = start
    for _ in range(_MAX_BOX_HEADERS):
        if position == stop:
            return
        if stop - position < 8:
            raise ValueError('Incomplete media box header')
        stream.seek(position)
        header = stream.read(8)
        if len(header) != 8:
            raise ValueError('Incomplete media box header')
        length = int.from_bytes(header[:4], 'big')
        header_size = 8
        if length == 1:
            extended = stream.read(8)
            if len(extended) != 8:
                raise ValueError('Incomplete extended media box header')
            length = int.from_bytes(extended, 'big')
            header_size = 16
        elif length == 0:
            length = stop - position
        if not header_size <= length <= stop - position:
            raise ValueError('Media box is out of bounds')
        yield header[4:], position + header_size, position + length
        position += length
    raise ValueError('Too many media box headers')


def movie_duration(path):
    """Read the movie timescale and duration, including the 64-bit header format."""
    if path is None or Path(path).suffix.lower() not in ('.mp4', '.mov', '.m4v'):
        return None
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            for name, start, end in _boxes(stream, 0, stream.tell()):
                if name != b'moov':
                    continue
                for box, offset, limit in _boxes(stream, start, end):
                    if box != b'mvhd':
                        continue
                    stream.seek(offset)
                    content = stream.read(min(32, limit - offset))
                    if len(content) >= 20 and content[0] == 0:
                        scale = int.from_bytes(content[12:16], 'big')
                        length = int.from_bytes(content[16:20], 'big')
                        unavailable = 2 ** 32 - 1
                    elif len(content) >= 32 and content[0] == 1:
                        scale = int.from_bytes(content[20:24], 'big')
                        length = int.from_bytes(content[24:32], 'big')
                        unavailable = 2 ** 64 - 1
                    else:
                        return None
                    return length / scale if scale and 0 < length < unavailable else None
    except (OSError, ValueError, OverflowError):
        return None
    return None


def replay_scope(result, path=None, verified_coverage=None):
    name = getattr(result, 'algorithm_name', '')
    entered = _nonnegative_count(getattr(result, 'Entering_num', None))
    exited = _nonnegative_count(getattr(result, 'Exiting_num', None))
    if not isinstance(name, str) or not ('人数统计' in name or name.strip() == '人员计数'):
        return None
    if entered is None or exited is None or not (entered or exited):
        return None

    lo, start = _alarm_time(getattr(result, 'result_count_time', None))
    hi, end = _alarm_time(getattr(result, 'res_time', None))
    span = hi - lo if lo is not None and hi is not None and hi >= lo else None
    duration = movie_duration(path)
    timeline = verified_coverage if isinstance(verified_coverage, dict) else None
    assessment = timeline['coverage'] if timeline is not None else verified_coverage
    coverage = 'unknown'
    if span is not None and duration is not None and duration + _SHORTFALL_TOLERANCE < span:
        coverage = 'partial'
    elif span is not None and assessment in ('full', 'partial'):
        coverage = assessment

    message = getattr(result, 'warning_message', None)
    totals = _TOTALS.fullmatch(message.strip()) if isinstance(message, str) and len(message) <= 128 else None
    scope = {
        'entering': entered, 'exiting': exited,
        'total_entering': int(totals[1]) if totals else None,
        'total_exiting': int(totals[2]) if totals else None,
        'start_time': start, 'end_time': end,
        'interval_seconds': round(span, 2) if span is not None else None,
        'recording_seconds': round(duration, 2) if duration is not None else None,
        'coverage': coverage,
    }
    if timeline is not None:
        scope['timeline'] = _public_timeline(timeline, duration, coverage)
    return scope


def _time_label(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def _confirmed_pictures(receipt, names, first, last):
    entries = receipt.get('images')
    if not isinstance(entries, list) or len(entries) > 512:
        return []
    allowed = Counter(names)
    duplicate = Counter(item.get('name') for item in entries if isinstance(item, dict)
                        and isinstance(item.get('name'), str))
    pictures = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        stamp = item.get('platform_ts')
        kind = item.get('evidence_kind')
        if (not isinstance(name, str) or not _PICTURE_NAME.fullmatch(name)
                or allowed[name] != 1 or duplicate[name] != 1
                or kind not in ('observed', 'last_visible')
                or type(stamp) not in (int, float) or not math.isfinite(stamp)):
            continue
        try:
            label = _time_label(stamp)
        except (OSError, OverflowError, ValueError):
            continue
        picture = {'name': name, 'platform_time': label, 'evidence_kind': kind}
        offset, source = item.get('offset_seconds'), item.get('source_ts')
        # A capture time alone must never be presented as a matched video frame.
        if (type(offset) in (int, float) and math.isfinite(offset)
                and type(source) in (int, float) and source == stamp
                and first <= source <= last and offset >= 0
                and abs(offset - (source - first)) <= .005):
            picture['offset_seconds'] = round(offset, 3)
        pictures.append(picture)
    return pictures


def _public_timeline(timeline, duration, coverage):
    start, end = timeline['start'], timeline['end']
    first, last = timeline['first'], timeline['last']
    result = {
        'alarm_start': _time_label(start), 'alarm_end': _time_label(end),
        'recording_start': _time_label(first), 'recording_end': _time_label(last),
    }
    # The writer preserves source PTS. Verify the recorded duration before
    # mapping its absolute clock to the browser's media clock.
    can_seek = duration is not None and abs(duration - (last - first)) <= _SHORTFALL_TOLERANCE
    if can_seek and coverage == 'full':
        for name, stamp in (('alarm_start_offset_seconds', start), ('alarm_end_offset_seconds', end)):
            offset = stamp - first
            if first <= stamp <= last and offset < duration:
                result[name] = round(offset, 3)
    if timeline['pictures']:
        result['pictures'] = []
        for picture in timeline['pictures']:
            display = dict(picture)
            if not can_seek or display.get('offset_seconds', 0) >= duration:
                display.pop('offset_seconds', None)
            result['pictures'].append(display)
    return result


def receipt_timeline(result, path, receipt, image_names=()):
    """Use timing only when the recorder receipt identifies this alarm and file."""
    alarm_start, _ = _alarm_time(getattr(result, 'result_count_time', None))
    alarm_end, _ = _alarm_time(getattr(result, 'res_time', None))
    try:
        file_info = path.stat()
        start, end = receipt['start'], receipt['end']
        first, last = receipt['first_frame'], receipt['last_frame']
        max_gap = receipt['largest_gap']
        frame_tolerance = receipt['frame_tolerance']
        if not all(type(v) in (int, float) and math.isfinite(v)
                   for v in (start, end, first, last, max_gap, frame_tolerance)):
            return None
        if (receipt['conf_name'] != getattr(result, 'conf_name', None)
                or receipt['video_size'] != file_info.st_size or receipt['video_mtime_ns'] != file_info.st_mtime_ns
                or not file_info.st_size or alarm_start is None or alarm_end is None
                or abs(start - alarm_start) > _SHORTFALL_TOLERANCE or abs(end - alarm_end) > _SHORTFALL_TOLERANCE
                or start > end or first >= last or max_gap < 0 or not .15 <= frame_tolerance <= 1.0):
            return None
        for value in (start, end, first, last):
            _time_label(value)
        fully_observed = first <= start + frame_tolerance and last >= end - frame_tolerance and max_gap <= 1.0
        return {'coverage': 'full' if fully_observed else 'partial',
                'start': start, 'end': end, 'first': first, 'last': last,
                'pictures': _confirmed_pictures(receipt, image_names, first, last)}
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None
