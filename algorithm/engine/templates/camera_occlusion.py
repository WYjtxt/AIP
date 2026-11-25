# -*- coding: utf-8 -*-
'''
camera_occlusion.py —— 摄像头遮挡检测（多证据融合 + 场景自适应基线）

挂在 templates/rtsp_infer_push.py 引擎上的独立后台监测线程：每 check_interval（默认 10s）
从取流回调"按需借帧"（frame_tap）拷贝几帧原始解码帧做检测。平时对热路径的开销只有每帧一次
Event 标志判断，检查窗口内才拷贝（每轮拷 frames_per_check 帧），完全不影响实时推理/推流。

判定算法（四路证据 + 多帧投票，兼顾高查准率与部分遮挡召回）：
  ① 极端画面：镜头被罩死 → 全黑；红外补光被近距离遮挡物反射 → 全白。均值/标准差直接判。
     基线场景本身很暗时（夜间无补光）不启用，防止夜里灯灭误报。
  ② 分块纹理塌缩（绝对证据）：灰度图 grid×grid 分块，块内 Laplacian 方差与"去光照趋势的
     高通残差"标准差同时低于阈值 → "平坦块"（残差 std 对补光光斑的平滑亮度渐变免疫）。
     遮挡物贴近镜头必然严重失焦，无论遮挡物本身有无纹理，成像都会塌缩为平坦模糊块。平坦块占比 ≥ 60%，且"直方图熵 ≤ entropy_thresh（遮挡后直方图聚集、熵骤降）
     或 横向梯度细节 gx_detail ≤ detail_thresh"才成立 —— 红外补光打在近距遮挡物上形成的
     平滑光斑会拉宽直方图、熵不一定降，但同样没有任何真实结构，横向梯度细节能兜住这种情况；
     基线场景天然平坦（对白墙/暗巷道）时不启用该证据。
  ③ 分块纹理丢失（相对基线证据，抓部分遮挡）：只在"确认无遮挡"时用 EMA 慢速更新每块的
     Canny 边缘密度基线。"丢失块" = 基线有纹理、当前既平坦又边缘骤降的块；丢失块占基线
     纹理块的比例 ≥ occlude_ratio 才成立。
     光照渐变/日夜切换后边缘结构仍在（不平坦）→ 不会误报；基线随场景缓慢自适应。
  ④ 补光灯振荡（检查级证据，抓"套袋后光感元件反复开关补光灯"）：镜头被罩住后光感元件
     在 补光亮→反光刺眼→关灯→变黑→再开灯 间振荡，画面亮暗闪烁：亮帧是遮挡物上的平滑
     光斑（熵高、直方图证据失效），暗帧近全黑，逐帧证据可能各只占一半票数而漏检。
     故在一次检查的采样帧间做时域融合：帧间亮度摆幅 ≥ flicker_delta 且"无结构帧"
     （gx_detail ≤ detail_thresh 或近全黑）占比 ≥ min_vote_ratio → 判遮挡。
     正常场景即便灯光在闪，亮帧里场景纹理仍在（gx_detail 高）→ 不会误报；
     基线场景本身无结构时不启用。亮度剧烈波动的检查窗口也不更新基线，防学入垃圾帧。
  ⑤ 场景结构替换（相对基线证据，抓"有纹理的遮挡物"）：编织袋等纹理遮挡物在近焦距离
     成像时画面并不平坦（编织纹/缝线产生大量边缘），①~④ 全部失效。但正常场景无论光照
     怎么变（日夜切换/灯开关只改对比度），边缘的"位置"不变，当前帧梯度结构图与基线的
     归一化相关系数（NCC）始终较高；遮挡物把整个场景换掉后，纹理再丰富、其结构与基线
     也毫不相关（NCC≈0）。判据：struct_corr ≤ corr_thresh 且当前帧确有结构
     （gx_detail 达标，全黑/纯光斑帧由①②兜住）且基线场景有结构。需基线预热完成
     （默认 3 轮 ≈ 15 分钟无遮挡画面）后才启用。
     注意：摄像头转动（云台巡航/人为调整视角）也会让场景整体改变而命中该证据，
     须与"纹理遮挡物"区分开 —— 见下方"转动抑制"三层逻辑：确认在焦的视角变化只
     静默重建基线、不报警。
  ⑥ 失焦+单色（绝对证据，无需基线；抓"开机/重启即被彩色织物贴脸遮挡"，此时基线可能
     已被遮挡画面污染、相对证据③⑤全部失效）：近距遮挡物必然失焦 —— 几乎没有锐利边缘。
     锐利度两条路任一满足即算"失焦"：全帧锐利梯度占比 ≤ sharp_thresh，或锐利块覆盖度
     ≤ spread_thresh（把锐利像素落到 grid×grid 块上数"含锐利内容的块"的占比 ——
     OSD 时间戳/厂名文字、织物上的零星镜面反光点虽能把全帧占比推过 sharp_thresh，
     但只集中在少数几个块里，推不动覆盖度；正常在焦场景锐利边缘遍布大半个画面）。
     再叠加"大面积同一色相高饱和"（红/橙编织袋被补光染满全屏）。正常在焦场景总有大范围
     锐利边缘、且大面积单色高饱和极罕见，双条件同时命中基本只可能是贴脸彩色遮挡物。
     夜间红外灰度画面饱和度≈0 不会命中（夜间场景由①②④负责）。门控：干净基线场景本身
     单色高饱和 且 基线有边缘结构（如对着刷漆的设备/墙面）时不启用 —— 若基线单色却几乎
     没有边缘，说明基线极可能就是被学进去的遮挡物（污染），⑥保持启用以便自救；
     开机即单色失焦则按"无基线"节流报警。
     防污染守卫：命中⑥色彩特征（大面积单色 + 边缘极低）的帧即便未达报警条件也一律
     不参与基线更新，防止漏检期间遮挡画面被 EMA 学成基线、反过来锁死相对证据③⑤与⑥门控。

转动抑制（防云台巡航/人为调整视角触发遮挡误报，三层）：
  a) 平移容差（证据⑤内）：NCC 低于阈值时再做一次平移搜索 —— 基线梯度图中央区域当模板
     在当前梯度图上滑动匹配（容差约 ±15% 画幅）。小幅转动/支架位移后场景只是"平移"而非
     "被替换"，平移后相关性恢复即不算 scene_replaced；被遮挡物替换的场景怎么平移都对不上。
  b) 转动中跳过（检查级）：相邻采样帧的梯度结构图做相位相关，全局平移 ≥ motion_shift 格
     说明摄像头正在转动 —— 帧间互相错位且有运动模糊，逐帧证据不可信，本轮直接跳过
     （不判遮挡、不更新基线）。连续跳过超过 motion_max_skip 轮则不再跳过，防止风吹飘动
     的遮挡物借"全局位移"永久逃逸检测。全黑/纯光斑等无结构帧的相位相关是噪声，
     不参与转动判定（遮挡帧伪造不出"转动"）。
  c) 转定后的新场景（检查级）：仅命中 scene_replaced 且画面确认在焦（sharp_frac 与
     sharp_spread 双达标、非单色可疑帧）→ 判为视角变化而非遮挡：不报警，连续
     relearn_checks 轮后走原自愈流程静默重建基线。贴近镜头的纹理遮挡物必然失焦
     （sharp_spread 推不过阈值，见证据⑥），转动后的真实场景锐利边缘遍布画面，
     二者以锐度区分；失焦/单色可疑帧仍按遮挡照常报警。

基线持久化与自愈：基线每次更新后落盘（默认 <输出根>/<conf_name>/baseline.npz），进程重启
直接加载、不再裸预热 —— 防止"重启时正被遮挡 → 遮挡画面被学成基线"（此时 corr≈1，
证据③⑤全部失效）。若基线仍被污染（如首次部署即遮挡），取下遮挡物后真实场景会连续
仅命中 scene_replaced，达到 relearn_checks 轮后自动重建基线恢复正常。

多帧投票：一次检查采 frames_per_check 帧（间隔 frame_gap 秒），判遮挡帧数占比 ≥ min_vote_ratio
（或命中证据④）才算遮挡，排除行人短暂贴近镜头等瞬态干扰。

报警：发送方式与人员计数模块（muban_PersonCount.counting_upload_worker）相同 ——
存原图与报警标注图（遮挡块半透明标红，仅本地留档排查用），原图 URL（主机=算力盒本机
cm.localhost_ip，图存盒子上）经 data_send.upload_hwj 的 carousel/ori 两个字段上报 kafka，
warning_message 携带报警文本"疑似存在视频遮挡"，报警开始时间走 result_count_time
字段（平台读该字段作开始时间，start_time 平台不读、仅一并携带），结束时间走 res_time
（现场暂定开始=结束=本次上报时刻；遮挡 episode 实际起点只写本地日志）；
另经 data_send.insert_alg_log 写本地算法日志。上报本身就在监测线程里执行，
不占用引擎聚合/推流线程。

接入方式（见 model_start.stream_worker / rtsp_infer_push.run）：
    cfg['occlusion'] = camera_occlusion.occlusion_cfg_from_row(rows[0])
    rtsp_infer_push.run(cfg)     # 引擎检测到 cfg['occlusion'] 自动创建并启动 OcclusionMonitor
cfg['occlusion'] 除身份字段外还可覆盖检测参数（check_interval / frames_per_check / occlude_ratio
/ lap_thresh / entropy_thresh ... 见 OcclusionMonitor.__init__ 与 OcclusionDetector.__init__）。
'''
import os
import math
import time
import logging
import threading
from datetime import datetime

