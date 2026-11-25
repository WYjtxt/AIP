"""Small source repairs for native backend deployments; never modify site data."""
from pathlib import Path
import ast
import re


def _source_node_end(tree, target, lines):
    """Exclusive source-line boundary, including on Python without end_lineno."""
    end = getattr(target, 'end_lineno', None)
    if end is not None:
        return end
    for parent in ast.walk(tree):
        for _, values in ast.iter_fields(parent):
            if not isinstance(values, list):
                continue
            for index, child in enumerate(values):
                if child is not target:
                    continue
                following = [item for item in values[index + 1:] if isinstance(item, ast.stmt)]
                if following:
                    sibling = following[0]
                    return min([sibling.lineno] + [item.lineno for item in getattr(sibling, 'decorator_list', [])]) - 1
                return len(lines) if parent is tree else _source_node_end(tree, parent, lines)
    raise ValueError('无法定位源码函数边界')


NATIVE_VERSION = '''"""Read the native platform release for the existing About endpoint."""
import json
import os
from pathlib import Path

INSTALL_ROOT = Path(os.environ.get('PLATFORM_NATIVE_ROOT', str(Path(__file__).resolve().parents[2])))
STATE = Path(os.environ.get('PLATFORM_OPS_STATE_DIR', str(INSTALL_ROOT / 'platform_ops/state')))


def read_native_version():
    for path in (STATE / 'release.json', INSTALL_ROOT / 'native-deployment.json'):
        try:
            source = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            continue
        record = json.loads(source)
        version = record.get('release') if isinstance(record, dict) else None
        if not isinstance(version, str) or not version.strip():
            raise ValueError('Native release label unavailable')
        return version.strip()
    raise ValueError('Native release record unavailable')


def backend_version_response():
    try:
        return {'code': 200, 'msg': '查询成功', 'data': read_native_version()}
    except (OSError, ValueError):
        return {'code': 503, 'msg': '暂时无法读取平台版本，请稍后重试'}
'''


def patch_native_version(root):
    """Keep the About response contract while replacing container-only lookup."""
    path = Path(root) / 'backend/common/image_version.py'
    if path.is_file() and path.read_text(encoding='utf-8') == NATIVE_VERSION:
        return []
    compile(NATIVE_VERSION, str(path), 'exec')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(NATIVE_VERSION)
    return ['common/image_version.py']


def patch_native_alarm_details(root):
    """Expose the alarm's analysis type separately from its warning message."""
    path = Path(root) / 'backend/service/algorithm_model_service.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-alarm-detail-analysis-v1'
    if marker in source:
        return []
    before = "            'algorithm_name': row.warning_message if row.warning_message is not None else row.algorithm_name,\n"
    if source.count(before) != 1:
        raise ValueError('无法定位报警弹窗解析类型补丁入口')
    source = marker + '\n' + source.replace(before,
        "            'analysis_type': row.algorithm_name,\n" + before)
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as output:
        output.write(source)
    return ['service/algorithm_model_service.py']


def patch_native_diagnosis_runtime(root):
    """Bound RTSP startup probing and retain the built-in diagnosis item alias."""
    changed = []
    path = Path(root) / 'backend/service/vqd_diagnosis.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-runtime-alias-v1'
    if marker not in source:
        before = "    thresholds = {row['name']: (int(row['prewarn_threshold']), int(row['warn_threshold'])) for row in owner.data2}"
        after = ("    thresholds = {('滚动条纹' if row['name'] == '滚动干扰' else row['name']):\n"
                 "                  (int(row['prewarn_threshold']), int(row['warn_threshold'])) for row in owner.data2}")
        if source.count(before) != 1:
            raise ValueError('无法定位诊断项目阈值名称映射')
        source = marker + '\n' + source.replace(before, after, 1)
        compile(source, str(path), 'exec')
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        changed.append('service/vqd_diagnosis.py')

    path = Path(root) / 'backend/tool/VQD.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-bounded-probe-v1'
    if marker in source:
        return changed
    before = 'rtsp_transport;tcp|buffer_size;92160000|analyzeduration;900000000|probesize;900000000'
    after = 'rtsp_transport;tcp|analyzeduration;1000000|probesize;1048576'
    if source.count(before) != 1:
        raise ValueError('无法定位诊断取流探测参数')
    source = marker + '\n' + source.replace(before, after, 1)
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(source)
    changed.append('tool/VQD.py')
    return changed


