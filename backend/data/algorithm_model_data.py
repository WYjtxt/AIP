from service.count_algorithm_family import count_template_matches, is_count_model_name
import bdb
import datetime
import os
import ast
import dbutils.steady_db
from flask import jsonify, request, Blueprint, make_response
from config.configs import *
from model.admin import *
from model.algorithm import *
from service.person_count_scope import count_model_scopes
from model.equipment import *
from model.extra import *
from model.log import *
from model.ai_camera import *
from sqlalchemy import and_, func, update, select, text, cast, Integer, or_,desc
import yaml
import io
import zipfile
from datetime import datetime, timedelta
import cv2
from urllib.parse import urlparse, quote
import time
import json
import random
import string
import asyncio
from sqlalchemy.exc import SQLAlchemyError
from service.algorithm_model_service import *
from model.algorithm import *


def fetch_algorithm_type_data(algorithm_library_id):
    """查询算法类型相关数据"""
    algo_model_data = db.session.query(
        Algorithm_library.model_type_name,
        Algorithm_library.model_name,
        Algorithm_library.template_small_name,
        Algorithm_library.algorithm_version,
        Algorithm_library.analysis_type
    ).filter(Algorithm_library.id == algorithm_library_id).first()

    if not algo_model_data:
        return [], [], [], [], []

    model_type_data = db.session.query(Model_template_config_type.id,
                                       Model_template_config_type.model_type_name).filter(
        Model_template_config_type.model_type_name == algo_model_data[0]).all()
    model_type_data = convert_folder_to_dict_list(model_type_data, ['id', 'model_type_name'])

    model_data = [{'id': row.id, 'model_name': row.model_name}
                  for row in compatible_model_templates(algo_model_data[1], algo_model_data[4])]

    template_small_data = db.session.query(Model_template_small.id,
                                           Model_template_small.template_small_name).filter(
        Model_template_small.template_small_name == algo_model_data[2]).all()
    template_small_data = convert_folder_to_dict_list(template_small_data, ['id', 'template_small_name'])

    algorithm_data = db.session.query(Algorithm_test_type.id, Algorithm_test_type.test_type_ename,
                                      Algorithm_test_type.test_type_cname,
                                      Algorithm_test_type.Algorithm_library_id).filter(
        Algorithm_test_type.Algorithm_library_id == algorithm_library_id).all()
    algorithm_data = convert_folder_to_dict_list(algorithm_data, ['id', 'test_type_ename', 'test_type_cname',
                                                                  'Algorithm_library_id', ])

    algo_version = algo_model_data[3]
    analysis_type_val = algo_model_data[4]
    algorithm_child = db.session.query(Algorithm_library).filter(
        Algorithm_library.algorithm_version == algo_version,
        Algorithm_library.analysis_type == analysis_type_val,
        Algorithm_library.algorithm_child == 2
    ).first()
    # 子算法数据查询
    algorithm_child_data = []
    if algorithm_child:
        algorithm_child_data = db.session.query(Algorithm_test_type.id, Algorithm_test_type.test_type_ename,
                                                Algorithm_test_type.test_type_cname,
                                                Algorithm_test_type.Algorithm_library_id).filter(
            Algorithm_test_type.Algorithm_library_id == algorithm_child.id).all()
        algorithm_child_data = convert_folder_to_dict_list(algorithm_child_data,
                                                           ['id', 'test_type_ename', 'test_type_cname',
                                                            'Algorithm_library_id', ])

    return model_type_data, model_data, template_small_data, algorithm_data,algorithm_child_data


def fetch_algorithm_type_data_aicam(algorithm_library_id):
    """查询算法类型相关数据"""
    algo_model_data = db.session.query(
        Algorithm_library_3588.model_type_name,
        Algorithm_library_3588.model_name,
        Algorithm_library_3588.template_small_name,
        Algorithm_library_3588.algorithm_version,
        Algorithm_library_3588.analysis_type
    ).filter(Algorithm_library_3588.id == algorithm_library_id).first()

    if not algo_model_data:
        return [], [], [], [], []

    model_type_data = db.session.query(Model_template_config_type_3588.id,
                                       Model_template_config_type_3588.model_type_name).filter(
        Model_template_config_type_3588.model_type_name == algo_model_data[0]).all()
    model_type_data = convert_folder_to_dict_list(model_type_data, ['id', 'model_type_name'])

    model_data = db.session.query(Model_template_config_3588.id, Model_template_config_3588.model_name).filter(
        Model_template_config_3588.model_name == algo_model_data[1]).all()
    model_data = convert_folder_to_dict_list(model_data, ['id', 'model_name'])

    template_small_data = db.session.query(Model_template_small_3588.id,
                                           Model_template_small_3588.template_small_name).filter(
        Model_template_small_3588.template_small_name == algo_model_data[2]).all()
    template_small_data = convert_folder_to_dict_list(template_small_data, ['id', 'template_small_name'])

    algorithm_data = db.session.query(Algorithm_test_type_3588.id, Algorithm_test_type_3588.test_type_ename,
                                      Algorithm_test_type_3588.test_type_cname,
                                      Algorithm_test_type_3588.Algorithm_library_id).filter(
        Algorithm_test_type_3588.Algorithm_library_id == algorithm_library_id).all()
    algorithm_data = convert_folder_to_dict_list(algorithm_data, ['id', 'test_type_ename', 'test_type_cname',
                                                                  'Algorithm_library_id', ])

    algo_version = algo_model_data[3]
    analysis_type_val = algo_model_data[4]
    algorithm_child = db.session.query(Algorithm_library_3588).filter(
        Algorithm_library_3588.algorithm_version == algo_version,
        Algorithm_library_3588.analysis_type == analysis_type_val,
        Algorithm_library_3588.algorithm_child == 2
    ).first()
    # 子算法数据查询
    algorithm_child_data = []
    if algorithm_child:
        algorithm_child_data = db.session.query(Algorithm_test_type_3588.id, Algorithm_test_type_3588.test_type_ename,
                                                Algorithm_test_type_3588.test_type_cname,
                                                Algorithm_test_type_3588.Algorithm_library_id).filter(
            Algorithm_test_type_3588.Algorithm_library_id == algorithm_child.id).all()
        algorithm_child_data = convert_folder_to_dict_list(algorithm_child_data,
                                                           ['id', 'test_type_ename', 'test_type_cname',
                                                            'Algorithm_library_id', ])

    return model_type_data, model_data, template_small_data, algorithm_data,algorithm_child_data



def fetch_equipment_image_data(equipment_id):
    """查询设备图像相关信息"""
    from model.equipment import Equipment
    equipment_data = Equipment.query.with_entities(
        Equipment.id,
        Equipment.equipment_uname,
        Equipment.equipment_password,
        Equipment.equipment_ip,
        Equipment.equipment_type,
        Equipment.parent_id,
        Equipment.code,
        Equipment.Hik_rtsp_url,
        Equipment.Ziguang_ape_rtsp_url,
        Equipment.equipment_aisles
    ).filter(Equipment.id == equipment_id).first()

    return equipment_data

def get_mine_info():
    """获取矿山信息"""
    return db.session.query(Mine).first()

def get_trade_type_id(trade_name):
    """根据厂商名称获取厂商ID"""
    return db.session.query(Dict_data.data_id).filter(
        func.lower(Dict_data.data_value) == trade_name.lower()
    ).first()

def get_model_template_info(model_type_name, model_name, template_small_name):
    """获取模型模板相关信息"""
    model_type = db.session.query(Model_template_config_type.id).filter(
        Model_template_config_type.model_type_name == model_type_name
    ).first()
    candidates = compatible_model_templates(model_name, declared_type=model_type[0] if model_type else None)
    model = (candidates[0].id,) if candidates else None
    small_model = db.session.query(Model_template_small.id).filter(
        Model_template_small.template_small_name == template_small_name
    ).first()
    return model_type, model, small_model

