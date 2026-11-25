# coding:utf-8
'''
RetinaFace 人脸检测器（算能 BM1684X / sophon-sail 版，自 templates/RetinaFace 样例移植）。

只保留人脸【检测】主流程与可选的人脸【识别】能力：
  - detect(image)             : 对整图做 RetinaFace 人脸检测，返回 [x1,y1,x2,y2,score,landmark10] 数组；
  - is_face_in_bbox(image, bbox): 判断给定目标框区域内是否存在人脸（过线触发用）；
  - recognize(image, box)     : 可选，对单张人脸做特征提取并与库比对，返回姓名（保留识别能力）。

运行时：sophon.sail Engine（SYSIO 模式），模型为 .bmodel（如 retinaface_mobilenet0.25_fp32_1b.bmodel）。
预处理与 sophon-demo RetinaFace 样例一致：BGR 顺序、减均值 (104,117,123)、NCHW float32；
输入尺寸以 bmodel 实际输入为准（无需手工配置 320/640）。
模型路径默认在本模块 model_data/ 下寻找（精确名未命中时按 *.bmodel 关键字兜底），
找不到再回退板端 /RetinaFace 目录。
'''

import os
import glob
import logging
import threading

import cv2
import numpy as np

from .face_utils import (
    letterbox_resize, PriorBox, box_decode, decode_landm,
    nms, non_max_suppression, Alignment_1, compare_faces, cv2ImgAddText,
)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_MODEL_DIR = os.path.join(_MODULE_DIR, 'model_data')
_BOARD_MODEL_DIR = '/RetinaFace/model_data'

# TPU 设备号：单卡盒子恒为 0，可用环境变量 TPU_DEV_ID 覆盖
_DEFAULT_DEV_ID = int(os.environ.get('TPU_DEV_ID', '0') or 0)


def _resolve_model(name, model_dir=None, keyword=None):
    '''按 [显式目录, 本地 model_data, 板端 /RetinaFace/model_data] 顺序寻找模型文件。
    精确名未命中且给了 keyword 时，在同一批目录里按 *.bmodel 文件名关键字（不区分大小写）兜底。'''
    dirs = [d for d in (model_dir, _LOCAL_MODEL_DIR, _BOARD_MODEL_DIR) if d]
    for base in dirs:
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    if keyword:
        kw = keyword.lower()
        for base in dirs:
            for p in sorted(glob.glob(os.path.join(base, '*.bmodel'))):
                if kw in os.path.basename(p).lower():
                    logging.info('[face] 未找到 %s，按关键字 %r 匹配到 bmodel: %s', name, keyword, p)
                    return p
    # 找不到也返回本地默认路径（便于日志定位）
    return os.path.join(_LOCAL_MODEL_DIR, name)


class _SailNet(object):
    '''sail.Engine 薄封装：单输入多输出，SYSIO 模式喂 numpy float32。'''

    def __init__(self, model_path, dev_id=None):
        import sophon.sail as sail
        if not os.path.exists(model_path):
            raise FileNotFoundError('bmodel 不存在: %s' % model_path)
        self.model_path = model_path
        self.dev_id = _DEFAULT_DEV_ID if dev_id is None else int(dev_id)
        self.engine = sail.Engine(model_path, self.dev_id, sail.IOMode.SYSIO)
        self.graph_name = self.engine.get_graph_names()[0]
        self.input_name = self.engine.get_input_names(self.graph_name)[0]
        self.input_shape = list(self.engine.get_input_shape(self.graph_name, self.input_name))
        self.output_names = self.engine.get_output_names(self.graph_name)
        # NCHW：input_shape = [n, c, h, w]
        self.input_h = int(self.input_shape[-2])
        self.input_w = int(self.input_shape[-1])
        self._lock = threading.Lock()
        logging.info('[face] bmodel 已加载: %s dev=%d 输入=%dx%d',
                     model_path, self.dev_id, self.input_w, self.input_h)

    def process(self, blob):
        '''blob: (1,C,H,W) float32，返回输出 ndarray 列表（顺序不保证，由调用方按形状识别）。'''
        with self._lock:
            out = self.engine.process(self.graph_name, {self.input_name: blob})
        return [np.asarray(out[name]) for name in self.output_names]

    def release(self):
        '''sail.Engine 无显式释放接口，解除引用交给 GC（保留方法兼容调用方）。'''
        self.engine = None


