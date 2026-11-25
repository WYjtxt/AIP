"""Reissue the two gateway leaves with the existing private site CA.

Planning is read-only.  Building writes only to a private temporary directory
and returns bytes for the caller's backed-up, atomic file transaction.
"""
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time


class CertificateMigrationError(Exception):
    pass


def _address(value):
    address = ipaddress.ip_address(str(value))
    if address.version != 4 or address.is_unspecified or address.is_multicast or address.is_loopback:
        raise CertificateMigrationError('证书迁移需要有效的业务 IPv4 地址')
    return str(address)


def _file(path, root, required=True):
    if path.is_symlink() or path.resolve() != path or root not in path.parents:
        raise CertificateMigrationError('证书目录存在不明确的链接：'+str(path))
    if not path.is_file():
        if required:
            raise CertificateMigrationError('缺少现有证书或密钥：'+str(path))
        return None
    data = path.read_bytes()
    if required and not data:
        raise CertificateMigrationError('现有证书或密钥为空：'+str(path))
    return data


def _sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _openssl(root, explicit=None):
    if explicit:
        return str(explicit)
    found = shutil.which('openssl')
    if found:
        return found
    candidate = root/'runtime/bin/openssl'
    if candidate.is_file():
        return str(candidate)
    raise CertificateMigrationError('找不到现有 OpenSSL，未安装软件或修改证书')


def _run(executable, args, runner=None):
    command = [executable]+[str(value) for value in args]
    if runner is None:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=45)
    else:
        result = runner(command, timeout=45)
    if isinstance(result, (str, bytes)):
        return result.encode('utf-8') if isinstance(result, str) else result
    if result.returncode:
        # Never forward arbitrary tool stderr: it may include key material or
        # interactive password prompts. The transaction has not written files.
        raise CertificateMigrationError('现有证书检查/签发失败：OpenSSL '+str(args[0])+
                                         '，退出码 '+str(result.returncode))
    output = result.stdout
    return output.encode('utf-8') if isinstance(output, str) else output


def _sans(executable, certificate, runner):
    output = _run(executable, ['x509', '-in', certificate, '-noout', '-ext', 'subjectAltName'], runner).decode('utf-8', 'replace')
    ips, names = [], []
    for value in re.findall(r'IP Address:([^,\s]+)', output):
        try:
            value = str(ipaddress.ip_address(value))
        except ValueError:
            raise CertificateMigrationError('现有证书包含无法识别的 IP SAN')
        if value not in ips:ips.append(value)
    for value in re.findall(r'DNS:([^,\s]+)', output):
        if not re.fullmatch(r'[A-Za-z0-9_.*-]+', value):
            raise CertificateMigrationError('现有证书包含无法识别的 DNS SAN')
        if value not in names:names.append(value)
    if re.search(r'(?:URI:|email:|Registered ID:|othername:|DirName:)', output, re.I):
        raise CertificateMigrationError('现有证书含自定义 SAN，需要人工确认后迁移')
    return ips, names


def _public_key(executable, path, is_certificate, runner):
    args = (['x509', '-in', path, '-pubkey', '-noout'] if is_certificate else
            ['pkey', '-in', path, '-passin', 'pass:', '-pubout'])
    return b''.join(_run(executable, args, runner).split())


def _check_key(executable, key, certificate, runner):
    if _public_key(executable, key, False, runner) != _public_key(executable, certificate, True, runner):
        raise CertificateMigrationError('现有证书与私钥不匹配：'+str(certificate))


