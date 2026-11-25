from data.ZiguangVMSClient_data import ZiguangVMSData
from tool.OpenAPI_hs_data_Class import ZiguangVMSClient
from concurrent.futures import ThreadPoolExecutor, as_completed

class ZiguangVMSService:
    def __init__(self):
        self.data_layer = ZiguangVMSData()

    def add_ziguang_platform(self, ziguang_host, ziguang_port, ziguang_id, ziguang_password, Mine_id):
        # 参数校验
        if not all([ziguang_host, ziguang_port, ziguang_id, ziguang_password, Mine_id]):
            return {'code': 400, 'msg': '设备数据有未填写项'}

        # 检查是否已存在
        if self.data_layer.check_ziguang_exists(ziguang_host):
            return {'code': 400, 'msg': '紫光华智设备信息已经存在,同步失败！'}

        # 初始化客户端
        ziguang_client = ZiguangVMSClient(
            ip=ziguang_host,
            port=ziguang_port,
            client_id=ziguang_id,
            client_secret=ziguang_password
        )

        if not ziguang_client.get_access_token():
            return {'code': 200, 'msg': '信息错误，同步失败！'}

        devices = ziguang_client.get_device_list()
        print('当前从紫光华智获取数据长度为:', len(devices))

        # 写入同步记录
        ziguang_data_data = self.data_layer.create_ziguang_data(
            devices[0]['org_name'], ziguang_host, ziguang_id, ziguang_password, ziguang_port, Mine_id
        )

        # 添加父设备
        equipment_data = self.data_layer.create_parent_equipment(
            devices[0]['org_name'], ziguang_host, Mine_id, ziguang_data_data.id
        )

        # 多线程并发拉取 RTSP
        def fetch_rtsp(device):
            ape_id = device.get("ape_id")
            if not ape_id:
                return None
            stream = ziguang_client.get_live_stream_url(ape_id)
            return {
                'device': device,
                'rtsp_url': stream.get("data") if stream else None
            }

        equipment_list = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_rtsp, dev) for dev in devices]
            for future in as_completed(futures):
                result = future.result()
                if not result:
                    continue
                dev = result['device']
                rtsp = result['rtsp_url']
                equipment_list.append({
                    'equipment_type': "紫光华智",
                    'manufacturer_type': "紫光华智",
                    'equipment_name': dev.get('dev_name'),
                    'equipment_ip': dev.get('ip_addr'),
                    'Mine_id': equipment_data.Mine_id,
                    'parent_id': equipment_data.id,
                    'online': dev.get('is_online', 2),
                    'Ziguang_ape_indexCode': dev.get('ape_id'),
                    'Ziguang_ape_rtsp_url': rtsp,
                    'Ziguang_id': ziguang_data_data.id,
                })

        # 批量插入子设备
        self.data_layer.bulk_create_equipment(equipment_list)
        return {'code': 200, 'msg': '紫光华智设备信息同步成功！'}

    def delete_ziguang_platform(self, id):
        if not id:
            return {'code': 400, 'msg': '参数缺失，请提供有效的 ID！'}

        if not self.data_layer.check_ziguang_exists_by_id(id):
            return {'code': 404, 'msg': '未找到对应的紫光华智平台信息！'}

        self.data_layer.delete_ziguang_platform(id)
        return {'code': 200, 'msg': '删除成功！'}

    def get_ziguang_platform_data(self, type_st, id, page, per_page):
        if not type_st:
            return {'code': 400, 'msg': '参数状态未有！'}

        if int(type_st) == 1:
            data, total, current_page, pages = self.data_layer.get_all_ziguang_data(page, per_page)
            return {
                'code': 200,
                'msg': "查询成功",
                'data': data,
                'total': total,
                'page': current_page,
                'pages': pages
            }
        else:
            parent_data = self.data_layer.get_ziguang_data_by_id(id)
            children_data, total, current_page, pages = self.data_layer.get_children_equipment(id, page, per_page)
            parent_data['children'] = children_data
            parent_data['total'] = total
            parent_data['page'] = current_page
            parent_data['pages'] = pages
            return {'code': 200, 'msg': "查询成功", 'data': parent_data}

    def sync_ziguang_devices_task(self):
        try:
            platforms = self.data_layer.get_all_platforms()
            for platform in platforms:
                client = ZiguangVMSClient(
                    ip=platform.ziguang_ip,
                    port=platform.ziguang_port,
                    client_id=platform.ziguang_id,
                    client_secret=platform.ziguang_password
                )
                if not client.get_access_token():
                    print(f"[警告] 获取平台 {platform.ziguang_name} 的 token 失败")
                    continue

                devices = client.get_device_list()
                print(f"[同步] {platform.ziguang_name} 获取设备数：{len(devices)}")

                parent_equipment = self.data_layer.get_parent_equipment(platform.id)
                if not parent_equipment:
                    print(f"[异常] 未找到平台 {platform.ziguang_name} 的父设备记录")
                    continue

                def fetch_rtsp(device):
                    ape_id = device.get("ape_id")
                    if not ape_id:
                        return None
                    stream = client.get_live_stream_url(ape_id)
                    return {
                        'device': device,
                        'rtsp_url': stream.get("data") if stream else None
                    }

                current_ape_ids = set([d["ape_id"] for d in devices if d.get("ape_id")])
                self.data_layer.delete_children_not_in_ape_ids(platform.id, parent_equipment.id, current_ape_ids)

                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_rtsp, dev) for dev in devices]
                    for future in as_completed(futures):
                        result = future.result()
                        if not result:
                            continue
                        dev = result["device"]
                        rtsp = result["rtsp_url"]
                        device_exist = self.data_layer.find_device_by_ape_index(
                            platform.id, parent_equipment.id, dev.get("ape_id")
                        )
                        if device_exist:
                            updates = {}
                            changed = False
                            if device_exist.equipment_name != dev.get("dev_name"):
                                updates['equipment_name'] = dev.get("dev_name")
                                changed = True
                            if device_exist.Ziguang_ape_rtsp_url != rtsp:
                                updates['Ziguang_ape_rtsp_url'] = rtsp
                                changed = True
                            if changed:
                                # self.data_layer.update_equipment_fields(device_exist.id, updates)
                                print(f"[更新] 设备：{dev.get('dev_name')} 信息已更新")
                        else:
                            new_device = {
                                'equipment_type': "紫光华智",
                                'manufacturer_type': "紫光华智",
                                'equipment_name': dev.get('dev_name'),
                                'equipment_ip': dev.get('ip_addr'),
                                'Mine_id': parent_equipment.Mine_id,
                                'parent_id': parent_equipment.id,
                                'online': dev.get('is_online', 2),
                                'Ziguang_ape_indexCode': dev.get('ape_id'),
                                'Ziguang_ape_rtsp_url': rtsp,
                                'Ziguang_id': platform.id,
                            }
                            self.data_layer.bulk_create_equipment([new_device])
                            print(f"[新增] 新设备：{dev.get('dev_name')}")
            return True, "紫光华智设备定时同步完成"
        except Exception as e:
            return False, f"紫光华智同步任务异常：{e}"
