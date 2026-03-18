#!/bin/bash
###############################################################################
# SSH 隧道管理脚本（nit 服务器版本）
# 用法：
#   ./tunnel_manager.sh start    # 启动隧道
#   ./tunnel_manager.sh stop     # 停止隧道
#   ./tunnel_manager.sh status   # 查看状态
#   ./tunnel_manager.sh restart  # 重启隧道
#   ./tunnel_manager.sh log      # 查看日志
###############################################################################

TUNNEL_DIR="$(cd "$(dirname "$0")" && pwd)"
TUNNEL_SCRIPT="$TUNNEL_DIR/maintain_tunnel.sh"
PID_FILE="$HOME/.tunnel_pid"
LOG_DIR="$HOME/tunnel_logs"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查脚本是否存在
check_script() {
    if [ ! -f "$TUNNEL_SCRIPT" ]; then
        log_error "隧道脚本不存在: $TUNNEL_SCRIPT"
        exit 1
    fi

    if [ ! -x "$TUNNEL_SCRIPT" ]; then
        log_warn "脚本没有执行权限，正在添加..."
        chmod +x "$TUNNEL_SCRIPT"
    fi
}

# 启动隧道
start_tunnel() {
    check_script

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_warn "隧道已在运行 (PID: $PID)"
            exit 0
        else
            log_warn "清理旧的 PID 文件..."
            rm -f "$PID_FILE"
        fi
    fi

    log_info "启动 SSH 反向隧道..."

    # 使用 nohup 在后台运行
    nohup "$TUNNEL_SCRIPT" > /dev/null 2>&1 &

    # 等待一下，确保启动
    sleep 2

    if [ -f "$PID_FILE" ]; then
        NEW_PID=$(cat "$PID_FILE")
        log_info "✓ 隧道已启动 (PID: $NEW_PID)"
        log_info "日志目录: $LOG_DIR"
    else
        log_error "隧道启动失败，请检查日志"
        exit 1
    fi
}

# 停止隧道
stop_tunnel() {
    if [ ! -f "$PID_FILE" ]; then
        log_warn "隧道未运行"
        exit 0
    fi

    PID=$(cat "$PID_FILE")

    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_warn "隧道进程不存在，清理 PID 文件"
        rm -f "$PID_FILE"
        exit 0
    fi

    log_info "停止隧道 (PID: $PID)..."
    kill "$PID"

    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # 如果还没结束，强制 kill
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warn "强制停止隧道..."
        kill -9 "$PID"
    fi

    rm -f "$PID_FILE"
    log_info "✓ 隧道已停止"
}

# 重启隧道
restart_tunnel() {
    log_info "重启隧道..."
    stop_tunnel
    sleep 1
    start_tunnel
}

# 查看状态
status_tunnel() {
    if [ ! -f "$PID_FILE" ]; then
        echo "状态: 未运行"
        exit 0
    fi

    PID=$(cat "$PID_FILE")

    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "状态: 已停止（PID 文件存在但进程不存在）"
        echo "建议运行: $0 stop 清理 PID 文件"
        exit 1
    fi

    echo "状态: 运行中"
    echo "PID: $PID"
    echo "运行时间: $(ps -p "$PID" -o etime= | tr -d ' ')"

    # 检查 SSH 连接
    if ps aux | grep -q "ssh.*$PID.*3022"; then
        echo "SSH 隧道: 已建立"
    else
        echo "SSH 隧道: 未建立（可能在重连中）"
    fi

    # 显示最近的日志
    if [ -d "$LOG_DIR" ]; then
        LATEST_LOG=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            echo ""
            echo "最近日志 ($LATEST_LOG):"
            tail -n 5 "$LATEST_LOG"
        fi
    fi
}

# 查看日志
show_log() {
    if [ -d "$LOG_DIR" ]; then
        LATEST_LOG=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            log_info "显示日志: $LATEST_LOG"
            tail -f "$LATEST_LOG"
        else
            log_error "未找到日志文件"
            exit 1
        fi
    else
        log_error "日志目录不存在: $LOG_DIR"
        exit 1
    fi
}

# 主程序
case "$1" in
    start)
        start_tunnel
        ;;
    stop)
        stop_tunnel
        ;;
    restart)
        restart_tunnel
        ;;
    status)
        status_tunnel
        ;;
    log)
        show_log
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        echo ""
        echo "命令说明："
        echo "  start   - 启动隧道"
        echo "  stop    - 停止隧道"
        echo "  restart - 重启隧道"
        echo "  status  - 查看运行状态"
        echo "  log     - 实时查看日志"
        exit 1
        ;;
esac