def patch_native_diagnosis_rating(root):
    """Rate completed checks only, while retaining explicit execution failures."""
    changed = []
    path = Path(root) / 'backend/service/vqd_diagnosis.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-rating-v1'
    if marker not in source:
        start = source.index('def _row(source, statuses, image, reason):\n')
        end = source.index("    return [str(source['id'])", start)
        source = source[:start] + '''def _row(source, statuses, image, reason, failed=False):
    checked = [value for value in statuses if value != '未检测']
    if failed or '检测失败' in checked:
        overall = '失败'
    elif '报警' in checked:
        overall = '很差'
    elif '预警' in checked:
        overall = '一般'
    elif checked and all(value == '正常' for value in checked):
        overall = '达标'
    else:
        overall = '未检测'
''' + source[end:]
        for before, after in (
            ("return _row(source, ['未检测'] * len(ITEMS), '', reason)",
             "return _row(source, ['未检测'] * len(ITEMS), '', reason, failed=True)"),
            ("return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但解码连接建立失败')",
             "return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但解码连接建立失败', failed=True)"),
            ("return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但没有收到可解码的有效画面')",
             "return _row(source, ['未检测'] * len(ITEMS), '', '视频源已连通，但没有收到可解码的有效画面', failed=True)"),
            ("return _row(source, [results[label] for label in LABELS], image, notes)",
             "return _row(source, [results[label] for label in LABELS], image, notes, failed=details.get('failed', False))"),
        ):
            source = _replace(source, before, after)
        source = marker + '\n' + source
        compile(source, str(path), 'exec')
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        changed.append('service/vqd_diagnosis.py')

    path = Path(root) / 'backend/service/vqd_quality.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-sampling-failure-v1'
    if marker not in source:
        source = _replace(source,
            "{'reason': '有效采样不足，无法可靠判断画质', 'samples': count}",
            "{'reason': '有效采样不足，无法可靠判断画质', 'samples': count, 'failed': True}")
        source = marker + '\n' + source
        compile(source, str(path), 'exec')
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        changed.append('service/vqd_quality.py')
    return changed


VQD_AUTO_REFERENCE = '''"""Establish a fixed per-source reference once from a usable diagnostic window."""
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
        temporary.write_text(json.dumps({'auto_reference_enabled': enabled}) + '\\n', encoding='utf-8')
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
'''


AUTO_REFERENCE_SETTINGS_ENDPOINT = '''


# native-diagnosis-auto-reference-settings-v1
@model_views.route('/diagnosis_reference_settings', methods=['GET', 'POST'])
@jwt_required_with_refresh
def diagnosis_reference_settings():
    from service.vqd_auto_reference import get_settings, write_settings
    from service.vqd_reference import can_set_reference
    if request.method == 'POST':
        if not can_set_reference():
            return jsonify({'code': 403, 'msg': '当前账号没有诊断配置修改权限'}), 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get('auto_reference_enabled')) is not bool:
            return jsonify({'code': 400, 'msg': '自动建立基准开关必须为布尔值'}), 400
        try:
            settings = write_settings(payload['auto_reference_enabled'])
        except (OSError, ValueError):
            return jsonify({'code': 503, 'msg': '自动基准设置保存失败'}), 503
        return jsonify({'code': 200, 'msg': '自动基准设置已保存', 'data': settings})
    try:
        return jsonify({'code': 200, 'data': get_settings()})
    except (OSError, ValueError):
        return jsonify({'code': 503, 'msg': '自动基准设置读取失败'}), 503
'''


