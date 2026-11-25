# -*- coding: utf-8 -*-
p = '/Seal_system/common/platform_access.py'
s = open(p, encoding='utf-8').read()
if "'/uuid_qr'" not in s:
    old = "    '/captcha': frozenset(('GET',)),\n"
    new = old + "    '/uuid_qr': frozenset(('GET',)),\n    '/activate/product_upload': frozenset(('POST',)),\n"
    assert old in s, 'anchor not found'
    s = s.replace(old, new, 1)
    open(p, 'w', encoding='utf-8').write(s)
print('HAS_UUID_QR' if "'/uuid_qr'" in open(p, encoding='utf-8').read() else 'PATCH_FAILED')
