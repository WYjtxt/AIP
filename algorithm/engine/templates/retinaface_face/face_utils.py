# coding:utf-8
'''
RetinaFace 人脸检测/识别后处理工具（自 RetinaFace/python/utils.py 精简移植）。
只保留人脸检测与识别所需的核心函数：
  - letterbox_resize：等比缩放 + 填充，得到定尺推理输入；
  - PriorBox / box_decode / decode_landm：RetinaFace 先验框与框/关键点解码；
  - nms / non_max_suppression：非极大值抑制；
  - Alignment_1：按 5 点关键点做人脸对齐（识别用）；
  - face_distance / compare_faces：人脸特征比对（识别用）；
  - cv2ImgAddText：在图像上绘制中文文字（识别可视化用）。
'''

import math
from math import ceil
from itertools import product as product

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = ImageDraw = ImageFont = None


def letterbox_resize(image, size, bg_color):
    '''等比缩放并居中填充到 size=(width, height)，返回 (图像, 缩放比, x偏移, y偏移)。'''
    if isinstance(image, str):
        image = cv2.imread(image)
    target_width, target_height = size
    image_height, image_width = image.shape[:2]
    aspect_ratio = min(target_width / image_width, target_height / image_height)
    new_width = int(image_width * aspect_ratio)
    new_height = int(image_height * aspect_ratio)
    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    result_image = np.ones((target_height, target_width, 3), dtype=np.uint8) * bg_color
    offset_x = (target_width - new_width) // 2
    offset_y = (target_height - new_height) // 2
    result_image[offset_y:offset_y + new_height, offset_x:offset_x + new_width] = image
    return result_image, aspect_ratio, offset_x, offset_y


def PriorBox(image_size):
    '''生成 RetinaFace 先验框（支持 320/640 等 32 倍数输入）。'''
    anchors = []
    min_sizes = [[16, 32], [64, 128], [256, 512]]
    steps = [8, 16, 32]
    feature_maps = [[ceil(image_size[0] / step), ceil(image_size[1] / step)] for step in steps]
    for k, f in enumerate(feature_maps):
        min_sizes_ = min_sizes[k]
        for i, j in product(range(f[0]), range(f[1])):
            for min_size in min_sizes_:
                s_kx = min_size / image_size[1]
                s_ky = min_size / image_size[0]
                dense_cx = [x * steps[k] / image_size[1] for x in [j + 0.5]]
                dense_cy = [y * steps[k] / image_size[0] for y in [i + 0.5]]
                for cy, cx in product(dense_cy, dense_cx):
                    anchors += [cx, cy, s_kx, s_ky]
    return np.array(anchors).reshape(-1, 4)


def box_decode(loc, priors):
    '''用先验框把网络回归输出解码为 [x1,y1,x2,y2] 框。'''
    variances = [0.1, 0.2]
    boxes = np.concatenate((
        priors[:, :2] + loc[:, :2] * variances[0] * priors[:, 2:],
        priors[:, 2:] * np.exp(loc[:, 2:] * variances[1])), axis=1)
    boxes[:, :2] -= boxes[:, 2:] / 2
    boxes[:, 2:] += boxes[:, :2]
    return boxes


def decode_landm(pre, priors):
    '''用先验框解码 5 点人脸关键点。'''
    variances = [0.1, 0.2]
    landmarks = np.concatenate((
        priors[:, :2] + pre[:, :2] * variances[0] * priors[:, 2:],
        priors[:, :2] + pre[:, 2:4] * variances[0] * priors[:, 2:],
        priors[:, :2] + pre[:, 4:6] * variances[0] * priors[:, 2:],
        priors[:, :2] + pre[:, 6:8] * variances[0] * priors[:, 2:],
        priors[:, :2] + pre[:, 8:10] * variances[0] * priors[:, 2:]
    ), axis=1)
    return landmarks


