from data.exts import db
# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_

class AlgLogData:
    """算法日志数据层，处理数据库操作"""
    
    @staticmethod
    def get_alg_logs(page, per_page, level=None, alg_name=None):
        """获取算法日志，支持分页和筛选"""
        try:
            # 定义筛选列表
            filters = []
            # 当筛选条件存在时添加到列表
            if level:
                filters.append(Alg_logs.level == level)
            if alg_name:
                filters.append(Alg_logs.alg_name.like(f"%{alg_name}%"))  # 模糊匹配

            # 构建查询条件
            query = and_(*filters) if filters else True

            # 查询并进行分页
            pagination = db.session.query(Alg_logs).filter(query).order_by(Alg_logs.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            return pagination
        except Exception as e:
            print(f"获取算法日志失败: {e}")
            return None
    
    @staticmethod
    def get_platform_login_logs(page, per_page, status=None):
        """获取平台登录日志，支持分页和筛选"""
        try:
            # 定义筛选列表
            filters = []
            # 当筛选条件存在时添加到列表
            if status:
                filters.append(Platform_login.status == status)

            # 构建查询条件
            query = and_(*filters) if filters else True

            # 查询并进行分页
            pagination = db.session.query(Platform_login).filter(query).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            return pagination
        except Exception as e:
            print(f"获取平台登录日志失败: {e}")
            return None
