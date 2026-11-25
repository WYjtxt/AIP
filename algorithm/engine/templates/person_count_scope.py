"""Pure count-task scope checks, shared with the deployed inference host.

Only template IDs are read from submitted/saved model metadata. Their types
must be resolved through the caller's trusted server template lookup.
"""
import ast
import json


def _value(config, key):
    return config.get(key) if isinstance(config, dict) else getattr(config, key, None)


def _template_id(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def configured_template_ids(config):
    result = [(0, _template_id(_value(config, 'model_template_config_id')))]
    raw = _value(config, 'model_algo_data_ori')
    if raw is None or raw == '':
        return result
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            try:
                raw = ast.literal_eval(raw)
            except (ValueError, TypeError, SyntaxError):
                raise ValueError('高级算法原始配置无法解析，不能确认人数统计归属')
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError('高级算法原始配置无效，不能确认人数统计归属')
    result.extend((index, _template_id(item.get('model_template_config_id')))
                  for index, item in enumerate(raw, 1))
    return result


def count_model_scopes(config, template_type_lookup):
    """Return actual (model index, template ID) count models; ignore client tcid."""
    return [(index, template_id) for index, template_id in configured_template_ids(config)
            if template_id is not None and is_person_template(template_type_lookup(template_id))]


def is_person_template(template):
    """Quantity templates also include vehicles; tcid alone is insufficient."""
    if isinstance(template, dict):
        kind, name = template.get('model_template_config_type_id'), template.get('model_name')
    elif isinstance(template, (list, tuple)) and len(template) >= 2:
        kind, name = template[:2]
    else:
        kind = getattr(template, 'model_template_config_type_id', None)
        name = getattr(template, 'model_name', None)
    return kind == 3 and str(name or '').strip() in ('人数统计', '人员计数', '人数统计_全身', '人数统计_头肩')


def unique_count_scope(config, template_type_lookup):
    scopes = count_model_scopes(config, template_type_lookup)
    if len(scopes) > 1:
        raise ValueError('同一任务存在多个人数统计模板，不能共享累计人数')
    return scopes[0] if scopes else None
