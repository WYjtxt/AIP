"""Prove alarm-storage capabilities without switching the configured directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, '/data/AIGO/platform_start/platform_ops')
import storage_operations as storage

MEDIA_CONFIG = Path('/data/AIGO/platform_start/platform_gateway/nginx.conf')


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete(manager, runtime_unavailable=False, media_config=MEDIA_CONFIG, wait_seconds=0):
    """Only successful real backend/media checks can create valid readiness."""
    state_file = manager.state / 'storage-readiness.json'
    with manager.lock():
        pending = {'schema': 2, 'inventory_complete': False, 'media_route_ready': False,
                   'checked_at': int(time.time()), 'reason': 'storage verification pending'}
        storage.atomic_json(state_file, pending, 0o600)
        try:
            revision = manager.revision(manager.document())
            if not runtime_unavailable:
                deadline = time.monotonic() + wait_seconds
                while True:
                    try:
                        before = manager.runtime_inventory()
                        break
                    except storage.StorageError:
                        if time.monotonic() >= deadline: raise
                        time.sleep(0.5)
            else:
                before = None
            if runtime_unavailable and manager.driver.runtime_processes():
                raise RuntimeError('Cannot label a running algorithm runtime as unavailable')
            if not manager.driver.shared(manager.volumes):
                raise RuntimeError('Alarm volume root is not a shared mount')
            media_hash = fingerprint(media_config)
            volume_id = uuid.uuid4().hex[:20]
            source = manager.state / ('readiness-probe-' + volume_id)
            slot = manager.volumes / volume_id
            source_created = slot_created = mounted = False
            proof = source / 'proof.txt'
            try:
                source.mkdir(mode=0o755); source_created = True; source.chmod(0o755)
                slot.mkdir(mode=0o755); slot_created = True; slot.chmod(0o755)
                expected = ('oneclick-storage-readiness-' + uuid.uuid4().hex).encode()
                proof.write_bytes(expected); proof.chmod(0o644)
                manager.driver.mount(source, slot); mounted = True
                identity = storage.identity(slot)
                if identity != storage.identity(source):
                    raise RuntimeError('Temporary alarm mount identity mismatch')
                manager.driver.backend_probe(slot, identity, manager.config)
                manager.driver.media_probe(volume_id, proof.name, expected)
            finally:
                if mounted or (slot_created and manager.driver.mounted(slot)):
                    manager.driver.unmount(slot)
                if slot_created:
                    slot.rmdir()
                if source_created:
                    if proof.exists(): proof.unlink()
                    source.rmdir()
            if manager.revision(manager.document()) != revision:
                raise RuntimeError('Alarm registry changed during capability verification')
            if fingerprint(media_config) != media_hash or not manager.driver.shared(manager.volumes):
                raise RuntimeError('Media configuration or shared mount changed during verification')
            after = manager.runtime_inventory() if not runtime_unavailable else None
            if before != after or (runtime_unavailable and manager.driver.runtime_processes()):
                raise RuntimeError('Algorithm process inventory changed during verification; retry when stable')
            result = {'schema': 2, 'inventory_complete': not runtime_unavailable,
                      'media_route_ready': True, 'shared_mount_ready': True,
                      'new_child_backend_probe': True, 'new_child_http_probe': True,
                      'algorithm_runtime': 'not_available' if runtime_unavailable else 'available',
                      'checked_at': int(time.time()), 'media_config_sha256': media_hash,
                      'registry_revision_at_check': revision}
            if after: result.update(after)
            storage.atomic_json(state_file, result, 0o600)
            if not runtime_unavailable:
                manager.readiness()
            return result
        except Exception as exc:
            pending['reason'] = str(exc)
            pending['checked_at'] = int(time.time())
            storage.atomic_json(state_file, pending, 0o600)
            raise


def check(manager, runtime_unavailable=False):
    if runtime_unavailable:
        ready = storage.load_json(manager.state / 'storage-readiness.json', {})
        required = ('media_route_ready', 'shared_mount_ready', 'new_child_backend_probe', 'new_child_http_probe')
        if (ready.get('schema') != 2 or ready.get('algorithm_runtime') != 'not_available'
                or ready.get('inventory_complete') is not False
                or not all(ready.get(key) is True for key in required)
                or manager.driver.runtime_processes() or not manager.driver.shared(manager.volumes)
                or ready.get('media_config_sha256') != fingerprint(MEDIA_CONFIG)):
            raise RuntimeError('SC7 platform capabilities are not verified or runtime state changed')
    else:
        ready = manager.readiness()
        required = ('inventory_complete', 'media_route_ready', 'shared_mount_ready', 'new_child_backend_probe', 'new_child_http_probe')
        if ready.get('schema') != 2 or not all(ready.get(key) is True for key in required):
            raise RuntimeError('Storage service has not completed current capability verification')
    manager.driver.backend_probe(manager.volumes, storage.identity(manager.volumes), manager.config)
    return ready


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--install', action='store_true')
    modes.add_argument('--check', action='store_true')
    parser.add_argument('--runtime-unavailable', action='store_true')
    parser.add_argument('--wait-seconds', type=int, default=60)
    args = parser.parse_args()
    manager = storage.StorageManager()
    try:
        result = complete(manager, args.runtime_unavailable, wait_seconds=max(0, min(args.wait_seconds, 120))) if args.install else check(manager, args.runtime_unavailable)
    except Exception as exc:
        print('ALARM_STORAGE_CAPABILITY=FAIL; ' + str(exc), file=sys.stderr)
        return 1
    if args.runtime_unavailable:
        print('ALARM_STORAGE_CAPABILITY=NOT_AVAILABLE_SC7; platform media/shared mounts verified; algorithm runtime not supplied; ready=false')
    else:
        print('ALARM_STORAGE_CAPABILITY=PASS; runtime inventory, shared mounts, backend visibility and real media content verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
