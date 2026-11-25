# 导入模型字段
from model.admin import *
from model.algorithm import *
from model.equipment import *
from model.extra import *
from model.log import *
from sqlalchemy import and_
from model.ai_camera import *

class ModelTemplateConfData:
    # 算法类型模板大类表数据操作
    @staticmethod
    def get_model_type_template_list(page, per_page):
        """
        获取算法类型模板大类列表（支持分页）
        """
        return db.session.query(Model_template_config_type).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_model_type_template_by_id(id):
        """
        根据ID获取算法类型模板大类详情
        """
        return db.session.query(Model_template_config_type).filter(Model_template_config_type.id == id).first()
    @staticmethod
    def get_model_type_template_by_id_aicam(id):
        """
        根据ID获取算法类型模板大类详情
        """
        return db.session.query(Model_template_config_type_3588).filter(Model_template_config_type_3588.id == id).first()

    @staticmethod
    def create_model_type_template(model_type_name, model_type_content):
        """
        创建算法类型模板大类
        """
        new_template = Model_template_config_type(
            model_type_name=model_type_name,
            model_type_content=model_type_content
        )
        db.session.add(new_template)
        db.session.commit()
        return new_template

    @staticmethod
    def update_model_type_template(id, model_type_name=None, model_type_content=None):
        """
        更新算法类型模板大类
        """
        template_detail = db.session.query(Model_template_config_type).filter(Model_template_config_type.id == id).first()
        if template_detail:
            if model_type_name is not None:
                template_detail.model_type_name = model_type_name
            if model_type_content is not None:
                template_detail.model_type_content = model_type_content
            db.session.commit()
        return template_detail

    @staticmethod
    def delete_model_type_template(id):
        """
        删除算法类型模板大类
        """
        result = db.session.query(Model_template_config_type).filter(Model_template_config_type.id == id).delete()
        db.session.commit()
        return result

    @staticmethod
    def get_model_type_template_by_name(model_type_name):
        """
        根据名称获取算法类型模板大类
        """
        return db.session.query(Model_template_config_type).filter(Model_template_config_type.model_type_name == model_type_name).first()

    # 算法类型模板表数据操作
    @staticmethod
    def get_model_template_list(page, per_page, model_type=None, model_template_config_type_id=None):
        """
        获取算法类型模板列表（支持分页和筛选）
        """
        filters = []
        if model_type:
            filters.append(Model_template_config.model_type == model_type)
        if model_template_config_type_id:
            filters.append(Model_template_config.model_template_config_type_id == model_template_config_type_id)

        query = and_(*filters) if filters else True
        return db.session.query(Model_template_config).filter(query).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_model_template_by_id(id):
        """
        根据ID获取算法类型模板详情
        """
        return db.session.query(Model_template_config).filter_by(id=id).first()

    @staticmethod
    def create_model_template(model_name, model_template_config_type_id):
        """
        创建算法类型模板
        """
        new_template = Model_template_config(
            model_name=model_name,
            model_template_config_type_id=model_template_config_type_id
        )
        db.session.add(new_template)
        db.session.commit()
        return new_template

    @staticmethod
    def update_model_template(id, model_name=None, model_conf_list=None, model_template_config_type_id=None):
        """
        更新算法类型模板
        """
        template_detail = db.session.query(Model_template_config).filter_by(id=id).first()
        if template_detail:
            if model_name is not None:
                template_detail.model_name = model_name
            if model_conf_list is not None:
                template_detail.model_conf_list = model_conf_list
            if model_template_config_type_id is not None:
                template_detail.model_template_config_type_id = model_template_config_type_id
            db.session.commit()
        return template_detail

    @staticmethod
    def delete_model_template(id):
        """
        删除算法类型模板
        """
        result = db.session.query(Model_template_config).filter(Model_template_config.id == id).delete()
        db.session.commit()
        return result

    @staticmethod
    def get_model_template_by_name(model_name):
        """
        根据名称获取算法类型模板
        """
        return db.session.query(Model_template_config).filter(Model_template_config.model_name == model_name).first()

    # 大类下方小类数据操作
    @staticmethod
    def get_model_template_small_list(page, per_page, model_template_config_type_id=None):
        """
        获取算法类型模板小类列表（支持分页和筛选）
        """
        filters = []
        if model_template_config_type_id:
            filters.append(Model_template_small.model_template_config_type_id == model_template_config_type_id)

        query = and_(*filters) if filters else True
        return (
            db.session.query(Model_template_small.id,
                             Model_template_small.template_small_name,
                             Model_template_small.template_small_number,
                             Model_template_small.template_small_gauss,
                             Model_template_small.template_small_threshold,
                             Model_template_small.template_small_iou,
                             Model_template_small.template_small_start,
                             Model_template_small.template_small_end,
                             Model_template_small.template_small_upload,
                             Model_template_small.model_template_config_type_id,
                             Model_template_small.list_data,
                             Model_template_config_type.model_type_name,
                             Model_template_small.created_at,
                             Model_template_small.updated_at,
                             )
                .join(
                Model_template_config_type,
                Model_template_config_type.id == Model_template_small.model_template_config_type_id
            )
                .filter(query)
                .paginate(page=page, per_page=per_page, error_out=False)
        )

    @staticmethod
    def get_model_template_small_list_aicam(page, per_page, model_template_config_type_id=None):
        """
        获取算法类型模板小类列表（支持分页和筛选）
        """
        filters = []
        if model_template_config_type_id:
            filters.append(Model_template_small_3588.model_template_config_type_id == model_template_config_type_id)

        query = and_(*filters) if filters else True
        return (
            db.session.query(Model_template_small_3588.id,
                             Model_template_small_3588.template_small_name,
                             Model_template_small_3588.template_small_number,
                             Model_template_small_3588.template_small_gauss,
                             Model_template_small_3588.template_small_threshold,
                             Model_template_small_3588.template_small_iou,
                             Model_template_small_3588.template_small_start,
                             Model_template_small_3588.template_small_end,
                             Model_template_small_3588.template_small_upload,
                             Model_template_small_3588.model_template_config_type_id,
                             Model_template_small_3588.list_data,
                             Model_template_config_type_3588.model_type_name,
                             Model_template_small_3588.created_at,
                             Model_template_small_3588.updated_at,
                             )
                .join(
                Model_template_config_type_3588,
                Model_template_config_type_3588.id == Model_template_small_3588.model_template_config_type_id
            )
                .filter(query)
                .paginate(page=page, per_page=per_page, error_out=False)
        )

    @staticmethod
    def get_model_template_small_by_id(id):
        """
        根据ID获取算法类型模板小类详情
        """
        return db.session.query(Model_template_small).filter_by(id=id).first()
    @staticmethod
    def get_model_template_small_by_id_aicam(id):
        """
        根据ID获取算法类型模板小类详情
        """
        return db.session.query(Model_template_small_3588).filter_by(id=id).first()
    @staticmethod
    def create_model_template_small(model_template_config_type_id, list_data, template_small_name):
        """
        创建算法类型模板小类
        """
        new_template = Model_template_small(
            template_small_name=template_small_name,
            model_template_config_type_id=model_template_config_type_id,
            list_data=list_data
        )
        db.session.add(new_template)
        db.session.commit()
        return new_template

    @staticmethod
    def update_model_template_small(id, model_template_config_type_id=None, template_small_name=None,
                                   template_small_number=None, template_small_gauss=None,
                                   template_small_threshold=None, template_small_iou=None,
                                   template_small_start=None, template_small_end=None,
                                   template_small_upload=None, list_data=None):
        """
        更新算法类型模板小类
        """
        template_detail = db.session.query(Model_template_small).filter_by(id=id).first()
        if template_detail:
            if model_template_config_type_id is not None:
                template_detail.model_template_config_type_id = model_template_config_type_id
            if template_small_name is not None:
                template_detail.template_small_name = template_small_name
            if template_small_number is not None:
                template_detail.template_small_number = template_small_number
            if template_small_gauss is not None:
                template_detail.template_small_gauss = template_small_gauss
            if template_small_threshold is not None:
                template_detail.template_small_threshold = template_small_threshold
            if template_small_iou is not None:
                template_detail.template_small_iou = template_small_iou
            if template_small_start is not None:
                template_detail.template_small_start = template_small_start
            if template_small_end is not None:
                template_detail.template_small_end = template_small_end
            if template_small_upload is not None:
                template_detail.template_small_upload = template_small_upload
            if list_data is not None:
                template_detail.list_data = list_data
            db.session.commit()
        return template_detail

    @staticmethod
    def delete_model_template_small(id):
        """
        删除算法类型模板小类
        """
        result = db.session.query(Model_template_small).filter(Model_template_small.id == id).delete()
        db.session.commit()
        return result

    @staticmethod
    def get_model_template_small_by_name(template_small_name):
        """
        根据名称获取算法类型模板小类
        """
        return db.session.query(Model_template_small).filter(Model_template_small.template_small_name == template_small_name).first()

    @staticmethod
    def get_model_warning_message_by_name(algorithm_name):
        """
        根据名称获取算法类型模板
        """
        return db.session.query(Algorithm_result_warning_message).filter(Algorithm_result_warning_message.algorithm_name == algorithm_name).first()

    # @staticmethod
    # def create_model_warning_message(algorithm_name, template_type_id, warning_message):
    #     """
    #     创建算法类型模板
    #     :param algorithm_name: 算法名称
    #     :param template_type_id: 模板类型ID
    #     :param warning_message: 数组格式，每个元素包含 message_index 和 warning_message
    #     :return: 创建的记录列表
    #     """
    #     created_templates = []
    #
    #     if isinstance(warning_message, list):
    #         for item in warning_message:
    #             message_index = item.get('message_index')
    #             warning_text = item.get('warning_message')
    #
    #             if message_index is not None and warning_text is not None:
    #                 new_template = Algorithm_result_warning_message(
    #                     algorithm_name=algorithm_name,
    #                     template_type_id=template_type_id,
    #                     warning_message=warning_text,
    #                     message_index=message_index
    #                 )
    #                 db.session.add(new_template)
    #                 created_templates.append(new_template)
    #
    #     db.session.commit()
    #     return created_templates

    @staticmethod
    def create_model_warning_message(algorithm_name, template_type_id, warning_message):
        """
        创建算法报警信息（自动生成 message_index）
        :param algorithm_name: 算法名称
        :param template_type_id: 模板类型ID
        :param warning_message: 报警消息文本字符串
        :return: 创建的记录
        """
        # 获取当前算法配置下的最大 message_index
        max_index_record = db.session.query(
            db.func.max(Algorithm_result_warning_message.message_index)
        ).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id
            )
        ).scalar()

        # 计算新的 message_index（从1开始）
        new_message_index = (max_index_record or 0) + 1

        # 创建新记录
        new_template = Algorithm_result_warning_message(
            algorithm_name=algorithm_name,
            template_type_id=template_type_id,
            warning_message=warning_message,
            message_index=new_message_index
        )
        db.session.add(new_template)
        db.session.commit()

        return new_template
    @staticmethod
    def get_warning_messages_by_algorithm(algorithm_name, template_type_id):
        """
        根据算法名称和模板类型ID获取所有报警信息（按message_index排序）
        """
        return db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id
            )
        ).order_by(Algorithm_result_warning_message.message_index).all()

    @staticmethod
    def get_warn_message_list(page, per_page, algorithm_name=None, model_template_config_type_id=None):
        """
        报警信息展示（支持分页）
        """
        filters = []
        if algorithm_name:
            filters.append(Algorithm_result_warning_message.algorithm_name == algorithm_name)
        if model_template_config_type_id:
            filters.append(Algorithm_result_warning_message.template_type_id == model_template_config_type_id)

        query = and_(*filters) if filters else True
        return db.session.query(Algorithm_result_warning_message).filter(query).order_by(
            Algorithm_result_warning_message.template_type_id,
            Algorithm_result_warning_message.algorithm_name,
            Algorithm_result_warning_message.message_index
        ).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_model_warning_message_by_id(id):
        """
        根据ID获取算法类型模板大类详情
        """
        return db.session.query(Algorithm_result_warning_message).filter(Algorithm_result_warning_message.id == id).first()

    # @staticmethod
    # def batch_update_warning_messages(id, algorithm_name, template_type_id, warning_messages,message_index):
    #     """
    #     批量更新报警信息（根据message_index匹配）
    #     :param id: 主记录ID（用于验证是否存在）
    #     :param algorithm_name: 算法名称（可能需要更新）
    #     :param template_type_id: 模板类型ID（可能需要更新）
    #     :param warning_messages: 数组格式，每个元素包含 message_index 和 warning_message
    #     :return: 更新的记录数量
    #     """
    #     updated_count = 0
    #
    #     if isinstance(warning_messages, list):
    #         for item in warning_messages:
    #             message_index = item.get('message_index')
    #             warning_text = item.get('warning_message')
    #
    #             if message_index is not None and warning_text is not None:
    #                 # 查找对应的记录（使用旧的 algorithm_name 和 template_type_id 定位）
    #                 # 注意：这里需要先查询出旧值，因为前端可能已经修改了 algorithm_name 和 template_type_id
    #                 # 所以我们需要通过 id 来找到原始记录
    #                 pass
    #
    #         # 先通过 id 获取原始记录的 algorithm_name 和 template_type_id
    #         original_record = db.session.query(Algorithm_result_warning_message).filter(
    #             Algorithm_result_warning_message.id == id
    #         ).first()
    #
    #         if not original_record:
    #             return 0
    #
    #         # 使用原始的 algorithm_name 和 template_type_id 来定位记录
    #         old_algorithm_name = original_record.algorithm_name
    #         old_template_type_id = original_record.template_type_id
    #
    #         for item in warning_messages:
    #             message_index = item.get('message_index')
    #             warning_text = item.get('warning_message')
    #
    #             if message_index is not None and warning_text is not None:
    #                 # 使用原始值查找记录
    #                 message_detail = db.session.query(Algorithm_result_warning_message).filter(
    #                     and_(
    #                         Algorithm_result_warning_message.algorithm_name == old_algorithm_name,
    #                         Algorithm_result_warning_message.template_type_id == old_template_type_id,
    #                         Algorithm_result_warning_message.message_index == message_index
    #                     )
    #                 ).first()
    #
    #                 if message_detail:
    #                     # 如果存在则更新所有字段
    #                     message_detail.algorithm_name = algorithm_name
    #                     message_detail.template_type_id = template_type_id
    #                     message_detail.warning_message = warning_text
    #                     updated_count += 1
    #                 else:
    #                     # 如果不存在，创建新记录（使用新的 algorithm_name 和 template_type_id）
    #                     new_template = Algorithm_result_warning_message(
    #                         algorithm_name=algorithm_name,
    #                         template_type_id=template_type_id,
    #                         warning_message=warning_text,
    #                         message_index=message_index
    #                     )
    #                     db.session.add(new_template)
    #                     updated_count += 1
    #
    #     db.session.commit()
    #     return updated_count
    @staticmethod
    def batch_update_warning_messages(id, algorithm_name, template_type_id, warning_message, message_index):
        """
        更新单条报警信息（支持更新算法名称、模板类型ID和报警消息）
        :param id: 主记录ID（用于验证是否存在）
        :param algorithm_name: 算法名称（更新后的值，也用于定位记录）
        :param template_type_id: 模板类型ID（更新后的值，也用于定位记录）
        :param warning_message: 报警消息文本字符串
        :param message_index: 消息索引（用于定位具体记录）
        :return: 更新的记录数量（0或1）
        """
        # 先通过 id 获取原始记录，验证主记录是否存在
        original_record = db.session.query(Algorithm_result_warning_message).filter(
            Algorithm_result_warning_message.id == id
        ).first()

        if not original_record:
            return False

        # 使用传入的 algorithm_name + template_type_id + message_index 定位要更新的记录
        message_detail = db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.id == id,
                Algorithm_result_warning_message.message_index == message_index
            )
        ).first()

        if message_detail:
            # 如果存在则更新所有字段
            message_detail.algorithm_name = algorithm_name
            message_detail.template_type_id = template_type_id
            message_detail.warning_message = warning_message
            db.session.commit()
            return True
        else:
            # 如果不存在，返回0表示未找到记录
            return False
    @staticmethod
    def get_warning_messages_count(algorithm_name, template_type_id):
        """
        获取指定算法配置下的报警信息数量
        """
        count = db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id
            )
        ).count()
        return count


    @staticmethod
    def get_model_warning_message_by_algorithm_and_index(algorithm_name, template_type_id, message_index):
        """
        根据算法名称、模板类型ID和message_index获取报警信息
        """
        return db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id,
                Algorithm_result_warning_message.message_index == message_index
            )
        ).first()

    @staticmethod
    def delete_model_warning_message(id):
        """
        删除单条报警信息
        """
        result = db.session.query(Algorithm_result_warning_message).filter(Algorithm_result_warning_message.id == id).delete()
        db.session.commit()
        return result

    @staticmethod
    def delete_all_warning_messages_by_algorithm(algorithm_name, template_type_id):
        """
        删除指定算法名称和模板类型下的所有报警信息
        :param algorithm_name: 算法名称
        :param template_type_id: 模板类型ID
        :return: 删除的记录数量
        """
        result = db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id
            )
        ).delete()
        db.session.commit()
        return result


    @staticmethod
    def get_model_warning_message_by_algorithm_and_index(algorithm_name, template_type_id, message_index):
        """
        根据算法名称、模板类型ID和message_index获取报警信息
        """
        return db.session.query(Algorithm_result_warning_message).filter(
            and_(
                Algorithm_result_warning_message.algorithm_name == algorithm_name,
                Algorithm_result_warning_message.template_type_id == template_type_id,
                Algorithm_result_warning_message.message_index == message_index
            )
        ).first()
