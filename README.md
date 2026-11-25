# AIP 视频分析平台

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
