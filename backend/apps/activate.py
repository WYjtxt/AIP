from flask import Response, jsonify, Flask, request, Blueprint, url_for
from config.configs import *
from service.activate_service import ActivateService

# 创建蓝图，对应的register目录（激活操作视图）
activate = Blueprint('activate', __name__)


def _bootstrap_repository():
    from common.activation_bootstrap import ActivationRepository
    from data.exts import db
    from model.admin import Activate_info
    return ActivationRepository(db, Activate_info)


@activate.route('/bootstrap', methods=['GET'])
def activation_bootstrap():
    from common.activation_bootstrap import issue_challenge
    from common.platform_origins import allowed_origins
    return issue_challenge(_bootstrap_repository(), allowed_origins())


@activate.route('/bootstrap_upload', methods=['POST'])
def activation_bootstrap_upload():
    from common.activation_bootstrap import import_first_activation
    from common.platform_origins import allowed_origins
    return import_first_activation(_bootstrap_repository(), allowed_origins(), activate_key, get_machine_uuid())


# 产品信息获取生成ak文件
@activate.route('/product_information', methods=['POST'])
def product_information():
    # 用户名称
    username = strip_whitespace(request.form.get('username', None))
    # 公司
    company = strip_whitespace(request.form.get('company', None))
    # 国家
    nation = strip_whitespace(request.form.get('nation', None))
    # 电话
    mobile = strip_whitespace(request.form.get('mobile', None))
    # 省
    province = strip_whitespace(request.form.get('province', None))
    # 市
    city = strip_whitespace(request.form.get('city', None))
    # 地址
    address = strip_whitespace(request.form.get('address', None))
    # 激活时间
    time = strip_whitespace(request.form.get('time', None))

    # 机器序列code
    uuid_code = strip_whitespace(request.form.get('uuid_code', None))


    # 添加有效期（例如，有效期30天）
    valid_until = strip_whitespace(request.form.get('valid_until', None))

    # 参数构建判断是否为空
    params = [username, company, nation, mobile, province, city, address, time, uuid_code, valid_until]

    if not all(params):
        return jsonify({'code': 400, 'msg': '设备数据有未填写项'})

    # 调用服务层生成ak文件
    success, result = ActivateService.generate_ak_file(
        username, company, nation, mobile, province, city, address, time, uuid_code, valid_until
    )

    if success:
        return jsonify({'code': 200, 'msg': 'ak激活码文件生成', 'file': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# ak激活文件上传及验证
@activate.route('/product_upload', methods=['POST'])
def product_upload():
    # 解析ak文件内容
    files = request.files.get('files', None)

    # 判断当文件存在时
    if files:
        # 调用服务层验证ak文件
        success, msg = ActivateService.validate_ak_file(files)

        if success:
            return jsonify({'code': 200, 'msg': msg})
        else:
            return jsonify({'code': 400, 'msg': msg})
    else:
        return jsonify({'code': 400, 'msg': 'ak文件未上传!', })


# 平台激活序列判断
@activate.route('/activate_verify', methods=['GET'])
def activate_verify():
    # 调用服务层验证激活状态
    success, msg = ActivateService.verify_activation_status()

    if success:
        return jsonify({"msg": msg, 'code': 200})
    else:
        return jsonify({"msg": msg, 'code': 400})


# 激活序列内容编码展示
@activate.route('/activate_show', methods=['GET'])
def activate_show():
    # 调用服务层获取激活信息
    success, data = ActivateService.get_activate_info()

    if success:
        return jsonify({"msg": "查询成功", 'data': data})
    else:
        return jsonify({"msg": "查询失败", 'data': []})
