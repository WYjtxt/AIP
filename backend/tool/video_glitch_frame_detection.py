# 花帧检测
import cv2
import time
import math
import numpy as np

# 视频帧分析
def analyze_frame(frame):
    # 转换为灰度图
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 区域权重
    h, w = frame.shape[:2]

    # 定义中心区域（占画面60%）
    roi = frame[int(h * 0.2):int(h * 0.8), int(w * 0.2):int(w * 0.8)]

    # 计算ROI指标时权重更高
    roi_weight = 0.7
    full_weight = 0.3

    # 全图、ROI 边缘检测计算
    edge_full = cv2.Canny(gray, 50, 150)    # 全图边缘检测
    edge_roi = cv2.Canny(roi, 50, 150)   # ROI边缘检测
    # 边缘检测
    edge_density = roi_weight * np.mean(edge_roi > 0) + full_weight * np.mean(edge_full > 0)    # 计算边缘密度

    # 颜色异常检测（检测绿色/紫色块）
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)       # 转换为HSV空间
    green_mask = cv2.inRange(hsv, (35, 20, 20), (85, 255, 255)) # 绿色范围
    purple_mask = cv2.inRange(hsv, (130, 20, 20), (170, 255, 255))  # 紫色范围
    abnormal_color_ratio = (np.sum(green_mask > 0) + np.sum(purple_mask > 0)) / (frame.size / 3)    # 计算异常颜色占比

    # 模糊检测
    blur_variance = cv2.Laplacian(gray, cv2.CV_64F).var()   # 计算模糊程度

    return edge_density, abnormal_color_ratio, blur_variance

# 视频流异常检测
def run(cap, fps, prewarn_threshold=30, warn_threshold=70, dtime=1.0):
    # 初始化参数
    glitch_frames = []
    frame_count = 0
    prev_metrics = None
    # 获取检测开始时间
    start_time = time.time()
    # 定义归一化因子为numpy数组
    NORM_FACTORS = np.array([1.0, 1.0, 100.0], dtype=np.float32)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 超时检测
        if (time.time() - start_time) > dtime:
            # print(f"达到检测时间限制 {dtime}秒")
            break

        # 分析当前帧
        try:
            edge_density, color_ratio, blur_var = analyze_frame(frame)
        except cv2.error as e:
            # print(f"帧分析失败: {str(e)}")
            continue

        # 是否花帧
        is_glitch = False

        # 边缘密度异常检测（正常视频通常在0.05-0.3之间）
        if not (0.02 < edge_density < 0.35):
            is_glitch = True

        # 异常颜色占比过高检测
        if color_ratio > 0.15:  # 超过15%的区域为异常颜色
            is_glitch = True

        # 模糊程度异常检测（正常帧通常在50以上）
        if blur_var < 30:
            is_glitch = True

        # 帧差异过大检测
        if prev_metrics is not None:
            current_metrics = np.array([edge_density, color_ratio, blur_var], dtype=np.float32)
            normalized_current = current_metrics / NORM_FACTORS
            normalized_prev = prev_metrics / NORM_FACTORS
            diff = np.mean(np.abs(normalized_current - normalized_prev))
            if diff > 0.3:
                is_glitch = True
        # 记录异常帧
        if is_glitch:
            glitch_frames.append(frame_count)
        # 记录当前帧的指标为下一帧的参考
        prev_metrics = np.array([edge_density, color_ratio, blur_var], dtype=np.float32)
        frame_count += 1

    # 释放视频资源
    cap.release()


    # 统计诊断结果
    # print(f"总帧数:{frame_count}, 异常帧数:{len(glitch_frames)}，异常帧索引:{glitch_frames}")
    prewarn_thres = math.ceil(fps * prewarn_threshold / 100)
    warn_thres = math.floor(fps * warn_threshold / 100)
    if len(glitch_frames) > warn_thres:
        return "报警"
    elif warn_thres > len(glitch_frames) > prewarn_thres:
        return "预警"
    else:
        return "正常"

if __name__ == "__main__":
    cap = cv2.VideoCapture("rtsp://12138@192.168.7.36")
    res = run(cap)
    print(res)
