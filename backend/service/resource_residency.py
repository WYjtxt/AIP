"""Short-lived evidence that resuming a task will reuse a loaded shared worker.

Installed unchanged as both comm.resource_residency and service.resource_residency.
The backend has a separate PID namespace, so it checks authenticated local runtime
files and recent worker telemetry, never an unrelated backend /proc PID.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time


CONFIG_SOURCE_SQL = """SELECT a.*,
            c.id AS Mine_id, c.mine_name, c.mine_code,
            d.id AS Equipment_id,
            d.equipment_name,
            d.equipment_type,
            d.manufacturer_type,
            d.equipment_port,
            d.Hik_indexCode, d.Hik_rtsp_url,
            hp.hik_host, hp.hik_port, hp.hik_appKey, hp.hik_appSecret, hp.hik_artemis,
            d.equipment_ip,
            d.equipment_aisles,
            d.code,
            d.online,
            d.GB28181_code,
            a.id AS Conf_id,
            a.Algorithm_library_id,
            a.conf_area,
            e.test_type_ename,
            e.test_type_cname,
            b.algorithm_status,
            b.algorithm_path,
            b.algorithm_name,
            b.algorithm_type_list,
            b.algorithm_trade_type,
            a.status,
            a.conf_name,
            a.shield_status,
            a.tem_conf_area,
            a.draw_type,
            a.confidence,
            a.interval_time,
            a.duration_time,
            a.image_draw_type,
            a.scene_typename,
            a.sensitivity,
            a.image_count,
            a.template_list_area,
            a.computing_id,
            a.template_data,
            a.conf_status,
            a.stream_type,
            a.res_type,
            a.template_small_id,
            h.template_small_name,
            a.model_status,
            a.amp,
            a.alg_select_type,
            a.cross_line_area,
            a.model_two_data,
            a.model_algo_data,
            g.model_name AS template_name,
            g.model_type AS template_type,
            g.model_template_config_type_id AS template_config_type_id,
            a.label_list,
            conf_img_resolution,
            defense_time_start,
            defense_time_end,
            g.model_conf_list AS template_model_conf_list,
            g.id AS template_id,
            h.list_data, 
            d.equipment_uname,
            d.equipment_password,
            v.vcr_type,
            v.vcr_ip,
            v.vcr_username,
            v.vcr_password,
            d.person_count_url,
            a.all_Entering_num,
            a.all_Exiting_num,
            a.resource_id,
            r.dev_id AS resource_dev_id,
            d.zlk_dat_id,
            zb.zlk_rtsp AS _bound_proxy_rtsp,
            zb.cameras_rtsp AS _bound_camera_rtsp,
            zb.equipment_id AS _bound_proxy_equipment_id
            FROM `t_algorithm_config` AS a
            JOIN `t_algorithm_library` AS b ON a.Algorithm_library_id = b.id 
            JOIN `t_mine` AS c ON a.Mine_id = c.id
            JOIN `t_equipment` AS d ON a.Equipment_id = d.id
            LEFT JOIN t_hik_security_platform_up_area ha ON d.Hik_id = ha.id
            LEFT JOIN t_hik_security_platform_info hp ON ha.hik_info_id = hp.id 
            JOIN `t_algorithm_test_type` AS e ON a.Algorithm_test_type_id = e.id 
            LEFT JOIN `t_model_template_config` AS g ON a.model_template_config_id = g.id
            LEFT JOIN `t_model_template_small` AS h ON a.template_small_id = h.id
            LEFT JOIN `t_vcr_data` AS v ON d.VCR_data_id = v.id
            LEFT JOIN `t_resource_usage` AS r ON a.resource_id = r.id AND r.computing_id = a.computing_id
            LEFT JOIN `t_zlk_data` AS zb ON d.zlk_dat_id = zb.id
