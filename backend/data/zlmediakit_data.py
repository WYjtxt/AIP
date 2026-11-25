# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *

class ZLMediaKitData:
    @staticmethod
    def get_stream_by_key(stream_key):
        """
        根据流密钥查询流信息
        """
        return Zlk_data.query.filter_by(zlk_key=stream_key).first()

    @staticmethod
    def get_stream_by_id(id):
        """
        根据ID查询流信息
        """
        return Zlk_data.query.filter_by(id=id).first()

    @staticmethod
    def delete_stream(stream):
        """
        删除流记录
        """
        try:
            db.session.delete(stream)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_all_streams():
        """
        获取所有流信息
        """
        return Zlk_data.query.all()

    @staticmethod
    def get_stream_by_rtsp(rtsp):
        return Zlk_data.query.filter_by(cameras_rtsp=rtsp).first()


    @staticmethod
    def get_recoverable_streams():
        """恢复当前设备实际绑定的流，跳过历史孤立记录。"""
        bound = db.session.query(Equipment.id).filter(
            Equipment.zlk_dat_id == Zlk_data.id).exists()
        return Zlk_data.query.filter(bound).all()