def parse_yaml_from_zip(zip_ref, yaml_filename='data.yaml'):
    """从ZIP文件中解析YAML文件"""
    if yaml_filename in zip_ref.namelist():
        with zip_ref.open(yaml_filename) as yaml_file:
            return yaml.safe_load(yaml_file)
    return None

def extract_bmodel_file(zip_ref, file_extension='.bmodel'):
    """提取ZIP中的.bmodel文件"""
    files_to_check = [f for f in zip_ref.namelist() if f.endswith(file_extension)]
    if files_to_check:
        return files_to_check[0], zip_ref.open(files_to_check[0]).read()
    return None, None

def fetch_algorithm_library_basic(type_param=None):
    if type_param =='2':
        query = db.session.query(
            Algorithm_library_3588.id,
            Algorithm_library_3588.algorithm_name,
            Algorithm_library_3588.algorithm_file_name,
            Algorithm_library_3588.algorithm_type,
            Algorithm_library_3588.algorithm_path,
            Algorithm_library_3588.model_type_name,
        ).filter(
            Algorithm_library_3588.algorithm_status == 1,
            Algorithm_library_3588.algorithm_parent == 1,
            Algorithm_library_3588.algorithm_child == 1
        )
    else:
        query = db.session.query(
            Algorithm_library.id,
            Algorithm_library.algorithm_name,
            Algorithm_library.algorithm_file_name,
            Algorithm_library.algorithm_type,
            Algorithm_library.algorithm_path,
            Algorithm_library.model_type_name,
        ).filter(
            Algorithm_library.algorithm_status == 1,
            Algorithm_library.algorithm_parent == 1,
            Algorithm_library.algorithm_child == 1
        )
    if type_param == '1':
        query = query.filter(Algorithm_library.model_type_name == '基础检测类')
    return query.all()

def fetch_algorithm_library_cascade(type_param= None):
    if type_param =='2':
        return db.session.query(
            Algorithm_library_3588.id,
            Algorithm_library_3588.algorithm_name,
            Algorithm_library_3588.algorithm_file_name,
            Algorithm_library_3588.algorithm_type,
            Algorithm_library_3588.algorithm_path,
        ).filter(
            Algorithm_library_3588.algorithm_status == 1,
            Algorithm_library_3588.algorithm_parent == 1,
            Algorithm_library_3588.algorithm_child == 2
        ).all()
    else:
        return db.session.query(
            Algorithm_library.id,
            Algorithm_library.algorithm_name,
            Algorithm_library.algorithm_file_name,
            Algorithm_library.algorithm_type,
            Algorithm_library.algorithm_path,
        ).filter(
            Algorithm_library.algorithm_status == 1,
            Algorithm_library.algorithm_parent == 1,
            Algorithm_library.algorithm_child == 2
        ).all()

def fetch_algorithm_configs_joined(type_param= None):
    if type_param =='2':
        return db.session.query(
            Algorithm_config_3588.id,
            Algorithm_config_3588.conf_name,
            Algorithm_library_3588.algorithm_path
        ).join(
            Algorithm_library_3588,
            Algorithm_config_3588.Algorithm_library_id == Algorithm_library_3588.id
        ).all()
    else:
        return db.session.query(
            Algorithm_config.id,
            Algorithm_config.conf_name,
            Algorithm_library.algorithm_path
        ).join(
            Algorithm_library,
            Algorithm_config.Algorithm_library_id == Algorithm_library.id
        ).all()

def list_dict_data_rows():
    return db.session.query(
        Dict_data.id, Dict_data.data_label, Dict_data.data_value, Dict_data.type_code, Dict_data.enable, Dict_data.remark
    ).all()

def list_dict_type_rows():
    return db.session.query(
        DictType.id, DictType.type_name, DictType.type_code, DictType.description, DictType.enable
    ).all()

def list_diagnosis_type_rows():
    return db.session.query(
        Diagnosis_type.id, Diagnosis_type.name, Diagnosis_type.prewarn, Diagnosis_type.warn
    ).all()

def list_model_template_types(type_param=None):
    if type_param =='2':
        return db.session.query(Model_template_config_type_3588).all()
    else:
        return db.session.query(Model_template_config_type).all()

def list_model_templates_by_type(type_id, type_param=None):
    if type_param =='2':
        return db.session.query(Model_template_config_3588).filter(
            Model_template_config_3588.model_template_config_type_id == type_id
        ).all()
    else:
        return db.session.query(Model_template_config).filter(
            Model_template_config.model_template_config_type_id == type_id
        ).all()

def list_model_template_all(type_param=None):
    if type_param =='2':
        return db.session.query(Model_template_config_3588).all()
    else:
        return db.session.query(Model_template_config).all()

def list_mines_rows():
    return db.session.query(Mine.id, Mine.mine_name).all()

def list_equipment_root_by_mine(mine_id,type_param=None):
    if type_param =='2':
        return db.session.query(Equipment).filter(
            Equipment.Mine_id == int(mine_id),
            Equipment.parent_id == None,
            or_(
                Equipment.equipment_type == 'AI单光摄像头',
                Equipment.equipment_type == 'AI双光摄像头'
             )
        ).all()
    else:
        return db.session.query(Equipment).filter(
            Equipment.Mine_id == int(mine_id), Equipment.parent_id == None
        ).all()

def list_equipment_root_all(type_param= None):
    if type_param =='2':
        return db.session.query(Equipment).filter(Equipment.parent_id == None,
            or_(
                Equipment.equipment_type == 'AI单光摄像头',
                Equipment.equipment_type == 'AI双光摄像头'
             )).all()
    else:
        return db.session.query(Equipment).filter(Equipment.parent_id == None).all()

def get_algorithm_config_by_name(conf_name):
    return db.session.query(Algorithm_config).filter(Algorithm_config.conf_name == conf_name).first()
def get_algorithm_config_by_name_aicam(conf_name, equipment_id):
    return db.session.query(Algorithm_config_3588).filter(
        and_(
            Algorithm_config_3588.conf_name == conf_name,
            Algorithm_config_3588.Equipment_id == equipment_id
        )
    ).first()

def get_algorithm_config_by_equipment_and_library(equipment_id, library_id):
    return db.session.query(Algorithm_config).filter(
        Algorithm_config.Equipment_id == equipment_id,
        Algorithm_config.Algorithm_library_id == library_id
    ).first()
def get_algorithm_config_by_equipment_and_library_aicam(equipment_id, library_id):
    return db.session.query(Algorithm_config_3588).filter(
        Algorithm_config_3588.Equipment_id == equipment_id,
        Algorithm_config_3588.Algorithm_library_id == library_id
    ).first()
def get_algorithm_library_by_id(library_id):
    return db.session.query(Algorithm_library).filter(Algorithm_library.id == library_id).first()
def get_algorithm_library_by_id_aicam(library_id):
    return db.session.query(Algorithm_library_3588).filter(Algorithm_library_3588.id == library_id).first()

def get_mine_by_id(mine_id):
    return db.session.query(Mine).filter(Mine.id == mine_id).first()

def get_resource_usage_by_id(resource_id):
    return db.session.query(Resource_usage).filter(Resource_usage.id == resource_id).first()

