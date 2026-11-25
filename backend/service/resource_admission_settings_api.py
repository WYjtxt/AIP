# native-role-policy-v1
"""Super-administrator settings endpoint using the platform's live account policy."""
from flask import g, jsonify, request
from sqlalchemy import LargeBinary, cast

from data.exts import db
from model.admin import Permission, UserPermission
from service.resource_admission_settings import read_settings, save_settings, SettingsConflict


def is_administrator(user_id):
    from service.platform_role_policy import is_superadmin
    return is_superadmin(user_id)


def settings_response():
    if not is_administrator(g.platform_user.id):
        return jsonify({'code': 403, 'msg': '只有超级管理员可查看和修改算力调度设置'}), 403
    from service.resource_admission import seed_policy
    try:
        seed = seed_policy()
        if request.method == 'POST':
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {'policy', 'revision'}:
                raise ValueError('请提交完整配置及当前版本')
            data = save_settings(body['policy'], body['revision'], g.platform_user.username, seed)
        else:
            data = read_settings(seed)
        from service.resource_admission import snapshot
        from service.resource_admission_policy import warmup_seconds
        data['can_edit'] = True
        data['effective_observation_seconds'] = warmup_seconds(data['policy'])
        try:
            data['hosts'] = list(snapshot()['hosts'].values())
            data['telemetry_available'] = True
        except Exception:
            data['hosts'] = []
            data['telemetry_available'] = False
        return jsonify({'code': 200, 'msg': '配置已保存并生效' if request.method == 'POST' else '查询成功', 'data': data})
    except SettingsConflict as error:
        return jsonify({'code': 409, 'msg': str(error)}), 409
    except ValueError as error:
        return jsonify({'code': 400, 'msg': str(error)}), 400
    except Exception:
        return jsonify({'code': 503, 'msg': '算力调度设置暂不可用，请稍后重试'}), 503
