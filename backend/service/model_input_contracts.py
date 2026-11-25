"""Preserve an uploaded OM's explicit input contract without inferring its type."""
import hashlib
import json
import uuid
from service.algorithm_package_validation import AlgorithmPackageError, _decoded_name, _entries


def read_model_input_contract(archive, model_member, model_content):
    if not str(model_member).casefold().endswith('.om'):
        return None
    model_name = _decoded_name(archive.getinfo(model_member)).replace('\\', '/')
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