def patch_native_diagnosis_auto_reference(root):
    """Enable an editable, once-per-source diagnostic reference without DB changes."""
    backend = Path(root) / 'backend'
    changed = []
    diagnosis = backend / 'service/vqd_diagnosis.py'
    source = diagnosis.read_text(encoding='utf-8')
    marker = '# native-diagnosis-auto-reference-v1'
    if marker not in source:
        source = marker + '\nfrom service.vqd_auto_reference import ensure_reference\n' + source
        source = _replace(source,
            "        reference = load_reference(source['id'], url)\n",
            "        reference = load_reference(source['id'], url)\n"
            "        reference_note = ''\n"
            "        if reference is None and any(label in thresholds for label in ('视频遮挡', '偏色', '清晰度', '场景变化', '对比度')):\n"
            "            reference, reference_note = ensure_reference(\n"
            "                source['id'], url, frames, times, failures, reference=reference)\n")
        source = _replace(source,
            "        notes = details['reason']\n",
            "        notes = details['reason']\n"
            "        if reference_note:\n"
            "            notes = (notes + '；' if notes else '') + reference_note\n")
        compile(source, str(diagnosis), 'exec')
        with diagnosis.open('w', encoding='utf-8', newline='\n') as output:
            output.write(source)
        changed.append('service/vqd_diagnosis.py')
    helper = backend / 'service/vqd_auto_reference.py'
    if not helper.is_file() or helper.read_text(encoding='utf-8') != VQD_AUTO_REFERENCE:
        compile(VQD_AUTO_REFERENCE, str(helper), 'exec')
        with helper.open('w', encoding='utf-8', newline='\n') as output:
            output.write(VQD_AUTO_REFERENCE)
        changed.append('service/vqd_auto_reference.py')
    quality = backend / 'service/vqd_quality.py'
    source = quality.read_text(encoding='utf-8')
    if '# native-diagnosis-reference-origin-v1' not in source:
        source = _replace(source,
            'def save_reference(equipment_id, source, frame):',
            'def save_reference(equipment_id, source, frame, automatic=False):')
        source = _replace(source,
            'created=np.array(time.time()))',
            'created=np.array(time.time()), automatic=np.array(bool(automatic)))')
        source = '# native-diagnosis-reference-origin-v1\n' + source
        compile(source, str(quality), 'exec')
        with quality.open('w', encoding='utf-8', newline='\n') as output:
            output.write(source)
        changed.append('service/vqd_quality.py')
    app = backend / 'apps/model_views.py'
    source = app.read_text(encoding='utf-8')
    if '# native-diagnosis-auto-reference-settings-v1' not in source:
        source += AUTO_REFERENCE_SETTINGS_ENDPOINT
        compile(source, str(app), 'exec')
        with app.open('w', encoding='utf-8', newline='\n') as output:
            output.write(source)
        changed.append('apps/model_views.py')
    return changed


def patch_native_diagnosis_configuration(root):
    """Keep diagnosis creation and enabled/disabled status contracts consistent."""
    changed = []
    path = Path(root) / 'backend/apps/scheduler_task.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-configuration-v1'
    if marker not in source:
        before = "    return jsonify({'msg': '任务已添加', 'task_id': result.id})"
        if source.count(before) != 1:
            raise ValueError('无法定位诊断方案新增响应')
        source = marker + '\n' + source.replace(before,
            "    return jsonify({'code': 200, 'msg': '任务已添加', 'task_id': result.id})", 1)
        compile(source, str(path), 'exec')
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        changed.append('apps/scheduler_task.py')

    path = Path(root) / 'backend/service/scheduler_task_service.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-diagnosis-status-v1'
    if marker not in source:
        for variable in ('i', 'task'):
            before = "vcr_status[int({0}.scheduled_status) - 1]['value'] if {0}.scheduled_status else ''".format(variable)
            after = "'启用' if str({0}.scheduled_status) == '1' else '禁用'".format(variable)
            if source.count(before) != 1:
                raise ValueError('无法定位诊断方案状态显示：' + variable)
            source = source.replace(before, after, 1)
        source = marker + '\n' + source
        compile(source, str(path), 'exec')
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        changed.append('service/scheduler_task_service.py')
    return changed


def patch_native_model_bootstrap(root):
    """Allow initial model import to target only the deployment's own server."""
    path = Path(root) / 'backend/service/algorithm_model_service.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-model-bootstrap-target-v1'
    if marker in source:
        return []
    signature = 'def handle_algorithm_upload_single(uploaded_file, algorithm_status, algorithm_ps):'
    if source.count(signature) != 1:
        raise ValueError('无法定位预安装模型的单包上传入口')
    start = source.index(signature)
    end = source.find('\ndef ', start + len(signature))
    if end == -1:
        end = len(source)
    original = source[start:end]
    before = ('    computing_info = db.session.query(Computing_equipment).filter(\n'
              '        Computing_equipment.server_type == 1\n'
              '    ).all()')
    after = ('    computing_query = db.session.query(Computing_equipment).filter(\n'
             '        Computing_equipment.server_type == 1\n'
             '    )\n'
             '    if computing_ids is not None:\n'
             '        computing_query = computing_query.filter(Computing_equipment.id.in_(computing_ids))\n'
             '    computing_info = computing_query.all()')
    if original.count(before) != 1:
        raise ValueError('无法定位预安装模型的算力设备筛选')
    updated = original.replace(signature, signature[:-2] + ', computing_ids=None):', 1).replace(before, after, 1)
    source = marker + '\n' + source[:start] + updated + source[end:]
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as output:
        output.write(source)
    return ['service/algorithm_model_service.py']