"""
PROOF_PATH = Path('/data/AIGO/platform_runtime_health/residency.json')
CALIBRATION_ROOT = Path('/data/AIGO/platform_start/platform_ops/state/uniqueness')
TTL = 8.0
# Pipeline telemetry flushes every 3s; the supervisor publishes every 5s.
# Keep the certificate itself short-lived while allowing that independent
# sampling cadence plus a small scheduling margin (normal health allows 15s).
HEARTBEAT_TTL = 12.0
_VOLATILE = frozenset(('status', 'model_status', 'conf_status', 'update_time',
    'conf_time', 'Algorithm_config_ps', 'Entering_num', 'Exiting_num',
    'all_Entering_num', 'all_Exiting_num', 'online', 'person_count_url'))


def configuration_fingerprint(row, labels):
    # The common SELECT includes a.* before joins. Hash the original values,
    # before runtime path/coordinate conversions; retain no credentials in files.
    stable = {key: value for key, value in row.items()
              if key not in _VOLATILE and not key.startswith('_residency_')}
    raw = json.dumps([stable, list(labels)], sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def calibration_fingerprint(conf_id, root=CALIBRATION_ROOT):
    try:
        return hashlib.sha256((Path(root) / ('config-%d.json' % int(conf_id))).read_bytes()).hexdigest()
    except FileNotFoundError:
        return 'missing'
    except OSError:
        return None  # Admission loses its proof; ordinary scheduler work continues.


def fresh(stamp, now, ttl=TTL):
    return (isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            and math.isfinite(stamp) and 0 <= now - stamp <= ttl)


def task_success(task, conf_id):
    if str(task.get('conf_id')) != str(conf_id) or task.get('inference_complete', 0) <= 0:
        return False
    if task.get('callback_required') and task.get('callback_success', 0) <= 0:
        return False
    for error, success in (('infer_error', 'inference_complete'),
                           ('postprocess_error', 'inference_complete'),
                           ('callback_error', 'callback_success')):
        if task.get('last_' + error + '_monotonic', 0) > task.get('last_' + success + '_monotonic', 0):
            return False
    return True


def make_proof(row, record, transition, metrics, peer, now):
    try:
        return _make_proof(row, record, transition, metrics, peer, now)
    except (KeyError, TypeError, ValueError, OSError):
        return None


def _make_proof(row, record, transition, metrics, peer, now):
    """Caller supplies a different peer whose current epoch has healthy video."""
    if not record.get('proc') or not record['proc'].is_alive():
        return None
    if (not transition.get('ever_completed') or not transition.get('resident')
            or not fresh(transition.get('resident_mono'), now, 1.0)):
        return None
    conf_id = str(row['Conf_id'])
    if not row.get('_residency_fingerprint') or not row.get('_residency_calibration'):
        return None
    if (not peer or not peer.get('healthy') or str(peer['conf_id']) == conf_id
            or peer.get('worker_pid') != record['pid']
            or peer.get('generation') != record['generation']):
        return None
    if (not metrics or metrics.get('pid') != record['pid']
            or str(metrics.get('proc_start_ticks')) != str(record.get('start_ticks'))
            or metrics.get('generation') != record['generation']
            or not fresh(metrics.get('monotonic'), now, HEARTBEAT_TTL)
            or metrics.get('flags', {}).get('phase') != 'processing'
            or conf_id not in [str(i) for i in metrics.get('conf_ids', [])]):
        return None
    task = metrics.get('tasks', {}).get(str(row['conf_name']), {})
    if not task_success(task, conf_id):
        return None
    session_started=metrics.get('session_started_mono')
    if (not isinstance(session_started,(float,int))
            or task.get('last_inference_complete_monotonic',0)<session_started
            or task.get('callback_required') and task.get('last_callback_success_monotonic',0)<session_started):
        return None
    return dict(conf_id=int(conf_id), configuration_fingerprint=row['_residency_fingerprint'],
        calibration_fingerprint=row['_residency_calibration'], worker_pid=record['pid'],
        start_ticks=record['start_ticks'], generation=record['generation'],
        worker_session=metrics.get('session'), heartbeat_mono=metrics['monotonic'],
        resident_mono=transition['resident_mono'], sampled_mono=now,
        task_epoch=transition['epoch'], completed_epoch=transition['ever_completed'],
        wanted=transition['wanted'], acknowledged_epoch=transition['ack'],
        enabled=transition['enabled'], healthy_peer_id=int(peer['conf_id']),
        state=('running' if transition['wanted'] else 'paused'
               if transition['ack'] == transition['epoch'] and not transition['enabled'] else 'stopping'))


def publish(proofs, path=PROOF_PATH, now=None):
    now = time.monotonic() if now is None else now
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(version=1, master_pid=os.getpid(),
            sampled_mono=now, sampled_at=time.time(), tasks=proofs), ensure_ascii=False), encoding='utf-8')
        os.replace(str(temporary), str(path))
    except OSError:
        # Never preserve a fresh-looking success when writes fail.
        try:
            path.unlink()
        except OSError:
            pass


def validate_proof(document, row, labels, calibration, health, now=None):
    now = time.monotonic() if now is None else now
    if (document.get('version') != 1 or not fresh(document.get('sampled_mono'), now)
            or not fresh(health.get('monotonic'), now)
            or document.get('master_pid') != health.get('master_pid')):
        return False
    conf_id = str(row.get('Conf_id', row.get('id')))
    proof = next((p for p in document.get('tasks', []) if str(p.get('conf_id')) == conf_id), None)
    if (not proof or not all(fresh(proof.get(key), now)
                            for key in ('sampled_mono', 'resident_mono'))
            or not fresh(proof.get('heartbeat_mono'), now, HEARTBEAT_TTL)):
        return False
    if (proof.get('configuration_fingerprint') != configuration_fingerprint(row, labels)
            or proof.get('calibration_fingerprint') != calibration
            or not proof.get('completed_epoch') or not proof.get('worker_pid')
            or not proof.get('start_ticks') or not proof.get('generation')
            or not proof.get('worker_session') or str(proof.get('healthy_peer_id')) == conf_id):
        return False
    # A second, independently published current health view invalidates a proof
    # as soon as the peer fails or the supervisor replaces its process/session.
    peer = next((p for p in health.get('tasks', [])
                 if str(p.get('conf_id')) == str(proof.get('healthy_peer_id'))), {})
    return (peer.get('healthy') is True and peer.get('worker_pid') == proof['worker_pid']
            and peer.get('generation') == proof['generation']
            and peer.get('session') == proof['worker_session'])


def _read_document(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Runtime evidence is too large')
    return json.loads(path.read_text(encoding='utf-8'))


def is_resident_resume(current):
    """Backend predicate; uncertainty always falls back to cold-start admission."""
    try:
        if str(current.status) != '2':
            return False
        from data.exts import db
        from sqlalchemy import text
        result = db.session.execute(text(CONFIG_SOURCE_SQL + ' WHERE a.id=:conf_id'),
                                    {'conf_id': int(current.id)})
        values = result.fetchone()
        if values is None:
            return False
        row = dict(zip(result.keys(), values))
        if str(row.get('status')) != '2':
            return False
        labels = [item[0] for item in db.session.execute(text(
            'SELECT test_type_cname FROM t_algorithm_test_type '
            'WHERE Algorithm_library_id=:library_id ORDER BY id ASC'),
            {'library_id': row['Algorithm_library_id']}).fetchall() if item[0]]
        return validate_proof(_read_document(PROOF_PATH), row, labels,
            calibration_fingerprint(current.id), _read_document(PROOF_PATH.with_name('health.json')))
    except Exception:
        return False
