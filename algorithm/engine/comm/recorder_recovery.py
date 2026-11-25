"""Resolve a matching camera stream after a recorder rejects RTSP SETUP."""
from dataclasses import dataclass
import ctypes
from http.client import HTTPException
from ipaddress import ip_address
import re
import os
import subprocess
import sys
import tempfile
from urllib.error import URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import (HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
                            HTTPRedirectHandler, ProxyHandler, build_opener)
import xml.etree.ElementTree as ET


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_camera_decoder(factory, *args):
    """SAIL logs complete credentials to native fd 1/2 while opening a URL."""
    flush_native = ctypes.CDLL(None).fflush
    sys.stdout.flush()
    sys.stderr.flush()
    flush_native(None)
    with tempfile.TemporaryFile() as capture:
        stdout, stderr = os.dup(1), os.dup(2)
        try:
            os.dup2(capture.fileno(), 1)
            os.dup2(capture.fileno(), 2)
            try:
                return factory(*args)
            except Exception:
                raise RuntimeError('摄像机直连解码器打开失败') from None
        finally:
            flush_native(None)
            os.dup2(stdout, 1)
            os.dup2(stderr, 2)
            os.close(stdout)
            os.close(stderr)
            capture.seek(0)
            for line in capture:
                sys.stderr.buffer.write(re.sub(rb"""(?i)rtsps?://[^\s"'<>]+""", b'[RTSP]', line))
            sys.stderr.flush()


@dataclass(frozen=True, repr=False)
class RecorderChannel:
    recorder_ip: str
    channel: int
    api_port: int
    camera_ip: str
    camera_port: int
    camera_user: str
    camera_password: str

    @classmethod
    def from_task(cls, row):
        if (row.get('equipment_type') != '录像机' or (row.get('vcr_type') or row.get('manufacturer_type')) != '海康'
                or not row.get('recorder_api_port') or not row.get('equipment_uname') or not row.get('equipment_password')):
            return None
        try:
            camera_ip = str(ip_address(row['equipment_ip']))
            recorder_ip = str(ip_address(row['vcr_ip']))
            if camera_ip == recorder_ip:
                return None
            channel = int(row['equipment_aisles'])
            camera_port, api_port = int(row.get('equipment_port') or 554), int(row['recorder_api_port'])
            if channel < 1 or not (1 <= camera_port <= 65535 and 1 <= api_port <= 65535):
                return None
            return cls(recorder_ip, channel, api_port, camera_ip, camera_port, row['equipment_uname'], row['equipment_password'])
        except (KeyError, ValueError, TypeError):
            return None

    def verified_camera_after_failure(self, primary):
        try:
            url = urlsplit(primary)
            if url.scheme != 'rtsp' or str(ip_address(url.hostname)) != self.recorder_ip:
                return None
        except (TypeError, ValueError):
            return None
        match = re.fullmatch(r'/Streaming/(?:Unicast/)?Channels/(\d+)(01|02)', url.path)
        if not match or int(match.group(1)) != self.channel or not url.username or not url.password:
            return None
        # The hardware decoder reports all open failures under the same error.
        # An independent SETUP distinguishes upstream 5xx from rejected credentials.
        try:
            probe = subprocess.run(['/data/AIGO/platform_start/runtime/bin/ffprobe', '-v', 'error',
                                    '-rtsp_transport', 'tcp', '-show_entries', 'stream=codec_name', primary],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=6)
            if probe.returncode == 0 or not re.search(rb'method SETUP failed:\s*5\d\d\b', probe.stderr):
                return None
            host = self.recorder_ip
            host = '[' + host + ']' if ':' in host else host
            endpoint = 'http://{}:{}/ISAPI/ContentMgmt/InputProxy/channels/{}'.format(host, self.api_port, self.channel)
            auth = HTTPPasswordMgrWithDefaultRealm()
            auth.add_password(None, endpoint, unquote(url.username), unquote(url.password))
            opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPDigestAuthHandler(auth))
            with opener.open(endpoint, timeout=4) as response:
                root = ET.fromstring(response.read(131072))
            for node in root.iter():
                node.tag = node.tag.rsplit('}', 1)[-1]
            if root.findtext('id') != str(self.channel) or ip_address(root.findtext('.//ipAddress')) != ip_address(self.camera_ip):
                return None
            src = int(root.findtext('.//srcInputPort'))
            if not 1 <= src <= 99999:
                return None
            host = '[' + self.camera_ip + ']' if ':' in self.camera_ip else self.camera_ip
            return 'rtsp://{}:{}@{}:{}/Streaming/Channels/{}{}'.format(
                quote(self.camera_user, safe=''), quote(self.camera_password, safe=''), host, self.camera_port, src, match.group(2))
        except (TypeError, ValueError, OSError, HTTPException, URLError, ET.ParseError, subprocess.TimeoutExpired):
            return None
