"""Downsample stored task configuration stills for the authenticated task list."""
from functools import lru_cache
import os
from pathlib import Path
import re
import stat

import cv2
import numpy as np
from flask import Response

from service.algorithm_stream_source import normalize_stream_type


MAX_SOURCE_BYTES = 16 * 1024 * 1024
THUMBNAIL_SIZE = (192, 108)
EQUIPMENT_ID = re.compile(r'[1-9][0-9]{0,9}\Z')


def _signature(info):
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SOURCE_BYTES:
        raise ValueError('invalid snapshot file')
    return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size


@lru_cache(maxsize=192)
def _render(path, signature):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if _signature(os.fstat(stream.fileno())) != signature:
            raise FileNotFoundError('snapshot replaced')
        payload = stream.read(signature[-1] + 1)
        if len(payload) != signature[-1] or not payload.startswith(b'\xff\xd8'):
            raise ValueError('invalid JPEG')
    frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_REDUCED_COLOR_2)
    if frame is None or frame.size == 0:
        raise ValueError('invalid JPEG')
    view = cv2.resize(frame, THUMBNAIL_SIZE, interpolation=cv2.INTER_AREA)
    success, encoded = cv2.imencode('.jpg', view, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not success:
        raise ValueError('JPEG encoding failed')
    return encoded.tobytes()


def task_roi_thumbnail(equipment_id, stream_type):
    from config.configs import FILE_SAVE_PATH

    identifier = equipment_id or ''
    if not isinstance(identifier, str) or not EQUIPMENT_ID.fullmatch(identifier):
        return Response(status=400)
    try:
        profile = normalize_stream_type(stream_type)
    except ValueError:
        return Response(status=400)
    suffix = '_' + profile if profile else ''
    path = Path(FILE_SAVE_PATH) / ('em_' + identifier + suffix + '.jpg')
    for _ in range(2):
        try:
            pixels = _render(str(path), _signature(path.lstat()))
            return Response(pixels, mimetype='image/jpeg', headers={'Cache-Control': 'private, no-store'})
        except FileNotFoundError:
            # An atomic native still can be replaced between stat and open.
            continue
        except (OSError, ValueError, cv2.error):
            break
    return Response(status=404, headers={'Cache-Control': 'private, no-store'})
