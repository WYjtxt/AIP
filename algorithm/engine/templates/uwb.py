import argparse
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  # 把项目根目录加入路径

import pymysql
from datetime import datetime
import math
import numpy as np

from config import common as cm

# ===================== 全局配置常量 =====================
# 兼容旧调用方的占位路径：MySQL 化后连接信息统一取自 config/ApiConfig.ini，db_path 参数不再使用
DEFAULT_UWB_DB_PATH = None


def _connect_uwb_db():
    """按 config/ApiConfig.ini 中的配置连接 MySQL 8.0（uwb_data 表所在库）"""
    return pymysql.connect(
        host=cm.db_host,
        port=int(cm.db_port),
        user=cm.db_user,
        password=cm.db_password,
        database=cm.db_name,
        charset='utf8mb4',
        read_timeout=10,
        write_timeout=10,
    )

# ---------- 场景参数 ----------
CAMERA_RANGE = 10.0  # 摄像头有效监测范围(m)
UWB_RANGE = 20.0  # UWB探测范围(m)
UWB_REPORT_INTERVAL = 2.0  # 定位卡数据上报间隔(秒)

# ---------- 方向判定参数 ----------
DIRECTION_DIST_THRESHOLD = 0.1  # 进入/离开判定的开始结束距离差值阈值(m)
V_SHAPE_DEPTH_MIN = 3.0  # V形谷底相对两端最小凹陷深度(m)，低于此值不认定V形

# ---------- 轨迹过滤参数 ----------
STATIC_RANGE_THRESHOLD = 3.0  # 静态卡片活动范围极差阈值，极差≤该值判定静态
EXPAND_STEP = 2  # 单次窗口扩容时长(前后各加秒)
MIN_DIRECTION_RECORD = 3    # 方向判定最少数据条数，满足则直接判断不再扩容
MIN_SIMILARITY_RECORD = 10  # 相似度比对最少数据条数，不足则持续扩容至达到或边界
MAX_TOTAL_EXPAND = 20.0  # 最大累计扩容总时长，防止无限循环扩容
MAX_EXPAND_OFFSET = 15.0  # 扩容窗口距离原始窗口单边最大偏移(秒)
DIST_LOWER = 0.5  # time_a初始窗口距离过滤下限(m)
MAX_NORMAL_SPEED = 5  # 行人正常径向最大速度m/s，超过判定测距突变脏数据

# ---------- 相似度参数 ----------
SIMILARITY_THRESHOLD = 0.70   # 轨迹高度相似判定阈值(综合相似度>=该值视为重复/同组卡片)
TRACK_SAMPLE_INTERVAL = 0.2   # 时序轨迹统一插值采样间隔(秒)
MAX_ALLOW_AVG_OFFSET = 1.5    # 同时刻两卡平均测距偏移硬门槛(m)
MAX_ALLOW_MAX_OFFSET = 2.0    # 任意时刻最大测距偏移上限(m)：防均值掩盖局部偏离，超过则不判相似
POINT_OUTLIER_THRESHOLD = 1.5 # 逐点偏移超过此值视为"偏离点"(m)
MAX_OUTLIER_RATIO = 0.20      # 偏离点占总采样点比例上限，超过则认为两卡轨迹不一致
SPACE_OFFSET_THRESHOLD = 3.0  # 空间贴近度满分参考距离：均值偏移达到此值时得分归零(m)

# ---------- 轨迹搜索与通行区判定参数 ----------
TIME_A_EXPAND_SEC = 20.0    # 搜索窗口单边扩充时长(s)：原始窗口两端各扩充此量寻找UWB卡
FULL_TRACK_DURATION = 30.0  # 单卡完整轨迹拉取时长(s)：以原始窗口中点为中心向前后各15s
PASS_ZONE_MIN = 3.0         # 通行有效区间下限(m)：原始窗口内轨迹需经过此距离范围才算有效过卡
PASS_ZONE_MAX = 8.0         # 通行有效区间上限(m)：超出此距离视为未进入有效摄像头覆盖区