class FaceDetector(object):
    '''RetinaFace 人脸检测器（可选携带 mobilefacenet 识别模型）。'''

    def __init__(self, det_model='RetinaFace.bmodel', rec_model='mobilefacenet.bmodel',
                 model_dir=None, target=None, dev_id=None, model_size=None,
                 det_score_thresh=0.5, nms_iou=0.3, enable_recognition=False,
                 rec_threshold=0.9, font_name='simhei.ttf',
                 rec_rgb=False, rec_mean=127.5, rec_std=127.5):
        '''初始化检测器：加载 RetinaFace 检测 bmodel，按需加载识别模型与人脸特征库。
        target 为旧 RKNN 版遗留参数（忽略）；model_size 不再需要手工指定，以 bmodel 输入为准。
        rec_rgb/rec_mean/rec_std 为识别模型预处理参数（blob = (img - mean) / std，rec_rgb=True
        时先 BGR→RGB）：必须与 bmodel 转换时的归一化约定匹配，用 tools/verify_facenet.py 实测确定。'''
        self.model_dir = model_dir
        self.dev_id = dev_id
        self.bg_color = 0               # 与 sophon-demo RetinaFace 样例一致：黑边填充
        self.confidence = 0.05          # 后处理初筛置信度（低阈值多召回）
        self.det_score_thresh = det_score_thresh  # 判定"是人脸"的最终得分阈值
        self.nms_iou = nms_iou
        self.rec_threshold = rec_threshold
        self.rec_rgb = bool(rec_rgb)
        self.rec_mean = float(rec_mean)
        self.rec_std = float(rec_std)
        self.mean_bgr = np.array([104.0, 117.0, 123.0], dtype=np.float32)
        self.font_path = _resolve_model(font_name, model_dir)
        self._prior_cache = {}

        # 人脸检测模型（必需）；输入尺寸以 bmodel 为准
        det_path = _resolve_model(det_model, model_dir, keyword='retinaface')
        self._det = _SailNet(det_path, dev_id)
        self.model_width = self._det.input_w
        self.model_height = self._det.input_h
        if model_size and int(model_size) != self.model_width:
            logging.info('[face] model_size 配置=%s 与 bmodel 输入=%d 不一致，以 bmodel 为准',
                         model_size, self.model_width)

        # 人脸识别模型 + 特征库（可选）
        self._rec = None
        self.known_face_encodings = None
        self.known_face_names = None
        if enable_recognition:
            try:
                rec_path = _resolve_model(rec_model, model_dir, keyword='facenet')
                self._rec = _SailNet(rec_path, dev_id)
                self.known_face_encodings = np.load(_resolve_model('face_encoding.npy', model_dir))
                self.known_face_names = np.load(_resolve_model('names.npy', model_dir))
                logging.info('[face] 人脸识别已启用，特征库 %d 人', len(self.known_face_names))
            except Exception:
                logging.exception('[face] 人脸识别模型/特征库加载失败，仅保留检测能力')
                self._rec = None

    def _get_priors(self):
        '''按当前模型输入尺寸缓存并复用先验框。'''
        key = (self.model_height, self.model_width)
        priors = self._prior_cache.get(key)
        if priors is None:
            priors = PriorBox(image_size=key)
            self._prior_cache[key] = priors
        return priors

    @staticmethod
    def _split_outputs(outputs, num_priors):
        '''按末维形状把输出映射为 (loc[N,4], conf[N,2], landms[N,10])，不依赖输出顺序。'''
        loc = conf = landms = None
        for out in outputs:
            arr = out.reshape(num_priors, -1) if out.ndim != 2 else out
            if arr.ndim == 3:
                arr = arr.reshape(-1, arr.shape[-1])
            last = arr.shape[-1]
            if last == 4:
                loc = arr
            elif last == 2:
                conf = arr
            elif last == 10:
                landms = arr
        if loc is None or conf is None or landms is None:
            raise ValueError('RetinaFace 输出形状异常: %s' % [o.shape for o in outputs])
        return loc, conf, landms

    def detect(self, image):
        '''对整图做人脸检测，返回 [x1,y1,x2,y2,score,landmark10] 的 ndarray（无人脸返回空数组）。'''
        if image is None or image.size == 0:
            return np.empty((0, 15))
        img_height, img_width = image.shape[:2]
        letterbox_img, aspect_ratio, offset_x, offset_y = letterbox_resize(
            image, (self.model_width, self.model_height), self.bg_color)
        # 与 sophon-demo RetinaFace 样例一致：保持 BGR、减均值、HWC→NCHW float32
        blob = letterbox_img.astype(np.float32) - self.mean_bgr
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
        blob = np.ascontiguousarray(blob)

        outputs = self._det.process(blob)
        priors = self._get_priors()
        loc, conf, landmarks = self._split_outputs(
            [o.squeeze(0) if o.ndim == 3 else o for o in outputs], len(priors))

        boxes = box_decode(loc, priors)
        scale = np.array([self.model_width, self.model_height, self.model_width, self.model_height])
        boxes = boxes * scale // 1
        boxes[..., 0::2] = np.clip((boxes[..., 0::2] - offset_x) / aspect_ratio, 0, img_width)
        boxes[..., 1::2] = np.clip((boxes[..., 1::2] - offset_y) / aspect_ratio, 0, img_height)

        scores = conf[:, 1]
        landmarks = decode_landm(landmarks, priors)
        scale_landmarks = np.array([self.model_width, self.model_height] * 5)
        landmarks = landmarks * scale_landmarks // 1
        landmarks[..., 0::2] = np.clip((landmarks[..., 0::2] - offset_x) / aspect_ratio, 0, img_width)
        landmarks[..., 1::2] = np.clip((landmarks[..., 1::2] - offset_y) / aspect_ratio, 0, img_height)

        inds = np.where(scores > 0.02)[0]
        boxes, landmarks, scores = boxes[inds], landmarks[inds], scores[inds]
        if len(scores) == 0:
            return np.empty((0, 15))
        order = scores.argsort()[::-1]
        boxes, landmarks, scores = boxes[order], landmarks[order], scores[order]
        dets = np.hstack((boxes, scores[:, np.newaxis])).astype(np.float32, copy=False)
        keep = nms(dets, 0.5)
        dets, landmarks = dets[keep], landmarks[keep]
        boxes_conf_landms = np.concatenate((dets, landmarks), axis=1)
        boxes_conf_landms = non_max_suppression(boxes_conf_landms, self.confidence, self.nms_iou)
        if len(boxes_conf_landms) == 0:
            return np.empty((0, 15))
        return np.asarray(boxes_conf_landms)

    def is_face_in_bbox(self, image, bbox, expand=0.15):
        '''判断给定目标框 [x1,y1,x2,y2] 区域内是否为人脸。
        裁剪该区域（可外扩）后做人脸检测，取最高得分与阈值比较。
        返回 (是否人脸: bool, 最高得分: float, 人脸框(整图坐标) 或 None)。'''
        if image is None or image.size == 0 or bbox is None:
            return False, 0.0, None
        h, w = image.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
        # 外扩并裁剪到图像范围内
        bw, bh = x2 - x1, y2 - y1
        if bw <= 0 or bh <= 0:
            return False, 0.0, None
        ex, ey = int(bw * expand), int(bh * expand)
        cx1 = max(0, x1 - ex)
        cy1 = max(0, y1 - ey)
        cx2 = min(w, x2 + ex)
        cy2 = min(h, y2 + ey)
        crop = image[cy1:cy2, cx1:cx2]
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return False, 0.0, None

        dets = self.detect(crop)
        if len(dets) == 0:
            return False, 0.0, None
        best = max(dets, key=lambda d: float(d[4]))
        best_score = float(best[4])
        if best_score < self.det_score_thresh:
            return False, best_score, None
        # 人脸框映射回整图坐标
        fb = [int(best[0]) + cx1, int(best[1]) + cy1,
              int(best[2]) + cx1, int(best[3]) + cy1]
        return True, best_score, fb

    def recognize(self, image, box_conf_landm):
        '''可选：对单张人脸做特征提取并与库比对，返回识别姓名（无识别模型返回 "Unknown"）。
        预处理按 __init__ 的 rec_rgb/rec_mean/rec_std 执行（blob = (img - mean) / std，NCHW）；
        参数必须与 bmodel 转换时的归一化约定匹配，用 tools/verify_facenet.py 实测确定。'''
        if self._rec is None or self.known_face_encodings is None:
            return 'Unknown', 1.0
        try:
            b = np.maximum(box_conf_landm, 0)
            x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
            crop = image[y1:y2, x1:x2]
            landmark = np.reshape(b[5:], (5, 2)) - np.array([x1, y1])
            aligned, _ = Alignment_1(crop, landmark)
            face_img = cv2.resize(aligned, (self._rec.input_w, self._rec.input_h),
                                  interpolation=cv2.INTER_CUBIC)
            if self.rec_rgb:
                face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            blob = (face_img.astype(np.float32) - self.rec_mean) / self.rec_std
            blob = np.ascontiguousarray(blob.transpose(2, 0, 1)[np.newaxis, ...])
            out = self._rec.process(blob)[0]
            out = out.reshape(1, -1)
            norms = np.linalg.norm(out, ord=2, axis=1, keepdims=True)
            encoding = (out / norms)[0]
            matches, distances = compare_faces(self.known_face_encodings, encoding, tolerance=self.rec_threshold)
            best_idx = int(np.argmin(distances))
            if matches[best_idx]:
                return str(self.known_face_names[best_idx]), float(distances[best_idx])
            return 'Unknown', float(distances[best_idx])
        except Exception:
            logging.exception('[face] 人脸识别失败')
            return 'Unknown', 1.0

    def release(self):
        '''释放推理引擎引用。'''
        for r in (self._det, self._rec):
            try:
                if r is not None:
                    r.release()
            except Exception:
                pass
