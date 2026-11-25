#!/bin/bash
# 等待所有 BM1684X 设备节点就绪后确保 aiplatform-algorithm-master 容器正常启动
set -u

CONTAINER="aiplatform-algorithm-master"
MAX_WAIT=300
INTERVAL=2

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "[aiplatform-sophon-ready] 容器 $CONTAINER 不存在，跳过"
    exit 0
fi

DEVICES=$(docker inspect "$CONTAINER" --format "{{range .HostConfig.Devices}}{{.PathOnHost}}{{\"\n\"}}{{end}}" | sed "/^$/d")

elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
    missing=0
    for dev in $DEVICES; do
        if [ ! -e "$dev" ]; then
            missing=1
            break
        fi
    done
    if [ "$missing" -eq 0 ]; then
        break
    fi
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done

if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "[aiplatform-sophon-ready] 等待加速卡设备超时 (${MAX_WAIT}s)，仍尝试启动 $CONTAINER" >&2
else
    echo "[aiplatform-sophon-ready] 所有加速卡设备已就绪 (耗时 ${elapsed}s)"
fi

running=$(docker inspect -f "{{.State.Running}}" "$CONTAINER" 2>/dev/null || echo "false")
if [ "$running" != "true" ]; then
    echo "[aiplatform-sophon-ready] 正在启动 $CONTAINER ..."
    docker start "$CONTAINER"
fi

sleep 3
running=$(docker inspect -f "{{.State.Running}}" "$CONTAINER" 2>/dev/null || echo "false")
echo "[aiplatform-sophon-ready] $CONTAINER 运行状态: $running"
[ "$running" = "true" ]
