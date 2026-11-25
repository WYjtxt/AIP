"""Install the Sophon tailgate extension into the site's persistent directories."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import pymysql

ROOT = Path('/data/AIGO/platform_start')
SOURCE = Path(__file__).resolve().parent
NAME = '闸机尾随'
MODEL_SHA = '7bae5fee2f8083b7953c36de004f761297c251c08151bb41c78ef11c56ea23ae'


def publish(path, data, mode=0o644):
    if path.is_symlink():
        raise ValueError('Unexpected symbolic link at ' + str(path))
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(data)
        tmp = Path(stream.name)
    try:
        tmp.chmod(mode)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def find_or_insert(cur, table, match, defaults):
    fields = sorted(match)
    terms = ' AND '.join(key + '=%s' for key in fields)
    cur.execute('SELECT id FROM ' + table + ' WHERE ' + terms + ' ORDER BY id LIMIT 1', [match[k] for k in fields])
    result = cur.fetchone()
    if result:
        return result[0]
    values = dict(defaults, **match)
    keys = sorted(values)
    cur.execute('INSERT INTO ' + table + ' (' + ','.join(keys) + ') VALUES (' + ','.join(['%s'] * len(keys)) + ')', [values[k] for k in keys])
    return cur.lastrowid


def install():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ROOT / 'Config_files/config.ini')
    db = cfg['database']
    info = json.loads((SOURCE / 'catalog.json').read_bytes())
    package = ROOT / 'model_algorithm_package'
    filename = info['model']
    model = package / filename
    if not model.exists():
        publish(model, (SOURCE / filename).read_bytes())
    if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA:
        raise ValueError('尾随模型文件与随包校验值不一致')
    conn = pymysql.connect(host=db['DB_HOST'], port=int(db.get('DB_PORT', 3306)), user=db['DB_USER'],
                           password=db['DB_PASSWORD'], database=db['DB_NAME'], charset='utf8mb4')
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK('aiplatform_sophon_tailgate_catalog',20)")
            if cur.fetchone()[0] != 1:
                raise RuntimeError('尾随模型登记正在执行')
            template = find_or_insert(cur, 't_model_template_config',
                                      {'model_name': NAME, 'model_template_config_type_id': 4}, {'model_type': '1'})
            small = find_or_insert(cur, 't_model_template_small',
                                   {'template_small_name': NAME, 'model_template_config_type_id': 4}, {'list_data': info['list_data']})
            library = find_or_insert(cur, 't_algorithm_library',
                                     {'algorithm_path': str(model), 'template_small_name': NAME}, info['library'])
            cur.execute('SELECT id FROM t_algorithm_test_type WHERE Algorithm_library_id=%s AND test_type_cname=%s ORDER BY id LIMIT 1', (library, '人员'))
            row = cur.fetchone()
            kind = row[0] if row else find_or_insert(cur, 't_algorithm_test_type', {'Algorithm_library_id': library, 'test_type_cname': '人员'}, {'test_type_ename': 'renyuan'})
            conn.commit()
            ext = package / 'tailgate_ext'
            for src in sorted((SOURCE / 'files').rglob('*')):
                if not src.is_file():
                    continue
                rel = src.relative_to(SOURCE / 'files')
                data = src.read_bytes()
                if str(rel) == 'web/tailgate.html':
                    old = b'var LIB_ID = 100, TEMPLATE_ID = 100, TEMPLATE_SMALL_ID = 100, TYPE_ID = 100;'
                    assert data.count(old) == 1
                    data = data.replace(old, ('var LIB_ID = %d, TEMPLATE_ID = %d, TEMPLATE_SMALL_ID = %d, TYPE_ID = %d;' % (library, template, small, kind)).encode())
                elif str(rel) == 'web/tailgate-standard.js':
                    for name, ident in [('LIB_IDS', library), ('TEMPLATE_IDS', template)]:
                        import re
                        data, n = re.subn(rb"(var " + name.encode() + rb"\s*=\s*)\{[^}\n]*\}", lambda m: m[1] + ("{ '%d': 1 }" % ident).encode(), data)
                        assert n == 1
                publish(ext / rel, data)
            publish(ROOT / 'platform_gateway/tailgate/index.html', (ext / 'web/tailgate.html').read_bytes())
            publish(ROOT / 'Config_files/platform-site-ui.200c60522e99.js', (SOURCE / 'platform-site-ui.200c60522e99.js').read_bytes())
        return {'library_id': library, 'template_id': template, 'type_id': kind}
    finally:
        conn.close()


if __name__ == '__main__':
    print(json.dumps(install()))
