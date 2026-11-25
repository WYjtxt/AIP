import requests
import json
from datetime import datetime
import time

def sync_model_status_to_main_system(conf_id, conf_name, model_status, equipment_ip):
    """
    同步模型状态到主系统
    
    Args:
        conf_id:摄像头算法配置ID
        conf_name: 摄像头端的算法配置名称
        model_status: 模型状态 (1运行/2停止/3异常/4等待)
        equipment_ip: 设备IP地址
    
    Returns:
        dict: 响应结果
    """
    
    # 主系统地址（根据实际情况修改）
    main_system_url = "http://127.0.0.1:5000/ai_camera_view/model_status_callback"
    
    # 构建请求数据
    payload = {
        'conf_id': conf_id,     
        'conf_name': conf_name,
        'model_status': model_status,
        'equipment_ip': equipment_ip
    }
    # print(f"payload:{payload}")
    time.sleep(1)
    try:
        print(time.time())
        response = requests.post(
            main_system_url,
            json=payload,
            timeout=5,
            headers={'Content-Type': 'application/json'}
        )
        
        result = response.json()
        
        if result.get('code') == 200:
            print(f"[{datetime.now()}] 状态同步成功: conf_id={conf_id}, conf_name={conf_name}, status={model_status}")
            return {'success': True, 'data': result}
        else:
            print(f"[{datetime.now()}] 状态同步失败: {result.get('msg')}")
            return {'success': False, 'error': result.get('msg')}
            
    except requests.exceptions.Timeout:
        print(f"[{datetime.now()}] 请求超时，主系统可能无响应")
        return {'success': False, 'error': '请求超时'}
    except requests.exceptions.ConnectionError:
        print(f"[{datetime.now()}] 连接失败，请检查主系统地址和网络")
        return {'success': False, 'error': '连接失败'}
    except Exception as e:
        print(f"[{datetime.now()}] 同步异常: {str(e)}")
        return {'success': False, 'error': str(e)}