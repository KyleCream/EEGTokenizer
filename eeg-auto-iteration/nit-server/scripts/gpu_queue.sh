#!/bin/bash
###############################################################################
# GPU 队列管理脚本（nit 服务器版本）
# 用法：./gpu_queue.sh <训练命令>
#
# 功能：
#   1. 检查 GPU 是否空闲
#   2. 如果 GPU 被占用，等待直到空闲
#   3. GPU 空闲时自动运行训练
#   4. 支持超时和强制运行选项
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
GPU_MEMORY_THRESHOLD=90        # GPU 内存使用率阈值（%）
MAX_WAIT_TIME=7200             # 最大等待时间（秒，2小时）
CHECK_INTERVAL=30              # 检查间隔（秒）
FORCE_RUN=false                # 是否强制运行（忽略 GPU 占用）

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查参数
if [ $# -lt 1 ]; then
    log_error "用法: $0 <训练命令>"
    echo ""
    echo "选项："
    echo "  FORCE_RUN=true    强制运行（忽略 GPU 占用）"
    echo "  MAX_WAIT_TIME=xxx 最大等待时间（秒）"
    echo ""
    echo "示例："
    echo "  $0 \"cd ~/EEGTokenizer && python train.py\""
    echo "  FORCE_RUN=true $0 \"cd ~/EEGTokenizer && python train.py\""
    echo "  MAX_WAIT_TIME=3600 $0 \"cd ~/EEGTokenizer && python train.py\""
    exit 1
fi

TRAINING_CMD="$1"

# 检查 nvidia-smi 是否可用
if ! command -v nvidia-smi &> /dev/null; then
    log_error "未找到 nvidia-smi，无法检测 GPU 状态"
    log_error "请确认 NVIDIA 驱动已安装"
    exit 1
fi

# 检查 GPU 函数
check_gpu() {
    # 获取 GPU 使用情况
    local gpu_info=$(nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null)

    if [ -z "$gpu_info" ]; then
        log_error "无法获取 GPU 信息"
        return 1
    fi

    # 解析 GPU 信息
    local gpu_index=$(echo "$gpu_info" | cut -d',' -f1 | xargs)
    local gpu_name=$(echo "$gpu_info" | cut -d',' -f2 | xargs)
    local mem_used=$(echo "$gpu_info" | cut -d',' -f3 | xargs)
    local mem_total=$(echo "$gpu_info" | cut -d',' -f4 | xargs)
    local gpu_util=$(echo "$gpu_info" | cut -d',' -f5 | xargs)

    # 计算内存使用率
    local mem_usage_percent=$((mem_used * 100 / mem_total))

    # 检查是否有活跃进程
    local processes=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null)

    # 判断 GPU 是否空闲
    local is_idle=false
    if [ "$mem_usage_percent" -lt "$GPU_MEMORY_THRESHOLD" ] && [ -z "$processes" ]; then
        is_idle=true
    fi

    # 返回结果
    echo "$is_idle|$gpu_index|$gpu_name|$mem_used|$mem_total|$mem_usage_percent|$gpu_util|$processes"
}

# 显示 GPU 状态
show_gpu_status() {
    local status="$1"
    IFS='|' read -r is_idle gpu_index gpu_name mem_used mem_total mem_usage_percent gpu_util processes <<< "$status"

    echo "========================================="
    echo "🖥️  GPU 状态"
    echo "========================================="
    echo "GPU ID:    $gpu_index"
    echo "GPU 名称:  $gpu_name"
    echo "显存使用:  $mem_used / $mem_total MiB ($mem_usage_percent%)"
    echo "GPU 利用:  $gpu_util%"
    echo "========================================="

    if [ -n "$processes" ]; then
        echo "🔴 当前运行的 GPU 进程："
        echo "$processes"
        echo "========================================="
    else
        echo "✅ 无活跃 GPU 进程"
        echo "========================================="
    fi

    if [ "$is_idle" = "true" ]; then
        echo "✅ GPU 空闲，可以运行训练"
    else
        echo "⚠️  GPU 忙碌，等待空闲..."
    fi
    echo ""
}

# 主逻辑
log_info "========================================="
log_info "🚀 GPU 队列管理器"
log_info "========================================="
log_info "训练命令: ${TRAINING_CMD}"
log_info "GPU 阈值: ${GPU_MEMORY_THRESHOLD}%"
log_info "最大等待: ${MAX_WAIT_TIME}秒"
log_info "强制运行: ${FORCE_RUN}"
log_info "========================================="
echo ""

# 如果强制运行，跳过检查
if [ "$FORCE_RUN" = "true" ]; then
    log_warn "⚠️  强制运行模式，忽略 GPU 占用"
    log_warn "⚠️  可能会导致显存不足！"
    echo ""

    eval "$TRAINING_CMD"
    exit $?
fi

# 正常模式：等待 GPU 空闲
log_info "开始检查 GPU 状态..."
echo ""

START_TIME=$(date +%s)

while true; do
    # 检查 GPU
    GPU_STATUS=$(check_gpu)

    if [ $? -ne 0 ]; then
        log_error "检查 GPU 失败"
        exit 1
    fi

    IFS='|' read -r is_idle gpu_index gpu_name mem_used mem_total mem_usage_percent gpu_util processes <<< "$GPU_STATUS"

    # 显示 GPU 状态
    show_gpu_status "$GPU_STATUS"

    # 如果 GPU 空闲，运行训练
    if [ "$is_idle" = "true" ]; then
        log_info "✅ GPU 空闲，开始运行训练！"
        echo ""

        eval "$TRAINING_CMD"
        exit $?
    fi

    # 检查是否超时
    CURRENT_TIME=$(date +%s)
    ELAPSED_TIME=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED_TIME -ge $MAX_WAIT_TIME ]; then
        log_error "⏰ 等待超时（${MAX_WAIT_TIME}秒）"
        log_error "GPU 仍然繁忙"
        echo ""
        log_error "选项："
        log_error "  1. 使用 FORCE_RUN=true 强制运行"
        log_error "  2. 增加 MAX_WAIT_TIME"
        log_error "  3. 手动停止占用 GPU 的进程"
        exit 1
    fi

    # 计算剩余等待时间
    REMAINING_TIME=$((MAX_WAIT_TIME - ELAPSED_TIME))
    log_info "⏳ 等待 GPU 空闲...（已等待 ${ELAPSED_TIME}秒，最多再等 ${REMAINING_TIME}秒）"
    echo ""

    # 等待一段时间后再次检查
    sleep "$CHECK_INTERVAL"
done
