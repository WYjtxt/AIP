from model.equipment import Equipment
from model.extra import Zlk_data
from sqlalchemy.exc import SQLAlchemyError
from data.exts import db
import bdb
import datetime
import os
import ast
import dbutils.steady_db
from flask import jsonify, request, Blueprint, make_response
import config.configs as configs
from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_, func, update, select, text, cast, Integer,or_
import yaml
import io
import zipfile
from datetime import datetime, timedelta
import cv2
from urllib.parse import urlparse, quote
import time
# 在model_view.py中添加导入
import json
import random
import string
import asyncio
from sqlalchemy.exc import SQLAlchemyError


class EquipmentData:
    """设备数据操作类"""
    
    # @staticmethod
    # def check_equipment_exists(equipment_ip):
    #     """
    #     检查设备是否已存在
    #     :param equipment_ip: 设备IP地址
    #     :return: 设备对象，如果不存在返回None
    #     """
    #     try:
    #         return db.session.query(Equipment).filter(Equipment.equipment_ip == equipment_ip).first()
    #     except SQLAlchemyError as e:
    #         print(f"检查设备存在性时出错: {str(e)}")
    #         db.session.rollback()
    #         return None

    @staticmethod
    def get_equipment_detail(equipment_id):
        """
        获取设备详情
        :param equipment_id: 设备ID
        :return: 设备对象
        """
        try:
            return db.session.query(
                Equipment.id, Equipment.equipment_type, Equipment.Mine_id,
                Equipment.manufacturer_type, Equipment.equipment_name,
                Equipment.equipment_ip, Equipment.equipment_uname,
                Equipment.equipment_password, Equipment.equipment_aisles,
                Equipment.equipment_codetype, Equipment.user_status,
                Equipment.create_time, Equipment.parent_id, Equipment.code, Equipment.flower_frames,
                Equipment.uwb_ip, Equipment.alarm_device_ip
            ).filter(Equipment.id == equipment_id).first()
        except SQLAlchemyError as e:
            print(f"获取设备详情时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def update_equipment(equipment_id, equipment_data):
        """
        更新设备信息
        :param equipment_id: 设备ID
        :param equipment_data: 设备数据
        :return: 设备对象
        """
        try:
            equipment = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not equipment:
                return None

            # 更新设备信息
            for key, value in equipment_data.items():
                if hasattr(equipment, key):
                    setattr(equipment, key, value)

            db.session.commit()
            return equipment
        except SQLAlchemyError as e:
            print(f"更新设备信息时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def update_vcr_data(vcr_id, vcr_data):
        """
        更新VCR数据
        :param vcr_id: VCR ID
        :param vcr_data: VCR数据
        :return: 是否成功
        """
        try:
            from sqlalchemy import update
            from model.equipment import VCR_data

            update_query = update(VCR_data).where(VCR_data.id == vcr_id).values(vcr_data)
            db.session.execute(update_query)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新VCR数据时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_children_equipment(vcr_id, equipment_data):
        """
        更新子设备信息
        :param vcr_id: VCR ID
        :param equipment_data: 设备数据
        :return: 是否成功
        """
        try:
            from sqlalchemy import update

            update_query = update(Equipment).where(
                Equipment.VCR_data_id == vcr_id, Equipment.parent_id != None
            ).values(equipment_data)
            db.session.execute(update_query)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新子设备信息时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_children_equipment_by_parent(parent_id, equipment_data):
        """
        根据父ID更新子设备信息
        :param parent_id: 父设备ID
        :param equipment_data: 设备数据
        :return: 是否成功
        """
        try:
            from sqlalchemy import update, or_

            update_query = update(Equipment).where(
                or_(
                    Equipment.id == parent_id,
                    Equipment.parent_id == parent_id
                )
            ).values(equipment_data)
            db.session.execute(update_query)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"根据父ID更新子设备信息时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def equipment_create_data(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname,
                              equipment_password, equipment_aisles, equipment_codetype, Mine_id, flower_frames,
                              parent_id=None, code=None, uwb_ip=None,alarm_device_ip=None):
        """data层：创建设备数据库记录"""
        equipment_data = Equipment(
            equipment_type=equipment_type if equipment_type in ['摄像头', '录像机', '特殊摄像头', '安防平台', '浙江双视热成像','AI单光摄像头','AI双光摄像头'] else None,
            manufacturer_type=manufacturer_type if manufacturer_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星', '浙江双视',
                                                                         '紫光华智', '艾斯卡普','阳光三极'] else None,
            equipment_name=equipment_name if equipment_name else None,
            equipment_ip=equipment_ip if equipment_ip is not None else None,
            equipment_uname=equipment_uname if equipment_uname else None,
            equipment_password=equipment_password if equipment_password else None,
            equipment_aisles=equipment_aisles if equipment_aisles else None,
            equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
            Mine_id=int(Mine_id) if Mine_id else None,
            flower_frames=flower_frames if flower_frames else None,
            parent_id=parent_id if parent_id else None,
            code=code if code else None,
            uwb_ip=uwb_ip if uwb_ip else None,
            alarm_device_ip = alarm_device_ip if alarm_device_ip else None
        )
        db.session.add(equipment_data)
        db.session.commit()
        return equipment_data

    @staticmethod
    def check_equipment_exists(equipment_ip):
        """data层：检查设备是否已存在"""
        return db.session.query(Equipment).filter(Equipment.equipment_ip == equipment_ip).first()

    @staticmethod
    def update_equipment_zlk_id(equipment_id, zlk_dat_id):
        """
        更新设备的ZLK数据ID
        :param equipment_id: 设备ID
        :param zlk_dat_id: ZLK数据ID
        :return: 是否更新成功
        """
        try:
            equipment = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if equipment:
                equipment.zlk_dat_id = zlk_dat_id
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新设备ZLK ID时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_equipment_parent_id(equipment_id):
        """
        获取设备的父ID
        :param equipment_id: 设备ID
        :return: 父ID，如果不存在返回None
        """
        try:
            return db.session.query(Equipment.parent_id).filter(Equipment.id == equipment_id).scalar()
        except SQLAlchemyError as e:
            print(f"获取设备父ID时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_matching_children_parent_ids(equipment_name):
        """
        获取匹配设备名称的子设备的父ID
        :param equipment_name: 设备名称
        :return: 父ID列表
        """
        try:
            matching_children = db.session.query(Equipment.parent_id).filter(
                Equipment.parent_id != None,
                Equipment.equipment_name.like(f"%{equipment_name}%")
            ).distinct().all()
            return [child.parent_id for child in matching_children if child.parent_id is not None]
        except SQLAlchemyError as e:
            print(f"获取匹配子设备父ID时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def get_zlk_data(equipment_id):
        """
        获取设备的ZLK数据
        :param equipment_id: 设备ID
        :return: ZLK数据对象
        """
        try:
            return db.session.query(Zlk_data).filter(Zlk_data.equipment_id == equipment_id).first()
        except SQLAlchemyError as e:
            print(f"获取ZLK数据时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_equipment_by_id(equipment_id):
        """
        根据ID获取设备
        :param equipment_id: 设备ID
        :return: 设备对象
        """
        try:
            return db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
        except SQLAlchemyError as e:
            print(f"根据ID获取设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_children_by_parent_id(parent_id):
        """
        根据父ID获取子设备列表
        :param parent_id: 父设备ID
        :return: 子设备列表
        """
        try:
            return db.session.query(Equipment).filter(Equipment.parent_id == parent_id).all()
        except SQLAlchemyError as e:
            print(f"获取子设备列表时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def get_all_equipment_status():
        """
        获取所有设备的状态信息
        :return: 设备状态列表
        """
        try:
            return db.session.query(Equipment.id, Equipment.equipment_ip, Equipment.online).all()
        except SQLAlchemyError as e:
            print(f"获取设备状态时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def update_equipment_online_status(equipment_ip, online):
        """
        更新设备在线状态
        :param equipment_ip: 设备IP
        :param online: 在线状态
        :return: 是否更新成功
        """
        try:
            equipment = db.session.query(Equipment).filter(Equipment.equipment_ip == equipment_ip).first()
            if equipment:
                equipment.online = online
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新设备在线状态时出错: {str(e)}")
            db.session.rollback()
            return False



    @staticmethod
    def delete_zlk_data(equipment_ids):
        """
        删除设备的流媒体数据
        :param equipment_ids: 设备ID列表
        :return: 删除的记录数
        """
        try:
            deleted = db.session.query(Zlk_data).filter(Zlk_data.equipment_id.in_(equipment_ids)).delete(
                synchronize_session=False)
            db.session.commit()
            return deleted
        except SQLAlchemyError as e:
            print(f"删除流媒体数据时出错: {str(e)}")
            db.session.rollback()
            return 0

    @staticmethod
    def delete_equipment_records(equipment_id):
        """
        删除设备记录
        :param equipment_id: 设备ID列表
        :return: 删除结果
        """
        try:
            for i in equipment_id:
                if isinstance(i, dict) and i.get('children'):
                    # 删除父设备
                    db.session.query(Equipment).filter_by(id=i['id']).delete()
                    db.session.commit()
                    # 删除子设备
                    for child in i.get('children', []):
                        child_id = child.get('id') if isinstance(child, dict) else child
                        if child_id:
                            db.session.query(Equipment).filter_by(id=child_id).delete()
                            db.session.commit()
                else:
                    # 删除单个设备
                    equipment_item_id = i.get('id') if isinstance(i, dict) else i
                    if equipment_item_id:
                        db.session.query(Equipment).filter_by(id=equipment_item_id).delete()
                        db.session.commit()
            return True
        except Exception as e:
            print(f"删除设备记录时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def check_vcr_exists(ip):
        """
        检查录像机是否已存在
        :param ip: 录像机IP
        :return: 录像机设备信息
        """
        try:
            return db.session.query(Equipment).filter(Equipment.equipment_ip == ip).first()
        except SQLAlchemyError as e:
            print(f"检查录像机存在性时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def create_vcr_data(vcr_type, vcr_way, vcr_name, ip, username, password, port, mine_id):
        """
        创建VCR数据
        :param vcr_type: 厂商类型
        :param vcr_way: 接入方式
        :param vcr_name: 录像机名称
        :param ip: 录像机ip
        :param username: 录像机用户
        :param password: 录像机密码
        :param port: 录像机端口
        :param mine_id: 矿id
        :return: VCR数据ID
        """
        try:
            VCR_data_data = VCR_data(
                vcr_type=vcr_type if vcr_type in ['海康', '大华', '索尼', '宇视', '天地伟业', '三星'] else None,
                vcr_way=vcr_way if vcr_way in ['私有SDK', 'Onvif', 'GB28181'] else None,
                vcr_name=vcr_name,
                vcr_ip=ip,
                vcr_username=username,
                vcr_password=password,
                vcr_port=port,
                Mine_id=mine_id,
                online=1,
                type=1
            )
            db.session.add(VCR_data_data)
            db.session.commit()
            return VCR_data_data.id
        except SQLAlchemyError as e:
            print(f"创建VCR数据时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def create_parent_equipment(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname, equipment_password, mine_id, vcr_data_id):
        """
        创建父设备
        :param equipment_type: 设备类型
        :param manufacturer_type: 厂商类型
        :param equipment_name: 设备名称
        :param equipment_ip: 设备IP
        :param equipment_uname: 设备用户名
        :param equipment_password: 设备密码
        :param mine_id: 矿id
        :param vcr_data_id: VCR数据ID
        :return: 父设备对象
        """
        try:
            equipment_data = Equipment(
                equipment_type=equipment_type,
                manufacturer_type=manufacturer_type,
                equipment_name=equipment_name,
                equipment_ip=equipment_ip,
                equipment_uname=equipment_uname,
                equipment_password=equipment_password,
                Mine_id=int(mine_id) if mine_id else None,
                online=1,
                VCR_data_id=vcr_data_id,
            )
            db.session.add(equipment_data)
            db.session.commit()
            return equipment_data
        except SQLAlchemyError as e:
            print(f"创建父设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def create_child_equipment(equipment_type, manufacturer_type, equipment_name, equipment_ip, equipment_uname, equipment_password, equipment_aisles, mine_id, parent_id, code, vcr_data_id, online, equipment_width_height, equipment_codetype, equipment_constantBitRate, equipment_maxFrameRate, onvif_rtsp_url=None):
        """
        创建子设备
        :param equipment_type: 设备类型
        :param manufacturer_type: 厂商类型
        :param equipment_name: 设备名称
        :param equipment_ip: 设备IP
        :param equipment_uname: 设备用户名
        :param equipment_password: 设备密码
        :param equipment_aisles: 设备通道
        :param mine_id: 矿id
        :param parent_id: 父设备ID
        :param code: 设备编码
        :param vcr_data_id: VCR数据ID
        :param online: 在线状态
        :param equipment_width_height: 设备分辨率
        :param equipment_codetype: 设备码流类型
        :param equipment_constantBitRate: 设备恒定码率
        :param equipment_maxFrameRate: 设备最大帧率
        :param onvif_rtsp_url: Onvif RTSP URL
        :return: 子设备对象
        """
        try:
            child_equipment_data = Equipment(
                equipment_type=equipment_type if equipment_type else None,
                manufacturer_type=manufacturer_type if manufacturer_type else None,
                equipment_name=equipment_name if equipment_name else None,
                equipment_ip=equipment_ip if equipment_ip is not None else None,
                equipment_uname=equipment_uname if equipment_uname else None,
                equipment_password=equipment_password if equipment_password else None,
                equipment_aisles=equipment_aisles if equipment_aisles else None,
                Mine_id=int(mine_id) if mine_id else None,
                parent_id=int(parent_id) if parent_id else None,
                code=code if code else None,
                VCR_data_id=vcr_data_id,
                online=online,
                equipment_width_height=equipment_width_height if equipment_width_height else '',
                equipment_codetype=equipment_codetype if equipment_codetype in ['H265', 'H264'] else None,
                equipment_constantBitRate=equipment_constantBitRate if equipment_constantBitRate else '',
                equipment_maxFrameRate=equipment_maxFrameRate if equipment_maxFrameRate else '',
                Onvif_rtsp_url=onvif_rtsp_url if onvif_rtsp_url else None
            )
            db.session.add(child_equipment_data)
            db.session.commit()
            return child_equipment_data
        except SQLAlchemyError as e:
            print(f"创建子设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def update_vcr_status(vcr_data_id, status):
        """
        更新VCR数据状态
        :param vcr_data_id: VCR数据ID
        :param status: 状态
        :return: 是否更新成功
        """
        try:
            vcr_data = db.session.query(VCR_data).filter(VCR_data.id == vcr_data_id).first()
            if vcr_data:
                vcr_data.vcr_status = status
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新VCR数据状态时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_vcr_data_by_id(vcr_id):
        """
        根据ID获取VCR数据
        :param vcr_id: VCR ID
        :return: VCR数据对象
        """
        try:
            return db.session.query(VCR_data).filter(VCR_data.id == vcr_id).first()
        except SQLAlchemyError as e:
            print(f"获取VCR数据时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def update_vcr_data_by_id(vcr_id, vcr_data):
        """
        根据ID更新VCR数据
        :param vcr_id: VCR ID
        :param vcr_data: VCR数据
        :return: 是否更新成功
        """
        try:
            update_query = update(VCR_data).where(VCR_data.id == vcr_id).values(**vcr_data)
            db.session.execute(update_query)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新VCR数据时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_equipment_by_vcr_id(vcr_id, equipment_data, is_parent=True):
        """
        根据VCR ID更新设备数据
        :param vcr_id: VCR ID
        :param equipment_data: 设备数据
        :param is_parent: 是否为父设备
        :return: 是否更新成功
        """
        try:
            if is_parent:
                update_query = update(Equipment).where(Equipment.VCR_data_id == vcr_id, Equipment.parent_id == None).values(**equipment_data)
            else:
                update_query = update(Equipment).where(Equipment.VCR_data_id == vcr_id, Equipment.parent_id != None).values(**equipment_data)
            db.session.execute(update_query)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新设备数据时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_vcr_data_list(vcr_type=None, page=1, per_page=1000):
        """
        获取VCR数据列表
        :param vcr_type: VCR类型
        :param page: 页码
        :param per_page: 每页条数
        :return: 分页对象
        """
        try:
            query = db.session.query(VCR_data)
            if vcr_type is not None:
                query = query.filter(VCR_data.type == vcr_type)
            return query.paginate(page=page, per_page=per_page, error_out=False)
        except SQLAlchemyError as e:
            print(f"获取VCR数据列表时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_vcr_data_with_children(vcr_id, vcr_type=None):
        """
        获取VCR数据及其子设备
        :param vcr_id: VCR ID
        :param vcr_type: VCR类型
        :return: VCR数据对象
        """
        try:
            query = db.session.query(VCR_data).filter(VCR_data.id == vcr_id)
            if vcr_type is not None:
                query = query.filter(VCR_data.type == vcr_type)
            return query.first()
        except SQLAlchemyError as e:
            print(f"获取VCR数据及其子设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_children_equipment_by_vcr_id(vcr_id, page=1, per_page=1000):
        """
        根据VCR ID获取子设备
        :param vcr_id: VCR ID
        :param page: 页码
        :param per_page: 每页条数
        :return: 分页对象
        """
        try:
            query = db.session.query(Equipment).filter(Equipment.VCR_data_id == vcr_id, Equipment.parent_id != None)
            return query.paginate(page=page, per_page=per_page, error_out=False)
        except SQLAlchemyError as e:
            print(f"获取子设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_equipment_ids_by_vcr_id(vcr_id):
        """
        根据VCR ID获取设备ID列表
        :param vcr_id: VCR ID
        :return: 设备ID列表
        """
        try:
            equipment_ids = db.session.query(Equipment.id).filter(Equipment.VCR_data_id == vcr_id).all()
            return [i[0] for i in equipment_ids]
        except SQLAlchemyError as e:
            print(f"获取设备ID列表时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def get_algorithm_config_ids_by_equipment_ids(equipment_ids):
        """
        根据设备ID列表获取算法配置ID列表
        :param equipment_ids: 设备ID列表
        :return: 算法配置ID列表
        """
        try:
            algorithm_config_ids = db.session.query(Algorithm_config.id).filter(Algorithm_config.Equipment_id.in_(equipment_ids)).all()
            return [i[0] for i in algorithm_config_ids]
        except SQLAlchemyError as e:
            print(f"获取算法配置ID列表时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def delete_algorithm_configs(algorithm_config_ids):
        """
        删除算法配置
        :param algorithm_config_ids: 算法配置ID列表
        :return: 是否删除成功
        """
        try:
            db.session.query(Algorithm_config).filter(Algorithm_config.id.in_(algorithm_config_ids)).delete()
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"删除算法配置时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def delete_algorithm_results(algorithm_config_ids):
        """
        删除算法结果
        :param algorithm_config_ids: 算法配置ID列表
        :return: 是否删除成功
        """
        try:
            from service.alarm_retention_service import queue_and_delete_alarm_records
            alarm_ids = [row.id for row in db.session.query(Algorithm_result.id).filter(
                Algorithm_result.Algorithm_config_id.in_(algorithm_config_ids)).all()]
            queue_and_delete_alarm_records(alarm_ids)
            return True
        except Exception as e:
            print(f"删除算法结果时出错: {type(e).__name__}")
            db.session.rollback()
            return False

    @staticmethod
    def delete_equipment_by_ids(equipment_ids):
        """
        根据ID列表删除设备
        :param equipment_ids: 设备ID列表
        :return: 是否删除成功
        """
        try:
            db.session.query(Equipment).filter(Equipment.id.in_(equipment_ids)).delete()
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"删除设备时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def delete_vcr_data_by_id(vcr_id):
        """
        根据ID删除VCR数据
        :param vcr_id: VCR ID
        :return: 是否删除成功
        """
        try:
            db.session.query(VCR_data).filter(VCR_data.id == vcr_id).delete()
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"删除VCR数据时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_all_vcr_data():
        """
        获取所有VCR数据
        :return: VCR数据列表
        """
        try:
            return db.session.query(VCR_data).all()
        except SQLAlchemyError as e:
            print(f"获取所有VCR数据时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def update_equipment_online_by_vcr_id(vcr_id, online, zlk_dat_id=None):
        """
        根据VCR ID更新设备在线状态
        :param vcr_id: VCR ID
        :param online: 在线状态
        :param zlk_dat_id: 流媒体数据ID
        :return: 是否更新成功
        """
        try:
            update_data = {'online': online}
            if zlk_dat_id is not None:
                update_data['zlk_dat_id'] = zlk_dat_id
            db.session.query(Equipment).filter(Equipment.VCR_data_id == vcr_id).update(update_data)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新设备在线状态时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_vcr_online_by_id(vcr_id, online):
        """
        根据ID更新VCR在线状态
        :param vcr_id: VCR ID
        :param online: 在线状态
        :return: 是否更新成功
        """
        try:
            db.session.query(VCR_data).filter(VCR_data.id == vcr_id).update({'online': online})
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"更新VCR在线状态时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_parent_equipment_by_vcr_id(vcr_id):
        """
        根据VCR ID获取父设备
        :param vcr_id: VCR ID
        :return: 父设备对象
        """
        try:
            return db.session.query(Equipment).filter(
                Equipment.VCR_data_id == vcr_id,
                Equipment.parent_id == None
            ).first()
        except SQLAlchemyError as e:
            print(f"获取父设备时出错: {str(e)}")
            db.session.rollback()
            return None



    @staticmethod
    def update_equipment_by_id(equipment_id, update_data):
        """
        根据ID更新设备信息
        :param equipment_id: 设备ID
        :param update_data: 更新数据字典
        :return: 是否更新成功
        """
        try:
            equipment = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if equipment:
                for key, value in update_data.items():
                    if hasattr(equipment, key):
                        setattr(equipment, key, value)
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新设备信息时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def create_equipment_from_dict(equipment_data):
        """
        创建设备（从字典）
        :param equipment_data: 设备数据字典
        :return: 设备对象
        """
        try:
            new_device = Equipment(**equipment_data)
            db.session.add(new_device)
            db.session.commit()
            return new_device
        except SQLAlchemyError as e:
            print(f"创建设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def delete_equipment_by_id(equipment_id):
        """
        根据ID删除设备
        :param equipment_id: 设备ID
        :return: 是否删除成功
        """
        try:
            db.session.query(Equipment).filter(Equipment.id == equipment_id).delete()
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            print(f"删除设备时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def get_equipment_by_ip(equipment_ip):
        """
        根据IP获取设备
        :param equipment_ip: 设备IP
        :return: 设备对象
        """
        try:
            return db.session.query(Equipment).filter(Equipment.equipment_ip == equipment_ip).first()
        except SQLAlchemyError as e:
            print(f"根据IP获取设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_equipment_by_parent_id(parent_id):
        """
        根据父设备ID获取设备
        :param parent_id: 父设备ID
        :return: 设备对象
        """
        try:
            return db.session.query(Equipment).filter(Equipment.parent_id == parent_id).first()
        except SQLAlchemyError as e:
            print(f"根据父设备ID获取设备时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def get_empty_zlk_equipments():
        """
        获取zlk_dat_id为空的设备列表
        :return: 设备列表
        """
        try:
            return db.session.query(Equipment).filter(Equipment.zlk_dat_id.is_(None)).all()
        except SQLAlchemyError as e:
            print(f"获取zlk_dat_id为空的设备时出错: {str(e)}")
            db.session.rollback()
            return []

    @staticmethod
    def get_zlk_data_by_id(zlk_id):
        """
        根据ID获取ZLK数据
        :param zlk_id: ZLK数据ID
        :return: ZLK数据对象
        """
        try:
            return db.session.query(Zlk_data).filter(Zlk_data.id == zlk_id).first()
        except SQLAlchemyError as e:
            print(f"获取ZLK数据时出错: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def update_zlk_data_equipment(zlk_id, equipment):
        """
        更新ZLK数据的设备关联
        :param zlk_id: ZLK数据ID
        :param equipment: 设备对象
        :return: 是否更新成功
        """
        try:
            zlk_data = db.session.query(Zlk_data).filter(Zlk_data.id == zlk_id).first()
            if zlk_data:
                zlk_data.equipment = equipment
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新ZLK数据设备关联时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def clear_zlk_data_equipment(zlk_id):
        """
        清空ZLK数据的设备关联
        :param zlk_id: ZLK数据ID
        :return: 是否更新成功
        """
        try:
            zlk_data = db.session.query(Zlk_data).filter(Zlk_data.id == zlk_id).first()
            if zlk_data:
                zlk_data.equipment = None
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"清空ZLK数据设备关联时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_equipment_zlk_dat_id(equipment_id, zlk_dat_id):
        """
        更新设备的ZLK数据ID
        :param equipment_id: 设备ID
        :param zlk_dat_id: ZLK数据ID
        :return: 是否更新成功
        """
        try:
            equipment = db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if equipment:
                equipment.zlk_dat_id = zlk_dat_id
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            print(f"更新设备ZLK数据ID时出错: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def clear_zlk_data_equipment_by_vcr_id(vcr_id):
        """
        根据VCR ID清空ZLK数据的设备关联
        :param vcr_id: VCR ID
        :return: 是否更新成功
        """
        try:
            equipment_ids = db.session.query(Equipment.id).filter(Equipment.VCR_data_id == vcr_id).subquery()
            db.session.query(Zlk_data).filter(Zlk_data.equipment.has(id=equipment_ids.c.id)).update(
                {Zlk_data.equipment: None}, synchronize_session=False
            )
            return True
        except SQLAlchemyError as e:
            print(f"清空ZLK数据设备关联时出错: {str(e)}")
            db.session.rollback()
            return False