def parse_uwb_time(value):
    """时间字符串/时间戳统一转为秒级浮点时间戳"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    time_formats = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M:%S'
    ]
    for fmt in time_formats:
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"无法解析时间参数: {value}")


def format_uwb_time(timestamp_value):
    """秒级时间戳转 毫秒级可读时间字符串"""
    if timestamp_value is None:
        return ""
    dt = datetime.fromtimestamp(float(timestamp_value))
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def expand_window(base_start: float, base_end: float, orig_s: float, orig_e: float, expand_sec: float):
    """在原始窗口基础上扩展指定秒数，且不超过最大偏移限制"""
    new_s = base_start - expand_sec
    new_e = base_end + expand_sec
    limit_min = orig_s - MAX_EXPAND_OFFSET
    limit_max = orig_e + MAX_EXPAND_OFFSET
    new_s = max(new_s, limit_min)
    new_e = min(new_e, limit_max)
    return new_s, new_e


def filter_outlier_distance_track(track_list: list):
    """剔除UWB轨迹中测距突变异常点"""
    if len(track_list) <= 2:
        return track_list
    clean_track = [track_list[0]]
    for i in range(1, len(track_list)):
        prev = clean_track[-1]
        curr = track_list[i]
        dt = curr["ts"] - prev["ts"]
        if dt <= 1e-3:
            clean_track.append(curr)
            continue
        dd_abs = abs(curr["dist"] - prev["dist"])
        max_allow_dd = dt * MAX_NORMAL_SPEED
        if dd_abs > max_allow_dd:
            print(
                f"[轨迹滤波] 剔除异常点 ts={format_uwb_time(curr['ts'])}, dist={curr['dist']}, 允许最大差值={round(max_allow_dd, 3)}, 实际差值={round(dd_abs, 3)}")
            continue
        clean_track.append(curr)
    return clean_track


def calc_average_speed_full_track(track_points: list):
    """计算UWB轨迹的平均速度"""
    segment_speeds = []
    for i in range(1, len(track_points)):
        prev = track_points[i - 1]
        curr = track_points[i]
        delta_t = curr["ts"] - prev["ts"]
        if delta_t <= 1e-3:
            continue
        delta_d = abs(curr["dist"] - prev["dist"])
        seg_speed = delta_d / delta_t
        segment_speeds.append(seg_speed)
    if not segment_speeds:
        return {"valid": False, "speed_m_s": 0.0, "segment_count": 0, "speed_seq": []}
    avg_speed = sum(segment_speeds) / len(segment_speeds)
    return {
        "valid": True,
        "speed_m_s": round(avg_speed, 4),
        "segment_count": len(segment_speeds),
        "speed_seq": segment_speeds
    }


def judge_move_type(distance_list: list):
    """
    根据UWB距离轨迹判断人员运动方向。

    场景：UWB+摄像头安装在巷道中央，摄像头对着巷道一侧(10m范围)，
    UWB探测30m范围，定位卡每2秒上报一次。
    工人从一侧走向设备再走向另一侧，UWB轨迹呈V形（距离先减后增）。

    判定规则：
    1. V形轨迹：
       - 开始距离和结束距离均>10m(摄像头范围外) → 万能卡(方向不确定)
       - 开始距离 < 结束距离，差值>3m → 离开
       - 开始距离 > 结束距离，差值>3m → 进入
       - 差值≤3m → 万能卡(方向不确定)
    2. 非V形(单调趋势)：
       - 距离整体递减(人靠近) → 进入
       - 距离整体递增(人远离) → 离开
    """
    data_len = len(distance_list)
    if data_len < MIN_DIRECTION_RECORD:
        return "无法判定"

    # -------- 平滑：3点滑动均值，抑制UWB测距抖动 --------
    smooth_list = []
    for idx in range(data_len):
        left = max(0, idx - 1)
        right = min(data_len, idx + 2)
        smooth_list.append(sum(distance_list[left:right]) / (right - left))

    # -------- 提取开始/结束距离（取前后各20%点均值减少端点抖动） --------
    n_avg = max(1, data_len // 5)
    start_dist = sum(smooth_list[:n_avg]) / n_avg
    end_dist = sum(smooth_list[-n_avg:]) / n_avg

    # -------- V形检测：最小距离点在中间区域 且 两侧凹陷深度足够 --------
    min_dist = min(smooth_list)
    min_idx = smooth_list.index(min_dist)
    margin = max(1, data_len // 5)
    is_v_shape = False

    if margin <= min_idx <= data_len - 1 - margin:
        # 检查前半段下降、后半段上升的趋势是否成立
        front_half = smooth_list[:min_idx + 1]
        back_half = smooth_list[min_idx:]
        depth_from_start = start_dist - min_dist
        depth_from_end = end_dist - min_dist
        if depth_from_start >= V_SHAPE_DEPTH_MIN and depth_from_end >= V_SHAPE_DEPTH_MIN:
            # 验证前半段整体下降，后半段整体上升
            if len(front_half) >= 2 and len(back_half) >= 2:
                front_trend = front_half[0] - front_half[-1]  # 正=递减
                back_trend = back_half[-1] - back_half[0]  # 正=递增
                if front_trend >= 0 and back_trend >= 0:
                    is_v_shape = True

    delta = start_dist - end_dist  # 正=开始远结束近(进入)，负=开始近结束远(离开)
    abs_delta = abs(delta)

    print(f"[方向判定] 数据点数:{data_len}, 开始距离:{round(start_dist, 2)}m, "
          f"结束距离:{round(end_dist, 2)}m, 最小距离:{round(min_dist, 2)}m, "
          f"首尾差值:{round(abs_delta, 2)}m, V形:{is_v_shape}")

    if is_v_shape:
        # ---- V形轨迹方向判定 ----
        # 规则1：开始和结束距离均大于摄像头范围，无法可靠确定方向
        if start_dist > CAMERA_RANGE and end_dist > CAMERA_RANGE:
            print(f"[V形万能卡] 开始{round(start_dist, 2)}m和结束{round(end_dist, 2)}m均>摄像头范围{CAMERA_RANGE}m")
            return "万能计数卡"
        # 规则2：差值大于阈值则可判方向
        if abs_delta > DIRECTION_DIST_THRESHOLD:
            if start_dist < end_dist:
                # 开始近结束远 → 离开
                print(f"[V形离开] 开始{round(start_dist, 2)}m < 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "离开"
            else:
                # 开始远结束近 → 进入
                print(f"[V形进入] 开始{round(start_dist, 2)}m > 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "进入"
        # 规则3：V形但差值不够大，作为万能卡处理
        print(f"[V形万能卡] 差值{round(abs_delta, 2)}m ≤ 阈值{DIRECTION_DIST_THRESHOLD}m，方向不确定")
        return "万能计数卡"
    else:
        # ---- 非V形(单调趋势)方向判定 ----
        if abs_delta > DIRECTION_DIST_THRESHOLD:
            if delta > 0:
                # 开始远结束近 → 进入
                print(f"[单调进入] 开始{round(start_dist, 2)}m > 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "进入"
            else:
                # 开始近结束远 → 离开
                print(f"[单调离开] 开始{round(start_dist, 2)}m < 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "离开"
        print(f"[万能计数卡] 首尾差值{round(abs_delta, 2)}m ≤ 阈值{DIRECTION_DIST_THRESHOLD}m，无明显方向")
        return "万能计数卡"


def query_previous_distance(conn, card_id: str, before_ts: float):
    """查询指定卡在before_ts之前最近一条距离数据，用于数据量=1时的方向比较"""
    sql = """
        SELECT distance FROM uwb_data
        WHERE card_id = %s AND timestamp < %s
        ORDER BY timestamp DESC
        LIMIT 1
    """
    cursor = conn.cursor()
    cursor.execute(sql, [str(card_id), before_ts])
    row = cursor.fetchone()
    if row:
        return float(row[0])
    return None


def judge_move_type_lite(distance_list: list):
    """
    数据量在(2, 8)区间的方向判定：
    使用judge_move_type的核心逻辑（V形检测+单调趋势），
    但去除3点滑动均值和前后各20%点均值提取，直接使用原始距离值。
    """
    data_len = len(distance_list)
    if data_len <= 2:
        return "无法判定"

    # 直接使用原始数据的首尾作为开始/结束距离（不做平滑和均值处理）
    start_dist = distance_list[0]
    end_dist = distance_list[-1]

    # -------- V形检测：最小距离点在中间区域 且 两侧凹陷深度足够 --------
    min_dist = min(distance_list)
    min_idx = distance_list.index(min_dist)
    margin = max(1, data_len // 5)
    is_v_shape = False

    if margin <= min_idx <= data_len - 1 - margin:
        front_half = distance_list[:min_idx + 1]
        back_half = distance_list[min_idx:]
        depth_from_start = start_dist - min_dist
        depth_from_end = end_dist - min_dist
        if depth_from_start >= V_SHAPE_DEPTH_MIN and depth_from_end >= V_SHAPE_DEPTH_MIN:
            if len(front_half) >= 2 and len(back_half) >= 2:
                front_trend = front_half[0] - front_half[-1]
                back_trend = back_half[-1] - back_half[0]
                if front_trend >= 0 and back_trend >= 0:
                    is_v_shape = True

    delta = start_dist - end_dist  # 正=开始远结束近(进入)，负=开始近结束远(离开)
    abs_delta = abs(delta)

    print(f"[方向判定-lite] 数据点数:{data_len}, 开始距离:{round(start_dist, 2)}m, "
          f"结束距离:{round(end_dist, 2)}m, 最小距离:{round(min_dist, 2)}m, "
          f"首尾差值:{round(abs_delta, 2)}m, V形:{is_v_shape}")

    if is_v_shape:
        if start_dist > CAMERA_RANGE and end_dist > CAMERA_RANGE:
            print(f"[V形万能卡-lite] 开始{round(start_dist, 2)}m和结束{round(end_dist, 2)}m均>摄像头范围{CAMERA_RANGE}m")
            return "万能计数卡"
        if abs_delta > DIRECTION_DIST_THRESHOLD:
            if start_dist < end_dist:
                print(f"[V形离开-lite] 开始{round(start_dist, 2)}m < 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "离开"
            else:
                print(f"[V形进入-lite] 开始{round(start_dist, 2)}m > 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "进入"
        print(f"[V形万能卡-lite] 差值{round(abs_delta, 2)}m ≤ 阈值{DIRECTION_DIST_THRESHOLD}m，方向不确定")
        return "万能计数卡"
    else:
        if abs_delta > DIRECTION_DIST_THRESHOLD:
            if delta > 0:
                print(f"[单调进入-lite] 开始{round(start_dist, 2)}m > 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "进入"
            else:
                print(f"[单调离开-lite] 开始{round(start_dist, 2)}m < 结束{round(end_dist, 2)}m, 差值{round(abs_delta, 2)}m")
                return "离开"
        print(f"[万能计数卡-lite] 首尾差值{round(abs_delta, 2)}m ≤ 阈值{DIRECTION_DIST_THRESHOLD}m，无明显方向")
        return "万能计数卡"


def query_card_group_data(conn, win_start, win_end, limit_distance=None, target_card_id=None):
    """查询指定时间窗口内的UWB卡片数据，可选距离过滤和指定卡片ID"""
    params = [win_start, win_end]
    dist_filter = ""
    card_filter = ""
    if limit_distance is not None:
        dist_filter = " AND distance > %s AND distance < %s"
        params.append(DIST_LOWER)
        params.append(float(limit_distance))
    if target_card_id is not None:
        card_filter = " AND card_id = %s"
        params.append(str(target_card_id))
    sql = f"""
        SELECT timestamp, card_id, distance
        FROM uwb_data
        WHERE timestamp BETWEEN %s AND %s{dist_filter}{card_filter}
        ORDER BY timestamp ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    res_list = []
    for ts_val, cid, dist in rows:
        res_list.append({
            "card_id": str(cid),
            "ts": float(ts_val),
            "dist": float(dist),
            "time_str": format_uwb_time(float(ts_val))
        })
    return res_list


