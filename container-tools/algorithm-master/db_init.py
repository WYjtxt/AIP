#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""初始化 8888 平台数据库：建表 + alembic stamp + 预置数据（等价手册 2.19.1.7 流程）。"""
import os
import subprocess
import sys
import traceback

sys.path.insert(0, '/Seal_system')
os.chdir('/Seal_system')
out = open('/tmp/oneclick_db_init.result', 'w')
exit_code = 0
try:
    from server_app_factory import create_app
    from server_runtime import db
    # Schema creation must not start retention/diagnosis/background jobs.
    app = create_app(start_scheduler=False)
    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect
        tables = len(inspect(db.engine).get_table_names())
        out.write('TABLES %d\n' % tables)
    # The current release schema and built-in catalog are applied by the
    # reference synchronizer. Do not stamp an unapplied migration or run the
    # legacy CLI that creates fixed-password sample accounts.
except Exception:
    exit_code = 1
    out.write(traceback.format_exc())
out.close()
print(open('/tmp/oneclick_db_init.result').read())
sys.exit(exit_code)
