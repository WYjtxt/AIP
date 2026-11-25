# -*- coding: utf-8 -*-
'''
video_quality.py —— 视频质量异常检测（在摄像头遮挡检测之上扩展其余 8 类画质异常）

在 camera_occlusion.OcclusionMonitor（画面遮挡，多证据融合+场景基线）基础上继承扩展，
共用同一条借帧链路（frame_tap）、同一轮采样帧与逐帧 metrics，新增开销仅为每轮几次
标量比较 + 两张 160×90 小图差分（冻结检测），不另拉流、不占推理热路径。

九类视频质量异常与判据：
  画面遮挡    —— 基类 camera_occlusion 原有六路证据，行为完全不变。
  摄像仪挪动  —— 两路：①大幅挪动/转动 = 基类"转动抑制 c)"命中（场景结构被整体替换但
                画面在焦，_on_view_changed 钩子），原逻辑只静默重建基线，现同时上报；
                ②小幅挪动 = 逐帧 base_shift（梯度结构图对基线中央模板匹配的最优平移，
                无条件计算）≥ move_cells 格且平移后模板相关 shift_corr ≥ move_corr
                （位移大但相关高 = 同一场景被平移 = 支架被碰/被扳动，遮挡物替换场景
                怎么平移都对不上），且按该位移对齐后全帧重叠区 NCC shift_full_corr ≥
                move_full_corr —— 真挪动是整幅场景平移、重叠区相关依然高；大面积近景
                前景物（有人站到镜头前挡住半边）只是把中央模板匹配挤到别处，位移解释
                不了整幅画面（现场实测的误报模式）。连续 move_checks 轮成立才报；
                转动中(moving)本轮位移量不可信，跳过。
  画面过暗    —— 帧均值 < dark_mean 且暗像素(<50)占比 ≥ dark_frac，按轮投票 +
                连续 dark_checks 轮（防灯光瞬断误报）。本轮已命中遮挡"全黑(blackout)"
                证据时让位于遮挡报警（镜头罩死优先按遮挡处理）。
  画面过曝    —— 饱和像素(≥250)占比 ≥ overexpose_frac，按轮投票 + 连续
                overexpose_checks 轮。已命中遮挡"全白(whiteout)"时让位。
  图像模糊    —— 锐度对自身基线塌缩：sharp_frac 跌到基线的 blur_ratio 以下且
                sharp_spread 跌到基线的 blur_spread_ratio 以下（分析图 4 倍降采样对模糊
                有"变相锐化"效应，覆盖度跌幅天然小于占比跌幅，故两阈值分设），且场景
                结构仍与基线相关（struct_corr ≥ blur_corr，区别于遮挡的"结构被替换"）、
                画面仍有结构（gx_detail 达标，区别于全黑/光斑）。锐度基线为独立 EMA
                （只在"干净轮"更新：无遮挡证据、无质量异常、非转动、亮度稳定），随基线
                记录场景亮度：本轮亮度与基线亮度偏差超过 blur_mean_jump（日夜切换/红外
                启停/灯光开合 = 照明制式变化，锐度不可比）时整个锐度基线重置重预热
                （约 1 分钟），绝不拿白天基线判夜间红外画面 —— 沿用旧基线会整夜误报，
                且命中轮不学基线、死锁永不自愈（对抗审查发现的缺陷）。落盘
                blur_baseline.npz 防重启期间被糊帧污染。需预热 blur_warmup 轮 +
                基线场景本身足够锐利才启用（天然低纹理场景不判）。
  画面冻结    —— 跨检查窗口帧内容逐位不变：本轮末帧与上一轮存帧在全分辨率灰度上
                "变化像素(|Δ|>1)占比" ≤ freeze_px_frac（默认 0.01%），且本轮首末帧同样
                不变，连续 freeze_checks 轮（默认约 1 分钟）。真冻结是同一解码缓冲重复、
                逐位相同；活流即使场景完全静止也有传感器噪声/OSD 时钟走秒，变化像素占比
                远超阈值（缩图均差判据会把噪声平均掉造成误判，故必须全分辨率数变化像素）。
                近全黑帧不参与（黑帧天然全同，由遮挡/过暗负责）。
  视频丢失    —— 整轮借帧全部超时（拉流中断且引擎重连未成，_on_no_frames 钩子）连续
                loss_checks 轮。报警不带图（无帧可存）；报警视频仅本次断流 episode 首报
                触发，且把片段起点传为断流起始时刻 —— 环形缓冲里只有断流前旧帧，按默认
                窗口（报警时刻±5s）必然取不到帧、上报的 URL 是死链（审查核实），传断流
                起点后片段=断流前最后几秒画面（恰是排查素材）；重复报不再触发视频
                （缓冲无新帧，反复保存同段旧画面纯耗磁盘）。恢复借帧时打恢复日志。
  画面抖动    —— 同轮相邻采样帧（间隔 frame_gap≈0.5s）梯度结构图相位相关的全局位移：
                ≥ jitter_shift 格的显著位移帧对 ≥ jitter_pairs 对，且存在方向反转
                （相邻位移向量夹角 > 120°，风吹/支架松动的往复震荡），连续 jitter_checks
                轮。云台单向巡航方向一致、无反转，不误报（由"转动抑制"跳过机制处理）。
  分辨率异常  —— 引擎 raw_size_tap 上报解码原始尺寸（缩放到配置尺寸之前）：与平台配置
                conf_img_resolution 不符（容忍 90° 旋转的宽高互换）或中途变化，连续
                res_checks 轮。tap 帧本身已被引擎缩放到配置尺寸，故必须由引擎在
                缩放前报告（见 rtsp_infer_push pre 线程）。

报警通道与遮挡完全一致（_upload_alarm：算法日志 + kafka upload_hwj，warning_message
携带各自报警文本，result_alarm=2、报警视频分析类型 03=视频质量）；各类报警独立节流
（*_alarm_interval），且同一异常 episode（条件持续成立期间）前 quality_free_alarms 次
按正常间隔报、之后退避到 quality_backoff 一次 —— 过暗/冻结/丢失等故障可整夜/数天持续，
不退避会刷爆平台并按节流间隔持续产出报警视频占满磁盘（对抗审查发现）；条件解除后
episode 归零。上报失败不吃间隔、下轮命中立即重试。报警图存
results/quality/result/<conf_name>/images（整幅红框标注 + 原图，同遮挡口径经
cm.localhost_ip 上 URL），与报警视频/遮挡报警图目录一并按 alarm_video.prune_dir 滚动
清理（默认保留 7 天，ALARM_VIDEO_KEEP_DAYS 可调）。质量类上报走独立异步线程
（kafka/DB 最坏可阻塞 ~20s，不许拖慢同轮的遮挡投票/基线更新）；遮挡报警本身也在本类
中加了同样的 episode 退避（alarm_interval 默认 10s，持续遮挡不退避会每小时产出
~3.6GB 报警视频占满磁盘），检测与前几次报警行为不变。

接入方式（见 model_start.stream_worker / rtsp_infer_push.run）：
    cfg['occlusion'] = video_quality.quality_cfg_from_row(rows[0])
    rtsp_infer_push.run(cfg)   # 引擎自动创建 VideoQualityMonitor（含遮挡全部原有行为）
cfg['occlusion'] 可覆盖所有基类遮挡参数与本模块 *_enable / 阈值 / *_checks /
*_alarm_interval 参数；某类检测不需要时置 <type>_enable=False（type 取
move/dark/overexpose/blur/freeze/loss/jitter/resolution）。
'''
import os
import math
import time
import queue
import logging
import threading

