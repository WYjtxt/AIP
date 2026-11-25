import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET

# 海康硬盘录像机获取通道监控点资源信息类
class VCRDeviceInfo:
    def __init__(self, username, password, ip, port):
        """
        初始化录像机设备信息类
        :param username: 用户名
        :param password: 密码
        :param ip: 录像机 IP 地址
        :param port: 端口号
        """
        self.username = username
        self.password = password
        self.ip = ip
        self.port = port

    @staticmethod
    def _remove_namespace(tag):
        """去除命名空间前缀"""
        return tag.split('}')[-1] if '}' in tag else tag

    @staticmethod
    def _xml_to_dict(element):
        """将 XML 转换为列表套字典结构"""
        result_list = []
        for child in element:
            result = {}
            if child.text is not None:
                result[VCRDeviceInfo._remove_namespace(child.tag)] = child.text.strip()
            if len(child) > 0:
                result[VCRDeviceInfo._remove_namespace(child.tag)] = VCRDeviceInfo._xml_to_dict(child)
            result_list.append(result)
        return result_list

    def _parse_xml(self, response_info):
        """解析录像机状态 XML 数据"""
        root = ET.fromstring(response_info.text.strip())
        xml_dict = self._xml_to_dict(root)

        device_status_list = []
        for i in xml_dict:
            channel_info = {
                'id': i['InputProxyChannelStatus'][0]['id'],
                'ip_address': i['InputProxyChannelStatus'][1]['sourceInputPortDescriptor'][2]['ipAddress'],
                'online': i['InputProxyChannelStatus'][2]['online'],
                'username': i['InputProxyChannelStatus'][1]['sourceInputPortDescriptor'][5]['userName'],
                'password_status': i['InputProxyChannelStatus'][6]['SecurityStatus'][0]['PasswordStatus']
            }
            device_status_list.append(channel_info)
        return device_status_list

    def _xml_data(self, response_info):
        """解析录像机基础信息 XML 数据"""
        root = ET.fromstring(response_info.text.strip())
        xml_dict = self._xml_to_dict(root)

        device_status_list = []
        for i in xml_dict:
            channel_info = {
                'id': i['InputProxyChannel'][0]['id'],
                'name': i['InputProxyChannel'][1]['name'],
                'ip_address': i['InputProxyChannel'][2]['sourceInputPortDescriptor'][2]['ipAddress'],
                'managePortNo': i['InputProxyChannel'][2]['sourceInputPortDescriptor'][3]['managePortNo'],
                'username': i['InputProxyChannel'][2]['sourceInputPortDescriptor'][5]['userName']
            }
            device_status_list.append(channel_info)
        return device_status_list

    def _xml_info(self, response_info):
        """解析录像机帧率信息 XML 数据"""
        root = ET.fromstring(response_info.text.strip())
        xml_dict = self._xml_to_dict(root)

        device_status_list = []
        for i in xml_dict:
            channel_info = {
                'id': i.get('StreamingChannel', [{}])[4].get('Video', [{}])[1].get('dynVideoInputChannelID', None),
                'channelName': i.get('StreamingChannel', [{}])[1].get('channelName', ''),
                'videoCodecType': i.get('StreamingChannel', [{}])[4].get('Video', [{}])[2].get('videoCodecType', None)
            }
            video_info = i.get('StreamingChannel', [{}])[4].get('Video', [{}])
            channel_info.update({
                'videoResolutionWidth': video_info[4].get('videoResolutionWidth', None),
                'videoResolutionHeight': video_info[5].get('videoResolutionHeight', None),
                'constantBitRate': video_info[7].get('constantBitRate', None),
                'maxFrameRate': str(30) if video_info[9].get('maxFrameRate', '0') == '0' else str(int(int(video_info[9]['maxFrameRate']) / 100))
            })
            if not channel_info['channelName'].endswith('2'):
                device_status_list.append(channel_info)
        return device_status_list

    def get_vcr_data_info(self):
        """获取录像机的基础信息和状态"""
        try:
            # 录像机下方信息
            url_data = f'http://{self.ip}:{self.port}/ISAPI/ContentMgmt/InputProxy/channels'
            response_data = requests.get(url_data, auth=HTTPDigestAuth(self.username, self.password), timeout=15)

            # 录像机状态信息
            url_status = f'http://{self.ip}:{self.port}/ISAPI/ContentMgmt/InputProxy/channels/status/1'
            response_status = requests.get(url_status, auth=HTTPDigestAuth(self.username, self.password), timeout=5)

            # 录像机通道信息
            url_info = f'http://{self.ip}:{self.port}/ISAPI/Streaming/channels'
            response_info = requests.get(url_info, auth=HTTPDigestAuth(self.username, self.password), timeout=5)

            # 当所有请求状态为 200 时处理数据
            if response_data.status_code == 200 and response_status.status_code == 200 and response_info.status_code == 200:
                status_list = self._parse_xml(response_status)
                data_list = self._xml_data(response_data)
                info_list = self._xml_info(response_info)

                # 合并数据
                merged_data = [
                    {
                        **data,
                        **next((status for status in status_list if status['id'] == data['id']), {}),
                        **next((info for info in info_list if info['id'] == data['id']), {})
                    }
                    for data in data_list
                ]
                return merged_data
            else:
                return []
        except Exception as e:
            return []

# # 使用示例
# if __name__ == "__main__":
#     pass
#
#     # 实例化 配置相关参数
#     vcr = VCRDeviceInfo(
#         username='admin',
#         password='',
#         ip='192.168.7.50',
#         port=80
#     )
#
#     # 获取录像机下方通道数据信息
#     device_info = vcr.get_vcr_data_info()
#     print(device_info)
