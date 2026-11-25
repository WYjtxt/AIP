from kafka import KafkaProducer
from dbutils.pooled_db import PooledDB
from datetime import datetime, timedelta
import json
import os
import threading
from config import common as cm
import pymysql



# kakka信息
kafka_ip = cm.kafka_ip
kafka_port = int(cm.kafka_port)


#本机IP
localhost = cm.localhost_ip


# sql数据库配置信息（MySQL 8.0，来自 config/ApiConfig.ini）
db_host = cm.db_host
db_port = int(cm.db_port)
db_user = cm.db_user
db_password = cm.db_password
db_name = cm.db_name


pool = PooledDB(
    creator=pymysql,          # 使用 pymysql 连接 MySQL 8.0
    maxconnections=30,        # 最大连接数
    mincached=2,              # 启动时创建的空闲连接
    maxcached=5,              # 池中最大空闲连接
    blocking=True,            # 连接用完时阻塞等待
    ping=1,                   # 取用连接前 ping 检测存活，断连自动重建
    host=db_host,
    port=db_port,
    user=db_user,
    password=db_password,
    database=db_name,
    charset='utf8mb4',
    read_timeout=10,
    write_timeout=10,
)



# Kafka producer 进程内单例：
#  - 原实现每次报警都新建 KafkaProducer（要走 bootstrap + 元数据探测，秒级同步开销），
#    且 retries 默认 0 —— broker 瞬断/超时时这条报警直接丢弃，表现为“本地有报警图、
#    kafka 消费端收不到”。改为复用连接 + 自动重试。
#  - kafka-python 的 producer 是线程安全的，可被多个报警线程共用；
#    按 pid 记录，防止 multiprocessing fork 后子进程误用父进程的连接。
_producer = None
_producer_pid = None
_producer_lock = threading.Lock()


def _get_producer():
    '''获取进程内 Kafka producer 单例（懒创建、线程安全）；fork 出的子进程按 pid 判断自动重建。'''
    global _producer, _producer_pid
    with _producer_lock:
        if _producer is None or _producer_pid != os.getpid():
            _producer = KafkaProducer(
                bootstrap_servers='{}:{}'.format(kafka_ip, kafka_port),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retries=3,               # 瞬时失败自动重试，报警不轻易丢
                max_block_ms=10000,      # 元数据不可用时最多阻塞 10s，不永久卡住报警线程
                request_timeout_ms=10000,
            )
            _producer_pid = os.getpid()
        return _producer


def _reset_producer():
    '''发送失败后废弃当前 producer（连接可能已坏），下次报警时重建。'''
    global _producer
    with _producer_lock:
        p, _producer = _producer, None
    if p is not None:
        try:
            p.close(timeout=2)
        except Exception:
            pass


def _fmt_time(t):
    '''时间字段统一成 'YYYY-mm-dd HH:MM:SS' 字符串：datetime/时间戳自动转换，
    str 原样透传，None/空串返回 None（调用方好用 or 接缺省值）。'''
    if t is None:
        return None
    if isinstance(t, datetime):
        return t.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')
    return str(t) or None


# 算能盒子本地上传
# PLATFORM_PERSON_COUNT_ALARM_ID_V1
def _valid_count_alarm_id(value):
    return isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value)


