from onvif import ONVIFCamera
import logging

def _required_site_value(name):
    import os
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError("Required deployment setting is missing: " + name)
    return value


# 配置日志
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)


class ONVIFAdapter:
    """
    ONVIF适配器类，用于对接不同厂商的录像机摄像头
    提供统一的ONVIF接口调用方法
    """

    def __init__(self, host, port, username, password, timeout=30):
        """
        初始化ONVIF设备连接
        :param host: 设备IP地址
        :param port: ONVIF端口（通常为80或8080）
        :param username: 设备用户名
        :param password: 设备密码
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.camera = None
        self.media_service = None
        self.device_service = None

    def connect(self):
        """
        建立与设备的连接
        :return: 连接是否成功
        """
        try:
            self.camera = ONVIFCamera(
                self.host, self.port, self.username, self.password,
                no_cache=True
            )
            # 创建媒体服务实例
            self.media_service = self.camera.create_media_service()
            # 创建设备管理服务实例
            self.device_service = self.camera.create_devicemgmt_service()
            print("设备连接成功")
            return True
        except Exception as e:
            print(f"设备连接失败: {str(e)}")
            return False

    def get_profiles(self):
        """
        调用GetProfiles接口
        :return: Profiles列表或None（如果出错）
        """
        try:
            response = self.media_service.GetProfiles()
            return response
        except Exception as e:
            print(f"GetProfiles调用失败: {str(e)}")
            return None

    def get_video_sources(self):
        """
        调用GetVideoSources接口
        :return: VideoSources列表或None（如果出错）
        """
        try:
            response = self.media_service.GetVideoSources()
            return response
        except Exception as e:
            print(f"GetVideoSources调用失败: {str(e)}")
            return None

    def get_video_source_configurations(self):
        """
        调用GetVideoSourceConfigurations接口
        :return: VideoSourceConfigurations列表或None（如果出错）
        """
        try:
            response = self.media_service.GetVideoSourceConfigurations()
            return response
        except Exception as e:
            print(f"GetVideoSourceConfigurations调用失败: {str(e)}")
            return None

    def get_video_encoder_configurations(self):
        """
        调用GetVideoEncoderConfigurations接口
        :return: VideoEncoderConfigurations列表或None（如果出错）
        """
        try:
            response = self.media_service.GetVideoEncoderConfigurations()
            return response
        except Exception as e:
            print(f"GetVideoEncoderConfigurations调用失败: {str(e)}")
            return None

    def get_stream_uri(self, profile_token, protocol='RTSP'):
        """
        调用GetStreamUri接口
        :param profile_token: 配置文件Token
        :param protocol: 传输协议，默认为RTSP
        :return: Stream URI或None（如果出错）
        """
        try:
            request = self.media_service.create_type('GetStreamUri')
            request.ProfileToken = profile_token
            request.StreamSetup = {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': protocol}
            }

            response = self.media_service.GetStreamUri(request)
            return response
        except Exception as e:
            print(f"GetStreamUri调用失败: {str(e)}")
            return None

    def get_osds(self, video_source_token=None):
        """
        调用GetOSDs接口获取OSD配置信息
        :param video_source_token: 视频源Token（可选）
        :return: 指定视频源或所有视频源的OSD配置信息或None（如果出错）
        """
        try:
            # 如果指定了特定的视频源token
            if video_source_token:
                request = self.media_service.create_type('GetOSDs')
                request.ConfigurationToken = video_source_token
                response = self.media_service.GetOSDs(request)
                return response
            else:
                # 获取所有视频源的OSD信息
                video_sources = self.get_video_sources()
                if not video_sources:
                    return None
                
                all_osds = []
                for video_source in video_sources:
                    try:
                        request = self.media_service.create_type('GetOSDs')
                        request.ConfigurationToken = video_source.token
                        response = self.media_service.GetOSDs(request)
                        all_osds.append({
                            'video_source_token': video_source.token,
                            'osds': response
                        })
                    except Exception as e:
                        print(f"获取视频源 {video_source.token} 的OSD信息失败: {str(e)}")
                        all_osds.append({
                            'video_source_token': video_source.token,
                            'osds': None,
                            'error': str(e)
                        })
                
                return all_osds
        except Exception as e:
            print(f"GetOSDs调用失败: {str(e)}")
            return None

    def get_device_information(self):
        """
        获取设备基本信息
        :return: 设备信息或None（如果出错）
        """
        try:
            response = self.device_service.GetDeviceInformation()
            return response
        except Exception as e:
            print(f"获取设备信息失败: {str(e)}")
            return None

    def get_network_interfaces(self):
        """
        获取网络接口信息
        :return: 网络接口信息或None（如果出错）
        """
        try:
            response = self.device_service.GetNetworkInterfaces()
            return response
        except Exception as e:
            print(f"获取网络接口信息失败: {str(e)}")
            return None

    def get_profiles_with_details(self):
        """
        获取配置文件详情，包括通道名称等信息
        :return: 配置文件详情列表或None（如果出错）
        """
        try:
            profiles = self.get_profiles()
            if not profiles:
                return None

            detailed_profiles = []
            for profile in profiles:
                profile_info = {
                    'token': getattr(profile, 'token', None),
                    'name': getattr(profile, 'Name', None),
                    'video_source_configuration': getattr(profile, 'VideoSourceConfiguration', None),
                    'video_encoder_configuration': getattr(profile, 'VideoEncoderConfiguration', None)
                }
                detailed_profiles.append(profile_info)

            return detailed_profiles
        except Exception as e:
            print(f"获取配置文件详情失败: {str(e)}")
            return None

    def get_stream_uri_for_all_profiles(self):
        """
        为所有配置文件获取视频流URI
        :return: 包含所有配置文件流URI的列表或None（如果出错）
        """
        try:
            profiles = self.get_profiles()
            if not profiles:
                return None

            stream_uris = []
            for profile in profiles:
                profile_token = getattr(profile, 'token', None)
                if not profile_token:
                    continue

                uri_result = self.get_stream_uri(profile_token)
                if uri_result:
                    stream_uris.append({
                        'profile_token': profile_token,
                        'profile_name': getattr(profile, 'Name', None),
                        'uri': getattr(uri_result, 'Uri', None)
                    })

            return stream_uris
        except Exception as e:
            print(f"获取所有配置文件的流URI失败: {str(e)}")
            return None

    def get_video_source_modes(self, video_source_token=None):
        """
        调用GetVideoSourceModes接口
        :param video_source_token: 视频源Token（可选）
        :return: 视频源模式信息或None（如果出错）
        """
        try:
            if not video_source_token:
                video_sources = self.get_video_sources()
                if not video_sources:
                    return None
                video_source_token = video_sources[0].token

            request = self.media_service.create_type('GetVideoSourceModes')
            request.VideoSourceToken = video_source_token

            response = self.media_service.GetVideoSourceModes(request)
            return response
        except Exception as e:
            print(f"GetVideoSourceModes调用失败（某些设备不支持此功能）: {str(e)}")
            return None


def Dahua_data_test(username, password, ip, port):
    """
    通过ONVIF协议获取大华设备的通道信息
    :param username: 用户名
    :param password: 密码
    :param ip: 设备IP地址
    :param port: 端口号
    :return: 通道信息列表
    """
    try:
        # 导入ONVIF适配器
        from onvif_adapter import ONVIFAdapter

        # 创建ONVIF适配器实例
        adapter = ONVIFAdapter(ip, port, username, password)

        # 连接设备
        if not adapter.connect():
            return []

        # 获取视频源信息 (包含Framerate和Resolution)
        video_sources = adapter.get_video_sources()
        if not video_sources:
            return []

        # 获取所有配置文件的流URI
        stream_uris = adapter.get_stream_uri_for_all_profiles()
        if not stream_uris:
            return []

        # 获取所有视频源的OSD信息
        osd_infos = adapter.get_osds()
        if not osd_infos:
            return []

        # 创建OSD信息字典，以token为键
        osd_dict = {}
        for osd_info in osd_infos:
            if 'error' not in osd_info and osd_info.get('osds'):
                osd_dict[osd_info['video_source_token']] = osd_info['osds']

        # 解析并组合数据
        result = []
        for i, video_source in enumerate(video_sources):
            channel_data = {}

            # 通道ID (使用索引作为ID)
            channel_data['id'] = i

            # 从VideoSource获取Framerate和Resolution
            channel_data['maxFrameRate'] = getattr(video_source, 'Framerate', None)
            if hasattr(video_source, 'Resolution') and video_source.Resolution:
                channel_data['videoResolutionWidth'] = getattr(video_source.Resolution, 'Width', None)
                channel_data['videoResolutionHeight'] = getattr(video_source.Resolution, 'Height', None)

            # 从OSD获取通道名称 (Type为Plain的PlainText)
            channel_name = f"Channel {i}"
            if video_source.token in osd_dict:
                for osd in osd_dict[video_source.token]:
                    # 查找Type为Plain的OSD
                    if hasattr(osd, 'TextString') and osd.TextString and \
                            hasattr(osd.TextString, 'Type') and osd.TextString.Type == 'Plain' and \
                            hasattr(osd.TextString, 'PlainText') and osd.TextString.PlainText:
                        channel_name = osd.TextString.PlainText
                        break
            channel_data['name'] = channel_name

            # 查找主码流URI (subtype=0)
            main_stream_uri = None
            for stream_uri in stream_uris:
                # 判断是否为主码流 (通过profile_name或uri参数)
                profile_token = stream_uri.get('profile_token', '')
                # 匹配规则: MediaProfile + 视频源token = profile_token
                # 例如: 视频源token为'00100'应该匹配'MediaProfile00100'开头的profile_token
                if profile_token.startswith('MediaProfile' + video_source.token) and \
                        ('subtype=0' in stream_uri.get('uri', '') or 'MainStream' in stream_uri.get('profile_name',
                                                                                                    '')):
                    main_stream_uri = stream_uri.get('uri')
                    break

            # 如果没找到明确的主码流，使用第一个匹配视频源token的
            if not main_stream_uri:
                for stream_uri in stream_uris:
                    profile_token = stream_uri.get('profile_token', '')
                    if profile_token.startswith('MediaProfile' + video_source.token):
                        main_stream_uri = stream_uri.get('uri')
                        break

            channel_data['main_stream_uri'] = main_stream_uri

            result.append(channel_data)

        return result

    except Exception as e:
        print(f"Error in Dahua_data_test: {e}")
        return []

if __name__ == '__main__':
    username = 'admin'
    password = _required_site_value("AIP_ONVIF_PASSWORD")
    ip = '192.168.14.65'
    port = 80
    result = Dahua_data_test(username, password, ip, port)
    print(result)