"""Request correlation and bounded asynchronous database audit logging."""
import logging
import re
import socket
import traceback
import uuid

from flask import request, g, jsonify
from data.exts import db
from model.log import Log
from model.admin import User
from flask_jwt_extended import get_jwt_identity
from common.audit_writer import AuditWriter, audit_text
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
_NO_LOG_PREFIXES = ('/captcha', '/uuid_qr', '/static', '/activate/activate_verify', '/activate/activate_show')


def init_error_handlers(app, writer=None, user_lookup=None):
    def persist(rows):
        with app.app_context():
            try:
                db.session.bulk_insert_mappings(Log, rows)
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

    if writer is None:
        writer = AuditWriter(persist).start()
    app.extensions['platform_audit_writer'] = writer

    def user():
        if getattr(g, '_audit_user_loaded', False):
            return getattr(g, '_audit_user', None)
        g._audit_user_loaded = True
        try:
            identity = get_jwt_identity()
            g._audit_user = (user_lookup(identity) if user_lookup else
                             db.session.query(User).filter(User.username == identity).first())
        except Exception:
            g._audit_user = None
        return g._audit_user

    def log_row(response=None, exception=None):
        owner = user()
        if owner is None:
            return
        if request.is_json:
            payload = request.get_json(silent=True)
        elif request.method == 'GET':
            payload = request.args.to_dict(flat=False)
        else:
            payload = request.form.to_dict(flat=False)
        status = 500 if exception else response.status_code
        response_data = ''
        if response is not None and not response.direct_passthrough and not response.is_streamed:
            try:
                response_data = response.get_json(silent=True)
                if response_data is None:
                    response_data = response.get_data(as_text=True)[:100]
            except Exception:
                response_data = ''
        stack = traceback.format_exc() if exception else ''
        writer.enqueue({
            'user_id': owner.id, 'user_name': audit_text(owner.name, 100),
            'level': 'ERROR' if status >= 500 else 'WARNING' if status >= 400 else 'INFO',
            'message': '请求失败!' if status >= 400 else '请求成功!',
            'ip_address': request.remote_addr, 'url': audit_text(request.base_url, 255),
            'method': request.method, 'module': request.blueprint,
            'request_data': audit_text(payload), 'response_data': audit_text(response_data, 100),
            'stack_trace': audit_text('request_id={}\n{}'.format(g.request_id, stack), 16384),
            'context': 'Production', 'error_code': str(status), 'hostname': socket.gethostname(),
        })

    @app.before_request
    def before_request():
        supplied = request.headers.get('X-Request-ID', '')
        g.request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())

    @app.errorhandler(Exception)
    def handle_exception(error):
        if isinstance(error, HTTPException):
            return jsonify({'code': error.code, 'msg': error.name, 'request_id': g.request_id}), error.code
        logger.error('Request failed request_id=%s type=%s', g.request_id, type(error).__name__)
        try:
            log_row(exception=error)
            g._audit_error_recorded = True
        except Exception as audit_error:
            logger.warning('Audit capture failed: %s', type(audit_error).__name__)
        return jsonify({'message': '内部服务器错误', 'request_id': g.request_id}), 500

    @app.after_request
    def after_request(response):
        response.headers['X-Request-ID'] = g.request_id
        if (request.method == 'OPTIONS' or request.path == '/' or request.path.startswith(_NO_LOG_PREFIXES)
                or getattr(g, '_audit_error_recorded', False)):
            return response
        try:
            log_row(response=response)
        except Exception as error:
            logger.warning('Audit capture failed request_id=%s type=%s', g.request_id, type(error).__name__)
        return response
