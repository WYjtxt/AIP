from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.log_service import LogService

# 创建蓝图，对应的register目录（激活操作视图）
log_view = Blueprint('log_view', __name__)

# 日志信息展示
@log_view.route('/log_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def log_data():

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    level = request.args.get('level')  # 日志等级

    # 调用服务层方法获取日志数据
    success, result = LogService.get_log_data(page, per_page, level)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})




