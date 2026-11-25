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


class Zlk_data(db.Model):
    __tablename__ = 't_zlk_data'  # 表名
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': '用于存储 ZLK 视频资源表'  # 表注释
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键，自增，用于唯一标识每条记录')
    cameras_name = db.Column(db.String(50), comment='监控点名称，例如摄像头或视频流的名称，最长100个字符')
    cameras_rtsp = db.Column(db.String(255), comment='监控点rtsp流')
    zlk_app = db.Column(db.String(100), comment='ZLK-app地址')
    zlk_live = db.Column(db.String(100), comment='ZLK-live地址')
    zlk_key = db.Column(db.Text, comment='用于删除该流的键')
    # 新增字段：存储关联设备的IP地址
    equipment_ip = db.Column(db.String(32), comment='关联设备的IP地址，同步自t_equipment表的equipment_ip')
    equipment_id = db.Column(db.String(32), comment='关联设备的唯一ID值，同步自t_equipment表的id')

    zlk_hls = db.Column(db.String(255), comment='ZLK-hls播放地址')
    zlk_hls_fmp4 = db.Column(db.String(255), comment='ZLK-hls-fmp4播放地址')
    zlk_mp4 = db.Column(db.String(255), comment='ZLK-mp4播放地址')
    zlk_rtmp = db.Column(db.String(255), comment='ZLK-rtmp播放地址')
    zlk_rtsp = db.Column(db.String(255), comment='ZLK-rtsp播放地址')
    zlk_ts = db.Column(db.String(255), comment='ZLK-ts播放地址')
    zlk_flv = db.Column(db.String(255), comment='ZLK-flv播放地址')

    create_date = db.Column(db.DateTime, default=datetime.utcnow, comment='记录创建时间，默认是当前时间（UTC）')
    update_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='记录更新时间，默认是当前时间（UTC）')

    # 双向关系映射：与Equipment.zlk_data绑定，实现反向查询（无外键，仅模型层关联）
    equipment = db.relationship(
        'Equipment',
        back_populates='zlk_data',
        lazy='joined',
        uselist=False  # 明确一对一，一个ZLK数据仅对应一个设备
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cameras_name': self.cameras_name,
            'cameras_rtsp': self.cameras_rtsp,
            'equipment_ip': self.equipment_ip,  # 新增字段返回
            'zlk_app': self.zlk_app,
            'zlk_live': self.zlk_live,
            'zlk_key': self.zlk_key,
            'zlk_hls': self.zlk_hls,
            'zlk_hls_fmp4': self.zlk_hls_fmp4,
            'zlk_mp4': self.zlk_mp4,
            'zlk_rtmp': self.zlk_rtmp,
            'zlk_rtsp': self.zlk_rtsp,
            'zlk_ts': self.zlk_ts,
            'zlk_flv': self.zlk_flv,
            'create_date': self.create_date.isoformat() if self.create_date else None,
            'update_date': self.update_date.isoformat() if self.update_date else None,
            # 反向获取设备信息（无需存储equipment_id，通过关系映射即可获取）
            'related_equipment_id': self.equipment.id if self.equipment else None,
            'related_equipment_name': self.equipment.equipment_name if self.equipment else None
        }

class Uwb_data(db.Model):
    """定时删除已删除的算法id对应报警结果"""
    __tablename__ = 't_uwb_data'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'comment': 'uwb_id人名对照表'
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uwb_id = db.Column(db.String(50),comment='uwb_id')
    uwb_name = db.Column(db.String(50),comment='人名')