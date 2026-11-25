import bdb
import uuid
from datetime import datetime

from flask import Response, jsonify, Flask, request, Blueprint,url_for,current_app
from config.configs import *
from service.resource_view_service import ResourceViewService

# 创建蓝图，对应的register目录（激活操作视图）
resource_view = Blueprint('resource', __name__)


# 算力资源展示
@resource_view.route('/resource_data', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def resource_data():
    # 调用服务层方法获取算力资源数据
    success, result = ResourceViewService.get_resource_data()
    if success:
        from service.resource_admission import attach
        result = attach(result)
        return jsonify({'code': 200, 'msg': '查询成功', 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# 算力设备新增
@resource_view.route('/computing_insert', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def computing_insert():
    # 获取请求参数
    computing_ip = strip_whitespace(request.form.get('computing_ip', None))
    computing_name = strip_whitespace(request.form.get('computing_name', None))
    computing_user = strip_whitespace(request.form.get('computing_user', None))
    computing_password = strip_whitespace(request.form.get('computing_password', None))

    # 调用服务层方法添加算力设备
    success, message = ResourceViewService.add_computing_equipment(
        computing_ip, computing_name, computing_user, computing_password
    )

    if success:
        # 更新定时任务
        scheduler = current_app.apscheduler
        scheduler.modify_job(id="computing_equipment_task_1", next_run_time=datetime.now())
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 算力设备删除
@resource_view.route('/computing_delete', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def computing_delete():
    # 获取请求参数
    id = strip_whitespace(request.form.get('id', None))

    # 调用服务层方法删除算力设备
    success, message = ResourceViewService.delete_computing_equipment(id)

    if success:
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 算力设备修改
@resource_view.route('/computing_update', methods=['POST'])
# @jwt_required()
@jwt_required_with_refresh
def computing_update():
    # 获取请求参数
    id = strip_whitespace(request.form.get('id', None))
    computing_ip = strip_whitespace(request.form.get('computing_ip', None))
    computing_name = strip_whitespace(request.form.get('computing_name', None))
    computing_user = strip_whitespace(request.form.get('computing_user', None))
    computing_password = strip_whitespace(request.form.get('computing_password', None))

    # 调用服务层方法更新算力设备
    success, message = ResourceViewService.update_computing_equipment(
        id, computing_ip, computing_name, computing_user, computing_password
    )

    if success:
        # 更新定时任务
        scheduler = current_app.apscheduler
        scheduler.modify_job(id="computing_equipment_task_1", next_run_time=datetime.now())
        return jsonify({'code': 200, 'msg': message})
    else:
        return jsonify({'code': 400, 'msg': message})


# 算力设备展示
@resource_view.route('/computing_show', methods=['GET'])
# @jwt_required()
@jwt_required_with_refresh
def computing_show():
    """
    算法模板信息展示（支持分页）
    page（str）： 当前页码
    per_page（str）： 每页显示条目数量
    """

    # 获取分页参数
    page = request.args.get('page', default=1, type=int)  # 当前页码
    per_page = request.args.get('per_page', default=15, type=int)  # 每页显示条目数量

    # 调用服务层方法获取算力设备列表
    success, result = ResourceViewService.get_computing_equipment_paginated(page, per_page)

    if success:
        return jsonify({'code': 200, 'data': result})
    else:
        return jsonify({'code': 400, 'msg': result})


# def computing_equipment_check():
#     try:
#         with current_app.app_context():
#             # 获取设备信息和对应的算法配置
#             computing_info = db.session.query(Computing_equipment).all()
#             if not computing_info:
#                 print('暂无设备信息')
#
#             # 创建多个 SSH 实例，表示要上传的服务器-
#             SSH_list = [SSH_Func(i.computing_ip, i.computing_user, i.computing_password) for i in computing_info]
#             for i in SSH_list:
#                     # 上传文件到服务器
#                     ssh,status = i.connect_ssh()
#                     if status == 1:
#                         # 更新数据库
#                         db.session.query(Computing_equipment).filter(Computing_equipment.computing_ip == i.ssh_host).update(
#                             {'computing_status': status})
#                         db.session.commit()
#                         print(f"{i.ssh_host}算力设备状态为{status}")
#                         if ssh:
#                             ssh.close()
#                     else:
#                         db.session.query(Computing_equipment).filter(Computing_equipment.computing_ip == i.ssh_host).update(
#                             {'computing_status': status})
#                         db.session.commit()
#                     print(f"{i.ssh_host}算力设备状态为{status}")
#     except Exception as e:
#         # 捕获其他所有类型的异常
#         print(f"发生错误：{str(e)}")

@resource_view.route('/admission', methods=['GET'])
@jwt_required_with_refresh
def resource_admission_snapshot():
    from service.resource_admission import snapshot
    try:
        return jsonify({'code': 200, 'data': snapshot()})
    except Exception:
        return jsonify({'code': 503, 'msg': '资源状态暂不可用，暂停新增部署'})


@resource_view.route('/algorithm_metadata', methods=['POST'])
@jwt_required_with_refresh
def algorithm_metadata_save():
    from service.resource_admission import save_metadata
    try:
        return jsonify(save_metadata(request.json or {}))
    except Exception:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '名称与备注保存失败，请稍后重试'})


@resource_view.route('/admission/settings', methods=['GET', 'POST'])
@jwt_required_with_refresh
def resource_admission_settings():
    from service.resource_admission_settings_api import settings_response
    return settings_response()
