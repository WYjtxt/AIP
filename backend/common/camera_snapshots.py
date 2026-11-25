"""Publish a captured JPEG only after it has been written successfully."""
import os
from pathlib import Path
import re
import tempfile

import cv2


class SnapshotWriteError(RuntimeError):
    pass


def persist_snapshot(frame, equipment_id, directory):
    identity = str(equipment_id)
    if not re.fullmatch(r'\d+(?:_(?:main|sub))?', identity):
        raise SnapshotWriteError('Invalid snapshot identity')
    root = Path(directory)
    temporary = None
    try:
        if root.is_symlink():
            raise OSError('Snapshot directory is a symlink')
        root.mkdir(parents=True, exist_ok=True, mode=0o755)
        target = root / ('em_' + identity + '.jpg')
        fd, temporary = tempfile.mkstemp(prefix='.snapshot-', suffix='.jpg', dir=str(root))
        os.close(fd)
        if not cv2.imwrite(temporary, frame) or os.path.getsize(temporary) == 0:
            raise OSError('JPEG write returned no image')
        os.chmod(temporary, 0o644)
        os.replace(temporary, str(target))
        temporary = None
        return str(target)
    except (OSError, cv2.error) as exc:
        raise SnapshotWriteError('Snapshot could not be saved') from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
