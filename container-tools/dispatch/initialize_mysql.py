"""Initialize local MySQL without interpolating passwords into shell/SQL syntax."""
import os
from pathlib import Path
import subprocess
import sys


def literal(value):
    if any(c in value for c in '\x00\r\n'):
        raise ValueError('Database password contains unsupported control characters')
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def main():
    client = sys.argv[1]
    root = os.environ['MYSQL_ROOT_PASS']; admin = os.environ['MYSQL_ADMIN_PASS']
    def query(sql, password):
        return subprocess.run([client, '--no-defaults', '-uroot', '--socket=/tmp/mysql.sock'],
                              input="SET SESSION sql_mode='';\n" + sql,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, env=dict(os.environ, MYSQL_PWD=password))
    if query('SELECT 1;', '').returncode == 0:
        if query("ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY " + literal(root) + ';', '').returncode:
            raise ValueError('Initializing local MySQL root failed')
    elif query('SELECT 1;', root).returncode:
        raise ValueError('Existing MySQL credentials rejected; database was preserved')
    sql = ("CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED WITH caching_sha2_password BY " + literal(root) + ";\n"
           "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;\n"
           "CREATE USER IF NOT EXISTS 'admin'@'%' IDENTIFIED WITH mysql_native_password BY " + literal(admin) + ";\n"
           "GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%' WITH GRANT OPTION;\n"
           "CREATE DATABASE IF NOT EXISTS seal_system CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
    if query(sql, root).returncode:
        raise ValueError('MySQL account/database initialization failed; credentials were not logged')
    print('MYSQL_INITIALIZATION=PASS')


if __name__ == '__main__': main()
