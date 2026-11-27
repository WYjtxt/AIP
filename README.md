# AIP 

本仓库收录 2026 年 11 月 25 日从运行环境核验的发布代码与配套资源。

| 目录 | 内容 |
| --- | --- |
| `frontend/` | 主站页面、发布版 JavaScript 和 CSS、源码映射及随包提供的 Vue 源文件 |
| `backend/` | 平台接口、数据模型、业务服务和数据库迁移 |
| `algorithm/engine/` | 算法启动程序、推理流程、后处理模板与通用组件 |
| `algorithm/packages/` | 现场模型包、权重、消息消费与推送代码 |
| `dispatch/` | 调度服务及其管理页面 |
| `media/` | 媒体服务、网页工具和构建信息 |
| `host/` | 宿主机服务、运维接口、推送队列、服务单元和备用程序 |
| `container-tools/` | 各服务容器携带的运行入口、工具与内置资源 |

查找主站或算法的生效实现时，从 `frontend/`、`backend/`、`algorithm/` 对应目录开始。`host/` 与 `container-tools/` 的同名文件按其部署位置保留。前端 `static/js/config.js` 保存了发布时所引用配置脚本的内容。

运行平台还需要对应版本的容器运行环境、数据库、消息服务、硬件驱动和部署配置。摄像机账号、服务口令和密钥应在部署环境中提供。

### 凭据配置

| 变量 | 使用位置 |
| --- | --- |
| `AIP_DB_PASSWORD`、`AIP_BOX_PASSWORD`、`AIP_ZLK_SECRET` | 安装器尚未写入相应配置时，分别为算法包提供数据库口令、主机口令和媒体服务密钥 |
| `AIP_INITIAL_ADMIN_PASSWORD`、`AIP_INITIAL_SECONDARY_PASSWORD` | 初始化对应平台账号时使用 |
| `AIP_ACTIVATION_KEY` | 后端激活校验 |
| `AIP_VQD_SFTP_PASSWORD` | 视频质量诊断工具的 SFTP 连接 |
| `AIP_COMPUTING_PASSWORD` | 计算设备配置 |
| `AIP_ONVIF_PASSWORD` | 独立运行 ONVIF 示例 |
| `AIP_CAMERA_PASSWORD` | 设备未单独指定密码时使用的可选默认值 |

## 录像资源优化与算力监控

算能算法按压缩字节限制报警录像缓存，大录像片段可临时落盘并逐帧编码。推理运行时沿用容器的 OpenCV 线程设置，只有持续空读时才增加轮询等待。x86_64 Linux 上可以从源码构建可选的原生加速库。[构建说明](algorithm/engine/runtime_acceleration/README.md)

算能采集器按宿主机的稳定标识归属板卡，云管中心用数据库时间判定卡数据的新鲜度。已有的海康安防平台长效地址及 8604 接入仍从原网关模块供预览和算法使用。

已有 Compose 基础环境可以用 `python3 algorithm/vendor_algorithms.py probe` 检查驱动，按厂商选择独立算法包。`verify` 核对包内容，`apply-auto` 从离线目录选择适配包并验收算法服务。本仓库沿用 `algorithm/engine` 和 `algorithm/packages` 作为公开算能源码目录，华为厂商包由相应交付介质提供。

## 原生部署

原生部署由 Linux 的 systemd 管理前后端、媒体、数据库、消息服务和算法进程。以下安装步骤适用于 **`V3.0.5-native` 完整交付包**。本仓库收录的现场版本采用 Docker Compose，当前 `3.0.8-261124-field5` 安装器仅提供容器模式。需要从零搭建原生环境时，请先取得带原生清单的对应版本介质。本仓库可直接用于下文的已安装站点自检。

### 1. 准备安装介质和目标机

