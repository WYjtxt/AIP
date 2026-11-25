from data.log_data import LogData
from config.configs import format_datetime


class LogService:
    """
    日志服务层，处理日志相关的业务逻辑
    """

    @staticmethod
    def get_log_data(page, per_page, level=None):
        """
        获取日志数据，支持分页和筛选

        Args:
            page (int): 当前页码
            per_page (int): 每页显示条目数量
            level (str, optional): 日志等级. Defaults to None.

        Returns:
            tuple: (success, result)，success 为布尔值，result 为数据或错误信息
        """
        try:
            # 调用数据层方法获取日志数据
            pagination = LogData.get_logs(page, per_page, level)
            if not pagination:
                return False, '获取日志数据失败'

            # 处理分页后的数据
            data_list = [
                {
                    'id': item.id,
                    'user_id': item.user_name,
                    'ip_address': item.ip_address,
                    'level': item.level,
                    'message': item.message,
                    'module': item.module,
                    'method': item.method,
                    'url': item.url,
                    'request_data': item.request_data if item.response_data else item.stack_trace,
                    'response_data': item.response_data,
                    'error_code': item.error_code,
                    'hostname': item.hostname,
                    'context': item.context,
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
            print(f"获取日志数据失败: {e}")
            return False, str(e)