# ===================== 时序轨迹对齐插值 + 轨迹相似度计算 =====================
def align_track_to_uniform_time_axis(track: list, global_t_min: float, global_t_max: float, sample_gap: float):
    """将轨迹对齐到统一时间轴并插值"""
    orig_ts = np.array([p["ts"] for p in track], dtype=np.float64)
    orig_dist = np.array([p["dist"] for p in track], dtype=np.float64)
    uniform_ts = np.arange(global_t_min, global_t_max + sample_gap, sample_gap)
    uniform_dist = np.interp(uniform_ts, orig_ts, orig_dist)
    return uniform_ts.tolist(), uniform_dist.tolist()


def calc_cosine(vec1: list, vec2: list) -> float:
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = math.sqrt(sum(x ** 2 for x in vec1))
    mag2 = math.sqrt(sum(x ** 2 for x in vec2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    sim = dot / (mag1 * mag2)
    return round(max(min(sim, 1.0), 0.0), 4)


def resample_seq(seq: list, target_len: int) -> list:
    """将序列均匀插值到目标长度，用于不同长度速度序列对齐比较"""
    if not seq:
        return [0.0] * target_len
    if len(seq) == target_len:
        return seq
    x_old = np.linspace(0, 1, len(seq))
    x_new = np.linspace(0, 1, target_len)
    return np.interp(x_new, x_old, np.array(seq, dtype=np.float64)).tolist()


def calc_pearson(vec1: list, vec2: list) -> float:
    """皮尔逊相关系数：去均值后计算相关，反映趋势形态而非绝对距离大小
    将返回值裁断到 [0, 1]：负相关（轨迹完全反向）截断为0"""
    if len(vec1) < 2 or len(vec2) < 2:
        return 0.0
    arr1 = np.array(vec1, dtype=np.float64)
    arr2 = np.array(vec2, dtype=np.float64)
    if np.std(arr1) < 1e-9 or np.std(arr2) < 1e-9:
        return 0.0  # 常数序列（如静止卡片）无法体现趋势
    r = float(np.corrcoef(arr1, arr2)[0, 1])
    return round(max(min(r, 1.0), 0.0), 4)  # 负相关截断为0（不是同一人）


def calc_time_series_track_similarity(track1: list, speed_seq1: list, track2: list, speed_seq2: list):
    """计算两条UWB轨迹的时序相似度"""
    ts1 = np.array([p["ts"] for p in track1], dtype=np.float64)
    ts2 = np.array([p["ts"] for p in track2], dtype=np.float64)

    # 1. 全局公共时间轴，统一插值对齐时间
    t_min = min(np.min(ts1), np.min(ts2))
    t_max = max(np.max(ts1), np.max(ts2))
    uniform_ts, dist_curve1 = align_track_to_uniform_time_axis(track1, t_min, t_max, TRACK_SAMPLE_INTERVAL)
    _, dist_curve2 = align_track_to_uniform_time_axis(track2, t_min, t_max, TRACK_SAMPLE_INTERVAL)

    # 2. 距离曲线趋势相似度：皮尔逊相关（去均值）而非余弦，避免绝对距离大当导致虚高相似度
    track_time_sim = calc_pearson(dist_curve1, dist_curve2)

    # 3. 速度序列对齐：两卡速度段数可能不同，先插值到相同长度再比较
    target_len = max(len(speed_seq1), len(speed_seq2))
    speed_sim = calc_cosine(
        resample_seq(speed_seq1, target_len),
        resample_seq(speed_seq2, target_len)
    )

    # 4. 同一时刻两卡测距差値（局域空间偏移）
    dist_diff_arr = [abs(d1 - d2) for d1, d2 in zip(dist_curve1, dist_curve2)]
    avg_dist_offset = float(np.mean(dist_diff_arr))
    max_dist_offset = float(np.max(dist_diff_arr))

    # 逐点超阈偏离占比：统计偏移超过POINT_OUTLIER_THRESHOLD的采样点占比
    # 防止均值掩盖局部严重偏离（某些时刻两卡距离差很大，但均值仍看起来较小）
    outlier_count = sum(1 for d in dist_diff_arr if d > POINT_OUTLIER_THRESHOLD)
    outlier_ratio = round(outlier_count / len(dist_diff_arr), 4) if dist_diff_arr else 1.0

    # 空间贴近度：均值偏移越小得分越高（0~1）
    space_close_sim = max(0.0, 1.0 - avg_dist_offset / SPACE_OFFSET_THRESHOLD)

    # 5. 融合：距离趋势相似度 + 速度相似度 + 空间贴近度
    total_sim = round(track_time_sim * 0.5 + speed_sim * 0.2 + space_close_sim * 0.3, 4)

    return {
        "时序轨迹曲线相似度": track_time_sim,
        "速度曲线相似度": speed_sim,
        "同时刻平均测距偏移(m)": round(avg_dist_offset, 3),
        "同时刻最大测距偏移(m)": round(max_dist_offset, 3),
        "逐点超阈偏离占比": outlier_ratio,
        "空间贴近度得分": round(space_close_sim, 4),
        "综合轨迹相似度": total_sim,
        "公共时间区间": [format_uwb_time(t_min), format_uwb_time(t_max)],
        "统一采样点数": len(dist_curve1)
    }

# ==============================================================================
def uwb_similarity_monitor(enter_card_ids, card_full_track_cache):
    """对指定卡片组进行两两轨迹相似度计算，判断是否存在高度相似卡片"""
    similar_pairs = []
    if len(enter_card_ids) >= 2:
        for i in range(len(enter_card_ids)):
            c1 = enter_card_ids[i]
            track1 = card_full_track_cache[c1]["full_track"]
            sp1 = card_full_track_cache[c1]["speed_seq"]
            for j in range(i + 1, len(enter_card_ids)):
                c2 = enter_card_ids[j]
                track2 = card_full_track_cache[c2]["full_track"]
                sp2 = card_full_track_cache[c2]["speed_seq"]
                sim_res = calc_time_series_track_similarity(track1, sp1, track2, sp2)
                avg_off = sim_res["同时刻平均测距偏移(m)"]
                max_off = sim_res["同时刻最大测距偏移(m)"]
                outlier_r = sim_res.get("逐点超阈偏离占比", 1.0)
                is_high_similar = (
                    sim_res["综合轨迹相似度"] >= SIMILARITY_THRESHOLD  # 综合趋势相似
                    and avg_off <= MAX_ALLOW_AVG_OFFSET                # 平均偏移不超限
                    and max_off <= MAX_ALLOW_MAX_OFFSET                 # 任意时刻最大偏移不超限
                    and outlier_r <= MAX_OUTLIER_RATIO                  # 逐点偏离点占比不超限
                )
                pair_info = {
                    "卡片对": [c1, c2],
                    "公共时间窗口": sim_res["公共时间区间"],
                    "时序轨迹曲线相似度": sim_res["时序轨迹曲线相似度"],
                    "速度曲线相似度": sim_res["速度曲线相似度"],
                    "综合轨迹相似度": sim_res["综合轨迹相似度"],
                    "同时刻平均偏移(m)": avg_off,
                    "同时刻最大偏移(m)": max_off,
                    "逐点超阈偏离占比": outlier_r,
                    "统一采样点数": sim_res["统一采样点数"],
                    "高度相似": is_high_similar
                }
                similar_pairs.append(pair_info)
                print(f"  综合相似度:{sim_res['综合轨迹相似度']} 均值偏移:{avg_off}m "
                      f"最大偏移:{max_off}m 超阈占比:{outlier_r:.1%} → 高度相似:{is_high_similar}")
    else:
        print("轨迹数量小于2 无法判断")
        return 0

    # 全部相似度计算完成后统一判断是否存在高度相似卡片
    has_high_similar = any(item["高度相似"] for item in similar_pairs)
    if has_high_similar:
        print(f"检测到高度相似卡片对(综合相似≥{SIMILARITY_THRESHOLD} 且 均值偏移≤{MAX_ALLOW_AVG_OFFSET}m"
              f" 且 最大偏移≤{MAX_ALLOW_MAX_OFFSET}m 且 超阈占比≤{MAX_OUTLIER_RATIO:.0%})，返回1")
        return 1
    else:
        print(f"未检测到满足全部高度相似条件的卡片对，返回0")
        return 0


def get_uwb_continuous_distance_info(
        db_path, start_time, end_time, Entering_num, Exiting_num, max_distance=20
):
    conn = None
    try:
        # db_path 参数仅为兼容旧调用方保留；实际连接 config/ApiConfig.ini 配置的 MySQL
        orig_s = parse_uwb_time(start_time)
        orig_e = parse_uwb_time(end_time)
        if orig_s > orig_e:
            orig_s, orig_e = orig_e, orig_s
        conn = _connect_uwb_db()

        # ===== 阶段一：扩充±TIME_A_EXPAND_SEC搜索窗口，寻找max_distance范围内的所有UWB卡 =====
        search_s = orig_s - TIME_A_EXPAND_SEC
        search_e = orig_e + TIME_A_EXPAND_SEC
        print(f"[搜索窗口] {format_uwb_time(search_s)} ~ {format_uwb_time(search_e)} "
              f"(±{TIME_A_EXPAND_SEC}s扩充) | 距离过滤: {DIST_LOWER}~{max_distance}m")
        search_all_raw = query_card_group_data(conn, search_s, search_e, limit_distance=max_distance)
        found_card_ids = sorted({item["card_id"] for item in search_all_raw})
        if not found_card_ids:
            print(f"[提示] 搜索窗口内 {max_distance}m 范围内无任何UWB卡片")
            return -1, []
        print(f"[搜索结果] 共找到 {len(found_card_ids)} 张卡: {found_card_ids}")

        # ===== 阶段二：为每张卡拉取FULL_TRACK_DURATION秒完整轨迹（以原始窗口中点为中心）=====
        # 完整轨迹用于补全稀疏时段的运动信息，无距离过滤保留全程数据
        mid_t = (orig_s + orig_e) / 2
        track_s = mid_t - FULL_TRACK_DURATION / 2
        track_e = mid_t + FULL_TRACK_DURATION / 2
        print(f"[轨迹窗口] {format_uwb_time(track_s)} ~ {format_uwb_time(track_e)} "
              f"({FULL_TRACK_DURATION}s, 中心={format_uwb_time(mid_t)}) | 无距离过滤")

        card_full_track_cache = {}
        static_eliminate_count = 0

        for card_id in found_card_ids:
            # 拉取完整轨迹（无距离过滤，保留全程测距数据）
            raw_track = query_card_group_data(conn, track_s, track_e,
                                              limit_distance=None, target_card_id=card_id)
            if not raw_track:
                print(f"[卡片{card_id}] 轨迹窗口内无数据，跳过")
                continue

            # 滤除测距突变异常点
            clean_track = filter_outlier_distance_track(raw_track)
            if len(clean_track) < MIN_DIRECTION_RECORD:
                print(f"[卡片{card_id}] 滤波后仅{len(clean_track)}条 < {MIN_DIRECTION_RECORD}，数据不足，跳过")
                continue

            # ===== 阶段三：通行区间检测 ——
            #   使用完整轨迹插值，判断原始时间窗口a内是否有轨迹经过 PASS_ZONE_MIN~PASS_ZONE_MAX =====
            ts_min = min(p["ts"] for p in clean_track)
            ts_max = max(p["ts"] for p in clean_track)
            interp_start = max(orig_s, ts_min)
            interp_end = min(orig_e, ts_max)
            in_pass_zone = False
            if interp_start < interp_end:
                # 在原始时间窗口内插值，精确判断是否经过通行区
                _, interp_dist = align_track_to_uniform_time_axis(
                    clean_track, interp_start, interp_end, TRACK_SAMPLE_INTERVAL)
                in_pass_zone = any(PASS_ZONE_MIN <= d <= PASS_ZONE_MAX for d in interp_dist)
                min_d_in_orig = min(interp_dist) if interp_dist else float('inf')
            else:
                min_d_in_orig = float('inf')

            if not in_pass_zone:
                orig_pts = sum(1 for p in clean_track if orig_s <= p["ts"] <= orig_e)
                print(f"[卡片{card_id}] 原始时间窗口内轨迹未经过{PASS_ZONE_MIN}~{PASS_ZONE_MAX}m通行区 "
                      f"(窗口内点数:{orig_pts}, 最近距离:{round(min_d_in_orig, 2)}m)，排除")
                continue
            print(f"[卡片{card_id}] 通过通行区检测({PASS_ZONE_MIN}~{PASS_ZONE_MAX}m)，保留")

            # 静态卡片检测（5-95百分位极差）
            dist_arr = np.array([p["dist"] for p in clean_track], dtype=np.float64)
            dist_range = round(float(np.percentile(dist_arr, 95) - np.percentile(dist_arr, 5)), 3)
            if dist_range <= STATIC_RANGE_THRESHOLD:
                static_eliminate_count += 1
                print(f"[卡片{card_id}] 全轨迹活动范围{dist_range}m ≤ {STATIC_RANGE_THRESHOLD}m，判定静态，剔除")
                continue

            # 缓存完整轨迹，供后续方向判定和相似度比对共用
            speed_res = calc_average_speed_full_track(clean_track)
            card_full_track_cache[card_id] = {
                "full_track": clean_track,
                "speed_seq": speed_res["speed_seq"],
                "speed_m_s": speed_res["speed_m_s"],
                "segment_count": speed_res["segment_count"]
            }
            print(f"[卡片{card_id}] 轨迹构建完成: {len(clean_track)}条 | "
                  f"平均速度{speed_res['speed_m_s']}m/s")

        if not card_full_track_cache:
            print("[提示] 所有卡均被过滤（无通行区数据或静态卡），无有效卡片")
            return -1, []

        # ===== 阶段四：方向判定（统一使用完整FULL_TRACK_DURATION秒轨迹，数据充足无需分级）=====
        card_direction_results = {}
        for card_id, cache in card_full_track_cache.items():
            dist_list = [p["dist"] for p in cache["full_track"]]
            move_type = judge_move_type(dist_list)
            card_direction_results[card_id] = move_type
            print(f"[卡片{card_id}] 方向判定: {move_type} ({len(dist_list)}条轨迹数据)")

        # ===== 阶段五：汇总方向统计 =====
        detail_list = []
        stat = {
            "进入人数": 0,
            "离开人数": 0,
            "万能计数卡数量": 0,
            "无法判定": 0,
            "静态剔除卡片数": static_eliminate_count
        }
        exit_card_ids = []
        enter_card_ids = []
        universal_card_ids = []
        for cid, move_type in card_direction_results.items():
            track_cache = card_full_track_cache.get(cid, {})
            speed = track_cache.get("speed_m_s", 0.0)
            seg_cnt = track_cache.get("segment_count", 0)
            full_track_len = len(track_cache.get("full_track", []))
            card_info = {
                "card_id": cid,
                "相似度轨迹点数": full_track_len,
                "速度有效分段数": seg_cnt,
                "平均径向速度(m/s)": speed,
                "运动分类": move_type
            }
            detail_list.append(card_info)
            if move_type == "进入":
                stat["进入人数"] += 1
                enter_card_ids.append(cid)
            elif move_type == "离开":
                stat["离开人数"] += 1
                exit_card_ids.append(cid)
            elif move_type == "万能计数卡":
                stat["万能计数卡数量"] += 1
                universal_card_ids.append(cid)
            else:
                stat["无法判定"] += 1

        # ===== 阶段六：人卡一致性判断 =====
        print('uwb信息', stat)
        expected_enter = max(0, int(Entering_num or 0))
        expected_exit = max(0, int(Exiting_num or 0))
        expected_total = expected_enter + expected_exit
        uwb_enter = stat["进入人数"]
        uwb_exit = stat["离开人数"]
        universal_count = stat["万能计数卡数量"]
        directional_total = uwb_enter + uwb_exit
        valid_uwb_total = directional_total + universal_count
        all_valid_card_ids = enter_card_ids + exit_card_ids + universal_card_ids
        if expected_total <= 0:
            # 没有视觉过线人数，无需比对，但仍返回所有检测到的卡ID
            return 0, all_valid_card_ids
        # 万能卡表示该时间段确有携卡人员经过但方向不确定，只用于补足视觉人数，不单独触发多卡报警。
        if valid_uwb_total < expected_total:
            print('UWB有效携卡人数少于视觉过线人数，疑似有人未携带定位卡')
            return -1, all_valid_card_ids
        if valid_uwb_total == expected_total:
            print('UWB有效携卡人数与视觉过线人数一致，万能卡按方向不确定人员参与匹配')
            return 0, all_valid_card_ids
        if directional_total == expected_total:
            print('UWB有效携卡人数与视觉过线人数一致，有向数恰好匹配，万能卡不计入')
            return 0, enter_card_ids + exit_card_ids
        # UWB有效卡数多于视觉人数时，仅在轨迹高度相似时判定一人多卡；否则不强报警，避免误报
        print('UWB有效携卡人数多于视觉过线人数，进入相似轨迹去重判断')
        if uwb_enter > expected_enter and uwb_similarity_monitor(enter_card_ids, card_full_track_cache) == 1:
            return 1, enter_card_ids + exit_card_ids
        if uwb_exit > expected_exit and uwb_similarity_monitor(exit_card_ids, card_full_track_cache) == 1:
            return 1, enter_card_ids + exit_card_ids
        return 0, all_valid_card_ids
    except pymysql.MySQLError as e:
        print(f"[数据库异常] {str(e)}")
        return 0, []
    except Exception as e:
        print(f"[程序运行异常] {str(e)}")
        import traceback
        traceback.print_exc()
        return 0, []
    finally:
        if conn:
            conn.close()


def main():
    """主函数入口"""
    parser = argparse.ArgumentParser(
        description="UWB出入口统计 | 时序时间+距离轨迹曲线相似度比对"
    )
    parser.add_argument("--db-path", default=DEFAULT_UWB_DB_PATH,
                        help="[已废弃] 连接信息统一取自config/ApiConfig.ini的MySQL配置")
    parser.add_argument("--start-time", default="2026-06-18 15:22:44", help="查询起始时间戳/日期字符串")
    parser.add_argument("--end-time", default="2026-06-18 15:22:53", help="查询结束时间戳/日期字符串")
    parser.add_argument("--max-distance", type=float, default=30,
                        help="time_a初始窗口距离过滤上限(m)，默认UWB探测范围30m")
    parser.add_argument("--expect-enter", type=int, default=0, help="预期进入人数Entering_num")
    parser.add_argument("--expect-exit", type=int, default=0, help="预期离开人数Exiting_num")
    args = parser.parse_args()
    result_code, uwb_card_ids = get_uwb_continuous_distance_info(
        db_path=args.db_path,
        start_time=args.start_time,
        end_time=args.end_time,
        Entering_num=args.expect_enter,
        Exiting_num=args.expect_exit,
        max_distance=args.max_distance
    )
    print(f"函数返回结果：{result_code} | UWB卡ID列表：{uwb_card_ids}")


def uwb01(db_path, start_time, end_time, Entering_num, Exiting_num, max_distance):
    """返回 (result_code: int, uwb_card_ids: list)
    result_code:  0=正常/不报警  1=应报警(一人多卡)  -1=UWB卡数少于视觉人数
    uwb_card_ids: 该分支下有效的UWB卡ID列表，无数据时为 []
    """
    return get_uwb_continuous_distance_info(
        db_path, start_time, end_time, Entering_num, Exiting_num, max_distance
    )


if __name__ == "__main__":
    main()