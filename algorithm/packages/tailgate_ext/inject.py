#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Site-level hotfix injector for 视频AI识别分析管理平台.

Invoked by /data/AIGO/platform_start/Config_files/platform_release_site_entrypoint.py
(_apply_tailgate_inject hook) on every container start, BEFORE the stock container
runtime starts. Idempotent, backs up originals, never blocks platform startup.

role=backend:
  A) backend/service/algorithm_configuration_contract.py
     allow legacy runtime templates 闸机尾随 + 跨越闸机 in the 新增算法配置 wizard
  B) backend/tool/VQD.py
     drop analyzeduration;1000000 from OPENCV_FFMPEG_CAPTURE_OPTIONS (H.265 解码失败根因)
  C) backend/service/vqd_diagnosis.py
     OpenCV open timeout 6000 -> 10000 ms

role=algorithm-master:
  D) templates/crossing.py                (new; from V1.2 package)
  E) models/yolov8_sophon.py              append postprocess_pose()
  F) templates/rtsp_infer_push.py         pose inference branch + tolerant result rows
  G) model_start.py                       route 跨越闸机 -> templates.crossing
"""
import os
import sys
import time
import shutil
import pathlib

ROOT = pathlib.Path('/data/AIGO/platform_start')
EXT = ROOT / 'model_algorithm_package' / 'tailgate_ext'
PAYLOAD = EXT / 'payload' / 'engine'
BK = EXT / 'backups'
LOG = EXT / 'apply.log'
ENGINE = ROOT / 'platform_algorithm_start'


def log(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + str(msg)
    try:
        BK.mkdir(parents=True, exist_ok=True)
        with open(str(LOG), 'a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    except Exception:
        pass
    try:
        print('[site-patch] ' + str(msg))
    except Exception:
        pass


def _backup(path):
    BK.mkdir(parents=True, exist_ok=True)
    target = BK / (path.name + '.' + time.strftime('%Y%m%d-%H%M%S') + '.bak')
    if not target.exists():
        shutil.copy2(str(path), str(target))
    return target


def _write(path, data):
    temp = path.with_name('.' + path.name + '.site-patch-%d' % os.getpid())
    temp.write_bytes(data)
    try:
        shutil.copymode(str(path), str(temp))
    except Exception:
        pass
    os.replace(str(temp), str(path))


def replace_once(path, old, new, marker, expect=1):
    if not path.is_file():
        log('skip missing %s' % (path,))
        return False
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return False
    if text.count(old) != expect:
        log('skip anchor-count-%d %s' % (text.count(old), path))
        return False
    updated = text.replace(old, new, expect)
    try:
        compile(updated, str(path), 'exec')
    except SyntaxError as error:
        log('skip syntax-error %s (%s)' % (path, error))
        return False
    saved = _backup(path)
    _write(path, updated.encode('utf-8'))
    log('patched %s (backup %s)' % (path, saved.name))
    return True


def copy_payload(name, destination):
    source = PAYLOAD / name
    if not source.is_file():
        log('skip missing payload %s' % (source,))
        return False
    data = source.read_bytes()
    if destination.is_file() and destination.read_bytes() == data:
        return False
    if destination.is_file():
        stored = _backup(destination)
        log('backup %s -> %s' % (destination, stored.name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == '.py':
        try:
            compile(data.decode('utf-8'), str(destination), 'exec')
        except (SyntaxError, UnicodeDecodeError) as error:
            log('skip payload syntax-error %s (%s)' % (name, error))
            return False
    _write(destination, data)
    log('installed %s' % (destination,))
    return True


def append_fragment(path, marker, fragment_name):
    if not path.is_file():
        log('skip missing %s' % (path,))
        return False
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return False
    fragment = PAYLOAD / fragment_name
    if not fragment.is_file():
        log('skip missing fragment %s' % (fragment,))
        return False
    updated = text.rstrip() + '\n\n\n# ' + marker + '\n' + fragment.read_text(encoding='utf-8').rstrip() + '\n'
    try:
        compile(updated, str(path), 'exec')
    except SyntaxError as error:
        log('skip syntax-error %s (%s)' % (path, error))
        return False
    saved = _backup(path)
    _write(path, updated.encode('utf-8'))
    log('patched %s (backup %s)' % (path, saved.name))
    return True


# ---------------------------------------------------------------- backend role
CONTRACT = ROOT / 'backend' / 'service' / 'algorithm_configuration_contract.py'
CONTRACT_ANCHOR = "    type_id = str(field(template, 'model_template_config_type_id', ''))\n"
GATE_V1_LINE = "    if type_id == '4' and name == '闸机尾随':\n"
GATE_V2_LINES = (
    "    # SITE_PATCH_GATE_WIZARD_V2: legacy gate templates enabled for 新增算法配置 wizard\n"
    "    if type_id == '4' and name in ('闸机尾随', '跨越闸机'):\n")


def ensure_gate():
    if not CONTRACT.is_file():
        log('skip missing %s' % (CONTRACT,))
        return False
    text = CONTRACT.read_text(encoding='utf-8')
    if 'SITE_PATCH_GATE_WIZARD_V2' in text:
        return False
    if GATE_V1_LINE in text:
        updated = text.replace(GATE_V1_LINE, GATE_V2_LINES, 1)
    elif CONTRACT_ANCHOR in text:
        updated = text.replace(CONTRACT_ANCHOR, CONTRACT_ANCHOR + GATE_V2_LINES, 1)
    else:
        log('skip gate-anchor-missing %s' % (CONTRACT,))
        return False
    try:
        compile(updated, str(CONTRACT), 'exec')
    except SyntaxError as error:
        log('skip syntax-error gate (%s)' % (error,))
        return False
    saved = _backup(CONTRACT)
    _write(CONTRACT, updated.encode('utf-8'))
    log('patched %s (backup %s)' % (CONTRACT, saved.name))
    return True


VQD = ROOT / 'backend' / 'tool' / 'VQD.py'
VQD_OLD = '"rtsp_transport;tcp|analyzeduration;1000000|probesize;1048576"'
VQD_NEW = '"rtsp_transport;tcp|probesize;1048576"  # SITE_PATCH_VQD_HEVC_V1'

DIAG = ROOT / 'backend' / 'service' / 'vqd_diagnosis.py'
DIAG_OLD = '            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 6000,'
DIAG_NEW = ('            # SITE_PATCH_VQD_HEVC_V1\n'
            '            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000,')


# ---------------------------------------------------------------- engine role
RTSP = ENGINE / 'templates' / 'rtsp_infer_push.py'
RTSP_POSTPROC_OLD = (
    "                        boxes, classes, scores = y8.postprocess(\n"
    "                            pred, w, h, ratio, txy, obj_th, nms_th)\n"
    "                        if boxes is not None:\n"
    "                            for box, score, cl in zip(boxes, scores, classes):\n"
    "                                if score < obj_th:\n"
    "                                    continue\n"
    "                                cl_int = int(cl)\n"
    "                                if cat and cl_int not in cat:\n"
    "                                    continue\n"
    "                                xmin, ymin, xmax, ymax = box\n"
    "                                if has_regions and not _box_in_polygons(\n"
    "                                        (xmin, ymin, xmax, ymax), regions_np):\n"
    "                                    continue\n"
    "                                results.append([cl_int, '%.2f' % score,\n"
    "                                                [int(xmin), int(ymin), int(xmax), int(ymax)]])\n")
RTSP_POSTPROC_NEW = (
    "                        if m.get('pose'):\n"
    "                            # SITE_PATCH_CROSSING_POSE_V1: YOLOv8-pose keypoints\n"
    "                            boxes, classes, scores, keypoints = y8.postprocess_pose(\n"
    "                                pred, w, h, ratio, txy, obj_th, nms_th,\n"
    "                                kpt_num=int(m.get('kpt_num', 17)))\n"
    "                        else:\n"
    "                            boxes, classes, scores = y8.postprocess(\n"
    "                                pred, w, h, ratio, txy, obj_th, nms_th)\n"
    "                            keypoints = None\n"
    "                        if boxes is not None:\n"
    "                            for bi, (box, score, cl) in enumerate(zip(boxes, scores, classes)):\n"
    "                                if score < obj_th:\n"
    "                                    continue\n"
    "                                cl_int = int(cl)\n"
    "                                if cat and cl_int not in cat:\n"
    "                                    continue\n"
    "                                xmin, ymin, xmax, ymax = box\n"
    "                                if has_regions and not _box_in_polygons(\n"
    "                                        (xmin, ymin, xmax, ymax), regions_np):\n"
    "                                    continue\n"
    "                                if keypoints is not None:\n"
    "                                    results.append([cl_int, '%.2f' % score,\n"
    "                                                    [int(xmin), int(ymin), int(xmax), int(ymax)],\n"
    "                                                    keypoints[bi].tolist()])\n"
    "                                else:\n"
    "                                    results.append([cl_int, '%.2f' % score,\n"
    "                                                    [int(xmin), int(ymin), int(xmax), int(ymax)]])\n")

RTSP_RESULTS_OLD = (
    "    for cid, score, box in results:\n"
    "        try:\n"
    "            cid_i = int(cid)\n")
RTSP_RESULTS_NEW = (
    "    # SITE_PATCH_RESULTS_ROW_V1: pose rows carry an extra keypoints column\n"
    "    for row in results:\n"
    "        cid, score, box = row[0], row[1], row[2]\n"
    "        try:\n"
    "            cid_i = int(cid)\n")

MODEL_START = ENGINE / 'model_start.py'
GROUP_OLD = "    if tcid == 4 and f['template_name'] in ('领导换班', '闸机尾随'):  # TAILGATE_DISPATCH_V1\n"
GROUP_NEW = "    if tcid == 4 and f['template_name'] in ('领导换班', '闸机尾随', '跨越闸机'):  # TAILGATE_DISPATCH_V1 CROSSING_GROUPABLE_V1\n"

ROUTE_OLD = (
    "    if tcid == 4 and f['template_name'] == '闸机尾随':  # TAILGATE_DISPATCH_V1\n"
    "        from templates import tailgate\n"
    "        logging.info(\"{}执行闸机尾随模板\".format(f['conf_name']))\n"
    "        return tailgate.build_spec(*common, f['cross_line_area'],\n"
    "                                   label_prefix=label_prefix, names_cn=names_cn,\n"
    "                                   Mine_id=f['Mine_id'], mine_code=f['mine_code'],\n"
    "                                   region_color=region_color)\n")
ROUTE_NEW = ROUTE_OLD + (
    "\n    if tcid == 4 and f['template_name'] == '跨越闸机':  # CROSSING_DISPATCH_V1\n"
    "        from templates import crossing\n"
    "        logging.info(\"{}执行跨越闸机模板\".format(f['conf_name']))\n"
    "        return crossing.build_spec(*common, f['cross_line_area'],\n"
    "                                  label_prefix=label_prefix, names_cn=names_cn,\n"
    "                                  Mine_id=f['Mine_id'], mine_code=f['mine_code'],\n"
    "                                  region_color=region_color)\n")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == 'run':
        role = sys.argv[2]
    else:
        role = sys.argv[1] if len(sys.argv) > 1 else ''
    if role == 'backend':
        log('apply start role=backend')
        changed = 0
        changed += 1 if ensure_gate() else 0
        changed += 1 if replace_once(VQD, VQD_OLD, VQD_NEW, 'SITE_PATCH_VQD_HEVC_V1') else 0
        changed += 1 if replace_once(DIAG, DIAG_OLD, DIAG_NEW, 'SITE_PATCH_VQD_HEVC_V1') else 0
        log('apply done role=backend changed=%d' % changed)
    elif role == 'algorithm-master':
        log('apply start role=algorithm-master')
        changed = 0
        changed += 1 if copy_payload('crossing.py', ENGINE / 'templates' / 'crossing.py') else 0
        changed += 1 if append_fragment(ENGINE / 'models' / 'yolov8_sophon.py',
                                        'SITE_PATCH_CROSSING_POSE_V1', 'postprocess_pose.pyfrag') else 0
        changed += 1 if replace_once(RTSP, RTSP_POSTPROC_OLD, RTSP_POSTPROC_NEW,
                                     'SITE_PATCH_CROSSING_POSE_V1', expect=1) else 0
        changed += 1 if replace_once(RTSP, RTSP_RESULTS_OLD, RTSP_RESULTS_NEW,
                                     'SITE_PATCH_RESULTS_ROW_V1', expect=1) else 0
        changed += 1 if replace_once(MODEL_START, GROUP_OLD, GROUP_NEW,
                                     'CROSSING_GROUPABLE_V1', expect=1) else 0
        changed += 1 if replace_once(MODEL_START, ROUTE_OLD, ROUTE_NEW,
                                     'CROSSING_DISPATCH_V1', expect=1) else 0
        log('apply done role=algorithm-master changed=%d' % changed)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        import traceback
        log('apply failed: ' + traceback.format_exc().replace('\n', ' | '))
        sys.exit(0)
