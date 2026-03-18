#!/bin/bash
###############################################################################
# EEGTokenizer 自动迭代脚本（云服务器版本）
# 用法：./auto_iterate.sh <训练命令> [最大重试次数]
#
# 功能：
#   1. 运行训练
#   2. 如果失败，发送详细错误通知
#   3. 等待修复代码
#   4. 自动重新运行
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置
NIT_SSH_PORT="${NIT_SSH_PORT:-3022}"
TRAINING_CMD="$1"
MAX_RETRIES="${2:-1}"  # 默认只运行一次

SCRIPT_DIR="/root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts"
RUN_SCRIPT="${SCRIPT_DIR}/run_training.sh"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <训练命令> [最大重试次数]"
    echo ""
    echo "示例："
    echo "  $0 \"cd ~/EEGTokenizer && python train.py\""
    echo "  $0 \"cd ~/EEGTokenizer && python train.py\" 3"
    echo ""
    echo "说明："
    echo "  - 最大重试次数：失败后自动重试的次数（默认 1，即只运行一次）"
    echo "  - 设置为 0 表示无限重试，直到成功"
    exit 1
fi

log_info "========================================="
log_info "🔄 EEGTokenizer 自动迭代模式"
log_info "========================================="
log_info "nit 隧道端口: ${NIT_SSH_PORT}"
log_info "训练命令: ${TRAINING_CMD}"
log_info "最大重试: ${MAX_RETRIES}"
log_info "========================================="

RETRY_COUNT=0

while true; do
    RETRY_COUNT=$((RETRY_COUNT + 1))

    log_info "========================================="
    log_info "第 ${RETRY_COUNT} 次尝试运行..."
    log_info "========================================="

    # 运行训练（带错误捕获）
    if "${RUN_SCRIPT}" "${TRAINING_CMD}"; then
        # 成功
        log_info "========================================="
        log_info "🎉 训练成功完成！"
        log_info "========================================="

        # 发送成功通知
        curl -X POST "http://localhost:5000/webhook/eegtokenizer" \
          -H "Content-Type: application/json" \
          -d "{
            \"event\": \"iteration_completed\",
            \"status\": \"success\",
            \"project\": \"EEGTokenizer\",
            \"message\": \"自动迭代成功完成！共尝试 ${RETRY_COUNT} 次\",
            \"details\": {
              \"retry_count\": ${RETRY_COUNT},
              \"nit_port\": ${NIT_SSH_PORT}
            }
          }" 2>/dev/null || true

        exit 0
    else
        # 失败
        log_error "========================================="
        log_error "❌ 第 ${RETRY_COUNT} 次尝试失败"
        log_error "========================================="

        # 检查是否继续重试
        if [ "${MAX_RETRIES}" != "0" ] && [ $RETRY_COUNT -ge "${MAX_RETRIES}" ]; then
            log_error "已达到最大重试次数 (${MAX_RETRIES})，停止尝试"

            # 发送失败通知
            curl -X POST "http://localhost:5000/webhook/eegtokenizer" \
              -H "Content-Type: application/json" \
              -d "{
                \"event\": \"iteration_failed\",
                \"status\": \"failed\",
                \"project\": \"EEGTokenizer\",
                \"message\": \"自动迭代失败，已达到最大重试次数 (${MAX_RETRIES})\",
                \"details\": {
                  \"retry_count\": ${RETRY_COUNT},
                  \"max_retries\": ${MAX_RETRIES}
                }
              }" 2>/dev/null || true

            exit 1
        fi

        # 如果需要继续重试
        if [ "${MAX_RETRIES}" = "0" ] || [ $RETRY_COUNT -lt "${MAX_RETRIES}" ]; then
            log_error "等待修复后自动重试..."
            log_error "提示：修复代码后，此脚本将自动重新运行"

            # 发送重试通知
            curl -X POST "http://localhost:5000/webhook/eegtokenizer" \
              -H "Content-Type: application/json" \
              -d "{
                \"event\": \"waiting_for_fix\",
                \"status\": \"retrying\",
                \"project\": \"EEGTokenizer\",
                \"message\": \"第 ${RETRY_COUNT} 次尝试失败，等待修复后重试...\",
                \"details\": {
                  \"retry_count\": ${RETRY_COUNT},
                  \"max_retries\": ${MAX_RETRIES},
                  \"next_retry\": $((RETRY_COUNT + 1)),
                  \"suggestion\": \"请修复代码并推送到 GitHub\"
                }
              }" 2>/dev/null || true

            # 等待一段时间（让老板有时间修复代码）
            log_info "等待 30 秒后重试..."
            sleep 30
        fi
    fi
done