def upload_hwj(Algorithm_conf_id,
               res_type,
               Equipment_id,
               carousel_images_list,
               ori_images_list,
               result_count,
               Entering_num,
               Exiting_num,
               result_count_time,
               template_id,
               template_type_id,
               res_time,
               conf_name,
               equipment_name,
               equipment_ip,
               Algorithm_library_id,
               start_time = None,
               result_card_id = None,     # UWB 定位卡核验：异常关联的卡号（人数统计模板用，可选）
               result_alarm = None,        # UWB 核验结果：1=疑似多卡 / -1=疑似漏卡（可选）
               warning_message = None,     # 人数统计报警文本（可选）
               warning_video = None,       # 报警视频 URL（alarm_video.trigger 返回值，
                                           # 平台写入 t_algorithm_result.warning_video；可选）
               analysis_case = None,       # 视频质量异常编码 0001~0009（遮挡/挪动/过暗/过曝/
                                           # 模糊/冻结/丢失/抖动/分辨率，平台写入
                                           # t_algorithm_result.analysis_case；非质量类报警不传）
               all_Entering_num = None,
               all_Exiting_num = None,
               Mine_id = None,             # 矿区扩展元数据：当前部分盒端配置不提供
               Equipment_parent_id = None,
               mine_code = None,
               Hik_indexCode = None,
               alarm_event_id = None,
               count_state_managed = False
               ):
    '''把报警/统计结果组装成 JSON 消息发送到 Kafka（topic=my-topic），阻塞等待 broker 确认；
    发送失败时废弃 producer 单例并把异常抛给调用方处理。'''
    if alarm_event_id is not None and not _valid_count_alarm_id(alarm_event_id):
        raise ValueError('Invalid people-count alarm event ID')
    print("Entering_num",Entering_num)
    print(" result_count_time", result_count_time)

    try:
        producer = _get_producer()
        payload = {'Algorithm_config_id':Algorithm_conf_id,
                               'res_type':res_type,
                               'Mine_id': Mine_id,
                               'Equipment_id':Equipment_id,
                               'Equipment_parent_id':Equipment_parent_id,
                               'carousel_images_list':carousel_images_list,
                               'ori_images_list':ori_images_list,
                               'result_count':result_count,
                               'Entering_num':Entering_num,
                               'Exiting_num':Exiting_num,
                               'result_count_time':_fmt_time(result_count_time),
                               'template_type_id':template_type_id,
                               'template_id':template_id,
                               # res_time 平台读作报警结束时间：尊重调用方传入的事件结束时刻
                               # （与报警视频文件名的结束时间戳同源），缺省才用当前时刻。
                               # 旧版此处硬编码 now() 覆盖 —— 报警视频文件名与平台始末时间
                               # 对不上的根因（会话结束判定滞后 ≈3s，全部落在上报时刻）。
                               'res_time':_fmt_time(res_time) or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                               'conf_name':conf_name,
                               'equipment_name':equipment_name,
                               'equipment_ip':equipment_ip,
                               'Algorithm_library_id':Algorithm_library_id,
                               'start_time': _fmt_time(start_time),
                               'result_card_id': result_card_id,
                               'result_alarm': result_alarm,
                               'warning_message': warning_message,
                               'warning_video': warning_video,
                               'analysis_case': analysis_case,
                               'all_Entering_num':all_Entering_num,
                               'all_Exiting_num':all_Exiting_num,
                               'mine_code':mine_code,
                               'Hik_indexCode':Hik_indexCode
                               }
        if count_state_managed:
            payload['count_state_managed'] = True
        if alarm_event_id is None:
            future = producer.send('my-topic', payload)
        else:
            payload['alarm_event_id'] = alarm_event_id
            task_key = 'person-count:{}'.format(Algorithm_conf_id).encode('ascii')
            future = producer.send('my-topic', payload, key=task_key)
        # send() 是异步的，只把消息放进本地缓冲；必须阻塞等待 broker 确认，否则消息可能
        # 还没真正发出 —— “本地有图、平台不显示”的根因之一。
        meta = future.get(timeout=10)   # 拿到分区/offset 才算真正投递成功；失败会抛异常
        print('------------------------------------kafka数据写入成功 topic=%s partition=%s offset=%s------------------------------------'
              % (meta.topic, meta.partition, meta.offset))
    except Exception:
        # 连接可能已坏：废弃单例、下次报警重建；异常继续抛给调用方记录（调用方须自行 try/except，
        # 各模板已把上报放到后台线程并捕获，不会砸掉推理/推流热路径）。
        _reset_producer()
        raise

def update_conf_status(status, conf_name):
    '''更新 t_algorithm_config 表中指定配置的 conf_status（配置更新确认标志）。'''
    conn = pool.connection()
    cursor = conn.cursor()
    try:
        sql = "UPDATE t_algorithm_config SET conf_status = %s WHERE conf_name = %s"
        cursor.execute(sql, (status, conf_name))
        conn.commit()
        print('------------------------------------算法参数更新成功------------------------------------')
    finally:
        cursor.close()
        conn.close()  # 关键：确保关闭