def patch_native_preview_recovery(root):
    """Restore an owned Onvif profile without inventing a numeric channel."""
    backend = Path(root) / 'backend'
    marker = '# native-onvif-bound-preview-v1'
    outputs = {}
    path = backend / 'service/preview_source_service.py'
    source = path.read_text(encoding='utf-8')
    if marker not in source:
        start = source.index("    elif vendor == '大华' and equipment.Onvif_rtsp_url:\n")
        end = source.index("    else:\n        raise CompatError(409, '该录像机通道", start)
        onvif = source[start:end].replace('    elif ', '    if ', 1)
        source = source[:start] + source[end:]
        before = '    channel = equipment.equipment_aisles\n'
        source = _replace(source, before, onvif + before)
        outputs[path] = marker + '\n' + source

    path = backend / 'service/preview_service.py'
    source = path.read_text(encoding='utf-8')
    if marker not in source:
        source = _replace(source,
            "                       and getattr(row, 'equipment_aisles', None)\n",
            "                       and (getattr(row, 'equipment_aisles', None) or (\n"
            "                           getattr(row, 'parent_vendor', '') == '大华'\n"
            "                           and getattr(row, 'source_onvif_url', None)\n"
            "                           and str(getattr(row, 'binding_owner', None)) == str(row.id)))\n")
        source = _replace(source,
            "        Equipment.online.label('source_online'), parent.manufacturer_type.label('parent_vendor'),\n",
            "        Equipment.online.label('source_online'), parent.manufacturer_type.label('parent_vendor'),\n"
            "        Equipment.Onvif_rtsp_url.label('source_onvif_url'), Zlk_data.equipment_id.label('binding_owner'),\n")
        outputs[path] = marker + '\n' + source
    for path, source in outputs.items():
        compile(source, str(path), 'exec')
    for path, source in outputs.items():
        with path.open('w', encoding='utf-8', newline='\n') as output:
            output.write(source)
    return [str(path.relative_to(backend)).replace('\\', '/') for path in outputs]


RECORDER_IDENTITY = '''"""Identify recorder channels and stream owners without using a shared IP."""


def channel_key(value):
    text = str(value).strip() if value is not None else ''
    return str(int(text)) if text.isdigit() else text


def plan_binding_complements(devices, sources):
    """Return (device ID, source ID) pairs only for explicit, unclaimed owners."""
    claimed = {item.zlk_dat_id for item in devices if item.zlk_dat_id is not None}
    by_owner = {}
    for source in sorted(sources, key=lambda item: item.id, reverse=True):
        owner = channel_key(source.equipment_id)
        if owner and source.id not in claimed:
            by_owner.setdefault(owner, source.id)
    result = []
    for device in devices:
        if device.zlk_dat_id is not None:
            continue
        source_id = by_owner.get(channel_key(device.id))
        if source_id is not None and source_id not in claimed:
            result.append((device.id, source_id))
            claimed.add(source_id)
    return result
'''


BINDING_BATCH = '''"""Complement unbound devices only from an explicit stream ownership record."""
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from service.recorder_binding_identity import plan_binding_complements


def planned_binding_complements():
    devices = db.session.query(Equipment.id, Equipment.zlk_dat_id).all()
    sources = db.session.query(Zlk_data.id, Zlk_data.equipment_id).all()
    return plan_binding_complements(devices, sources)


def complement_unbound_devices():
    """Keep existing associations and commit explicit, unclaimed owners together."""
    try:
        count = 0
        for equipment_id, source_id in planned_binding_complements():
            count += db.session.query(Equipment).filter(
                Equipment.id == equipment_id,
                Equipment.zlk_dat_id.is_(None)).update(
                    {Equipment.zlk_dat_id: source_id}, synchronize_session=False)
        db.session.commit()
        return count
    except Exception:
        db.session.rollback()
        raise
'''


CAMERA_IP_ENDPOINT = '''

# native-camera-ip-endpoint-v1
@model_view.route('/sync_aicam_ip', methods=['POST'])
@jwt_required_with_refresh
def sync_aicam_ip():
    """Report the available IP maintenance action without changing devices."""
    count = db.session.query(Equipment.id).filter(
        Equipment.equipment_type.in_(('AI单光摄像头', 'AI双光摄像头'))).count()
    data = {'total': count, 'synced': 0}
    if count == 0:
        return jsonify({'code': 200, 'msg': '暂无AI摄像头需要同步', 'data': data})
    return jsonify({
        'code': 400,
        'msg': '当前版本未提供AI摄像头自动IP同步，请通过设备编辑维护IP。',
        'data': data})
'''


