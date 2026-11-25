import os
import dbutils.steady_db
from flask import jsonify, request, Blueprint
from config.configs import *
from service.model_views_service import ModelViewsService

# 创建数据操作蓝图1，对应的register目录
model_views = Blueprint('model_views', __name__)

#离线状态的全局变量 默认为True
offline_status = True
#本次离线持续时间
offline_keepTime = 0
#设备的离线开始时间
offline_start_time = None


# --------新筛选，录像机-监控点--------
@model_views.route('/vcr_em_select', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def vcr_em_select():
    # 录像机ip
    vcr_id = request.args.get('vcr_id')

    # 当选择录像机的时候展示录像机下子集数据
    if vcr_id:
        # 调用服务层方法获取录像机下监控点列表数据
        success, result = ModelViewsService.get_equipment_by_vcr_id(vcr_id)
        if success:
            return jsonify({'code': 200, 'msg': '查询成功', 'em_data': result})
        else:
            return jsonify({'code': 400, 'msg': result})

    # 当未选择录像机展示全部
    else:
        # 调用服务层方法获取所有设备信息
        success, result = ModelViewsService.get_all_equipment()
        if success:
            return jsonify({'code': 200, 'msg': '查询成功',
                            'var_data_name': '录像机列表',
                            'var_data': result,
                            })
        else:
            return jsonify({'code': 400, 'msg': result})


# --------诊断数据展示接口--------
@model_views.route('/diagnosis_all', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def diagnosis_all():

    # 录像机设备id
    equipment_id = request.args.getlist("vcr_id[]")

    # 取前两个
    first_vcr_id = equipment_id[0] if len(equipment_id) > 0 else None
    second_vcr_id = equipment_id[1] if len(equipment_id) > 1 else None

    # 诊断状态   达标  一般  很差  失败
    diagnosis_type = request.args.get('diagnosis_type')

    # 开始时间
    start_time = request.args.get('start_time')
    # 结束时间
    end_time = request.args.get('end_time')

    # 第几页
    page = request.args.get('current_page', default=1, type=int)
    # 每页条数
    per_page = request.args.get('per_page', default=15, type=int)

    # 调用服务层方法获取诊断数据
    success, result = ModelViewsService.get_diagnosis_data(
        page, per_page, first_vcr_id, second_vcr_id, diagnosis_type, start_time, end_time
    )

    if success:
        from service.vqd_reference import can_set_reference
        result['can_set_reference'] = can_set_reference()
        return jsonify({'code': 200, 'msg': '查询成功', 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


#监测点离线信息
@model_views.route('/monitorPoint_offline',methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def monitorPoint_offline():
    # 调用服务层方法获取监测点离线信息
    success, message = ModelViewsService.get_monitor_point_offline()

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


@model_views.route('/diagnosis_reference', methods=['POST'])
@jwt_required_with_refresh
def diagnosis_reference():
    from service.vqd_reference import set_reference
    return set_reference()



# native-diagnosis-auto-reference-settings-v1
@model_views.route('/diagnosis_reference_settings', methods=['GET', 'POST'])
@jwt_required_with_refresh
def diagnosis_reference_settings():
    from service.vqd_auto_reference import get_settings, write_settings
    from service.vqd_reference import can_set_reference
    if request.method == 'POST':
        if not can_set_reference():
            return jsonify({'code': 403, 'msg': '当前账号没有诊断配置修改权限'}), 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get('auto_reference_enabled')) is not bool:
            return jsonify({'code': 400, 'msg': '自动建立基准开关必须为布尔值'}), 400
        try:
            settings = write_settings(payload['auto_reference_enabled'])
        except (OSError, ValueError):
            return jsonify({'code': 503, 'msg': '自动基准设置保存失败'}), 503
        return jsonify({'code': 200, 'msg': '自动基准设置已保存', 'data': settings})
    try:
        return jsonify({'code': 200, 'data': get_settings()})
    except (OSError, ValueError):
        return jsonify({'code': 503, 'msg': '自动基准设置读取失败'}), 503
