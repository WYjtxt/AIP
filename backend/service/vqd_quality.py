# native-diagnosis-reference-origin-v1
# native-diagnosis-sampling-failure-v1
"""Shared-window video quality measurements with explicit evidence requirements.

Saved thresholds remain percentages of actual eligible samples. Reference-based
checks abstain when no confirmed same-source reference exists.
"""
import hashlib
from pathlib import Path
import time
import uuid

import cv2
import numpy as np

LABELS = ('视频抖动', '条纹干扰', '视频丢失', '视频遮挡', '视频冻结', '高亮度', '低亮度',
          '视频噪声', '偏色', '清晰度', '场景变化', '对比度', '横纹干扰', '滚动条纹', '横波干扰', '花帧检测')
REFERENCE_CHECKS = frozenset(('视频遮挡', '偏色', '清晰度', '场景变化', '对比度'))
REFERENCE_ROOT = Path('/data/AIGO/outputs/vqd/references')


def small(frame):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
        raise ValueError('Invalid video frame')
    width = 480
    return cv2.resize(frame, (width, max(32, round(frame.shape[0] * width / frame.shape[1]))), interpolation=cv2.INTER_AREA)


def content(frame):
    # Camera timestamps/names must not become scene-change or corruption evidence.
    frame = small(frame)
    height = frame.shape[0]
    return frame[round(height * .13):round(height * .92)]


def source_digest(source):
    return hashlib.sha256(str(source).encode()).hexdigest()


def reference_path(equipment_id):
    equipment_id = int(equipment_id)
    if not 0 < equipment_id < 2147483647:
        raise ValueError('Invalid equipment')
    return REFERENCE_ROOT / ('equipment-' + str(equipment_id) + '.npz')


def save_reference(equipment_id, source, frame, automatic=False):
    path = reference_path(equipment_id)
    if REFERENCE_ROOT.is_symlink() or path.is_symlink():
        raise OSError('Invalid reference path')
    REFERENCE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    REFERENCE_ROOT.chmod(0o700)
    temporary = path.with_name(path.stem + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            np.savez_compressed(stream, frame=small(frame), source=np.array(source_digest(source)), created=np.array(time.time()), automatic=np.array(bool(automatic)))
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        # The production image still runs Python 3.7.
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def load_reference(equipment_id, source):
    try:
        path = reference_path(equipment_id)
        if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
            return None
        with np.load(path, allow_pickle=False) as archive:
            if str(archive['source']) != source_digest(source):
                return None
            frame = archive['frame'].copy()
        return small(frame)
    except (OSError, ValueError, KeyError, EOFError):
        return None


def longest_run(values):
    best = run = 0
    for value in values:
        run = run + 1 if value else 0
        best = max(best, run)
    return best


def classify(flags, prewarn, warn, min_run=2):
    if not len(flags):
        return '未检测'
    ratio = 100 * sum(bool(flag) for flag in flags) / len(flags)
    # Inclusive comparisons avoid a normal gap at an exact threshold.
    if longest_run(flags) < min_run:
        return '正常'
    if ratio > 0 and ratio >= float(warn):
        return '报警'
    if ratio > 0 and ratio >= float(prewarn):
        return '预警'
    return '正常'


def gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)


def normalized(image):
    low, high = np.percentile(image, (10, 90))
    return (image - np.median(image)) / max(float(high - low), 20.0)


def correlation(a, b):
    a = a.ravel().astype(np.float32)
    b = b.ravel().astype(np.float32)
    a -= np.mean(a); b -= np.mean(b)
    scale = float(np.linalg.norm(a) * np.linalg.norm(b))
    if scale > 1e-5:
        return float(np.dot(a, b) / scale)
    return 1.0 if np.linalg.norm(a) < 1e-3 and np.linalg.norm(b) < 1e-3 else 0.0


