# hik-gateway-catalog-v1
from tool.hik_gateway import HikGateway, HikGatewayError

# -*- coding: UTF-8 -*-
import hashlib
import hmac
import base64
import time
import uuid
import requests
import json


# 安防平台SDK参考文档地址
# https://open.hikvision.com/docs/docId?version=%2F29c78ef52ca842c7933bd2b8e051e9d0&tagPath=%E6%96%87%E6%A1%A3%E8%AF%B4%E6%98%8E

# 海康安防平台获取资源信息类
class HikVisionAPI:
    def __init__(self, host, port, app_key, app_secret, artemis='artemis', method='POST'):
        """
        初始化类，配置海康威视 API 相关信息
        :param host: 安防平台主机地址
        :param port: 安防平台端口号
        :param app_key: 安防平台合作方的 AppKey
        :param app_secret: 安防平台合作方的 AppSecret
        :param artemis: artemis 服务器路径前缀
        :param method: 请求方法（默认为 POST）
        """
        self.host = host
        self.port = port
        self.app_key = app_key
        self.app_secret = app_secret
        self.artemis = artemis
        self.method = method

    def _generate_signature(self, api):
        """
        生成请求头中的签名信息
        :param api: API 路径
        :return: 包含签名的请求头字典
        """
        timestamp = str(int(round(time.time() * 1000)))  # 当前时间戳（毫秒级）
        nonce = str(uuid.uuid1())  # 生成唯一随机数
        secret = self.app_secret.encode('utf-8')
        # 构造签名消息
        message = f"{self.method}\n*/*\napplication/json\nx-ca-key:{self.app_key}\nx-ca-nonce:{nonce}\nx-ca-timestamp:{timestamp}\n/{self.artemis}{api}".encode(
            'utf-8')
        # 计算 HMAC-SHA256 签名并进行 Base64 编码
        signature = base64.b64encode(hmac.new(secret, message, digestmod=hashlib.sha256).digest())

        # 构造请求头
        headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'X-Ca-Key': self.app_key,
            'X-Ca-Signature': signature,
            'X-Ca-timestamp': timestamp,
            'X-Ca-nonce': nonce,
            'X-Ca-Signature-Headers': 'x-ca-key,x-ca-nonce,x-ca-timestamp',
        }
        return headers

    def _post(self, api, payload):
        return self._gateway().post(api, payload)

    def _gateway(self):
        return HikGateway(dict(host=self.host, port=self.port, artemis=self.artemis,
                               app_key=self.app_key, app_secret=self.app_secret))

    def get_video_area(self, page_no=1, page_size=1000, resource_type='region'):
        return self._gateway().regions(page_no, page_size, resource_type)

    def get_video_area_info(self, code, page_no=1, page_size=1000):
        return self._gateway().cameras(code, page_no, page_size)

    def get_rtsp_url(self, code, stream_type=0):
        mode = {'0': 'main', '1': 'sub', 'main': 'main', 'sub': 'sub'}.get(str(stream_type))
        if mode is None:
            raise HikGatewayError('安防平台码流类型必须为主码流或子码流')
        return self._gateway().preview(code, mode)

    def get_video_area_vcr_info(self, resource_index_codes):
        """
        根据资源索引编号获取录像机信息
        :param resource_index_codes: 资源索引编号列表
        :return: 录像机信息数据
        """
        api = '/api/resource/v1/resource/indexCodes/search'
        payload = {
            "resourceType": "encodeDevice",
            "resourceIndexCodes": resource_index_codes,
        }
        return self._post(api, payload).get('data', {})

    def get_video_area_onine_status(self,index_codes):
        """
        获取资源的历史在线记录接口
        :param resource_index_codes: 资源索引编号列表
        :return: 录像机信息数据
        """
        api = '/api/nms/v1/online/camera/get'
        payload = {
            "indexCodes":index_codes ,
            "pageNo": 1,
            "pageSize": 99999,
        }
        return self._post(api, payload).get('data', {})

    def get_camera_info(self, index_code):
        payload = {'pageNo': 1, 'pageSize': 1, 'expressions': [
            {'key': 'indexCode', 'operator': 0, 'values': [index_code]}]}
        data = self._post('/api/resource/v2/camera/search', payload).get('data')
        rows = data.get('list', []) if isinstance(data, dict) else []
        if rows:
            return rows[0].get('externalIndexCode') or rows[0].get('externalCode')
        return None
