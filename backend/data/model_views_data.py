# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_, desc, update
from datetime import datetime


class ModelViewsData:
    # 设备相关数据操作
    @staticmethod
    def get_equipment_by_vcr_id(vcr_id):
        """
        根据录像机ID获取监控点列表
        """
        return db.session.query(Equipment).filter(
            Equipment.VCR_data_id == vcr_id,
            Equipment.parent_id != None
        ).all()

    @staticmethod
    def get_all_equipment():
        """
        获取所有设备信息
        """
        return db.session.query(Equipment).filter(Equipment.parent_id == None).all()

    @staticmethod
    def get_equipment_status():
        """
        获取设备在线状态信息
        """
        return db.session.query(Equipment.id, Equipment.equipment_ip, Equipment.online, Equipment.duration_time).all()

    @staticmethod
    def update_equipment_duration_time(equipment_id, duration_time):
        """
        更新设备离线持续时间
        """
        update_query = (
            update(Equipment)
            .where(Equipment.id == equipment_id)
            .values(duration_time=duration_time)
        )
        db.session.execute(update_query)
        db.session.commit()

    # 诊断数据相关操作
    @staticmethod
    def get_diagnosis_data(page, per_page, first_vcr_id=None, second_vcr_id=None, diagnosis_type=None, start_time=None, end_time=None):
        """
        获取诊断数据列表（支持分页和筛选）
        """
        filters = []

        if first_vcr_id:
            filters.append(and_(Diagnosis_data.vcr_ip == first_vcr_id))

        if second_vcr_id:
            filters.append(and_(Diagnosis_data.equipment_id == second_vcr_id))

        if diagnosis_type:
            filters.append(Diagnosis_data.diagnosis_type == diagnosis_type)

        if start_time and end_time:
            filters.append(Diagnosis_data.create_time.between(start_time, end_time))

        if len(filters) >= 2:
            query_filter = and_(*filters)
        else:
            query_filter = filters[0] if filters else None

        if query_filter is not None:
            return db.session.query(
                Diagnosis_data.id,
                Diagnosis_data.equipment_id, Diagnosis_data.equipment_ip,
                Diagnosis_data.equipment_name, Diagnosis_data.vcr_ip,
                Diagnosis_data.diagnosis_type, Diagnosis_data.db101, Diagnosis_data.db102,
                Diagnosis_data.db103, Diagnosis_data.db104, Diagnosis_data.db105,
                Diagnosis_data.db106, Diagnosis_data.db107, Diagnosis_data.db108,
                Diagnosis_data.db109, Diagnosis_data.db110, Diagnosis_data.db111,
                Diagnosis_data.db112, Diagnosis_data.db113, Diagnosis_data.db114,
                Diagnosis_data.db115, Diagnosis_data.db116, Diagnosis_data.diagnosis_pic, Diagnosis_data.create_time, Diagnosis_data.diagnosis_time,
                Diagnosis_data.parent_name, Diagnosis_data.diagnosis_reason,
            ).filter(query_filter).paginate(page=page, per_page=per_page, error_out=False)
        else:
            return db.session.query(
                Diagnosis_data.id,
                Diagnosis_data.equipment_id, Diagnosis_data.equipment_ip,
                Diagnosis_data.equipment_name, Diagnosis_data.vcr_ip,
                Diagnosis_data.diagnosis_type, Diagnosis_data.db101, Diagnosis_data.db102,
                Diagnosis_data.db103, Diagnosis_data.db104, Diagnosis_data.db105,
                Diagnosis_data.db106, Diagnosis_data.db107, Diagnosis_data.db108,
                Diagnosis_data.db109, Diagnosis_data.db110, Diagnosis_data.db111,
                Diagnosis_data.db112, Diagnosis_data.db113, Diagnosis_data.db114,
                Diagnosis_data.db115, Diagnosis_data.db116, Diagnosis_data.diagnosis_pic, Diagnosis_data.diagnosis_time, Diagnosis_data.create_time,
                Diagnosis_data.parent_name, Diagnosis_data.diagnosis_reason,
            ).paginate(page=page, per_page=per_page, error_out=False)

    # 离线信息相关操作
    @staticmethod
    def get_last_offline_info(equipment_id):
        """
        获取设备最后一条离线信息
        """
        return db.session.query(Offline_info).filter(
            Offline_info.equipment_id == equipment_id
        ).order_by(desc(Offline_info.id)).first()

    @staticmethod
    def create_offline_info(equipment_id, equipment_ip):
        """
        创建新的离线信息
        """
        new_offline_info = Offline_info(
            equipment_id=equipment_id,
            offline_start_time=datetime.now(),
            status='2',
            create_time=datetime.now(),
            offline_end_time=None,
            equipment_ip=equipment_ip
        )
        db.session.add(new_offline_info)
        db.session.commit()
        return new_offline_info

    @staticmethod
    def update_offline_info(offline_info_id, offline_end_time, offline_keep_time):
        """
        更新离线信息
        """
        update_query = (
            update(Offline_info)
            .where(Offline_info.id == offline_info_id)
            .values(
                offline_end_time=offline_end_time,
                offline_keep_time=offline_keep_time
            )
        )
        db.session.execute(update_query)
        db.session.commit()