# 防止报警数据量过大影响sql速率
def algorithm_run(conf_name, alarm_start_time, send_flag):
    '''把算法运行状态（报警开始时间/发送标志）写入 t_algorithm_run_status：已存在则更新，否则插入。'''
    # 从连接池获取连接对象
    conn = pool.connection()
    cursor = conn.cursor()

    # 构建 SQL 语句和要插入的值
    #sql = "INSERT INTO `t_algorithm_run_status` (`conf_name`, `alarm_start_time`,  `send_flag`) VALUES (%s, %s, %s)"
    #values = (conf_name, alarm_start_time, send_flag)
    check_sql = "SELECT COUNT(*) FROM t_algorithm_run_status WHERE conf_name = %s"
    cursor.execute(check_sql, (conf_name,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        # 2. 如果存在 → 更新
        update_sql = """
            UPDATE t_algorithm_run_status
            SET alarm_start_time = %s, send_flag = %s
            WHERE conf_name = %s
        """
        update_values = (alarm_start_time, send_flag, conf_name)
        cursor.execute(update_sql, update_values)
    else:
        # 3. 如果不存在 → 插入
        insert_sql = """
            INSERT INTO t_algorithm_run_status
            (conf_name, alarm_start_time, send_flag)
            VALUES (%s, %s, %s)
        """
        insert_values = (conf_name, alarm_start_time, send_flag)
        cursor.execute(insert_sql, insert_values)


    # 执行 SQL 语句并提交事务
    #cursor.execute(sql, values)
    conn.commit()
    print('------------------------------------算法运行状态写入成功------------------------------------')

def update_model_status(status, conf_name):
    '''更新 t_algorithm_config 表中指定配置的 model_status（1运行/2停止/3异常/4等待）。'''
    conn = pool.connection()
    cursor = conn.cursor()
    try:
        sql = "UPDATE t_algorithm_config SET model_status = %s WHERE conf_name = %s"
        cursor.execute(sql, (status, conf_name))
        conn.commit()
        print('------------------------------------算法状态更新成功------------------------------------')
    finally:
        cursor.close()
        conn.close()


def update_algorithm_run(conf_name):
    '''把 t_algorithm_run_status 表中指定配置的 send_flag 置 1（标记已发送）。'''
    print('------------------------------------进入算法运行状态更新------------------------------------')
    conn = pool.connection()
    cursor = conn.cursor()
    try:
        sql = "UPDATE t_algorithm_run_status SET send_flag = 1 WHERE conf_name = %s"
        cursor.execute(sql, (conf_name,))
        conn.commit()
        print('------------------------------------算法运行状态更新成功------------------------------------')
    finally:
        cursor.close()
        conn.close()


def insert_alg_log(
    ip_address: str,
    Level: str,
    message: str,
    alg_name: str,
    response_data: str = None,
    error_code: str = None,
    hostname: str = None
):
    """
    向 t_alg_logs 表插入算法日志
    
    参数:
        ip_address: 盒子IP地址 (必填)
        Level: 日志级别 (INFO/ERROR/WARNING) (必填)
        message: 日志内容 (必填)
        alg_name: 算法配置名称 (必填)
        response_data: 响应数据 (可选)
        error_code: 错误代码 (可选)
        hostname: 服务器主机名 (可选)
    """
    # 从连接池获取连接对象
    conn = pool.connection()
    cursor = conn.cursor()

    try:
        # 构建 SQL 语句和参数
        sql = """
        INSERT INTO t_alg_logs (
            ip_address, Level, message, alg_name,
            response_data, error_code, hostname
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            localhost,
            Level,
            message,
            alg_name,
            response_data,
            error_code,
            hostname
        )

        # 执行并提交
        cursor.execute(sql, values)
        conn.commit()
        print(f'[SUCCESS] 算法日志写入成功 | {alg_name} | {Level}')

    except Exception as e:
        conn.rollback()
        # 不要 raise：on_result 里 insert_alg_log 在 upload_hwj 之前调用，
        # 若此处抛出（如 t_alg_logs 表不存在）会中断报警上报且不更新报警间隔，
        # 导致每帧重复触发并刷屏。日志写失败仅记录，不影响主流程。
        print(f'[ERROR] 日志写入失败: {str(e)}')
        return False

    finally:
        cursor.close()
        conn.close()







def mirror_people_count(entered, exited, conf_id):
    """Mirror the local count state without changing task control fields."""
    from comm.data_receive import _resolve_computing_id

    conn = pool.connection()
    try:
        with conn.cursor() as cursor:
            computing_id = _resolve_computing_id(cursor)
            if computing_id is None:
                conn.rollback()
                return
            cursor.execute("""
                UPDATE t_algorithm_config a
                JOIN t_model_template_config t ON t.id=a.model_template_config_id
                SET a.all_Entering_num=%s, a.all_Exiting_num=%s, a.update_time=a.update_time
                WHERE a.id=%s AND a.computing_id=%s
                  AND t.model_template_config_type_id=3 AND t.model_name IN ('人数统计','人员计数','人数统计_全身','人数统计_头肩')
                  AND TRIM(COALESCE(a.model_algo_data, '[]')) IN ('','[]')
                  AND (NOT (a.all_Entering_num <=> %s) OR NOT (a.all_Exiting_num <=> %s))
            """, (str(entered), str(exited), int(conf_id), computing_id, str(entered), str(exited)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
