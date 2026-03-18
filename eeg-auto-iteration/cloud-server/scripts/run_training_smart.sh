#!/bin/bash
###############################################################################
# EEGTokenizer 自动回环训练脚本（云服务器版本）- 支持智能环境检测
# 用法：./run_training_smart.sh <训练命令> [选项]
#
# 功能：
#   1. 通过 SSH 反向隧道连接到 nit
#   2. 自动从 GitHub 同步最新代码
#   3. 使用智能训练脚本（自动检测环境、等待 GPU）
#   4. 运行训练并完整捕获输出
#   5. 发送详细的结果通知到飞书
#   6. 失败时自动附带错误日志
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置（根据实际情况修改）
NIT_SSH_PORT="${NIT_SSH_PORT:-3022}"              # nit 隧道端口
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:5000/webhook/eegtokenizer}"
PROJECT_NAME="${PROJECT_NAME:-EEGTokenizer}"
AUTO_SYNC="${AUTO_SYNC:-true}"                   # 是否自动同步代码

# nit 上的代码目录和脚本位置
REPO_DIR="~/EEGTokenizer"
NIT_SCRIPT_DIR="~/eeg-auto-iteration/nit-server/scripts"
SMART_TRAIN_SCRIPT="${NIT_SCRIPT_DIR}/smart_train.sh"

# 日志文件路径
LOG_DIR="/root/.openclaw/workspace/eeg-auto-iteration/logs"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_LOG_FILE="${LOG_DIR}/run_${RUN_ID}.log"
ERROR_LOG_FILE="${LOG_DIR}/error_${RUN_ID}.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$RUN_LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$RUN_LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$RUN_LOG_FILE"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1" | tee -a "$RUN_LOG_FILE"
}

# 发送 Webhook 通知
send_notification() {
    local status="$1"
    local message="$2"
    local details_json="$3"
    local error_log_file="$4"

    local notification_data="{
        \"event\": \"training_completed\",
        \"status\": \"${status}\",
        \"project\": \"${PROJECT_NAME}\",
        \"message\": \"${message}\",
        \"details\": ${details_json}
    }"

    # 如果有错误日志，添加到通知中
    if [ -n "$error_log_file" ] && [ -f "$error_log_file" ]; then
        local error_content=$(tail -n 50 "$error_log_file" | head -c 2000)
        notification_data=$(echo "$notification_data" | jq --arg err "$error_content" \
            '.details.error_log = $err' 2>/dev/null || echo "$notification_data")
    fi

    log_info "发送通知到飞书..."
    curl -X POST "${WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -d "$notification_data" 2>/dev/null || log_warn "发送通知失败"
}

