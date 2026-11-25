"""Seven-day database log retention with bounded, small transactions.

Only the three log tables are touched. Alarm results and user configuration
are outside this cleanup policy.
"""
import logging
import os
from datetime import datetime, timedelta

from data.exts import db
from model.log import Log, Alg_logs, Platform_login


logger = logging.getLogger(__name__)


def _row_limit():
    try:
        requested = int(os.environ.get('SEAL_DB_LOG_MAX_ROWS', '50000'))
    except ValueError:
        requested = 50000
    return max(1000, min(200000, requested))


def cleanup_database_logs(cutoff=None, *, session=None, models=None,
                          max_rows=None, batch_size=1000, max_batches=25):
    """Delete expired logs, then oldest excess rows, in at most 25 batches/table.

    A backlog is drained over successive calls instead of holding one large
    transaction. Defaults cap each table at 50,000 records between cleanups.
    The result states whether another pass is needed.
    """
    session = session if session is not None else db.session
    models = models if models is not None else (Log, Alg_logs, Platform_login)
    cutoff = cutoff or datetime.now() - timedelta(days=7)
    # Even if an older caller provides a longer retention, never exceed 7 days.
    cutoff = max(cutoff, datetime.now() - timedelta(days=7))
    limit = _row_limit() if max_rows is None else max(1, int(max_rows))
    batch_size = max(1, min(1000, int(batch_size)))
    result = {'ok': True, 'tables': {}, 'pending': False}
    for model in models:
        table_result = {'expired': 0, 'excess': 0, 'pending': False}
        result['tables'][model.__tablename__] = table_result
        try:
            batches = 0
            while batches < max_batches:
                ids = [row[0] for row in session.query(model.id).filter(
                    model.created_at < cutoff).order_by(model.created_at, model.id).limit(batch_size).all()]
                if not ids:
                    break
                deleted = session.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)
                session.commit()
                table_result['expired'] += deleted
                batches += 1
            remaining = session.query(model.id).filter(model.created_at < cutoff).first() is not None
            if not remaining:
                excess = max(0, session.query(model).count() - limit)
                while excess and batches < max_batches:
                    ids = [row[0] for row in session.query(model.id).order_by(
                        model.created_at, model.id).limit(min(batch_size, excess)).all()]
                    if not ids:
                        break
                    deleted = session.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)
                    session.commit()
                    table_result['excess'] += deleted
                    excess -= deleted
                    batches += 1
                remaining = excess > 0
            table_result['pending'] = remaining
            result['pending'] = result['pending'] or remaining
            session.commit()  # End any SELECT transaction before the next run.
        except Exception:
            session.rollback()
            result['ok'] = False
            # Avoid dumping database URLs, query parameters, or log payloads.
            logger.error('Database log cleanup failed for %s', model.__tablename__)
    return result
