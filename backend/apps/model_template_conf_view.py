from flask import Response, jsonify, Flask, request, Blueprint,url_for
from config.configs import *
from service.model_template_conf_service import ModelTemplateConfService



# 创建蓝图，对应的register目录（激活操作视图）
model_template = Blueprint('model_template', __name__)


# 算法类型模板大类表数据展示（算法模板大类管理）
@model_template.route('/model_type_template_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_type_template_show():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量

    # 调用服务层方法获取算法类型模板大类列表
    success, result = ModelTemplateConfService.get_model_type_template_list(page, per_page)

    if success:
        return jsonify({'code': 200, 'data': {'code': 200, 'data': result['data'], 'pagination': result['pagination']}})
    else:
        return jsonify({'code': 400, 'msg': result})



# 算法类型模板表数据展示（算法模板管理）
@model_template.route('/model_template_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_show():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    model_type = request.args.get('model_type', type=int)  # 算法类型
    model_template_config_type_id = request.args.get('model_template_config_type_id', type=int)  # 大类id

    # 调用服务层方法获取算法类型模板列表
    success, result = ModelTemplateConfService.get_model_template_list(page, per_page, model_type, model_template_config_type_id)

    if success:
        return jsonify({'code': 200, 'data': {'code': 200, 'data': result['data'], 'pagination': result['pagination']}})
    else:
        return jsonify({'code': 400, 'msg': result})


# 大类下方小类展示（算法模板管理）
@model_template.route('/model_template_small_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_small_show():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    model_template_type_id = request.args.get('model_template_type_id', type=int)  # 模板大类id

    # 调用服务层方法获取算法类型模板小类列表
    success, result = ModelTemplateConfService.get_model_template_small_list(page, per_page, model_template_type_id)

    if success:
        return jsonify({'code': 200, 'data': {'code': 200, 'data': result['data'], 'pagination': result['pagination']}})
    else:
        return jsonify({'code': 400, 'msg': result})


@model_template.route('/model_warnmessage_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_warnmessage_show():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量
    algorithm_name = request.args.get('algorithm_name', type=str)  # 算法类型
    model_template_config_type_id = request.args.get('model_template_config_type_id', type=int)  # 大类id

    # 调用服务层方法获取算法类型模板列表
    success, result = ModelTemplateConfService.get_warn_message_list(page, per_page, algorithm_name, model_template_config_type_id)

    if success:
        return jsonify({'code': 200, 'data': {'code': 200, 'data': result['data'], 'pagination': result['pagination']}})
    else:
        return jsonify({'code': 400, 'msg': result})



@model_template.route('/model_template_detail', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_detail():
    """
    算法类型模板表单详情接口
    参数:
        id (str): 模板ID
    返回:
        JSON响应: 模板详情数据或错误消息
    """

    # 获取模板id
    template_id = request.args.get('id')

    # 参数校验
    if not template_id:
        return jsonify({'code': 400, 'msg': '模板ID未填写'})

    # 调用服务层方法获取算法类型模板详情
    success, result = ModelTemplateConfService.get_model_template_detail(template_id)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 大类下方小类详情（算法模板管理）
@model_template.route('/model_small_detail', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_small_detail():
    """
    算法类型模板表单详情接口
    参数:
        id (str): 模板ID
    返回:
        JSON响应: 模板详情数据或错误消息
    """

    # 获取模板id
    id = request.args.get('id')

    # 参数校验
    if not id:
        return jsonify({'code': 400, 'msg': '模板ID未填写'})

    # 调用服务层方法获取算法类型模板小类详情
    success, result = ModelTemplateConfService.get_model_template_small_detail(id)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 算法类型模板大类表数据详情（算法模板大类管理）
@model_template.route('/model_type_template_detail', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def model_type_template_detail():
    """
    算法类型模板表单详情接口
    参数:
        id (str): 模板ID
    返回:
        JSON响应: 模板详情数据或错误消息
    """

    # 获取模板id
    id = request.args.get('id')

    # 参数校验
    if not id:
        return jsonify({'code': 400, 'msg': '模板ID未填写'})

    # 调用服务层方法获取算法类型模板大类详情
    success, result = ModelTemplateConfService.get_model_type_template_detail(id)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 算法类型模板表数据修改（算法模板管理）
@model_template.route('/model_template_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_update():
    """
    算法类型模板表数据修改接口
    参数:
        id (str): 模板ID
        model_conf_list (str): 基础配置参数
        model_name (str): 算法类型名称
        model_template_config_type_id (str): 算法模板大类id
    返回:
        JSON响应: 修改成功或错误消息
    """

    try:
        # 获取请求参数
        template_id = strip_whitespace(request.form.get('id', None))
        model_conf_list = strip_whitespace(request.form.get('model_conf_list', None))
        model_name = strip_whitespace(request.form.get('model_name', None))
        model_template_config_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))

        # 参数校验
        if not template_id:
            return jsonify({'code': 400, 'msg': '模板ID未填写'})

        # 调用服务层方法更新算法类型模板
        success, message = ModelTemplateConfService.update_model_template(
            template_id, model_name, model_conf_list, model_template_config_type_id
        )

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 大类下方小类修改（算法模板管理）
@model_template.route('/model_template_small_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_small_update():
    try:
        # 获取请求参数
        id = strip_whitespace(request.form.get('id', None))
        list_data = strip_whitespace(request.form.get('list_data', '[{}]'))
        model_template_config_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
        template_small_name = strip_whitespace(request.form.get('template_small_name', ''))
        template_small_number = strip_whitespace(request.form.get('template_small_number', ''))
        template_small_gauss = strip_whitespace(request.form.get('template_small_gauss', ''))
        template_small_threshold = strip_whitespace(request.form.get('template_small_threshold', ''))
        template_small_iou = strip_whitespace(request.form.get('template_small_iou', ''))
        template_small_start = strip_whitespace(request.form.get('template_small_start', ''))
        template_small_end = strip_whitespace(request.form.get('template_small_end', ''))
        template_small_upload = strip_whitespace(request.form.get('template_small_upload', ''))

        # 参数校验
        if not id:
            return jsonify({'code': 400, 'msg': '模板小类ID未填写'})

        # 调用服务层方法更新算法类型模板小类
        success, message = ModelTemplateConfService.update_model_template_small(
            id, model_template_config_type_id, template_small_name,
            template_small_number, template_small_gauss,
            template_small_threshold, template_small_iou,
            template_small_start, template_small_end,
            template_small_upload, list_data
        )

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 算法类型模板大类表数据修改（算法模板大类管理）
@model_template.route('/model_type_template_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_type_template_update():
    try:
        # 获取请求参数
        id = strip_whitespace(request.form.get('id', None))
        model_type_name = strip_whitespace(request.form.get('model_type_name', None))
        model_type_content = strip_whitespace(request.form.get('model_type_content', ''))

        # 参数校验
        if not id:
            return jsonify({'code': 400, 'msg': '模板大类ID未填写'})

        # 调用服务层方法更新算法类型模板大类
        success, message = ModelTemplateConfService.update_model_type_template(id, model_type_name, model_type_content)

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 算法类型模板大类表数据新增（算法模板大类管理）
@model_template.route('/model_warn_maessage_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_warn_maessage_update():
    """
    算法报警信息修改接口
    前端传入：id + algorithm_name + template_type_id + warning_message（数组格式）
    根据传入的字段更新数据库对应记录
    """
    # 获取请求参数
    id = strip_whitespace(request.form.get('id', None))
    algorithm_name = strip_whitespace(request.form.get('algorithm_name', None))
    template_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
    warning_message = strip_whitespace(request.form.get('warning_message', None))
    message_index = strip_whitespace(request.form.get('message_index', None))
    # 解析 warning_message（可能是 JSON 字符串）
    # try:
    #     if warning_message:
    #         warning_message = json.loads(warning_message) if isinstance(warning_message, str) else warning_message
    # except json.JSONDecodeError:
    #     return jsonify({'code': 400, 'msg': 'warning_message 格式错误，需要有效的 JSON 格式'})

    # 参数验证
    if not id or not algorithm_name or not template_type_id:
        return jsonify({'code': 400, 'msg': '信息不全'})


    # 调用服务层批量更新
    success, message = ModelTemplateConfService.update_model_warning_message(
        id, algorithm_name, template_type_id, warning_message,message_index
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})
# 大类下方小类新增（算法模板管理）
@model_template.route('/model_template_small_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_small_add():
    """
    算法类型模板表数据修改接口
    参数:
        model_template_config_type_id (str): 算法模板大类id
        list_data (str): 模板数据
        template_small_name (str): 模板小类名称
    返回:
        JSON响应: 修改成功或错误消息
    """

    # 获取请求参数
    model_template_config_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
    list_data = strip_whitespace(request.form.get('list_data', '[{}]'))
    template_small_name = strip_whitespace(request.form.get('template_small_name', None))

    # 参数构建判断是否为空
    params = [model_template_config_type_id, list_data, template_small_name]

    if not all(params):
        return jsonify({'code': 400, 'msg': '模板数据有未填写项'})

    # 调用服务层方法添加算法类型模板小类
    success, message = ModelTemplateConfService.add_model_template_small(
        model_template_config_type_id, list_data, template_small_name
    )

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})



# 算法类型模板小类数据新增（算法模板管理）
@model_template.route('/model_template_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_add():
    """
    算法类型模板表数据修改接口
    参数:
        model_name (str): 算法类型名称
        model_template_config_type_id (str): 算法模板大类id
    返回:
        JSON响应: 修改成功或错误消息
    """

    # 获取请求参数
    model_name = strip_whitespace(request.form.get('model_name', None))
    model_template_config_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))

    # 参数构建判断是否为空
    params = [model_name, model_template_config_type_id]

    if not all(params):
        return jsonify({'code': 400, 'msg': '模板数据有未填写项'})

    # 调用服务层方法添加算法类型模板
    success, message = ModelTemplateConfService.add_model_template(model_name, model_template_config_type_id)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})



# 算法类型模板大类表数据新增（算法模板大类管理）
@model_template.route('/model_type_template_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_type_template_add():
    """
    算法类型模板表数据修改接口
    参数:
        model_type_content (str): 算法模板大类描述
        model_type_name (str): 算法模板大类名称
    返回:
        JSON响应: 修改成功或错误消息
    """

    # 获取请求参数
    model_type_content = strip_whitespace(request.form.get('model_type_content', None))
    model_type_name = strip_whitespace(request.form.get('model_type_name', None))

    # 参数构建判断是否为空
    params = [model_type_content, model_type_name]

    if not all(params):
        return jsonify({'code': 400, 'msg': '模板数据有未填写项'})

    # 调用服务层方法添加算法类型模板大类
    success, message = ModelTemplateConfService.add_model_type_template(model_type_name, model_type_content)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})

# 算法报警类型表数据新增（算法报警类型新增）
@model_template.route('/model_warn_maessage_add', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_warn_maessage_add():
    """
    为算法配置添加一条新的报警信息
    参数:
        algorithm_name (str): 算法名称
        model_template_config_type_id (int): 模板大类ID
        warning_message (str): 报警信息内容
    返回:
        自动分配 message_index（从1开始递增）
    """
    # 获取请求参数
    algorithm_name = strip_whitespace(request.form.get('algorithm_name', None))
    template_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
    warning_message = strip_whitespace(request.form.get('warning_message', None))

    # 参数校验
    params = [algorithm_name, template_type_id, warning_message]
    if not all(params):
        return jsonify({'code': 400, 'msg': '报警信息有未填写项'})

    # 调用服务层方法添加报警信息
    success, message = ModelTemplateConfService.add_model_warning_message(algorithm_name, template_type_id,
                                                                          warning_message)
    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 算法类型模板表数据删除（算法模板管理）
@model_template.route('/model_template_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_delete():
    try:
        # 获取请求参数
        template_id = strip_whitespace(request.form.get('id', None))
        # 参数校验
        if not template_id:
            return jsonify({'code': 400, 'msg': '要删除ID未填写'})

        # 调用服务层方法删除算法类型模板
        success, message = ModelTemplateConfService.delete_model_template(template_id)

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})





# 算法类型模板表数据删除（算法模板管理）
@model_template.route('/model_template_small_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_template_small_delete():
    try:
        # 获取请求参数
        template_id = strip_whitespace(request.form.get('id', None))
        # 参数校验
        if not template_id:
            return jsonify({'code': 400, 'msg': '要删除ID未填写'})

        # 调用服务层方法删除算法类型模板小类
        success, message = ModelTemplateConfService.delete_model_template_small(template_id)

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


# 算法类型模板大类表数据删除（算法模板大类管理）
@model_template.route('/model_type_template_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_type_template_delete():
    try:
        # 获取请求参数
        template_id = strip_whitespace(request.form.get('id', None))
        # 参数校验
        if not template_id:
            return jsonify({'code': 400, 'msg': '要删除ID未填写'})

        # 调用服务层方法删除算法类型模板大类
        success, message = ModelTemplateConfService.delete_model_type_template(template_id)

        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})

# 算法类型模板大类表数据删除（算法模板大类管理）
# @model_template.route('/model_warning_message_delete', methods=['POST'])
# # @jwt_required()
# @jwt_required_with_refresh
# def model_warning_message_delete():
#     """
#     删除算法报警信息接口
#     支持两种删除场景：
#     1. 删除单条报警：传 id + message_index
#     2. 删除整个算法的所有报警：传 id（不传 message_index）
#     """
#     try:
#         # 获取请求参数
#         id = strip_whitespace(request.form.get('id', None))
#         algorithm_name = strip_whitespace(request.form.get('algorithm_name', None))
#         template_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
#         message_index = strip_whitespace(request.form.get('message_index', None))
#
#         # 参数验证 - id 必须传入
#         if not id:
#             return jsonify({'code': 400, 'msg': '缺少参数'})
#
#         if message_index:
#             # 场景1：删除单条报警（根据 message_index）
#             success, message = ModelTemplateConfService.delete_model_warning_message_by_index(
#                 id, algorithm_name, template_type_id, int(message_index)
#             )
#         else:
#             # 场景2：删除整个算法的所有报警
#             success, message = ModelTemplateConfService.delete_all_warning_messages_by_algorithm(
#                 id, algorithm_name, template_type_id
#             )
#
#         if success:
#             return jsonify({'code': 200, 'msg': message})
#         else:
#             return jsonify({'code': 400, 'msg': message})
#
#     except Exception as e:
#         return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})


@model_template.route('/model_warning_message_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def model_warning_message_delete():
    """
    删除算法报警信息接口
    支持两种删除场景：
    1. 删除单条报警：传 id + message_index
    2. 删除整个算法的所有报警：传 id（不传 message_index）
    """
    try:
        # 获取请求参数
        id = strip_whitespace(request.form.get('id', None))
        # algorithm_name = strip_whitespace(request.form.get('algorithm_name', None))
        # template_type_id = strip_whitespace(request.form.get('model_template_config_type_id', None))
        # message_index = strip_whitespace(request.form.get('message_index', None))

        # 参数验证 - id 必须传入
        if not id:
            return jsonify({'code': 400, 'msg': '缺少参数'})

        # 场景1：删除单条报警（根据 message_index）
        success, message = ModelTemplateConfService.delete_model_warning_message_by_id(
            id
        )


        if success:
            return jsonify({'code': 200, 'msg': message})
        else:
            return jsonify({'code': 400, 'msg': message})

    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'})



