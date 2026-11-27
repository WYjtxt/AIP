"""Bounded, lossless alarm buffer blocks for the x86 AVX2 field installation."""
import ctypes
from pathlib import Path
import os

import numpy as np


def open_library(path):
    from numpy.core._multiarray_umath import __cpu_features__
    if not __cpu_features__.get('AVX2', False):
        return None
    lib = ctypes.CDLL(str(path))
    pointer, size = ctypes.c_void_p, ctypes.c_size_t
    lib.alarm_delta_encode.argtypes = [pointer, pointer, size, pointer, size]
    lib.alarm_delta_encode.restype = size
    lib.alarm_delta_decode.argtypes = [ctypes.c_char_p, size, pointer, size, pointer]
    lib.alarm_delta_decode.restype = ctypes.c_int
    return lib


try:
    _LIB = open_library(Path(__file__).with_name('alarm_delta_avx2.dll' if os.name == 'nt' else 'alarm_delta_avx2.so'))
except (OSError, AttributeError, ImportError):
    _LIB = None


class Block:
    __slots__ = ('key', 'deltas', 'bgr')

    def __init__(self, data, bgr):
        self.key = data.copy()
        self.key.flags.writeable = False
        self.deltas = []
        self.bgr = bgr


class Frame:
    __slots__ = ('block', 'index')

    def __init__(self, block):
        self.block = block
        self.index = len(block.deltas)


class Packer:
    """A private rolling reference plus a key every 32 frames bounds random seeks."""

    def __init__(self):
        self.block = self.previous = self.output = self.source_shape = None
        self.bgr = True
        self.delta_bytes = 0

    def pack(self, bgr, to_i420):
        if bgr.dtype != np.uint8 or bgr.ndim != 3 or bgr.shape[2] != 3:
            raise ValueError('Expected uint8 BGR archive input')
        changed_size = self.source_shape != bgr.shape
        new_key = changed_size or len(self.block.deltas) == 31
        if new_key:
            if changed_size:
                self.bgr = True
            else:
                # Preserve native BGR cheaply in quiet scenes. When temporal
                # residuals are large, discard unneeded chroma detail at exactly
                # the same I420 conversion point as the original archive.
                ratio = self.delta_bytes / (len(self.block.deltas)*self.block.key.nbytes)
                if self.bgr and ratio > .20:
                    self.bgr = False
                elif not self.bgr and ratio < .12:
                    self.bgr = True
        data = np.ascontiguousarray(bgr) if self.bgr else to_i420(bgr)
        if new_key:
            self.block = Block(data, self.bgr)
            if self.previous is None or self.previous.shape != data.shape:
                self.previous = np.empty_like(data)
                self.output = ctypes.create_string_buffer(data.nbytes + (data.nbytes+127)//128)
            np.copyto(self.previous, data)
            self.source_shape = bgr.shape
            self.delta_bytes = 0
        else:
            # encode advances only this packer's private reference. The key and
            # all bytes referenced by readers of earlier frames stay immutable.
            n = _LIB.alarm_delta_encode(data.ctypes.data, self.previous.ctypes.data,
                                        data.nbytes, self.output, len(self.output))
            if not n:
                raise ValueError('Alarm delta encode failed')
            self.block.deltas.append(self.output[:n])
            self.delta_bytes += n
        return Frame(self.block)


class Reader:
    def __init__(self):
        self.block = self.current = None
        self.index = 0

    def unpack(self, frame, to_i420):
        block = frame.block
        if self.block is not block or self.index > frame.index:
            self.block, self.index = block, 0
            self.current = block.key.copy()
        while self.index < frame.index:
            payload = block.deltas[self.index]
            data = self.current
            if not _LIB.alarm_delta_decode(payload, len(payload), data.ctypes.data,
                                           data.nbytes, data.ctypes.data):
                self.block = self.current = None
                raise ValueError('Invalid alarm delta frame')
            self.index += 1
        return to_i420(self.current) if block.bgr else self.current


def create_packer():
    return Packer() if _LIB is not None else None
