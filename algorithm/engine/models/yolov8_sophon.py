# coding:utf-8
'''
yolov8_sophon.py —— 算能 BM1684X 上 YOLOv8/YOLOv11 bmodel 的统一推理封装（sophon-sail）。

供 templates/rtsp_infer_push.py（多模型并行引擎）与 templates/muban_s2m.py（单路多模）共用：
  - YOLOv8Model : 加载 bmodel（sail.Engine, SYSIO 模式），输入尺寸以 bmodel 实际输入为准；
  - preprocess  : BGR 任意尺寸 → letterbox(114 填充) → RGB/255 → NCHW float32；
  - postprocess : YOLOv8 OPT 单输出 (N, 4+nc) 解码 → 置信度过滤 → NMS → letterbox 逆映射回原图；
  - infer       : 整图一步推理便捷入口，返回 [[cls_id, '%.2f'%score, [x1,y1,x2,y2]], ...]。

说明：
  - 只支持 YOLOv8/YOLOv11 的单输出导出模型 [b, num_boxes, 4+nc]（anchor-free、无 objectness，
    两者输出格式相同，按 sophon-demo 的 OPT 方式导出）；未转置的 [b, 4+nc, num_boxes]
    会自动转置兼容；三尺度多输出的原始导出会报错提示重新导出。
  - SYSIO 模式下 sail 内部自动处理 int8 量化的输入/输出缩放，喂 float32 即可。
  - 同一 Engine 实例非线程安全：YOLOv8Model 内部持锁，跨线程调用安全（引擎里每个
    模型独占一个实例并单线程使用，锁基本无竞争）。
'''

import os
import logging
import threading

import cv2
import numpy as np
import sophon.sail as sail

# TPU 设备号：单卡盒子恒为 0，可用环境变量 TPU_DEV_ID 覆盖
DEFAULT_DEV_ID = int(os.environ.get('TPU_DEV_ID', '0') or 0)


