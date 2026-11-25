"""Establish a fixed per-source reference once from a usable diagnostic window."""
import json
from pathlib import Path
import uuid

import numpy as np

from service.vqd_quality import content, focus, gray, load_reference, save_reference


SETTINGS_PATH = Path(__file__).resolve().parents[2] / 'Config_files/vqd-settings.json'


def get_settings():
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'auto_reference_enabled': True}
    if not isinstance(settings, dict):
        raise ValueError('Invalid automatic reference settings')
    enabled = settings.get('auto_reference_enabled', True)
    if type(enabled) is not bool:
        raise ValueError('Invalid automatic reference setting')
    return {'auto_reference_enabled': enabled}


def write_settings(enabled):
    if type(enabled) is not bool:
        raise ValueError('Automatic reference setting must be boolean')
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_PATH.with_name(SETTINGS_PATH.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps({'auto_reference_enabled': enabled}) + '\n', encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(SETTINGS_PATH)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return {'auto_reference_enabled': enabled}


def candidate_frame(frames, timestamps, read_errors):
    if (len(frames) < 16 or len(timestamps) != len(frames)
            or timestamps[-1] - timestamps[0] < 2.5 or read_errors):
        return None, '自动基准待建立：有效采样不足或读取不稳定'
    # Match the diagnosis engine's startup-frame exclusion and content crop.
    usable = frames[2:]
    images = [gray(content(frame)) for frame in usable]
    differences = [float(np.mean(np.abs(b - a))) for a, b in zip(images, images[1:])]
    if float(np.median(differences)) >= 12:
        return None, '自动基准待建立：画面变化较大，等待稳定画面'
    levels = [float(np.median(image)) for image in images]
    median_level = float(np.median(levels))
    candidates = []
    for index in range(1, len(images) - 1):
        image = images[index]
        low, high = np.percentile(image, (5, 95))
        detail, gradient = focus(image)
        if (20 <= levels[index] <= 235 and high - low > 30 and gradient > 100
                and detail > .02 and max(differences[index - 1:index + 1]) < 12):
            candidates.append((abs(levels[index] - median_level), -gradient, index))
    if not candidates:
        return None, '自动基准待建立：画面过暗、过亮或清晰纹理不足'
    return usable[min(candidates)[2]], ''


def ensure_reference(equipment_id, source, frames, timestamps, read_errors=0, reference=None):
    if reference is not None:
        return reference, ''
    try:
        if not get_settings()['auto_reference_enabled']:
            return None, ''
        candidate, note = candidate_frame(frames, timestamps, read_errors)
        if candidate is None:
            return None, note
        # A manual reference saved while capture was in progress takes precedence.
        existing = load_reference(equipment_id, source)
        if existing is not None:
            return existing, ''
        save_reference(equipment_id, source, candidate, automatic=True)
        saved = load_reference(equipment_id, source)
        if saved is None:
            return None, '自动基准建立失败，本轮保留未检测'
        return saved, '已自动建立正常画面基准'
    except (OSError, ValueError):
        return None, '自动基准建立失败，本轮保留未检测'
