from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.hik_security_platform_service import HikSecurityPlatformService



# 创建蓝图，对应的register目录（激活操作视图）
hik_security_platform_info_view = Blueprint('hik_security_platform_info_view', __name__)

# 海康安防平台区域数据接入（安防平台）
# hik-connection-form-v1
def _hik_connection_form():
    names = ('hik_host', 'hik_port', 'hik_scheme', 'hik_appKey', 'hik_appSecret')
    return {name: request.form.get(name, '').strip() for name in names}


def _hik_connection_failure(message, reason='invalid_config'):
    return jsonify({'code': 400, 'msg': message, 'data': {'reason': reason}})


@hik_security_platform_info_view.route('/hik_security_platform_test', methods=['POST'])
def hik_security_platform_test():
    from flask import g
    from common.platform_access import has_menu_permission
    from tool.hik_gateway import HikGateway, HikGatewayError

    user = getattr(g, 'platform_user', None)
    if user is None or not has_menu_permission(user.id, 'hkaf_sbtb', 'c'):
        return jsonify({'code': 403, 'msg': '没有接入海康安防平台的权限'}), 403
    try:
        result = HikGateway(_hik_connection_form()).test_connection()
    except HikGatewayError as error:
        return _hik_connection_failure(str(error), getattr(error, 'reason', 'gateway_error'))
    except Exception:
        return jsonify({'code': 500, 'msg': '连接测试失败，请稍后重试'}), 500
    return jsonify({'code': 200, 'msg': '连接成功', 'data': result})


@hik_security_platform_info_view.route('/hik_security_platform_add', methods=['POST'])
# @jwt_required()
def hik_security_platform_add():
    from tool.hik_gateway import HikGateway, HikGatewayError

    form = _hik_connection_form()
    mine_id = request.form.get('Mine_id', '').strip()
    if not mine_id or any(not form[name] for name in ('hik_host', 'hik_appKey', 'hik_appSecret')):
        return _hik_connection_failure('设备数据有未填写项')
    try:
        gateway = HikGateway(form)
    except HikGatewayError as error:
        return _hik_connection_failure(str(error), getattr(error, 'reason', 'gateway_error'))

    success, message = HikSecurityPlatformService.add_hik_security_platform(
        gateway.host, str(gateway.port), form['hik_appKey'], form['hik_appSecret'], mine_id)
    return jsonify({'code': 200 if success else 400, 'msg': message})


# 海康安防平台资源信息联动删除（安防平台）
@hik_security_platform_info_view.route('/hik_security_platform_delete', methods=['POST'])
def hik_security_platform_delete():
    from flask import g
    from common.platform_access import has_menu_permission

    user = getattr(g, 'platform_user', None)
    if user is None or not has_menu_permission(user.id, 'hkaf_sbtb', 'd'):
        return jsonify({'code': 403, 'msg': '没有删除安防平台的权限'}), 403

    ids = request.form.getlist('id')
    if len(ids) != 1:
        return jsonify({'code': 400, 'msg': '请选择一个有效的安防平台'})
    raw_id = ids[0].strip()
    if (not 1 <= len(raw_id) <= 10 or not raw_id.isascii() or not raw_id.isdecimal()
            or not 1 <= int(raw_id) <= 2147483647):
        return jsonify({'code': 400, 'msg': '请选择一个有效的安防平台'})

    try:
        success, message = HikSecurityPlatformService.delete_hik_security_platform(int(raw_id))
        return jsonify({'code': 200 if success else 400, 'msg': message})
    except Exception:
        return jsonify({'code': 500, 'msg': '删除安防平台失败，请稍后重试'})


# 海康安防平台信息展示（安防平台）
@hik_security_platform_info_view.route('/hik_security_platform_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def hik_security_platform_data():
    """
    海康安防平台信息展示
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=15, type=int)

    # 调用服务层获取海康安防平台信息列表
    success, result = HikSecurityPlatformService.get_hik_security_platform_data(page, per_page)

    if success:
        from flask import g
        from common.platform_access import has_menu_permission

        user = getattr(g, 'platform_user', None)
        result['can_delete'] = user is not None and has_menu_permission(user.id, 'hkaf_sbtb', 'd')
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 海康安防平台资源信息展示（安防平台）
@hik_security_platform_info_view.route('/hik_security_platform_resource_data', methods=['GET'])
# @jwt_required()
def hik_security_platform_resource_data():
    """
    海康安防平台资源信息展示
    id (str)  二级区域id

    page (str)  第几页
    per_page (str)  每页条数
    """

    # 点击二级区域详情获取下方对应数据，及二级区域主数据

    # 二级区域安防信息id
    id = request.args.get('id',None)

    # 第几页
    page = request.args.get('page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=15, type=int)

    params = [id]

    # 当必传参数没填，返回错误
    if not all(params):
        return jsonify({'code': 400, 'msg': '参数状态未有！'})

    # 调用服务层获取海康安防平台资源信息
    success, result = HikSecurityPlatformService.get_hik_security_platform_resource_data(id, page, per_page)

    if success:
        return jsonify({'code': 200, 'msg': "查询成功", 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


