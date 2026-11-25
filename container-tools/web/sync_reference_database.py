"""Add reference schema and built-in catalogue entries without replacing site accounts."""
import configparser
import json
import re
from pathlib import Path
import pymysql

ALLOWED = frozenset(('t_menu', 't_dict_type', 't_dict_data', 't_model_template_config_type', 't_model_template_config_type_3588', 't_model_template_config_3588', 't_model_template_small_3588',
                     't_model_template_config', 't_model_template_small', 't_version', 't_diagnosis_type'))


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('Invalid database identifier')
    return '`' + value + '`'


def sync_catalogue_rows(cursor, table, rows):
    """Add missing built-ins without replacing site names or thresholds."""
    if table not in ALLOWED:
        raise ValueError('Reference contains a non-catalogue table: ' + table)
    name = identifier(table)
    for row in rows:
        if 'id' not in row:
            raise ValueError('Catalogue entry has no stable id: ' + table)
        columns = list(row)
        cursor.execute('SELECT COUNT(*) FROM ' + name + ' WHERE id=%s', (row['id'],))
        if not cursor.fetchone()[0]:
            cursor.execute('INSERT INTO ' + name + ' (' + ','.join(map(identifier, columns)) + ') VALUES (' +
                           ','.join(['%s'] * len(columns)) + ')', [row[key] for key in columns])
        elif table == 't_version':
            updates = [key for key in columns if key != 'id']
            cursor.execute('UPDATE ' + name + ' SET ' + ','.join(identifier(key) + '=%s' for key in updates) +
                           ' WHERE id=%s', [row[key] for key in updates] + [row['id']])


def main():
    reference = json.loads(Path('/tmp/oneclick-reference.json').read_text(encoding='utf-8'))
    config = configparser.ConfigParser(interpolation=None)
    config.read('/Seal_system/config.ini')
    section = config['database']
    db = pymysql.connect(host=section['DB_HOST'], port=int(section.get('DB_PORT', 3306)),
                         user=section['DB_USER'], password=section['DB_PASSWORD'],
                         database=section['DB_NAME'], charset='utf8mb4', autocommit=False)
    try:
        with db.cursor() as cursor:
            cursor.execute('SHOW TABLES')
            existing = {row[0] for row in cursor.fetchall()}
            # DDL from SHOW CREATE is alphabetic; create missing tables in FK
            # dependency order instead of disabling checks on existing data.
            pending={name:ddl for name,ddl in reference['schema'].items() if name not in existing}
            while pending:
                ready=[name for name,ddl in pending.items()
                       if set(re.findall(r'REFERENCES `([^`]+)`',ddl)) <= existing | {name}]
                if not ready:
                    raise ValueError('无法确定新增表外键依赖顺序：' + ','.join(pending))
                for name in ready:
                    ddl=pending.pop(name)
                    if not ddl.startswith('CREATE TABLE ' + identifier(name) + ' ('):
                        raise ValueError('Unexpected reference schema')
                    cursor.execute(ddl);existing.add(name)
                    print('Created table:',name)
            for table, ddl in reference['schema'].items():
                name = identifier(table)
                if not ddl.startswith('CREATE TABLE ' + name + ' ('):
                    raise ValueError('Unexpected reference schema for ' + table)
                if table not in existing:
                    cursor.execute(ddl)
                    print('Created table:', table)
                    continue
                cursor.execute('SHOW COLUMNS FROM ' + name)
                columns = {row[0] for row in cursor.fetchall()}
                # Add only columns missing from an older installation. Never drop,
                # truncate or rewrite an existing column or business row.
                for line in ddl.splitlines()[1:]:
                    match = re.match(r'^\s*`([A-Za-z_][A-Za-z0-9_]*)`\s+', line)
                    if match and match.group(1) not in columns:
                        cursor.execute('ALTER TABLE ' + name + ' ADD COLUMN ' + line.strip().rstrip(','))
                        print('Added column:', table + '.' + match.group(1))
            for table, rows in reference['tables'].items():
                sync_catalogue_rows(cursor, table, rows)
            cursor.execute("UPDATE t_version SET version=%s WHERE id=1", ('V2.2.0',))
            db.commit()
        print('REFERENCE_DATABASE=PASS; existing accounts, permissions and business rows retained')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
