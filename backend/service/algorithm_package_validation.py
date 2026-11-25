"""Validate algorithm packages before SSH, database writes, or filesystem writes.

This module deliberately does not load or convert any model. The extension is a
runtime contract: OM -> Ascend, BMODEL -> Sophon, RKNN -> Rockchip. Historical OM
filenames can retain a Sophon/RK source vendor/chip after an explicit conversion.
"""
from dataclasses import dataclass
import io
import posixpath
import re
import stat
import zipfile

import yaml


MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MAX_UNPACKED_BYTES = 256 * 1024 * 1024
MAX_YAML_BYTES = 1024 * 1024
MAX_MEMBERS = 512
MAX_GROUP_PACKAGES = 64
MODEL_FAMILIES = {'.om': 'ascend', '.bmodel': 'sophon', '.rknn': 'rockchip'}
FAMILY_LABELS = {'ascend': '昇腾（.om）', 'sophon': '算能（.bmodel）', 'rockchip': '瑞芯微（.rknn）'}
LEGACY_PERSON_COUNT_NAME = '人数统计'
FULL_BODY_COUNT_NAME = '人数统计_全身'
HEAD_SHOULDER_COUNT_NAME = '人数统计_头肩'
_PERSON_COUNT_VARIANTS = {'全身': FULL_BODY_COUNT_NAME, '头肩': HEAD_SHOULDER_COUNT_NAME}


class AlgorithmPackageError(ValueError):
    """A user-correctable validation failure; never includes credentials."""


@dataclass(frozen=True)
class AlgorithmPackage:
    model_member: str
    yaml_member: str
    filename: str
    extension: str
    words: tuple
    labels: tuple
    class_count: int

    @property
    def family(self):
        return MODEL_FAMILIES[self.extension]

    @property
    def trade(self):
        return self.words[7].casefold()

    @property
    def chip(self):
        return self.words[8]

    @property
    def algorithm_type(self):
        return '1' if self.class_count > 1 else '2'

    def display_name(self, mine_name):
        return '_'.join((str(mine_name),) + self.words[1:])


def read_uploaded_zip(uploaded_file):
    if uploaded_file is None or not str(uploaded_file.filename or '').casefold().endswith('.zip'):
        raise AlgorithmPackageError('文件格式不正确，请导入 ZIP 格式压缩包')
    stream = uploaded_file.stream
    stream.seek(0)
    content = stream.read(MAX_UPLOAD_BYTES + 1)
    stream.seek(0)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AlgorithmPackageError('文件大小超过 60MB 限制，请重新上传')
    if not content:
        raise AlgorithmPackageError('上传的 ZIP 文件为空')
    return content


def open_package_zip(content):
    try:
        return zipfile.ZipFile(io.BytesIO(content), 'r')
    except (zipfile.BadZipFile, ValueError, OSError):
        raise AlgorithmPackageError('ZIP 压缩包损坏或格式不正确')


def _decoded_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        raw = info.filename.encode('cp437')
    except UnicodeEncodeError:
        return info.filename
    for codec in ('utf-8', 'gbk'):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            pass
    return info.filename


def _entries(archive):
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise AlgorithmPackageError('压缩包文件数量超过限制（最多 512 项）')
    total = 0
    entries = {}
    for info in infos:
        decoded = _decoded_name(info).replace('\\', '/')
        if any(ord(char) < 32 or ord(char) == 127 for char in decoded):
            raise AlgorithmPackageError('压缩包文件路径包含不安全的控制字符')
        if decoded.startswith('/') or re.match(r'^[A-Za-z]:', decoded):
            raise AlgorithmPackageError('压缩包包含不安全的绝对路径')
        parts = decoded.rstrip('/').split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise AlgorithmPackageError('压缩包包含不安全的文件路径')
        if stat.S_ISLNK(info.external_attr >> 16):
            raise AlgorithmPackageError('压缩包不允许包含符号链接')
        if info.flag_bits & 1:
            raise AlgorithmPackageError('不支持加密 ZIP 压缩包')
        key = '/'.join(parts).casefold()
        if key in entries:
            raise AlgorithmPackageError('压缩包存在重名文件（忽略大小写后重复）')
        entries[key] = (info, '/'.join(parts))
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise AlgorithmPackageError('压缩包解压后大小超过 256MB 限制')
    return [(info, name) for info, name in entries.values()
            if not info.is_dir() and not name.startswith('__MACOSX/')
            and not posixpath.basename(name).startswith('._')]


def _read(archive, info, maximum):
    if info.file_size > maximum:
        raise AlgorithmPackageError('压缩包内文件大小超过限制')
    try:
        with archive.open(info) as stream:
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise AlgorithmPackageError('压缩包内文件大小超过限制')
        return content
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError):
        raise AlgorithmPackageError('无法读取压缩包内容，请检查 ZIP 文件是否损坏')


