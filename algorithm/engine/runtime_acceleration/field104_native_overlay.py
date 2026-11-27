"""Optional single-pass BGR overlay for the field x86 workers."""
import ctypes
from pathlib import Path

import numpy as np


try:
    _project = ctypes.CDLL(str(Path(__file__).with_name('libfield104_overlay.so'))).project_bgr
    _ptr, _stride, _int = ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int
    _project.argtypes = [_ptr,_stride,_ptr,_stride,_ptr,_stride,_int,_int,_int,_int,_ptr,_ptr]
    _project.restype = _int
except (OSError, AttributeError):
    _project = None


def fast_project_overlay(annotated, reference, native, nearest_limits):
    if _project is None or annotated.shape != reference.shape or not native.flags.writeable:
        return False
    for a in (annotated, reference, native):
        if (a.dtype != np.uint8 or a.ndim != 3 or a.shape[2] != 3 or
                a.strides[1:] != (3,1) or a.strides[0] < a.shape[1]*3):
            return False
    if np.may_share_memory(annotated, native) or np.may_share_memory(reference, native):
        return False
    h,w = annotated.shape[:2]
    nh,nw = native.shape[:2]
    if not (0 < w <= 65536 and 0 < h <= 65536 and 0 < nw <= 65536 and 0 < nh <= 65536):
        return False
    xs,ys = nearest_limits(w,nw,False), nearest_limits(h,nh,True)
    if xs is None or ys is None:
        return False
    return bool(_project(annotated.ctypes.data, annotated.strides[0],
                         reference.ctypes.data, reference.strides[0],
                         native.ctypes.data, native.strides[0], w,h,nw,nh,
                         xs.ctypes.data,ys.ctypes.data))