import cv2
import numpy as np

from config import common as cm
from templates import alarm_video, camera_occlusion

logger = logging.getLogger('rtsp_infer_push')

# 各类质量异常的报警文本（与遮挡"疑似存在视频遮挡"同一句式；warning_message +
# 本地算法日志共用，平台按文本区分类型）
ALARM_TEXTS = {
    'move':       '疑似存在摄像仪挪动',
    'dark':       '疑似存在画面过暗',
    'overexpose': '疑似存在画面过曝',
    'blur':       '疑似存在图像模糊',
    'freeze':     '疑似存在画面冻结',
    'loss':       '疑似存在视频丢失',
    'jitter':     '疑似存在画面抖动',
    'resolution': '疑似存在分辨率异常',
}

# 视频质量异常编码（平台 t_algorithm_result.analysis_case；遮挡 0001 见
# camera_occlusion.ALARM_CASE，随基类 _alarm 上报）
ALARM_CASES = {
    'move':       '0002',
    'dark':       '0003',
    'overexpose': '0004',
    'blur':       '0005',
    'freeze':     '0006',
    'loss':       '0007',
    'jitter':     '0008',
    'resolution': '0009',
}

# 报警图输出根目录（与遮挡 results/occlusion/result/<conf>/images 同风格）
_OUTPUT_ROOT = '/data/AIGO/outputs/quality/result'


