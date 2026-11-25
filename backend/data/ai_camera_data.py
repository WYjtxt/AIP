import numpy as np
from model.ai_camera import Aicam_image_calibration
from data.exts import db


class AiCameraCalibrationData:
    """AI摄像头标定数据操作类"""

    @staticmethod
    def check_calibration_points_valid(points1, points2):
        """
        校验标定点位数据是否有效

        :param points1: 摄像头1的点位列表 [{"x": 783, "y": 379}, ...]
        :param points2: 摄像头2的点位列表 [{"x": 1173, "y": 949}, ...]
        :return: (is_valid, error_msg)
        """
        if not points1 or not points2:
            return False, '点位数据不能为空'

        if len(points1) != len(points2):
            return False, f'两个摄像头点数必须相同，当前摄像头1有{len(points1)}个点，摄像头2有{len(points2)}个点'

        if len(points1) < 6:
            return False, f'每个摄像头至少需要6个点位，当前只有{len(points1)}个点'

        return True, None

    @staticmethod
    def convert_points_to_numpy(points_list):
        """
        将点位列表转换为numpy数组

        :param points_list: [{"x": 783, "y": 379}, ...]
        :return: numpy array [[783, 379], ...]
        """
        return np.array([[p['x'], p['y']] for p in points_list], dtype=np.float32)

    @staticmethod
    def get_calibration_by_cameras(source_equipment_id, target_equipment_id):
        """
        根据两个摄像头ID查询标定记录

        :param source_equipment_id: 源相机ID
        :param target_equipment_id: 目标相机ID
        :return: Aicam_image_calibration对象或None
        """
        return Aicam_image_calibration.query.filter_by(
            source_equipment_id=source_equipment_id,
            target_equipment_id=target_equipment_id
        ).first()

    @staticmethod
    def create_calibration_record(source_equipment_id, target_equipment_id, homography_matrix_str, avg_test_err):
        """
        创建新的标定记录

        :param source_equipment_id: 源相机ID
        :param target_equipment_id: 目标相机ID
        :param homography_matrix_str: 单应矩阵JSON字符串
        :param avg_test_err: 平均测试误差
        :return: Aicam_image_calibration对象
        """
        new_calibration = Aicam_image_calibration(
            source_equipment_id=source_equipment_id,
            target_equipment_id=target_equipment_id,
            homography_matrix=homography_matrix_str,
            avg_test_err=avg_test_err
        )
        db.session.add(new_calibration)
        return new_calibration

    @staticmethod
    def update_calibration_record(calibration, homography_matrix_str, avg_test_err):
        """
        更新已有的标定记录

        :param calibration: Aicam_image_calibration对象
        :param homography_matrix_str: 单应矩阵JSON字符串
        :param avg_test_err: 平均测试误差
        :return: Aicam_image_calibration对象
        """
        calibration.homography_matrix = homography_matrix_str
        calibration.avg_test_err = avg_test_err
        return calibration

    @staticmethod
    def commit_session():
        """提交数据库事务"""
        db.session.commit()

    @staticmethod
    def rollback_session():
        """回滚数据库事务"""
        db.session.rollback()
