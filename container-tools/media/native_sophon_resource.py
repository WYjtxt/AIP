"""Publish real BM1684X card measurements using the installed SAIL SDK."""
import configparser
import logging
from pathlib import Path
import time

import pymysql
import sophon.sail as sail

COMPUTING_ID = 1


def sample_cards(api, ip):
    rows = []
    for device_id in range(api.get_available_tpu_num()):
        handle = api.Handle(device_id)
        total, used, util = api.get_dev_stat(device_id)
        rows.append((ip, device_id, str(handle.get_target()), str(handle.get_sn()),
                     str(api.get_board_temp(device_id)), str(api.get_chip_temp(device_id)),
                     '%sMB/%sMB' % (used, total), '%.2f%%' % (used * 100 / total if total else 0),
                     '%.2f%%' % util))
    return rows


def publish(connection, rows, computing_id):
    with connection.cursor() as cursor:
        for row in rows:
            cursor.execute('SELECT id FROM t_resource_usage WHERE dev_ip=%s AND dev_id=%s LIMIT 1', row[:2])
            existing = cursor.fetchone()
            if existing:
                cursor.execute('UPDATE t_resource_usage SET dev_get_target=%s,dev_get_sn=%s,board_temp=%s,'
                    'chip_temp=%s,mem_used_mem_total=%s,memory_usage_rate=%s,tpu_util=%s,computing_id=%s,updated_at=NOW() WHERE id=%s',
                    row[2:] + (int(computing_id), existing[0]))
            else:
                cursor.execute('INSERT INTO t_resource_usage (dev_ip,dev_id,dev_get_target,dev_get_sn,'
                    'board_temp,chip_temp,mem_used_mem_total,memory_usage_rate,tpu_util,computing_id,resource_num) '
                    'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)', row + (int(computing_id),))
    connection.commit()


def main():
    root = Path(__file__).resolve().parents[1]
    config = configparser.ConfigParser(interpolation=None)
    config.read(str(root / 'Config_files/config.ini'), encoding='utf-8')
    database = config['database']
    algorithm = configparser.ConfigParser(interpolation=None)
    algorithm.read(str(root / 'platform_algorithm_start/config/ApiConfig.ini'), encoding='utf-8')
    ip = algorithm['ipconfig']['localhost_ip']
    logging.basicConfig(level=logging.INFO)
    while True:
        connection = None
        try:
            connection = pymysql.connect(host=database['DB_HOST'], port=int(database.get('DB_PORT',3306)),
                user=database['DB_USER'], password=database['DB_PASSWORD'], database=database['DB_NAME'],
                charset='utf8mb4', connect_timeout=10)
            publish(connection, sample_cards(sail, ip), COMPUTING_ID)
        except Exception as error:
            if connection is not None:
                connection.rollback()
            logging.error('Sophon resource collection failed: %s', type(error).__name__)
        finally:
            if connection is not None:
                connection.close()
        time.sleep(2)


if __name__ == '__main__':
    main()