import cv2
import numpy as np

from comm import data_send
from config import common as cm
from templates import alarm_video

# 汇入该路流引擎的日志文件（rtsp_infer_push_<流标识>.log），现场排查时同一处看
logger = logging.getLogger('rtsp_infer_push')

# 报警文本（upload_hwj 的 warning_message 字段 + 本地算法日志共用）
ALARM_TEXT = '疑似存在视频遮挡'
ALARM_CASE = '0001'   # 视频质量异常编码：画面遮挡（平台 t_algorithm_result.analysis_case）

# 报警图输出根目录（与 dangerous 等模板同风格：results/<业务>/result/<conf_name>/images）
_OUTPUT_ROOT = '/data/AIGO/outputs/occlusion/result'

# OcclusionDetector 可从 cfg['occlusion'] 覆盖的参数名
_DETECTOR_KEYS = ('grid', 'occlude_ratio', 'lap_thresh', 'std_thresh', 'entropy_thresh',
                  'detail_thresh', 'corr_thresh', 'sharp_thresh', 'spread_thresh',
                  'mono_thresh', 'edge_drop_ratio', 'textured_edge', 'baseline_alpha',
                  'baseline_warmup', 'analysis_width')

# 证据⑤梯度结构图的尺寸：粗到能压住噪声/轻微抖动，细到能区分"结构搬家"（64×36 ≈ 16:9）
_GRAD_MAP_SIZE = (64, 36)