def insert_algorithm_config(fields):
    config_data = Algorithm_config(
        conf_name=fields.get('conf_name'),
        stream_type=fields.get('stream_type'),
        Algorithm_library_id=int(fields.get('Algorithm_library_id')),
        Mine_id=int(fields.get('Mine_id')),
        Equipment_id=int(fields.get('Equipment_id')),
        conf_area=str(fields.get('conf_area')) if fields.get('conf_area') else str([]),
        status=fields.get('status') if fields.get('status') else '1',
        Algorithm_test_type_id=fields.get('test_type_id'),
        shield_status=fields.get('shield_status'),
        tem_conf_area=str(fields.get('tem_conf_area')) if fields.get('tem_conf_area') else str([]),
        label_list=str(fields.get('label_list')) if fields.get('label_list') else str([]),
        tem_frames=fields.get('tem_frames'),
        draw_type=fields.get('draw_type'),
        confidence=fields.get('confidence') if fields.get('confidence') else '0.2',
        interval_time=fields.get('interval_time'),
        conf_img_resolution=fields.get('img_resolution'),
        duration_time=fields.get('duration_time'),
        image_draw_type=fields.get('image_draw_type'),
        Algorithm_config_ps=fields.get('Algorithm_config_ps'),
        scene_typename=fields.get('scene_typename'),
        sensitivity=fields.get('sensitivity'),
        resource_id=fields.get('resource_id'),
        computing_id=fields.get('computing_id'),
        model_status=1,
        model_template_config_id=fields.get('model_template_config_id'),
        template_list_area=str(fields.get('template_list_area')) if fields.get('template_list_area') else str([]),
        image_count=fields.get('image_count'),
        template_small_id=fields.get('template_small_id'),
        conf_status=1,
        count_time=int(fields.get('count_time')) if fields.get('count_time') else 0,
        res_type=fields.get('res_type'),
        defense_time_start=fields.get('defense_time_start'),
        defense_time_end=fields.get('defense_time_end'),
        template_data=fields.get('template_data') if fields.get('template_data') else '',
        model_template_type_id=fields.get('model_template_type_id') if fields.get('model_template_type_id') else '',
        amp=fields.get('amp', 10),
        alg_select_type=fields.get('alg_select_type', 3),
        model_two_data=fields.get('model_two_data'),
        model_two_type=fields.get('model_two_type'),
        priority=fields.get('priority'),
        run_time=fields.get('run_time'),
        model_algo_data=fields.get('model_algo_data') if fields.get('model_algo_data') else '',
        model_algo_data_ori=fields.get('model_algo_data_ori') if fields.get('model_algo_data_ori') else '',
        multimodels_type=fields.get('multimodels_type') if fields.get('multimodels_type') else 0,
        Entering_num = fields.get('Entering_num'),
        Exiting_num = fields.get('Exiting_num'),
        all_Entering_num = fields.get('all_Entering_num'),
        all_Exiting_num = fields.get('all_Exiting_num'),
        cross_line_area = fields.get('cross_line_area'),
    )
    db.session.add(config_data)
    db.session.commit()
    return config_data

def insert_algorithm_config_aicam(fields):
    config_data = Algorithm_config_3588(
        conf_name=fields.get('conf_name'),
        Algorithm_library_id=int(fields.get('Algorithm_library_id')),
        Mine_id=int(fields.get('Mine_id')),
        Equipment_id=int(fields.get('Equipment_id')),
        conf_area=str(fields.get('conf_area')) if fields.get('conf_area') else str([]),
        status=fields.get('status') if fields.get('status') else '1',
        Algorithm_test_type_id=fields.get('test_type_id'),
        shield_status=fields.get('shield_status'),
        tem_conf_area=str(fields.get('tem_conf_area')) if fields.get('tem_conf_area') else str([]),
        label_list=str(fields.get('label_list')) if fields.get('label_list') else str([]),
        tem_frames=fields.get('tem_frames'),
        draw_type=fields.get('draw_type'),
        confidence=fields.get('confidence') if fields.get('confidence') else '0.2',
        interval_time=fields.get('interval_time'),
        conf_img_resolution=fields.get('img_resolution'),
        duration_time=fields.get('duration_time'),
        image_draw_type=fields.get('image_draw_type'),
        Algorithm_config_ps=fields.get('Algorithm_config_ps'),
        scene_typename=fields.get('scene_typename'),
        sensitivity=fields.get('sensitivity'),
        resource_id=fields.get('resource_id'),
        computing_id=fields.get('computing_id'),
        model_status=1,
        model_template_config_id=fields.get('model_template_config_id'),
        template_list_area=str(fields.get('template_list_area')) if fields.get('template_list_area') else str([]),
        image_count=fields.get('image_count'),
        template_small_id=fields.get('template_small_id'),
        conf_status=1,
        count_time=int(fields.get('count_time')) if fields.get('count_time') else 0,
        res_type=fields.get('res_type'),
        defense_time_start=fields.get('defense_time_start'),
        defense_time_end=fields.get('defense_time_end'),
        template_data=fields.get('template_data') if fields.get('template_data') else '',
        model_template_type_id=fields.get('model_template_type_id') if fields.get('model_template_type_id') else '',
        amp=fields.get('amp', 10),
        alg_select_type=fields.get('alg_select_type', 3),
        model_two_data=fields.get('model_two_data'),
        model_two_type=fields.get('model_two_type'),
        priority=fields.get('priority'),
        run_time=fields.get('run_time'),
        model_algo_data=fields.get('model_algo_data') if fields.get('model_algo_data') else '',
        model_algo_data_ori=fields.get('model_algo_data_ori') if fields.get('model_algo_data_ori') else '',
        multimodels_type=fields.get('multimodels_type') if fields.get('multimodels_type') else 0,
        uwb_distance=fields.get('uwb_distance'),
        camera_config_id=fields.get('camera_config_id'),
        cross_line_area = fields.get('cross_line_area'),
        Entering_num = fields.get('Entering_num'),
        Exiting_num = fields.get('Exiting_num'),
        all_Entering_num = fields.get('all_Entering_num'),
        all_Exiting_num = fields.get('all_Exiting_num'),
    )
    db.session.add(config_data)
    db.session.commit()
    return config_data

_PERSON_COUNT_READ_ONLY_FIELDS = frozenset((
    'Entering_num', 'Exiting_num', 'all_Entering_num', 'all_Exiting_num',
))


def _person_count_read_only_fields(config, fields, library_model):
    # A settings form can carry an old snapshot or missing (None) count values.
    # Identify the existing task before applying any submitted library change.
    # Status-only updates do not need another library lookup.
    if not _PERSON_COUNT_READ_ONLY_FIELDS.intersection(fields):
        return frozenset()
    if library_model is Algorithm_library:
        # A count model may be the primary model or one advanced child. Protect
        # both the current scope and a newly selected count scope before applying
        # any submitted template/library/model change or stale counter snapshot.
        template_types = {}

        def template_type(template_id):
            if template_id not in template_types:
                row = db.session.query(Model_template_config.model_template_config_type_id,
                                       Model_template_config.model_name).filter(
                    Model_template_config.id == template_id).first()
                template_types[template_id] = (row[0], row[1]) if row else None
            return template_types[template_id]

        desired = {
            'model_template_config_id': fields.get('model_template_config_id', config.model_template_config_id),
            'model_algo_data_ori': fields.get('model_algo_data_ori', config.model_algo_data_ori),
        }
        try:
            if count_model_scopes(config, template_type) or count_model_scopes(desired, template_type):
                return _PERSON_COUNT_READ_ONLY_FIELDS
        except ValueError:
            # An unreadable scope cannot authorize overwriting runtime output.
            return _PERSON_COUNT_READ_ONLY_FIELDS
    library = db.session.query(library_model.analysis_type).filter(
        library_model.id == config.Algorithm_library_id).first()
    if library and is_count_model_name(library[0]):
        return _PERSON_COUNT_READ_ONLY_FIELDS
    return frozenset()