def plan_certificates(root, old_ip, new_ip, runner=None, openssl=None, retain_old_ip=False):
    if not isinstance(retain_old_ip, bool):
        raise CertificateMigrationError('旧地址证书保留选项必须为布尔值')
    root = Path(root).absolute()
    if root.is_symlink() or root.resolve() != root:
        raise CertificateMigrationError('证书迁移需要平台实际目录')
    old_ip, new_ip = _address(old_ip), _address(new_ip)
    if old_ip == new_ip:
        raise CertificateMigrationError('新旧业务 IP 相同')
    executable = _openssl(root, openssl)
    ca = root/'config_dispatch/tls/ca'
    ca_certificate, ca_key = ca/'root.crt', ca/'root.key'
    inputs = {}
    for path in (ca_certificate, ca_key):
        inputs[str(path)] = _sha(_file(path, root))
    _check_key(executable, ca_key, ca_certificate, runner)
    end = _run(executable, ['x509', '-in', ca_certificate, '-noout', '-enddate'], runner).decode('ascii', 'replace').strip()
    try:
        ca_expires = ssl.cert_time_to_seconds(end.split('=', 1)[1])
    except (ValueError, IndexError):
        raise CertificateMigrationError('无法读取现有 CA 有效期')
    remaining_days = int((ca_expires-time.time())/86400)-1
    if remaining_days < 1:
        raise CertificateMigrationError('现有 CA 已过期或即将到期，未生成替代 CA')
    leaves, write_paths = [], []
    for relative in ('platform_gateway/tls', 'config_dispatch/tls/server'):
        folder = root/relative
        certificate, key = folder/'server.crt', folder/'server.key'
        for path in (certificate, key):
            inputs[str(path)] = _sha(_file(path, root))
        _check_key(executable, key, certificate, runner)
        _run(executable, ['verify', '-no_check_time', '-CAfile', ca_certificate, certificate], runner)
        ips, names = _sans(executable, certificate, runner)
        renew = new_ip not in ips or (old_ip not in ips if retain_old_ip else old_ip in ips)
        new_ips = list(ips) if retain_old_ip else [value for value in ips if value != old_ip]
        if retain_old_ip and old_ip not in new_ips:new_ips.append(old_ip)
        if new_ip not in new_ips:new_ips.append(new_ip)
        if 'localhost' not in names:names.append('localhost')
        outputs = [certificate]
        for name in ('server-chain.crt', 'server.csr', 'server.cnf', 'server.ext', 'native.ext'):
            path = folder/name
            value = _file(path, root, required=False)
            inputs[str(path)] = _sha(value)
            if value is not None:outputs.append(path)
        if renew:write_paths += [str(path) for path in outputs]
        leaves.append(dict(folder=str(folder), certificate=str(certificate), key=str(key),
                           ips=new_ips, dns=names, renew=renew,
                           outputs=[str(path) for path in outputs]))
    media_pem = root/'Config_files/zlk/default.pem'
    media = _file(media_pem, root, required=False)
    inputs[str(media_pem)] = _sha(media)
    gateway_key = _file(Path(leaves[0]['key']), root)
    gateway_certificate = _file(Path(leaves[0]['certificate']), root)
    expected_media = gateway_key.rstrip()+b'\n'+gateway_certificate.rstrip()+b'\n'+ca_certificate.read_bytes().rstrip()+b'\n'
    update_media = media is not None and (leaves[0]['renew'] or media != expected_media)
    if update_media:write_paths.append(str(media_pem))
    return dict(schema=1, root=str(root), old_ip=old_ip, new_ip=new_ip, retain_old_ip=retain_old_ip,
                openssl=executable, ca_certificate=str(ca_certificate), ca_key=str(ca_key),
                ca_preserved=True, days=min(825, remaining_days), inputs=inputs,
                leaves=leaves, write_paths=write_paths, media_pem=str(media_pem),
                update_media=update_media)


def _configuration(ips, names, common_name):
    source = ('[req]\ndistinguished_name=dn\nprompt=no\n[dn]\nCN='+common_name+
              '\n[server_ext]\nbasicConstraints=critical,CA:FALSE\n'
              'keyUsage=critical,digitalSignature,keyEncipherment\n'
              'extendedKeyUsage=serverAuth\nsubjectAltName=@alt_names\n[alt_names]\n')
    source += ''.join('IP.%d=%s\n' % (i+1, value) for i, value in enumerate(ips))
    source += ''.join('DNS.%d=%s\n' % (i+1, value) for i, value in enumerate(names))
    return source.encode('ascii')


