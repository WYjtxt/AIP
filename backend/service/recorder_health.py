"""Refresh recorder availability without changing the catalogue or opening media proxies."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import socket
from time import monotonic
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth


log = logging.getLogger(__name__)
_previous_failures = {}


def parse_hik_channel_states(body):
    root = ET.fromstring(body)
    if root.tag.rsplit('}', 1)[-1] != 'InputProxyChannelStatusList':
        return {}
    result, seen = {}, set()
    for node in root:
        if node.tag.rsplit('}', 1)[-1] != 'InputProxyChannelStatus':
            continue
        fields = {item.tag.rsplit('}', 1)[-1]: (item.text or '').strip() for item in node}
        channel_id = fields.get('id', '')
        if not channel_id.isdecimal() or len(channel_id) > 10:
            continue
        channel = int(channel_id)
        if not 0 < channel <= 2147483647:
            continue
        if channel in seen:
            result.pop(channel, None)
            continue
        seen.add(channel)
        value = fields.get('online', '').lower()
        if value in ('true', 'false', '1', '0'):
            result[channel] = int(value in ('true', '1'))
    return result


def probe_recorder(recorder):
    _, vendor, method, host, configured_port, username, password = recorder
    if not host or any(c in host for c in '/@?#') or any(c.isspace() for c in host):
        return None, {}
    try:
        port = int(configured_port or 80)
        if not 1 <= port <= 65535:
            return None, {}
    except (TypeError, ValueError):
        return None, {}
    if vendor == '海康' and method == '私有SDK':
        authority = '[{}]'.format(host) if ':' in host else host
        url = 'http://{}:{}/ISAPI/ContentMgmt/InputProxy/channels/status'.format(authority, port)
        received_response = False
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.get(url, auth=HTTPDigestAuth(username or '', password or ''),
                                 timeout=(1.5, 3), stream=True, allow_redirects=False) as response:
                    received_response = True
                    if response.status_code != 200:
                        return True, {}
                    body = bytearray()
                    deadline = monotonic() + 4
                    for part in response.iter_content(32768):
                        body.extend(part)
                        if len(body) > 1024 * 1024 or monotonic() >= deadline:
                            return True, {}
                    return True, parse_hik_channel_states(body)
        except (requests.RequestException, ET.ParseError, ValueError):
            if received_response:
                return True, {}

    # The management endpoint can restart independently of the recorder's RTSP listener.
    for number in dict.fromkeys((port, 554)):
        try:
            with socket.create_connection((host, number), timeout=1.5):
                return True, {}
        except OSError:
            continue
    return False, {}


def _apply_result(recorder, online, states):
    from model.admin import db
    from model.equipment import Equipment, VCR_data
    from sqlalchemy import or_

    recorder_id, vendor, method, host, port, username, password = recorder
    current = db.session.query(VCR_data).filter_by(id=recorder_id, type='1').with_for_update().first()
    if (current is None or
            (current.vcr_type, current.vcr_way, current.vcr_ip, current.vcr_port, current.vcr_username,
             current.vcr_password) != (vendor, method, host, port, username, password)):
        db.session.rollback()
        return
    current.online = int(online)
    devices = db.session.query(Equipment).filter_by(VCR_data_id=recorder_id, equipment_type='录像机')

    def update(query, value):
        query.filter(or_(Equipment.online.is_(None), Equipment.online != value)).update(
            {Equipment.online: value}, synchronize_session=False)

    if online:
        update(devices.filter(Equipment.parent_id.is_(None)), 1)
        children = devices.filter(Equipment.parent_id.isnot(None))
        for value in (0, 1):
            ids = [channel for channel, state in states.items() if state == value]
            if ids:
                update(children.filter(Equipment.equipment_aisles.in_(ids)), value)
    else:
        update(devices, 0)
    db.session.commit()


def refresh_registered_recorders():
    from model.admin import db
    from model.equipment import VCR_data

    rows = db.session.query(VCR_data.id, VCR_data.vcr_type, VCR_data.vcr_way,
                            VCR_data.vcr_ip, VCR_data.vcr_port, VCR_data.vcr_username,
                            VCR_data.vcr_password).filter(VCR_data.type == '1').all()
    recorders = [tuple(row) for row in rows]
    db.session.remove()
    active_ids = {row[0] for row in recorders}
    for recorder_id in list(_previous_failures):
        if recorder_id not in active_ids:
            _previous_failures.pop(recorder_id, None)
    if not recorders:
        return
    with ThreadPoolExecutor(max_workers=min(4, len(recorders))) as pool:
        jobs = {pool.submit(probe_recorder, row): row for row in recorders}
        for job in as_completed(jobs):
            row = jobs[job]
            try:
                online, states = job.result()
                if online is False:
                    previous = _previous_failures.get(row[0])
                    _previous_failures[row[0]] = row[1:5]
                    if previous != row[1:5]:
                        continue
                else:
                    _previous_failures.pop(row[0], None)
                    if online is None:
                        continue
                _apply_result(row, online, states)
            except Exception as exc:
                db.session.rollback()
                log.warning('录像机 %s 状态刷新失败 (%s)', row[0], type(exc).__name__)
            finally:
                db.session.remove()
