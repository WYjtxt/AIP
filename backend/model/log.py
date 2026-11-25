from data.exts import db
from sqlalchemy import Index, Column, Integer, String, ForeignKey,event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship,validates
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from flask import request, g
import pytz
import traceback
import socket
import json
from model.admin import TimestampMixin


local_tz = pytz.timezone('Asia/Shanghai')

# 日志表
class Log(db.Model,TimestampMixin):
    """日志表"""
    __tablename__ = 't_logs'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '日志表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True,comment='id')
    user_id = db.Column(db.Integer,comment='用户ID')  # 用户ID
    user_name = db.Column(db.String(100),comment='用户名称')  # 用户名称
    ip_address = db.Column(db.String(50),comment='ip地址')  # ip地址
    level = db.Column(db.String(50),comment='日志级别')  # 日志级别
    message = db.Column(db.Text,comment='日志内容')  # 日志内容
    module = db.Column(db.String(100),comment='模块名称')  # 模块名称
    method = db.Column(db.String(50),comment='方法名称')  # 方法名称
    url = db.Column(db.String(255),comment='请求的URL')  # 请求的URL
    request_data = db.Column(db.Text,comment='请求数据')  # 请求数据
    response_data = db.Column(db.Text,comment='响应数据')  # 响应数据
    error_code = db.Column(db.String(50),comment='错误代码')  # 错误代码
    stack_trace = db.Column(db.Text,comment='堆栈追踪')  # 堆栈追踪
    hostname = db.Column(db.String(100),comment='服务器主机名')  # 服务器主机名
    context = db.Column(db.String(255),comment='上下文信息')  # 上下文信息

    def __repr__(self):
        return f"<ErrorLog(id={self.id}, ip_address={self.ip_address}, level={self.level}, message={self.message})>"

    # db.session 进行数据提交等操作
    @staticmethod
    def log_message(session, exception=None, user_id=None,user_name=None,error_code=None,level=None, message=None, **kwargs):
        try:
            # 获取请求数据
            request_data=''
            if request.method == 'GET':
                request_data = str(dict(request.args))  # 直接获取查询参数
            elif request.method == 'POST':
                if request.is_json:
                    request_data = str(request.get_json())  # 获取 JSON 数据
                else:
                    request_data = str(request.form)  # 获取表单数据

            # 获取请求的其他信息
            ip_address = request.remote_addr  # 获取客户端IP地址
            url = request.url  # 获取请求的URL
            response_data = str(kwargs.get('response_data', ''))  # 获取响应数据
            stack_trace = traceback.format_exc() if exception else ""  # 获取堆栈追踪
            hostname = socket.gethostname()  # 获取服务器主机名
            context = kwargs.get('context', 'Production')  # 上下文（默认生产环境）

            if not message:
                message = str(exception) if exception else "Unknown error"

            # 检查错误响应数据并跳过日志记录
            try:
                # 将响应数据从字符串转换为字典
                response_dict = json.loads(response_data)
                if isinstance(response_dict, dict) and response_dict.get("message") == "内部服务器错误":
                    return  # 跳过日志记录
            except json.JSONDecodeError:
                # 如果无法解析 JSON，则跳过判断
                pass
            # print(user_id)
            # 创建并保存日志条目
            log = Log(
                user_id=user_id if user_id else 0,
                user_name=user_name if user_name else 0,
                level=level,
                message=message,
                ip_address=ip_address,
                url=url,
                request_data=request_data,
                response_data=response_data,
                stack_trace=stack_trace,
                hostname=hostname,
                context=context,
                method=request.method,
                module=request.blueprint,
                error_code=error_code,
            )

            # 保存日志条目
            db.session.add(log)
            db.session.commit()

        except Exception as e:
            print(e)
            pass


# 算法日志表
class Alg_logs(db.Model,TimestampMixin):
    """算法日志表"""
    __tablename__ = 't_alg_logs'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '算法日志表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True,comment='id')
    ip_address = db.Column(db.String(50),comment='ip地址')  # 盒子ip地址
    level = db.Column(db.String(50),comment='日志级别  INFO  ERROR ')  # 日志级别
    message = db.Column(db.Text,comment='日志内容')  # 日志内容
    alg_name = db.Column(db.String(100),comment='算法配置名称')  # 算法配置名称
    response_data = db.Column(db.Text,comment='响应数据')  # 响应数据
    error_code = db.Column(db.String(50),comment='错误代码')  # 错误代码
    hostname = db.Column(db.String(100),comment='服务器主机名')  # 服务器主机名



# 登录日志表
class Platform_login(db.Model, TimestampMixin):
    """登录日志表"""
    __tablename__ = 't_platform_login'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '平台用户登录日志记录表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键 ID')
    user_id = db.Column(db.Integer, comment='用户 ID')
    user_name = db.Column(db.String(100), comment='用户名称')
    ip_address = db.Column(db.String(50), comment='登录 IP 地址')
    response_data = db.Column(db.Text, comment='响应数据（如 token、返回内容）')
    hostname = db.Column(db.String(100), comment='服务器主机名')
    user_agent = db.Column(db.String(255), comment='客户端 User-Agent 信息')
    location = db.Column(db.String(100), comment='登录地点（IP归属地或定位）')

    status = db.Column(db.String(20), default='成功', comment='登录状态：成功/失败/异常')
    login_status = db.Column(db.String(20),comment='登录/退出')
    error_message = db.Column(db.Text, comment='失败时的错误信息，成功则为空')

from sqlalchemy import event
# Bound diagnostic payloads regardless of the endpoint that creates the row.
# Database log retention is applied separately, in small transactions.
from common.log_payload import limit_log_payload
for _log_model in (Log, Alg_logs, Platform_login):
    event.listen(_log_model, 'before_insert', limit_log_payload)
    event.listen(_log_model, 'before_update', limit_log_payload)
