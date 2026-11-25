from data.alg_log_data import AlgLogData
from config.configs import format_datetime

class AlgLogService:
    """算法日志服务层，处理业务逻辑"""
    
    @staticmethod
    def get_alg_log_data(page, per_page, level=None, alg_name=None):
        """获取算法日志数据"""
        try:
            # 调用数据层获取算法日志
            pagination = AlgLogData.get_alg_logs(page, per_page, level, alg_name)
            
            if not pagination:
                return False, '获取算法日志失败'
            
            # 格式化数据
            data_list = [
                {
                    'id': item.id,
                    'ip_address': item.ip_address,
                    'level': item.level,
                    'message': item.message,
                    'alg_name': item.alg_name,
                    'response_data': item.response_data,
                    'error_code': item.error_code,
                    'hostname': item.hostname,
                    'created_at': format_datetime(item.created_at),
                }
                for item in pagination.items
            ]
            
            # 构造返回结果，包括分页信息
            response = {
                'code': 200,
                'data': data_list,
                'pagination': {
                    'current_page': pagination.page,
                    'total_pages': pagination.pages,
                    'total_items': pagination.total,
                    'per_page': pagination.per_page
                }
            }
            
            return True, response
        except Exception as e:
            print(f"获取算法日志数据失败: {e}")
            return False, str(e)
    
    @staticmethod
    def get_platform_login_data(page, per_page, status=None):
        """获取平台登录日志数据"""
        try:
            # 调用数据层获取平台登录日志
            pagination = AlgLogData.get_platform_login_logs(page, per_page, status)
            
            if not pagination:
                return False, '获取平台登录日志失败'
            
            # 格式化数据
            data_list = [
                {
                    'id': item.id,
                    'user_id': item.user_id,
                    'user_name': item.user_name,
                    'ip_address': item.ip_address,
                    'response_data': item.response_data,
                    'hostname': item.hostname,
                    'user_agent': item.user_agent,
                    'status': item.status,
                    'login_status': item.login_status,
                    'created_at': format_datetime(item.created_at),
                }
                for item in pagination.items
            ]
            
            # 构造返回结果，包括分页信息
            response = {
                'code': 200,
                'data': data_list,
                'pagination': {
                    'current_page': pagination.page,
                    'total_pages': pagination.pages,
                    'total_items': pagination.total,
                    'per_page': pagination.per_page
                }
            }
            
            return True, response
        except Exception as e:
            print(f"获取平台登录日志数据失败: {e}")
            return False, str(e)
