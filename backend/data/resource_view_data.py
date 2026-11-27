# host-identity-delete-v1
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import func, text
from sqlalchemy.exc import DBAPIError


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
        """Read card measurements against the database clock, including legacy rows."""
        from common.platform_host_identity import RESOURCE_SAMPLE_TABLE, TABLE, _missing_table

        fields = ('SELECT r.id,r.dev_ip,r.dev_id,r.board_temp,r.chip_temp,r.dev_get_sn,r.dev_get_target,'
                  'r.mem_used_mem_total,r.memory_usage_rate,r.tpu_util,')
        filters = ' WHERE r.computing_id=:computing_id ORDER BY r.id'
        params = {'computing_id': computing_id}
        try:
            query = fields + ('s.resource_id IS NOT NULL AS identity_sample, '
                'COALESCE(s.sampled_at,r.updated_at) AS sample_token, '
                'TIMESTAMPDIFF(MICROSECOND,COALESCE(s.sampled_at,r.updated_at),CURRENT_TIMESTAMP(6))/1000000.0 AS sample_age '
                'FROM t_resource_usage AS r LEFT JOIN ' + TABLE + ' AS i ON i.computing_id=r.computing_id '
                'LEFT JOIN ' + RESOURCE_SAMPLE_TABLE + ' AS s ON s.host_uid=i.host_uid AND s.resource_id=r.id')
            return [dict(row) for row in db.session.execute(text(query + filters), params).mappings()]
        except DBAPIError as error:
            if not _missing_table(error.orig):
                raise
            db.session.rollback()
        query = fields + ('0 AS identity_sample, r.updated_at AS sample_token, '
            'TIMESTAMPDIFF(MICROSECOND,r.updated_at,CURRENT_TIMESTAMP(6))/1000000.0 AS sample_age '
            'FROM t_resource_usage AS r')
        return [dict(row) for row in db.session.execute(text(query + filters), params).mappings()]

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
