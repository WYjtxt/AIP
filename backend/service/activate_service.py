import uuid
import json
import os
from datetime import datetime
from cryptography.fernet import Fernet, InvalidToken
from data.activate_data import ActivateData
from config.configs import activate_key, key_key, FILE_SAVE_PATH, DB_HOST

class ActivateService:
    """激活服务层，处理业务逻辑"""
    
    @staticmethod
    def generate_ak_file(username, company, nation, mobile, province, city, address, time, uuid_code, valid_until):
        """生成ak激活文件"""
        try:
            # 收集所有信息到一个字典
            info = {
                'username': username,
                'company': company,
                'nation': nation,
                'mobile': mobile,
                'province': province,
                'city': city,
                'address': address,
                'time': time,
                'machine_uuid': str(uuid_code),
                'key': activate_key,
                'date_time': str(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'valid_until': str(valid_until)
            }

            # 将信息转换为JSON字符串
            info_string = json.dumps(info, sort_keys=True)
            cipher_suite = Fernet(key_key)
            key = cipher_suite.encrypt(info_string.encode())

            info_block = """--------------------------------------------------------- BEGIN Information ---------------------------------------------------------
    Software description     : 平台激活序列
    Extended description     : 序列生成
    Type                     : 激活码
--------------------------------------------------------- END Information ---------------------------------------------------------"""

            activation_block = f"""--------------------------------------------------------- BEGIN BLOCK ---------------------------------------------------------
{key.decode()}
--------------------------------------------------------- END BLOCK ---------------------------------------------------------"""

            activation_block_key = f"""--------------------------------------------------------- BEGIN BLOCK KEY ---------------------------------------------------------
{key_key.decode()}
--------------------------------------------------------- END BLOCK KEY ---------------------------------------------------------"""

            # 完整的激活文件内容
            ak_file_content = f"""---------------------------------------------------------- Activation File ---------------------------------------------------------
    #PLEASE DO NOT MODIFY THIS FILE. MAKING ANY CHANGE TO THIS FILE WILL INVALIDATE YOUR LICENSE.
    Copyright (C) 2024 Your Company Name. All rights reserved.

{info_block}

{activation_block}

{activation_block_key}
"""
            
            # 生成文件名
            ak_name = 'activation_file_{}.ak'.format(datetime.now().strftime('%Y%m%d%H%M%S'))
            
            # 保存文件
            ak_create_path = os.path.join(FILE_SAVE_PATH, 'ak_create')
            file_path = ActivateData.save_ak_file(ak_file_content, ak_create_path, ak_name)
            
            if file_path:
                # 返回文件访问URL
                file_url = 'http://{}:5000/static/ak_create/{}'.format(DB_HOST, ak_name)
                return True, file_url
            else:
                return False, '文件生成失败'
                
        except Exception as e:
            print(f"生成ak文件失败: {e}")
            return False, str(e)
    
    @staticmethod
    def validate_ak_file(file):
        """验证ak激活文件"""
        try:
            # 保存上传的文件
            ak_activate_path = os.path.join(FILE_SAVE_PATH, 'ak_activate')
            file_path = ActivateData.save_uploaded_file(file, ak_activate_path)
            
            if not file_path:
                return False, '文件保存失败'
            
            # 提取密钥和加密数据
            activation_key, activation_key_key = ActivateData.extract_activation_key(file_path)
            
            if not activation_key or not activation_key_key:
                return False, '文件中没有找到激活码'
            
            # 进行编码处理
            key = activation_key_key.encode()
            encrypted_data = activation_key.encode()
            
            # 解密
            cipher_suite = Fernet(key)
            decrypted_info = cipher_suite.decrypt(encrypted_data).decode()
            
            # 将解密后的 JSON 字符串转换为字典
            info_dict = json.loads(decrypted_info)
            
            if not info_dict.get('valid_until'):
                return False, 'ak导入校验错误,请导入正确ak激活序列文件!'

            # 对秘钥进行比对
            if info_dict.get('key') != activate_key:
                return False, 'ak导入校验错误,请导入正确ak激活序列文件!'

            # 这里应该调用获取机器UUID的函数
            # if info_dict.get('machine_uuid') != get_machine_uuid():
            #     return False, 'ak导入校验错误，机器编码对比错误!'

            # 判断key跟激活码是否存在
            if ActivateData.check_activate_key_exists(key, encrypted_data):
                return False, '该激活码已经使用，请重新获取激活码!'

            # 创建激活记录
            if not ActivateData.create_activate_record(info_dict, key, encrypted_data):
                return False, '激活记录创建失败'
            
            return True, '系统激活成功！'
            
        except FileNotFoundError:
            return False, 'ak导入校验错误,请导入正确ak激活序列文件!'
        except InvalidToken:
            return False, 'ak导入校验错误,请导入正确ak激活序列文件!'
        except json.JSONDecodeError:
            return False, 'ak导入校验错误,请导入正确ak激活序列文件!'
        except Exception as e:
            print(f"验证ak文件失败: {e}")
            return False, 'ak导入校验错误,请导入正确ak激活序列文件!'
    
    @staticmethod
    def verify_activation_status():
        """验证激活状态"""
        try:
            # 获取激活码序列数据及对应状态确认系统
            res = ActivateData.get_valid_activate_records()
            
            # 标记是否有有效的激活记录
            valid_activation_found = False
            
            if not res:
                return False, '该系统尚未激活！请登录运管中心授权！'
            else:
                for i in res:
                    current_time = datetime.now()
                    valid_until = datetime.strptime(i.activate_valid_until, '%Y-%m-%d')
                    if valid_until:
                        if current_time > valid_until:
                            # 更新激活状态为过期
                            ActivateData.update_activate_status(i.id, 0)
                            # 更新算法状态为停止
                            ActivateData.update_algorithm_status(2)
                        else:
                            valid_activation_found = True
                
                if valid_activation_found:
                    return True, '系统已激活！'
                else:
                    return False, '系统激活序列已过期！！'
                    
        except Exception as e:
            print(f"验证激活状态失败: {e}")
            return False, '验证激活状态失败'
    
    @staticmethod
    def get_activate_info():
        """获取激活序列内容"""
        try:
            res = ActivateData.get_all_activate_records()
            # 转换为字典列表
            data = []
            for item in res:
                data.append({
                    'id': item.id,
                    'activate_username': item.activate_username,
                    'activate_company': item.activate_company,
                    'activate_nation': item.activate_nation,
                    'activate_mobile': item.activate_mobile,
                    'activate_province': item.activate_province,
                    'activate_city': item.activate_city,
                    'activate_address': item.activate_address,
                    'activate_time': item.activate_time,
                    'activate_key': item.activate_key,
                    'activate_encrypted_data': item.activate_encrypted_data,
                    'activate_status': item.activate_status,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                    'activate_valid_until': item.activate_valid_until
                })
            return True, data
            
        except Exception as e:
            print(f"获取激活信息失败: {e}")
            return False, []
