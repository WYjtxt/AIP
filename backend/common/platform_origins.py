"""Explicit frontend origins for the existing local and Hikvision deployment."""
import os
from urllib.parse import urlsplit

DEFAULT_ORIGINS = ('http://127.0.0.1:8888', 'http://localhost:8888',
                   'http://172.16.129.236:8888', 'http://192.168.111.20:8888')


def allowed_origins():
    configured = os.environ.get('SEAL_ALLOWED_ORIGINS')
    origins = configured.split(',') if configured else DEFAULT_ORIGINS
    result = []
    for value in origins:
        value = value.strip().rstrip('/')
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
                or parsed.password or parsed.path or parsed.query or parsed.fragment or '*' in value):
            raise ValueError('SEAL_ALLOWED_ORIGINS must contain explicit HTTP(S) origins')
        parsed.port  # Validate the port while loading configuration.
        if value not in result:
            result.append(value)
    return result