MODEL_INPUT_CONTRACTS = '''"""Preserve an uploaded OM's explicit input contract without inferring its type."""
import hashlib
import json
import uuid
from service.algorithm_package_validation import AlgorithmPackageError, _decoded_name, _entries


def read_model_input_contract(archive, model_member, model_content):
    if not str(model_member).casefold().endswith('.om'):
        return None
    model_name = _decoded_name(archive.getinfo(model_member)).replace('\\\\', '/')
    expected = (model_name + '.input.json').casefold()
    matches = [info for info, name in _entries(archive) if name.casefold() == expected]
    if not matches:
        return None
    info = matches[0]
    if info.file_size > 64 * 1024:
        raise AlgorithmPackageError('模型输入合同超过64KB')
    content = archive.read(info)
    try:
        contract = json.loads(content.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise AlgorithmPackageError('模型输入合同必须是UTF-8 JSON')
    expected_sha = hashlib.sha256(model_content).hexdigest()
    if not isinstance(contract, dict) or contract.get('om_sha256') != expected_sha:
        raise AlgorithmPackageError('模型输入合同的OM SHA256不匹配，未上传模型')
    return content


def install_model_input_contract(server, model_path, model_sha256, contract):
    """Verify a possibly pre-existing OM, then atomically install its contract."""
    ssh, status = server.connect_ssh()
    if status != 1:
        raise AlgorithmPackageError('无法连接目标服务器核验模型输入合同')
    sftp = ssh.open_sftp()
    destination = model_path + '.input.json'
    temporary = destination + '.upload-' + uuid.uuid4().hex
    try:
        checksum = hashlib.sha256()
        with sftp.open(model_path, 'rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                checksum.update(block)
        if checksum.hexdigest() != model_sha256:
            raise AlgorithmPackageError('远端同名OM与上传内容的SHA256不一致，未修改旧模型或登记算法')
        try:
            with sftp.open(destination, 'rb') as current:
                if current.read(64 * 1024 + 1) == contract:
                    return
        except IOError:
            pass
        with sftp.open(temporary, 'wb') as output:
            output.write(contract)
            output.flush()
        sftp.posix_rename(temporary, destination)
        with sftp.open(destination, 'rb') as installed:
            if installed.read(64 * 1024 + 1) != contract:
                raise AlgorithmPackageError('远端模型输入合同核验失败，算法尚未登记')
    except AlgorithmPackageError:
        raise
    except Exception:
        raise AlgorithmPackageError('模型输入合同原子安装失败，请重试；算法尚未登记')
    finally:
        try:
            sftp.remove(temporary)
        except IOError:
            pass
        sftp.close()
        ssh.close()


def upload_model_with_contract(upload, servers, model_content, model_filename, archive, model_member):
    contract = read_model_input_contract(archive, model_member, model_content)
    result = upload(servers, model_content, model_filename)
    failures = ('无法上传文件', '上传中断，请稍后重试', '服务器连接异常')
    if contract is not None and not any(item in failures for item in result):
        if len(result) != len(servers):
            raise AlgorithmPackageError('模型输入合同上传失败，请重试；算法尚未登记')
        checksum = hashlib.sha256(model_content).hexdigest()
        for server, path in zip(servers, result):
            install_model_input_contract(server, path, checksum, contract)
    return result
'''


def _replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('无法定位录像机通道关联补丁入口')
    return source.replace(old, new)


