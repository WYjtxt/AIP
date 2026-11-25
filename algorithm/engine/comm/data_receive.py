# host-identity-scheduler-v1
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  # 把项目根目录加入路径

from dbutils.pooled_db import PooledDB
from urllib.parse import quote
import copy
import ast
import logging
import os
import pymysql
from config import common as cm

# ======================================================================
# algorithm_path 本地化兜底映射（算能 BM1684X 移植）
# 平台数据库里的 algorithm_path 常与盒子实际不符：
#   · 旧 RK3588 的 .rknn 路径；
#   · .bmodel 但目录不对（平台写 /data2/model_algorithm_package/，盒上在
#     /data/AIGO/platform_start/model_algorithm_package/）或文件名日期段不同版本。
# 映射顺序：① 本地模型目录找同名文件；② 去掉 8 位日期段模糊匹配（取最新）；
# ③ 仍找不到回退默认 bmodel（人员计数模型）。
# ======================================================================
import glob as _glob
import re as _re

_BMODEL_DIR = str(Path(__file__).parent.parent / 'models' / 'BM1684X')
_LOCAL_BMODEL_DIRS = [str(Path(__file__).resolve().parents[2] / 'model_algorithm_package'), _BMODEL_DIR]
def _map_algorithm_path(path):
    """Resolve the exact uploaded BMODEL name; never substitute another algorithm."""
    if not path or not str(path).lower().endswith('.bmodel') or os.path.isfile(path):
        return path
    name = os.path.basename(str(path))
    for directory in _LOCAL_BMODEL_DIRS:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    return path


# sql数据库配置信息（MySQL 8.0，来自 config/ApiConfig.ini）
db_host = cm.db_host
db_port = int(cm.db_port)
db_user = cm.db_user
db_password = cm.db_password
db_name = cm.db_name

pool = PooledDB(
    creator=pymysql,          # 使用 pymysql 连接 MySQL 8.0
    maxconnections=30,        # 最大连接数
    mincached=2,              # 启动时创建的空闲连接
    maxcached=5,              # 池中最大空闲连接
    blocking=True,            # 连接用完时阻塞等待
    ping=1,                   # 取用连接前 ping 检测存活，断连自动重建
    host=db_host,
    port=db_port,
    user=db_user,
    password=db_password,
    database=db_name,
    charset='utf8mb4',
    read_timeout=10,
    write_timeout=10,
)




# ======================================================================
# rtsp_url 组装：按 t_equipment 的 equipment_type × 厂商决定取流格式
#   · 录像机(NVR 下的通道)：设备行的 equipment_ip 是摄像头自身 IP，取流必须走
#     所属录像机（t_vcr_data，经 d.VCR_data_id 联查）：IP/账号用 vcr_ip/vcr_username/
#     vcr_password，厂商用 vcr_type（缺省回退 manufacturer_type）。通道：海康优先用
#     code 通道编码（如 '801'=8 通道主码流，无 code 用 aisles*100+1）；大华
#     realmonitor?channel=aisles；宇视 /unicast/c<aisles>/s0/live。
#     注意 vcr_port 是 SDK/HTTP 端口（如 80），RTSP 固定用 554。
#   · 摄像头/特殊摄像头(IPC 直连)：用设备自身 IP/账号——海康 /Streaming/Channels/101；
#     大华 channel=1；宇视 /video1；端口优先 equipment_port，空则 554。
#   · AI单光/AI双光摄像头（阳光三极自研）：走盒内 mediamtx 汇聚，固定 :8554/stream11
#   · 其余类型/厂商暂不支持取流，返回 None（同一组合只提示一次）
# ======================================================================
_VENDOR_URL_WARNED = set()


