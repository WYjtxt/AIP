"""Production application factory retaining the current blueprints and settings."""
from server_runtime import *


def create_app(start_scheduler=True, audit_writer=None):
    configure_logging()
    app = Flask(__name__,template_folder='templates')
    from common.platform_secrets import load_platform_security
    load_platform_security(app)

    # --------注册CORS, "/*" 允许访问所有api--------
    from common.platform_origins import allowed_origins
    CORS(app, resources={r'/*': {'origins': allowed_origins()}}, supports_credentials=True, expose_headers=['X-Request-ID'])

    app.config.update(
        SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=True
    )

    # --------获取 Flask 应用的根路径--------
    root_path = app.root_path

    # SQLALCHEMY_TRACK_MODIFICATIONS: 这个选项用于启用或禁用 SQLAlchemy 对象修改的追踪功能。
    # True: 启用追踪。当数据库会话中的对象被修改时，SQLAlchemy 会发出信号。这在某些情况下可能会有用，例如，你需要在对象修改时执行某些操作。
    # False: 禁用追踪。这是默认的推荐设置。禁用后，可以减少内存开销，因为追踪对象修改需要额外的内存
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --------第一种登录认证--------配置 Flask-Session 及login会话--------
    # 设置 login-secret_key
    # 设置会话超时时间为30分钟
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
    app.config['SESSION_TYPE'] = 'redis'  # 可以使用 'redis', 'filesystem', 'mongodb', 等
    app.config['SESSION_PERMANENT'] = True
    # 配置 Redis 连接
    app.config['SESSION_REDIS'] = redis.Redis(host=Redis_ip, port=Redis_port, password=Redis_password,db=0)  # 使用你的 Redis 主机、端口和密码
    Session(app)

    # 设置login初始化组件
    # login_manager = LoginManager()
    # login_manager.init_app(app)
    # login_manager.login_view = 'login'  # 指定未登录时重定向的视图函数


    # --------第二种登录认证--------初始化 JWTManager--------
    jwt = JWTManager(app)
    # 过期时间
    # app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=12)
    # 配置密钥
    # 自定义过期错误消息
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'code': 401,
            'msg': '令牌已过期，请重新登录！'
        })

    # --------解决中文乱码--------
    app.config['JSON_AS_ASCII'] = False

    # --------定时任务配置--------
    # 配置 APScheduler
    class Config_APScheduler:
        SCHEDULER_API_ENABLED = False
    app.config.from_object(Config_APScheduler)

    # 初始化 APScheduler
    scheduler = APScheduler()
    scheduler.init_app(app)
    # Started only after database/routes/jobs/hooks are ready.

    # --------在应用对象上注册蓝图--------
    app.register_blueprint(user_view, url_prefix='/user_view') # 用户蓝图
    app.register_blueprint(cli) # 预置数据蓝图
    app.register_blueprint(model_view,url_prefix='/model_view') # 数据操作蓝图
    app.register_blueprint(menu_view,url_prefix='/menu_view')  # 菜单蓝图
    app.register_blueprint(model_views,url_prefix='/model_views') # 新增数据操作蓝图1
    app.register_blueprint(scheduler_task,url_prefix='/scheduler_task') # 定时任务蓝图
    app.register_blueprint(activate,url_prefix='/activate') # 激活序列蓝图
    app.register_blueprint(role_view,url_prefix='/role_view') # 角色蓝图
    app.register_blueprint(resource_view,url_prefix='/resource_view') # 算力资源蓝图
    app.register_blueprint(video_view,url_prefix='/video_view')
    app.register_blueprint(preview_view, url_prefix='/video_view/preview')
    app.register_blueprint(storage_retention_view, url_prefix='/storage_view')
    from apps.platform_ops_view import platform_ops_view
    app.register_blueprint(platform_ops_view, url_prefix='/platform_ops')
    # platform-site-api-factory-v1
    from apps.platform_site_view import platform_site_view
    app.register_blueprint(platform_site_view, url_prefix='/platform_site')
    # platform-network-confirm-access-v1
    from apps.platform_site_view import install_network_confirmation_access
    install_network_confirmation_access()
    app.register_blueprint(preview_compat_view, url_prefix='/video_view/preview/compat')
    app.register_blueprint(analysis_preview_view, url_prefix='/video_view/analysis_preview') # 实时视频蓝图
    app.register_blueprint(log_view,url_prefix='/log_view') # 平台日志
    app.register_blueprint(alg_log_view,url_prefix='/alg_log_view') # 算法日志
    app.register_blueprint(model_template,url_prefix='/model_template') # 实时视频蓝图
    app.register_blueprint(hik_security_platform_info_view,url_prefix='/hik_security_platform_info_view') # 海康安防平台数据业务蓝图
    app.register_blueprint(ziguang_platform_info_view,url_prefix='/ziguang_platform_info_view') # 紫光华智平台数据业务蓝图
    app.register_blueprint(zlmediakit_view,url_prefix='/zlmediakit_view') # 流媒体业务蓝图
    app.register_blueprint(ai_camera_view,url_prefix='/ai_camera_view') # 流媒体业务蓝图
    # --------连接数据库--------
    app.config.from_object(Config)

    # --------初始化--------
    db.init_app(app)

    # --------绑定app和数据库--------
    migrate = Migrate(app,db)



    @app.route('/', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH'])
    def def1():
        print('启动成功!',flush=True)
        # return render_template('index.html')  # 应确保 index.html 在 Flask 项目的 static 或 templates 目录下
        return jsonify({'code':200,'msg':'启动成功'})

    # captchas=1
    # 图片验证码
    @app.route('/captcha')
    def captcha():
        from common.platform_captcha import issue_captcha, set_captcha_cookie
        captcha_text = generate_captcha_text()
        # 存入redis 有效过期时间为180
        captcha_id = issue_captcha(redis_client, captcha_text)
        image = generate_captcha_image(captcha_text)

        buf = io.BytesIO()
        image.save(buf, 'PNG')
        buf.seek(0)
        return set_captcha_cookie(send_file(buf, mimetype='image/png'), captcha_id)

    # 激活二维码
    @app.route("/uuid_qr")
    def generate_qr():
        uuid_value = get_machine_uuid()

        # 生成二维码
        qr = qrcode.QRCode(
            version=None,  # 按机器申请码长度选择尺寸，避免固定大码缩小后难以识别
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # 低级别容错
            box_size=10,  # 每个格子的像素大小
            border=4  # 保留完整静区，方便手机扫码
        )
        qr.add_data(uuid_value)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")

        # 将二维码转换为字节流
        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)

        response = send_file(img_io, mimetype="image/png")
        response.headers['Cache-Control'] = 'no-store'
        return response


    # --------摄像头设备信息定时同步--------
    #更新时间：2025/10/16
    from server_scheduler_jobs import init_scheduler
    from common.error_handlers import init_error_handlers
    app.extensions['platform_jobs'] = init_scheduler(app, scheduler)
    init_error_handlers(app, writer=audit_writer)
    from common.platform_media import install_platform_media
    install_platform_media(app)
    from common.platform_access import install_platform_access
    install_platform_access(app)
    if start_scheduler:
        scheduler.start()
    return app
