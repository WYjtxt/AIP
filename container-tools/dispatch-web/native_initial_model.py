"""Install the bundled person-count model for the detected native driver."""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace


MODEL_PACKAGES = {'huawei': 'person_count_huawei.zip', 'sophon': 'person_count_sophon.zip'}
MODEL_FAMILIES = {'huawei': 'ascend', 'sophon': 'sophon'}


def _load_backend():
    from data.exts import db
    from model.algorithm import Algorithm_library
    from model.equipment import Resource_usage
    from service.algorithm_model_service import handle_algorithm_upload_single
    from service.algorithm_package_validation import (open_package_zip, inspect_algorithm_package,
                                                     same_model_slot, matching_device_ids)
    from werkzeug.datastructures import FileStorage
    return SimpleNamespace(db=db, library=Algorithm_library, upload=handle_algorithm_upload_single,
                           open_zip=open_package_zip, inspect=inspect_algorithm_package,
                           same_slot=same_model_slot, file_storage=FileStorage,
                           resource=Resource_usage, matching_devices=matching_device_ids)


def wait_for_local_resource(backend, package, computing_id):
    """Let the existing resource service provide real matching cards."""
    deadline = time.monotonic() + 30
    while True:
        # Release the prior read transaction so the next sample sees updates
        # committed by the independent resource collector.
        backend.db.session.rollback()
        rows = backend.db.session.query(backend.resource).filter(
            backend.resource.computing_id == int(computing_id)).all()
        resources = [{'computing_id': row.computing_id, 'dev_get_target': row.dev_get_target}
                     for row in rows]
        if backend.matching_devices(package, resources, [int(computing_id)]):
            return
        if time.monotonic() >= deadline:
            raise ValueError('等待本机算力资源采集超时，人数统计模型未预安装；请检查resource服务')
        time.sleep(1)


def preinstall_model(models_root, family, computing_id):
    """Run in the backend app context after registering and collecting this host.

    A pre-existing model slot belongs to the site: keep its model, remarks and
    task references. New models use the normal validated upload service, scoped
    to the deployment server rather than all registered compute devices.
    """
    if family not in MODEL_PACKAGES:
        return {'status': 'skipped', 'family': family, 'reason': '未检测到华为或算能驱动，未预安装模型'}
    package_path = Path(models_root) / MODEL_PACKAGES[family]
    if not package_path.is_file():
        if family == 'sophon':
            return {'status': 'skipped', 'family': family, 'reason': '算能人数统计模型暂未提供，保留待补充'}
        raise ValueError('缺少华为预安装人数统计模型：' + package_path.name)
    if int(computing_id) <= 0:
        raise ValueError('预安装模型需要有效的本机算力设备ID')
    backend = _load_backend()
    with backend.open_zip(package_path.read_bytes()) as archive:
        package = backend.inspect(archive)
    if package.family != MODEL_FAMILIES[family]:
        raise ValueError('预安装模型格式与检测到的驱动不匹配')
    rows = backend.db.session.query(backend.library).all()
    existing = next((row for row in rows if backend.same_slot(row.algorithm_file_name, package)), None)
    if existing is not None:
        return {'status': 'preserved', 'family': family, 'library_id': existing.id,
                'reason': '相同模型槽位已存在，保留现场模型、备注及任务引用'}
    wait_for_local_resource(backend, package, computing_id)
    with package_path.open('rb') as stream:
        uploaded = backend.file_storage(stream=stream, filename=package_path.name, content_type='application/zip')
        response = backend.upload(uploaded, '1', '预安装模型', computing_ids=[int(computing_id)])
    body = response.get_json()
    if body.get('code') != 200:
        raise ValueError('预安装人数统计模型失败：' + str(body.get('msg', '导入未完成')))
    rows = backend.db.session.query(backend.library).all()
    installed = next((row for row in rows if backend.same_slot(row.algorithm_file_name, package)), None)
    if installed is None:
        raise ValueError('预安装人数统计模型导入后未找到算法记录')
    return {'status': 'installed', 'family': family, 'library_id': installed.id,
            'reason': '人数统计模型已预安装，算法备注为预安装模型'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--models-root', type=Path, required=True)
    parser.add_argument('--family', required=True, choices=('huawei', 'sophon', 'unknown'))
    parser.add_argument('--computing-id', type=int, required=True)
    args = parser.parse_args()
    # Missing future-model branches do not need to load the entire backend.
    if args.family == 'unknown' or (args.family == 'sophon' and
            not (args.models_root / MODEL_PACKAGES['sophon']).is_file()):
        result = preinstall_model(args.models_root, args.family, args.computing_id)
    else:
        sys.path.insert(0, str(args.root / 'backend'))
        from server_app_factory import create_app
        app = create_app(start_scheduler=False)
        with app.app_context():
            result = preinstall_model(args.models_root, args.family, args.computing_id)
    print('PREINSTALLED_MODEL=' + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
