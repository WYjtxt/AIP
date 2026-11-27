import time
import configparser
import logging
from logging.handlers import TimedRotatingFileHandler
from kafka import KafkaConsumer
from kafka.structs import TopicPartition, OffsetAndMetadata
from dbutils.pooled_db import PooledDB
import json
import math
import pymysql
import os
import sys
from pathlib import Path

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value


# PLATFORM_DURABLE_ALARM_PUSH_V1
_algorithm_package = Path(__file__).resolve().parent
_push_module_dir = _algorithm_package / '_platform_push'
_push_module = _push_module_dir / 'push_outbox.py'
if _push_module_dir.is_symlink() or _push_module.is_symlink() or not _push_module.is_file():
    raise RuntimeError('Platform push outbox module has not been staged')
sys.path.insert(0, str(_push_module_dir))
os.environ.setdefault('PLATFORM_OPS_STATE_DIR', str(_algorithm_package.parent / 'platform_ops/state'))
import push_outbox
#from Conf_files import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# kafka地址
KAFKA_HOST = '127.0.0.1'


# Prefer mounted site settings while preserving the native installer and environment fallback.
_deployment_config = configparser.ConfigParser(interpolation=None)
_deployment_path = _algorithm_package.parent / 'Config_files/config.ini'
_deployment_config.read(str(_deployment_path), encoding='utf-8')
_database = _deployment_config['database'] if _deployment_config.has_section('database') else {}
DB_HOST = _database.get('DB_HOST', '127.0.0.1')
DB_user = _database.get('DB_USER', 'admin')
DB_password = '__ONECLICK_DB_PASSWORD__'
if not DB_password or DB_password == '__ONECLICK_' + 'DB_PASSWORD__':
    DB_password = _database.get('DB_PASSWORD') or _required_site_value('AIP_DB_PASSWORD')

# 设置日志：参数
"""
when='midnight' 表示每天的午夜（00:00）时，日志文件会进行切割。也就是说，每天晚上 12 点会生成一个新的日志文件。
interval=1 表示日志文件每隔 1 天切割一次
backupCount=7: 表示最多保留 7 个日志文件，超过 7 个的日志文件会被自动删除。这是用来防止日志文件过多。
"""
log_handler = TimedRotatingFileHandler(
    'app_log.log', when='midnight', interval=1, backupCount=7
)

# 设置日志格式    %(asctime)s：日志时间    %(levelname)s：日志级别（例如：INFO, ERROR） %(message)s：日志内容
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log_handler.suffix = "%Y-%m-%d.log"  # 日志文件后缀，按日期分割

# 创建控制台日志处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# 配置 logging，输出到文件和控制台
logging.basicConfig(level=logging.INFO, handlers=[log_handler, console_handler])


# 数据库连接池
pool = PooledDB(
    pymysql, maxconnections=10, host=DB_HOST, user=DB_user, password=DB_password,
    port=int(_database.get('DB_PORT', 3306)), database=_database.get('DB_NAME', 'seal_system'),
    read_timeout=30, write_timeout=30, charset='utf8mb4'
)