def patch_recorder_bindings(root):
    """Patch source only. The caller owns backup, packaging and service restart."""
    backend = Path(root) / 'backend'
    service_path = backend / 'service/equipment_model_service.py'
    jobs_path = backend / 'server_scheduler_jobs.py'
    marker = '# native-recorder-channel-identity-v1'
    service = service_path.read_text(encoding='utf-8')
    jobs = jobs_path.read_text(encoding='utf-8')
    if marker not in service:
        service = marker + '\nfrom service.recorder_binding_identity import channel_key\n' + service
        service = _replace(service,
            '{device.equipment_ip: device for device in child_equipments}',
            '{channel_key(device.equipment_aisles): device for device in child_equipments}')
        service = _replace(service,
            "manufacturer in ['海康', '宇视'] and ip_address in equipment_dict",
            "manufacturer in ['海康', '宇视'] and channel_key(item.get('id')) in equipment_dict")
        service = _replace(service,
            "equipment_dict[ip_address] if manufacturer != '大华' else equipment_dict[name]",
            "equipment_dict[channel_key(item.get('id'))] if manufacturer != '大华' else equipment_dict[name]")
        service = _replace(service,
            'exists = EquipmentData.get_equipment_by_ip(ip_address) is not None',
            "exists = db.session.query(Equipment.id).filter(\n"
            "                Equipment.parent_id == parent_equipment.id,\n"
            "                Equipment.equipment_aisles == item.get('id')).first() is not None")
    if marker not in jobs:
        jobs = marker + '\nfrom service.recorder_binding_identity import channel_key\n' + jobs
        jobs = _replace(jobs,
            '{device.equipment_ip: device for device in db_equipment_list}',
            '{channel_key(device.equipment_aisles): device for device in db_equipment_list}', 2)
        jobs = _replace(jobs, 'if ip_address in db_equipment_dict:',
            'if channel_key(id) in db_equipment_dict:', 2)
        jobs = _replace(jobs, 'db_device = db_equipment_dict[ip_address]',
            'db_device = db_equipment_dict[channel_key(id)]', 2)
        jobs = _replace(jobs,
            'Equipment.equipment_ip == ip_address\n                                            ).first()',
            'Equipment.parent_id == db_equipment_parent_id.id,\n'
            '                                                Equipment.equipment_aisles == id\n'
            '                                            ).first()')
    outputs = {
        service_path: service,
        jobs_path: jobs,
        backend / 'service/recorder_binding_identity.py': RECORDER_IDENTITY,
        backend / 'service/vcr_binding_batch.py': BINDING_BATCH,
    }
    changed = []
    for path, text in outputs.items():
        compile(text, str(path), 'exec')
    for path, text in outputs.items():
        if not path.exists() or path.read_text(encoding='utf-8') != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='\n') as output:
                output.write(text)
            changed.append(str(path.relative_to(backend)))
    return changed


def patch_camera_ip_endpoint(root):
    """Restore the legacy URL with an authenticated, truthful capability result."""
    path = Path(root) / 'backend/apps/model_view.py'
    source = path.read_text(encoding='utf-8')
    if '# native-camera-ip-endpoint-v1' in source:
        return []
    source += CAMERA_IP_ENDPOINT
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as output:
        output.write(source)
    return ['apps/model_view.py']


def patch_model_input_contracts(root):
    """Keep supplied, SHA-matched input contracts beside server-side OM files."""
    backend = Path(root) / 'backend'
    path = backend / 'service/algorithm_model_service.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-model-input-contracts-v1'
    if marker in source:
        return []
    lines = source.splitlines(keepends=True)
    changes = []
    nodes = ast.parse(source).body
    for index, node in enumerate(nodes):
        if isinstance(node, ast.FunctionDef) and node.name in (
                'handle_algorithm_upload_group', 'handle_algorithm_upload_single'):
            end = nodes[index + 1].lineno - 1 if index + 1 < len(nodes) else len(lines)
            original = ''.join(lines[node.lineno - 1:end])
            archive = 'sub_zip_ref' if node.name.endswith('_group') else 'zip_ref'
            pattern = r'(?m)^([ \t]*)res = upload_to_multiple_servers\(SSH_list, extracted_file_content,\s*algorithm_filename\)'
            def replacement(match):
                indent = match.group(1)
                return (indent + 'res = upload_model_with_contract(upload_to_multiple_servers, SSH_list,\n' +
                        indent + '    extracted_file_content, algorithm_filename, ' + archive + ', algorithm_filename_old)')
            updated, count = re.subn(pattern, replacement, original)
            if count != 1:
                raise ValueError('无法定位模型输入合同上传补丁入口')
            changes.append((node.lineno - 1, end, updated))
    if len(changes) != 2:
        raise ValueError('未找到算法单包和组包上传入口')
    for start, end, updated in reversed(changes):
        lines[start:end] = [updated]
    source = (marker + '\nfrom service.model_input_contracts import upload_model_with_contract\n' + ''.join(lines))
    helper = backend / 'service/model_input_contracts.py'
    compile(source, str(path), 'exec')
    compile(MODEL_INPUT_CONTRACTS, str(helper), 'exec')
    for output, text in ((path, source), (helper, MODEL_INPUT_CONTRACTS)):
        with output.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    return ['service/algorithm_model_service.py', 'service/model_input_contracts.py']