class YOLOv8Model(object):
    '''YOLOv8 bmodel 推理实例（sail.Engine SYSIO）。'''

    def __init__(self, bmodel_path, dev_id=None):
        if not os.path.exists(bmodel_path):
            raise FileNotFoundError('bmodel 不存在: %s' % bmodel_path)
        self.bmodel_path = bmodel_path
        self.dev_id = DEFAULT_DEV_ID if dev_id is None else int(dev_id)
        self.engine = sail.Engine(bmodel_path, self.dev_id, sail.IOMode.SYSIO)
        self.graph_name = self.engine.get_graph_names()[0]
        self.input_name = self.engine.get_input_names(self.graph_name)[0]
        self.input_shape = list(self.engine.get_input_shape(self.graph_name, self.input_name))
        self.output_names = self.engine.get_output_names(self.graph_name)
        if len(self.input_shape) != 4:
            raise ValueError('bmodel 输入应为 NCHW 4 维，实际 %s: %s'
                             % (self.input_shape, bmodel_path))
        self.batch_size = int(self.input_shape[0])
        self.net_h = int(self.input_shape[2])
        self.net_w = int(self.input_shape[3])
        if len(self.output_names) != 1:
            raise ValueError(
                '检测 bmodel 应为 YOLOv8/YOLOv11 单输出导出模型（[b, boxes, 4+nc]），实际 %d 个输出。'
                '请参考 sophon-demo docs/YOLOv8_Export_Guide.md 重新导出: %s'
                % (len(self.output_names), bmodel_path))
        self.output_shape = list(self.engine.get_output_shape(self.graph_name, self.output_names[0]))
        # anchor-free 网格数校验：行数应等于 (w/8)(h/8)+(w/16)(h/16)+(w/32)(h/32)（如 640→8400），
        # 不匹配多半是放错了模型（如 YOLOv5 转的 bmodel），提前告警便于定位
        grid = ((self.net_w // 8) * (self.net_h // 8) + (self.net_w // 16) * (self.net_h // 16)
                + (self.net_w // 32) * (self.net_h // 32))
        rows = max(int(self.output_shape[-2]), int(self.output_shape[-1])) \
            if len(self.output_shape) >= 2 else 0
        if rows != grid:
            logging.warning('[yolov8_sophon] 输出行数 %d 与输入 %dx%d 的 YOLOv8/v11 网格数 %d 不匹配，'
                            '该 bmodel 可能不是 YOLOv8/YOLOv11 导出，检测结果可能异常: %s',
                            rows, self.net_w, self.net_h, grid, bmodel_path)
        self._lock = threading.Lock()
        logging.info('[yolov8_sophon] 加载成功 %s dev=%d 输入=%dx%d batch=%d 输出=%s',
                     os.path.basename(bmodel_path), self.dev_id, self.net_w, self.net_h,
                     self.batch_size, self.output_shape)

    @property
    def img_size(self):
        return self.net_w

    def infer_raw(self, blob):
        '''blob: (1,3,H,W) float32（preprocess 的输出）。
        返回解码前的预测张量 (num_boxes, 4+nc)（自动兼容未转置的 (4+nc, num_boxes)）。'''
        with self._lock:
            out = self.engine.process(self.graph_name, {self.input_name: blob})
        pred = np.asarray(out[self.output_names[0]])
        if pred.ndim == 3:
            pred = pred[0]
        # OPT 模型为 (num_boxes, 4+nc)；未转置导出 (4+nc, num_boxes) 时转置兼容
        if pred.shape[0] < pred.shape[1]:
            pred = np.ascontiguousarray(pred.T)
        return pred

    def release(self):
        '''sail.Engine 无显式释放接口，解除引用交给 GC 即可（保留方法兼容调用方）。'''
        self.engine = None


def preprocess(image_bgr, net_w, net_h=None):
    '''BGR(任意尺寸) → 等比缩放 + 居中 114 填充(letterbox) → RGB/255 → NCHW float32。
    返回 (blob, ratio=(rx,ry), txy=(tx,ty))，后两者供 postprocess 把框映射回原图。'''
    if net_h is None:
        net_h = net_w
    img_h, img_w = image_bgr.shape[:2]
    r = min(net_w / img_w, net_h / img_h)
    tw, th = int(round(r * img_w)), int(round(r * img_h))
    tx, ty = (net_w - tw) / 2.0, (net_h - th) / 2.0
    resized = cv2.resize(image_bgr, (tw, th), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((net_h, net_w, 3), 114, dtype=np.uint8)
    top, left = int(round(ty - 0.1)), int(round(tx - 0.1))
    canvas[top:top + th, left:left + tw] = resized
    cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB, dst=canvas)
    blob = canvas.astype(np.float32)
    blob *= 1.0 / 255.0
    blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
    return np.ascontiguousarray(blob), (r, r), (tx, ty)


def xywh2xyxy(x):
    '''[中心x,中心y,w,h] → [x1,y1,x2,y2]。'''
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def nms_boxes(boxes, scores, nms_thresh):
    '''非极大值抑制，boxes 为 xyxy，返回保留框索引。'''
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 0.00001)
        h = np.maximum(0.0, yy2 - yy1 + 0.00001)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= nms_thresh)[0]
        order = order[inds + 1]
    return np.array(keep)


# 按类别做偏移后一次 NMS（等价按类别分组 NMS），偏移量须大于任何可能的框坐标
_NMS_CLASS_OFFSET = 7680.0


def postprocess(pred, img_w, img_h, ratio, txy, conf_thresh, nms_thresh, max_det=300):
    '''YOLOv8/YOLOv11 单输出解码：置信度过滤 → xywh→xyxy → 类别偏移 NMS → letterbox 逆映射回原图并裁边。
    pred: (num_boxes, 4+nc)，前 4 列 xywh（输入尺寸坐标系），后 nc 列各类别得分（无 objectness）。
    返回 (new_boxes[[x1,y1,x2,y2]...], classes, scores)，无结果三者均为 None。'''
    if pred is None or pred.size == 0:
        return None, None, None
    cls_scores = pred[:, 4:]
    scores = cls_scores.max(axis=1)
    keep = scores >= conf_thresh
    if not keep.any():
        return None, None, None
    scores = scores[keep]
    classes = cls_scores[keep].argmax(axis=1)
    boxes = xywh2xyxy(pred[keep, :4])
    offset = classes.astype(np.float32) * _NMS_CLASS_OFFSET
    keep_idx = nms_boxes(boxes + offset[:, None], scores, nms_thresh)
    if keep_idx.size == 0:
        return None, None, None
    if keep_idx.size > max_det:
        keep_idx = keep_idx[:max_det]
    boxes = boxes[keep_idx]
    classes = classes[keep_idx]
    scores = scores[keep_idx]
    # letterbox 逆映射：去 padding → 除缩放比 → 裁到原图范围
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - txy[0]) / ratio[0]
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - txy[1]) / ratio[1]
    new_boxes = []
    for box in boxes:
        xmin = max(0, int(box[0]))
        ymin = max(0, int(box[1]))
        xmax = min(img_w, int(box[2]))
        ymax = min(img_h, int(box[3]))
        new_boxes.append([xmin, ymin, xmax, ymax])
    return new_boxes, classes, scores