def _build_rtsp_url(i):
    '''按设备类型×厂商组装 RTSP 取流地址；拿不到 IP 或类型/厂商未覆盖返回 None。'''
    # native_hik_stream integration
    if str(i.get('equipment_type')) == '安防平台':
        from comm.algorithm_platform_source import HikStreamReference
        platform = {key: i.get(key) for key in ('hik_host', 'hik_port', 'hik_appKey', 'hik_appSecret', 'hik_artemis')}
        return HikStreamReference(platform, i.get('Hik_indexCode'),
                                  i.get('stream_type'), i.get('Hik_rtsp_url'))
    etype = i.get('equipment_type')
    etype_s = str(etype or '')

    # 阳光三极自研 AI 相机（旧 RK 平台 equipment_type 为数字 1，一并兼容）
    if etype_s in ('AI单光摄像头', 'AI双光摄像头') or etype in (1, '1'):
        ip = i.get('equipment_ip')
        if not ip:
            return None
        uname = i.get('equipment_uname') or ''
        pw = i.get('equipment_password') or ''
        auth = f"{quote(uname)}:{quote(pw)}@" if uname else ''
        return f"rtsp://{auth}{quote(str(ip))}:8554/stream11"

    is_nvr = etype_s == '录像机'
    if is_nvr:
        # 走所属录像机取流；平台老数据可能没配 t_vcr_data，回退设备自身字段
        manu = str(i.get('vcr_type') or i.get('manufacturer_type') or '')
        ip = i.get('vcr_ip') or i.get('equipment_ip')
        uname = i.get('vcr_username') or i.get('equipment_uname') or ''
        pw = i.get('vcr_password') or i.get('equipment_password') or ''
        port = 554
    else:
        manu = str(i.get('manufacturer_type') or '')
        ip = i.get('equipment_ip')
        uname = i.get('equipment_uname') or ''
        pw = i.get('equipment_password') or ''
        port = i.get('equipment_port') or 554
    if not ip:
        return None
    auth = f"{quote(uname)}:{quote(pw)}@" if uname else ''
    host = f"{quote(str(ip))}:{port}"

    try:
        aisle = int(i.get('equipment_aisles') or 0)
    except (TypeError, ValueError):
        aisle = 0
    code = str(i.get('code') or '').strip()

    if etype_s in ('录像机', '摄像头', '特殊摄像头'):
        if manu == '海康':
            if is_nvr:
                ch = code if code.isdigit() else (f"{aisle}01" if aisle else '101')
                if i.get('stream_type') in ('main','sub') and len(ch)>2:
                    ch = ch[:-2] + ('02' if i['stream_type']=='sub' else '01')
            else:
                ch = '101'
            auth = f"{quote(uname,safe='')}:{quote(pw,safe='')}@" if uname else ''
            return f"rtsp://{auth}{host}/Streaming/Channels/{ch}"
        if manu == '大华':
            ch = aisle if (is_nvr and aisle) else 1
            return f"rtsp://{auth}{host}/cam/realmonitor?channel={ch}&subtype=0"
        if manu == '宇视':
            if is_nvr:
                return f"rtsp://{auth}{host}/unicast/c{aisle or 1}/s0/live"
            return f"rtsp://{auth}{host}/video1"

    key = (etype_s, manu)
    if key not in _VENDOR_URL_WARNED:
        _VENDOR_URL_WARNED.add(key)
        print('[data_receive] 未支持的取流组合 equipment_type=%r 厂商=%r，rtsp_url 置 None'
              % (etype_s, manu))
    return None


def _build_push_url(equipment_id):
    '''推流（AI 标注输出）地址：固定推向配置的上传服务器，
    与录像机/摄像头拉流地址完全解耦。'''
    upload_ip = str(cm.upload_ip or '').strip()
    if not upload_ip or equipment_id is None:
        return None
    return f"rtsp://{upload_ip}:8554/stream/{equipment_id}"


# 转换成袁总格式数据
def convert_data_format(res):
    '''把区域配置列表转换为 [{'type': 区域名, 'data': [点...]}] 的嵌套格式（剔除 type/color 键）。'''
    result = []
    for group in res:
        if not group:
            continue
        common_type = group[0]['type']
        # 使用列表推导式删除 'type' 键
        data_without_type = [{k: v for k, v in item.items() if k != 'type' and k != 'color'} for item in group]
        data = {'type': common_type, 'data': data_without_type}
        result.append([data])
    return result


# 获取所需数据

def _resolve_computing_id(cursor):
    """Stable host identity first; old IP is used only for unbound legacy hosts."""
    from comm.platform_host_identity import read_host_identity, resolve_device, IdentityConflict
    state=getattr(_resolve_computing_id,'_identity_state',{})
    _resolve_computing_id._identity_state=state
    try:
        device=resolve_device(cursor,read_host_identity(),getattr(cm,'localhost_ip',None))
        if device is None:raise IdentityConflict('本机未登记，保留现有任务并等待重新绑定')
        cid=device['computing_id']
    except Exception as error:
        reason=str(error) if isinstance(error,IdentityConflict) else type(error).__name__
        count=state.get('errors',0)
        if reason!=state.get('reason') or count%60==0:logging.error('设备身份解析失败: %s',reason)
        state.update(errors=count+1,reason=reason)
        return None
    if state.get('id')!=cid:
        logging.info('computing_id 按 %s 解析为 %s',device['source'],cid)
        state['id']=cid
    state.update(errors=0,reason=None)
    return cid