def update_algorithm_config_fields(id, fields):
    conf_id = db.session.query(Algorithm_config).filter(Algorithm_config.id == id).first()
    if conf_id:
        read_only_fields = _person_count_read_only_fields(conf_id, fields, Algorithm_library)
        for field, value in fields.items():
            if field not in read_only_fields:
                setattr(conf_id, field, value)
        db.session.commit()
    return conf_id


def update_algorithm_config_fields_aicam(id, fields):
    conf_id = db.session.query(Algorithm_config_3588).filter(Algorithm_config_3588.id == id).first()
    if conf_id:
        read_only_fields = _person_count_read_only_fields(conf_id, fields, Algorithm_library_3588)
        for field, value in fields.items():
            if field not in read_only_fields:
                setattr(conf_id, field, value)
        db.session.commit()
    return conf_id

def fetch_algorithm_config_detail(conf_id):
    return db.session.query(
        Algorithm_config.id,
        Algorithm_config.status,
        Algorithm_library.id.label('Algorithm_library_id'),
        Algorithm_library.algorithm_name,
        Algorithm_library.algorithm_version,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.parent_id.label("editor_equipment_parent_id"),
        Equipment.code,
        Algorithm_config.conf_name,
        Algorithm_config.conf_object,
        Algorithm_config.conf_time,
        Algorithm_config.conf_area,
        Algorithm_config.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config.shield_status,
        Algorithm_config.tem_conf_area,
        Algorithm_config.tem_frames,
        Algorithm_config.draw_type,
        Algorithm_config.confidence,
        Algorithm_config.interval_time,
        Algorithm_config.conf_img_resolution,
        Algorithm_config.duration_time,
        Algorithm_config.image_draw_type,
        Algorithm_config.update_time,
        Algorithm_config.Algorithm_config_ps,
        Algorithm_config.scene_typename,
        Algorithm_config.sensitivity,
        Algorithm_config.model_status,
        Algorithm_config.resource_id,
        Algorithm_config.defense_time_start,
        Algorithm_config.defense_time_end,
        Algorithm_config.model_template_config_id,
        Algorithm_config.template_list_area,
        Algorithm_config.image_count,
        Algorithm_config.template_small_id,
        Algorithm_config.count_time,
        Algorithm_config.res_type,
        Algorithm_config.template_data,
        Algorithm_config.label_list,
        Algorithm_config.conf_status,
        Algorithm_config.amp,
        Algorithm_config.alg_select_type,
        Algorithm_config.model_two_data,
        Algorithm_config.model_two_type,
        Algorithm_config.priority,
        Algorithm_config.run_time,
        Algorithm_config.model_algo_data_ori,
        Algorithm_config.model_template_type_id,
        Algorithm_config.computing_id,
        Algorithm_config.multimodels_type,
        Algorithm_config.stream_type,
        Algorithm_config.Entering_num,
        Algorithm_config.Exiting_num,
        Algorithm_config.all_Entering_num,
        Algorithm_config.all_Exiting_num,
        Algorithm_config.cross_line_area
    ).join(
        Algorithm_config,
        Algorithm_library.id == Algorithm_config.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    ).order_by(Algorithm_config.conf_time.desc()).filter(Algorithm_config.id == conf_id).first()

def editor_equipment_path(equipment_id, equipment_name, equipment_type, parent_id, mine_id):
    if not equipment_id or not equipment_name:
        return []
    path = [{'id': equipment_id, 'equipment_name': equipment_name, 'equipment_type': equipment_type,
             'parent_id': parent_id, 'Mine_id': mine_id}]
    seen = {equipment_id}
    while parent_id and parent_id not in seen and len(path) < 8:
        parent = db.session.query(Equipment.id, Equipment.equipment_name, Equipment.equipment_type,
                                  Equipment.parent_id, Equipment.Mine_id).filter(
            Equipment.id == parent_id, Equipment.Mine_id == mine_id).first()
        if parent is None or not parent.equipment_name:
            break
        seen.add(parent.id)
        path.append(dict(parent._mapping))
        parent_id = parent.parent_id
    return list(reversed(path))


def editor_algorithm_identity(library_id):
    return db.session.query(Algorithm_library.id, Algorithm_library.algorithm_name,
                            Algorithm_library.algorithm_version).filter(Algorithm_library.id == library_id).first()


def fetch_algorithm_config_detail_aicam(conf_id):
    return db.session.query(
        Algorithm_config_3588.id,
        Algorithm_config_3588.status,
        Algorithm_library_3588.id.label('Algorithm_library_id'),
        Algorithm_library_3588.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config_3588.conf_name,
        Algorithm_config_3588.conf_object,
        Algorithm_config_3588.conf_time,
        Algorithm_config_3588.conf_area,
        Algorithm_config_3588.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config_3588.shield_status,
        Algorithm_config_3588.tem_conf_area,
        Algorithm_config_3588.tem_frames,
        Algorithm_config_3588.draw_type,
        Algorithm_config_3588.confidence,
        Algorithm_config_3588.interval_time,
        Algorithm_config_3588.conf_img_resolution,
        Algorithm_config_3588.duration_time,
        Algorithm_config_3588.image_draw_type,
        Algorithm_config_3588.update_time,
        Algorithm_config_3588.Algorithm_config_ps,
        Algorithm_config_3588.scene_typename,
        Algorithm_config_3588.sensitivity,
        Algorithm_config_3588.model_status,
        Algorithm_config_3588.resource_id,
        Algorithm_config_3588.defense_time_start,
        Algorithm_config_3588.defense_time_end,
        Algorithm_config_3588.model_template_config_id,
        Algorithm_config_3588.template_list_area,
        Algorithm_config_3588.image_count,
        Algorithm_config_3588.template_small_id,
        Algorithm_config_3588.count_time,
        Algorithm_config_3588.res_type,
        Algorithm_config_3588.template_data,
        Algorithm_config_3588.label_list,
        Algorithm_config_3588.conf_status,
        Algorithm_config_3588.amp,
        Algorithm_config_3588.alg_select_type,
        Algorithm_config_3588.model_two_data,
        Algorithm_config_3588.model_two_type,
        Algorithm_config_3588.priority,
        Algorithm_config_3588.run_time,
        Algorithm_config_3588.model_algo_data_ori,
        Algorithm_config_3588.model_template_type_id,
        Algorithm_config_3588.computing_id,
        Algorithm_config_3588.multimodels_type,
        Algorithm_config_3588.uwb_distance,
        Algorithm_config_3588.camera_config_id,
        Algorithm_config_3588.cross_line_area,
        Algorithm_config_3588.Entering_num,
        Algorithm_config_3588.Exiting_num,
        Algorithm_config_3588.all_Entering_num,
        Algorithm_config_3588.all_Exiting_num,
    ).join(
        Algorithm_config_3588,
        Algorithm_library_3588.id == Algorithm_config_3588.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config_3588.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config_3588.Equipment_id == Equipment.id
    ).order_by(Algorithm_config_3588.conf_time.desc()).filter(Algorithm_config_3588.id == conf_id).first()