def patch_native_user_capabilities(root):
    """Expose enabled super-administrator capability without changing role IDs."""
    path = Path(root) / 'backend/service/user_view_service.py'
    source = path.read_text(encoding='utf-8')
    marker = '# native-user-capabilities-v1'
    if marker in source:
        return []
    login = r"(?m)^([ \t]*)'user_role_id': query\.role_id if query else None,[ \t]*$"
    source, count = re.subn(login, lambda match: match.group(0) + '\n' + match.group(1)
                           + "'is_superadmin': _platform_is_superadmin(user_info.id),", source)
    if count != 2:
        raise ValueError('无法定位登录与免验证码登录的角色能力响应')
    protected = r"(?m)^([ \t]*)'logged_in_as': current_user,[ \t]*$"
    source, count = re.subn(protected, lambda match: match.group(0) + '\n' + match.group(1)
                           + "'is_superadmin': _platform_is_superadmin(user_info.id),", source)
    if count != 1:
        raise ValueError('无法定位当前用户的角色能力响应')
    helper = '''

def _platform_is_superadmin(user_id):
    # Import on request to avoid coupling the user service's module startup.
    from service.resource_admission_settings_api import is_administrator
    return bool(is_administrator(user_id))
'''
    source = marker + '\n' + source.rstrip() + '\n' + helper
    compile(source, str(path), 'exec')
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(source)
    return ['service/user_view_service.py']


ROLE_MANAGEMENT = '''"""Role-menu normalization, atomic saves and built-in account protection."""
import ast
import json

from sqlalchemy import LargeBinary, cast
from data.exts import db
from model.admin import Menu, Permission, PermissionMenu, UserPermission


BUILTIN_SUPERADMIN_CODES = frozenset(('sysadmin', 'bootstrap_superadmin', 'bootstrap-admin'))


def _value(row, key):
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def protected_role(role):
    return _value(role, 'permission_code') in BUILTIN_SUPERADMIN_CODES


def protected_user(user):
    if _value(user, 'username') == 'sysadmin':
        return True
    rows = db.session.query(Permission.permission_code).join(UserPermission,
        cast(Permission.id, LargeBinary) == cast(UserPermission.permission_id, LargeBinary)).filter(
        UserPermission.user_id == _value(user, 'id')).all()
    return any(row[0] in BUILTIN_SUPERADMIN_CODES for row in rows)


def positive_id(value):
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0:
        return int(value)
    raise ValueError('角色或菜单ID必须是正整数')


def role_actions(actions):
    if isinstance(actions, str):
        text = actions.strip()
        try:
            actions = json.loads(text)
        except ValueError:
            try:
                actions = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                if not (text.startswith('[') and text.endswith(']')):
                    raise ValueError('菜单操作权限格式错误')
                actions = [part.strip() for part in text[1:-1].split(',')] if text[1:-1].strip() else []
    if (not isinstance(actions, list) or
            any(type(action) is not str or action not in ('c', 'r', 'u', 'd') for action in actions)):
        raise ValueError('菜单操作只能包含c、r、u、d')
    return [action for action in 'crud' if action in actions]


def canonical_actions(value):
    return '[' + ','.join(role_actions(value)) + ']'


def normalize_role_menus(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError('菜单权限必须是列表')
    combined = {}
    for item in value:
        if not isinstance(item, dict) or not {'menu_id', 'permissions_list'}.issubset(item):
            raise ValueError('菜单权限字段不完整')
        menu_id = positive_id(item['menu_id'])
        actions = role_actions(item['permissions_list'])
        combined.setdefault(menu_id, set()).update(actions)
    # Preserve the original browser/menu reader's unquoted action-list format.
    return [{'menu_id': menu_id, 'permissions_list': '[' + ','.join(action for action in 'crud' if action in actions) + ']'}
            for menu_id, actions in sorted(combined.items()) if actions]


def replace_role_menus(permission_id, value):
    role_id = positive_id(permission_id)
    rows = normalize_role_menus(value)
    session = db.session
    try:
        role = session.query(Permission).filter(Permission.id == role_id).with_for_update().first()
        if role is None:
            raise ValueError('角色不存在')
        ids = {row['menu_id'] for row in rows}
        if ids:
            existing = {row[0] for row in session.query(Menu.id).filter(Menu.id.in_(ids)).all()}
            if ids != existing:
                raise ValueError('菜单不存在，请刷新后重新授权')
        session.query(PermissionMenu).filter(PermissionMenu.premission_id == role_id).delete(synchronize_session=False)
        session.add_all([PermissionMenu(premission_id=role_id, **row) for row in rows])
        session.commit()
    except Exception:
        session.rollback()
        raise
'''


