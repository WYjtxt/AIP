# -*- coding: utf-8 -*-
"""容器启动时注入“闸机尾随”模板/配置页/后端白名单（幂等，可反复执行）。
由 Config_files/platform_release_site_entrypoint.py 在 run <role> 之前调用。
"""
import os
import shutil
import sys

ROOT = '/data/AIGO/platform_start'
EXT = os.path.join(ROOT, 'model_algorithm_package', 'tailgate_ext')
MARK = 'TAILGATE_DISPATCH_V1'
CONTRACT_MARK = 'TAILGATE_CONTRACT_V1'


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _write(path, text):
    tmp = path + '.tailgate.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


def patch_algorithm():
    src = os.path.join(EXT, 'tailgate.py')
    dst = os.path.join(ROOT, 'platform_algorithm_start', 'templates', 'tailgate.py')
    if not os.path.isfile(src):
        return 'skip: no template'
    shutil.copy2(src, dst)

    ms = os.path.join(ROOT, 'platform_algorithm_start', 'model_start.py')
    text = _read(ms)
    if MARK in text:
        return 'already patched'

    old_group = "    if tcid == 4 and f['template_name'] == '领导换班':\n        return True"
    new_group = ("    if tcid == 4 and f['template_name'] in ('领导换班', '闸机尾随'):"
                 "  # " + MARK + "\n        return True")
    if old_group in text:
        text = text.replace(old_group, new_group, 1)
    else:
        return 'error: is_groupable anchor not found'

    anchor = 'return muban_LeadSwitch.build_spec('
    idx = text.find(anchor)
    if idx < 0:
        return 'error: leadswitch anchor not found'
    tail = text.find('\n    return None', idx)
    if tail < 0:
        return 'error: return None anchor not found'
    block = (
        "\n    if tcid == 4 and f['template_name'] == '闸机尾随':  # " + MARK + "\n"
        "        from templates import tailgate\n"
        "        logging.info(\"{}执行闸机尾随模板\".format(f['conf_name']))\n"
        "        return tailgate.build_spec(*common, f['cross_line_area'],\n"
        "                                   label_prefix=label_prefix, names_cn=names_cn,\n"
        "                                   Mine_id=f['Mine_id'], mine_code=f['mine_code'],\n"
        "                                   region_color=region_color)\n"
    )
    text = text[:tail] + block + text[tail:]
    _write(ms, text)
    return 'patched'


def patch_backend():
    """放行“闸机尾随”模板：平台原有规则只放行人数统计 / 领导换班。"""
    path = os.path.join(ROOT, 'backend', 'service', 'algorithm_configuration_contract.py')
    if not os.path.isfile(path):
        return 'skip: no contract'
    text = _read(path)
    if CONTRACT_MARK in text:
        return 'already patched'
    old = ("    if type_id == '4' and name in KINDS:\n"
           "        return '当前算能平台尚未提供人员尾随、违规跨越的 BM1684X INT8 模型'")
    new = ("    if type_id == '4' and name == '闸机尾随':  # " + CONTRACT_MARK + "\n"
           "        return ''\n") + old
    if old not in text:
        return 'error: contract anchor not found'
    text = text.replace(old, new, 1)
    _write(path, text)
    return 'patched'


def patch_web():
    js_src = os.path.join(EXT, 'web', 'tailgate-route.js')
    js_dst = os.path.join(ROOT, 'frontend', 'static', 'js', 'tailgate-route.js')
    if os.path.isfile(js_src):
        shutil.copy2(js_src, js_dst)

    std_src = os.path.join(EXT, 'web', 'tailgate-standard.js')
    std_dst = os.path.join(ROOT, 'frontend', 'static', 'js', 'tailgate-standard.js')
    if os.path.isfile(std_src):
        shutil.copy2(std_src, std_dst)

    page_src = os.path.join(EXT, 'web', 'tailgate.html')
    page_dir = os.path.join(ROOT, 'platform_gateway', 'tailgate')
    os.makedirs(page_dir, exist_ok=True)
    if os.path.isfile(page_src):
        shutil.copy2(page_src, os.path.join(page_dir, 'index.html'))

    index = os.path.join(ROOT, 'frontend', 'index.html')
    text = _read(index)
    changed = False
    for tag in ('<script src="./static/js/tailgate-route.js?v=tailgate-1"></script>',
                '<script src="./static/js/tailgate-standard.js?v=tailgate-2"></script>'):
        if tag not in text:
            text = text.replace('</body>', tag + '</body>', 1)
            changed = True
    if changed:
        _write(index, text)

    conf = os.path.join(ROOT, 'platform_gateway', 'default.conf')
    cfg = _read(conf)
    loc = ("    location ^~ /tailgate/ {\n"
           "        alias /data/AIGO/platform_start/platform_gateway/tailgate/;\n"
           "        index index.html;\n"
           "        add_header Cache-Control no-store;\n"
           "    }\n")
    if '/tailgate/' not in cfg:
        pos = cfg.find('    location = /index.html {')
        if pos > 0:
            _write(conf, cfg[:pos] + loc + cfg[pos:])
    return 'web patched'


def main():
    role = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        if role == 'algorithm-master':
            print('[tailgate] algorithm:', patch_algorithm(), file=sys.stderr)
        elif role == 'backend':
            print('[tailgate] backend:', patch_backend(), file=sys.stderr)
        elif role == 'web':
            print('[tailgate] web:', patch_web(), file=sys.stderr)
    except Exception as e:
        print('[tailgate] inject failed: %r' % (e,), file=sys.stderr)


if __name__ == '__main__':
    main()
