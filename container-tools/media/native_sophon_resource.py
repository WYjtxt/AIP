"""Publish Sophon card measurements using the installed SAIL SDK."""
import configparser
import logging
import os
from pathlib import Path
import sys
import time

import pymysql
import sophon.sail as sail


def sample_cards(api, ip):
    rows = []
    for device_id in range(api.get_available_tpu_num()):
        try:
            handle = api.Handle(device_id)
            total, used, util = api.get_dev_stat(device_id)
            if not 0 <= used <= total or not 0 <= util <= 100 or total <= 0:
                raise ValueError('invalid Sophon sample')
            rows.append((ip, device_id, str(handle.get_target()), handle.get_sn(),
                         str(api.get_board_temp(device_id)), str(api.get_chip_temp(device_id)),
                         '%sMB/%sMB' % (used, total), '%.2f%%' % (used * 100 / total),
                         '%.2f%%' % util))
        except Exception as error:
            logging.warning('Sophon card %d measurement unavailable: %s', device_id, type(error).__name__)
    return rows


def main():
    root = Path(os.environ.get('PLATFORM_NATIVE_ROOT', Path(__file__).absolute().parents[1]))
    sys.path.insert(0, str(root / 'platform_algorithm_start'))
    from comm.platform_host_identity import ensure_schema, publish_resources, read_host_identity, resource_sample_clock
    identity = read_host_identity()
    config = configparser.ConfigParser(interpolation=None)
    config.read(str(root / 'Config_files/config.ini'), encoding='utf-8')
    database = config['database']
    algorithm = configparser.ConfigParser(interpolation=None)
    algorithm.read(str(root / 'platform_algorithm_start/config/ApiConfig.ini'), encoding='utf-8')
    ip = algorithm.get('ipconfig', 'localhost_ip', fallback=None)
    logging.basicConfig(level=logging.INFO)
    connection = None
    previous_conflicts = ()
    while True:
        try:
            if connection is None:
                connection = pymysql.connect(host=database['DB_HOST'], port=database.getint('DB_PORT', fallback=3306),
                    user=database['DB_USER'], password=database['DB_PASSWORD'], database=database['DB_NAME'],
                    charset='utf8mb4', connect_timeout=10, read_timeout=10, write_timeout=10)
                ensure_schema(connection)
            else:
                connection.ping(reconnect=True)
            sampled_at = resource_sample_clock(connection)
            measurements = sample_cards(sail, ip)
            result = publish_resources(connection, measurements, identity, ip, sampled_at)
            conflicts = tuple(result['skipped_device_ids'])
            if conflicts and conflicts != previous_conflicts:
                logging.warning('Sophon IDs with conflicting card identities: %s', conflicts)
            previous_conflicts = conflicts
        except Exception as error:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
                try:
                    connection.close()
                except Exception:
                    pass
                connection = None
            logging.error('Sophon resource collection failed: %s', type(error).__name__)
        time.sleep(2)


if __name__ == '__main__':
    main()
