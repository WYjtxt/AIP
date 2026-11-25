# coding:utf-8
'''
retinaface_face —— 精简版 RetinaFace 人脸检测/识别模块，供人数统计过线时调用。

对外接口：
  - init_face_detector(**kwargs): 启动时初始化人脸检测模型（全局单例，仅加载一次）；
  - face(image, bbox):           过线触发入口——判断目标框区域内是否为人脸，
                                  是人脸则把人脸框外扩后裁剪成纯人脸图保存到 save_dir，返回保存路径(str)；
  - get_face_detector():         获取已初始化的 FaceDetector 单例（未初始化返回 None）；
  - FaceDetector:                人脸检测器类（检测 + 可选识别）。

设计要点：
  - face() 若在 init 之前被调用，会用默认参数惰性初始化，保证不漏调用；
  - 人脸检测/保存失败均只写日志，绝不向调用方抛异常，避免影响人数统计热路径。
'''

import os
import time
import logging
import threading

import cv2

from .face_detector import FaceDetector

__all__ = ['FaceDetector', 'init_face_detector', 'face', 'get_face_detector']

_DETECTOR = None
_INIT_LOCK = threading.Lock()
_INIT_FAILED = False
_WARNED_NO_DETECTOR = False   # 检测器不可用时仅告警一次，避免每次过线刷屏

# 判定为人脸后裁剪图的默认保存目录（板端优先 results/，失败回退模块同级目录）
_DEFAULT_SAVE_DIRS = ['/data/AIGO/outputs/face_captures',
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), 'face_captures')]
_SAVE_DIR = None
_FACE_EXPAND = 0.5   # 人脸框外扩比例：按人脸框宽/高各边外扩该比例后裁剪，保存纯人脸图（无框无文字）


def _pick_save_dir(save_dir=None):
    '''选择可写的保存目录：优先显式传入，其次板端目录，最后模块同级目录。'''
    candidates = ([save_dir] if save_dir else []) + _DEFAULT_SAVE_DIRS
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except OSError:
            continue
    return os.getcwd()


def init_face_detector(save_dir=None, face_expand=0.5, **kwargs):
    '''启动时初始化人脸检测模型（全局单例）。face_expand 为人脸框各边外扩比例。
    kwargs 透传给 FaceDetector（如 det_score_thresh、enable_recognition、model_dir、target 等）。
    返回单例；失败返回 None 且不再重复尝试。'''
    global _DETECTOR, _SAVE_DIR, _FACE_EXPAND, _INIT_FAILED
    with _INIT_LOCK:
        if _DETECTOR is not None:
            return _DETECTOR
        if _INIT_FAILED:
            return None
        _SAVE_DIR = _pick_save_dir(save_dir)
        _FACE_EXPAND = max(0.0, float(face_expand))
        try:
            _DETECTOR = FaceDetector(**kwargs)
            logging.info('[face] 人脸检测模型初始化完成，保存目录=%s', _SAVE_DIR)
        except Exception:
            _INIT_FAILED = True
            _DETECTOR = None
            logging.exception('[face] 人脸检测模型初始化失败，过线时将跳过人脸检测')
        return _DETECTOR


def get_face_detector():
    '''获取已初始化的 FaceDetector 单例；未初始化返回 None。'''
    return _DETECTOR


def _save_face_crop(image, face_box, score):
    '''把人脸框按 _FACE_EXPAND 外扩后裁剪出【纯人脸图】（无框、无文字）保存到 _SAVE_DIR，
    返回保存路径或 None。'''
    try:
        if face_box is None or image is None or image.size == 0:
            return None
        h, w = image.shape[:2]
        fx1, fy1, fx2, fy2 = [int(v) for v in face_box[:4]]
        fw, fh = fx2 - fx1, fy2 - fy1
        if fw <= 0 or fh <= 0:
            return None
        ex, ey = int(fw * _FACE_EXPAND), int(fh * _FACE_EXPAND)
        cx1 = max(0, fx1 - ex)
        cy1 = max(0, fy1 - ey)
        cx2 = min(w, fx2 + ex)
        cy2 = min(h, fy2 + ey)
        crop = image[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None
        save_dir = _SAVE_DIR or _pick_save_dir()
        ts = time.strftime('%Y-%m-%d_%H-%M-%S')
        path = os.path.join(save_dir, 'face_%s_%.2f.jpg' % (ts, score))
        # cv2.imwrite 失败不抛异常、只返回 False（路径/权限/磁盘满等），必须检查返回值
        if not cv2.imwrite(path, crop):
            logging.error('[face] 人脸裁剪图写入失败(imwrite=False): %s', path)
            return None
        return path
    except Exception:
        logging.exception('[face] 保存人脸裁剪图失败')
        return None


def face(image, bbox):
    '''过线触发入口：判断目标框 bbox=[x1,y1,x2,y2] 区域内是否为人脸。
    是人脸则把人脸框外扩后裁剪成纯人脸图保存，返回【保存路径】(str)；
    非人脸/检测器不可用/保存失败均返回 None。全程不抛异常。'''
    global _WARNED_NO_DETECTOR
    try:
        detector = _DETECTOR or init_face_detector()
        if detector is None:
            if not _WARNED_NO_DETECTOR:
                _WARNED_NO_DETECTOR = True
                logging.warning('[face] 人脸检测器不可用（模型未初始化/初始化失败），本次及后续过线均跳过人脸检测')
            return None
        is_face, score, face_box = detector.is_face_in_bbox(image, bbox)
        if not is_face:
            # 未命中也打印最高得分与阈值，便于判断是“未检到人脸(得分~0)”还是“得分不足”
            logging.info('[face] 目标框未判定为人脸（最高得分=%.3f，阈值=%.2f），bbox=%s',
                         score, detector.det_score_thresh, bbox)
            return None
        path = _save_face_crop(image, face_box, score)
        logging.info('[face] 目标框判定为人脸(得分=%.2f)，已保存人脸裁剪图(外扩%.0f%%): %s',
                     score, _FACE_EXPAND * 100, path)
        return path
    except Exception:
        logging.exception('[face] face() 执行异常（不影响人数统计）')
        return None
