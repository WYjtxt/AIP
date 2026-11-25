# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_, func
from sqlalchemy.exc import SQLAlchemyError
from service.diagnosis_scheduler import normalize_status


class SchedulerTaskData:
    # 定时任务相关数据操作
    @staticmethod
    def create_task(name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status):
        """
        创建新的定时任务
        """
        new_task = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            time_type=time_type,
            rtsp_list=rtsp_list,
            diagnosis_type_list=diagnosis_type_list,
            scheduled_concent=scheduled_concent,
            scheduled_status=normalize_status(scheduled_status),
            next_run_time=datetime.now() if normalize_status(scheduled_status) else None,
            create_time=datetime.now()
        )
        db.session.add(new_task)
        db.session.commit()
        return new_task

    @staticmethod
    def get_task_by_id(task_id):
        """
        根据ID获取定时任务
        """
        return db.session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()

    @staticmethod
    def get_all_tasks(page=1, per_page=15, name=None, time_type=None, scheduled_status=None):
        """
        获取定时任务列表（支持分页和筛选）
        """
        filters = []
        if name:
            filters.append(ScheduledTask.name.ilike(f"%{name}%"))
        if time_type:
            filters.append(ScheduledTask.time_type == time_type)
        if scheduled_status:
            filters.append(ScheduledTask.scheduled_status == int(scheduled_status))

        query = db.session.query(ScheduledTask)
        if filters:
            query = query.filter(and_(*filters))

        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def update_task(task_id, name, interval_seconds, time_type, rtsp_list, diagnosis_type_list, scheduled_concent, scheduled_status):
        """
        更新定时任务
        """
        task = db.session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if task:
            status = normalize_status(scheduled_status)
            schedule_changed = (
                int(task.interval_seconds) != int(interval_seconds) or task.time_type != time_type or
                task.rtsp_list != rtsp_list or task.diagnosis_type_list != diagnosis_type_list)
            was_enabled = task.scheduled_status == 1
            task.name = name
            task.interval_seconds = interval_seconds
            task.time_type = time_type
            task.rtsp_list = rtsp_list
            task.diagnosis_type_list = diagnosis_type_list
            task.scheduled_concent = scheduled_concent
            task.scheduled_status = status
            if not status:
                task.next_run_time = None
            elif not was_enabled or schedule_changed:
                task.next_run_time = datetime.now()
            db.session.commit()
        return task

    @staticmethod
    def delete_task(task_id):
        """
        删除定时任务
        """
        task = db.session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if task:
            db.session.delete(task)
            db.session.commit()
        return task

    # 诊断数据相关数据操作
    @staticmethod
    def move_diagnosis_data_to_history():
        """
        将现有诊断数据移动到历史表
        """
        try:
            existing_data = db.session.query(Diagnosis_data).all()
            if existing_data:
                # 创建要插入到历史表中的数据列表
                history_entries = [
                    Diagnosis_data_old(
                        equipment_id=entry.equipment_id,
                        equipment_ip=entry.equipment_ip,
                        equipment_name=entry.equipment_name,
                        vcr_ip=entry.vcr_ip,
                        diagnosis_type=entry.diagnosis_type,
                        db101=entry.db101, db102=entry.db102, db103=entry.db103,
                        db104=entry.db104, db105=entry.db105, db106=entry.db106,
                        db107=entry.db107, db108=entry.db108, db109=entry.db109,
                        db110=entry.db110, db111=entry.db111, db112=entry.db112,
                        db113=entry.db113, db114=entry.db114, db115=entry.db115,
                        db116=entry.db116, diagnosis_pic=entry.diagnosis_pic,
                        diagnosis_reason=entry.diagnosis_reason,
                        parent_name=entry.parent_name,
                        create_time=entry.create_time
                    )
                    for entry in existing_data
                ]
                # 批量保存到历史表
                db.session.bulk_save_objects(history_entries)
            return True
        except SQLAlchemyError as e:
            print(f'移动诊断数据到历史表失败: {str(e)}')
            return False

    @staticmethod
    def clear_diagnosis_data():
        """
        清空诊断数据表
        """
        try:
            db.session.query(Diagnosis_data).delete()
            return True
        except SQLAlchemyError as e:
            print(f'清空诊断数据表失败: {str(e)}')
            return False

    @staticmethod
    def add_diagnosis_data(data):
        """
        添加诊断数据
        """
        try:
            # 准备批量插入的新诊断数据
            new_entries = [
                Diagnosis_data(
                    equipment_id=i[0], equipment_ip=i[1], equipment_name=i[2], vcr_ip=i[3],
                    diagnosis_type=i[4], db101=i[5], db102=i[6], db103=i[7],
                    db104=i[8], db105=i[9], db106=i[10], db107=i[11],
                    db108=i[12], db109=i[13], db110=i[14], db111=i[15],
                    db112=i[16], db113=i[17], db114=i[18], db115=i[19],
                    db116=i[20], diagnosis_pic=i[21],
                    parent_name=i[22],
                    diagnosis_reason=i[23] if len(i) > 23 else None,
                    create_time=datetime.now()
                )
                for i in data
            ]
            # 批量插入新的诊断数据
            db.session.bulk_save_objects(new_entries)
            return True
        except SQLAlchemyError as e:
            print(f'添加诊断数据失败: {str(e)}')
            return False

    @staticmethod
    def perform_diagnostic_task(data):
        """
        执行诊断任务数据处理
        """
        try:
            if not data:
                return False, '没有可写入的诊断结果'
            with db.session.begin_nested():
                if not SchedulerTaskData.move_diagnosis_data_to_history():
                    raise ValueError('诊断历史归档失败')
                if not SchedulerTaskData.clear_diagnosis_data():
                    raise ValueError('诊断结果清理失败')
                if not SchedulerTaskData.add_diagnosis_data(data):
                    raise ValueError('诊断结果写入失败')
            db.session.commit()
            return True, '诊断数据上传完成！'
        except Exception:
            db.session.rollback()
            return False, '诊断结果未保存，已回滚本次写入'

    @staticmethod
    def get_independent_cameras():
        return db.session.query(Equipment).filter(
            Equipment.equipment_type == '摄像头',
            Equipment.parent_id == None
        ).all()

    @staticmethod
    def set_cameras_online_status(status_by_id):
        try:
            if not status_by_id:
                return True
            for equipment_id, online_status in status_by_id.items():
                db.session.query(Equipment).filter(Equipment.id == equipment_id).update({'online': online_status})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def get_vcr_list_by_type(vcr_type):
        return db.session.query(VCR_data).filter(VCR_data.type == vcr_type).all()

    @staticmethod
    def set_vcr_online(vcr_id, online):
        try:
            db.session.query(VCR_data).filter(VCR_data.id == vcr_id).update({VCR_data.online: online})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def get_equipments_by_vcr(vcr_id):
        return db.session.query(Equipment).filter(Equipment.VCR_data_id == vcr_id).all()

    @staticmethod
    def set_equipments_online_by_vcr_parent(vcr_id, online):
        try:
            db.session.query(Equipment).filter(
                Equipment.VCR_data_id == vcr_id,
                Equipment.parent_id == None
            ).update({Equipment.online: online})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def get_parent_equipment_by_vcr(vcr_id):
        return db.session.query(Equipment).filter(
            Equipment.VCR_data_id == vcr_id,
            Equipment.parent_id == None
        ).first()

    @staticmethod
    def get_child_equipments_by_vcr(vcr_id):
        return db.session.query(Equipment).filter(
            Equipment.VCR_data_id == vcr_id,
            Equipment.parent_id != None
        ).all()

    @staticmethod
    def update_equipment_fields(equipment_id, updates):
        try:
            db.session.query(Equipment).filter(Equipment.id == equipment_id).update(updates)
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def delete_equipment_by_id(equipment_id):
        try:
            eq = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if eq:
                db.session.delete(eq)
                db.session.commit()
                return True
            return False
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def add_equipment(data):
        try:
            new_device = Equipment(**data)
            db.session.add(new_device)
            db.session.commit()
            return new_device
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def find_equipment_by_ip(ip_address):
        return db.session.query(Equipment).filter(Equipment.equipment_ip == ip_address).first()

    @staticmethod
    def find_equipment_by_name(name):
        return db.session.query(Equipment).filter(Equipment.equipment_name == name).first()

    @staticmethod
    def get_active_algorithm_configs_with_equipment():
        return db.session.query(
            Equipment.id, Equipment.equipment_ip, Algorithm_config.id, Algorithm_config.status
        ).join(Algorithm_config, Algorithm_config.Equipment_id == Equipment.id).filter(Algorithm_config.status == 1).all()

    @staticmethod
    def update_algorithm_model_status(config_id, status):
        try:
            db.session.query(Algorithm_config).filter(Algorithm_config.id == config_id).update({'model_status': status})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def get_all_algorithm_configs():
        return db.session.query(Algorithm_config).all()

    @staticmethod
    def update_algorithm_status(config_id, status_value):
        try:
            db.session.query(Algorithm_config).filter(Algorithm_config.id == config_id).update({'status': status_value})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def delete_logs_before(cutoff_datetime):
        from service.log_retention_service import cleanup_database_logs
        return cleanup_database_logs(cutoff_datetime)['ok']

    @staticmethod
    def get_algorithm_delete_ids():
        return [i.algorithm_id for i in db.session.query(Algorithm_result_delete.algorithm_id).all()]

    @staticmethod
    def delete_algorithm_results_by_library_ids(ids):
        try:
            from service.alarm_retention_service import queue_and_delete_alarm_records
            alarm_ids = [row.id for row in db.session.query(Algorithm_result.id).filter(
                Algorithm_result.Algorithm_library_id.in_(ids)).all()]
            return queue_and_delete_alarm_records(alarm_ids)
        except SQLAlchemyError:
            db.session.rollback()
            return 0

    @staticmethod
    def get_all_algorithm_config_ids():
        return [i.id for i in db.session.query(Algorithm_config.id).all()]

    @staticmethod
    def delete_results_where_config_id_not_in(valid_config_ids):
        try:
            from service.alarm_retention_service import queue_and_delete_alarm_records
            alarm_ids = [row.id for row in db.session.query(Algorithm_result.id).filter(
                ~Algorithm_result.Algorithm_config_id.in_(valid_config_ids)).all()]
            return queue_and_delete_alarm_records(alarm_ids)
        except SQLAlchemyError:
            db.session.rollback()
            return 0

    @staticmethod
    def get_active_activations():
        return db.session.query(Activate_info).filter(Activate_info.activate_status == 1).all()

    @staticmethod
    def set_all_algorithm_configs_status(status_value):
        try:
            db.session.query(Algorithm_config).update({"status": status_value})
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def list_all_scheduled_tasks():
        return db.session.query(ScheduledTask).all()
