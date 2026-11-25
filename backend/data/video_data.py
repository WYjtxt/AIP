from config.configs import *
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from tool.OpenApi_public_Class import HikVisionAPI
import redis
import re
import urllib.parse

def get_model(model_id=None, algorithm_name=None):
    if model_id is not None:
        return db.session.query(Algorithm_library).filter(Algorithm_library.id == model_id).first()
    if algorithm_name is not None:
        return db.session.query(Algorithm_library).filter(Algorithm_library.analysis_type == algorithm_name).first()
    return None

def get_equipment_by_id(equipment_id):
    return db.session.query(Equipment).filter(Equipment.id == equipment_id).first()
def get_result_video_by_id(id):
    return db.session.query(Algorithm_result).filter(Algorithm_result.id == id).first()
def get_parent_equipment_by_id(parent_id):
    if not parent_id:
        return None
    return db.session.query(Equipment).filter(Equipment.id == parent_id).first()

def get_hik_platform_api():
    platform_data = db.session.query(Hik_security_platform_info).all()
    platform_dict_list = convert_folder_to_dict_list(
        platform_data,
        ['id', 'hik_host', 'hik_port', 'hik_appKey', 'hik_appSecret', 'Mine_id']
    )
    if not platform_dict_list:
        return None
    p = platform_dict_list[0]
    return HikVisionAPI(
        host=p.get('hik_host'),
        port=p.get('hik_port'),
        app_key=p.get('hik_appKey'),
        app_secret=p.get('hik_appSecret')
    )

def extract_ip_from_rtsp(rtsp_url):
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', rtsp_url)
    return m.group(1) if m else None

def get_redis(db_index):
    return redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password, decode_responses=True, db=db_index)

def r_set(db_index, key, value):
    r = get_redis(db_index)
    r.set(key, value)
    return r

def r_get(db_index, key):
    r = get_redis(db_index)
    return r.get(key)

def r_delete(db_index, key):
    r = get_redis(db_index)
    r.delete(key)
    return r

def set_video_data_list(data_list):
    r = get_redis(3)
    r.set('video_data_list', str(data_list))
    return r

def set_stream_data_flag(flag, db_index=3):
    r = get_redis(db_index)
    r.set('stream_data_flag', flag)
    return r

def get_video_type(db_index=3):
    return r_get(db_index, 'video_type')

def get_zlk_data_by_id(zlk_id):
    if not zlk_id:
        return None
    return db.session.query(Zlk_data).filter(Zlk_data.id == zlk_id).first()