def infer(image_bgr, model, obj_thresh, nms_thresh, category_id=None):
    '''整图一步推理：预处理 → TPU 推理 → 后处理 → 类别过滤。
    model 为 YOLOv8Model 实例；category_id 为保留的类别 id 列表（空/None=不过滤）。
    返回 [[cls_id:int, '%.2f'%score:str, [x1,y1,x2,y2]], ...]（与原 RKNN 版 infer 输出格式一致）。'''
    img_h, img_w = image_bgr.shape[:2]
    blob, ratio, txy = preprocess(image_bgr, model.net_w, model.net_h)
    pred = model.infer_raw(blob)
    boxes, classes, scores = postprocess(pred, img_w, img_h, ratio, txy, obj_thresh, nms_thresh)
    result_lst = []
    if boxes is None:
        return result_lst
    cat = set(int(c) for c in (category_id or []))
    for box, score, cl in zip(boxes, scores, classes):
        cl_int = int(cl)
        if cat and cl_int not in cat:
            continue
        result_lst.append([cl_int, '%.2f' % float(score), list(box)])
    return result_lst


# SITE_PATCH_CROSSING_POSE_V1
def postprocess_pose(pred, img_w, img_h, ratio, txy, conf_thresh, nms_thresh,
                     kpt_num=17, max_det=300):
    '''YOLOv8-pose 单输出解码：置信度过滤 → NMS → letterbox 逆映射（框与关键点一起回原图）。
    pred: (num_boxes, 4+nc+3*kpt)，前 4 列 xywh，接着 nc 列类别得分，再接着 kpt 个 [x,y,conf]。
    返回 (boxes[[x1,y1,x2,y2]...], classes, scores, keypoints[N,kpt_num,3])；无结果四者均 None。'''
    if pred is None or pred.size == 0:
        return None, None, None, None
    dim = int(pred.shape[1])
    kpt_dim = int(kpt_num) * 3
    nc = dim - 4 - kpt_dim
    if nc < 1:
        raise ValueError('姿态模型输出维度 %d 无法拆出 %d 个关键点（应为 4+nc+%d）'
                         % (dim, kpt_num, kpt_dim))
    cls_scores = pred[:, 4:4 + nc]
    scores = cls_scores.max(axis=1)
    keep = scores >= conf_thresh
    if not keep.any():
        return None, None, None, None
    scores = scores[keep]
    classes = cls_scores[keep].argmax(axis=1)
    boxes = xywh2xyxy(pred[keep, :4])
    keypoints = pred[keep, 4 + nc:].reshape(-1, int(kpt_num), 3).copy()
    offset = classes.astype(np.float32) * _NMS_CLASS_OFFSET
    keep_idx = nms_boxes(boxes + offset[:, None], scores, nms_thresh)
    if keep_idx.size == 0:
        return None, None, None, None
    if keep_idx.size > max_det:
        keep_idx = keep_idx[:max_det]
    boxes = boxes[keep_idx]
    classes = classes[keep_idx]
    scores = scores[keep_idx]
    keypoints = keypoints[keep_idx]
    # letterbox 逆映射：框与关键点用同一组 ratio/txy
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - txy[0]) / ratio[0]
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - txy[1]) / ratio[1]
    keypoints[:, :, 0] = (keypoints[:, :, 0] - txy[0]) / ratio[0]
    keypoints[:, :, 1] = (keypoints[:, :, 1] - txy[1]) / ratio[1]
    keypoints[:, :, 0] = np.clip(keypoints[:, :, 0], 0, img_w)
    keypoints[:, :, 1] = np.clip(keypoints[:, :, 1], 0, img_h)
    new_boxes = []
    for box in boxes:
        xmin = max(0, int(box[0]))
        ymin = max(0, int(box[1]))
        xmax = min(img_w, int(box[2]))
        ymax = min(img_h, int(box[3]))
        new_boxes.append([xmin, ymin, xmax, ymax])
    return new_boxes, classes, scores, keypoints
