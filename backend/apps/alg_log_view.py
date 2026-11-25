from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.alg_log_service import AlgLogService

# 创建蓝图，对应的register目录（激活操作视图）
alg_log_view = Blueprint('alg_log_view', __name__)

# 算法日志信息展示
@alg_log_view.route('/alg_log_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def alg_log_data():

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    level = request.args.get('level')  # 日志等级
    alg_name = request.args.get('alg_name')  # 算法配置名称

    # 调用服务层获取算法日志数据
    success, result = AlgLogService.get_alg_log_data(page, per_page, level, alg_name)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 平台登录日志信息展示
@alg_log_view.route('/platform_login_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def platform_login_data():

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    status = request.args.get('status')  # 成功 失败 异常

    # 调用服务层获取平台登录日志数据
    success, result = AlgLogService.get_platform_login_data(page, per_page, status)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})