def fetch_algorithm_configs(query_filter=None):
    base_query = db.session.query(
        Algorithm_config.id,
        Algorithm_config.status,
        Algorithm_library.id.label('Algorithm_library_id'),
        Algorithm_library.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config.conf_name,
        Algorithm_config.conf_object,
        Algorithm_config.conf_time,
        Algorithm_config.conf_area,
        Algorithm_config.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config.shield_status,
        Algorithm_config.tem_conf_area,
        Algorithm_config.tem_frames,
        Algorithm_config.draw_type,
        Algorithm_config.confidence,
        Algorithm_config.interval_time,
        Algorithm_config.conf_img_resolution,
        Algorithm_config.duration_time,
        Algorithm_config.image_draw_type,
        Algorithm_config.update_time,
        Algorithm_config.Algorithm_config_ps,
        Algorithm_config.scene_typename,
        Algorithm_config.sensitivity,
        Algorithm_config.model_status,
        Algorithm_config.resource_id,
        Algorithm_config.defense_time_start,
        Algorithm_config.defense_time_end,
        Algorithm_config.model_template_config_id,
        Algorithm_config.template_list_area,
        Algorithm_config.image_count,
        Algorithm_config.template_small_id,
        Algorithm_config.count_time,
        Algorithm_config.res_type,
        Algorithm_config.template_data,
        Algorithm_config.label_list,
        Algorithm_config.conf_status,
        Algorithm_config.amp,
        Algorithm_config.alg_select_type,
        Algorithm_config.model_two_data,
        Algorithm_config.model_two_type,
        Algorithm_config.priority,
        Algorithm_config.run_time,
        Algorithm_config.model_algo_data_ori,
        Algorithm_config.model_template_type_id,
        Algorithm_config.computing_id,
        Algorithm_config.multimodels_type,
        Algorithm_config.stream_type,
        Algorithm_config.Entering_num,
        Algorithm_config.Exiting_num,
        Algorithm_config.all_Entering_num,
        Algorithm_config.all_Exiting_num,
        Algorithm_config.cross_line_area
    ).join(
        Algorithm_config,
        Algorithm_library.id == Algorithm_config.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    ).order_by(Algorithm_config.conf_time.desc())
    if query_filter is not None:
        base_query = base_query.filter(query_filter)
    return base_query.all()

def fetch_algorithm_configs_aicam(query_filter=None):
    base_query = db.session.query(
        Algorithm_config_3588.id,
        Algorithm_config_3588.status,
        Algorithm_library_3588.id.label('Algorithm_library_id'),
        Algorithm_library_3588.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config_3588.conf_name,
        Algorithm_config_3588.conf_object,
        Algorithm_config_3588.conf_time,
        Algorithm_config_3588.conf_area,
        Algorithm_config_3588.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config_3588.shield_status,
        Algorithm_config_3588.tem_conf_area,
        Algorithm_config_3588.tem_frames,
        Algorithm_config_3588.draw_type,
        Algorithm_config_3588.confidence,
        Algorithm_config_3588.interval_time,
        Algorithm_config_3588.conf_img_resolution,
        Algorithm_config_3588.duration_time,
        Algorithm_config_3588.image_draw_type,
        Algorithm_config_3588.update_time,
        Algorithm_config_3588.Algorithm_config_ps,
        Algorithm_config_3588.scene_typename,
        Algorithm_config_3588.sensitivity,
        Algorithm_config_3588.model_status,
        Algorithm_config_3588.resource_id,
        Algorithm_config_3588.defense_time_start,
        Algorithm_config_3588.defense_time_end,
        Algorithm_config_3588.model_template_config_id,
        Algorithm_config_3588.template_list_area,
        Algorithm_config_3588.image_count,
        Algorithm_config_3588.template_small_id,
        Algorithm_config_3588.count_time,
        Algorithm_config_3588.res_type,
        Algorithm_config_3588.template_data,
        Algorithm_config_3588.label_list,
        Algorithm_config_3588.conf_status,
        Algorithm_config_3588.amp,
        Algorithm_config_3588.alg_select_type,
        Algorithm_config_3588.model_two_data,
        Algorithm_config_3588.model_two_type,
        Algorithm_config_3588.priority,
        Algorithm_config_3588.run_time,
        Algorithm_config_3588.model_algo_data_ori,
        Algorithm_config_3588.model_template_type_id,
        Algorithm_config_3588.computing_id,
        Algorithm_config_3588.multimodels_type,
        Algorithm_config_3588.uwb_distance,
        Algorithm_config_3588.camera_config_id,
        Algorithm_config_3588.cross_line_area,
        Algorithm_config_3588.Entering_num,
        Algorithm_config_3588.Exiting_num,
        Algorithm_config_3588.all_Entering_num,
        Algorithm_config_3588.all_Exiting_num,
    ).join(
        Algorithm_config_3588,
        Algorithm_library_3588.id == Algorithm_config_3588.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config_3588.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config_3588.Equipment_id == Equipment.id
    ).order_by(Algorithm_config_3588.conf_time.desc())
    if query_filter is not None:
        base_query = base_query.filter(query_filter)
    return base_query.all()

def insert_algorithm_config_history_from_config(config_obj, operation_type):
    history_data = Algorithm_config_history(
        stream_type=getattr(config_obj, 'stream_type', None),
        conf_name=config_obj.conf_name if config_obj.conf_name else None,
        Algorithm_library_id=int(config_obj.Algorithm_library_id) if config_obj.Algorithm_library_id else None,
        Mine_id=int(config_obj.Mine_id) if config_obj.Mine_id else None,
        Equipment_id=int(config_obj.Equipment_id) if config_obj.Equipment_id else None,
        conf_area=str(config_obj.conf_area) if config_obj.conf_area else None,
        status=config_obj.status if config_obj.status else '1',
        Algorithm_test_type_id=config_obj.Algorithm_test_type_id if config_obj.Algorithm_test_type_id else None,
        shield_status=config_obj.shield_status,
        tem_conf_area=str(config_obj.tem_conf_area) if config_obj.tem_conf_area else str([]),
        tem_frames=config_obj.tem_frames if config_obj.tem_frames else None,
        draw_type=config_obj.draw_type,
        confidence=config_obj.confidence if config_obj.confidence else '0.2',
        interval_time=config_obj.interval_time if config_obj.interval_time else 0,
        conf_img_resolution=config_obj.conf_img_resolution,
        duration_time=config_obj.duration_time if config_obj.duration_time else 0,
        image_draw_type=config_obj.image_draw_type if config_obj.image_draw_type else 1,
        Algorithm_config_ps=config_obj.Algorithm_config_ps if config_obj.Algorithm_config_ps else None,
        scene_typename=config_obj.scene_typename if config_obj.scene_typename else None,
        operation_type=operation_type,
        config_id=config_obj.id,
        sensitivity=config_obj.sensitivity if config_obj.sensitivity else 0,
        resource_id=config_obj.resource_id,
        defense_time_start=config_obj.defense_time_start,
        defense_time_end=config_obj.defense_time_end,
        model_template_config_id=config_obj.model_template_config_id,
        template_list_area=str(config_obj.template_list_area) if config_obj.template_list_area else str([]),
        image_count=config_obj.image_count,
        template_small_id=config_obj.template_small_id,
        conf_status=0,
        count_time=int(config_obj.count_time) if config_obj.count_time else 0,
        res_type=config_obj.res_type,
    )
    db.session.add(history_data)
    db.session.commit()
    return history_data