# 数据上传函数
def upload_data(Algorithm_conf_id, res_type, Mine_id, Equipment_id, Equipment_parent_id,
                carousel_images_list,ori_images_list, result_count, result_count_time, template_id, template_type_id, Algorithm_library_id, res_time,Entering_num,Exiting_num,all_Entering_num=None,all_Exiting_num=None,
                algorithm_name = None, conf_name = None,conf_img_resolution = None, equipment_type = None, equipment_name = None,mine_name = None,warning_message =  None,warning_video = None,analysis_type = None,analysis_case =None, event_key=None, count_state_managed=False):
    conn = pool.connection()
    try:
        with conn.cursor() as cursor:

            if event_key is not None:
                cursor.execute("INSERT IGNORE INTO t_platform_push_ingest (event_key) VALUES (%s)", (event_key,))
                if cursor.rowcount == 0:
                    conn.rollback()
                    return False

            if not warning_message and algorithm_name:
                query_warning_sql = "SELECT warning_message FROM t_algorithm_result_warning_message WHERE algorithm_name = %s LIMIT 1"
                cursor.execute(query_warning_sql, (algorithm_name,))
                warning_result = cursor.fetchone()
                if warning_result:
                    warning_message = warning_result[0]
                    logging.info(f"从Algorithm_result_warning_message表查询到warning_message: {warning_message}")
                else:
                    logging.warning(
                        f"未在Algorithm_result_warning_message表中找到algorithm_name={algorithm_name}对应的warning_message")

            sql = """
                INSERT INTO `t_algorithm_result` 
                (`Algorithm_config_id`, `res_type`, `Mine_id`, `Equipment_id`, `Equipment_parent_id`,
                 `carousel_images_list`,`ori_images_list`, `result_count`,`result_count_time`, `template_id`,
                 `template_type_id`, `Algorithm_library_id`, `res_time`, `Entering_num`, `Exiting_num`,
                 `algorithm_name`,`conf_name`,`conf_img_resolution`,`equipment_type`,`equipment_name`,`mine_name`,`disposal_status`,`warning_message`,`warning_video`,`analysis_type`,`analysis_case`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s, %s, %s, %s, %s,%s,%s,%s,%s,%s,%s,%s)
            """
            values = (
                Algorithm_conf_id, res_type, Mine_id, Equipment_id, Equipment_parent_id, str(carousel_images_list),str(ori_images_list),
                result_count, result_count_time, template_id, template_type_id, Algorithm_library_id, res_time,Entering_num,Exiting_num,
                algorithm_name, conf_name,conf_img_resolution,equipment_type,equipment_name,mine_name,0,warning_message,warning_video,analysis_type,analysis_case)
            cursor.execute(sql, values)
            #人员计数算法结果修改配置
            if (not count_state_managed and Entering_num is not None and Exiting_num is not None
                    and all_Entering_num is not None and all_Exiting_num is not None):
                update_config_sql = """
                    UPDATE `t_algorithm_config`
                    SET `all_Entering_num` = %s, `all_Exiting_num` = %s
                    WHERE `id` = %s
                """
                cursor.execute(update_config_sql, (all_Entering_num, all_Exiting_num, Algorithm_conf_id))
                logging.info(
                    f"更新算法配置进出人数成功: Algorithm_conf_id={Algorithm_conf_id}, "
                    f"进入人数：Entering_num={Entering_num}, 离开人数：Exiting_num={Exiting_num}"
                )

            conn.commit()
        logging.info("视频AI识别分析管理平台数据写入成功!")

        return True
    except Exception as e:
        conn.rollback()
        logging.error('Alarm database write failed (%s)', type(e).__name__)
        raise
    finally:
        conn.close()

res_type_to_alarm_level = {
    '1': '5',
    '2': '4',
    '3': '3'
}
# 发送告警信息函数
def send_alarm_info(dict_data, event_key):
    res_type = dict_data.get('res_type')
    alarm_level = res_type_to_alarm_level.get(str(res_type), '5')  # 默认值为 '5'

    data = {
        'alarmLevel': alarm_level, # （字符串）
        'alarmTime': dict_data.get('datetime'), # 时间 （字符串）
        'resultCountStartTime': dict_data.get('result_count_time'), # 统计时长段 开始时间 （字符串）
        'alarmTypeName': dict_data.get('conf_name'), # 算法配置名称 （字符串）
        'deviceName': dict_data.get('equipment_name'), # 设备名称 （字符串）
        'ip': dict_data.get('equipment_ip'), # 设备ip （字符串）
        'resultCount': dict_data.get('result_count'), # 统计数量 （字符串）
        "httpUrl": dict_data.get('image_url')[0] if dict_data.get('image_url') else None, # 单张图片 （字符串）
        "httpUrlList": dict_data.get('image_url'), # 图片列表  （对象）
        'templateId': dict_data.get('template_id'),  # 模板id （字符串）
        'templateTypeId': dict_data.get('template_type_id'),  # 模板大类id （字符串）
        'mineId': dict_data.get('mine_id'),  # 矿id （字符串）
        'equipmentId': dict_data.get('equipment_id'),  # 设备id （字符串）
        'equipmentParentId': dict_data.get('equipment_parent_id'),  # 设备父id （字符串）
        'algorithmConfigId': dict_data.get('algorithm_config_id'),  # 算法配置id （字符串）
        'algorithmLibraryId': dict_data.get('Algorithm_library_id'),  # 算法id （字符串）
        'unitCode': dict_data.get('unitCode') if dict_data.get('unitCode') else None,  # 煤矿编码 （字符串）
        'Entering_num': dict_data.get('Entering_num'),
        'Exiting_num': dict_data.get('Exiting_num'),
        'all_Entering_num': dict_data.get('all_Entering_num'),
        'all_Exiting_num': dict_data.get('all_Exiting_num'),
        'warning_message': dict_data.get('warning_message'),
        'warning_video': dict_data.get('warning_video'),
        'analysis_type': dict_data.get('analysis_type'),
        'analysis_case': dict_data.get('analysis_case'),
        'GB28181_code': dict_data.get('GB28181_code'),
    }
    result = push_outbox.enqueue(data, event_key=event_key)
    logging.info('Alarm queued durably: delivery_id=%s duplicate=%s', result['id'], result['duplicate'])
    return result