def get_data():
    '''从 MySQL 读取全部启用中的算法配置（多表 JOIN），并解析区域/模型列表、拼接 rtsp_url。
    返回配置 dict 列表；数据库读取异常返回 None（调用方据此保活进程、下轮重试）。'''
    conn = None
    cursor = None
    try:
        # 1️⃣ 从连接池获取连接
        conn = pool.connection()
        cursor = conn.cursor()
        # 注意：不能再按 b.algorithm_trade_type = 1 过滤——现平台库里算法的
        # algorithm_trade_type 全部为 '2'（旧 RK 平台才是 1），加了必查空；
        # 本盒的配置范围由 computing_id + status 界定即可。
        sql = """SELECT
            c.id AS Mine_id, c.mine_name, c.mine_code,
            d.id AS Equipment_id,
            d.equipment_name,
            d.equipment_type,
            d.manufacturer_type,
            d.equipment_port,
            d.Hik_indexCode, d.Hik_rtsp_url,
            hp.hik_host, hp.hik_port, hp.hik_appKey, hp.hik_appSecret, hp.hik_artemis,
            d.equipment_ip,
            d.equipment_aisles,
            d.code,
            d.online,
            d.GB28181_code,
            a.id AS Conf_id,
            a.Algorithm_library_id,
            a.conf_area,
            e.test_type_ename,
            e.test_type_cname,
            b.algorithm_status,
            b.algorithm_path,
            b.algorithm_name,
            b.analysis_type AS library_analysis_type,
            b.algorithm_type_list,
            b.algorithm_trade_type,
            a.status,
            a.conf_name,
            a.shield_status,
            a.tem_conf_area,
            a.draw_type,
            a.confidence,
            a.interval_time,
            a.duration_time,
            a.image_draw_type,
            a.scene_typename,
            a.sensitivity,
            a.image_count,
            a.template_list_area,
            a.computing_id,
            r.dev_id AS dev_id,
            a.template_data,
            a.conf_status,
            a.stream_type,
            a.res_type,
            a.template_small_id,
            h.template_small_name,
            a.model_status,
            a.amp,
            a.alg_select_type,
            a.cross_line_area,
            a.model_two_data,
            a.model_algo_data,
            g.model_name AS template_name,
            g.model_type AS template_type,
            g.model_template_config_type_id AS template_config_type_id,
            a.label_list,
            conf_img_resolution,
            defense_time_start,
            defense_time_end,
            g.model_conf_list AS template_model_conf_list,
            g.id AS template_id,
            h.list_data, 
            d.equipment_uname,
            d.equipment_password,
            v.vcr_type,
            v.vcr_ip,
            CASE WHEN p.equipment_ip=v.vcr_ip AND p.VCR_data_id=v.id
                      AND (p.user_status='1' OR p.user_status IS NULL)
                      AND (d.user_status='1' OR d.user_status IS NULL)
                 THEN COALESCE(NULLIF(v.vcr_port, 0),80) END AS recorder_api_port,
            v.vcr_username,
            v.vcr_password,
            d.person_count_url,
            a.all_Entering_num,
            a.all_Exiting_num 
            FROM `t_algorithm_config` AS a 
            JOIN `t_algorithm_library` AS b ON a.Algorithm_library_id = b.id 
            JOIN `t_mine` AS c ON a.Mine_id = c.id
            JOIN `t_equipment` AS d ON a.Equipment_id = d.id 
            LEFT JOIN t_hik_security_platform_up_area ha ON d.Hik_id = ha.id
            LEFT JOIN t_hik_security_platform_info hp ON ha.hik_info_id = hp.id
            JOIN `t_algorithm_test_type` AS e ON a.Algorithm_test_type_id = e.id 
            LEFT JOIN `t_model_template_config` AS g ON a.model_template_config_id = g.id
            LEFT JOIN `t_model_template_small` AS h ON a.template_small_id = h.id
            LEFT JOIN `t_vcr_data` AS v ON d.VCR_data_id = v.id
            LEFT JOIN `t_equipment` AS p ON p.id=d.parent_id
            LEFT JOIN `t_resource_usage` AS r ON a.resource_id = r.id
            WHERE a.computing_id = %s and a.status = 1;"""
        
        cid = _resolve_computing_id(cursor)
        if cid is None: return None
        cursor.execute(sql, (cid,))

        # 2️⃣ 防御 cursor.description
        if cursor.description is None:
            print("cursor.description is None，数据库连接异常")
            return None  # 出错（非"空配置"）：调用方据此保活进程、下轮重试

        columns = [i[0] for i in cursor.description]
        results = cursor.fetchall()
        # print(f"results:{results}")
        result_dict_list = [dict(zip(columns, row)) for row in results]
        all_cname_list=[]
        updated_result_dict_list = []
        # print(f"result_dict_list:{result_dict_list}")
        for i in result_dict_list:
            updated_dict = copy.deepcopy(i)

            # 0️⃣ rknn → bmodel 兜底映射（主模型）
            updated_dict['algorithm_path'] = _map_algorithm_path(i.get('algorithm_path'))

            algorithm_library_id = i.get('Algorithm_library_id')
            if algorithm_library_id:
                label_sql = "SELECT test_type_cname FROM t_algorithm_test_type WHERE Algorithm_library_id = %s"
                cursor.execute(label_sql, (algorithm_library_id,))
                label_results = cursor.fetchall()
                updated_dict['test_type_cname_list'] = [label[0] for label in label_results if label[0]]
            else:
                updated_dict['test_type_cname_list'] = []


            # 3️⃣ conf_area
            try:
                updated_dict['conf_area'] = convert_data_format(
                    ast.literal_eval(i['conf_area'])
                ) if i.get('conf_area') else []
            except Exception:
                updated_dict['conf_area'] = []

            # 4️⃣ template_list_area
            try:
                updated_dict['template_list_area'] = convert_data_format(
                    ast.literal_eval(i['template_list_area'])
                ) if i.get('template_list_area') else []
            except Exception:
                updated_dict['template_list_area'] = []

            # 5️⃣ model_algo_data
            try:
                model_algo_list = ast.literal_eval(
                    i['model_algo_data']
                ) if i.get('model_algo_data') else []
            except Exception:
                model_algo_list = []

            for item in model_algo_list:
                if not isinstance(item, dict):
                    continue

                # rknn → bmodel 兜底映射（单路多模的子模型）
                item['algorithm_path'] = _map_algorithm_path(item.get('algorithm_path'))

                # algorithm_type_list
                try:
                    item["algorithm_type_list"] = ast.literal_eval(
                        item.get("algorithm_type_list", "[]")
                    )
                except Exception:
                    item["algorithm_type_list"] = []

                # label_list
                try:
                    label_str = item.get("label_list", "[]").replace("\\", "")
                    item["label_list"] = ast.literal_eval(label_str)
                except Exception:
                    item["label_list"] = []

            updated_dict['model_algo_data'] = str(model_algo_list)

            # 6️⃣ rtsp_url：按 equipment_type × manufacturer_type 组装（见 _build_rtsp_url）
            try:
                updated_dict['rtsp_url'] = _build_rtsp_url(i)
            except Exception as e:
                print("rtsp_url 生成失败 conf_name=%s err=%s"
                      % (i.get('conf_name'), repr(e)))
                updated_dict['rtsp_url'] = None

            # 7️⃣ push_url（AI 标注输出推流地址），并回写 t_equipment.person_count_url。
            # get_data 每 5s 轮询一次，仅在值变化时 UPDATE，避免每轮写库。
            push_url = _build_push_url(i.get('Equipment_id'))
            updated_dict['push_url'] = push_url
            if push_url and push_url != i.get('person_count_url'):
                try:
                    cursor.execute(
                        "UPDATE t_equipment SET person_count_url=%s WHERE id=%s",
                        (push_url, i['Equipment_id']))
                    conn.commit()
                    print('[data_receive] person_count_url 已回写 Equipment_id=%s -> %s'
                          % (i['Equipment_id'], push_url))
                except Exception as e:
                    print('person_count_url 回写失败 Equipment_id=%s err=%s'
                          % (i.get('Equipment_id'), repr(e)))

            updated_result_dict_list.append(updated_dict)

        return updated_result_dict_list

    except Exception as e:
        print("get_data 执行异常: %s", repr(e))
        return None  # 出错（非"空配置"）：调用方据此保活进程、下轮重试

    finally:
        # ❗确保连接归还
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    print(get_data())








