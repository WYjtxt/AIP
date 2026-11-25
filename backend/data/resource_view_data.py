# host-identity-delete-v1
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import func


class ResourceViewData:
    # 算力设备相关数据操作
    @staticmethod
    def get_all_computing_equipment():
        """
        获取所有算力设备信息
        """
        return db.session.query(Computing_equipment).all()

    @staticmethod
    def get_computing_equipment_by_id(id):
        """
        根据ID获取算力设备信息
        """
        return db.session.query(Computing_equipment).filter(Computing_equipment.id == id).first()

    @staticmethod
    def get_computing_equipment_by_ip(computing_ip):
        """
        根据IP获取算力设备信息
        """
        return db.session.query(Computing_equipment).filter(Computing_equipment.computing_ip == computing_ip).first()

    @staticmethod
    def create_computing_equipment(computing_ip, computing_name, computing_code, computing_user, computing_password):
        """
        创建新的算力设备
        """
        new_computing = Computing_equipment(
            computing_ip=computing_ip,
            computing_name=computing_name,
            computing_code=computing_code,
            computing_user=computing_user,
            computing_password=computing_password,
            server_type = 1
        )
        db.session.add(new_computing)
        db.session.commit()
        return new_computing

    @staticmethod
    def update_computing_equipment(id, computing_ip=None, computing_name=None, computing_user=None, computing_password=None):
        """
        更新算力设备信息
        """
        computing_detail = db.session.query(Computing_equipment).filter(Computing_equipment.id == id).first()
        if computing_detail:
            if computing_ip is not None:
                computing_detail.computing_ip = computing_ip
            if computing_name is not None:
                computing_detail.computing_name = computing_name
            if computing_user is not None:
                computing_detail.computing_user = computing_user
            if computing_password is not None:
                computing_detail.computing_password = computing_password
            db.session.commit()
        return computing_detail

    @staticmethod
    def delete_computing_equipment(id):
        from service.computing_identity_service import delete_binding_and_device
        return delete_binding_and_device(id)

    @staticmethod
    def get_computing_equipment_paginated(page, per_page):
        """
        分页获取算力设备信息
        """
        return db.session.query(Computing_equipment).paginate(page=page, per_page=per_page, error_out=False)

    # 资源使用情况相关数据操作
    @staticmethod
    def get_resource_usage_by_computing_id(computing_id):
        """
        根据算力设备ID获取资源使用情况
        """
        return db.session.query(Resource_usage).filter(Resource_usage.computing_id == computing_id).all()

    # 算法配置相关数据操作
    @staticmethod
    def get_algorithm_config_by_resource_id(resource_id):
        """
        根据资源ID获取算法配置
        """
        return db.session.query(Algorithm_config).filter(Algorithm_config.resource_id == resource_id).all()

    @staticmethod
    def get_valid_algorithm_configs():
        """
        获取所有有效的算法配置
        """
        return db.session.query(Algorithm_config) \
            .filter(
            Algorithm_config.Algorithm_library_id.in_(
                db.session.query(Algorithm_library.id)
            ),
            Algorithm_config.Equipment_id.in_(
                db.session.query(Equipment.id)
            ),
            Algorithm_config.status == 1
        ) \
            .all()
