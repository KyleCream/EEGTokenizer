#!/bin/bash

###############################################################################
# GitHub Pull + 自动训练脚本（每次都运行版本）
# 功能：每次都拉取最新代码并运行训练（不管有没有更新）
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
log "自动训练脚本启动（每次都运行）"
log "========================================"

# 进入项目目录
cd "$PROJECT_DIR" || {
    log "错误：无法进入项目目录 $PROJECT_DIR"
    exit 1
}

# 总是拉取最新代码
log "拉取最新代码..."
git fetch origin $GIT_BRANCH >> "$CRON_LOG" 2>&1
git reset --hard origin/$GIT_BRANCH >> "$CRON_LOG" 2>&1

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
else
    log "错误：训练失败，查看日志: $TRAINING_LOG"
    exit 1
fi

# 推送结果回 GitHub（可选）
log "推送训练结果回 GitHub..."
git add eegtokenizer_v2/logs/ eegtokenizer_v2/checkpoints/ >> "$CRON_LOG" 2>&1
git commit -m "训练结果: $(date '+%Y-%m-%d %H:%M:%S')" >> "$CRON_LOG" 2>&1
git push origin $GIT_BRANCH >> "$CRON_LOG" 2>&1

log "========================================"
log "脚本执行完成"
log "========================================"