def nms(dets, thresh):
    '''标准 NMS，dets=[x1,y1,x2,y2,score]，返回保留下标列表。'''
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]
    return keep


def non_max_suppression(detection, conf_thres, nms_thres=0.3):
    '''置信度过滤 + IOU NMS，detection=[x1,y1,x2,y2,score,landmark...]，返回过滤后的数组。'''
    mask = detection[:, 4] >= conf_thres
    detection = detection[mask]
    if len(detection) <= 0:
        return []
    scores = detection[:, 4]
    arg_sort = np.argsort(scores)[::-1]
    detection = detection[arg_sort]
    best_boxes = []
    while len(detection) > 0:
        best_boxes.append(detection[0])
        if len(detection) == 1:
            break
        remaining = []
        for i in range(1, len(detection)):
            box1 = detection[0][:4]
            box2 = detection[i][:4]
            x1 = max(box1[0], box2[0])
            y1 = max(box1[1], box2[1])
            x2 = min(box1[2], box2[2])
            y2 = min(box1[3], box2[3])
            inter_area = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
            area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
            union_area = area1 + area2 - inter_area
            iou = inter_area / union_area if union_area > 0 else 0
            if iou < nms_thres:
                remaining.append(detection[i])
        detection = np.array(remaining) if remaining else np.empty((0, detection.shape[1]))
    return np.array(best_boxes) if best_boxes else np.empty((0, detection.shape[1]))


def Alignment_1(img, landmark):
    '''按 5 点关键点（左右眼）计算倾角并旋转对齐人脸，返回 (对齐图, 新关键点)。'''
    if landmark.shape[0] == 68:
        x = landmark[36, 0] - landmark[45, 0]
        y = landmark[36, 1] - landmark[45, 1]
    else:
        x = landmark[0, 0] - landmark[1, 0]
        y = landmark[0, 1] - landmark[1, 1]
    angle = 0 if x == 0 else math.atan(y / x) * 180 / math.pi
    center = (img.shape[1] // 2, img.shape[0] // 2)
    RotationMatrix = cv2.getRotationMatrix2D(center, angle, 1)
    new_img = cv2.warpAffine(img, RotationMatrix, (img.shape[1], img.shape[0]))
    RotationMatrix = np.array(RotationMatrix)
    new_landmark = []
    for i in range(landmark.shape[0]):
        pts = [
            RotationMatrix[0, 0] * landmark[i, 0] + RotationMatrix[0, 1] * landmark[i, 1] + RotationMatrix[0, 2],
            RotationMatrix[1, 0] * landmark[i, 0] + RotationMatrix[1, 1] * landmark[i, 1] + RotationMatrix[1, 2],
        ]
        new_landmark.append(pts)
    return new_img, np.array(new_landmark)


def face_distance(face_encodings, face_to_compare):
    '''计算待比对特征与已知特征库的欧氏距离数组。'''
    if len(face_encodings) == 0:
        return np.empty((0))
    return np.linalg.norm(face_encodings - face_to_compare, axis=1)


def compare_faces(known_face_encodings, face_encoding_to_check, tolerance=1):
    '''与人脸特征库比对，返回 (是否匹配列表, 距离数组)。'''
    dis = face_distance(known_face_encodings, face_encoding_to_check)
    return list(dis <= tolerance), dis


def cv2ImgAddText(img, label, left, top, textColor=(0, 0, 255), font_path=None, font_size=30):
    '''在 BGR 图像上绘制中文文字（依赖 PIL）；无字体/无 PIL 时回退 cv2.putText。'''
    if Image is None:
        cv2.putText(img, str(label), (int(left), int(top)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, textColor[::-1], 2)
        return img
    if not img.flags.writeable:
        img = img.copy()
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(img_pil)
    if isinstance(label, bytes):
        label = label.decode('utf-8')
    draw.text((left, top - font_size), label, fill=textColor, font=font)
    result = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    return result if result.flags.writeable else result.copy()
