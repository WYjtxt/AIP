import configparser
import os

# 配置信息
cf = configparser.ConfigParser()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE_DIR, "ApiConfig.ini")
cf.read(path, encoding='utf-8')  # 读取ApiConfig.ini配置文件


# 数据库信息（MySQL 8.0）
db_host = cf.get("ipconfig", "db_host")  # 获取[ipconfig]中db_host对应的值
db_port = cf.get("ipconfig", "db_port")  # 获取[ipconfig]中db_port对应的值
db_user = cf.get("ipconfig", "db_user")  # 获取[ipconfig]中db_user对应的值
db_password = cf.get("ipconfig", "db_password")  # 获取[ipconfig]中db_password对应的值
db_name = cf.get("ipconfig", "db_name")  # 获取[ipconfig]中db_name对应的值

# kafka信息
kafka_ip = cf.get("ipconfig", "kafka_ip")  # 获取[ipconfig]中ip对应的值
kafka_port = cf.get("ipconfig", "kafka_port")  # 获取[ipconfig]中port对应的值

# 上传信息
upload_ip = cf.get("ipconfig", "upload_ip")  # 获取[ipconfig]中ip对应的值
upload_port = cf.get("ipconfig", "upload_port")  # 获取[ipconfig]中port对应的值

#本机信息
localhost_ip = cf.get("ipconfig", "localhost_ip") #获取本地IP地址

# 推流服务器（AI 标注输出流推向此机的 ZLMediaKit）；缺省回退平台服务器 172.16.129.236
stream_push_ip = cf.get("ipconfig", "stream_push_ip", fallback="172.16.129.236")

computing_id = cf.getint("ipconfig", "computing_id", fallback=1)
