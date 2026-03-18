#!/bin/bash
###############################################################################
# 快速同步代码到 nit（使用 rsync）
# 用法：./sync_code.sh [本地代码目录]
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置
NIT_SSH_PORT="${NIT_SSH_PORT:-3022}"
REMOTE_DIR="~/EEGTokenizer"
LOCAL_DIR="${1:-/root/.openclaw/workspace/EEGTokenizer}"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查本地目录
if [ ! -d "$LOCAL_DIR" ]; then
    log_error "本地目录不存在: $LOCAL_DIR"
    exit 1
fi

log_info "========================================="
log_info "📤 同步代码到 nit（rsync）"
log_info "========================================="
log_info "本地目录: ${LOCAL_DIR}"
log_info "远程目录: ${REMOTE_DIR}"
log_info "隧道端口: ${NIT_SSH_PORT}"
log_info "========================================="

# 检查隧道
log_info "检查隧道连接..."
if ! ssh -p "${NIT_SSH_PORT}" -o ConnectTimeout=5 localhost "echo OK" 2>/dev/null; then
    log_error "无法连接到 nit，请检查隧道状态"
    exit 1
fi
log_info "✓ 隧道连接正常"

# rsync 选项
RSYNC_OPTIONS=(
    -avz
    --progress
    --delete
    --exclude='.git/'
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='.DS_Store'
    --exclude='*.log'
    --exclude='results/'
    --exclude='checkpoints/'
    --exclude='data/'
    -e "ssh -p ${NIT_SSH_PORT}"
)

# 执行同步
log_info "开始同步..."
rsync "${RSYNC_OPTIONS[@]}" "${LOCAL_DIR}/" "localhost:${REMOTE_DIR}/"

log_info "========================================="
log_info "✅ 同步完成！"
log_info "========================================="

# 显示文件统计
log_info "远程目录文件统计："
ssh -p "${NIT_SSH_PORT}" localhost "cd ${REMOTE_DIR} && find . -type f | wc -l && du -sh ."
