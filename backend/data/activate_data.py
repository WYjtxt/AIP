import os
import json
import re
from datetime import datetime
from data.exts import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *

class ActivateData:
    """激活数据层，处理数据库操作和文件操作"""
    
    @staticmethod
    def create_activate_record(info_dict, key, encrypted_data):
        """创建激活记录"""
        try:
            activate_data = Activate_info(
                activate_username=info_dict.get('username'),
                activate_company=info_dict.get('company'),
                activate_nation=info_dict.get('nation'),
                activate_mobile=info_dict.get('mobile'),
                activate_province=info_dict.get('province'),
                activate_city=info_dict.get('city'),
                activate_address=info_dict.get('address'),
                activate_time=info_dict.get('time'),
                activate_key=key,
                activate_encrypted_data=encrypted_data,
                activate_status='1',
                activate_valid_until=info_dict.get('valid_until'),
            )
            db.session.add(activate_data)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"创建激活记录失败: {e}")
            return False
    
    @staticmethod
    def check_activate_key_exists(key, encrypted_data):
        """检查激活码是否已存在"""
        try:
            res = db.session.query(Activate_info).filter(
                Activate_info.activate_key == key,
                Activate_info.activate_encrypted_data == encrypted_data,
                Activate_info.activate_status == 0,
            ).first()
            return res is not None
        except Exception as e:
            print(f"检查激活码失败: {e}")
            return False
    
    @staticmethod
    def get_all_activate_records():
        """获取所有激活记录"""
        try:
            res = db.session.query(Activate_info).all()
            return res
        except Exception as e:
            print(f"获取激活记录失败: {e}")
            return []
    
    @staticmethod
    def get_valid_activate_records():
        """获取有效的激活记录"""
        try:
            res = db.session.query(Activate_info).filter(Activate_info.activate_status==1).all()
            return res
        except Exception as e:
            print(f"获取有效激活记录失败: {e}")
            return []
    
    @staticmethod
    def update_activate_status(activate_id, status):
        """更新激活状态"""
        try:
            activate_record = db.session.query(Activate_info).filter(Activate_info.id == activate_id).first()
            if activate_record:
                activate_record.activate_status = status
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            print(f"更新激活状态失败: {e}")
            return False
    
    @staticmethod
    def update_algorithm_status(status):
        """更新算法状态"""
        try:
            db.session.query(Algorithm_config).update({"status": status})
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"更新算法状态失败: {e}")
            return False
    
    @staticmethod
    def save_ak_file(ak_file_content, file_save_path, file_name):
        """保存ak文件"""
        try:
            # 确保目录存在
            os.makedirs(file_save_path, exist_ok=True)
            # 拼接完整的文件保存路径
            file_path = os.path.join(file_save_path, file_name)
            # 写入文件
            with open(file_path, "w", encoding='utf-8') as file:
                file.write(ak_file_content)
            return file_path
        except Exception as e:
            print(f"保存ak文件失败: {e}")
            return None
    
    @staticmethod
    def save_uploaded_file(file, save_path):
        """保存上传的文件"""
        try:
            # 确保目录存在
            os.makedirs(save_path, exist_ok=True)
            # 拼接文件保存路径
            file_path = os.path.join(save_path, file.filename)
            # 保存文件
            file.save(file_path)
            return file_path
        except Exception as e:
            print(f"保存上传文件失败: {e}")
            return None
    
    @staticmethod
    def extract_activation_key(file_path):
        """从文件中提取激活密钥"""
        def clean_text(text):
            # 使用正则表达式去除上下的两条线和换行符
            cleaned_text = re.sub(r'^\s*-+\s*|\s*-+\s*$', '', text, flags=re.MULTILINE)
            return cleaned_text.strip()

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            # 使用正则表达式提取 BEGIN BLOCK 和 END BLOCK 之间的内容
            match = re.search(
                r'BEGIN BLOCK\s*(.*?)\s* END BLOCK',
                content, re.DOTALL)
            match_key = re.search(
                r'BEGIN BLOCK KEY\s*(.*?)\s* END BLOCK KEY',
                content, re.DOTALL)
            if match:
                activation_key = match.group(1).strip()
                activation_key_key = match_key.group(1).strip()
                return clean_text(activation_key), clean_text(activation_key_key)
            else:
                return None, None
        except Exception as e:
            print(f"提取激活密钥失败: {e}")
            return None, None
