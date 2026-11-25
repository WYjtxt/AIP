# native-diagnosis-bounded-probe-v1
# 添加当前目录和项目根目录到Python路径
import sys
import os

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value


# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录
project_root = os.path.dirname(current_dir)

# 添加目录到Python路径
sys.path.append(current_dir)
sys.path.append(project_root)

import video_avg_brightness_gaussian
import video_clearness_detect_ssim
import video_scene_change_detected_init
import video_stripe_interference_fft
import video_color_cast
import video_contrast_anomaly
import video_frame_loss
import video_freeze
import video_occlusion
import video_horizontal_stripes_detect_fdm
import video_horizontal_waves_detect
import video_jitter_lucas
import video_scroll_interference_fdm_sd
import video_noise
import video_glitch_frame_detection
from datetime import datetime
import paramiko
import cv2
import os
import subprocess
import ffmpeg
import time

# 延迟导入Flask应用，避免循环导入
app = None

def get_app():
    """
    延迟导入Flask应用
    """
    global app
    if app is None:
        from main import app
    return app

# 导入数据库相关模块
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from model.algorithm import Diagnosis_type

# 配置FFmpeg参数，确保所有VideoCapture对象都能使用相同的设置
os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|probesize;1048576"  # SITE_PATCH_VQD_HEVC_V1