def build_certificates(plan, runner=None):
    if not isinstance(plan, dict) or plan.get('schema') != 1:
        raise CertificateMigrationError('缺少有效的证书迁移计划')
    root = Path(plan['root'])
    fresh = plan_certificates(root, plan['old_ip'], plan['new_ip'], runner, plan['openssl'],
                              retain_old_ip=plan.get('retain_old_ip', False))
    # Recalculate all decisions. Never trust writable paths from the packet.
    if fresh['inputs'] != plan.get('inputs'):
        raise CertificateMigrationError('证书或密钥在预览后已变化，请重新预览')
    changes, generated = {}, {}
    ca_certificate = Path(fresh['ca_certificate'])
    executable = fresh['openssl']
    with tempfile.TemporaryDirectory(prefix='ip-migration-cert-') as directory:
        temporary = Path(directory)
        if os.name != 'nt':temporary.chmod(0o700)
        for index, leaf in enumerate(fresh['leaves']):
            if not leaf['renew']:
                continue
            folder = temporary/str(index)
            folder.mkdir(mode=0o700)
            config, csr, certificate = folder/'server.cnf', folder/'server.csr', folder/'server.crt'
            config_data = _configuration(leaf['ips'], leaf['dns'], fresh['new_ip'])
            config.write_bytes(config_data)
            _run(executable, ['req', '-new', '-key', leaf['key'], '-passin', 'pass:',
                              '-config', config, '-out', csr], runner)
            _run(executable, ['x509', '-req', '-in', csr, '-CA', ca_certificate,
                              '-CAkey', fresh['ca_key'], '-passin', 'pass:',
                              '-set_serial', '0x'+secrets.token_hex(16), '-out', certificate,
                              '-days', str(fresh['days']), '-sha256', '-extfile', config,
                              '-extensions', 'server_ext'], runner)
            _run(executable, ['verify', '-CAfile', ca_certificate, certificate], runner)
            _check_key(executable, Path(leaf['key']), certificate, runner)
            ips, names = _sans(executable, certificate, runner)
            if fresh['new_ip'] not in ips or (fresh['old_ip'] not in ips if fresh['retain_old_ip'] else fresh['old_ip'] in ips):
                raise CertificateMigrationError('新服务器证书的 IP SAN 校验失败')
            data = certificate.read_bytes().rstrip()+b'\n'
            chain = data+ca_certificate.read_bytes().rstrip()+b'\n'
            generated[leaf['certificate']] = data
            for value in leaf['outputs']:
                path = Path(value)
                changes[value] = (data if path.name == 'server.crt' else
                                  chain if path.name == 'server-chain.crt' else
                                  csr.read_bytes() if path.name == 'server.csr' else config_data)
        if fresh['update_media']:
            gateway = fresh['leaves'][0]
            certificate = generated.get(gateway['certificate']) or Path(gateway['certificate']).read_bytes()
            changes[fresh['media_pem']] = (Path(gateway['key']).read_bytes().rstrip()+b'\n'+
                                           certificate.rstrip()+b'\n'+ca_certificate.read_bytes().rstrip()+b'\n')
    if set(changes) != set(fresh['write_paths']):
        raise CertificateMigrationError('证书迁移文件清单不一致')
    for name, expected in fresh['inputs'].items():
        if _sha(_file(Path(name), root, required=False)) != expected:
            raise CertificateMigrationError('证书输入在签发期间发生变化，未发布新证书')
    # The site CA and existing leaf keys are inputs only.
    return dict(changes=changes, metadata=dict(ca_preserved=True, leaf_keys_preserved=True, retain_old_ip=fresh['retain_old_ip'],
                new_ip=fresh['new_ip'], changed_leaves=sum(leaf['renew'] for leaf in fresh['leaves']),
                changed_files=len(changes)))