def focus(image):
    dx = cv2.Sobel(image, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(image, cv2.CV_32F, 0, 1)
    gradient = float(np.mean(dx * dx + dy * dy))
    lap = float(np.var(cv2.Laplacian(image, cv2.CV_32F)))
    return lap / max(gradient, 1.0), gradient


def grid_score(image):
    """Look for distributed repeated block seams, never a color or blur alone."""
    best = 0.0
    for axis in (0, 1):
        profile = np.mean(np.abs(np.diff(image, axis=axis)), axis=1 - axis)
        floor = max(float(np.mean(profile)), 0.7)
        for period in (3, 4, 6, 8, 12, 16, 24):
            for offset in range(period):
                positions = np.arange(offset, len(profile), period)
                if len(positions) < 6:
                    continue
                peaks = profile[positions] > max(4.0, floor * 2)
                if np.sum(peaks) < max(5, len(positions) * .45):
                    continue
                selected = positions[peaks]
                if selected[-1] - selected[0] < len(profile) * .5:
                    continue
                best = max(best, float(np.mean(profile[positions])) / floor)
    return best


def line_metric(residual, axis):
    # A person/object affecting only part of a row is removed by the median.
    profile = np.median(residual, axis=axis)
    profile = profile - cv2.GaussianBlur(profile.reshape(-1, 1), (1, 0), 9).ravel()
    spectrum = np.fft.rfft(profile)
    amplitude = np.abs(spectrum)
    amplitude[:3] = 0
    amplitude[len(amplitude) // 2:] = 0
    peak = int(np.argmax(amplitude))
    if not amplitude.size or float(np.sum(amplitude ** 2)) < 1e-6:
        return 0.0, 0.0, peak, 0.0
    energy = float(amplitude[peak] ** 2 / np.sum(amplitude ** 2))
    strength = float(amplitude[peak] * 2 / len(profile))
    return strength, energy, peak, float(np.angle(spectrum[peak]))


def shift(a, b):
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    delta, response = cv2.phaseCorrelate(normalized(a).copy(), normalized(b).copy(), window)
    return np.array(delta, dtype=float), float(response)


def noise_estimate(image):
    smooth = cv2.medianBlur(image.astype(np.uint8), 3).astype(np.float32)
    residual = np.abs(image - smooth)
    dx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1)
    power = dx * dx + dy * dy
    flat = power <= max(160, float(np.percentile(power, 30)))
    return float(np.median(residual[flat])) * 1.4826


def analyze(frames, timestamps, thresholds, reference=None, read_errors=0, fps=8):
    count = len(frames)
    if count < 16 or len(timestamps) != count or timestamps[-1] - timestamps[0] < 2.5:
        return {name: '未检测' for name in LABELS}, {'reason': '有效采样不足，无法可靠判断画质', 'samples': count, 'failed': True}
    # Discard startup decoder transients; use one consistent window for all checks.
    frames = [small(frame) for frame in frames[2:]]
    times = np.asarray(timestamps[2:], dtype=float)
    areas = [content(frame) for frame in frames]
    grays = [gray(frame) for frame in areas]
    n = len(frames)
    reference_gray = gray(content(reference)) if reference is not None else None
    base = reference_gray if reference_gray is not None else np.median(np.stack(grays[:5]), axis=0)
    ref_color = content(reference) if reference is not None else np.median(np.stack(areas[:5]), axis=0).astype(np.uint8)
    base_focus, base_gradient = focus(base)
    base_grid = grid_score(base)
    base_range = float(np.percentile(base, 95) - np.percentile(base, 5))
    base_noise = noise_estimate(base)
    base_lab = cv2.cvtColor(ref_color, cv2.COLOR_BGR2LAB).astype(np.float32)
    flags = {name: [False] * n for name in LABELS}
    evidence = {name: [] for name in LABELS}
    shifts, row_phases, previous = [], [], None
    full_grays = [gray(frame) for frame in frames]
    freeze_start = None
    moving_before_freeze = False
    for i, image in enumerate(grays):
        low, median, high = np.percentile(image, (5, 50, 95))
        span = float(high - low)
        detail, gradient = focus(image)
        normalized_diff = normalized(image) - normalized(base)
        changed = float(np.mean(np.abs(normalized_diff) > .5))
        visual_similarity = correlation(normalized(image), normalized(base))
        grid = grid_score(image)
        flags['花帧检测'][i] = (grid > max(2.7, base_grid * 1.6 + .3) and changed > .12
                                  if reference is not None else grid > 4.5)
        evidence['花帧检测'].append({'block_seam': round(grid, 3), 'changed_fraction': round(changed, 3)})
        flags['高亮度'][i] = median > 245 and low > 230 and span < 30
        flags['低亮度'][i] = median < 12 and high < 28 and span < 24
        extreme = flags['高亮度'][i] or flags['低亮度'][i]
        flags['视频遮挡'][i] = (not extreme and base_gradient > 100 and gradient < base_gradient * .08
                                and visual_similarity < .35 and span < max(20, base_range * .3))
        flags['清晰度'][i] = (not extreme and not flags['视频遮挡'][i] and base_gradient > 100
                              and detail < base_focus * .38 and gradient < base_gradient * .65)
        flags['对比度'][i] = (not extreme and base_range > 45 and span < base_range * .38
                              and not flags['视频遮挡'][i])
        current_lab = cv2.cvtColor(areas[i], cv2.COLOR_BGR2LAB).astype(np.float32)
        chroma_delta = np.median(current_lab[:, :, 1:] - base_lab[:, :, 1:], axis=(0, 1))
        chroma_distance = float(np.linalg.norm(chroma_delta))
        spread = np.mean(np.linalg.norm(current_lab[:, :, 1:] - base_lab[:, :, 1:] - chroma_delta, axis=2) < 14)
        flags['偏色'][i] = not extreme and chroma_distance > 24 and spread > .7
        edge_similarity = correlation(cv2.Laplacian(cv2.GaussianBlur(image, (5, 5), 1), cv2.CV_32F),
                                      cv2.Laplacian(cv2.GaussianBlur(base, (5, 5), 1), cv2.CV_32F))
        flags['场景变化'][i] = (not extreme and visual_similarity < .8 and edge_similarity < .12 and changed > .1
                                and not flags['视频遮挡'][i] and not flags['花帧检测'][i]
                                and not flags['清晰度'][i])
        noise = noise_estimate(image)
        flags['视频噪声'][i] = noise > (max(10, base_noise * 3 + 3) if reference is not None else 14)
        residual = normalized_diff * max(base_range, 30)
        horizontal = line_metric(residual, 1)
        vertical = line_metric(residual, 0)
        horizontal_band = horizontal[0] > 9 and horizontal[1] > .32
        vertical_band = vertical[0] > 9 and vertical[1] > .32
        flags['条纹干扰'][i] = horizontal_band or vertical_band
        flags['横纹干扰'][i] = horizontal_band
        row_phases.append(horizontal)
        if previous is not None:
            delta, response = shift(previous, image)
            shifts.append((i, delta, response))
            # Rolling horizontal geometry requires coherent row shifts, not a moving object.
            if i % 3 == 0:
                row_shifts = []
                for a, b in zip(np.array_split(previous, 6), np.array_split(image, 6)):
                    row_delta, confidence = shift(a, b)
                    if confidence > .35 and abs(row_delta[1]) < 1.5:
                        row_shifts.append(row_delta[0] - delta[0])
                if len(row_shifts) >= 5 and np.std(row_shifts) > 3 and np.ptp(row_shifts) > 8:
                    for position in range(max(0, i - 2), i + 1):
                        flags['横波干扰'][position] = True
            difference = np.abs(full_grays[i] - full_grays[i - 1])
            # Full-frame exactness includes timestamp changes; static scenes alone are insufficient.
            identical = np.mean(difference) < .006 and np.mean(difference > 1) < .0002
            if identical:
                if freeze_start is None:
                    freeze_start = i - 1
                if times[i] - times[freeze_start] >= 3:
                    for position in range(freeze_start, i + 1):
                        flags['视频冻结'][position] = True
            else:
                freeze_start = None
                moving_before_freeze = True
        previous = image
    # Jitter is repeated whole-view movement with reversals; steady panning is a different event.
    reliable = [(i, delta) for i, delta, response in shifts if response > .35 and np.linalg.norm(delta) > 1.8]
    reversals = sum(float(np.dot(a[1], b[1])) < -1 for a, b in zip(reliable, reliable[1:]))
    if len(reliable) >= 5 and reversals >= 3:
        for i, _ in reliable:
            flags['视频抖动'][i] = True
    valid_phases = [(i, value) for i, value in enumerate(row_phases) if value[0] > 9 and value[1] > .32]
    if len(valid_phases) >= 6:
        bins = [value[2] for _, value in valid_phases]
        if len(set(bins)) == 1:
            phases = np.unwrap([value[3] for _, value in valid_phases])
            steps = np.diff(phases)
            if np.count_nonzero(np.abs(steps) > .1) >= len(steps) * .65 and np.std(steps) < .8:
                for i, _ in valid_phases:
                    flags['滚动条纹'][i] = True
    # Sampling cadence is not a packet timestamp. Only actual read failures count as loss evidence.
    # Do not turn a single recovered read failure into 100% frame loss.
    loss_count = min(n, round(n * read_errors / max(n + read_errors, 1)))
    flags['视频丢失'] = [True] * loss_count + [False] * (n - loss_count)
    results, metrics, notes = {}, {}, []
    for label in LABELS:
        if label not in thresholds:
            results[label] = '未检测'
            continue
        if label in REFERENCE_CHECKS and reference is None:
            results[label] = '未检测'
            continue
        if label == '清晰度' and base_gradient <= 100:
            results[label] = '未检测'
            notes.append('参考画面纹理不足，清晰度未检测')
            continue
        prewarn, warn = thresholds[label]
        status = classify(flags[label], prewarn, warn)
        # No temporal evidence can distinguish a truly static view from an already frozen stream.
        if label == '视频冻结' and status in ('报警', '预警') and not moving_before_freeze:
            status = '未检测'
            notes.append('画面持续不变，静止场景与冻结无法可靠区分')
        results[label] = status
        abnormal_count = int(sum(flags[label]))
        ratio = 100 * abnormal_count / n
        metrics[label] = {'abnormal_samples': abnormal_count, 'samples': n, 'ratio_percent': round(ratio, 2),
                          'longest_run': longest_run(flags[label]), 'status': status}
        if status in ('报警', '预警'):
            notes.append(label + '：异常采样占比' + str(round(ratio, 1)) + '%')
    if reference is None and any(label in thresholds for label in REFERENCE_CHECKS):
        notes.append('遮挡、偏色、清晰度、场景及对比度需设置正常画面基准')
    return results, {'reason': '；'.join(notes), 'samples': n, 'duration_seconds': round(float(times[-1] - times[0]), 2),
                     'reference_available': reference is not None, 'checks': metrics, 'glitch_evidence': evidence['花帧检测']}