# 视频质量诊断系统
class VQD:
    """
    视频质量诊断系统, 用于检测视频质量异常, 并将检测结果插入数据库
    """
    # 初始化
    def __init__(self, data1, data2, sftp_path, sftp_server, sftp_port, sftp_username, sftp_password):
        """
        初始化视频质量诊断系统
        :param data1: 视频流数据
        :param data2: 诊断项及阈值数据
        :param sftp_path: SFTP服务器路径
        :param sftp_server: SFTP服务器地址
        :param sftp_port: SFTP服务器端口
        :param sftp_username: SFTP服务器用户名
        :param sftp_password: SFTP服务器密码
        """
        self.data1 = data1                                                          # 视频流数据
        self.data2 = data2                                                          # 视频流数据
        self.warn_threshold = None                                                  # 报警阈值
        self.prewarn_threshold = None                                               # 预警阈值
        self.brightness_detection = video_avg_brightness_gaussian                         # 亮度异常检测
        self.clearness_detection = video_clearness_detect_ssim                            # 清晰度异常检测
        self.scene_change_detection = video_scene_change_detected_init                    # 场景变化检测
        self.stripe_interference_detection = video_stripe_interference_fft                # 条纹干扰检测
        self.color_cast_detection = video_color_cast                                # 偏色检测
        self.contrast_anomaly_detection = video_contrast_anomaly                    # 对比度异常检测
        self.frame_loss_detection = video_frame_loss                                # 视频丢失检测
        self.freeze_detection = video_freeze                                        # 视频冻结检测
        self.occlusion_detection = video_occlusion                                  # 视频遮挡检测
        self.horizontal_stripes_detection = video_horizontal_stripes_detect_fdm     # 横波干扰检测
        self.horizontal_waves_detection = video_horizontal_waves_detect             # 横纹干扰检测
        self.jitter_detection = video_jitter_lucas                                  # 抖动检测
        self.scroll_interference_detection = video_scroll_interference_fdm_sd       # 滚动干扰检测
        self.noise_detection = video_noise                                          # 噪声检测
        self.glitch_detection = video_glitch_frame_detection                              # 花帧检测
        self.sftp_path = sftp_path                                                  # SFTP服务器路径
        self.sftp_server = sftp_server                                              # SFTP服务器地址
        self.sftp_port = sftp_port                                                  # SFTP服务器端口
        self.sftp_username = sftp_username                                          # SFTP服务器用户名
        self.sftp_password = sftp_password                                          # SFTP服务器密码

    @staticmethod
    def sftp_upload(local_path, filename, sftp_path, sftp_server, sftp_port, sftp_username, sftp_password):
        """
        上传文件到SFTP服务器
        :param local_path: 本地文件路径
        :param filename: 文件名
        """
        # 创建一个SSH客户端对象
        port = 9001
        ssh = paramiko.SSHClient()
        sftp = None
        try:
            # 允许连接到不在know_hosts文件中的主机（谨慎使用，因为这可能会使你的连接容易受到中间人攻击）
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 连接到SFTP服务器
            ssh.connect(hostname=sftp_server, port=sftp_port, username=sftp_username, password=sftp_password)
            # print('连接到SFTP服务器成功')
            # 使用SSH客户端创建一个SFTP客户端对象
            sftp = ssh.open_sftp()
            remote_folder_1st_level = os.path.dirname(sftp_path)
            try:
                # 创建文件夹
                sftp.mkdir(remote_folder_1st_level)
            except Exception as e2:
                print(f"目录已经存在，无需再次创建，{e2}!")
                pass
            # 将本地图像文件写入到SFTP服务器
            file_name = os.path.join(sftp_path, filename)
            with sftp.file(file_name, 'wb') as f:
                _,img_data = cv2.imencode('.jpg', cv2.imread(local_path))
                f.write(img_data.tobytes())     # 将图像数据写入到SFTP服务器
            # print('上传文件成功')
            time.sleep(5)
            if os.path.exists(local_path):
                os.remove(local_path)   # 删除本地文件
            return f"http://{sftp_server}:{port}{file_name}"
        except Exception as e:
            print(f"上传文件失败：{e}")
            return ''
        finally:
            # 确保关闭SFTP和SSH连接
            if sftp:
                try:
                    sftp.close()
                except:
                    pass
            try:
                ssh.close()
            except:
                pass

    @staticmethod
    def capture_single_frame(video_stream_url, local_file):
        """
        捕获单帧图像并保存到本地
        :param video_stream_url: 视频流地址
        :param local_file: 本地文件路径
        """
        # 尝试连接摄像头（最多重试3次）
        max_retries = 3
        cap = None
        try:
            for _ in range(max_retries):
                cap = cv2.VideoCapture(video_stream_url, cv2.CAP_FFMPEG)
                if cap.isOpened():
                    break
                print("连接失败，重试中...")
                time.sleep(2)
            else:
                print("无法连接摄像头，请检查URL或网络")
                return False
            # 设置缓冲区大小
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # 等待摄像头初始化
            time.sleep(3)  # 至少 1 秒
            # 清空缓冲区（丢弃旧帧）
            for _ in range(5):  # 读取并丢弃前 5 帧
                cap.read()
            # 读取一帧
            ret, frame = cap.read()
            if not ret:
                print("获取帧失败")
                return False
            # 保存图像
            if ret and frame is not None and frame.size > 0:
                if len(frame.shape) == 3 and frame.shape[2] == 3:  # 确认是 3 通道 BGR 图像
                    cv2.imwrite(local_file, frame)
                else:
                    print("错误：图像通道异常")
                    return False
            else:
                print("错误：帧数据无效")
                return False
            print(f"保存成功: {local_file}")
            return True
        except Exception as e:
            print(f"捕获帧失败：{e}")
            return False
        finally:
            # 确保释放资源
            if cap:
                try:
                    cap.release()
                except:
                    pass

    # 视频质量诊断
    def detection(self):
        from service.vqd_diagnosis import diagnose
        return diagnose(self)

    # 调用检测函数
    @staticmethod
    def get_video_stream_data():
        try:
            from data.vqd_source_data import video_stream_data
            with get_app().app_context():
                return video_stream_data()
        except Exception as error:
            print("获取视频流数据失败: {}".format(type(error).__name__))
            return []

    @staticmethod
    def get_diagnosis_thresholds():
        """
        从数据库获取诊断阈值数据
        """
        try:
            print("开始从数据库获取诊断阈值数据...")
            # 获取Flask应用对象
            app = get_app()
            # 创建应用程序上下文
            with app.app_context():
                # 查询所有诊断类型及其阈值
                diagnosis_types = db.session.query(Diagnosis_type).all()
                
                print(f"查询到 {len(diagnosis_types)} 个诊断类型")
                
                data2 = []
                for diagnosis_type in diagnosis_types:
                    # 构建诊断阈值数据
                    threshold_data = {
                        "id": diagnosis_type.id,
                        "name": diagnosis_type.name,
                        "prewarn_threshold": diagnosis_type.prewarn,
                        "warn_threshold": diagnosis_type.warn
                    }
                    data2.append(threshold_data)
                    print(f"诊断类型 {diagnosis_type.name}：预警阈值={diagnosis_type.prewarn}，报警阈值={diagnosis_type.warn}")
                
                # 如果数据库中没有数据，返回默认值
                if not data2:
                    print("数据库中没有诊断阈值数据，使用默认值")
                    data2 = [
                        {"id": 1, "name": "视频抖动", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 2, "name": "条纹干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 3, "name": "视频丢失", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 4, "name": "视频遮挡", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 5, "name": "视频冻结", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 6, "name": "高亮度", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 7, "name": "低亮度", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 8, "name": "视频噪声", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 9, "name": "偏色", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 10, "name": "清晰度", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 11, "name": "场景变化", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 12, "name": "对比度", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 13, "name": "横纹干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 14, "name": "滚动干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 15, "name": "横波干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                        {"id": 16, "name": "花帧检测", "prewarn_threshold": "1", "warn_threshold": "10"}
                    ]
                
                print(f"成功获取 {len(data2)} 个诊断阈值数据")
                return data2
        except Exception as e:
            print(f"获取诊断阈值数据失败：{e}")
            import traceback
            traceback.print_exc()
            # 返回默认值
            print("使用默认诊断阈值数据")
            return [
                {"id": 1, "name": "视频抖动", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 2, "name": "条纹干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 3, "name": "视频丢失", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 4, "name": "视频遮挡", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 5, "name": "视频冻结", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 6, "name": "高亮度", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 7, "name": "低亮度", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 8, "name": "视频噪声", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 9, "name": "偏色", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 10, "name": "清晰度", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 11, "name": "场景变化", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 12, "name": "对比度", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 13, "name": "横纹干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 14, "name": "滚动干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 15, "name": "横波干扰", "prewarn_threshold": "30", "warn_threshold": "70"},
                {"id": 16, "name": "花帧检测", "prewarn_threshold": "1", "warn_threshold": "10"}
            ]

    @staticmethod
    def run(data1=None, data2=None, sftp_path=None, sftp_server=None, sftp_port=None, sftp_username=None, sftp_password=None):
        """
        调用检测函数
        """
        # 如果没有提供数据，从数据库获取
        if data1 is None:
            data1 = VQD.get_video_stream_data()
        else:
            from data.vqd_source_data import refresh_video_sources
            with get_app().app_context():
                refresh_video_sources(data1)
        if data2 is None:
            data2 = VQD.get_diagnosis_thresholds()
        
        # 设置默认SFTP参数
        if sftp_path is None:
            sftp_path = "/data/AIGO/platform_start/vqd_data/"
        if sftp_server is None:
            sftp_server = '192.168.7.51'
        if sftp_port is None:
            sftp_port = 22
        if sftp_username is None:
            sftp_username = 'root'
        if sftp_password is None:
            sftp_password = _required_site_value("AIP_VQD_SFTP_PASSWORD")
        
        vqd = VQD(data1, data2, sftp_path, sftp_server, sftp_port, sftp_username, sftp_password)  # 创建对象，参数为视频名称
        res = vqd.detection()  # 调用检测函数
        print("诊断完成！")
        return res

if __name__ == "__main__":
    print("=====================================")
    print("开始执行视频质量诊断")
    print("=====================================")
    
    # 直接调用run方法，不提供data1和data2，让其自动从数据库获取
    sftp_path = "/data/AIGO/platform_start/vqd_data/"
    sftp_server = '192.168.7.51'
    sftp_port = 22
    sftp_username = 'root'
    sftp_password = _required_site_value("AIP_VQD_SFTP_PASSWORD")
    
    print(f"SFTP服务器配置：")
    print(f"  路径: {sftp_path}")
    print(f"  服务器: {sftp_server}")
    print(f"  端口: {sftp_port}")
    print(f"  用户名: {sftp_username}")
    print("  密码: ******")
    
    print("\n开始从数据库获取数据...")
    
    # 从数据库获取数据并执行诊断
    res = VQD.run(sftp_path=sftp_path, sftp_server=sftp_server, sftp_port=sftp_port, 
                 sftp_username=sftp_username, sftp_password=sftp_password)
    
    print("\n=====================================")
    print("诊断完成！")
    print(f"诊断结果数量: {len(res)}")
    print("=====================================")
    print(res)
    # print(datetime.now())