# Kafka 消费者函数
# PLATFORM_PERSON_COUNT_ALARM_ID_V1
def _valid_count_alarm_id(value):
    return isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value)


def ensure_ingest_table():
    conn = pool.connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS t_platform_push_ingest (
                event_key varchar(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
                created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                KEY idx_platform_push_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        conn.commit()
    finally:
        conn.close()


def process_alarm(parsed_dict, event_key):
    # 执行关联查询获取所需数据
    conn = pool.connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询算法库表获取analysis_type
            algorithm_name = None
            algorithm_lib_sql = "SELECT analysis_type FROM t_algorithm_library WHERE id = %s"
            cursor.execute(algorithm_lib_sql, (parsed_dict.get('Algorithm_library_id'),))
            algorithm_lib_result = cursor.fetchone()
            if algorithm_lib_result:
                algorithm_name = algorithm_lib_result[0]

            # 2. 查询算法配置表获取conf_name和conf_img_resolution
            conf_name = None
            conf_img_resolution = None
            algorithm_config_sql = "SELECT conf_name, conf_img_resolution FROM t_algorithm_config WHERE id = %s"
            cursor.execute(algorithm_config_sql, (parsed_dict.get('Algorithm_config_id'),))
            algorithm_config_result = cursor.fetchone()
            if algorithm_config_result:
                conf_name = algorithm_config_result[0]
                conf_img_resolution = algorithm_config_result[1]

            # 3. 查询设备表获取equipment_type和equipment_name
            equipment_type = None
            equipment_name = None
            GB28181_code = None
            equipment_sql = "SELECT equipment_type, equipment_name,GB28181_code FROM t_equipment WHERE id = %s"
            cursor.execute(equipment_sql, (parsed_dict.get('Equipment_id'),))
            equipment_result = cursor.fetchone()
            if equipment_result:
                equipment_type = equipment_result[0]
                equipment_name = equipment_result[1]
                GB28181_code = equipment_result[2]
            # 4. 查询煤矿表获取mine_name
            mine_name = None
            mine_sql = "SELECT mine_name FROM t_mine WHERE id = %s"
            cursor.execute(mine_sql, (parsed_dict.get('Mine_id'),))
            mine_result = cursor.fetchone()
            if mine_result:
                mine_name = mine_result[0]

            # 更新parsed_dict中的字段
            parsed_dict['algorithm_name'] = algorithm_name
            parsed_dict['conf_name'] = conf_name
            parsed_dict['conf_img_resolution'] = conf_img_resolution
            parsed_dict['equipment_type'] = equipment_type
            parsed_dict['equipment_name'] = equipment_name
            parsed_dict['mine_name'] = mine_name
            parsed_dict['GB28181_code'] = GB28181_code

    finally:
        conn.close()

    upload_data(
        parsed_dict.get('Algorithm_config_id'),
        parsed_dict.get('res_type'),
        parsed_dict.get('Mine_id'),
        parsed_dict.get('Equipment_id'),
        parsed_dict.get('Equipment_parent_id'),
        parsed_dict.get('carousel_images_list', []),
        parsed_dict.get('ori_images_list', []),
        parsed_dict.get('result_count'),
        parsed_dict.get('result_count_time'),
        parsed_dict.get('template_id'),
        parsed_dict.get('template_type_id'),
        parsed_dict.get('Algorithm_library_id'),
        parsed_dict.get('res_time'),
        parsed_dict.get('Entering_num'),
        parsed_dict.get('Exiting_num'),
        parsed_dict.get('all_Entering_num'),
        parsed_dict.get('all_Exiting_num'),
        algorithm_name=parsed_dict.get('algorithm_name'),
        conf_name=parsed_dict.get('conf_name'),
        conf_img_resolution=parsed_dict.get('conf_img_resolution'),
        equipment_type=parsed_dict.get('equipment_type'),
        equipment_name=parsed_dict.get('equipment_name'),
        mine_name=parsed_dict.get('mine_name'),
        warning_message = parsed_dict.get('warning_message'),
        warning_video = parsed_dict.get('warning_video'),
        analysis_type = parsed_dict.get('analysis_type'),
        analysis_case = parsed_dict.get('analysis_case'),
        event_key=event_key,
        count_state_managed=parsed_dict.get('count_state_managed') is True,
    )
    # A previous delivery may have committed MySQL before enqueue failed.
    # Always retry the idempotent enqueue; the receipt already prevents a second row.
    send_alarm_info({
        'res_type': parsed_dict.get('res_type'), # 报警类型
        'conf_name': parsed_dict.get('algorithm_name'), # 算法配置名称
        'equipment_name': parsed_dict.get('equipment_name'), # 设备名称
        'equipment_ip': parsed_dict.get('equipment_ip'), # 设备ip
        'result_count': parsed_dict.get('result_count'), # 报警数量
        'result_count_time': str(parsed_dict.get('result_count_time')), # 统计开始时间
        'image_url': parsed_dict.get('carousel_images_list'), # 图片列表
        'datetime': str(parsed_dict.get('res_time')),  # 时间/（统计结束时间）

        'template_id': parsed_dict.get('template_id'),  # 模板id
        'template_type_id': parsed_dict.get('template_type_id'),  # 模板大类id
        'mine_id': parsed_dict.get('Mine_id'),  # 矿id
        'equipment_id': parsed_dict.get('Equipment_id'),  # 设备id
        'equipment_parent_id': parsed_dict.get('Equipment_parent_id'),  # 设备父id
        'algorithm_config_id': parsed_dict.get('Algorithm_config_id'),  # 算法配置id
        'Algorithm_library_id': parsed_dict.get('Algorithm_library_id'),  # 算法id
        'unitCode': parsed_dict.get('mine_code'),  # 煤矿编码id
        'Entering_num': parsed_dict.get('Entering_num'),
        'Exiting_num': parsed_dict.get('Exiting_num'),
        'all_Entering_num': parsed_dict.get('all_Entering_num'),
        'all_Exiting_num': parsed_dict.get('all_Exiting_num'),
        'start_time': parsed_dict.get('result_count_time'),
        'warning_message' : parsed_dict.get('warning_message'),
        'warning_video' : parsed_dict.get('warning_video'),
        'analysis_type' : parsed_dict.get('analysis_type'),
        'analysis_case' : parsed_dict.get('analysis_case'),
        'GB28181_code': parsed_dict.get('GB28181_code'),

    }, event_key)


ALARM_SCALAR_FIELDS = (
    'Algorithm_config_id', 'Algorithm_library_id', 'Equipment_id', 'Equipment_parent_id',
    'Mine_id', 'res_type', 'result_count', 'result_count_time', 'template_id',
    'template_type_id', 'res_time', 'Entering_num', 'Exiting_num', 'all_Entering_num',
    'all_Exiting_num', 'equipment_ip', 'mine_code', 'warning_message', 'warning_video',
    'analysis_type', 'analysis_case',
)
INVALID_ROW_CODES = {1048, 1264, 1265, 1292, 1366, 1406}


def consume_message(consumer, message):
    event_key = push_outbox.kafka_event_key(message.topic, message.partition, message.offset)
    raw = message.value.decode('utf-8', 'replace')
    try:
        parsed_dict = json.loads(message.value.decode('utf-8'))
        if not isinstance(parsed_dict, dict):
            raise ValueError('Alarm must be an object')
        for field in ALARM_SCALAR_FIELDS:
            value = parsed_dict.get(field)
            if value is not None and (type(value) not in (int, float, str)
                                      or isinstance(value, float) and not math.isfinite(value)):
                raise ValueError('Invalid alarm scalar field')
    except (UnicodeError, ValueError, RecursionError):
        push_outbox.quarantine(raw, event_key)
    else:
        alarm_event_id = parsed_dict.get('alarm_event_id')
        delivery_key = 'person-count:' + alarm_event_id if _valid_count_alarm_id(alarm_event_id) else event_key
        try:
            process_alarm(parsed_dict, delivery_key)
        except (pymysql.err.DataError, pymysql.err.IntegrityError) as error:
            if not error.args or error.args[0] not in INVALID_ROW_CODES:
                raise
            logging.warning('Quarantined invalid alarm at topic=%s partition=%s offset=%s code=%s',
                            message.topic, message.partition, message.offset, error.args[0])
            push_outbox.quarantine(raw, event_key, reason='数据库拒绝报警字段')
    # Acknowledge only after ingestion or quarantine was committed durably.
    try:
        metadata = OffsetAndMetadata(message.offset + 1, '', -1)
    except TypeError:  # kafka-python 2.0 compatibility
        metadata = OffsetAndMetadata(message.offset + 1, '')
    consumer.commit({TopicPartition(message.topic, message.partition): metadata})


def consumer_demo():
    while True:
        consumer = None
        try:
            ensure_ingest_table()
            consumer = KafkaConsumer('my-topic', bootstrap_servers='{}:9092'.format(KAFKA_HOST),
                auto_offset_reset='earliest', enable_auto_commit=False, group_id='my-consumer-group',
                max_poll_records=10, max_poll_interval_ms=300000)
            for message in consumer:
                consume_message(consumer, message)
        except Exception as error:
            logging.error('Alarm ingestion paused without acknowledgement (%s)', type(error).__name__)
        finally:
            if consumer is not None:
                consumer.close(autocommit=False)
        time.sleep(5)


if __name__ == '__main__':
    consumer_demo()