def patch_native_role_management(root):
    """Keep old browser payloads compatible and prevent partial permission saves."""
    import textwrap
    backend = Path(root) / 'backend'
    marker = '# native-role-management-v1'

    def replace_method(source, class_name, name, replacement):
        tree = ast.parse(source)
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        method = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == name)
        start = min([method.lineno] + [node.lineno for node in method.decorator_list]) - 1
        lines = source.splitlines(keepends=True)
        lines[start:_source_node_end(tree, method, lines)] = [textwrap.indent(textwrap.dedent(replacement).strip(), '    ') + '\n']
        return ''.join(lines)

    role_path = backend / 'service/role_view_service.py'
    role = role_path.read_text(encoding='utf-8')
    if marker not in role:
        role = replace_method(role, 'RoleViewService', 'update_permission_menu', '''
            @staticmethod
            def update_permission_menu(permission_id, menu_permissions_list):
                try:
                    replace_role_menus(permission_id, menu_permissions_list)
                    return True, '修改权限对应菜单标识完成！'
                except (TypeError, ValueError) as error:
                    return False, str(error)
                except Exception:
                    return False, '权限保存失败，原有授权已保留，请重试'
        ''')
        before = "            # 删除角色对应的所有权限数据\n"
        if role.count(before) != 1:
            raise ValueError('无法定位内置角色删除保护入口')
        role = role.replace(before, "            if protected_role(permiss_data):\n"
                            "                return False, '内置超级管理员角色不能删除'\n\n" + before, 1)
        before = "                        'permission_code': i.permission_code,"
        if role.count(before) != 1:
            raise ValueError('无法定位角色保护状态响应')
        role = role.replace(before, before + "\n                        'is_protected': protected_role(i),", 1)
        before = "            # 自定义排序函数  按照菜单表自定义顺序来对菜单进行排序\n"
        if role.count(before) != 1:
            raise ValueError('无法定位角色授权读取兼容入口')
        role = role.replace(before, "            for item in menu_list:\n"
                            "                item['permissions_list'] = canonical_actions(item['permissions_list'])\n\n" + before, 1)
        role = marker + '\nfrom service.platform_role_management import protected_role, replace_role_menus, canonical_actions\n' + role

    user_path = backend / 'service/user_view_service.py'
    user = user_path.read_text(encoding='utf-8')
    if marker not in user:
        before = "            # 删除用户数据\n            UserViewData.delete_user(user_id)"
        if user.count(before) != 1:
            raise ValueError('无法定位内置用户删除保护入口')
        user = user.replace(before, "            if protected_user(user_data):\n"
                            "                return False, '内置超级管理员账户不能删除'\n\n" + before, 1)
        before = "            return True ,None,{\n                'data': user_permission_datalist,"
        if user.count(before) != 1:
            raise ValueError('无法定位用户保护状态响应')
        user = user.replace(before, "            for item in user_permission_datalist:\n"
                            "                item['is_protected'] = protected_user(item)\n\n" + before, 1)
        user = marker + '\nfrom service.platform_role_management import protected_user\n' + user

    access_path = backend / 'common/platform_access.py'
    access = access_path.read_text(encoding='utf-8')
    if marker not in access:
        tree = ast.parse(access)
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_valid_role_menu_update')
        lines = access.splitlines(keepends=True)
        lines[method.lineno - 1:_source_node_end(tree, method, lines)] = [textwrap.dedent('''
            def _valid_role_menu_update():
                from service.platform_role_management import normalize_role_menus
                try:
                    normalize_role_menus(_payload().get('permissions_list'))
                    return True
                except (TypeError, ValueError):
                    return False
        ''').strip() + '\n']
        access = marker + '\n' + ''.join(lines)

    menu_path = backend / 'service/menu_service.py'
    menu = menu_path.read_text(encoding='utf-8')
    if marker not in menu:
        menu = replace_method(menu, 'MenuService', 'merge_permissions', '''
            @staticmethod
            def merge_permissions(permission_menu_list):
                combined = {}
                for item in permission_menu_list:
                    try:
                        actions = role_actions(item.get('permissions_list', '[]'))
                    except (TypeError, ValueError):
                        actions = []
                    combined.setdefault(item.get('menu_id'), set()).update(actions)
                return [{'menu_id': menu_id, 'permissions_list': [action for action in 'crud' if action in actions]}
                        for menu_id, actions in combined.items()]
        ''')
        menu = marker + '\nfrom service.platform_role_management import role_actions\n' + menu

    outputs = {role_path: role, user_path: user, access_path: access, menu_path: menu,
               backend / 'service/platform_role_management.py': ROLE_MANAGEMENT}
    for path, source in outputs.items():
        compile(source, str(path), 'exec')
    changed = []
    for path, source in outputs.items():
        if not path.is_file() or path.read_text(encoding='utf-8') != source:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(source)
            changed.append(str(path.relative_to(backend)).replace('\\', '/'))
    return changed