class OcclusionDetector:
    '''遮挡检测器：分块纹理塌缩 + 全局熵/边缘密度 + 场景自适应基线（EMA）。

    analyze() 是纯分析（不改状态）；update_baseline() 只应在"确认无遮挡"的帧上调用，
    否则遮挡画面会被学进基线导致持续遮挡不再报警。'''

    def __init__(self, grid=8, occlude_ratio=0.5, lap_thresh=15.0, std_thresh=8.0,
                 entropy_thresh=4.5, detail_thresh=0.015, corr_thresh=0.25,
                 sharp_thresh=0.010, spread_thresh=0.15, mono_thresh=0.5,
                 edge_drop_ratio=0.35, textured_edge=0.02, baseline_alpha=0.15,
                 baseline_warmup=3, analysis_width=480):
        self.grid = int(grid)                        # 分块数（grid×grid）
        self.occlude_ratio = float(occlude_ratio)    # 判部分遮挡所需的"丢失块"占比
        self.lap_thresh = float(lap_thresh)          # 平坦块：Laplacian 方差上限
        self.std_thresh = float(std_thresh)          # 平坦块：灰度标准差上限
        self.entropy_thresh = float(entropy_thresh)  # 全局直方图熵上限（遮挡后骤降）
        self.detail_thresh = float(detail_thresh)    # 横向梯度细节占比下限（正常场景 0.05~0.3，
                                                     # 近距失焦遮挡/纯光斑/全黑趋近 0）
        self.corr_thresh = float(corr_thresh)        # 梯度结构图与基线的 NCC 下限（正常光照变化
                                                     # >0.4，场景被遮挡物整体替换后 ≈0）
        self.sharp_thresh = float(sharp_thresh)      # 锐利梯度像素全帧占比上限（正常在焦场景
                                                     # 0.03~0.15，全画面失焦后 <0.005）
        self.spread_thresh = float(spread_thresh)    # 锐利块覆盖度上限：含锐利内容的块占比。
                                                     # 正常在焦场景锐利边缘遍布画面 >0.2，
                                                     # 失焦画面里只剩 OSD 文字/零星反光的
                                                     # 几个块 <0.15（证据⑥第二条失焦判据）
        self.mono_thresh = float(mono_thresh)        # 单色度下限：高饱和像素覆盖率×色相集中度
                                                     # （彩色织物贴脸 >0.7，正常场景 <0.3）
        self.edge_drop_ratio = float(edge_drop_ratio)  # 块边缘密度跌到基线的该比例以下算"骤降"
        self.textured_edge = float(textured_edge)    # 基线块边缘密度 ≥ 该值才算"有纹理块"
        self.baseline_alpha = float(baseline_alpha)  # 基线 EMA 步长（每次无遮挡检查更新一次）
        self.baseline_warmup = int(baseline_warmup)  # 基线累计更新次数达到后才启用相对证据/门控
        self.analysis_width = int(analysis_width)    # 分析用缩放宽度（降算力，1080p→480 足够）
        # 基线（仅 update_baseline 修改）
        self._base_blk_edge = None    # (grid, grid) 每块边缘密度
        self._base_grad = None        # _GRAD_MAP_SIZE 梯度结构图（证据⑤用）
        self._base_edge = 0.0         # 全局边缘密度
        self._base_flat = 0.0         # 平坦块占比
        self._base_mean = 0.0         # 全局亮度
        self._base_gx = 0.0           # 全局横向梯度细节占比
        self._base_mono = 0.0         # 单色度（证据⑥门控：干净场景本身单色则不启用⑥）
        self._base_n = 0              # 已更新次数

    def _prepare(self, frame_bgr):
        '''BGR → 灰度 → 等比缩到 analysis_width → 5×5 高斯（压制夜间红外高增益噪点的伪纹理：
        噪声的 Laplacian 方差必须压到 lap_thresh 以下，否则满屏噪点会让遮挡帧"看似有纹理"；
        真实场景纹理的 Laplacian 方差高一个数量级以上，5×5 平滑后依然远超阈值）。'''
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        if w > self.analysis_width:
            nh = max(self.grid, int(round(h * self.analysis_width / float(w))))
            gray = cv2.resize(gray, (self.analysis_width, nh), interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def analyze(self, frame_bgr):
        '''单帧遮挡分析。返回 (occluded: bool, metrics: dict)；metrics 含各特征值、
        flat_map/lost_map（grid×grid bool，供报警图标注）、reasons（命中的证据名列表）。'''
        g = self.grid
        gray = self._prepare(frame_bgr)
        h, w = gray.shape[:2]
        gh, gw = h // g, w // g
        if gh <= 0 or gw <= 0:
            return False, dict(mean=0.0, std=0.0, entropy=0.0, edge_density=0.0, gx_detail=0.0,
                               struct_corr=1.0, sharp_frac=0.0, sharp_spread=0.0,
                               mono_ratio=0.0, suspect=False, dark_frac=0.0, clip_frac=0.0,
                               base_shift=0.0, shift_corr=0.0, shift_full_corr=0.0,
                               flat_ratio=0.0, lost_ratio=0.0, reasons=[],
                               flat_map=np.zeros((g, g), bool), lost_map=np.zeros((g, g), bool),
                               blk_edge=np.zeros((g, g), np.float32),
                               grad_map=np.zeros(_GRAD_MAP_SIZE[::-1], np.float32))
        mean = float(gray.mean())
        std = float(gray.std())
        # 供视频质量检测（video_quality）复用的亮度分布量：暗像素/饱和像素占比。
        # 在同一份缩放灰度图上顺带统计，避免质量模块重复做灰度/缩放。
        # 口径注意：gray 已经过 INTER_AREA 降采样 + 5×5 高斯（_prepare），过曝/暗区
        # 边界像素被平滑拉离极值，clip_frac/dark_frac 相对原帧系统性偏低/偏钝 ——
        # 过暗/过曝阈值（dark_frac/overexpose_frac）按此口径整定，调参时勿按原帧理解。
        dark_frac = float((gray < 50).mean())
        clip_frac = float((gray >= 250).mean())

        lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
        med = float(np.median(gray))
        lo = int(max(0, 0.66 * med))
        hi = max(lo + 1, int(min(255, 1.33 * med)))
        edges = cv2.Canny(gray, lo, hi)
        edge_density = float(edges.mean()) / 255.0

        # 横向梯度细节占比：|Sobel_x| 显著的像素比例。对亮度绝对值、平滑光照渐变（红外光斑）、
        # 逐行曝光条带都不敏感，只响应真实场景结构（竖直边缘/纹理），是闪烁场景下最稳的结构量。
        # 阈值 20 高于高斯平滑后夜间噪声的 Sobel 响应尾部，避免高增益噪点被当成细节。
        sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gx_detail = float((np.abs(sx) > 20.0).mean())

        # 梯度结构图（证据⑤用）：梯度幅值缩到 _GRAD_MAP_SIZE，只保留"边缘长在哪"的空间布局。
        # 与基线做归一化相关（NCC）：对全局亮度/对比度变化不敏感，只对"结构搬家"敏感。
        gmag = cv2.magnitude(sx, sy)
        grad_map = cv2.resize(gmag, _GRAD_MAP_SIZE, interpolation=cv2.INTER_AREA)

        # 锐利梯度（证据⑥用）：在焦场景的物体边缘 1~2 像素完成灰度跳变，梯度幅值大且大范围
        # 分布；近距失焦画面只有"软"梯度。两种统计：全帧占比 sharp_frac；锐利块覆盖度
        # sharp_spread（锐利像素密度 >2% 的块占比）—— OSD 时间戳/厂名文字与织物上的零星
        # 镜面反光点能把全帧占比推过 sharp_thresh（现场实测袋子帧 sharp_frac=0.014），
        # 但只集中在少数块里，覆盖度依然极低；正常在焦场景锐利边缘遍布大半个画面。
        sharp_mask = gmag > 90.0
        sharp_frac = float(sharp_mask.mean())

        # 单色度（证据⑥用）：高饱和像素覆盖率 × 色相圆均值向量长（集中度）。红/橙织物贴脸
        # 且被补光染满全屏时 ≈0.7~1.0；正常场景色相分散或饱和度低 <0.3；夜间红外灰度 ≈0。
        small = cv2.resize(frame_bgr, (w, h), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        sat_mask = (hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 40)
        mono_ratio = 0.0
        cover = float(sat_mask.mean())
        if cover > 0.05:
            ang = hsv[:, :, 0][sat_mask].astype(np.float32) * (np.pi / 90.0)  # H∈[0,180)→全圆
            mono_ratio = cover * float(np.hypot(np.cos(ang).mean(), np.sin(ang).mean()))

        # 去光照趋势的高通残差：大尺度高斯模糊作估计的光照场，残差里只剩真实纹理/噪声。
        # 补光灯打在近距遮挡物上的平滑亮度渐变会把块内原始灰度 std 抬过阈值（"不平坦"→漏检），
        # 块内 std 改在高通残差上算即对光照渐变免疫，真实纹理块的残差 std 依然很高。
        illum = cv2.GaussianBlur(gray, (0, 0), 15)
        hp = gray.astype(np.float32) - illum.astype(np.float32)

        # 分块统计：reshape 成 (g, gh, g, gw) 后对块内两维聚合，无逐块 Python 循环
        gf = hp[:gh * g, :gw * g].reshape(g, gh, g, gw)
        blk_std = gf.std(axis=(1, 3))
        lf = lap[:gh * g, :gw * g].reshape(g, gh, g, gw)
        blk_lap_var = lf.var(axis=(1, 3))
        ef = edges[:gh * g, :gw * g].reshape(g, gh, g, gw)
        blk_edge = (ef.mean(axis=(1, 3)) / 255.0).astype(np.float32)
        sf = sharp_mask[:gh * g, :gw * g].reshape(g, gh, g, gw)
        sharp_spread = float((sf.mean(axis=(1, 3)) > 0.02).mean())

        flat_map = (blk_lap_var < self.lap_thresh) & (blk_std < self.std_thresh)
        flat_ratio = float(flat_map.mean())

        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
        p = hist / max(1.0, float(hist.sum()))
        p = p[p > 0]
        entropy = float(-(p * np.log2(p)).sum())

        base_ok = self._base_blk_edge is not None and self._base_n >= self.baseline_warmup
        reasons = []

        # 证据①：罩死全黑 / 红外近距反光全白（基线本身很暗的场景不启用，防夜间灯灭误报）
        if (mean < 8.0 or mean > 247.0) and std < 6.0:
            if not base_ok or self._base_mean >= 25.0:
                reasons.append('blackout' if mean < 8.0 else 'whiteout')

        # 证据②：绝对大面积纹理塌缩（基线天然平坦的场景不启用，防白墙/暗巷道误报）。
        # 熵、横向梯度细节两条路任一命中即可：补光灯打在近距遮挡物上的平滑光斑会拉宽直方图
        # （熵不降），但 gx_detail 仍趋近 0，能兜住"套袋 + 补光反光"这类亮而无结构的画面。
        if flat_ratio >= max(0.6, self.occlude_ratio) and \
                (entropy <= self.entropy_thresh or gx_detail <= self.detail_thresh):
            if not base_ok or self._base_flat <= 0.4:
                reasons.append('flat_collapse')

        # 证据⑥：整幅失焦 + 单色高饱和（绝对证据，无需基线，抓"开机/重启即被彩色织物贴脸
        # 遮挡"——此时基线可能已被遮挡画面污染，相对证据③⑤全部失效）。近距遮挡物必然失焦：
        # 几乎没有锐利边缘 —— 全帧占比 sharp_frac 与块覆盖度 sharp_spread 任一达标即算失焦
        # （OSD 文字/零星镜面反光会抬高 sharp_frac 但推不动 sharp_spread）；再叠加大面积
        # 同色相高饱和。正常在焦场景总有大范围锐利边缘，双条件同时命中基本只可能是贴脸
        # 彩色遮挡物。suspect 同时供基线更新守卫用：带⑥色彩特征的帧不学进基线（防污染）。
        # 门控：干净基线场景本身单色高饱和 且 基线有边缘结构（刷漆的设备/墙面）才不启用；
        # 基线单色却几乎无边缘 = 基线极可能就是被学进去的遮挡物（污染），⑥保持启用自救。
        suspect = mono_ratio >= self.mono_thresh and edge_density <= 0.012
        if suspect and (sharp_frac <= self.sharp_thresh
                        or sharp_spread <= self.spread_thresh):
            mono_scene = base_ok and self._base_mono >= 0.4 \
                and self._base_edge >= 0.5 * self.textured_edge
            if not mono_scene:
                reasons.append('blur_mono')

        # 证据⑤：场景结构被整体替换（编织袋等纹理遮挡物近焦成像时画面不平坦，①~④失效，
        # 但其梯度结构与基线场景毫不相关）。要求当前帧确有结构（gx_detail 达标——全黑/纯光斑
        # 由①②兜住，且防止"灯灭无梯度→相关性无意义"式误报）且基线场景有结构。
        # 正常光照变化/日夜切换只改对比度、不动边缘位置，NCC 仍高，不会误报。
        struct_corr = 1.0
        base_shift = 0.0        # 当前帧结构相对基线的最优平移量（梯度图格，64 格≈全宽）
        shift_corr = 0.0        # 平移搜索的最优相关（挪动检测用：位移大但相关高=同场景被移动）
        shift_full_corr = 0.0   # 按该位移对齐后全帧重叠区 NCC（挪动检测用：排除"前景物
                                # 挡住半边画面"造成的模板匹配假位移）
        if base_ok and self._base_grad is not None:
            a_map = grad_map - grad_map.mean()
            b_map = self._base_grad - self._base_grad.mean()
            denom = float(np.sqrt((a_map * a_map).sum() * (b_map * b_map).sum()))
            struct_corr = float((a_map * b_map).sum() / denom) if denom > 1e-6 else 1.0
            # 转动抑制 a) 平移容差：云台小幅转动/支架位移后场景只是"平移"而非"被替换"，
            # 原位 NCC 会骤降。把基线梯度图中央区域当模板在当前梯度图上滑动匹配
            # （容差约 ±15% 画幅），平移后相关性恢复则不算 scene_replaced；
            # 被遮挡物替换的场景与基线毫不相关，怎么平移都对不上。
            # 平移搜索现改为无条件执行（64×36 梯度图上开销可忽略）：除证据⑤外，还持续
            # 输出 base_shift/shift_corr 给视频质量检测的"摄像仪挪动"判据 —— 小幅挪动
            # 后 NCC 往往仍高于 corr_thresh，遮挡证据不响应，但位移本身即是挪动信号。
            mh, mw = _GRAD_MAP_SIZE[1] // 6, _GRAD_MAP_SIZE[0] // 6
            tpl = self._base_grad[mh:-mh, mw:-mw]
            if float(tpl.std()) > 1e-6:
                res = cv2.matchTemplate(grad_map, tpl, cv2.TM_CCOEFF_NORMED)
                _, mx, _, mloc = cv2.minMaxLoc(res)
                shift_corr = float(mx)
                sdx, sdy = mloc[0] - mw, mloc[1] - mh
                base_shift = float(math.hypot(sdx, sdy))
                # 全帧平移验证（挪动检测用）：把当前梯度图按找到的位移对齐基线后，
                # 在重叠区再算一次 NCC。真挪动是"整幅场景平移"，重叠区相关依然很高；
                # 大面积近景前景物（有人站在镜头前挡住半边）只是让中央模板匹配挪了位，
                # 位移解释不了整幅画面，重叠区相关上不去（现场实测的误报模式）。
                gh_m, gw_m = grad_map.shape
                ax0, ay0 = max(0, sdx), max(0, sdy)
                bx0, by0 = max(0, -sdx), max(0, -sdy)
                ow, oh = gw_m - abs(sdx), gh_m - abs(sdy)
                if ow > 8 and oh > 8:
                    a_ov = grad_map[ay0:ay0 + oh, ax0:ax0 + ow]
                    b_ov = self._base_grad[by0:by0 + oh, bx0:bx0 + ow]
                    a_c = a_ov - a_ov.mean()
                    b_c = b_ov - b_ov.mean()
                    den = float(np.sqrt((a_c * a_c).sum() * (b_c * b_c).sum()))
                    shift_full_corr = float((a_c * b_c).sum() / den) if den > 1e-6 else 0.0
                if struct_corr <= self.corr_thresh:
                    struct_corr = max(struct_corr, shift_corr)
            if struct_corr <= self.corr_thresh and gx_detail >= self.detail_thresh \
                    and self._base_gx >= 2.0 * self.detail_thresh:
                reasons.append('scene_replaced')

        # 证据③：相对基线的分块纹理丢失（部分遮挡；要求基线场景本身有足够纹理块）
        lost_map = np.zeros((g, g), bool)
        lost_ratio = 0.0
        if base_ok:
            textured = self._base_blk_edge >= self.textured_edge
            n_text = int(textured.sum())
            if n_text >= max(1, int(0.3 * g * g)):
                # 不用全局边缘密度做门控：Canny 阈值随全帧中值自适应，遮挡后剩余画面的阈值
                # 整体下移、边缘密度反而虚高，跨帧不可比；逐块三条件（基线有纹理+当前平坦+
                # 边缘骤降）已足够严格。
                lost_map = textured & flat_map & (blk_edge <= self._base_blk_edge * self.edge_drop_ratio)
                lost_ratio = float(lost_map.sum()) / float(n_text)
                if lost_ratio >= self.occlude_ratio:
                    reasons.append('edge_loss')

        metrics = dict(mean=mean, std=std, entropy=entropy, edge_density=edge_density,
                       gx_detail=gx_detail, struct_corr=struct_corr, sharp_frac=sharp_frac,
                       sharp_spread=sharp_spread, mono_ratio=mono_ratio, suspect=suspect,
                       dark_frac=dark_frac, clip_frac=clip_frac,
                       base_shift=base_shift, shift_corr=shift_corr,
                       shift_full_corr=shift_full_corr,
                       flat_ratio=flat_ratio, lost_ratio=lost_ratio,
                       reasons=reasons, flat_map=flat_map, lost_map=lost_map,
                       blk_edge=blk_edge, grad_map=grad_map)
        return bool(reasons), metrics

    def update_baseline(self, metrics):
        '''用一帧"确认无遮挡"的 metrics 更新场景基线（EMA）。'''
        a = self.baseline_alpha
        if self._base_blk_edge is None:
            self._base_blk_edge = metrics['blk_edge'].copy()
            self._base_grad = metrics['grad_map'].copy()
            self._base_edge = metrics['edge_density']
            self._base_flat = metrics['flat_ratio']
            self._base_mean = metrics['mean']
            self._base_gx = metrics['gx_detail']
            self._base_mono = metrics['mono_ratio']
        else:
            self._base_blk_edge += a * (metrics['blk_edge'] - self._base_blk_edge)
            self._base_grad += a * (metrics['grad_map'] - self._base_grad)
            self._base_edge += a * (metrics['edge_density'] - self._base_edge)
            self._base_flat += a * (metrics['flat_ratio'] - self._base_flat)
            self._base_mean += a * (metrics['mean'] - self._base_mean)
            self._base_gx += a * (metrics['gx_detail'] - self._base_gx)
            self._base_mono += a * (metrics['mono_ratio'] - self._base_mono)
        self._base_n += 1

    def reset_baseline(self):
        '''丢弃基线（自愈重学时用）。'''
        self._base_blk_edge = None
        self._base_grad = None
        self._base_edge = self._base_flat = self._base_mean = 0.0
        self._base_gx = self._base_mono = 0.0
        self._base_n = 0

    def save_baseline(self, path):
        '''基线落盘：进程重启后直接加载，不再裸预热 —— 防止"重启时正被遮挡 →
        遮挡画面被学成基线"（corr≈1，相对证据全失效）。原子替换写，断电不留半截文件。'''
        if self._base_blk_edge is None:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp.npz'
        np.savez(tmp, blk_edge=self._base_blk_edge, grad=self._base_grad,
                 scalars=np.array([self._base_edge, self._base_flat, self._base_mean,
                                   self._base_gx, self._base_mono,
                                   float(self._base_n)], np.float64))
        os.replace(tmp, path)

    def load_baseline(self, path):
        '''加载持久化基线；文件不存在/损坏/维度与当前参数不符时返回 False（照常裸预热）。'''
        try:
            with np.load(path) as z:
                blk, grad, sc = z['blk_edge'], z['grad'], z['scalars']
            if blk.shape != (self.grid, self.grid) or grad.shape != _GRAD_MAP_SIZE[::-1] \
                    or sc.size < 6:
                return False
            self._base_blk_edge = blk.astype(np.float32)
            self._base_grad = grad.astype(np.float32)
            (self._base_edge, self._base_flat, self._base_mean,
             self._base_gx, self._base_mono) = (float(v) for v in sc[:5])
            self._base_n = int(sc[5])
            return True
        except Exception:
            return False


class OcclusionMonitor(threading.Thread):
    '''遮挡监测线程：周期借帧 → 多帧投票/闪烁融合 → 报警（存图 + kafka 上报，同 base_model）。

    与引擎的耦合只有 offer_frame（由 on_new_sample 的 frame_tap 调用）：
    未处于检查窗口时 offer_frame 一次 Event 判断即返回，不拷贝、不加锁。'''

    def __init__(self, occl_cfg):
        super().__init__(daemon=True, name='occlusion')
        c = dict(occl_cfg or {})
        self.check_interval = max(10.0, float(c.get('check_interval', 10)))   # 检查周期，默认 10 秒
        self.frames_per_check = max(1, int(c.get('frames_per_check', 5)))      # 每次检查采样帧数
        self.frame_gap = max(0.0, float(c.get('frame_gap', 0.5)))              # 采样帧间隔(秒)
        self.min_vote_ratio = min(1.0, max(0.5, float(c.get('min_vote_ratio', 0.8))))  # 判遮挡票数占比
        self.alarm_interval = float(c.get('alarm_interval', self.check_interval))      # 报警最小间隔
        self.grab_timeout = float(c.get('grab_timeout', 5.0))                  # 单帧借帧超时(秒)
        self.flicker_delta = float(c.get('flicker_delta', 30.0))               # 证据④：判"补光灯振荡"
                                                                               # 所需的帧间亮度摆幅
        # 转动抑制 b)：相邻采样帧梯度结构图相位相关的全局平移 ≥ motion_shift（梯度图格，
        # 图宽 64 格 ≈ 1 格 1.5% 画幅）判"正在转动"跳过本轮；≤0 禁用。连续跳过超过
        # motion_max_skip 轮不再跳过（防风吹飘动的遮挡物借全局位移永久逃逸检测）。
        self.motion_shift = float(c.get('motion_shift', 1.5))
        self.motion_max_skip = max(1, int(c.get('motion_max_skip', 3)))
        self._moving_run = 0
        self._hann = None           # phaseCorrelate 汉宁窗（首次用时创建）
        # 无基线场景（开机即遮挡 / 场景天然平坦黑暗，二者无法区分）的报警节流，防无限刷报警
        self.nobase_free_alarms = max(0, int(c.get('nobase_free_alarms', 3)))  # 先照常报警的次数
        self.nobase_backoff = float(c.get('nobase_backoff', 3600))             # 之后的退避间隔(秒)
        self.identity = c                                                      # 上报身份字段来源
        self.conf_name = c.get('conf_name') or 'occlusion'
        self.detector = OcclusionDetector(**{k: c[k] for k in _DETECTOR_KEYS if k in c})
        # 自愈：连续该轮数仅命中 scene_replaced（画面健康、仅结构与基线不符 = 视角被调整
        # 或基线被污染后遮挡已移除）→ 重建基线；0=禁用。期间每轮都已报警提醒过运维。
        self.relearn_checks = max(0, int(c.get('relearn_checks', 1)))
        self._replaced_run = 0
        # 基线持久化文件（与报警图同根目录）；重启加载成功则跳过预热
        self.baseline_path = c.get('baseline_path') or os.path.join(
            _OUTPUT_ROOT, self.conf_name, 'baseline.npz')
        if self.detector.load_baseline(self.baseline_path):
            logger.info('[遮挡检测][%s] 已加载持久化基线（累计 %d 次更新），跳过预热',
                        self.conf_name, self.detector._base_n)
        self._want = threading.Event()      # 置位 = 监测线程正在索帧
        self._got = threading.Event()       # 置位 = 已拷到一帧
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()
        self._last_alarm = 0.0
        self._nobase_alarms = 0     # 已发出的"无基线"报警计数（节流用）
        self._occ_since = None      # 本次遮挡 episode 的开始时刻（上报始末时间节点用，
                                    # 同人员计数模块的会话始末语义）；恢复正常后清零

    # ---- 引擎侧接口（GStreamer 取流线程调用，必须极轻） ----
    def offer_frame(self, image_bgr):
        '''取流回调喂帧：仅在监测线程索帧时拷贝一份（每 5 分钟共 frames_per_check 次），
        平时只有一次 Event 判断的开销。'''
        if not self._want.is_set():
            return
        self._want.clear()
        with self._lock:
            self._frame = image_bgr.copy()   # 必须拷贝：原帧随后会被聚合线程画框/叠加污染
        self._got.set()

    def stop(self):
        '''请求监测线程退出（daemon 线程，进程退出也会自动结束）。'''
        self._stop.set()

    # ---- 监测线程内部 ----
    def _grab_frame(self):
        '''向取流回调索一帧，超时（拉流中断/重连中）返回 None。'''
        self._got.clear()
        self._want.set()
        if not self._got.wait(self.grab_timeout):
            self._want.clear()
            return None
        with self._lock:
            f, self._frame = self._frame, None
        return f

    def run(self):
        logger.info('[遮挡检测][%s] 启动：每 %.0fs 检查一次，每次采 %d 帧投票(占比≥%.0f%%判遮挡)，'
                    '报警间隔≥%.0fs', self.conf_name, self.check_interval, self.frames_per_check,
                    self.min_vote_ratio * 100, self.alarm_interval)
        while not self._stop.wait(self.check_interval):
            try:
                self._check_once()
            except Exception:
                logger.exception('[遮挡检测][%s] 本轮检查异常（忽略，下轮继续）', self.conf_name)

    def _sample_frames(self):
        '''采样 frames_per_check 帧（间隔 frame_gap）；停机中返回 None，全部超时返回 []。'''
        frames = []
        for i in range(self.frames_per_check):
            f = self._grab_frame()
            if f is not None:
                frames.append(f)
            if i + 1 < self.frames_per_check and self._stop.wait(self.frame_gap):
                return None
        return frames

    # ---- 视频质量检测钩子（video_quality.VideoQualityMonitor 覆写；基类保持纯遮挡行为） ----
    def _on_no_frames(self):
        '''整轮借帧全部超时（拉流中断/重连中）。子类在此累计"视频丢失"证据。'''
        logger.warning('[遮挡检测][%s] 借帧超时（拉流可能中断/重连中），跳过本轮', self.conf_name)

    def _on_frames_ok(self):
        '''本轮成功借到帧（视频丢失状态解除点）。'''

    def _on_view_changed(self, frame, metrics):
        '''转动抑制 c) 命中：场景与基线不符但画面在焦（判为视角变化而非遮挡）。
        子类在此上报"摄像仪挪动"。'''

    def _quality_round(self, frames, analyzed, pairs, moving):
        '''每轮采样帧分析完成后调用（先于遮挡投票/转动跳过），子类做画质类检测。
        pairs: _pair_shifts 的结果 [(i_from, i_to, dx, dy)]（梯度图格，仅含有结构且
        相关峰可信的帧对；i_to-i_from>1 表示中间隔了被过滤的无结构帧）。'''

    def _check_once(self):
        '''一轮检查：采样多帧 → 逐帧分析 → 投票 + 检查级闪烁融合（证据④）→ 报警/更新基线。'''
        frames = self._sample_frames()
        if frames is None:
            return
        # 借帧结果钩子：子类异常不许打断遮挡主流程（尤其 _on_frames_ok 位于分析之前，
        # 裸调用时子类系统性异常会让整轮遮挡分析被 run() 的 except 静默吞掉）
        if not frames:
            try:
                self._on_no_frames()
            except Exception:
                logger.exception('[视频质量][%s] 视频丢失钩子异常（忽略）', self.conf_name)
            return
        try:
            self._on_frames_ok()
        except Exception:
            logger.exception('[视频质量][%s] 借帧恢复钩子异常（忽略）', self.conf_name)

        analyzed = []       # [(frame, occluded, metrics)]，按采样顺序
        for f in frames:
            occluded, m = self.detector.analyze(f)
            analyzed.append((f, occluded, m))

        # 转动抑制 b)：摄像头正在转动（云台巡航/人为调整）时采样帧互相错位且有运动模糊，
        # 逐帧证据不可信 —— 本轮跳过（不判遮挡、不更新基线）。连续跳过有上限。
        pairs = self._pair_shifts(analyzed)
        shift = max((math.hypot(dx, dy) for _, _, dx, dy in pairs), default=0.0)
        moving = self.motion_shift > 0 and shift >= self.motion_shift

        # 视频质量检测（子类实现）：与遮挡判定互不阻塞，异常只记日志
        try:
            self._quality_round(frames, analyzed, pairs, moving)
        except Exception:
            logger.exception('[视频质量][%s] 本轮质量检测异常（忽略，不影响遮挡判定）', self.conf_name)
        if moving:
            self._moving_run += 1
            if self._moving_run <= self.motion_max_skip:
                logger.info('[遮挡检测][%s] 采样帧间全局位移 %.1f 格（摄像头转动中），'
                            '跳过本轮(%d/%d)', self.conf_name, shift,
                            self._moving_run, self.motion_max_skip)
                return
            logger.warning('[遮挡检测][%s] 连续 %d 轮画面全局位移（云台持续巡航或遮挡物'
                           '飘动），不再跳过、照常判定', self.conf_name, self._moving_run)
        else:
            self._moving_run = 0

        votes = sum(1 for _, o, _ in analyzed if o)
        need = max(1, int(math.ceil(self.min_vote_ratio * len(analyzed))))

        # 证据④（检查级）：补光灯振荡 + 全程异常。套袋后光感元件反复开关补光灯，采样帧亮度
        # 大幅摆动；亮帧或被逐帧证据判为遮挡（光斑→②，编织袋纹理→⑤），或全无结构；暗帧近黑
        # 无结构。逐帧投票此时可能亮暗各占一半票数而漏检，这里跨帧融合兜底：
        # "异常帧"=（逐帧判遮挡 或 无结构 gx_detail≤detail_thresh 或 近全黑）。
        # 正常场景灯光闪烁时亮帧既不判遮挡、纹理也仍在（gx_detail 高）→ 凑不够票，不误报；
        # 基线场景本身无结构则不启用。
        det = self.detector
        means = [m['mean'] for _, _, m in analyzed]
        swing = max(means) - min(means)
        abnormal = sum(1 for _, o, m in analyzed
                       if o or m['gx_detail'] <= det.detail_thresh or m['mean'] < 8.0)
        base_ok = det._base_blk_edge is not None and det._base_n >= det.baseline_warmup
        flicker_occ = (len(analyzed) >= 3 and swing >= self.flicker_delta
                       and abnormal >= need
                       and (not base_ok or det._base_gx > 2.0 * det.detail_thresh))

        is_occluded = votes >= need or flicker_occ
        # 报警用帧：优先取逐帧判遮挡的帧；纯证据④命中时取最亮一帧（遮挡物看得最清），
        # 并在其 reasons 里补上 'flicker' 便于日志/排查区分
        occ_hit = None
        clean_metrics = None
        for f, o, m in analyzed:
            if o:
                occ_hit = (f, m)
            else:
                clean_metrics = m
        if is_occluded and occ_hit is None:
            fb, _, mb = max(analyzed, key=lambda t: t[2]['mean'])
            occ_hit = (fb, mb)
        if flicker_occ and occ_hit is not None:
            occ_hit[1]['reasons'] = list(occ_hit[1]['reasons']) + ['flicker']

        m = (occ_hit[1] if is_occluded and occ_hit else analyzed[-1][2])
        logger.info('[遮挡检测][%s] 投票 %d/%d(需%d) 亮度摆幅=%.1f 异常帧=%d → %s | '
                    'mean=%.1f std=%.1f entropy=%.2f edge=%.4f gx=%.4f corr=%.2f '
                    'sharp=%.4f spread=%.2f mono=%.2f flat=%.2f lost=%.2f 证据=%s',
                    self.conf_name, votes, len(analyzed), need, swing, abnormal,
                    '遮挡' if is_occluded else '正常',
                    m['mean'], m['std'], m['entropy'], m['edge_density'], m['gx_detail'],
                    m['struct_corr'], m['sharp_frac'], m['sharp_spread'], m['mono_ratio'],
                    m['flat_ratio'], m['lost_ratio'], m['reasons'])

        if not is_occluded:
            self._replaced_run = 0
            self._occ_since = None      # 遮挡解除：本次 episode 结束，始末时间重新计
            # 只学"确认无遮挡"的帧；亮度剧烈波动（疑似补光灯振荡/日夜切换瞬间）的窗口
            # 采到的帧不可信，跳过本轮基线更新，防垃圾帧污染基线。
            # suspect（大面积单色+边缘极低=证据⑥色彩特征）帧即便未达报警条件也不学：
            # 一旦漏检期间把遮挡画面 EMA 进基线，corr→1、base_mono 抬高，
            # 相对证据③⑤与⑥门控会被反向锁死（现场实测过的事故模式）。
            # moving（转动跳过超上限后落到这里）的帧同样错位/模糊，不学。
            if clean_metrics is not None and swing < self.flicker_delta and not moving:
                if clean_metrics.get('suspect'):
                    logger.info('[遮挡检测][%s] 画面大面积单色且边缘极低（疑似遮挡未达报警条件），'
                                '跳过本轮基线更新', self.conf_name)
                else:
                    self.detector.update_baseline(clean_metrics)
                    try:
                        self.detector.save_baseline(self.baseline_path)
                    except Exception:
                        logger.exception('[遮挡检测][%s] 基线持久化失败（不影响检测）', self.conf_name)
            return

        # 自愈：仅 scene_replaced 命中（画面锐度/结构健康，只是与基线不符）连续达到
        # relearn_checks 轮 → 判为视角被调整或基线被污染后遮挡已移除，重建基线重学。
        # 真遮挡（袋子/光斑/全黑）总会伴随其它证据，不会走到这里。
        all_reasons = set()
        for _, o, mm in analyzed:
            if o:
                all_reasons.update(mm['reasons'])
        if flicker_occ:
            all_reasons.add('flicker')
        if all_reasons == {'scene_replaced'}:
            self._replaced_run += 1
            # 转动抑制 c) 的在焦判定：画面确认在焦（sharp_frac 与 sharp_spread 双达标 =
            # 真实远景，贴近镜头的纹理遮挡物必然失焦、spread 推不过阈值）且非单色可疑帧
            # → 视角变化而非遮挡。relearn_checks=0（自愈禁用）时不抑制，否则报警被永久压住。
            mm = occ_hit[1]
            in_focus = bool(self.relearn_checks) and not mm.get('suspect') \
                and mm['sharp_frac'] > det.sharp_thresh \
                and mm['sharp_spread'] > det.spread_thresh
            # 视频质量钩子：子类在此上报"摄像仪挪动"（基类无动作，保持原静默行为）。
            # 必须在下方自愈重建分支之前调用 —— 默认 relearn_checks=1 时自愈当轮即
            # return，钩子放其后将永不可达（审查发现的死路径）。
            if in_focus:
                try:
                    self._on_view_changed(occ_hit[0], mm)
                except Exception:
                    logger.exception('[视频质量][%s] 挪动报警钩子异常（忽略）', self.conf_name)
            # 自愈重建只对"画面在焦"的场景替换开放：在焦 = 真实远景（视角被调整，或基线
            # 污染后遮挡已移除），静默重建合理。失焦的场景替换 = 疑似纹理遮挡物（编织袋等
            # 贴近镜头必然失焦），若也走自愈会形成最重的漏检口子（审查核实，默认
            # relearn_checks=1 时首轮即重建基线、永不报警，且 ~30s 后遮挡物本身被 EMA
            # 学成基线 → ⑤永久失效）—— 故失焦时不自愈不静默，落到下方遮挡报警；
            # is_occluded=True 的轮次不更新基线，遮挡物不会被学入。
            if self.relearn_checks and self._replaced_run >= self.relearn_checks and in_focus:
                logger.warning('[遮挡检测][%s] 连续 %d 轮仅命中 scene_replaced 且画面在焦：判定为'
                               '摄像头视角被调整或旧基线失效，重建基线重学（如确系遮挡请人工处理）',
                               self.conf_name, self._replaced_run)
                self.detector.reset_baseline()
                self._replaced_run = 0
                try:
                    os.remove(self.baseline_path)
                except OSError:
                    pass
                return
            if in_focus:
                logger.info('[遮挡检测][%s] 场景与基线不符但画面在焦(sharp=%.4f spread=%.2f)：'
                            '判为摄像头转动/视角调整，不按遮挡报警（%d/%d 轮后重建基线）',
                            self.conf_name, mm['sharp_frac'], mm['sharp_spread'],
                            self._replaced_run, self.relearn_checks)
                return
        else:
            self._replaced_run = 0

        now = time.time()
        # 报警开始时间节点：首轮判定遮挡的时刻。跨报警间隔/多轮持续遮挡保持不变，
        # 使持续遮挡的每次上报都携带同一 episode 起点（同人员计数的会话开始时间语义）。
        if self._occ_since is None:
            self._occ_since = now
        gate = self._effective_alarm_interval()
        if now - self._last_alarm < gate:
            logger.info('[遮挡检测][%s] 仍处报警间隔内(%.0fs)，本轮不重复上报', self.conf_name, gate)
            return
        self._last_alarm = now
        if self.detector._base_n < self.detector.baseline_warmup:
            self._nobase_alarms += 1
        self._alarm(occ_hit[0], occ_hit[1])

    def _pair_shifts(self, analyzed):
        '''转动抑制 b) 与画面抖动检测共用的测量：相邻"有结构"采样帧的梯度结构图做相位
        相关，返回各帧对的全局平移向量 [(i_from, i_to, dx, dy)]（i_from/i_to = 帧对首尾
        帧在 analyzed 里的下标 —— 无结构帧被跳过时帧对可跨下标间隙，抖动检测据此判别
        位移向量是否真正时间相邻；dx/dy 单位为梯度图格）。摄像头转动/抖动时整幅结构一起
        平移、位移显著；行人/车辆只占画面局部，相关峰仍在 0 附近。只用双方都有结构
        （gx_detail 达标）的帧对 —— 全黑/纯光斑帧的相位相关是噪声，不能让遮挡帧借它
        伪造"转动"逃逸检测。response 门控：真转动是"同一场景整体平移"，相关峰强
        （实测≥0.7，含运动模糊）；两幅不相关画面峰值≈0，此时 dx/dy 是噪声。'''
        det = self.detector
        pairs = []
        prev = None
        prev_i = -1
        for i, (_, _, m) in enumerate(analyzed):
            if m['gx_detail'] < det.detail_thresh:
                continue
            if prev is not None:
                if self._hann is None:
                    self._hann = cv2.createHanningWindow(_GRAD_MAP_SIZE, cv2.CV_32F)
                (dx, dy), resp = cv2.phaseCorrelate(prev.astype(np.float32),
                                                    m['grad_map'].astype(np.float32), self._hann)
                if resp >= 0.3:
                    pairs.append((prev_i, i, float(dx), float(dy)))
            prev = m['grad_map']
            prev_i = i
        return pairs

    def _effective_alarm_interval(self):
        '''报警节流间隔：场景曾确认无遮挡（有干净基线）→ 按 alarm_interval（默认每轮检查都可报，
        持续遮挡持续报警）；从未建立过基线（开机即遮挡 或 场景天然平坦/黑暗，二者物理上无法
        区分）→ 先照常报 nobase_free_alarms 次提醒运维，之后退避到 nobase_backoff 一次，
        防止对天然平坦场景每 5 分钟无限刷报警。'''
        d = self.detector
        if d._base_n >= d.baseline_warmup:
            return self.alarm_interval
        if self._nobase_alarms < self.nobase_free_alarms:
            return self.alarm_interval
        return max(self.alarm_interval, self.nobase_backoff)

    # ---- 报警：存图 + 上报（已在监测线程内，不占引擎热路径） ----
    def _alarm(self, frame, metrics):
        """ 报警：存图 + 上报（发送方式同人员计数模块 counting_upload_worker） """
        # 报警时刻一次取定：报警视频文件名与上报的始末时间共用同一时刻，保证平台记录与
        # 视频文件名逐秒一致（旧版 trigger 在前、存图后才取 now()，可差 1~2s）。
        # 遮挡属视频质量报警：分析类型 03；返回的视频 URL 随上报进 warning_video。
        alarm_ts = time.time()
        video_url = alarm_video.trigger(self.conf_name, alarm_ts=alarm_ts, analysis_type='03')
        ori_paths = []
        try:
            _, ori_paths = self._save_alarm_images(frame, metrics)
        except Exception:
            logger.exception('[遮挡检测][%s] 报警图保存失败（仍尝试上报）', self.conf_name)
        ok = self._upload_alarm(ALARM_TEXT, ori_paths, alarm_ts, video_url,
                                analysis_case=ALARM_CASE)
        if not ok:
            self._last_alarm = 0.0    # 上报失败不吃掉报警间隔，下轮检查若仍遮挡立即重报
        return ok

    def _upload_alarm(self, alarm_text, ori_paths, alarm_ts, video_url, analysis_case=None):
        '''报警上报（算法日志 + kafka），发送方式同人员计数模块 counting_upload_worker。
        视频质量各类报警（video_quality）复用：仅报警文本/图不同，通道完全一致。
        返回 kafka 上报是否成功（失败由调用方决定是否重置报警间隔重试）。'''
        c = self.identity
        try:
            data_send.insert_alg_log(ip_address='None', Level='WARNING',
                                     message='%s%s' % (self.conf_name, alarm_text),
                                     alg_name=self.conf_name)
        except Exception:
            logger.exception('[遮挡检测][%s] 算法日志写入失败', self.conf_name)
        # 报警始末时间节点：现场暂定"开始=结束=报警时刻 alarm_ts"（平台反馈遮挡报警缺开始
        # 时间，先按同值上报；取 alarm_ts 而非 now() 是为与报警视频文件名逐秒一致）；
        # 遮挡 episode 实际起点 _occ_since 仍写本地日志供排查，
        # 平台侧需要真实起点时把 start_str 换回 _occ_since 即可
        end_str = datetime.fromtimestamp(alarm_ts).strftime('%Y-%m-%d %H:%M:%S')
        start_str = end_str
        try:
            # 与人员计数模块相同的发送方式：原图 URL 同时走 carousel/ori 两个字段，
            # warning_message 携带报警文本；result_alarm=2 标识视频质量类报警。
            # 平台把 result_count_time 读作报警开始时间（start_time 字段平台不读，
            # 仍一并携带），故开始时间必须走 result_count_time 传
            data_send.upload_hwj(
                Algorithm_conf_id=c.get('conf_id'), res_type=c.get('res_type'),
                Equipment_id=c.get('Equipment_id'), Mine_id=c.get('Mine_id'), mine_code=c.get('mine_code'),
                carousel_images_list=ori_paths, ori_images_list=ori_paths,
                result_count=None, Entering_num=None, Exiting_num=None,
                result_count_time=start_str,
                template_type_id=c.get('template_config_type_id'), template_id=c.get('template_id'),
                start_time=start_str, res_time=end_str,
                warning_message=alarm_text, conf_name=self.conf_name,
                equipment_name=c.get('equipment_name'), equipment_ip=c.get('equipment_ip'),
                Algorithm_library_id=c.get('Algorithm_library_id'),
                result_alarm=2, warning_video=video_url,
                analysis_case=analysis_case)
            logger.info('[遮挡检测][%s] 报警已上报 kafka：%s 开始=%s 结束=%s（episode 实际'
                        '起点=%s）原图=%s', self.conf_name, alarm_text, start_str, end_str,
                        datetime.fromtimestamp(self._occ_since).strftime('%Y-%m-%d %H:%M:%S')
                        if self._occ_since else '无', ori_paths)
            return True
        except Exception:
            logger.exception('[遮挡检测][%s] 报警上报失败（%s）', self.conf_name, alarm_text)
            return False

    def _save_alarm_images(self, frame, metrics):
        '''存报警图（遮挡块标注，不叠加文字，仅本地留档排查）与原图，
        返回 (报警图URL列表, 原图URL列表)。URL 主机同人员计数模块
        counting_upload_worker：算力盒本机 cm.localhost_ip（图存在盒子上，
        非设备 equipment_ip / 平台侧 upload_ip）。'''
        host = cm.localhost_ip
        port = int(cm.upload_port)
        out_dir = os.path.join(_OUTPUT_ROOT, self.conf_name, 'images')
        os.makedirs(out_dir, exist_ok=True)
        # 滚动清理旧报警图（监测线程内、非热路径；内部每小时至多真正扫描一次）——
        # 持续遮挡按报警间隔持续存图，无清理会无限增长
        try:
            alarm_video.prune_dir(out_dir, ('.jpg',))
        except Exception:
            pass
        marked = frame.copy()
        self._draw_overlay(marked, metrics)
        ts = time.strftime('%Y-%m-%d_%H-%M-%S')
        alarm_path = os.path.join(out_dir, 'alarm_%s.jpg' % ts)
        ori_path = os.path.join(out_dir, 'ori_%s.jpg' % ts)
        # cv2.imwrite 失败不抛异常、只返回 False（路径/权限/磁盘满等）——必须检查返回值
        if not cv2.imwrite(alarm_path, marked):
            logger.error('[遮挡检测][%s] 报警图写入失败(imwrite=False): %s', self.conf_name, alarm_path)
        else:
            logger.info('[遮挡检测][%s] 报警图已保存: %s', self.conf_name, alarm_path)
        if not cv2.imwrite(ori_path, frame):
            logger.error('[遮挡检测][%s] 原图写入失败(imwrite=False): %s', self.conf_name, ori_path)
        return (['http://%s:%d%s' % (host, port, alarm_path)],
                ['http://%s:%d%s' % (host, port, ori_path)])

    def _draw_overlay(self, image, metrics):
        '''报警图标注：命中的遮挡块半透明标红（作用同 base_model 的报警画框，不叠加文字）；
        全图遮挡/证据未落到具体块时画整幅红色描边。'''
        h, w = image.shape[:2]
        g = self.detector.grid
        reasons = metrics['reasons']
        if 'edge_loss' in reasons:
            mark = metrics['lost_map']
        elif 'flat_collapse' in reasons:
            mark = metrics['flat_map']
        else:
            # blur_mono/scene_replaced/blackout/whiteout/flicker 都是全画面证据，
            # flat_map 此时只是零散平坦块、不代表遮挡范围 → 画整幅红色描边
            mark = None
        if mark is None or not mark.any():
            cv2.rectangle(image, (0, 0), (w - 1, h - 1), (0, 0, 255), max(2, h // 200))
            return
        overlay = image.copy()
        for i in range(g):
            for j in range(g):
                if mark[i, j]:
                    cv2.rectangle(overlay, (j * w // g, i * h // g),
                                  ((j + 1) * w // g, (i + 1) * h // g), (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.25, image, 0.75, 0, dst=image)


def occlusion_cfg_from_row(row, **overrides):
    '''从一条算法配置行（data_receive.get_data() 的 row）提取遮挡报警所需身份字段，
    生成引擎 cfg["occlusion"]。同一路流多任务时用第一个任务的身份上报（同一摄像头）。
    overrides 可覆盖检测/周期参数，如 check_interval=300、occlude_ratio=0.5。'''
    c = dict(
        conf_id=row.get('Conf_id'),
        res_type=row.get('res_type'),
        Equipment_id=row.get('Equipment_id'),
        Mine_id=row.get('Mine_id'),
        mine_code=row.get('mine_code'),
        template_config_type_id=row.get('template_config_type_id'),
        template_id=row.get('template_id'),
        conf_name=row.get('conf_name'),
        equipment_name=row.get('equipment_name'),
        equipment_ip=row.get('equipment_ip'),
        Algorithm_library_id=row.get('Algorithm_library_id'),
    )
    c.update(overrides)
    return c