- 在 Windows 上将同一版本的 `PlatformOneClickDeployer.exe`、`payload/` 和 `packages/` 放在同一目录。核对 `payload/native-release.json` 的 `release` 为 `V3.0.5-native`，且列出了目标架构的文件和 SHA-256。
- 介质应包含 `payload/platform_code.tar.gz`、`packages/<架构>/runtime_bundle.tar.gz`、该架构的系统及 Python 依赖，以及 `packages/native/<架构>/` 下的 `backend-runtime.tar.gz`、`frontend-runtime.tar.gz`、`media-runtime.tar.gz` 和 `gateway-runtime.tar.gz`。
- **Ubuntu 20.04 / x86_64** 主机只需算能驱动可正常识别设备。各厂商的板卡商品名可以不同，现场可用 `bm-smi` 查看驱动识别的设备。
- **openEuler 22.03 SP4 / aarch64** 已核对的硬件配置为昇腾 310P3。
- 准备可通过 SSH 登录的 root 或具备 sudo 权限的账号。新装使用空程序目录，默认 `/data/AIGO/platform_start`。已有容器部署标记的目录会被原生安装器拒绝。

历史 `V3.0.5-native` 的 x86 安装器会校验 BM1684X 芯片。使用其他算能芯片时，请按驱动识别的实际芯片选择适配的安装介质、运行库和 BMODEL。

### 2. 首次安装

1. 在 Windows 介质根目录打开 `PlatformOneClickDeployer.exe`，填写服务器 IP、SSH 端口及账号，点击“测试连接”。
2. 选择 **native（原生部署）**、**fresh（首次安装）**，确认“部署介质根目录”和“服务器平台程序目录”。离线安装选择 `offline`。按界面为数据库和 8899 调度管理员设置本站口令。
3. 点击“开始部署”。工具将介质传到目标机 `/root/oneclick`，校验架构和安装包，安装运行环境和 MySQL、Redis、Kafka，部署应用、网关及对应硬件的算法服务，并注册 systemd 单元。
4. 等待日志输出 **`DEPLOY_RESULT=PASS`**。服务清单写入程序目录下的 `native-deployment.json`。在受信任的管理终端打开 `https://<服务器IP>:8888/` 登录主平台，按现场流程完成机器授权；调度入口为 `https://<服务器IP>:8899/login`。首次主平台账号信息由安装器写入受限的 `initial-access.json`。

### 3. 验收服务和业务

在 Windows 原生交付包目录中可单独运行验证。将示例 IP 和 SSH 用户替换为本站值；工具会提示输入 SSH 密码。

```powershell
.\PlatformOneClickDeployer.exe --runtime native --ip 192.0.2.10 --ssh-user deploy --mode verify --data-root /data/AIGO/platform_start
```

也可在**已经完成原生安装**的 Linux 主机上，从本仓库根目录运行只读自检。此处须显式指定 `MODE=verify`，脚本省略模式时默认进入修复流程。

```bash
sudo env MODE=verify PLATFORM_DATA_ROOT=/data/AIGO/platform_start python3 container-tools/web/deploy_native.py
```

自检逐项检查登记的 systemd 服务，并要求主站首页、`/api/activate/activate_verify` 和调度登录页均返回 HTTP 200，成功时输出 **`VERIFY_RESULT=PASS`**。业务验收时，再选一路可用摄像机确认实时预览、任务持续出帧，并用已知样例核对一次报警及录像。这一步验证实际的硬件推理和视频链路。[服务与自检实现](container-tools/web/deploy_native.py)

### 4. 中断与修复

首次安装中断且配置目录已经生成时，保持原程序目录，查阅目标机 `/root/oneclick/logs/` 中对应的部署日志，解决报错后选 `repair` 续装。已有原生环境仅更新代码时使用 `platform`，完成后再次执行 `verify`。后端启动失败可从以下两条命令定位，其他服务可使用 `native-deployment.json` 中登记的单元名。

```bash
systemctl status ai-platform-backend --no-pager
sudo journalctl -u ai-platform-backend -n 100 --no-pager
```
