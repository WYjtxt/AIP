# -*- coding: utf-8 -*-
"""
手动选点图像拼接（无需内参标定）：
    1. 直接加载两张待拼接图像
    2. 手动在两张图上各选择4个同名点
    3. 由4对同名点求单应矩阵H，将图像1透视变换到图像2视角并融合
"""
# import os
import cv2
import numpy as np
# from matplotlib import pyplot as plt
#
# plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
# plt.rcParams["axes.unicode_minus"] = False

def compute_homography_with_error(pts_src: np.ndarray, pts_dst: np.ndarray):
    """
    方法一：输入源点、目标同名点，按7:3划分，前部分求解H，后部分作为测试集计算重投影误差
    :param pts_src: 源图像点 N×2, float32
    :param pts_dst: 目标图像点 N×2, float32
    :return:
        H: 单应矩阵 3×3
        avg_train_err: 训练集平均重投影误差(像素)
        train_errors: 训练集每个点重投影误差
        avg_test_err: 测试集(未参与求解H)平均重投影误差(像素)
        test_errors: 测试集每个点重投影误差
    """
    num_pts = pts_src.shape[0]
    if num_pts < 4:
        raise RuntimeError("至少需要4对同名点求解单应矩阵")

    # 7:3划分，前70%训练，后30%测试
    split_idx = int(num_pts * 0.7)
    # 保证训练集至少4个点
    if split_idx < 4:
        split_idx = 4

    pts_train_src = pts_src[:split_idx, :]
    pts_train_dst = pts_dst[:split_idx, :]
    pts_test_src = pts_src[split_idx:, :]
    pts_test_dst = pts_dst[split_idx:, :]

    # 使用训练集求解单应矩阵，RANSAC
    H, mask = cv2.findHomography(pts_train_src, pts_train_dst, cv2.RANSAC, 5.0)
    if H is None:
        raise RuntimeError("求解单应矩阵失败，请检查同名点")

    # ---------------------- 测试集重投影误差（不参与H求解） ----------------------
    num_test = pts_test_src.shape[0]
    src_homo_test = np.hstack([pts_test_src, np.ones((num_test, 1), dtype=np.float32)]).T
    dst_proj_homo_test = H @ src_homo_test
    dst_proj_test = (dst_proj_homo_test[:2, :] / dst_proj_homo_test[2:, :]).T

    diff_test = dst_proj_test - pts_test_dst
    test_errors = np.sqrt(np.sum(diff_test ** 2, axis=1))
    avg_test_err = round(float(np.mean(test_errors)), 3)
    print(f"投影矩阵计算完成！【测试集真实平均重投影误差】{avg_test_err:.3f} 像素")  # avg_test_err >10  重新标定  两个摄像头点数相同 大于等于6个

    return H,  avg_test_err, test_errors


def project_points(H: np.ndarray, src_points: np.ndarray):
    """
    方法二：给定单应矩阵H，对输入源坐标点做透视投影，返回转换后图像坐标
    :param H: 3×3 单应矩阵
    :param src_points: N×2 源点坐标 float32
    :return: dst_points: N×2 投影之后的目标图像坐标
    """
    n = src_points.shape[0]
    # 转为齐次
    src_homo = np.hstack([src_points, np.ones((n, 1), dtype=np.float32)]).T  # 3 × N
    dst_homo = H @ src_homo
    # 齐次归一化
    dst_pts = dst_homo[:2, :] / dst_homo[2:, :]
    dst_points_array = dst_pts.T
    # 保留1位小数
    pts_rounded = np.round(dst_points_array, 1)
    return pts_rounded.tolist()


# 模拟输入4对同名点
pts_src = np.float32([[70.7, 225.10], [457.8, 125.0], [383.5, 486.3], [489.8, 396.5],[424.8, 302.5],[488.8, 256.1]])
pts_dst = np.float32([[689.0, 256.3], [1198.3, 440.7], [533.5, 612.7], [712.4, 685.7],[807.4, 545.3],[950.6, 601.7]])

# 方法一：求H和误差
H, avg_test_err, test_errors = compute_homography_with_error(pts_src, pts_dst)
print("H:\n", H)
print("平均重投影误差：", avg_test_err)

# 方法二：投影一批坐标
test_points = np.float32([[424.8, 302.5],[488.8, 256.1]])
out_pts = project_points(H, test_points)
print("投影输出坐标：\n", out_pts)