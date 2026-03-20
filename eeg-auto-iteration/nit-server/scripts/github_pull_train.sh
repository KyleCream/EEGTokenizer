#!/bin/bash

###############################################################################
# GitHub Pull + 自动训练脚本（标记文件控制版本）
# 功能：检查标记文件，如果存在则运行训练
# 标记文件：.needs_training
# 注意：只推送日志，不推送 .pth 模型文件
###############################################################################

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")"
source "$CONFIG_DIR/config/config.sh"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$CRON_LOG"
}

log "========================================"
log "自动训练脚本启动（标记文件控制）"
log "========================================"

# 进入项目目录
cd "$PROJECT_DIR" || {
    log "错误：无法进入项目目录 $PROJECT_DIR"
    exit 1
}

# 标记文件路径
TRAINING_FLAG=".needs_training"

# 先拉取最新代码（无论是否有标志文件）
log "拉取最新代码..."
git pull origin $GIT_BRANCH >> "$CRON_LOG" 2>&1

if [ $? -ne 0 ]; then
    log "错误：git pull 失败"
    exit 1
fi

log "代码更新完成"

# 检查标记文件
if [ ! -f "$TRAINING_FLAG" ]; then
    log "没有检测到训练标记文件 ($TRAINING_FLAG)，退出"
    exit 0
fi

log "检测到训练标记文件，准备运行训练..."

# 读取标记文件内容（可能包含训练参数）
TRAINING_PARAMS=$(cat "$TRAINING_FLAG" 2>/dev/null)

if [ -n "$TRAINING_PARAMS" ]; then
    log "训练参数: $TRAINING_PARAMS"
    # 如果标记文件有内容，使用其中的参数
    TRAIN_ARGS="$TRAINING_PARAMS"
fi

if [ $? -ne 0 ]; then
    log "错误：git pull 失败"
    exit 1
fi

log "代码更新完成"

# 激活 Conda 环境
log "激活 Conda 环境: $CONDA_ENV_NAME"

# 初始化 conda
if [ -f "$CONDA_INIT" ]; then
    source "$CONDA_INIT"
    conda activate $CONDA_ENV_NAME
else
    log "警告：找不到 $CONDA_INIT，尝试使用 conda 命令"
    # 尝试使用 PATH 中的 python
    if [ -f "$PYTHON_PATH" ]; then
        export PATH="$HOME/conda/envs/$CONDA_ENV_NAME/bin:$PATH"
    else
        log "错误：找不到 Python 解释器 $PYTHON_PATH"
        exit 1
    fi
fi

# 验证 Python 环境
log "Python 版本: $(python --version)"
log "Python 路径: $(which python)"

# 运行训练
log "开始训练..."
log "训练脚本: $TRAIN_SCRIPT"
log "训练参数: $TRAIN_ARGS"

cd "$PROJECT_DIR"
python $TRAIN_SCRIPT $TRAIN_ARGS >> "$TRAINING_LOG" 2>&1

if [ $? -eq 0 ]; then
    log "训练完成"

    # 训练成功后删除标记文件
    log "删除训练标记文件"
    rm -f "$TRAINING_FLAG"

    # 只推送日志（不推送 .pth 模型文件）
    log "推送训练日志到 GitHub..."

    # 检查是否有日志文件
    if ls eegtokenizer_v2/logs/*.log 1> /dev/null 2>&1; then
        # 强制添加日志文件 (因为被 .gitignore 忽略)
        git add -f eegtokenizer_v2/logs/*.log >> "$CRON_LOG" 2>&1

        # 检查是否有待提交的内容
        if git diff --cached --quiet; then
            log "没有新的日志文件需要提交"
        else
            # 提交
            git commit -m "训练日志: $(date '+%Y-%m-%d %H:%M:%S')" >> "$CRON_LOG" 2>&1

            # 推送
            MAX_RETRIES=3
            RETRY_COUNT=0

            while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
                git push origin $GIT_BRANCH >> "$CRON_LOG" 2>&1
                if [ $? -eq 0 ]; then
                    log "推送成功"
                    break
                else
                    RETRY_COUNT=$((RETRY_COUNT + 1))
                    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                        log "推送失败，10秒后重试 ($RETRY_COUNT/$MAX_RETRIES)..."
                        sleep 10
                    else
                        log "推送失败，已达到最大重试次数"
                        exit 1
                    fi
                fi
            done
        fi
    else
        log "没有找到日志文件"
    fi

else
    log "错误：训练失败，查看日志: $TRAINING_LOG"
    log "保留训练标记文件以便下次重试"

    # 即使失败也尝试推送日志 (强制添加被 .gitignore 忽略的文件)
    if ls eegtokenizer_v2/logs/*.log 1> /dev/null 2>&1; then
        git add -f eegtokenizer_v2/logs/*.log >> "$CRON_LOG" 2>&1

        if git diff --cached --quiet; then
            log "没有新的日志文件需要提交"
        else
            git commit -m "训练失败日志: $(date '+%Y-%m-%d %H:%M:%S')" >> "$CRON_LOG" 2>&1
            git push origin $GIT_BRANCH >> "$CRON_LOG" 2>&1
        fi
    fi

    # 失败时不删除标志文件，以便下次重试
    exit 1
fi

log "========================================"
log "脚本执行完成"
log "========================================"
