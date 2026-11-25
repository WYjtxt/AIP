# native-recorder-sync-v2
# native-recorder-channel-identity-v1
from service.recorder_binding_identity import channel_key
"""Production scheduler registration; original vendor/business operations retained."""
from server_runtime import *


def _publish_job(function):
    # Keep APScheduler function references importable despite app-bound closures.
    function.__qualname__ = function.__name__
    globals()[function.__name__] = function
    return function


def init_scheduler(app, scheduler):
    @_publish_job
    def camera_update_task():
        with app.app_context():
            success, message = SchedulerTaskService.update_camera_online_status_task()
            print(message)

    scheduler.add_job(func=polling_job(camera_update_task), args=[], id="camera_update_task_1", trigger="interval", minutes=10, replace_existing=True)

    # --------录像机设备信息定时同步--------
    # 先查找录像机父表是否有数据，如果有数据循环读取（录像机ip），
    # 用录像机ip去调用isapi来获取摄像头实时信息进行修改，如果不存在则进行添加操作
    ########版本分层后############
    # def vcr_update_task():  # 运行的定时任务的函数
    #     with app.app_context():
    #         success, message = SchedulerTaskService.update_vcr_equipment_task()
    #         print(message)
    # scheduler.add_job(func=polling_job(vcr_update_task), args=[], id="vcr_update_task_1", trigger="interval", minutes=10, replace_existing=True)

    ########版本分层前############
    @_publish_job
    def vcr_update_task():
        with app.app_context():
            from service.equipment_model_service import EquipmentService
            response = EquipmentService.manual_sync(prepare_streams=False)
            result = response.get('data') or {'created': 0, 'deleted': 0, 'failed': [response.get('msg', '同步失败')]}
            print('同步任务完成: 创建 {} 个, 删除 {} 个, 失败 {} 个'.format(result.get('created', 0), result.get('deleted', 0), len(result.get('failed', []))))
            for index, message in enumerate(result.get('failed', []), 1):
                print('  {}. {}'.format(index, message))
    scheduler.add_job(func=polling_job(vcr_update_task), args=[], id="vcr_update_task_1", trigger="interval", minutes=10, replace_existing=True)
    @_publish_job
    def recorder_health_task():
        with app.app_context():
            from service.recorder_health import refresh_registered_recorders
            refresh_registered_recorders()

    scheduler.add_job(func=polling_job(recorder_health_task), id="recorder_health_1",
                      trigger="interval", seconds=30, next_run_time=datetime.now() + timedelta(seconds=2),
                      replace_existing=True, max_instances=1, coalesce=True)
    # scheduler.add_job(func=polling_job(vcr_update_task), args=[], id="vcr_update_task_1", trigger="interval", seconds=10, replace_existing=True)

    # --------CVR设备信息定时同步--------
    # 先查找CVR父表是否有数据，如果有数据循环读取（CVRip），
    # 用CVRip去调用isapi来获取摄像头实时信息进行修改，如果不存在则进行添加操作
    @_publish_job
    def CVR_update_task():  # 运行的定时任务的函数
        with app.app_context():
            success, message = SchedulerTaskService.update_cvr_equipment_task()
            print(message)

    scheduler.add_job(func=polling_job(CVR_update_task), args=[], id="CVR_update_task_1", trigger="interval", minutes=10, replace_existing=True)
    # scheduler.add_job(func=polling_job(vcr_update_task), args=[], id="vcr_update_task_1", trigger="interval", seconds=10, replace_existing=True)


    # --------安防平台设备信息定时同步--------
    # 先查找安防平台表是否有数据，如果有数据循环读取信息
    # 用安防平台信息去调用Openapi-sdk来获取区域信息，如果不存在则进行添加操作
    @_publish_job
    def hik_security_platform_update_task():  # 定时任务函数
        with app.app_context():
            success, message = HikSecurityPlatformService.update_hik_security_platform_task()
            print(message)


    # scheduler.add_job(func=polling_job(hik_security_platform_update_task), args=[], id="hik_security_platform_update_task_1", trigger="interval", seconds=30, replace_existing=True)
    scheduler.add_job(func=polling_job(hik_security_platform_update_task), args=[], id="hik_security_platform_update_task_1", trigger="interval", minutes=20, replace_existing=True)


    #算法状态监控--正常，异常
    @_publish_job
    def monitorPoint_updata_task():
        print('-------------------------------------------算法状态监控-------------------------------------------')
        with app.app_context():
            success, message = SchedulerTaskService.monitor_algorithm_status_task()
            print(message)


    # scheduler.add_job(func=polling_job(monitorPoint_updata_task), args=[], id="monitorPoint_updata_task_1", trigger="interval", minutes=1, replace_existing=True)


    # 算法配置布防检测
    @_publish_job
    def algo_config_defense():
        print('-------------------------------------------算法配置布防检测-------------------------------------------\n')
        with app.app_context():
            success, message = SchedulerTaskService.algo_config_defense_task()
            print(message)

    # scheduler.add_job(func=polling_job(algo_config_defense), args=[], id="algo_config_defense_1", trigger="interval", minutes=5, replace_existing=True)

    # 日志七天删除定时任务
    @_publish_job
    def log_task():
        print('-------------------------------------------日志记录删除-------------------------------------------\n')
        with app.app_context():
            success, message = SchedulerTaskService.log_cleanup_task()
            print(message)

    scheduler.add_job(func=polling_job(log_task), args=[], id="log_task_1", trigger="interval", minutes=10, replace_existing=True)

    # 已删除的算法对应报警记录删除定时任务
    @_publish_job
    def algorithm_result_delete():
        print('-------------------------------------------报警记录删除-------------------------------------------\n')
        with app.app_context():
            success, message = SchedulerTaskService.algorithm_result_delete_task()
            print(message)

    # scheduler.add_job(func=polling_job(algorithm_result_delete), args=[], id="algorithm_result_delete_1", trigger="interval", minutes=10, replace_existing=True)

    # 紫光华智定时数据同步
    @_publish_job
    def sync_ziguang_devices():
        with app.app_context():
            service = ZiguangVMSService()
            success, message = service.sync_ziguang_devices_task()
            print(message)
    scheduler.add_job(func=polling_job(sync_ziguang_devices), args=[], id="sync_ziguang_devices_1", trigger="interval", minutes=30, replace_existing=True)



    @_publish_job
    def computing_equipment_task():
        print('-------------------------------------------算力设备状态监控-------------------------------------------')
        with app.app_context():
            success, message = SchedulerTaskService.computing_equipment_status_task()
            print(message)

    scheduler.add_job(func=polling_job(computing_equipment_task), args=[], id="computing_equipment_task_1", trigger="interval", hours=2, replace_existing=True)

    @_publish_job
    def zlk_stream_check_task():
        print('-------------------------------------------ZLMediaKit流媒体检查-------------------------------------------')
        with app.app_context():
            success, message = SchedulerTaskService.zlk_stream_check_task()
            print(message)


    # scheduler.add_job(func=polling_job(zlk_stream_check_task), args=[], id="zlk_stream_check_task_1", trigger="interval", minutes=1,replace_existing=True)
    scheduler.add_job(func=polling_job(zlk_stream_check_task), args=[], id="zlk_stream_check_task_1", trigger="interval", seconds=30, start_date=datetime.now() + timedelta(seconds=5), replace_existing=True, max_instances=1, coalesce=True)


    @_publish_job
    def algo_config_task():
        print('-------------------------------------------算法配置有效期状态监控-------------------------------------------')
        with app.app_context():
            success, message = SchedulerTaskService.algo_config_expiry_task()
            print(message)

    scheduler.add_job(func=polling_job(algo_config_task), args=[], id="algo_config_task_1", trigger="interval", days=1, replace_existing=True)
    # 报警信息语音播报定时任务
    @_publish_job
    def alarm_voice_broadcast_task():
        print('-------------------------------------------报警语音播报-------------------------------------------\n')
        with app.app_context():
            success, message = SchedulerTaskService.alarm_voice_broadcast_task()
            print(message)

    # 每1分钟检查一次新报警并播报
    # scheduler.add_job(func=polling_job(alarm_voice_broadcast_task), args=[], id="alarm_voice_broadcast_task_1", trigger="interval", seconds=15, replace_existing=True)

    # Durable deadlines are shared across Gunicorn workers and survive restarts.
    from service.diagnosis_scheduler import register_diagnosis_scheduler
    @_publish_job
    def setup_scheduler_tasks():
        return register_diagnosis_scheduler(app, scheduler)
    setup_scheduler_tasks()

    # Alarm media expires by the administrator's saved number of days only.
    from service.alarm_retention_service import run_alarm_cleanup
    @_publish_job
    def storage_cleanup_task():
        with app.app_context():
            run_alarm_cleanup()
    # The service decides under its shared DB lock whether the hourly check or
    # a bounded backlog continuation is due. A startup tick prevents web worker
    # reloads from restarting a one-hour wait before any cleanup can occur.
    scheduler.add_job(func=polling_job(storage_cleanup_task), id='storage_alarm_cleanup',
                      trigger='interval', minutes=1,
                      next_run_time=datetime.now() + timedelta(seconds=10),
                      coalesce=True, max_instances=1, misfire_grace_time=60,
                      replace_existing=True)
    # Independent periodic sampling; admission never depends on an open UI.
    from service.resource_admission import collect, policy
    @_publish_job
    def resource_admission_sample_task():
        with app.app_context():
            try:
                collect()
            except Exception:
                logging.getLogger(__name__).warning('Resource admission sampling unavailable', exc_info=False)
            finally:
                db.session.remove()
    scheduler.add_job(func=polling_job(resource_admission_sample_task), id='resource_admission_sample',
                      trigger='interval', seconds=policy()['sample_seconds'],
                      next_run_time=datetime.now() + timedelta(seconds=1),
                      coalesce=True, max_instances=1, misfire_grace_time=10, replace_existing=True)
    return {'camera_update_task': camera_update_task, 'vcr_update_task': vcr_update_task, 'CVR_update_task': CVR_update_task, 'hik_security_platform_update_task': hik_security_platform_update_task, 'monitorPoint_updata_task': monitorPoint_updata_task, 'algo_config_defense': algo_config_defense, 'log_task': log_task, 'algorithm_result_delete': algorithm_result_delete, 'sync_ziguang_devices': sync_ziguang_devices, 'computing_equipment_task': computing_equipment_task, 'zlk_stream_check_task': zlk_stream_check_task, 'algo_config_task': algo_config_task, 'alarm_voice_broadcast_task': alarm_voice_broadcast_task, 'setup_scheduler_tasks': setup_scheduler_tasks, 'storage_cleanup_task': storage_cleanup_task}
