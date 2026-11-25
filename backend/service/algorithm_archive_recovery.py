"""Restore a missing AI-camera ZIP from its persisted, bounded SFTP archive.

No database writes, camera requests, model loading, conversion, or private-key
handling. Existing local files are returned unchanged. Recovery is limited to
new UUID_SHA256 archive basenames in the two fixed application directories.
"""
import ast
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

from service.algorithm_package_validation import (
    MAX_UPLOAD_BYTES, AlgorithmPackageError, open_package_zip,
    inspect_algorithm_package, require_camera_package,
)


class AlgorithmArchiveRecoveryError(ValueError):
    """Safe, fixed operator-facing messages, never connection exception text."""


_ARCHIVE_NAME = re.compile(r'([0-9a-f]{32})_([0-9a-f]{64})\.zip\Z')
_REMOTE_ROOT = '/data/AIGO/platform_start/model_algorithm_package/'


class _LimitedSftp:
    def __init__(self, sftp, remote_path, local_directory, failure):
        self.sftp = sftp
        self.remote_path = remote_path
        self.local_directory = Path(local_directory)
        self.failure = failure

    def get(self, remote_path, local_path):
        try:
            return self._get(remote_path, local_path)
        except AlgorithmArchiveRecoveryError as error:
            self.failure.append(str(error))
            raise

    def _get(self, remote_path, local_path):
        expected_local = self.local_directory / self.remote_path.rsplit('/', 1)[1]
        if remote_path != self.remote_path or Path(local_path) != expected_local:
            raise AlgorithmArchiveRecoveryError('归档下载路径不符合平台恢复规则')
        info = self.sftp.lstat(remote_path)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_UPLOAD_BYTES:
            raise AlgorithmArchiveRecoveryError('归档必须是普通 ZIP 文件且大小不超过 60MB')
        expected_size = info.st_size

        def progress(transferred, total):
            if transferred > MAX_UPLOAD_BYTES or total > MAX_UPLOAD_BYTES or total != expected_size:
                raise AlgorithmArchiveRecoveryError('归档传输大小变化或超过 60MB 限制')

        # Preserve SSH_Func.download_files while adding its missing transfer cap.
        self.sftp.get(remote_path, str(expected_local), callback=progress)
        if expected_local.stat().st_size != expected_size:
            raise AlgorithmArchiveRecoveryError('归档文件下载不完整，请检查归档服务器')

    def close(self):
        self.sftp.close()


class _LimitedConnection:
    def __init__(self, connection, remote_path, local_directory, failure):
        self.connection, self.remote_path = connection, remote_path
        self.local_directory = local_directory
        self.failure = failure

    def open_sftp(self):
        try:
            return _LimitedSftp(self.connection.open_sftp(), self.remote_path, self.local_directory, self.failure)
        except Exception:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()


def _client(ssh_type, server, remote_path, local_directory, failure):
    class LimitedArchiveSSH(ssh_type):
        def connect_ssh(self):
            connection, status = super().connect_ssh()
            if connection is None:
                return None, status
            return _LimitedConnection(connection, remote_path, local_directory, failure), status
    return LimitedArchiveSSH(server.computing_ip, server.computing_user, server.computing_password)


def _validate_metadata(content, record):
    try:
        with open_package_zip(content) as archive:
            package = inspect_algorithm_package(archive)
            require_camera_package(package)
            expected = {
                'algorithm_file_name': package.filename,
                'algorithm_version': package.words[9],
                'analysis_type': package.words[1],
                'model_type_name': package.words[2],
                'model_name': package.words[3],
                'template_small_name': package.words[4],
                'algorithm_parent': package.words[10],
                'algorithm_child': package.words[11],
                'algorithm_type': package.algorithm_type,
            }
            if any(str(getattr(record, field, '')) != value for field, value in expected.items()):
                raise AlgorithmArchiveRecoveryError('归档模型元数据与算法库记录不一致，请重新核对上传包')
            labels = ast.literal_eval(str(getattr(record, 'algorithm_type_list', '')))
            if labels != [label['lable'] for label in package.labels]:
                raise AlgorithmArchiveRecoveryError('归档检测类别与算法库记录不一致，请重新核对上传包')
    except AlgorithmArchiveRecoveryError:
        raise
    except (AlgorithmPackageError, ValueError, SyntaxError, TypeError):
        raise AlgorithmArchiveRecoveryError('归档 ZIP 或模型元数据无效，请重新上传算法包') from None


def recover_camera_algorithm_archive(record, servers, ssh_type, archive_directory):
    """Return the existing local path or atomically recover a validated archive."""
    saved = getattr(record, 'algorithm_file_path', None)
    if saved and os.path.exists(saved):
        return saved
    remote_path = str(getattr(record, 'algorithm_path', '') or '')
    basename = remote_path.rsplit('/', 1)[-1]
    match = _ARCHIVE_NAME.fullmatch(basename)
    if match is None or remote_path != _REMOTE_ROOT + basename:
        raise AlgorithmArchiveRecoveryError('本地算法包缺失；旧版或非标准归档不支持自动恢复，请重新上传算法包')
    directory = Path(archive_directory).absolute()
    target = directory / basename
    if not saved or Path(saved) != target or directory.resolve() != directory:
        raise AlgorithmArchiveRecoveryError('本地算法包恢复路径不符合平台固定目录规则')
    available = [server for server in servers if str(getattr(server, 'server_type', '')) == '1']
    if not available:
        raise AlgorithmArchiveRecoveryError('本地算法包缺失，请先配置算法归档服务器（server_type=1）')
    try:
        directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    except OSError:
        raise AlgorithmArchiveRecoveryError('无法创建本地算法包恢复目录，请检查存储权限') from None
    last_message = '无法从归档服务器恢复算法包，请检查服务器连接和归档文件'
    for server in available:
        client = None
        try:
            with tempfile.TemporaryDirectory(prefix='.archive-recover-', dir=str(directory)) as temporary:
                failure = []
                client = _client(ssh_type, server, remote_path, temporary, failure)
                downloaded = client.download_files([remote_path], temporary)
                candidate = Path(temporary) / basename
                if (not isinstance(downloaded, list) or str(candidate) not in downloaded
                        or not candidate.is_file() or candidate.is_symlink()):
                    raise AlgorithmArchiveRecoveryError(failure[-1] if failure else
                        '无法完整下载算法归档，请检查归档文件及服务器连接')
                with candidate.open('rb') as stream:
                    content = stream.read(MAX_UPLOAD_BYTES + 1)
                if not 0 < len(content) <= MAX_UPLOAD_BYTES:
                    raise AlgorithmArchiveRecoveryError('归档 ZIP 为空或超过 60MB 限制')
                if hashlib.sha256(content).hexdigest() != match.group(2):
                    raise AlgorithmArchiveRecoveryError('算法归档 SHA-256 校验失败，请重新核对归档文件')
                _validate_metadata(content, record)
                candidate.chmod(0o644)
                with candidate.open('rb+') as stream:
                    os.fsync(stream.fileno())
                os.replace(str(candidate), str(target))
                return str(target)
        except AlgorithmArchiveRecoveryError as error:
            last_message = str(error)
        except Exception:
            last_message = '无法从归档服务器恢复算法包，请检查服务器连接和归档文件'
        finally:
            # Legacy download_files already closes its connection on its normal
            # path. Also close it when connect/open_sftp fails before that block.
            connection = getattr(client, 'ssh', None)
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
    raise AlgorithmArchiveRecoveryError(last_message)
