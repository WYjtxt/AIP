"""Original production imports, separate from application creation."""
import requests
import time
import threading
import redis
import logging
import concurrent.futures
import qrcode
from datetime import datetime, timedelta

from apps.ai_camera_view import ai_camera_view
from data.exts import db
from config.configs import *
from flask_cors import CORS
from flask import Response, jsonify, Flask, redirect, url_for, request,\
    flash, session, make_response,render_template,has_request_context,send_file
from flask_sqlalchemy import SQLAlchemy
from concurrent.futures import ThreadPoolExecutor, as_completed

# 蓝图导入
from apps.user_view import user_view
from apps.commands import cli  # 预置数据导入
from apps.model_view import model_view
from apps.menu_view import menu_view
from apps.model_views import model_views
from apps.scheduler_task import scheduler_task,run_task
from apps.activate import activate
from apps.role_view import role_view
from apps.resource_view import resource_view
from apps.video_views import video_view
from apps.preview_view import preview_view
from apps.preview_compat_view import preview_compat_view
from apps.analysis_preview_view import analysis_preview_view
from apps.storage_retention_view import storage_retention_view
from common.logging_policy import configure_logging, polling_job
from apps.hik_security_platform_view import hik_security_platform_info_view
from apps.ZiguangVMSClient_view import ziguang_platform_info_view
from apps.model_template_conf_view import model_template
from apps.log_view import log_view
from apps.alg_log_view import alg_log_view
from apps.zlmediakit_view import zlmediakit_view
from tool.OpenApi_public_Class import *
from tool.OpenAPI_hs_data_Class import *
from service.scheduler_task_service import SchedulerTaskService
from service.hik_security_platform_service import HikSecurityPlatformService
from service.ZiguangVMSClient_service import ZiguangVMSService


from flask_apscheduler import APScheduler
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_session import Session
from service.equipment_model_service import delete_zlk_data_for_equipment,create_zlk_data_for_equipment

# import logging
#
# # 创建一个日志器
# logger = logging.getLogger('my_logger')
# logger.setLevel(logging.DEBUG)  # 设置日志级别
#
# # 创建一个文件处理器
# handler = logging.FileHandler('app.log')
# handler.setLevel(logging.DEBUG)
#
# # 创建一个格式器
# formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
#
# # 将格式器添加到处理器
# logger.addHandler(handler)
#

# --------建立flask实例--------
