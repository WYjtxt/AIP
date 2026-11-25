# hik-gateway-catalog-v1
from tool.hik_gateway import HikGatewayError

import concurrent.futures
from data.hik_security_platform_data import HikSecurityPlatformData
from config.configs import convert_folder_to_dict_list
from tool.OpenApi_public_Class import HikVisionAPI
from model.equipment import *
from sqlalchemy.exc import IntegrityError

def _hik_catalog(api):
    """Fetch a complete list before opening the write transaction."""
    regions = api.get_video_area()
    if not regions:
        raise HikGatewayError('海康安防平台未返回可访问区域，请检查资源授权')
    codes = {region['indexCode'] for region in regions}
    catalog = []
    for region in regions:
        cameras = api.get_video_area_info(region['indexCode'])
        for camera in cameras:
            code = camera['indexCode']
            if code in codes:
                raise HikGatewayError('海康安防平台资源编号重复，请检查区域和监控点目录')
            codes.add(code)
        catalog.append((region, cameras))
    return catalog


def _apply_hik_catalog(platform, catalog):
    areas = db.session.query(Hik_security_platform_up_area).filter_by(hik_info_id=platform.id).all()
    areas_by_code = {area.indexCode: area for area in areas}
    if len(areas_by_code) != len(areas):
        raise HikGatewayError('平台内已有重复安防区域编号，请先核对原有区域')
    devices = (db.session.query(Equipment).filter(Equipment.Hik_id.in_([area.id for area in areas]),
               Equipment.equipment_type == '安防平台').all() if areas else [])
    devices_by_code = {device.Hik_indexCode: device for device in devices if device.Hik_indexCode}
    if len(devices_by_code) != sum(bool(device.Hik_indexCode) for device in devices):
        raise HikGatewayError('平台内已有重复安防设备编号，请先核对原有设备')
    region_codes = set(areas_by_code)
    region_codes.update(region['indexCode'] for region, _ in catalog)

    def save_device(code, name, area, parent=None, gb_code=None):
        device = devices_by_code.get(code)
        if device is None:
            device = Equipment(equipment_type='安防平台', manufacturer_type='海康',
                               equipment_name=name, Mine_id=platform.Mine_id, Hik_id=area.id,
                               Hik_indexCode=code, parent_id=parent, online=1 if parent is not None else None)
            db.session.add(device)
            db.session.flush()
        else:
            if (parent is None and device.Hik_id != area.id) or (parent is not None and code in region_codes):
                raise HikGatewayError('安防区域与已有监控点编号冲突，请核对目录')
            device.equipment_name = name
            device.Hik_id = area.id
            device.parent_id = parent
        if isinstance(gb_code, str) and gb_code.strip():
            device.GB28181_code = gb_code.strip()
        return device

    for region, cameras in catalog:
        code, name = region['indexCode'], region['name']
        area = areas_by_code.get(code)
        if area is None:
            area = Hik_security_platform_up_area(indexCode=code, name=name,
                                                hik_info_id=platform.id, Mine_id=platform.Mine_id)
            db.session.add(area)
            db.session.flush()
        else:
            area.name = name
        parent = save_device(code, name, area)
        for camera in cameras:
            save_device(camera['indexCode'], camera['name'], area, parent.id,
                        camera.get('externalIndexCode') or camera.get('externalCode'))
    # The remote catalog is permission-scoped. Omitted devices stay registered.


