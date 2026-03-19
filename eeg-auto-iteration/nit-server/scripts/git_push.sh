#!/bin/bash

###############################################################################
# Git 推送脚本（带重试）
# 功能：自动提交并推送到 GitHub，支持重试
###############################################################################

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 添加并提交
log "添加文件到 Git..."
git add "$@"

if [ $? -ne 0 ]; then
    log "错误：git add 失败"
    exit 1
fi

# 检查是否有变更
if git diff --cached --quiet; then
    log "没有需要提交的变更"
    exit 0
fi

# 提交
log "提交变更..."
git commit -m "$@"

if [ $? -ne 0 ]; then
    log "错误：git commit 失败"
    exit 1
fi

# 推送（带重试）
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    log "推送到 GitHub (尝试 $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
    git push origin main

    if [ $? -eq 0 ]; then
        log "✓ 推送成功！"
        exit 0
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            log "推送失败，10秒后重试..."
            sleep 10
        else
            log "❌ 推送失败，已达到最大重试次数 ($MAX_RETRIES)"
            exit 1
        fi
    fi
done