def _parse_resolution(text):
    '''"1920x1080"/"1920*1080" → (1920, 1080)；解析失败返回 None（不启用配置比对）。'''
    try:
        s = str(text or '').lower().replace('*', 'x').replace('×', 'x').strip()
        w, h = s.split('x')
        w, h = int(w), int(h)
        return (w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


class VideoQualityMonitor(camera_occlusion.OcclusionMonitor):
    '''视频质量监测线程：遮挡（基类原样）+ 8 类画质异常。

    与基类的全部交互走四个钩子（_on_no_frames/_on_frames_ok/_on_view_changed/
    _quality_round）与引擎新增的 offer_raw_size；不改动基类任何遮挡判定路径。'''

    def __init__(self, q_cfg):
        super().__init__(q_cfg)
        c = dict(q_cfg or {})
        # ---- 画面过暗 ----
        self.dark_mean = float(c.get('dark_mean', 40.0))          # 帧均值上限
        self.dark_frac = float(c.get('dark_frac', 0.85))          # 暗像素(<50)占比下限
        self.dark_checks = max(1, int(c.get('dark_checks', 3)))   # 连续命中轮数
        # ---- 画面过曝 ----
        self.overexpose_frac = float(c.get('overexpose_frac', 0.35))   # 饱和像素(≥250)占比下限
        self.overexpose_checks = max(1, int(c.get('overexpose_checks', 3)))
        # ---- 图像模糊 ----
        self.blur_ratio = float(c.get('blur_ratio', 0.45))        # sharp_frac 跌到基线该比例以下
        self.blur_spread_ratio = float(c.get('blur_spread_ratio', 0.7))  # sharp_spread 跌幅阈值
                                                                  # （降采样对模糊有变相锐化效应，
                                                                  # 覆盖度跌幅天然小于占比跌幅）
        self.blur_corr = float(c.get('blur_corr', 0.35))          # 结构仍与基线相关的下限
        self.blur_mean_jump = float(c.get('blur_mean_jump', 30.0))  # 本轮亮度与基线亮度的偏差上限，
                                                                  # 超过=照明制式变化→基线重置重预热
        self.blur_checks = max(1, int(c.get('blur_checks', 3)))
        self.blur_alpha = float(c.get('blur_alpha', 0.15))        # 锐度基线 EMA 步长
        self.blur_warmup = max(1, int(c.get('blur_warmup', 6)))   # 锐度基线预热轮数
        # ---- 画面冻结 ----
        self.freeze_px_frac = float(c.get('freeze_px_frac', 1e-4))  # 变化像素(|Δ|>1)占比上限
        self.freeze_checks = max(2, int(c.get('freeze_checks', 6)))
        # ---- 视频丢失 ----
        self.loss_checks = max(1, int(c.get('loss_checks', 2)))
        # ---- 画面抖动 ----
        self.jitter_shift = float(c.get('jitter_shift', 1.0))     # 显著位移阈值（梯度图格）
        self.jitter_pairs = max(1, int(c.get('jitter_pairs', 2)))  # 每轮所需显著位移帧对数
        self.jitter_checks = max(1, int(c.get('jitter_checks', 2)))
        # ---- 摄像仪挪动（小幅持续位移路径；大幅挪动走 _on_view_changed） ----
        self.move_cells = float(c.get('move_cells', 3.0))         # 位移阈值（梯度图格，64 格≈全宽）
        self.move_corr = float(c.get('move_corr', 0.5))           # 平移后模板相关下限（=同场景被移动）
        self.move_full_corr = float(c.get('move_full_corr', 0.65))  # 按位移对齐后全帧重叠区 NCC 下限：
                                                                  # 真挪动=整幅平移、重叠区相关高；
                                                                  # 有人在镜头前挡住半边只是模板被
                                                                  # 挤走，位移解释不了全幅（现场
                                                                  # 实测误报模式），此门必挡
        self.move_checks = max(1, int(c.get('move_checks', 3)))
        # ---- 分辨率异常 ----
        self.expect_resolution = _parse_resolution(c.get('expect_resolution'))
        self.res_checks = max(1, int(c.get('res_checks', 2)))
        # ---- 各类独立报警节流（秒）；上报失败不吃间隔 ----
        self.q_intervals = {
            'move':       float(c.get('move_alarm_interval', 600)),
            'dark':       float(c.get('dark_alarm_interval', 1800)),
            'overexpose': float(c.get('overexpose_alarm_interval', 1800)),
            'blur':       float(c.get('blur_alarm_interval', 1800)),
            'freeze':     float(c.get('freeze_alarm_interval', 600)),
            'loss':       float(c.get('loss_alarm_interval', 600)),
            'jitter':     float(c.get('jitter_alarm_interval', 1800)),
            'resolution': float(c.get('resolution_alarm_interval', 3600)),
        }
        # 同一异常 episode 的报警退避：条件持续成立时前 free 次按各类间隔报，之后退避。
        # 过暗（夜间关灯）/冻结/丢失（摄像头死机断线）可整夜或数天持续，不退避会刷爆
        # 平台报警且按节流间隔持续产出报警视频（~10MB/条）占满盒上磁盘。
        self.q_free_alarms = max(1, int(c.get('quality_free_alarms', 3)))
        self.q_backoff = float(c.get('quality_backoff', 14400))   # 退避间隔，默认 4 小时
        self.q_enabled = {t: bool(c.get(t + '_enable', True)) for t in ALARM_TEXTS}
        # ---- 运行状态 ----
        self._q_run = {t: 0 for t in ALARM_TEXTS}     # 各类连续命中轮数
        self._q_last = {t: 0.0 for t in ALARM_TEXTS}  # 各类上次报警时刻
        self._q_epi = {t: 0 for t in ALARM_TEXTS}     # 本次 episode 已发报警数（退避用）
        self._loss_run = 0
        self._loss_started = 0.0                      # 本次断流起始时刻（首报视频片段起点）
        self._loss_alarmed = False
        self._freeze_prev = None                      # 上一轮末帧的全分辨率灰度图
        # 锐度基线（独立于遮挡基线；只在"干净轮"更新并落盘，防糊帧污染；
        # _blur_mean 记录基线场景亮度，照明制式变化时整组重置重预热）
        self._blur_sharp = 0.0
        self._blur_spread = 0.0
        self._blur_mean = 0.0
        self._blur_n = 0
        self.blur_baseline_path = c.get('blur_baseline_path') or os.path.join(
            _OUTPUT_ROOT, self.conf_name, 'blur_baseline.npz')
        self._load_blur_baseline()
        # 引擎 raw_size_tap 报告的解码原始尺寸（缩放到配置尺寸之前）；引擎线程只在
        # 尺寸变化时调用一次，元组赋值原子，无需加锁
        self._raw_size = None
        self._raw_size_first = None
        # 遮挡报警的 episode 退避状态（见 _effective_alarm_interval 覆写）
        self._occ_alarms_epi = 0
        self._occ_epi_mark = None
        # 质量报警异步上报：kafka/DB 上报最坏可阻塞 ~20s，一轮最多 7 类同时命中；
        # 同步执行会把同轮的遮挡投票/报警/基线更新拖在后面（审查发现）。监测线程只做
        # 节流/存图/触发报警视频（均为快速本地操作），上报交独立线程；队列满即丢弃
        # 并回滚节流记录，绝不阻塞检测轮。
        self._q_queue = queue.Queue(maxsize=16)
        threading.Thread(target=self._q_upload_loop, name='quality-upload',
                         daemon=True).start()
        enabled = [t for t in ALARM_TEXTS if self.q_enabled[t]]
        logger.info('[视频质量][%s] 已启用检测: %s（+遮挡）；期望分辨率=%s',
                    self.conf_name, ','.join(enabled),
                    '%dx%d' % self.expect_resolution if self.expect_resolution else '未配置')

    # ---- 引擎侧接口（pre 线程仅在解码原始尺寸变化时调用，开销可忽略） ----
    def offer_raw_size(self, w, h):
        '''引擎报告解码原始帧尺寸（旋转/缩放到配置尺寸之前的真实流分辨率）。'''
        size = (int(w), int(h))
        if self._raw_size_first is None:
            self._raw_size_first = size
            logger.info('[视频质量][%s] 流原始分辨率 %dx%d', self.conf_name, w, h)
        elif size != self._raw_size:
            logger.warning('[视频质量][%s] 流分辨率发生变化: %s → %dx%d',
                           self.conf_name, '%dx%d' % self._raw_size, w, h)
        self._raw_size = size

    # ================= 基类钩子实现 =================
    def _on_no_frames(self):
        '''视频丢失：整轮借帧全部超时。引擎断流约 27s/轮（5 帧×5s 超时），连续
        loss_checks 轮 ≈ 1 分钟取不到帧才报，引擎正常重连（秒级）不会触发。
        报警视频仅首报触发（片段起点=断流起始，取缓冲里断流前最后几秒画面）。'''
        super()._on_no_frames()
        if self._loss_run == 0:
            self._loss_started = time.time()
        self._loss_run += 1
        if not self.q_enabled['loss']:
            return
        if self._loss_run >= self.loss_checks:
            if self._q_alarm('loss', None, None,
                             '连续 %d 轮借帧超时' % self._loss_run,
                             video_start_ts=self._loss_started,
                             no_video=self._loss_alarmed):
                self._loss_alarmed = True

    def _on_frames_ok(self):
        '''借帧恢复：视频丢失状态解除，episode 归零。'''
        if self._loss_run:
            if self._loss_alarmed:
                logger.info('[视频质量][%s] 视频丢失解除：借帧恢复（此前连续 %d 轮超时）',
                            self.conf_name, self._loss_run)
            self._loss_run = 0
            self._loss_alarmed = False
            self._q_epi['loss'] = 0

    def _on_view_changed(self, frame, metrics):
        '''摄像仪挪动（大幅）：场景结构被整体替换但画面在焦 —— 基类判为视角变化不按遮挡
        报警（并静默走自愈重建基线），这里按"摄像仪挪动"上报。'''
        if not self.q_enabled['move']:
            return
        self._q_alarm('move', frame, metrics,
                      '场景被整体替换且在焦(corr=%.2f sharp=%.4f)'
                      % (metrics['struct_corr'], metrics['sharp_frac']))

    def _quality_round(self, frames, analyzed, pairs, moving):
        '''每轮质量检测：在遮挡逐帧 metrics 上做标量判定 + 冻结小图差分。'''
        det = self.detector
        ms = [m for _, _, m in analyzed]
        n = len(ms)
        need = max(1, int(math.ceil(self.min_vote_ratio * n)))
        reasons_all = set()
        for m in ms:
            reasons_all.update(m['reasons'])
        means = [m['mean'] for m in ms]
        swing = (max(means) - min(means)) if means else 0.0
        stable = swing < self.flicker_delta       # 亮度稳定（无补光振荡/日夜切换瞬间）

        # ---- 画面过暗（镜头罩死的全黑由遮挡 blackout 负责，这里让位） ----
        dark_votes = sum(1 for m in ms
                         if m['mean'] < self.dark_mean and m['dark_frac'] >= self.dark_frac)
        dark_hit = dark_votes >= need and 'blackout' not in reasons_all
        self._q_step('dark', dark_hit, self.dark_checks, frames[-1], ms[-1],
                     'mean=%.1f dark_frac=%.2f' % (ms[-1]['mean'], ms[-1]['dark_frac']))

        # ---- 画面过曝（近距反光全白由遮挡 whiteout 负责，这里让位） ----
        over_votes = sum(1 for m in ms if m['clip_frac'] >= self.overexpose_frac)
        over_hit = over_votes >= need and 'whiteout' not in reasons_all
        self._q_step('overexpose', over_hit, self.overexpose_checks, frames[-1], ms[-1],
                     'clip_frac=%.2f mean=%.1f' % (ms[-1]['clip_frac'], ms[-1]['mean']))

        # ---- 图像模糊（锐度对自身基线塌缩，但场景结构仍在 = 失焦/脏污/水雾，
        #      区别于遮挡的结构替换；转动帧有运动模糊、不可信） ----
        # 照明制式门控：本轮亮度与基线亮度偏差超过 blur_mean_jump（日夜切换/红外启停/
        # 灯光开合完成后的稳态）→ 旧锐度基线不可比，整组重置重预热（约 1 分钟）。
        # 不能只拦截阶跃那一轮然后沿用旧基线：夜间红外画面天然偏软，拿白天基线判会
        # 整夜每个报警间隔误报一次，且命中轮不学基线 → 死锁永不自愈（审查核实的缺陷）。
        round_mean = sum(means) / n if n else 0.0
        if self._blur_n and abs(round_mean - self._blur_mean) > self.blur_mean_jump:
            logger.info('[视频质量][%s] 场景亮度 %.1f 偏离锐度基线亮度 %.1f 超过 %.0f'
                        '（照明制式变化），锐度基线重置重预热', self.conf_name,
                        round_mean, self._blur_mean, self.blur_mean_jump)
            self._blur_sharp = self._blur_spread = self._blur_mean = 0.0
            self._blur_n = 0
            self._save_blur_baseline()
        blur_base_ok = (self._blur_n >= self.blur_warmup
                        and self._blur_sharp >= 2.0 * det.sharp_thresh
                        and self._blur_spread >= det.spread_thresh)
        blur_hit = False
        if blur_base_ok and not moving and stable:
            blur_votes = sum(
                1 for m in ms
                if m['sharp_frac'] <= self.blur_ratio * self._blur_sharp
                and m['sharp_spread'] <= self.blur_spread_ratio * self._blur_spread
                and m['struct_corr'] >= self.blur_corr
                and m['gx_detail'] >= det.detail_thresh)
            blur_hit = blur_votes >= need
        self._q_step('blur', blur_hit, self.blur_checks, frames[-1], ms[-1],
                     'sharp=%.4f/%.4f spread=%.2f/%.2f corr=%.2f'
                     % (ms[-1]['sharp_frac'], self._blur_sharp,
                        ms[-1]['sharp_spread'], self._blur_spread, ms[-1]['struct_corr']))

        # ---- 画面抖动（同轮帧对位移大且方向往复；云台单向巡航无反转不命中） ----
        # 只用真正时间相邻的帧对（i_to-i_from==1，无结构帧被过滤后帧对可能跨间隙），
        # 且方向反转要求两位移向量共享一帧（前对末帧=后对首帧）—— 跨间隙/不相邻的
        # 位移向量不具备"瞬时往复"的物理含义（审查发现）
        sig = [(i_from, i_to, dx, dy) for i_from, i_to, dx, dy in pairs
               if i_to - i_from == 1 and math.hypot(dx, dy) >= self.jitter_shift]
        reversal = False
        for a, b in zip(sig, sig[1:]):
            if b[0] != a[1]:
                continue
            x1, y1, x2, y2 = a[2], a[3], b[2], b[3]
            d1 = math.hypot(x1, y1)
            d2 = math.hypot(x2, y2)
            if d1 > 1e-6 and d2 > 1e-6 and (x1 * x2 + y1 * y2) / (d1 * d2) < -0.5:
                reversal = True
                break
        jitter_hit = len(sig) >= self.jitter_pairs and reversal
        self._q_step('jitter', jitter_hit, self.jitter_checks, frames[-1], ms[-1],
                     '显著位移帧对=%d 反转=%s' % (len(sig), reversal))

        # ---- 摄像仪挪动（小幅持续位移：对基线平移大但平移后相关高=同场景被移动；
        #      转动中位移量不可信跳过；大幅挪动由 _on_view_changed 负责） ----
        move_hit = False
        if not moving and det._base_n >= det.baseline_warmup:
            move_votes = sum(1 for m in ms
                             if m['base_shift'] >= self.move_cells
                             and m['shift_corr'] >= self.move_corr
                             and m['shift_full_corr'] >= self.move_full_corr)
            move_hit = move_votes >= need
        self._q_step('move', move_hit, self.move_checks, frames[-1], ms[-1],
                     'base_shift=%.1f格 shift_corr=%.2f full=%.2f'
                     % (ms[-1]['base_shift'], ms[-1]['shift_corr'],
                        ms[-1]['shift_full_corr']))

        # ---- 画面冻结（跨轮 + 轮内帧内容严格不变；近全黑帧让位于遮挡/过暗） ----
        self._check_freeze(frames, ms)

        # ---- 分辨率异常（引擎报告的原始尺寸 vs 平台配置 / 中途变化） ----
        self._check_resolution(frames[-1], ms[-1])

        # ---- 锐度基线更新：只学"干净轮"（无任何遮挡证据、无质量异常命中、非转动、
        #      亮度稳定、非可疑单色帧），防糊帧/暗帧把基线拉低后漏检 ----
        if (not moving and stable and not reasons_all
                and not (dark_hit or over_hit or blur_hit or jitter_hit or move_hit)
                and not ms[-1].get('suspect')):
            clean = [m for _, o, m in analyzed if not o]
            if clean:
                sharp = sum(m['sharp_frac'] for m in clean) / len(clean)
                spread = sum(m['sharp_spread'] for m in clean) / len(clean)
                cmean = sum(m['mean'] for m in clean) / len(clean)
                a = self.blur_alpha
                if self._blur_n == 0:
                    self._blur_sharp, self._blur_spread = sharp, spread
                    self._blur_mean = cmean
                else:
                    self._blur_sharp += a * (sharp - self._blur_sharp)
                    self._blur_spread += a * (spread - self._blur_spread)
                    self._blur_mean += a * (cmean - self._blur_mean)
                self._blur_n += 1
                self._save_blur_baseline()

    # ================= 各类检测的内部实现 =================
    def _check_freeze(self, frames, ms):
        '''冻结判定：本轮末帧 vs 上一轮存帧、本轮首帧 vs 末帧，全分辨率灰度上
        "变化像素(|Δ|>1)占比"双双 ≤ freeze_px_frac。真冻结是同一解码缓冲重复、逐位相同
        （占比≈0）；活流即使场景完全静止也有传感器噪声/OSD 时钟走秒，占比远超阈值。
        不可用缩图均差判：降采样把噪声平均掉后活流也会"看似不变"（合成帧实测误判）。'''
        cur = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)
        prev, self._freeze_prev = self._freeze_prev, cur
        if not self.q_enabled['freeze']:
            return
        if float(cur.mean()) < 8.0:            # 近全黑：黑帧天然全同，由遮挡/过暗负责
            self._q_run['freeze'] = 0
            return
        freeze_hit = False
        across = within = -1.0
        if prev is not None and prev.shape == cur.shape:
            across = float((cv2.absdiff(prev, cur) > 1).mean())
            within = 0.0
            if len(frames) > 1:
                first = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
                within = float((cv2.absdiff(first, cur) > 1).mean())
            freeze_hit = across <= self.freeze_px_frac and within <= self.freeze_px_frac
        self._q_step('freeze', freeze_hit, self.freeze_checks, frames[-1], ms[-1],
                     '跨轮变化像素=%.5f%% 轮内=%.5f%%' % (across * 100, within * 100))

    def _check_resolution(self, frame, metrics):
        '''分辨率判定：引擎报告的解码原始尺寸与平台配置不符（容忍 90° 旋转的宽高互换）
        或中途变化。未收到引擎报告（旧引擎/尚无帧）时不判。'''
        rs = self._raw_size
        if rs is None:
            return
        detail = []
        exp = self.expect_resolution
        if exp is not None:
            w, h = rs
            ew, eh = exp
            if not ((w == ew and h == eh) or (w == eh and h == ew)):
                detail.append('实际 %dx%d ≠ 配置 %dx%d' % (w, h, ew, eh))
        if self._raw_size_first is not None and rs != self._raw_size_first:
            detail.append('中途由 %dx%d 变为 %dx%d' % (self._raw_size_first + rs))
        self._q_step('resolution', bool(detail), self.res_checks, frame, metrics,
                     '；'.join(detail) or '正常')

    # ================= 计数/报警公共通道 =================
    def _q_step(self, qtype, hit, need_checks, frame, metrics, detail):
        '''某类异常一轮判定的累计：连续 hit 满 need_checks 轮 → 报警（各类独立节流 +
        episode 退避）；条件解除时 episode 归零。'''
        if not self.q_enabled[qtype]:
            return
        if not hit:
            if self._q_run[qtype] >= need_checks:
                logger.info('[视频质量][%s] %s 解除（%s）', self.conf_name,
                            ALARM_TEXTS[qtype], detail)
            self._q_run[qtype] = 0
            self._q_epi[qtype] = 0
            return
        self._q_run[qtype] += 1
        logger.info('[视频质量][%s] %s 证据命中 %d/%d 轮（%s）', self.conf_name,
                    ALARM_TEXTS[qtype], self._q_run[qtype], need_checks, detail)
        if self._q_run[qtype] >= need_checks:
            self._q_alarm(qtype, frame, metrics, detail)

    def _q_alarm(self, qtype, frame, metrics, detail, video_start_ts=None, no_video=False):
        '''质量类报警：节流/退避 → 报警视频 → 存图 → 投递异步上报（通道同遮挡 _alarm）。
        返回是否已受理上报（节流内/队列满返回 False）。
        video_start_ts: 报警视频片段起点（视频丢失传断流起始时刻，取断流前画面）；
        no_video: 不触发报警视频（视频丢失重复报时缓冲无新帧，保存只耗磁盘）。'''
        now = time.time()
        gate = self.q_intervals[qtype]
        # episode 退避：同一持续异常前 q_free_alarms 次按正常间隔报，之后退避 ——
        # 过暗/冻结/丢失类故障可整夜/数天持续，防刷爆平台 + 报警视频占满磁盘
        if self._q_epi[qtype] >= self.q_free_alarms:
            gate = max(gate, self.q_backoff)
        if now - self._q_last[qtype] < gate:
            return False
        self._q_last[qtype] = now
        self._q_epi[qtype] += 1
        alarm_ts = time.time()
        # 视频质量类报警的分析类型 03（同遮挡），文件名与上报时间逐秒一致
        video_url = None
        if not no_video:
            video_url = alarm_video.trigger(self.conf_name, alarm_ts=alarm_ts,
                                            start_ts=video_start_ts, analysis_type='03')
        ori_paths = []
        if frame is not None:
            try:
                ori_paths = self._save_quality_images(qtype, frame)
            except Exception:
                logger.exception('[视频质量][%s] %s 报警图保存失败（仍尝试上报）',
                                 self.conf_name, ALARM_TEXTS[qtype])
        logger.warning('[视频质量][%s] %s：%s → 上报（episode 第 %d 次）', self.conf_name,
                       ALARM_TEXTS[qtype], detail, self._q_epi[qtype])
        try:
            self._q_queue.put_nowait((qtype, ALARM_TEXTS[qtype], ori_paths, alarm_ts, video_url))
        except queue.Full:
            logger.error('[视频质量][%s] 上报队列已满（kafka/DB 长时间不可达？），'
                         '丢弃本次 %s 上报', self.conf_name, ALARM_TEXTS[qtype])
            self._q_last[qtype] = 0.0
            self._q_epi[qtype] = max(0, self._q_epi[qtype] - 1)
            return False
        return True

    def _q_upload_loop(self):
        '''质量报警异步上报线程：串行消费队列调 _upload_alarm（算法日志 + kafka）。
        失败回滚该类型的节流记录与 episode 计数，下轮命中立即重试。'''
        while True:
            qtype, text, ori_paths, alarm_ts, video_url = self._q_queue.get()
            try:
                ok = self._upload_alarm(text, ori_paths, alarm_ts, video_url,
                                        analysis_case=ALARM_CASES.get(qtype))
            except Exception:
                logger.exception('[视频质量][%s] %s 异步上报异常', self.conf_name, text)
                ok = False
            finally:
                self._q_queue.task_done()
            if not ok:
                self._q_last[qtype] = 0.0     # 上报失败不吃间隔，下轮命中立即重试
                self._q_epi[qtype] = max(0, self._q_epi[qtype] - 1)

    # ---- 遮挡报警的 episode 退避（复用 quality_free_alarms/quality_backoff） ----
    # check_interval/alarm_interval 默认均为 10s：持续遮挡不退避 = 每 10s 一次上报 +
    # 一段报警视频（~10MB），一小时 ≈3.6GB，会占满盒上磁盘（审查发现）。只拉长同一次
    # 遮挡 episode 内的重复上报间隔（前 quality_free_alarms 次照常），检测/日志/
    # episode 起点语义均不变；episode 解除（出现干净轮）后计数归零。
    def _effective_alarm_interval(self):
        if self._occ_since != self._occ_epi_mark:
            # _occ_since 在每次遮挡 episode 首轮取定、解除时清 None —— 变化即新 episode
            self._occ_epi_mark = self._occ_since
            self._occ_alarms_epi = 0
        gate = super()._effective_alarm_interval()
        if self._occ_alarms_epi >= self.q_free_alarms:
            gate = max(gate, self.q_backoff)
        return gate

    def _alarm(self, frame, metrics):
        if super()._alarm(frame, metrics):
            self._occ_alarms_epi += 1
            return True
        return False

    def _save_quality_images(self, qtype, frame):
        '''存质量报警图（整幅红色描边标注 + 原图，仅本地留档排查），返回原图 URL 列表。
        URL 口径同遮挡/人员计数：主机 = 算力盒本机 cm.localhost_ip。'''
        host = cm.localhost_ip
        port = int(cm.upload_port)
        out_dir = os.path.join(_OUTPUT_ROOT, self.conf_name, 'images')
        os.makedirs(out_dir, exist_ok=True)
        # 滚动清理旧报警图（监测线程内、非热路径；内部每小时至多真正扫描一次）
        try:
            alarm_video.prune_dir(out_dir, ('.jpg',))
        except Exception:
            pass
        h, w = frame.shape[:2]
        marked = frame.copy()
        cv2.rectangle(marked, (0, 0), (w - 1, h - 1), (0, 0, 255), max(2, h // 200))
        ts = time.strftime('%Y-%m-%d_%H-%M-%S')
        alarm_path = os.path.join(out_dir, '%s_alarm_%s.jpg' % (qtype, ts))
        ori_path = os.path.join(out_dir, '%s_ori_%s.jpg' % (qtype, ts))
        if not cv2.imwrite(alarm_path, marked):
            logger.error('[视频质量][%s] 报警图写入失败(imwrite=False): %s',
                         self.conf_name, alarm_path)
        if not cv2.imwrite(ori_path, frame):
            logger.error('[视频质量][%s] 原图写入失败(imwrite=False): %s',
                         self.conf_name, ori_path)
            return []
        return ['http://%s:%d%s' % (host, port, ori_path)]

    # ================= 锐度基线持久化 =================
    def _save_blur_baseline(self):
        '''锐度基线落盘（原子替换写）：重启后直接加载，防"重启时正模糊 → 糊帧学成基线"。'''
        try:
            os.makedirs(os.path.dirname(self.blur_baseline_path), exist_ok=True)
            tmp = self.blur_baseline_path + '.tmp.npz'
            np.savez(tmp, scalars=np.array(
                [self._blur_sharp, self._blur_spread, self._blur_mean,
                 float(self._blur_n)], np.float64))
            os.replace(tmp, self.blur_baseline_path)
        except Exception:
            logger.exception('[视频质量][%s] 锐度基线持久化失败（不影响检测）', self.conf_name)

    def _load_blur_baseline(self):
        '''加载持久化锐度基线；文件缺失/损坏/旧版维度（无基线亮度）时照常预热。'''
        try:
            with np.load(self.blur_baseline_path) as z:
                sc = z['scalars']
            if sc.size >= 4:
                self._blur_sharp, self._blur_spread = float(sc[0]), float(sc[1])
                self._blur_mean = float(sc[2])
                self._blur_n = int(sc[3])
                logger.info('[视频质量][%s] 已加载锐度基线 sharp=%.4f spread=%.2f '
                            'mean=%.1f（%d 轮）', self.conf_name, self._blur_sharp,
                            self._blur_spread, self._blur_mean, self._blur_n)
        except Exception:
            pass


def quality_cfg_from_row(row, **overrides):
    '''从一条算法配置行提取视频质量检测所需字段（含遮挡身份字段 + 平台配置分辨率），
    生成引擎 cfg["occlusion"]。overrides 可覆盖任意检测/周期/节流参数。'''
    c = camera_occlusion.occlusion_cfg_from_row(row)
    c['expect_resolution'] = row.get('conf_img_resolution') or ''
    c.update(overrides)
    return c
