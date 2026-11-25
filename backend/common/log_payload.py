"""Small database audit payloads; do not serialize full polling responses."""
import re


_URL_CREDENTIALS = re.compile(r'((?:rtsp|https?|rtmp)://)[^\s/@]+:[^\s/@]*@', re.IGNORECASE)


def bounded_text(value, max_bytes=4096):
    if value is None:
        return None
    text = _URL_CREDENTIALS.sub(r'\1[redacted]@', str(value))
    payload = text.encode('utf-8', errors='replace')
    if len(payload) <= max_bytes:
        return text
    marker = b' ... [truncated]'
    return payload[:max_bytes - len(marker)].decode('utf-8', errors='ignore') + marker.decode('ascii')


def limit_log_payload(mapper, connection, target):
    limits = {'message': 4096, 'request_data': 4096, 'response_data': 4096,
              'stack_trace': 16384, 'error_message': 4096}
    for field, limit in limits.items():
        if hasattr(target, field):
            setattr(target, field, bounded_text(getattr(target, field), limit))
