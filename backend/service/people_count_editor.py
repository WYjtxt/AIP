"""Scoped reads and explicit corrections for task-level people totals."""

import logging
import os
import sqlite3

from common.platform_access import has_menu_permission
from common.platform_host_identity import IdentityConflict, read_host_identity, resolve_device
from data.exts import db
from flask import g
from model.algorithm import Algorithm_config, Model_template_config
from service.count_state import CountConflict, CountState, read_state, state_directory
from service.person_count_scope import unique_count_scope


LOGGER = logging.getLogger(__name__)


def _positive_id(value):
    if type(value) is int and 0 < value <= 2_147_483_647:
        return value
    if type(value) is str and value.isascii() and value.isdecimal() and len(value) <= 10:
        return _positive_id(int(value))
    raise ValueError('任务编号无效')


def _template_type(template_id):
    row = db.session.query(Model_template_config.model_template_config_type_id,
                           Model_template_config.model_name).filter_by(id=template_id).first()
    return tuple(row) if row is not None else None


def _is_local(config):
    try:
        with db.session.connection().connection.cursor() as cursor:
            node = resolve_device(cursor, read_host_identity(), os.environ.get('TARGET_IP'))
            return node is not None and node['computing_id'] == config.computing_id
    except (IdentityConflict, OSError):
        return False


def _counts(config, state=None, path=None):
    data = {'Algorithm_library_id': config.Algorithm_library_id,
            'all_Entering_num': config.all_Entering_num, 'all_Exiting_num': config.all_Exiting_num,
            'count_revision': None, 'count_editable': False}
    if state is None and path is not None and path.is_file() and not path.is_symlink() and _is_local(config):
        state = read_state(path, config.id)
    if state:
        data.update(all_Entering_num=state['entered'], all_Exiting_num=state['exited'],
                    count_revision=state['revision'],
                    count_editable=has_menu_permission(g.platform_user.id, 'sfgl', 'u'))
    return data


def people_count_editor(conf_id, data_id=None, correction=None):
    try:
        ident = _positive_id(conf_id)
        if data_id not in (None, '', 0, '0'):
            return {'code': 400, 'msg': '请从主人数统计任务打开累计人数'}, 400
        query = db.session.query(Algorithm_config.id, Algorithm_config.Algorithm_library_id,
                                 Algorithm_config.model_template_config_id, Algorithm_config.model_algo_data_ori,
                                 Algorithm_config.all_Entering_num, Algorithm_config.all_Exiting_num,
                                 Algorithm_config.computing_id, Algorithm_config.model_algo_data).filter_by(id=ident)
        config = (query.with_for_update() if correction is not None else query).first()
        if config is None:
            return {'code': 404, 'msg': '任务不存在'}, 404
        if unique_count_scope(config, _template_type) != (0, config.model_template_config_id):
            return {'code': 400, 'msg': '当前任务暂无可校正的人数累计'}, 400
        if str(config.model_algo_data or '').strip() not in ('', '[]'):
            if correction is None:
                return {'code': 200, 'datalist': _counts(config)}, 200
            return {'code': 400, 'msg': '当前多模型任务不支持校正累计人数'}, 400
        path = state_directory() / ('conf_%d.sqlite3' % ident)
        if correction is None:
            return {'code': 200, 'datalist': _counts(config, path=path)}, 200
        # The regular task-save permission gate has already run. Keep the
        # explicit check here so the correction cannot be reused around it.
        if not has_menu_permission(g.platform_user.id, 'sfgl', 'u'):
            return {'code': 403, 'msg': '当前账号没有校正人数的权限'}, 403
        if not _is_local(config):
            return {'code': 409, 'msg': '只能校正本机人数统计任务，请确认任务所属服务器'}, 409
        if _positive_id(correction.get('library_id')) != config.Algorithm_library_id:
            return {'code': 409, 'msg': '任务算法已变更，请重新打开配置'}, 409
        if not path.is_file() or path.is_symlink():
            return {'code': 409, 'msg': '人数累计尚未初始化，请运行该任务后重试'}, 409
        state = CountState(ident)
        try:
            applied = state.correct(correction.get('revision'), correction.get('entered'), correction.get('exited'))
        except CountConflict as conflict:
            return {'code': 409, 'msg': str(conflict), 'datalist': _counts(config, state=conflict.state)}, 409
        LOGGER.info('累计人数校正 task_id=%s actor_id=%s revision=%s', ident, g.platform_user.id, applied['revision'])
        return {'code': 200, 'msg': '累计人数已校正', 'datalist': _counts(config, state=applied)}, 200
    except (ValueError, TypeError) as error:
        return {'code': 400, 'msg': str(error)}, 400
    except (OSError, sqlite3.Error):
        return {'code': 503, 'msg': '暂时无法读取累计人数，请稍后重试'}, 503
    finally:
        if correction is not None:
            db.session.rollback()  # Release the locked configuration; only count state is written.