def _metadata(archive, info):
    try:
        data = yaml.safe_load(_read(archive, info, MAX_YAML_BYTES))
    except yaml.YAMLError:
        raise AlgorithmPackageError('data.yaml 格式错误，请检查 YAML 内容')
    if not isinstance(data, dict):
        raise AlgorithmPackageError('data.yaml 必须是包含 nc 和 lables 的配置对象')
    count = data.get('nc')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > 1024:
        raise AlgorithmPackageError('data.yaml 的 nc 必须是 1 至 1024 的整数')
    labels = data.get('lables')
    if not isinstance(labels, list) or len(labels) != count:
        raise AlgorithmPackageError('data.yaml 的 lables 列表长度必须与 nc 一致')
    normalized = []
    seen = set()
    for label in labels:
        if not isinstance(label, dict):
            raise AlgorithmPackageError('data.yaml 每个标签必须包含 lable 和 name')
        english, chinese = label.get('lable'), label.get('name')
        if not isinstance(english, str) or not english.strip() or len(english) > 50:
            raise AlgorithmPackageError('data.yaml 的 lable 必须是非空字符串且不超过 50 字符')
        if not isinstance(chinese, str) or not chinese.strip() or len(chinese) > 50:
            raise AlgorithmPackageError('data.yaml 的 name 必须是非空字符串且不超过 50 字符')
        english, chinese = english.strip(), chinese.strip()
        if english in seen:
            raise AlgorithmPackageError('data.yaml 中的 lable 不允许重复')
        seen.add(english)
        normalized.append({'lable': english, 'name': chinese})
    return count, tuple(normalized)


def split_algorithm_filename_fields(stem):
    """Preserve the qualified people-count label in its package name fields."""
    words = stem.split('_')
    if len(words) < 4 or words[1] != LEGACY_PERSON_COUNT_NAME or words[3] != '数量统计类':
        return tuple(words)
    suffix = words[2]
    variant = _PERSON_COUNT_VARIANTS.get(suffix)
    if variant is None:
        return tuple(words)
    words[1:3] = [variant]
    for index in (3, 4):
        if words[index:index + 2] == [LEGACY_PERSON_COUNT_NAME, suffix]:
            words[index:index + 2] = [variant]
    return tuple(words)


def _is_preinstalled_sophon_count(words, name):
    return (len(words) >= 12 and words[1:5] == (name, '数量统计类', name, name)
            and tuple(word.casefold() for word in words[5:9]) == ('yolov11s', 'int8', 'sophon', 'bm1684x')
            and words[10:12] == ('1', '1'))


def package_upgrade_analysis_types(package):
    """Only the built-in BM1684X count model can upgrade its historical name."""
    name = package.words[1]
    if (package.extension == '.bmodel' and _is_preinstalled_sophon_count(package.words, FULL_BODY_COUNT_NAME)
            and package.labels == ({'lable': 'person', 'name': '人'},)):
        return (name, LEGACY_PERSON_COUNT_NAME)
    return (name,)


def inspect_algorithm_package(archive):
    entries = _entries(archive)
    model_entries = [(info, name) for info, name in entries
                     if posixpath.splitext(name)[1].casefold() in MODEL_FAMILIES]
    if not model_entries:
        if any(name.casefold().endswith('.zip') for _, name in entries):
            raise AlgorithmPackageError('这是算法组包，请使用“上传算法组包”；单算法包应直接包含模型和 data.yaml')
        raise AlgorithmPackageError('压缩包内未找到模型文件，支持 .om、.bmodel、.rknn（需匹配目标硬件）')
    if len(model_entries) != 1:
        raise AlgorithmPackageError('单算法包只能包含一个模型；多个算法请分别打包后使用“上传算法组包”')
    model_info, model_path = model_entries[0]
    if model_info.file_size == 0:
        raise AlgorithmPackageError('算法模型文件为空')
    filename = posixpath.basename(model_path)
    extension = posixpath.splitext(filename)[1].casefold()
    stem = filename[:-len(extension)]
    words = split_algorithm_filename_fields(stem)
    if len(words) < 12 or any(not part.strip() for part in words[:12]):
        raise AlgorithmPackageError('模型文件名不符合平台规范：至少需要 12 个下划线分隔字段（含解析类型、模板、厂商、芯片、版本和父子类）')
    if len(filename.encode('utf-8')) > 255 or any(len(words[i]) > 255 for i in (1, 2, 3, 4)) or len(words[9]) > 32:
        raise AlgorithmPackageError('模型文件名或配置字段过长')
    if not re.fullmatch(r'[1-9][0-9]{0,8}', words[10]) or not re.fullmatch(r'[1-9][0-9]{0,8}', words[11]):
        raise AlgorithmPackageError('模型文件名中的算法父类和子类必须是正整数')
    parent = posixpath.dirname(model_path).casefold()
    yaml_entries = [(info, name) for info, name in entries
                    if posixpath.basename(name).casefold() == 'data.yaml'
                    and posixpath.dirname(name).casefold() == parent]
    if len(yaml_entries) != 1:
        raise AlgorithmPackageError('模型文件所在目录缺少唯一的 data.yaml；模型和 data.yaml 应放在同一目录')
    yaml_info, _ = yaml_entries[0]
    count, labels = _metadata(archive, yaml_info)
    # Upload a basename only; never propagate the ZIP wrapper directory to SFTP.
    filename = filename[:-len(extension)] + extension
    return AlgorithmPackage(model_info.filename, yaml_info.filename, filename, extension,
                            words, labels, count)


