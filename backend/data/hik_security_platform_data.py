from data.exts import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy.exc import IntegrityError

class HikSecurityPlatformData:
    """海康安防平台数据层，处理数据库操作"""
    
    @staticmethod
    def get_hik_security_platform_info(id):
        """获取海康安防平台信息"""
        try:
            hik_info = db.session.query(Hik_security_platform_info).filter_by(id=id).first()
            return hik_info
        except Exception as e:
            print(f"获取海康安防平台信息失败: {e}")
            return None
    
    @staticmethod
    def get_all_hik_security_platform_infos():
        try:
            return db.session.query(Hik_security_platform_info).all()
        except Exception as e:
            print(f"获取海康安防平台信息列表失败: {e}")
            return []
    
    @staticmethod
    def get_hik_security_platform_info_by_app_key(app_key, app_secret):
        """根据 app_key 和 app_secret 获取海康安防平台信息"""
        try:
            hik_info = db.session.query(Hik_security_platform_info).filter_by(
                hik_appKey=app_key, hik_appSecret=app_secret
            ).first()
            return hik_info
        except Exception as e:
            print(f"根据 app_key 和 app_secret 获取海康安防平台信息失败: {e}")
            return None
    
    @staticmethod
    def create_hik_security_platform_info(hik_name, hik_host, hik_port, hik_appKey, hik_appSecret, Mine_id):
        """创建海康安防平台信息"""
        try:
            hik_info_data = Hik_security_platform_info(
                hik_name=hik_name,
                hik_host=hik_host,
                hik_port=hik_port,
                hik_appKey=hik_appKey,
                hik_appSecret=hik_appSecret,
                Mine_id=Mine_id,
            )
            db.session.add(hik_info_data)
            db.session.flush()
            db.session.refresh(hik_info_data)
            return hik_info_data
        except Exception as e:
            db.session.rollback()
            print(f"创建海康安防平台信息失败: {e}")
            return None
    
    @staticmethod
    def get_hik_security_platform_up_area(indexCode, name):
        """获取海康安防平台区域信息"""
        try:
            area = db.session.query(Hik_security_platform_up_area).filter_by(
                indexCode=indexCode, name=name
            ).first()
            return area
        except Exception as e:
            print(f"获取海康安防平台区域信息失败: {e}")
            return None
    
    @staticmethod
    def get_area_by_index_code(indexCode):
        try:
            return db.session.query(Hik_security_platform_up_area).filter_by(indexCode=indexCode).first()
        except Exception as e:
            print(f"根据indexCode获取区域失败: {e}")
            return None
    
    @staticmethod
    def create_hik_security_platform_up_area(indexCode, name, hik_info_id, Mine_id):
        """创建海康安防平台区域信息"""
        try:
            area_record = Hik_security_platform_up_area(
                indexCode=indexCode,
                name=name,
                hik_info_id=hik_info_id,
                Mine_id=Mine_id,
            )
            db.session.add(area_record)
            db.session.flush()
            db.session.refresh(area_record)
            return area_record
        except Exception as e:
            db.session.rollback()
            print(f"创建海康安防平台区域信息失败: {e}")
            return None
    
    @staticmethod
    def update_area_by_index_code(indexCode, name, hik_info_id):
        try:
            area = db.session.query(Hik_security_platform_up_area).filter_by(indexCode=indexCode).first()
            if not area:
                return None
            area.name = name
            area.hik_info_id = hik_info_id
            db.session.commit()
            return area
        except Exception as e:
            db.session.rollback()
            print(f"更新区域失败: {e}")
            return None
    
    @staticmethod
    def create_equipment(equipment_type, manufacturer_type, equipment_name, Mine_id, Hik_id=None, Hik_indexCode=None, Hik_rtsp_url=None, parent_id=None,GB28181_code= None):
        """创建设备信息"""
        try:
            eq_record = Equipment(
                equipment_type=equipment_type,
                manufacturer_type=manufacturer_type,
                equipment_name=equipment_name,
                Mine_id=Mine_id,
                Hik_id=Hik_id,
                Hik_indexCode=Hik_indexCode,
                Hik_rtsp_url=Hik_rtsp_url,
                parent_id=parent_id,
                GB28181_code=GB28181_code
            )
            db.session.add(eq_record)
            db.session.flush()
            db.session.refresh(eq_record)
            return eq_record
        except IntegrityError as e:
            db.session.rollback()
            print(f"创建设备信息失败: {e}")
            return None
        except Exception as e:
            db.session.rollback()
            print(f"创建设备信息失败: {e}")
            return None
    
    @staticmethod
    def delete_hik_security_platform_info(id):
        """Delete a registration and its unused synchronized resources atomically."""
        import json
        from model.ai_camera import Algorithm_config_3588
        from service.algorithm_first_backend import equipment_locks, WorkflowError
        from service.scheduler_task_service import SchedulerTaskService

        session = db.session

        def select_catalog(lock=False):
            areas = session.query(Hik_security_platform_up_area.id).filter_by(hik_info_id=id)
            area_ids = [row.id for row in (areas.with_for_update() if lock else areas).all()]
            if not area_ids:
                return []
            devices = session.query(Equipment.id, Equipment.equipment_type, Equipment.manufacturer_type,
                                    Equipment.zlk_dat_id).filter(Equipment.Hik_id.in_(area_ids)).order_by(Equipment.id)
            return (devices.with_for_update() if lock else devices).all()

        try:
            device_ids = [row.id for row in select_catalog()]
            session.rollback()
            with equipment_locks(db, device_ids):
                platform = session.query(Hik_security_platform_info).filter_by(id=id).with_for_update().first()
                if platform is None:
                    session.rollback()
                    return False, '安防平台不存在或已删除'
                devices = select_catalog(lock=True)
                if [row.id for row in devices] != device_ids:
                    session.rollback()
                    return False, '平台正在同步资源，请刷新后重试'
                if device_ids:
                    if any(row.equipment_type != '安防平台' or row.manufacturer_type != '海康' for row in devices):
                        session.rollback()
                        return False, '平台区域仍被其他来源的设备引用，请先核对设备归属'
                    for model in (Algorithm_config, Algorithm_config_3588):
                        if session.query(model.id).filter(model.Equipment_id.in_(device_ids)).with_for_update().first():
                            session.rollback()
                            return False, '平台监控点已配置算法任务，请先移除对应任务后再删除平台'
                    if session.query(Equipment.id).filter(Equipment.parent_id.in_(device_ids),
                                                         ~Equipment.id.in_(device_ids)).with_for_update().first():
                        session.rollback()
                        return False, '平台区域仍被其他来源的设备引用，请先核对设备归属'
                    if any(row.zlk_dat_id is not None for row in devices):
                        session.rollback()
                        return False, '平台监控点仍有关联的流媒体转发，请先在流媒体管理中关闭对应转发'
                    owned_ids = {str(value) for value in device_ids}
                    for plan in session.query(ScheduledTask.rtsp_list).all():
                        try:
                            valid, sources = SchedulerTaskService.flatten_equipment_data(json.loads(plan.rtsp_list))
                        except (TypeError, ValueError):
                            continue
                        if valid and any(str(source['id']) in owned_ids for source in sources):
                            session.rollback()
                            return False, '平台监控点已配置视频质量诊断，请先移除诊断计划中的对应监控点'
                    session.query(Equipment).filter(Equipment.id.in_(device_ids)).delete(synchronize_session=False)
                session.query(Hik_security_platform_up_area).filter_by(hik_info_id=id).delete(synchronize_session=False)
                session.delete(platform)
                session.commit()
                return True, '删除成功'
        except WorkflowError as error:
            session.rollback()
            return False, str(error)
        except Exception as error:
            session.rollback()
            print('删除海康安防平台失败: {}'.format(type(error).__name__))
            return False, '删除安防平台失败，请稍后重试'
    
    @staticmethod
    def get_hik_security_platform_list(page, per_page):
        """获取海康安防平台列表，支持分页"""
        try:
            pagination = db.session.query(Hik_security_platform_info).paginate(
                page=page, per_page=per_page, error_out=False
            )
            return pagination
        except Exception as e:
            print(f"获取海康安防平台列表失败: {e}")
            return None
    
    @staticmethod
    def get_hik_security_platform_up_areas(hik_info_id):
        """获取海康安防平台区域列表"""
        try:
            areas = db.session.query(Hik_security_platform_up_area).filter(
                Hik_security_platform_up_area.hik_info_id == hik_info_id
            ).all()
            return areas
        except Exception as e:
            print(f"获取海康安防平台区域列表失败: {e}")
            return []
    
    @staticmethod
    def get_hik_security_platform_up_area_by_id(id):
        """根据 ID 获取海康安防平台区域信息"""
        try:
            area = db.session.query(Hik_security_platform_up_area).filter_by(id=id).first()
            return area
        except Exception as e:
            print(f"根据 ID 获取海康安防平台区域信息失败: {e}")
            return None
    
    @staticmethod
    def get_equipment_by_hik_id_and_parent_id(hik_id, parent_id):
        """根据 Hik_id 和 parent_id 获取设备信息"""
        try:
            query = db.session.query(Equipment).filter(Equipment.Hik_id == hik_id)
            if parent_id is not None:
                query = query.filter(Equipment.parent_id == parent_id)
            else:
                query = query.filter(Equipment.parent_id == None)
            return query.all()
        except Exception as e:
            print(f"获取设备信息失败: {e}")
            return []
    
    @staticmethod
    def get_equipment_by_hik_id(hik_id, parent_id=None, page=None, per_page=None):
        """根据 Hik_id 获取设备信息，支持分页"""
        try:
            query = db.session.query(Equipment).filter(Equipment.Hik_id == hik_id)
            if parent_id is not None:
                query = query.filter(Equipment.parent_id == parent_id)
            else:
                query = query.filter(Equipment.parent_id != None)
            
            if page and per_page:
                pagination = query.paginate(page=page, per_page=per_page, error_out=False)
                return pagination
            else:
                return query.all()
        except Exception as e:
            print(f"获取设备信息失败: {e}")
            return None

    @staticmethod
    def get_parent_equipment_by_index_code(indexCode):
        try:
            return db.session.query(Equipment).filter(
                Equipment.Hik_indexCode == indexCode,
                Equipment.parent_id == None
            ).first()
        except Exception as e:
            print(f"获取父设备失败: {e}")
            return None

    @staticmethod
    def find_equipment_by_hik_index_code(indexCode):
        try:
            return db.session.query(Equipment).filter_by(Hik_indexCode=indexCode).first()
        except Exception as e:
            print(f"查询设备失败: {e}")
            return None

    @staticmethod
    def update_equipment_fields(equipment_id, updates):
        try:
            db.session.query(Equipment).filter(Equipment.id == equipment_id).update(updates)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"更新设备失败: {e}")
            return False

    @staticmethod
    def delete_children_not_in_index_codes(hik_area_id, external_index_codes):
        try:
            deleted_count = db.session.query(Equipment).filter(
                Equipment.equipment_type == '安防平台',
                Equipment.parent_id != None,
                Equipment.Hik_id == hik_area_id,
                ~Equipment.Hik_indexCode.in_(external_index_codes)
            ).delete(synchronize_session=False)
            db.session.commit()
            return deleted_count
        except Exception as e:
            db.session.rollback()
            print(f"删除不在外部列表中的子设备失败: {e}")
            return 0