def fetch_algorithm_history_detail(history_id):
    return db.session.query(
        Algorithm_config_history.id,
        Algorithm_config_history.status,
        Algorithm_config_history.stream_type,
        Algorithm_library.id.label('Algorithm_library_id'),
        Algorithm_library.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config_history.conf_name,
        Algorithm_config_history.conf_object,
        Algorithm_config_history.conf_time,
        Algorithm_config_history.conf_area,
        Algorithm_config_history.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config_history.shield_status,
        Algorithm_config_history.tem_conf_area,
        Algorithm_config_history.tem_frames,
        Algorithm_config_history.draw_type,
        Algorithm_config_history.confidence,
        Algorithm_config_history.interval_time,
        Algorithm_config_history.conf_img_resolution,
        Algorithm_config_history.duration_time,
        Algorithm_config_history.image_draw_type,
        Algorithm_config_history.update_time,
        Algorithm_config_history.Algorithm_config_ps,
        Algorithm_config_history.operation_type,
        Algorithm_config_history.scene_typename,
        Algorithm_config_history.sensitivity,
        Algorithm_config.model_status,
        Algorithm_config.resource_id,
        Algorithm_config_history.defense_time_start,
        Algorithm_config_history.defense_time_end,
        Algorithm_config_history.model_template_config_id,
        Algorithm_config_history.template_list_area,
        Algorithm_config_history.image_count,
        Algorithm_config.template_small_id,
        Algorithm_config.count_time,
        Algorithm_config.res_type
    ).join(
        Algorithm_config_history,
        Algorithm_library.id == Algorithm_config_history.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config_history.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config_history.Equipment_id == Equipment.id
    ).join(
        Algorithm_config,
        Algorithm_config_history.config_id == Algorithm_config.id
    ).order_by(Algorithm_config_history.update_time.desc()).filter(
        Algorithm_config_history.id == history_id
    ).first()

def fetch_algorithm_configs_by_ids(id_list):
    return db.session.query(Algorithm_config).filter(Algorithm_config.id.in_(id_list)).all()

def delete_algorithm_configs_by_ids(id_list):
    db.session.query(Algorithm_config).filter(Algorithm_config.id.in_(id_list)).delete()
    db.session.commit()
    return True
def fetch_algorithm_configs_by_ids_aicam(id_list):
    return db.session.query(Algorithm_config_3588).filter(Algorithm_config_3588.id.in_(id_list)).all()

def delete_algorithm_configs_by_ids_aicam(id_list):
    db.session.query(Algorithm_config_3588).filter(Algorithm_config_3588.id.in_(id_list)).delete()
    db.session.commit()
    return True
def fetch_algorithm_result_total_count(query_filter):
    subquery_algorithm_result1 = db.session.query(
        Algorithm_result.id,
        Algorithm_result.Algorithm_config_id,
        Algorithm_result.Algorithm_library_id,
        Algorithm_result.res_time,
        Algorithm_result.res_type,
        Algorithm_result.res_image,
        Algorithm_result.res_video,
        Algorithm_result.res_frame_skip,
        Algorithm_result.carousel_images_list,
        Algorithm_result.result_count,
        Algorithm_result.result_count_time,
        Algorithm_result.template_type_id,
        Algorithm_result.Entering_num,
        Algorithm_result.Exiting_num,
        Algorithm_result.approval_status,
        Algorithm_result.disposal_status,
        Algorithm_result.approval_opinion,
        Algorithm_result.disposal_opinion,
        Algorithm_result.disposal_time,
        Algorithm_result.conf_name,
        Algorithm_result.conf_img_resolution,
        Algorithm_result.algorithm_name,
        Algorithm_result.equipment_name,
        Algorithm_result.equipment_type,
        Algorithm_result.mine_name,
        Algorithm_result.uwb_id,
    ).filter(query_filter if query_filter is not True else True).order_by(
        desc(Algorithm_result.res_time)
    ).subquery()
    total_count_query = db.session.query(func.count().label('total_count')).select_from(
        subquery_algorithm_result1)
    return total_count_query.scalar()

def fetch_equipment_types_distinct():
    equipment_types_query = db.session.query(Equipment.equipment_type).distinct().all()
    return [row[0] for row in equipment_types_query]

def fetch_algorithm_result_page(query_filter, per_page, page):
    algorithm_info = db.session.query(
        Algorithm_result.id.label('Algorithm_result_id'),
        Algorithm_result.res_time,
        func.coalesce(func.nullif(Algorithm_result.mine_name, ''), Mine.mine_name).label('mine_name'),
        Algorithm_result.equipment_name,
        Algorithm_result.equipment_type,
        Algorithm_result.conf_name,
        Algorithm_result.conf_img_resolution,
        Algorithm_result.res_type,
        Algorithm_result.res_image,
        Algorithm_result.res_video,
        Algorithm_result.warning_video,
        Algorithm_result.res_frame_skip,
        Algorithm_result.carousel_images_list,
        Algorithm_result.ori_images_list,
        Algorithm_result.result_count,
        Algorithm_result.result_count_time,
        Algorithm_result.template_type_id,
        Algorithm_result.Entering_num,
        Algorithm_result.Exiting_num,
        Algorithm_result.Algorithm_library_id,
        Algorithm_result.approval_status,
        Algorithm_result.disposal_status,
        Algorithm_result.approval_opinion,
        Algorithm_result.disposal_opinion,
        Algorithm_result.disposal_time,
        Algorithm_result.algorithm_name,
        Algorithm_result.template_id,
        Algorithm_result.Mine_id,
        Algorithm_result.Equipment_id,
        Algorithm_result.Algorithm_config_id,
        Algorithm_result.warning_message,
        Model_template_config.id,
        Algorithm_result.uwb_id,
        Model_template_config.model_name,
        Model_template_config.model_type,
        Model_template_config_type.model_type_name,
        Model_template_config_type.id.label('model_type_id'),
    ).outerjoin(Mine, Algorithm_result.Mine_id == Mine.id).outerjoin(
        Model_template_config,
        and_(
            Algorithm_result.template_id == Model_template_config.id
        )
    ).outerjoin(
        Model_template_config_type,
        Algorithm_result.template_type_id == Model_template_config_type.id
    ).filter(query_filter if query_filter is not True else True).order_by(
        desc(Algorithm_result.res_time)
    ).limit(per_page).offset((page - 1) * per_page).all()
    return algorithm_info

def fetch_equipment_algorithm_status_list():
    return db.session.query(
        Algorithm_config.Equipment_id,
        Algorithm_config.status,
        Equipment.equipment_ip,
        Equipment.online,
        Algorithm_config.algorithm_status,
        Algorithm_config.id
    ).join(Equipment, Algorithm_config.Equipment_id == Equipment.id).all()

def update_algorithm_status_by_id(config_id, status_value):
    db.session.query(Algorithm_config).filter(Algorithm_config.id == config_id).update({
        'algorithm_status': status_value
    })
    db.session.commit()

def fetch_algorithm_result_sqlalchemy_paginated(query_filter, page, per_page):
    return db.session.query(
        Algorithm_result.id.label('Algorithm_result_id'),
        Algorithm_result.res_time,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Algorithm_config.id.label('Algorithm_config_id'),
        Algorithm_config.conf_name,
        Algorithm_config.conf_img_resolution,
        Algorithm_result.res_type,
        Algorithm_result.res_image,
        Algorithm_result.res_video,
        Algorithm_result.res_frame_skip,
        Algorithm_library.algorithm_name,
    ).join(
        Algorithm_config,
        Algorithm_config.id == Algorithm_result.Algorithm_config_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    ).join(
        Algorithm_library,
        Algorithm_config.Algorithm_library_id == Algorithm_library.id
    ).filter(query_filter).order_by(Algorithm_result.res_time.desc()).paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_result_sqlalchemy_paginated_no_filter(page, per_page):
    return db.session.query(
        Algorithm_result.id.label('Algorithm_result_id'),
        Algorithm_result.res_time,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Algorithm_config.id.label('Algorithm_config_id'),
        Algorithm_config.conf_name,
        Algorithm_config.conf_img_resolution,
        Algorithm_result.res_type,
        Algorithm_result.res_image,
        Algorithm_result.res_video,
        Algorithm_result.res_frame_skip,
        Algorithm_library.algorithm_name,
    ).join(
        Algorithm_config,
        Algorithm_config.id == Algorithm_result.Algorithm_config_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    ).join(
        Algorithm_library,
        Algorithm_config.Algorithm_library_id == Algorithm_library.id
    ).order_by(Algorithm_result.res_time.desc()).paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_result_sqlalchemy_paginated_by_id(record_id, page, per_page):
    return db.session.query(
        Algorithm_result.id.label('Algorithm_result_id'),
        Algorithm_result.res_time,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Algorithm_config.id.label('Algorithm_config_id'),
        Algorithm_config.conf_name,
        Algorithm_config.conf_img_resolution,
        Algorithm_result.res_type,
        Algorithm_result.res_image,
        Algorithm_result.res_video,
        Algorithm_result.res_frame_skip,
        Algorithm_library.algorithm_name,
    ).join(
        Algorithm_config,
        Algorithm_config.id == Algorithm_result.Algorithm_config_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    ).join(
        Algorithm_library,
        Algorithm_config.Algorithm_library_id == Algorithm_library.id
    ).filter(Algorithm_result.id == record_id).order_by(Algorithm_result.res_time.desc()).paginate(page=page, per_page=per_page, error_out=False)