def inspect_algorithm_group(archive):
    entries = _entries(archive)
    if any(posixpath.splitext(name)[1].casefold() in MODEL_FAMILIES for _, name in entries):
        raise AlgorithmPackageError('这是单算法包，请使用“上传算法包”；组包应包含各算法的 ZIP 子包')
    children = [(info, name) for info, name in entries if name.casefold().endswith('.zip')]
    if not children:
        raise AlgorithmPackageError('算法组包中没有 ZIP 子包，请检查打包结构')
    if len(children) > MAX_GROUP_PACKAGES:
        raise AlgorithmPackageError('算法组包最多包含 64 个 ZIP 子包')
    result = {}
    total = 0
    for info, name in children:
        content = _read(archive, info, MAX_UPLOAD_BYTES)
        with open_package_zip(content) as child:
            total += sum(item.file_size for item in child.infolist())
            if total > MAX_UNPACKED_BYTES:
                raise AlgorithmPackageError('算法组包解压后总大小超过 256MB 限制')
            try:
                package = inspect_algorithm_package(child)
            except AlgorithmPackageError as error:
                raise AlgorithmPackageError('子压缩包 %s：%s' % (name, error))
        result[info.filename] = package
    return result


def hardware_family(target):
    token = re.sub(r'[^a-z0-9]', '', str(target or '').casefold())
    if token.startswith('ascend') or token.startswith('atlas') or token.startswith('huawei'):
        return 'ascend'
    if re.search(r'(?:^|sophon)bm(?:1684x?|1688)', token) or token.startswith('sophon'):
        return 'sophon'
    if token.startswith('rk35') or token.startswith('rv11') or token.startswith('rockchip'):
        return 'rockchip'
    return None


def matching_device_ids(package, resources, allowed_device_ids):
    """Return only explicitly detected compatible devices, never infer from IP.

    resources are dicts with computing_id and dev_get_target (database columns).
    Native BM/RK chip names must match; historical converted OM source names are
    accepted on Ascend because the file extension describes the new runtime.
    """
    allowed = {str(item) for item in allowed_device_ids}
    chip = re.sub(r'[^a-z0-9]', '', package.chip.casefold())
    result = set()
    for resource in resources:
        device_id = str(resource.get('computing_id'))
        target = re.sub(r'[^a-z0-9]', '', str(resource.get('dev_get_target') or '').casefold())
        if device_id not in allowed or hardware_family(target) != package.family:
            continue
        if hardware_family(chip) == package.family:
            if chip != target and not target.endswith(chip):
                continue
        result.add(device_id)
    return result


def require_matching_devices(package, resources, allowed_device_ids):
    matched = matching_device_ids(package, resources, allowed_device_ids)
    if not matched:
        raise AlgorithmPackageError('没有检测到与 %s 模型匹配的目标设备，请检查设备类型和算力资源；上传不会进行模型格式转换' % FAMILY_LABELS[package.family])
    return matched


def require_server_package(package):
    if package.family == 'rockchip':
        raise AlgorithmPackageError('检测到瑞芯微 RKNN 模型，请在“AI摄像仪算法安装”上传；该入口会单独入摄像仪算法库，再选择摄像仪下发，不能作为昇腾服务器算法运行')


def require_camera_package(package):
    if package.extension != '.rknn':
        raise AlgorithmPackageError('AI摄像仪算法安装仅接收瑞芯微 .rknn 模型；.om 和 .bmodel 请使用“智能算法安装”并匹配对应算力设备')


def canonical_algorithm_zip(archive, package):
    """Repackage only the validated model and YAML at ZIP root, without conversion.

    Camera firmware may still require root-level YAML and a lowercase suffix.
    Preserve both file payloads exactly; only ZIP names/structure are normalized.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        model_info = archive.getinfo(package.model_member)
        target.writestr(package.filename, _read(archive, model_info, MAX_UNPACKED_BYTES))
        target.writestr('data.yaml', _read(archive, archive.getinfo(package.yaml_member), MAX_YAML_BYTES))
    content = output.getvalue()
    if len(content) > MAX_UPLOAD_BYTES:
        raise AlgorithmPackageError('整理后的单算法 ZIP 超过 60MB 限制，请重新打包')
    return content


def same_model_slot(filename, package):
    """An upgrade must not replace another vendor/chip or a cascade sibling."""
    filename = posixpath.basename(str(filename or '').replace('\\', '/'))
    extension = posixpath.splitext(filename)[1].casefold()
    if extension != package.extension:
        return False
    words = split_algorithm_filename_fields(filename[:-len(extension)])
    if len(words) < 12:
        return False
    if not all(words[index].casefold() == package.words[index].casefold()
               for index in (7, 8, 10, 11)):
        return False
    if words[1].casefold() == package.words[1].casefold():
        return True
    return (LEGACY_PERSON_COUNT_NAME in package_upgrade_analysis_types(package)
            and _is_preinstalled_sophon_count(words, LEGACY_PERSON_COUNT_NAME))
