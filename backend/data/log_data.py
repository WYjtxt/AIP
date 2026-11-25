from data.exts import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_


class LogData:
    """
    日志数据层，处理日志相关的数据库操作
    """

    @staticmethod
    def get_logs(page, per_page, level=None):
        """
        获取日志数据，支持分页和筛选

        Args:
            page (int): 当前页码
            per_page (int): 每页显示条目数量
            level (str, optional): 日志等级. Defaults to None.

        Returns:
            pagination: 分页对象
        """
        try:
            # 定义筛选列表
            filters = []
            # 当筛选条件存在时添加到列表
            if level:
                filters.append(Log.level == level)

            # 构建查询条件
            query = and_(*filters) if filters else True  # 如果 filters 为空，默认条件为 True

            # 查询主区域点并进行分页
            pagination = db.session.query(Log).filter(query).order_by(Log.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            return pagination
        except Exception as e:
            print(f"获取日志数据失败: {e}")
            return None
