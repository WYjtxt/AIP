from config.configs import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from config import configs
from sqlalchemy.exc import IntegrityError

class ZiguangVMSData:
    def check_ziguang_exists(self, ziguang_host):
        return db.session.query(Ziguanhhuazhi_data).filter(Ziguanhhuazhi_data.ziguang_ip == ziguang_host).first() is not None

    def check_ziguang_exists_by_id(self, id):
        return db.session.query(Ziguanhhuazhi_data).filter_by(id=id).first() is not None

    def create_ziguang_data(self, org_name, ziguang_host, ziguang_id, ziguang_password, ziguang_port, Mine_id):
        ziguang_data = Ziguanhhuazhi_data(
            ziguang_name=org_name,
            ziguang_ip=ziguang_host,
            ziguang_id=ziguang_id,
            ziguang_password=ziguang_password,
            ziguang_port=ziguang_port,
            Mine_id=Mine_id,
            ziguang_status=1,
        )
        db.session.add(ziguang_data)
        db.session.flush()
        return ziguang_data

    def create_parent_equipment(self, org_name, ziguang_host, Mine_id, ziguang_data_id):
        equipment_data = Equipment(
            equipment_type="紫光华智",
            manufacturer_type="紫光华智",
            equipment_name=org_name,
            equipment_ip=ziguang_host,
            Mine_id=int(Mine_id) if Mine_id else None,
            online=1,
            Ziguang_id=ziguang_data_id,
        )
        db.session.add(equipment_data)
        db.session.flush()
        return equipment_data

    def bulk_create_equipment(self, equipment_list):
        equipment_objects = [
            Equipment(**eq) for eq in equipment_list
        ]
        db.session.bulk_save_objects(equipment_objects)
        db.session.commit()

    def delete_ziguang_platform(self, id):
        db.session.query(Equipment).filter_by(Ziguang_id=id).delete()
        ziguang_info = db.session.query(Ziguanhhuazhi_data).filter_by(id=id).first()
        db.session.delete(ziguang_info)
        db.session.commit()

    def get_all_ziguang_data(self, page, per_page):
        query = db.session.query(Ziguanhhuazhi_data)
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        res = configs.convert_folder_to_dict_list(paginated.items,
                                          ['id', 'ziguang_name', 'ziguang_ip', 'ziguang_id',
                                           'ziguang_password', 'ziguang_port', 'ziguang_status',
                                           'Mine_id', 'create_time'])
        return res, paginated.total, paginated.page, paginated.pages

    def get_ziguang_data_by_id(self, id):
        res = configs.convert_to_dict(db.session.query(Ziguanhhuazhi_data).filter(Ziguanhhuazhi_data.id == id).first(),
                              ['id', 'ziguang_name', 'ziguang_ip', 'ziguang_id','ziguang_password',
                               'ziguang_port', 'ziguang_status','Mine_id', 'create_time'])
        return res

    def get_children_equipment(self, id, page, per_page):
        query = db.session.query(Equipment).filter(
            Equipment.Ziguang_id == id, Equipment.parent_id != None
        )
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        res_children_list = configs.convert_folder_to_dict_list(paginated.items,
                                                        ['id', 'equipment_type', 'manufacturer_type', 'equipment_name',
                                                         'equipment_ip', 'Ziguang_ape_indexCode', 'Ziguang_ape_rtsp_url',
                                                         'create_time', 'online'])
        return res_children_list, paginated.total, paginated.page, paginated.pages

    def get_all_platforms(self):
        return db.session.query(Ziguanhhuazhi_data).all()

    def get_parent_equipment(self, platform_id):
        return db.session.query(Equipment).filter_by(Ziguang_id=platform_id, parent_id=None).first()

    def get_children_devices(self, platform_id, parent_id):
        return db.session.query(Equipment).filter_by(Ziguang_id=platform_id, parent_id=parent_id).all()

    def delete_children_not_in_ape_ids(self, platform_id, parent_id, ape_ids):
        try:
            # 当前数据库中的子设备列表
            db_devices = db.session.query(Equipment).filter_by(
                Ziguang_id=platform_id, parent_id=parent_id
            ).all()
            db_ape_ids = set([dev.Ziguang_ape_indexCode for dev in db_devices if dev.Ziguang_ape_indexCode])

            # 找出多余的设备（紫光平台中已删除）
            obsolete_devices = [dev for dev in db_devices if dev.Ziguang_ape_indexCode not in ape_ids]

            for dev in obsolete_devices:
                db.session.delete(dev)
                print(f"[删除] 数据库中多余设备：{dev.equipment_name} ({dev.Ziguang_ape_indexCode})")
            # deleted = db.session.query(Equipment).filter(
            #     Equipment.Ziguang_id == platform_id,
            #     Equipment.parent_id == parent_id,
            #     ~Equipment.Ziguang_ape_indexCode.in_(ape_ids)
            # ).delete(synchronize_session=False)
            # db.session.commit()
            # return deleted
        except Exception as e:
            db.session.rollback()
            print(f"删除紫光多余设备失败: {e}")
            return 0

    def find_device_by_ape_index(self, platform_id, parent_id, ape_id):
        return db.session.query(Equipment).filter_by(
            Ziguang_ape_indexCode=ape_id, Ziguang_id=platform_id, parent_id=parent_id
        ).first()

    def update_equipment_fields(self, equipment_id, updates):
        try:
            db.session.query(Equipment).filter(Equipment.id == equipment_id).update(updates)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"更新紫光设备失败: {e}")
            return False