def get_algorithm_result_by_id(id):
    return db.session.query(Algorithm_result).filter(Algorithm_result.id == id).first()

def update_algorithm_result_fields(id, update_fields):
    db.session.query(Algorithm_result).filter(Algorithm_result.id == id).update(update_fields)
    db.session.commit()
    return True

def fetch_algorithm_ratio_items(query_filter):
    base_query = db.session.query(
        Algorithm_config,
        Algorithm_result.res_time
    ).join(
        Algorithm_result,
        Algorithm_config.id == Algorithm_result.Algorithm_config_id
    ).join(
        Mine,
        Algorithm_config.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config.Equipment_id == Equipment.id
    )
    if query_filter is not None:
        base_query = base_query.filter(query_filter)
    return base_query.all()

def fetch_library_names_by_ids(library_ids):
    return db.session.query(
        Algorithm_library.id,
        Algorithm_library.algorithm_name
    ).filter(Algorithm_library.id.in_(library_ids)).all()

def fetch_video_show_equipments(page, per_page):
    query = db.session.query(
        Equipment.id,
        Equipment.equipment_name,
        Equipment.Mine_id,
        Equipment.equipment_ip,
        Equipment.equipment_uname,
        Equipment.equipment_password,
        Equipment.equipment_type,
        Equipment.parent_id,
        Equipment.code,
        Equipment.Hik_rtsp_url
    ).filter(
        ((Equipment.equipment_type == '浙江双视热成像') | (Equipment.equipment_type == '摄像头')
         | ((Equipment.parent_id != None) & (Equipment.equipment_type == '录像机'))
         | ((Equipment.parent_id != None) & (Equipment.equipment_type == '视频中心存储'))
         | ((Equipment.parent_id != None) & (Equipment.equipment_type == '特殊摄像头'))
         | ((Equipment.parent_id != None) & (Equipment.equipment_type == '安防平台')))
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_library_paginated(query_filter, page, per_page):
    base_query = db.session.query(Algorithm_library).filter(
        Algorithm_library.algorithm_parent == 1,
        Algorithm_library.algorithm_child == 1
    ).order_by(Algorithm_library.create_time.desc())
    if query_filter is not None:
        base_query = base_query.filter(query_filter)
    return base_query.paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_config_history_paginated(config_id, page, per_page):
    query = db.session.query(
        Algorithm_config_history.id,
        Algorithm_config_history.status,
        Algorithm_config_history.stream_type,
        Algorithm_library.id.label('Algorithm_library_id'),
        Algorithm_library.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config_history.conf_name,
        Algorithm_config_history.conf_object,
        Algorithm_config_history.conf_time,
        Algorithm_config_history.conf_area,
        Algorithm_config_history.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config_history.shield_status,
        Algorithm_config_history.tem_conf_area,
        Algorithm_config_history.tem_frames,
        Algorithm_config_history.draw_type,
        Algorithm_config_history.confidence,
        Algorithm_config_history.interval_time,
        Algorithm_config_history.conf_img_resolution,
        Algorithm_config_history.duration_time,
        Algorithm_config_history.image_draw_type,
        Algorithm_config_history.update_time,
        Algorithm_config_history.Algorithm_config_ps,
        Algorithm_config_history.operation_type,
        Algorithm_config_history.scene_typename,
        Algorithm_config_history.sensitivity,
        Algorithm_config.model_status,
        Algorithm_config.resource_id,
        Algorithm_config_history.defense_time_start,
        Algorithm_config_history.defense_time_end,
        Algorithm_config_history.model_template_config_id,
        Algorithm_config_history.template_list_area,
        Algorithm_config_history.image_count,
        Algorithm_config.template_small_id,
        Algorithm_config.count_time,
        Algorithm_config.res_type,
    ).join(
        Algorithm_config_history,
        Algorithm_library.id == Algorithm_config_history.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config_history.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config_history.Equipment_id == Equipment.id
    ).join(
        Algorithm_config,
        Algorithm_config_history.config_id == Algorithm_config.id
    ).filter(Algorithm_config_history.config_id == config_id).order_by(
        Algorithm_config_history.update_time.desc()
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_config_history_all_paginated(page, per_page):
    query = db.session.query(
        Algorithm_config_history.id,
        Algorithm_config_history.status,
        Algorithm_config_history.stream_type,
        Algorithm_library.id.label('Algorithm_library_id'),
        Algorithm_library.algorithm_name,
        Mine.id.label('Mine_id'),
        Mine.mine_name,
        Equipment.id.label('Equipment_id'),
        Equipment.equipment_name,
        Equipment.equipment_type,
        Equipment.code,
        Algorithm_config_history.conf_name,
        Algorithm_config_history.conf_object,
        Algorithm_config_history.conf_time,
        Algorithm_config_history.conf_area,
        Algorithm_config_history.Algorithm_test_type_id.label('test_type_id'),
        Algorithm_config_history.shield_status,
        Algorithm_config_history.tem_conf_area,
        Algorithm_config_history.tem_frames,
        Algorithm_config_history.draw_type,
        Algorithm_config_history.confidence,
        Algorithm_config_history.interval_time,
        Algorithm_config_history.conf_img_resolution,
        Algorithm_config_history.duration_time,
        Algorithm_config_history.image_draw_type,
        Algorithm_config_history.update_time,
        Algorithm_config_history.Algorithm_config_ps,
        Algorithm_config_history.operation_type,
        Algorithm_config_history.scene_typename,
        Algorithm_config_history.sensitivity,
        Algorithm_config.model_status,
        Algorithm_config.resource_id,
        Algorithm_config_history.defense_time_start,
        Algorithm_config_history.defense_time_end,
        Algorithm_config_history.model_template_config_id,
        Algorithm_config_history.template_list_area,
        Algorithm_config_history.image_count,
        Algorithm_config.template_small_id,
        Algorithm_config.count_time,
        Algorithm_config.res_type,
    ).join(
        Algorithm_config_history,
        Algorithm_library.id == Algorithm_config_history.Algorithm_library_id
    ).join(
        Mine,
        Algorithm_config_history.Mine_id == Mine.id
    ).join(
        Equipment,
        Algorithm_config_history.Equipment_id == Equipment.id
    ).join(
        Algorithm_config,
        Algorithm_config_history.config_id == Algorithm_config.id
    ).order_by(Algorithm_config_history.update_time.desc())
    return query.paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_configs_by_library_id(library_id):
    return db.session.query(Algorithm_config).filter(Algorithm_config.Algorithm_library_id == library_id).all()

def update_algorithm_library_status(library_id, status_value):
    db.session.query(Algorithm_library).filter(Algorithm_library.id == library_id).update({
        'algorithm_status': status_value
    })
    db.session.commit()
    return True

def update_configs_status_for_library(library_id, status_value, model_status_value, conf_status_value):
    db.session.query(Algorithm_config).filter(Algorithm_config.Algorithm_library_id == library_id).update({
        'status': status_value,
        'model_status': model_status_value,
        'conf_status': conf_status_value
    })
    db.session.commit()
    return True

def delete_algorithm_libraries_by_ids(library_ids):
    db.session.query(Algorithm_library).filter(Algorithm_library.id.in_(library_ids)).delete()
    db.session.commit()
    return True

def fetch_algorithm_config_ids_by_library_ids(library_ids):
    conf_id_rows = db.session.query(Algorithm_config.id).filter(Algorithm_config.Algorithm_library_id.in_(library_ids)).all()
    return [row[0] for row in conf_id_rows]

def add_algorithm_result_delete_records(library_ids):
    for lid in library_ids:
        delete_record = Algorithm_result_delete(algorithm_id=lid)
        db.session.add(delete_record)
    db.session.commit()
    return True

def dict_type_exists(type_code):
    return db.session.query(DictType).filter(DictType.type_code == type_code).first()

def add_dict_type(type_name, type_code, description, enable):
    dict_type = DictType(
        type_name=type_name,
        type_code=type_code,
        description=description,
        enable=enable if enable else '1'
    )
    db.session.add(dict_type)
    db.session.commit()
    return dict_type

def update_dict_type(id, fields):
    dict_type = db.session.query(DictType).filter(DictType.id == id).first()
    if dict_type:
        for k, v in fields.items():
            setattr(dict_type, k, v)
        db.session.commit()
    return dict_type

def update_dict_data_type_code(old_type_code, new_type_code):
    dict_datas = db.session.query(Dict_data).filter(Dict_data.type_code == old_type_code).all()
    for i in dict_datas:
        i.type_code = new_type_code
    db.session.commit()
    return True

def delete_dict_types_by_ids(ids):
    db.session.query(DictType).filter(DictType.id.in_(ids)).delete()
    db.session.commit()
    return True

def fetch_type_codes_by_type_ids(ids):
    code_rows = db.session.query(DictType.type_code).filter(DictType.id.in_(ids)).all()
    return [row[0] for row in code_rows]

def delete_dict_data_by_type_codes(type_codes):
    db.session.query(Dict_data).filter(Dict_data.type_code.in_(type_codes)).delete()
    db.session.commit()
    return True

def paginate_dict_types_by_name(dict_name, page, per_page):
    return db.session.query(DictType).order_by(DictType.create_time.desc()).filter(
        DictType.type_name.like(f'%{dict_name}%')
    ).paginate(page=page, per_page=per_page, error_out=False)

def paginate_dict_types(page, per_page):
    return db.session.query(DictType).order_by(DictType.create_time.desc()).paginate(page=page, per_page=per_page, error_out=False)

def fetch_max_data_id_for_type(type_code):
    return db.session.query(func.max(Dict_data.data_id)).filter(Dict_data.type_code == type_code).scalar()

def add_dict_data(data_label, data_value, type_code, is_default, enable, remark, data_id):
    dict_data = Dict_data(
        data_id=data_id,
        data_label=data_label,
        data_value=data_value,
        type_code=type_code,
        is_default=is_default if is_default else '0',
        enable=enable if enable else '1',
        remark=remark
    )
    db.session.add(dict_data)
    db.session.commit()
    return dict_data

def get_dict_data_by_id(id):
    return db.session.query(Dict_data).filter(Dict_data.id == id).first()

def update_dict_data_fields(id, fields):
    dict_data = db.session.query(Dict_data).filter(Dict_data.id == id).first()
    if dict_data:
        for k, v in fields.items():
            setattr(dict_data, k, v)
        db.session.commit()
    return dict_data

def delete_dict_data_by_ids(ids):
    db.session.query(Dict_data).filter(Dict_data.id.in_(ids)).delete()
    db.session.commit()
    return True

def paginate_dict_data_by_type_code(type_code, page, per_page):
    return db.session.query(Dict_data).filter(Dict_data.type_code == type_code).order_by(
        Dict_data.create_time.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

def fetch_algorithm_results_count_by_ids(id_list):
    return db.session.query(Algorithm_result.id).filter(Algorithm_result.id.in_(id_list)).count()

def delete_algorithm_results_by_ids(id_list):
    from service.alarm_retention_service import queue_and_delete_alarm_records
    return queue_and_delete_alarm_records(id_list)
    return True

def fetch_mine_by_name(mine_name):
    return db.session.query(Mine).filter(Mine.mine_name == mine_name).first()

def fetch_mine_by_code(mine_code):
    return db.session.query(Mine).filter(Mine.mine_code == mine_code).first()

def insert_mine(mine_name, mine_code):
    obj = Mine(mine_name=mine_name, mine_code=mine_code)
    db.session.add(obj)
    db.session.commit()
    return obj


def delete_mine_by_id(mine_id):
    obj = db.session.query(Mine).filter(Mine.id == mine_id).first()
    if obj:
        db.session.delete(obj)
        db.session.commit()
        return True
    return False

def update_mine_fields(mine_id, fields):
    obj = db.session.query(Mine).filter(Mine.id == mine_id).first()
    if obj:
        for k, v in fields.items():
            setattr(obj, k, v)
        db.session.commit()
    return obj

def paginate_mines(page, per_page):
    return db.session.query(Mine).paginate(page=page, per_page=per_page, error_out=False)

def fetch_mine_detail_by_id(mine_id):
    return db.session.query(Mine).filter_by(id=mine_id).first()

def fetch_equipment_search(equip_type_flag, name):
    query = db.session.query(Equipment)
    if equip_type_flag == '1':
        query = query.filter(Equipment.equipment_type == '录像机')
    elif equip_type_flag == '2':
        query = query.filter(Equipment.equipment_type == '安防平台')
    if name:
        query = query.filter(Equipment.equipment_name.ilike(f'%{name}%'), Equipment.parent_id != None)
    return query.all()

def fetch_first_version():
    return db.session.query(Version).first()


def get_unprocessed_alarms(start_time, end_time, excluded_ids):

    query_filter = and_(
        Algorithm_result.disposal_status == 0,  # 未审批状态
        Algorithm_result.res_time >= start_time,
        Algorithm_result.res_time <= end_time
    )

    if excluded_ids:
        query_filter = and_(query_filter, ~Algorithm_result.id.in_(excluded_ids))

    results = db.session.query(Algorithm_result).filter(query_filter) \
        .order_by(Algorithm_result.res_time.desc()).all()

    return results

# count-template-family-v1

def compatible_model_templates(model_name, analysis_type=None, declared_type=None):
    """Reuse count geometry only; the selected algorithm retains its own labels/OM."""
    rows=db.session.query(Model_template_config).all()
    matched=[row for row in rows if count_template_matches(model_name,row.model_name,
                row.model_template_config_type_id,analysis_type)]
    matched=[row for row in matched if not is_count_model_name(row.model_name) or str(row.model_type)=='1']
    if declared_type is not None:
        matched=[row for row in matched if str(row.model_template_config_type_id)==str(declared_type)]
    requested = str(analysis_type or model_name or "").strip()
    return sorted(matched,key=lambda row:(
        requested in ('人数统计_全身', '人数统计_头肩') and str(row.model_name or "").strip() != requested,
        0 if str(row.model_name or '').strip()=='人数统计' and str(row.model_type)=='1' else 1,
        0 if str(row.model_name or '').strip()=='人数统计' else 1,
        0 if str(row.model_name or '').strip()=='人员计数' else 1,int(row.id)))
