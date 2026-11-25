from flask import jsonify, request, Blueprint
from service.ZiguangVMSClient_service import ZiguangVMSService

# 创建蓝图
ziguang_platform_info_view = Blueprint('ziguang_platform_info_view', __name__)

@ziguang_platform_info_view.route('/ziguang_platform_add', methods=['POST'])
def ziguang_platform_add():
    """
    获取紫光平台视频数据
    :param ziguang_host: 主机地址
    :param ziguang_port: 端口号
    :param ziguang_id: 合作方id
    :param ziguang_password: 合作方密码
    :return: 视频区域列表或错误信息
    """
    ziguang_host = request.form.get('ziguang_host', None)
    ziguang_port = request.form.get('ziguang_port', 9000)
    ziguang_id = request.form.get('ziguang_id', None)
    ziguang_password = request.form.get('ziguang_password', None)
    Mine_id = request.form.get('Mine_id', None)

    service = ZiguangVMSService()
    result = service.add_ziguang_platform(ziguang_host, ziguang_port, ziguang_id, ziguang_password, Mine_id)
    return jsonify(result)

@ziguang_platform_info_view.route('/ziguang_security_platform_delete', methods=['POST'])
def ziguang_security_platform_delete():
    """
    删除紫光华智信息。
    参数:
        id (str): 紫光华智信息的主键 ID。
    """
    id = request.form.get('id', None)
    service = ZiguangVMSService()
    result = service.delete_ziguang_platform(id)
    return jsonify(result)

@ziguang_platform_info_view.route('/ziguang_security_platform_data', methods=['GET'])
def ziguang_security_platform_data():
    """
    查询紫光华智平台信息
    """
    type_st = request.args.get('type_st', None)
    id = request.args.get('id', None)
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=15, type=int)

    service = ZiguangVMSService()
    result = service.get_ziguang_platform_data(type_st, id, page, per_page)
    return jsonify(result)
