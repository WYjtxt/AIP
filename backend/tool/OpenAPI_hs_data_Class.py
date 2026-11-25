import requests
import logging


class ZiguangVMSClient:
    def __init__(self, ip, port, client_id, client_secret):
        self.ip = ip
        self.port = port
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    def get_access_token(self):
        url = f"http://{self.ip}:{self.port}/sso/oauth2.0/accessToken"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret"  : self.client_secret,
            "format": "json"
        }

        try:
            response = requests.get(url, params=params, headers={"Content-Type": "application/json"},timeout=5)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            if not self.access_token:
                logging.error(f"[×] 获取 access_token 失败，响应内容: {data}")
                return None
            logging.info(f"[✓] 获取 access_token 成功: {self.access_token}")
            return self.access_token
        except requests.RequestException as e:
            logging.error(f"[×] 获取 access_token 请求异常: {e}")
            return None

    def get_device_list(self):
        if not self.access_token:
            logging.warning("请先获取 access_token")
            return None

        url = f"http://{self.ip}:11125/api/bss/v1/udm/channel/list-with-device?page_size=9999"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.access_token
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # 检查结构
            device_list = data.get("data", {}).get("data")
            if not isinstance(device_list, list):
                logging.error(f"[×] 响应数据格式异常或设备列表为空: {data}")
                return None

            logging.info(f"[✓] 成功获取设备列表，共 {len(device_list)} 个设备")
            return device_list

        except requests.RequestException as e:
            logging.error(f"[×] 获取设备列表请求异常: {e}")
            return None

    def get_live_stream_url(self, channel_code, stream_type=0, stream_mode=1, keep_alive=1800):
        if not self.access_token:
            logging.warning("请先获取 access_token")
            return None

        if not channel_code:
            logging.error("参数错误：channel_code 不能为空")
            return None

        url = f"http://{self.ip}:11125/api/vms/v2/webuas/live/stream/url"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.access_token
        }
        params = {
            "channel_code": channel_code,
            "stream_type": stream_type,
            "stream_mode": stream_mode,
            "keep_alive": keep_alive,
            "visit_ip": self.ip
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("error_code") != "0000000000":
                logging.error(f"[×] 获取直播地址失败，平台返回: {data.get('msg', '未知错误')}")
                return None

            logging.info(f"[✓] 通道 {channel_code} 获取直播地址成功")
            return data

        except requests.RequestException as e:
            logging.error(f"[×] 获取直播地址请求异常: {e}")
            return None


# if __name__ == "__main__":
#     client = ZiguangVMSClient(
#         ip="192.168.125.28",
#         port="9000",
#         client_id='',
#         client_secret=""
#     )
#
#     # 获取 token
#     if client.get_access_token():
#         devices = client.get_device_list()
#         print(len(devices))
#         if devices:
#             for device in devices:
#                 # 取第一个通道
#                 channel_code = device.get("ape_id")
#                 if not channel_code:
#                     logging.error("设备记录中未找到 ape_id 字段")
#                 else:
#                     stream_info = client.get_live_stream_url(channel_code)
#                     if stream_info:
#                         print(stream_info)