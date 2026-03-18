#!/bin/bash
###############################################################################
# SSH 反向隧道维护脚本（nit 服务器版本）
# 用法：nohup ./maintain_tunnel.sh > tunnel.log 2>&1 &
#
# 前置条件：
#   1. 在云服务器上添加 nit 的 SSH 公钥
#   2. 修改下面的配置信息
###############################################################################

# ==================== 配置区域 ====================
# 请根据实际情况修改以下配置

# 云服务器信息
CLOUD_SERVER="root@<你的云服务器公网IP>"  # 必须修改！
CLOUD_SSH_PORT=22                         # 云服务器 SSH 端口（通常为 22）
TUNNEL_PORT=3022                          # 在云服务器上映射的端口

# nit 信息
REMOTE_USER="你的用户名"                   # nit 上的用户名

# ==================== 配置结束 ====================

# 日志配置
LOG_DIR="$HOME/tunnel_logs"
LOG_FILE="$LOG_DIR/tunnel_$(date +%Y%m%d).log"
PID_FILE="$HOME/.tunnel_pid"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "SSH 反向隧道维护脚本启动"
log "========================================="
log "云服务器: $CLOUD_SERVER"
log "隧道端口: $TUNNEL_PORT"
log "日志文件: $LOG_FILE"
log "========================================="

# 检查是否已经有实例在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        log "警告：检测到已有实例在运行 (PID: $OLD_PID)"
        log "如果需要重新启动，请先运行: kill $OLD_PID && rm $PID_FILE"
        exit 1
    else
        log "清理旧的 PID 文件..."
        rm -f "$PID_FILE"
    fi
fi

# 保存当前 PID
echo $$ > "$PID_FILE"

# 设置中断处理
cleanup() {
    log "收到退出信号，正在清理..."
    rm -f "$PID_FILE"
    log "隧道脚本已退出"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 主循环
RECONNECT_DELAY=5  # 初始重连延迟
MAX_DELAY=60       # 最大重连延迟

while true; do
    log "正在建立反向隧道..."

    # 建立 SSH 反向隧道
    ssh -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ConnectTimeout=10 \
        -p "$CLOUD_SSH_PORT" \
        -R "${TUNNEL_PORT}:localhost:22" \
        -N "$CLOUD_SERVER"

    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        log "隧道正常关闭"
    else
        log "隧道异常断开 (退出码: $EXIT_CODE)"
    fi

    log "等待 ${RECONNECT_DELAY} 秒后重连..."

    # 等待后重连
    sleep "$RECONNECT_DELAY"

    # 指数退避，避免频繁重连
    if [ "$RECONNECT_DELAY" -lt "$MAX_DELAY" ]; then
        RECONNECT_DELAY=$((RECONNECT_DELAY * 2))
    fi
done
