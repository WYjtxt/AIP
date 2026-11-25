
def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value

DB_HOST = '127.0.0.1'
DB_USER = 'root'
DB_PASSWORD = ''
if not DB_PASSWORD:
    DB_PASSWORD = _required_site_value("AIP_DB_PASSWORD")
DB_NAME = 'seal_system'
Redis_port = 6379
Redis_password = ''
Box_ip = '172.16.129.236'
Box_user = 'root'
Box_password = ''
if not Box_password:
    Box_password = _required_site_value("AIP_BOX_PASSWORD")
KAFKA_HOST = '127.0.0.1'
ZLK_HOST = '127.0.0.1'
ZLK_PORT = '8085'
ZLK_SECRET = ''
if not ZLK_SECRET:
    ZLK_SECRET = _required_site_value("AIP_ZLK_SECRET")