class HikSecurityPlatformService:
    """海康安防平台服务层，处理业务逻辑"""
    
    @staticmethod
    def add_hik_security_platform(hik_host, hik_port, hik_appKey, hik_appSecret, Mine_id):
        try:
            api = HikVisionAPI(hik_host, hik_port, hik_appKey, hik_appSecret)
            gateway = api._gateway()
            catalog = _hik_catalog(api)
            existing = db.session.query(Hik_security_platform_info).filter_by(
                hik_appKey=hik_appKey, hik_appSecret=hik_appSecret).first()
            if existing is not None:
                return False, '该安防平台信息已经存在!'
            platform = Hik_security_platform_info(
                hik_name=catalog[0][0]['name'], hik_host=gateway.host, hik_port=str(gateway.port),
                hik_appKey=hik_appKey, hik_appSecret=hik_appSecret, Mine_id=Mine_id, hik_status='1')
            db.session.add(platform)
            db.session.flush()
            _apply_hik_catalog(platform, catalog)
            db.session.commit()
            camera_count = sum(len(cameras) for _, cameras in catalog)
            return True, '安防平台接入成功，已同步 {} 个区域和 {} 个监控点'.format(
                len(catalog), camera_count)
        except HikGatewayError as error:
            db.session.rollback()
            return False, str(error)
        except IntegrityError:
            db.session.rollback()
            return False, '安防平台资源编号与已有设备冲突，请核对接入配置'
        except Exception:
            db.session.rollback()
            return False, '安防平台接入失败，请检查本地平台状态'

    @staticmethod
    def delete_hik_security_platform(id):
        """删除海康安防平台信息"""
        try:
            success, msg = HikSecurityPlatformData.delete_hik_security_platform_info(id)
            return success, msg
        except Exception as e:
            print(f"删除海康安防平台信息失败: {e}")
            return False, f'删除失败，错误信息：{str(e)}'
    
    @staticmethod
    def get_hik_security_platform_data(page, per_page):
        """获取海康安防平台信息列表"""
        try:
            # 获取海康安防平台列表，支持分页
            pagination = HikSecurityPlatformData.get_hik_security_platform_list(page, per_page)
            
            if not pagination:
                return False, '获取海康安防平台列表失败'
            
            # 初始化用于存储结果的数据列表
            data_list = []

            # 遍历分页后的主区域数据
            for main_area in pagination.items:
                # 查询下级区域数据信息
                area_data = convert_folder_to_dict_list(
                    HikSecurityPlatformData.get_hik_security_platform_up_areas(main_area.id),
                    ['id','indexCode', 'name', 'hik_info_id',
                     'created_at', 'updated_at']
                )

                # 组装主区域数据并添加下级区域数据
                data_list.append({
                    'id':main_area.id,
                    'hik_name': main_area.hik_name,
                    'hik_host': main_area.hik_host,
                    'hik_port': main_area.hik_port,
                    'hik_appKey': main_area.hik_appKey,
                    'hik_appSecret': main_area.hik_appSecret,
                    'hik_artemis': main_area.hik_artemis,
                    'hik_methon': main_area.hik_methon,
                    'Mine_id': main_area.Mine_id,
                    'created_at': main_area.created_at,
                    'updated_at': main_area.updated_at,
                    'children_list': area_data
                })

            # 构造响应数据，包括分页信息
            response_data = {
                "data": data_list,
                "pagination": {
                    "current_page": page,
                    "total_pages": pagination.pages,
                    "total_items": pagination.total,
                    "per_page": per_page
                }
            }

            return True, response_data
        except Exception as e:
            print(f"获取海康安防平台信息列表失败: {e}")
            return False, f'获取海康安防平台信息列表失败，错误信息：{str(e)}'
    
    @staticmethod
    def get_hik_security_platform_resource_data(id, page, per_page):
        """获取海康安防平台资源信息"""
        try:
            # 二级区域信息
            res = convert_folder_to_dict_list(
                HikSecurityPlatformData.get_hik_security_platform_up_area_by_id(id),
                ['id', 'indexCode', 'name', 'hik_info_id',
                 'created_at', 'updated_at']
            )

            if res:
                # 获取子设备信息并进行分页
                from model.equipment import Equipment
                from data.exts import db
                res_children_query = db.session.query(Equipment).filter(
                    Equipment.Hik_id == id, 
                    Equipment.parent_id != None
                )

                # 使用 paginate() 方法进行分页
                res_children = res_children_query.paginate(page=page, per_page=per_page, error_out=False)

                # 将分页结果转换为字典列表
                res_children_list = convert_folder_to_dict_list(res_children.items,
                                                                ['id', 'equipment_type', 'manufacturer_type', 'equipment_name',
                                                                 'equipment_ip','Hik_id','Hik_rtsp_url','Hik_indexCode','create_time',])

                res['children'] = res_children_list
                res['total'] = res_children.total  # 总记录数
                res['page'] = res_children.page  # 当前页数
                res['pages'] = res_children.pages  # 总页数

            return True, res
        except Exception as e:
            print(f"获取海康安防平台资源信息失败: {e}")
            return False, f'获取海康安防平台资源信息失败，错误信息：{str(e)}'

    # @staticmethod
    # def update_hik_security_platform_task():
    #     try:
    #         platforms = HikSecurityPlatformData.get_all_hik_security_platform_infos()
    #         if not platforms:
    #             return True, "安防平台设备信息不存在！"
    #         for platform in platforms:
    #             hik_api = HikVisionAPI(
    #                 host=platform.hik_host,
    #                 port=platform.hik_port,
    #                 app_key=platform.hik_appKey,
    #                 app_secret=platform.hik_appSecret
    #             )
    #             area_data = hik_api.get_video_area()
    #             for area in area_data:
    #                 index_code = area.get('indexCode')
    #                 name = area.get('name')
    #                 existing_area = HikSecurityPlatformData.get_area_by_index_code(index_code)
    #                 if not existing_area:
    #                     new_area = HikSecurityPlatformData.create_hik_security_platform_up_area(
    #                         index_code, name, platform.id, platform.Mine_id
    #                     )
    #                     if not new_area:
    #                         continue
    #                     parent_device = HikSecurityPlatformData.create_equipment(
    #                         '安防平台', '海康', name, platform.Mine_id, Hik_id=new_area.id, Hik_indexCode=index_code
    #                     )
    #                     child_data = hik_api.get_video_area_info(index_code)
    #                     if isinstance(child_data, dict):
    #                         child_data = child_data.get('data', {}).get('list', [])
    #                     elif not isinstance(child_data, list):
    #                         child_data = []
    #                     for child in child_data:
    #                         child_index_code = child.get('indexCode')
    #                         child_name = child.get('name')
    #                         if not child_index_code and not child_name:
    #                             continue
    #                         rtsp_url = hik_api.get_rtsp_url(child_index_code)
    #                         HikSecurityPlatformData.create_equipment(
    #                             '安防平台', '海康', child_name, platform.Mine_id,
    #                             Hik_id=new_area.id, Hik_indexCode=child_index_code,
    #                             Hik_rtsp_url=rtsp_url, parent_id=parent_device.id if parent_device else None
    #                         )
    #                 else:
    #                     HikSecurityPlatformData.update_area_by_index_code(index_code, name, platform.id)
    #                     parent_device = HikSecurityPlatformData.get_parent_equipment_by_index_code(index_code)
    #                     if parent_device:
    #                         HikSecurityPlatformData.update_equipment_fields(parent_device.id, {'equipment_name': name})
    #                     child_data = hik_api.get_video_area_info(index_code)
    #                     if isinstance(child_data, dict):
    #                         child_data = child_data.get('data', {}).get('list', [])
    #                     elif not isinstance(child_data, list):
    #                         child_data = []
    #                     parent_area = HikSecurityPlatformData.get_area_by_index_code(index_code)
    #                     if parent_area:
    #                         external_codes = {i.get('indexCode') for i in child_data}
    #                         HikSecurityPlatformData.delete_children_not_in_index_codes(parent_area.id, external_codes)
    #                     for child in child_data:
    #                         child_index_code = child.get('indexCode', '')
    #                         child_name = child.get('name')
    #                         if not child_index_code and not child_name:
    #                             continue
    #                         rtsp_url = hik_api.get_rtsp_url(child_index_code)
    #                         existing_device = HikSecurityPlatformData.find_equipment_by_hik_index_code(child_index_code)
    #                         if existing_device:
    #                             HikSecurityPlatformData.update_equipment_fields(
    #                                 existing_device.id,
    #                                 {'equipment_name': child_name, 'Hik_rtsp_url': rtsp_url}
    #                             )
    #                         else:
    #                             HikSecurityPlatformData.create_equipment(
    #                                 '安防平台', '海康', child_name, platform.Mine_id,
    #                                 Hik_id=existing_area.id, Hik_indexCode=child_index_code,
    #                                 Hik_rtsp_url=rtsp_url, parent_id=parent_device.id if parent_device else None
    #                             )
    #         return True, "安防平台数据更新完成"
    #     except Exception as e:
    #         return False, f"安防平台同步失败: {str(e)}"


    @staticmethod
    def update_hik_security_platform_task():
        try:
            platforms = db.session.query(Hik_security_platform_info).all()
        except Exception:
            db.session.rollback()
            return False, '无法读取安防平台配置'
        if not platforms:
            return True, '安防平台设备信息不存在！'
        platform_ids = [platform.id for platform in platforms]
        failures = []
        for platform_id in platform_ids:
            try:
                query = db.session.query(Hik_security_platform_info).filter_by(id=platform_id)
                platform = query.first()
                if platform is None:
                    continue
                config = (platform.hik_host, platform.hik_port, platform.hik_appKey,
                          platform.hik_appSecret, platform.hik_artemis or 'artemis')
                db.session.rollback()
                catalog = _hik_catalog(HikVisionAPI(*config))
                platform = query.with_for_update().first()
                if platform is None or config != (
                        platform.hik_host, platform.hik_port, platform.hik_appKey,
                        platform.hik_appSecret, platform.hik_artemis or 'artemis'):
                    raise HikGatewayError('安防平台配置在同步期间发生变化，请重试')
                _apply_hik_catalog(platform, catalog)
                db.session.commit()
            except HikGatewayError as error:
                db.session.rollback()
                failures.append('平台 {} {}'.format(platform_id, error))
            except IntegrityError:
                db.session.rollback()
                failures.append('平台 {} 的资源编号与已有设备冲突'.format(platform_id))
            except Exception:
                db.session.rollback()
                failures.append('平台 {} 同步失败，请检查本地平台状态'.format(platform_id))
        if failures:
            return False, '；'.join(failures)
        return True, '安防平台数据更新完成'

