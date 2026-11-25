from data.model_template_conf_data import ModelTemplateConfData
from datetime import datetime


class ModelTemplateConfService:
    # 算法类型模板大类表数据操作
    @staticmethod
    def get_model_type_template_list(page, per_page):
        """
        获取算法类型模板大类列表（支持分页）
        """
        try:
            pagination = ModelTemplateConfData.get_model_type_template_list(page, per_page)
            
            # 构造返回数据
            data_list = [
                {
                    'id': item.id,
                    'model_type_name': item.model_type_name,
                    'model_type_content': item.model_type_content,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                }
                for item in pagination.items
            ]
            
            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }
            
            return True, {
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取算法类型模板大类列表失败: {str(e)}'

    @staticmethod
    def get_model_type_template_detail(id):
        """
        获取算法类型模板大类详情
        """
        try:
            template_detail = ModelTemplateConfData.get_model_type_template_by_id(id)
            if not template_detail:
                return False, '大类模板不存在'
            
            # 构造返回数据
            data = {
                'id': template_detail.id,
                'model_type_name': template_detail.model_type_name,
                'model_type_content': template_detail.model_type_content,
                'created_at': template_detail.created_at,
                'updated_at': template_detail.updated_at,
            }
            
            return True, data
        except Exception as e:
            return False, f'获取算法类型模板大类详情失败: {str(e)}'

    @staticmethod
    def add_model_type_template(model_type_name, model_type_content):
        """
        添加算法类型模板大类
        """
        try:
            # 检查模板名称是否已存在
            existing_template = ModelTemplateConfData.get_model_type_template_by_name(model_type_name)
            if existing_template:
                return False, '该算法模板已经存在！'
            
            # 创建新模板
            ModelTemplateConfData.create_model_type_template(model_type_name, model_type_content)
            return True, '算法大类模板添加成功！'
        except Exception as e:
            return False, f'算法类型模板添加失败: {str(e)}'

    @staticmethod
    def update_model_type_template(id, model_type_name, model_type_content):
        """
        更新算法类型模板大类
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_type_template_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 更新模板
            ModelTemplateConfData.update_model_type_template(id, model_type_name, model_type_content)
            return True, '修改成功'
        except Exception as e:
            return False, f'更新算法类型模板大类失败: {str(e)}'

    @staticmethod
    def delete_model_type_template(id):
        """
        删除算法类型模板大类
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_type_template_by_id(id)
            if not template_detail:
                return False, '小类模板不存在'
            
            # 删除模板
            ModelTemplateConfData.delete_model_type_template(id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法类型模板大类失败: {str(e)}'

    # 算法类型模板表数据操作
    @staticmethod
    def get_model_template_list(page, per_page, model_type=None, model_template_config_type_id=None):
        """
        获取算法类型模板列表（支持分页和筛选）
        """
        try:
            pagination = ModelTemplateConfData.get_model_template_list(
                page, per_page, model_type, model_template_config_type_id
            )
            
            # 构造返回数据
            data_list = [
                {
                    'id': item.id,
                    'model_name': item.model_name,
                    'model_type': item.model_type,
                    'model_conf_list': item.model_conf_list,
                    'image': item.image,
                    'content': item.content,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                    'model_template_config_type_id': item.model_template_config_type_id,
                }
                for item in pagination.items
            ]
            
            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }
            
            return True, {
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取算法类型模板列表失败: {str(e)}'

    @staticmethod
    def get_model_template_detail(id):
        """
        获取算法类型模板详情
        """
        try:
            template_detail = ModelTemplateConfData.get_model_template_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 构造返回数据
            data = {
                'id': template_detail.id,
                'model_name': template_detail.model_name,
                'model_type': template_detail.model_type,
                'model_conf_list': template_detail.model_conf_list,
                'image': template_detail.image,
                'content': template_detail.content,
                'created_at': template_detail.created_at,
                'updated_at': template_detail.updated_at,
                'model_template_config_type_id': template_detail.model_template_config_type_id,
            }
            
            return True, data
        except Exception as e:
            return False, f'获取算法类型模板详情失败: {str(e)}'

    @staticmethod
    def add_model_template(model_name, model_template_config_type_id):
        """
        添加算法类型模板
        """
        try:
            # 检查模板名称是否已存在
            existing_template = ModelTemplateConfData.get_model_template_by_name(model_name)
            if existing_template:
                return False, '该算法类型已经存在！'
            
            # 创建新模板
            ModelTemplateConfData.create_model_template(model_name, model_template_config_type_id)
            return True, '算法类型模板添加成功！'
        except Exception as e:
            return False, f'算法类型模板添加失败: {str(e)}'

    @staticmethod
    def update_model_template(id, model_name=None, model_conf_list=None, model_template_config_type_id=None):
        """
        更新算法类型模板
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_template_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 更新模板
            ModelTemplateConfData.update_model_template(
                id, model_name, model_conf_list, model_template_config_type_id
            )
            return True, '修改成功'
        except Exception as e:
            return False, f'更新算法类型模板失败: {str(e)}'

    @staticmethod
    def delete_model_template(id):
        """
        删除算法类型模板
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_template_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 删除模板
            ModelTemplateConfData.delete_model_template(id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法类型模板失败: {str(e)}'

    # 算法类型模板小类表数据操作
    @staticmethod
    def get_model_template_small_list(page, per_page, model_template_type_id=None):
        """
        获取算法类型模板小类列表（支持分页和筛选）
        """
        try:
            pagination = ModelTemplateConfData.get_model_template_small_list(
                page, per_page, model_template_type_id
            )
            
            # 构造返回数据
            data_list = [
                {
                    'id': item.id,
                    'template_small_name': item.template_small_name,
                    'list_data': eval(item.list_data) if item.list_data else [{}],  # 安全处理 list_data
                    'template_small_number': item.template_small_number,
                    'template_small_gauss': item.template_small_gauss,
                    'template_small_threshold': item.template_small_threshold,
                    'template_small_iou': item.template_small_iou,
                    'template_small_start': item.template_small_start,
                    'template_small_end': item.template_small_end,
                    'template_small_upload': item.template_small_upload,
                    'model_template_config_type_id': item.model_template_config_type_id,
                    'model_template_config_type_name': item.model_type_name,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                }
                for item in pagination.items
            ]
            
            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }
            
            return True, {
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取算法类型模板小类列表失败: {str(e)}'

    @staticmethod
    def get_model_template_small_list_aicam(page, per_page, model_template_type_id=None):
        """
        获取算法类型模板小类列表（支持分页和筛选）
        """
        try:
            pagination = ModelTemplateConfData.get_model_template_small_list_aicam(
                page, per_page, model_template_type_id
            )

            # 构造返回数据
            data_list = [
                {
                    'id': item.id,
                    'template_small_name': item.template_small_name,
                    'list_data': eval(item.list_data) if item.list_data else [{}],  # 安全处理 list_data
                    'template_small_number': item.template_small_number,
                    'template_small_gauss': item.template_small_gauss,
                    'template_small_threshold': item.template_small_threshold,
                    'template_small_iou': item.template_small_iou,
                    'template_small_start': item.template_small_start,
                    'template_small_end': item.template_small_end,
                    'template_small_upload': item.template_small_upload,
                    'model_template_config_type_id': item.model_template_config_type_id,
                    'model_template_config_type_name': item.model_type_name,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                }
                for item in pagination.items
            ]

            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }

            return True, {
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取算法类型模板小类列表失败: {str(e)}'
    @staticmethod
    def get_model_template_small_detail(id):
        """
        获取算法类型模板小类详情
        """
        try:
            template_detail = ModelTemplateConfData.get_model_template_small_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 获取大类名称
            template_type = ModelTemplateConfData.get_model_type_template_by_id(template_detail.model_template_config_type_id)
            
            # 构造返回数据
            data = {
                'id': template_detail.id,
                'template_small_name': template_detail.template_small_name,
                'list_data': eval(template_detail.list_data),
                'template_small_number': template_detail.template_small_number,
                'template_small_gauss': template_detail.template_small_gauss,
                'template_small_threshold': template_detail.template_small_threshold,
                'template_small_iou': template_detail.template_small_iou,
                'template_small_start': template_detail.template_small_start,
                'template_small_end': template_detail.template_small_end,
                'template_small_upload': template_detail.template_small_upload,
                'model_template_config_type_id': template_detail.model_template_config_type_id,
                'model_template_config_type_name': template_type.model_type_name if template_type else '',
                'created_at': template_detail.created_at,
                'updated_at': template_detail.updated_at,
            }
            
            return True, data
        except Exception as e:
            return False, f'获取算法类型模板小类详情失败: {str(e)}'

    @staticmethod
    def get_model_template_small_detail_aicam(id):
        """
        获取算法类型模板小类详情
        """
        try:
            template_detail = ModelTemplateConfData.get_model_template_small_by_id_aicam(id)
            if not template_detail:
                return False, '模板不存在'

            # 获取大类名称
            template_type = ModelTemplateConfData.get_model_type_template_by_id_aicam(
                template_detail.model_template_config_type_id)

            # 构造返回数据
            data = {
                'id': template_detail.id,
                'template_small_name': template_detail.template_small_name,
                'list_data': eval(template_detail.list_data),
                'template_small_number': template_detail.template_small_number,
                'template_small_gauss': template_detail.template_small_gauss,
                'template_small_threshold': template_detail.template_small_threshold,
                'template_small_iou': template_detail.template_small_iou,
                'template_small_start': template_detail.template_small_start,
                'template_small_end': template_detail.template_small_end,
                'template_small_upload': template_detail.template_small_upload,
                'model_template_config_type_id': template_detail.model_template_config_type_id,
                'model_template_config_type_name': template_type.model_type_name if template_type else '',
                'created_at': template_detail.created_at,
                'updated_at': template_detail.updated_at,
            }

            return True, data
        except Exception as e:
            return False, f'获取算法类型模板小类详情失败: {str(e)}'
    @staticmethod
    def add_model_template_small(model_template_config_type_id, list_data, template_small_name):
        """
        添加算法类型模板小类
        """
        try:
            # 检查模板名称是否已存在
            existing_template = ModelTemplateConfData.get_model_template_small_by_name(template_small_name)
            if existing_template:
                return False, '该算法模板已经存在！'
            
            # 创建新模板
            ModelTemplateConfData.create_model_template_small(
                model_template_config_type_id, list_data, template_small_name
            )
            return True, '算法模板添加成功！'
        except Exception as e:
            return False, f'算法类型模板添加失败: {str(e)}'

    @staticmethod
    def update_model_template_small(id, model_template_config_type_id=None, template_small_name=None,
                                   template_small_number=None, template_small_gauss=None,
                                   template_small_threshold=None, template_small_iou=None,
                                   template_small_start=None, template_small_end=None,
                                   template_small_upload=None, list_data=None):
        """
        更新算法类型模板小类
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_template_small_by_id(id)
            if not template_detail:
                return False, '模板不存在'
            
            # 处理时间格式
            def time_zh(data):
                try:
                    if isinstance(data, str):
                        parsed_time = datetime.strptime(data.split("GMT")[0].strip(), "%a %b %d %Y %H:%M:%S")
                        return parsed_time.strftime("%H:%M:%S")
                except (ValueError, AttributeError):
                    pass
                return data
            
            # 处理参数
            if template_small_start is not None:
                template_small_start = time_zh(template_small_start)
            if template_small_end is not None:
                template_small_end = time_zh(template_small_end)
            if template_small_upload is not None:
                template_small_upload = time_zh(template_small_upload)
            
            # 更新模板
            ModelTemplateConfData.update_model_template_small(
                id, model_template_config_type_id, template_small_name,
                template_small_number, template_small_gauss,
                template_small_threshold, template_small_iou,
                template_small_start, template_small_end,
                template_small_upload, list_data
            )
            return True, '修改成功'
        except Exception as e:
            return False, f'更新算法类型模板小类失败: {str(e)}'

    @staticmethod
    def delete_model_template_small(id):
        """
        删除算法类型模板小类
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_template_small_by_id(id)
            if not template_detail:
                return False, '小类模板不存在'
            
            # 删除模板
            ModelTemplateConfData.delete_model_template_small(id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法类型模板小类失败: {str(e)}'

    # 算法类型模板表数据操作
    @staticmethod
    def get_warn_message_list(page, per_page, algorithm_name=None, model_template_config_type_id=None):
        """
        获取算法类型模板列表（支持分页和筛选）
        """
        try:
            pagination = ModelTemplateConfData.get_warn_message_list(
                page, per_page, algorithm_name, model_template_config_type_id
            )

            # 构造返回数据，将 message_index 和 warning_message 拼接
            data_list = []
            for item in pagination.items:
                # 拼接 message_index 和 warning_message
                # combined_message = f"{item.message_index}. {item.warning_message}" if item.message_index else item.warning_message
                combined_message = item.warning_message
                data_list.append({
                    'id': item.id,
                    'algorithm_name': item.algorithm_name,
                    'warning_message': combined_message,
                    'model_template_config_type_id': item.template_type_id,
                    'message_index': item.message_index,
                })

            # 构造分页信息
            pagination_info = {
                'current_page': pagination.page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': pagination.per_page
            }

            return True, {
                'data': data_list,
                'pagination': pagination_info
            }
        except Exception as e:
            return False, f'获取报警信息列表失败: {str(e)}'



    @staticmethod
    def add_model_warning_message(algorithm_name, template_type_id, warning_message):
        """
        添加算法报警信息（自动分配message_index）
        """
        try:
            # 验证该算法名称是否已存在报警记录
            existing_message = ModelTemplateConfData.get_model_warning_message_by_name(algorithm_name)
            if existing_message:
                return False, f'算法 "{algorithm_name}" 的报警信息已存在，无法重复添加'

            # 直接创建，数据层会自动计算message_index
            new_message = ModelTemplateConfData.create_model_warning_message(algorithm_name, template_type_id, warning_message)
            return True, f'算法报警信息添加成功！'
        except Exception as e:
            return False, f'算法报警信息添加失败: {str(e)}'

    @staticmethod
    def get_warning_messages_by_algorithm(algorithm_name, template_type_id):
        """
        获取指定算法配置的所有报警信息（包含总数统计）
        """
        try:
            messages = ModelTemplateConfData.get_warning_messages_by_algorithm(algorithm_name, template_type_id)

            data_list = [
                {
                    'id': item.id,
                    'message_index': item.message_index,
                    'algorithm_name': item.algorithm_name,
                    'warning_message': item.warning_message,
                    'model_template_config_type_id': item.template_type_id,
                }
                for item in messages
            ]

            # 返回总数和详细列表
            return True, {
                'total': len(data_list),
                'messages': data_list
            }
        except Exception as e:
            return False, f'获取算法报警信息失败: {str(e)}'

    @staticmethod
    def update_model_warning_message(id, algorithm_name, template_type_id, warning_message,message_index):
        """
        更新算法报警信息
        :param id: 数据库记录ID（用于定位原始记录）
        :param algorithm_name: 算法名称（更新后的值）
        :param template_type_id: 模板类型ID（更新后的值）
        :param warning_message: 数组格式，每个元素包含 message_index 和 warning_message
        """
        try:
            # 检查主记录是否存在
            message_detail = ModelTemplateConfData.get_model_warning_message_by_id(id)
            if not message_detail:
                return False, '报警信息不存在'

            # 批量更新报警信息（会同时更新 algorithm_name、template_type_id 和 warning_message）
            updated_count = ModelTemplateConfData.batch_update_warning_messages(
                id,
                algorithm_name,
                template_type_id,
                warning_message,
                message_index
            )

            if updated_count :
                return True, f'成功更新报警信息'
            else:
                return False, '没有更新任何报警信息'
        except Exception as e:
            return False, f'更新算法报警信息失败: {str(e)}'

    @staticmethod
    def delete_model_warning_message(id):
        """
        删除单条报警信息
        """
        try:
            # 检查模板是否存在
            template_detail = ModelTemplateConfData.get_model_warning_message_by_id(id)
            if not template_detail:
                return False, '报警信息不存在'

            # 删除单条记录
            ModelTemplateConfData.delete_model_warning_message(id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法报警信息失败: {str(e)}'

    @staticmethod
    def delete_model_warning_message_by_index(id, algorithm_name, template_type_id, message_index):
        """
        根据 message_index 删除单条报警信息
        """
        try:
            # 先通过 id 验证主记录存在
            template_detail = ModelTemplateConfData.get_model_warning_message_by_id(id)
            if not template_detail:
                return False, '报警信息不存在'

            # 根据 algorithm_name + template_type_id + message_index 查找要删除的记录
            record = ModelTemplateConfData.get_model_warning_message_by_algorithm_and_index(
                algorithm_name, template_type_id, message_index
            )

            if not record:
                return False, '未找到对应的报警信息'

            # 删除单条记录
            ModelTemplateConfData.delete_model_warning_message(record.id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法报警信息失败: {str(e)}'

    @staticmethod
    def delete_all_warning_messages_by_algorithm(id, algorithm_name, template_type_id):
        """
        删除指定算法的所有报警信息
        """
        try:
            # 先通过 id 验证主记录存在
            template_detail = ModelTemplateConfData.get_model_warning_message_by_id(id)
            if not template_detail:
                return False, '报警信息不存在'

            # 检查是否存在该算法的报警信息
            count = ModelTemplateConfData.get_warning_messages_count(algorithm_name, template_type_id)
            if count == 0:
                return False, '该算法下没有报警信息'

            # 批量删除
            deleted_count = ModelTemplateConfData.delete_all_warning_messages_by_algorithm(
                algorithm_name,
                template_type_id
            )

            return True, f'成功删除 {deleted_count} 条报警信息'
        except Exception as e:
            return False, f'批量删除算法报警信息失败: {str(e)}'

    @staticmethod
    def delete_model_warning_message_by_id(id):
        """
        根据 message_index 删除单条报警信息
        """
        try:
            # 先通过 id 验证主记录存在
            template_detail = ModelTemplateConfData.get_model_warning_message_by_id(id)
            if not template_detail:
                return False, '报警信息不存在'

            # 删除单条记录
            ModelTemplateConfData.delete_model_warning_message(template_detail.id)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除算法报警信息失败: {str(e)}'