# 检查参数
if [ $# -lt 1 ]; then
    log_error "用法: $0 <训练命令>"
    echo ""
    echo "示例："
    echo "  $0 \"python train.py\""
    echo "  $0 \"python train.py --epochs 100 --lr 0.001\""
    echo ""
    echo "环境变量："
    echo "  NIT_SSH_PORT=3022         nit 隧道端口（默认 3022）"
    echo "  AUTO_SYNC=false          跳过代码自动同步（默认 true）"
    echo "  USE_GPU_QUEUE=false      不使用 GPU 队列（默认 true）"
    echo ""
    echo "说明："
    echo "  - 智能训练脚本会自动检测 Python 环境（虚拟环境/conda）"
    echo "  - 智能训练脚本会自动等待 GPU 空闲"
    echo "  - 无需手动指定 python 路径或 CUDA 设备"
    exit 1
fi

TRAINING_CMD="$1"

log_info "========================================="
log_info "🚀 EEGTokenizer 智能训练"
log_info "========================================="
log_info "运行 ID: ${RUN_ID}"
log_info "训练命令: ${TRAINING_CMD}"
log_info "自动同步: ${AUTO_SYNC}"
log_info "========================================="

# 检查隧道是否可用
log_step "检查 nit 连接..."
if ! ssh -p "${NIT_SSH_PORT}" -o ConnectTimeout=5 localhost "echo '隧道正常'" 2>/dev/null; then
    log_error "无法连接到 nit (端口 ${NIT_SSH_PORT})"

    send_notification "failed" "隧道连接失败" \
        "{\"error\": \"无法连接到 nit，请检查隧道状态\", \"tunnel_port\": \"${NIT_SSH_PORT}\"}"

    exit 1
fi
log_info "✓ 隧道连接正常"

# 获取 nit 信息
NIT_HOSTNAME=$(ssh -p "${NIT_SSH_PORT}" localhost "hostname" 2>/dev/null || echo "未知")
NIT_USER=$(ssh -p "${NIT_SSH_PORT}" localhost "whoami" 2>/dev/null || echo "未知")

log_info "nit 主机: ${NIT_HOSTNAME}"
log_info "nit 用户: ${NIT_USER}"

# 发送开始通知
log_step "发送开始通知..."
send_notification "started" "开始运行训练" \
    "{\"run_id\": \"${RUN_ID}\", \"nit_hostname\": \"${NIT_HOSTNAME}\", \"command\": \"${TRAINING_CMD}\"}"

# Step 1: 同步代码
if [ "$AUTO_SYNC" = "true" ]; then
    log_step "Step 1/3: 同步代码..."
    log_info "正在从 GitHub 拉取最新代码..."

    SYNC_CMD="
        if [ ! -d ${REPO_DIR} ]; then
            echo '克隆仓库...'
            git clone https://github.com/KyleCream/EEGTokenizer.git ${REPO_DIR} 2>&1
        else
            echo '拉取更新...'
            cd ${REPO_DIR}
            git fetch origin main 2>&1
            git reset --hard origin/main 2>&1
        fi
        echo '当前版本:'
        cd ${REPO_DIR}
        git log -1 --oneline 2>&1
    "

    if SYNC_OUTPUT=$(ssh -p "${NIT_SSH_PORT}" localhost "${SYNC_CMD}" 2>&1); then
        log_info "✓ 代码同步成功"
        echo "$SYNC_OUTPUT" | tee -a "$RUN_LOG_FILE"
    else
        log_error "✗ 代码同步失败"
        echo "$SYNC_OUTPUT" | tee -a "$RUN_LOG_FILE"

        send_notification "failed" "代码同步失败" \
            "{\"run_id\": \"${RUN_ID}\", \"error\": \"无法从 GitHub 拉取代码\"}" "$RUN_LOG_FILE"

        exit 1
    fi
else
    log_info "跳过代码同步（AUTO_SYNC=false）"
fi

# Step 2: 检查智能训练脚本是否存在
log_step "Step 2/3: 检查智能训练脚本..."

if ! ssh -p "${NIT_SSH_PORT}" localhost "test -f ${SMART_TRAIN_SCRIPT}" 2>/dev/null; then
    log_warn "未找到智能训练脚本: ${SMART_TRAIN_SCRIPT}"
    log_info "将使用标准方式运行训练..."
    USE_SMART_TRAIN=false
else
    log_info "✓ 找到智能训练脚本"
    USE_SMART_TRAIN=true
fi

# Step 3: 运行训练
log_step "Step 3/3: 运行训练并捕获输出..."
log_info "开始执行训练命令..."

START_TIME=$(date +%s)

# 创建远程临时日志文件
REMOTE_LOG_FILE="/tmp/eegtokenizer_run_${RUN_ID}.log"

# 构建训练命令
if [ "$USE_SMART_TRAIN" = "true" ]; then
    # 使用智能训练脚本（会自动检测环境、等待 GPU）
    REMOTE_CMD="
        cd ${REPO_DIR} 2>/dev/null || cd ~
        ${SMART_TRAIN_SCRIPT} \"${TRAINING_CMD}\"
    "
    log_info "使用智能训练模式（自动环境检测 + GPU 队列）"
else
    # 使用标准方式
    REMOTE_CMD="
        cd ${REPO_DIR} 2>/dev/null || cd ~
        ${TRAINING_CMD}
    "
    log_info "使用标准训练模式"
fi

# 在 nit 上运行命令，捕获所有输出
REMOTE_CMD_FULL="{ ${REMOTE_CMD}; } > ${REMOTE_LOG_FILE} 2>&1; echo \$? > /tmp/exit_code_${RUN_ID}"

# 执行远程命令
set +e
ssh -p "${NIT_SSH_PORT}" localhost "${REMOTE_CMD_FULL}" 2>&1 | tee -a "$RUN_LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))
SECONDS=$((DURATION % 60))

# 获取远程日志
log_info "获取远程日志..."

# 下载远程日志文件
ssh -p "${NIT_SSH_PORT}" localhost "cat ${REMOTE_LOG_FILE}" 2>/dev/null > "$RUN_LOG_FILE.full" 2>/dev/null || true

# 检查退出码
if [ $EXIT_CODE -eq 0 ]; then
    # 成功
    STATUS="success"
    MESSAGE="训练成功完成！"

    log_info "========================================="
    log_info "🎉 训练成功完成！"
    log_info "   总耗时: ${HOURS}h ${MINUTES}m ${SECONDS}s"
    log_info "========================================="

    send_notification "success" "${MESSAGE}" \
        "{\"run_id\": \"${RUN_ID}\", \"duration\": ${DURATION}, \"duration_formatted\": \"${HOURS}h ${MINUTES}m ${SECONDS}s\", \"log_file\": \"${RUN_LOG_FILE}\"}"

else
    # 失败
    STATUS="failed"
    MESSAGE="训练失败，请检查错误日志"

    log_error "========================================="
    log_error "❌ 训练失败！"
    log_error "   退出码: ${EXIT_CODE}"
    log_error "   耗时: ${DURATION}秒"
    log_error "========================================="

    # 下载错误日志
    ssh -p "${NIT_SSH_PORT}" localhost "cat ${REMOTE_LOG_FILE}" 2>/dev/null > "$ERROR_LOG_FILE" 2>/dev/null || true

    # 发送失败通知（包含错误日志）
    send_notification "failed" "${MESSAGE}" \
        "{\"run_id\": \"${RUN_ID}\", \"exit_code\": ${EXIT_CODE}, \"duration\": ${DURATION}, \"error\": \"训练失败，退出码 ${EXIT_CODE}\"}" "$ERROR_LOG_FILE"

    # 显示错误日志摘要
    if [ -f "$ERROR_LOG_FILE" ]; then
        log_error "错误日志摘要："
        tail -n 30 "$ERROR_LOG_FILE" | tee -a "$RUN_LOG_FILE"
    fi
fi

# 清理远程临时文件
ssh -p "${NIT_SSH_PORT}" localhost "rm -f ${REMOTE_LOG_FILE} /tmp/exit_code_${RUN_ID}" 2>/dev/null || true

log_info "========================================="
log_info "运行日志: ${RUN_LOG_FILE}"
if [ "$STATUS" = "failed" ]; then
    log_error "错误日志: ${ERROR_LOG_FILE}"
fi
log_info "========================================="

exit $EXIT_CODE
