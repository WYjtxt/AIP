"""Keep role-related wording aligned with server-owned menu capabilities."""
from pathlib import Path
import hashlib
import re


def patch_native_drawing_default(root):
    """Start with detection regions; only an explicit line tool switches to lines."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        return False
    relative = asset.group(1)
    app_path = frontend / (relative[2:] if relative.startswith('./') else relative)
    if not app_path.is_file():
        return False
    app = app_path.read_text(encoding='utf-8')
    changed = False
    for chunk_id in ('chunk-415cc626', 'chunk-e0401796'):
        reference = re.search('"' + chunk_id + '":"([^"]+)"', app)
        if not reference:
            raise ValueError('未找到算法配置绘制模块: ' + chunk_id)
        old_name = chunk_id + '.' + reference.group(1) + '.js'
        path = frontend / 'assets/js' / old_name
        source = path.read_text(encoding='utf-8')
        if 'var algorithmDetectionRoi = {' not in source:
            raise ValueError('未找到独立检测区域绘制工具')
        updated = source.replace("algorithmDetectionDrawing: false, algorithmCountingDrawMode: 'line',",
                                 "algorithmDetectionDrawing: false, algorithmCountingDrawMode: 'roi',", 1)
        watcher = "'form.Algorithm_library_id'(value, previous) {if(String(value)!==String(previous))this.algorithmCountingDrawMode='roi';},"
        if watcher not in updated:
            anchor = "'form.conf_area': {immediate:true, handler(value) {this.restoreAlgorithmDetectionRegions(value);}},"
            if updated.count(anchor) != 1:
                raise ValueError('无法定位检测区域绘制初始化')
            updated = updated.replace(anchor, anchor + '\n    ' + watcher, 1)
        if updated != source:
            suffix = hashlib.sha256(updated.encode('utf-8')).hexdigest()[:8]
            new_name = chunk_id + '.' + suffix + '.js'
            (path.parent / new_name).write_text(updated, encoding='utf-8')
            app = app.replace('"' + chunk_id + '":"' + reference.group(1) + '"',
                              '"' + chunk_id + '":"' + suffix + '"', 1)
            index = index.replace(old_name, new_name)
            changed = True
    if changed:
        app_path.write_text(app, encoding='utf-8')
        index_path.write_text(index, encoding='utf-8')
    return changed


def patch_native_role_frontend(root):
    """Storage already uses settings.can_edit; do not override that capability."""
    changed = patch_native_drawing_default(root)
    frontend = Path(root) / 'frontend'
    index = (frontend / 'index.html').read_text(encoding='utf-8')
    script = re.search(r'<script[^>]+src=["\']((?:\./)?static/js/storage-management[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not script:
        raise ValueError('未找到当前存储管理页面脚本')
    relative = script.group(1)
    path = frontend / (relative[2:] if relative.startswith('./') else relative)
    source = path.read_text(encoding='utf-8')
    old = '只有超级管理员可以修改。'
    new = '当前账号没有存储管理修改权限。'
    if new in source:
        return changed
    if source.count(old) != 1:
        raise ValueError('无法定位存储管理权限提示')
    path.write_text(source.replace(old, new, 1), encoding='utf-8')
    return True
