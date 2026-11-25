"""Shared identity rules for people-count templates, never model/label aliases.

Install unchanged as comm.count_algorithm_family and service.count_algorithm_family.
Reusing a template must retain the selected library's model path and class names.
"""
import re


FULL_BODY_COUNT_NAME = '人数统计_全身'
HEAD_SHOULDER_COUNT_NAME = '人数统计_头肩'
_PERSON_COUNT_VARIANT_NAMES = (FULL_BODY_COUNT_NAME, HEAD_SHOULDER_COUNT_NAME)


def is_count_model_name(value):
    name = str(value or '').strip()
    return '人数统计' in name or name == '人员计数'


def _analysis_name(value):
    name = str(value or '').strip()
    return '' if name.lower() in ('', '0', '00', 'none', 'null', 'undefined') else name


def count_template_matches(library_name, template_name, type_id, analysis_type=None):
    library_name = str(library_name or '').strip()
    template_name = str(template_name or '').strip()
    analysis_name = _analysis_name(analysis_type) or library_name
    if is_count_model_name(analysis_name) or is_count_model_name(template_name):
        return (is_count_model_name(analysis_name) and is_count_model_name(template_name)
                and not isinstance(type_id, bool) and str(type_id) == '3')
    return bool(library_name) and library_name == template_name


def algorithm_display_name(algorithm_name, model_name='', fallback='', analysis_type=None):
    analysis_name = _analysis_name(analysis_type)
    if analysis_name:
        return analysis_name[:120]
    name = str(algorithm_name or '').strip()
    # Package naming is vendor_analysis_category_template_..._version_parent_child.
    # Generic template names intentionally do not erase variants such as 全身.
    stem = re.sub(r'\.(?:zip|om|bmodel|rknn)$', '', name, flags=re.I)
    parts = stem.split('_')
    if stem in _PERSON_COUNT_VARIANT_NAMES:
        return stem
    if len(parts) >= 13 and parts[3] == '数量统计类':
        variant_name = '_'.join(parts[1:3])
        if variant_name in _PERSON_COUNT_VARIANT_NAMES:
            return variant_name
    if len(parts) >= 12 and parts[1].strip() and parts[2].endswith('类') and parts[3].strip():
        return parts[1].strip()[:120]
    model = str(model_name or '').strip()
    if model:
        return model[:120]
    if name and len(name) <= 60 and not re.search(r'\.(?:zip|om|bmodel|rknn)$', name, re.I):
        return name
    return str(fallback or '')
