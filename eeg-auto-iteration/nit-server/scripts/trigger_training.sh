#!/bin/bash

###############################################################################
# 触发训练脚本
# 功能：创建标记文件，触发下一次 Cron 运行时训练
###############################################################################

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")"
source "$CONFIG_DIR/config/config.sh"

# 进入项目目录
cd "$PROJECT_DIR" || {
    echo "错误：无法进入项目目录 $PROJECT_DIR"
    exit 1
}

# 标记文件路径
TRAINING_FLAG=".needs_training"

# 创建标记文件
echo "$@" > "$TRAINING_FLAG"

echo "========================================="
echo "训练已触发"
echo "========================================="
echo ""
echo "标记文件已创建: $TRAINING_FLAG"
echo ""

if [ $# -gt 0 ]; then
    echo "训练参数: $@"
    echo ""
fi

echo "下次 Cron 运行时（每30分钟）将自动开始训练"
echo "或立即运行:"
echo "  cd $SCRIPT_DIR"
echo "  ./github_pull_train.sh"
echo ""
