#!/bin/bash

###############################################################################
# Cron 安装脚本（30分钟轮询版本）
# 功能：自动设置 GitHub + Cron 轮询
# 间隔：每 30 分钟
###############################################################################

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")"
source "$CONFIG_DIR/config/config.sh"

echo "========================================="
echo "EEGTokenizer GitHub + Cron 安装脚本"
echo "轮询间隔: 30 分钟"
echo "========================================="
echo ""

# 检查配置
echo "检查配置..."
echo "  项目目录: $PROJECT_DIR"
echo "  GitHub 仓库: $GITHUB_REPO"
echo "  Conda 环境: $CONDA_ENV_NAME"
echo "  Python 路径: $PYTHON_PATH"
echo "  检查间隔: $CHECK_INTERVAL 分钟"
echo ""

# 确认
read -p "配置是否正确？(y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "请修改配置文件: $CONFIG_DIR/config/config.sh"
    exit 1
fi

# 克隆仓库（如果不存在）
if [ ! -d "$PROJECT_DIR" ]; then
    echo "克隆 GitHub 仓库..."
    git clone $GITHUB_REPO $PROJECT_DIR
    if [ $? -ne 0 ]; then
        echo "错误：git clone 失败"
        exit 1
    fi
    echo "仓库克隆完成"
else
    echo "项目目录已存在: $PROJECT_DIR"
fi

# 设置脚本权限
echo "设置脚本权限..."
chmod +x "$SCRIPT_DIR/github_pull_train.sh"
echo "脚本权限设置完成"

# 安装 Cron 任务
echo ""
echo "========================================="
echo "安装 Cron 任务"
echo "========================================="
echo ""

# 获取当前 crontab
CURRENT_CRON=$(crontab -l 2>/dev/null)

# 检查是否已安装
if echo "$CURRENT_CRON" | grep -q "github_pull_train.sh"; then
    echo "Cron 任务已安装"
    read -p "是否重新安装？(y/n): " reinstall
    if [ "$reinstall" != "y" ]; then
        echo "保留现有 Cron 任务"
        exit 0
    fi

    # 删除旧的 Cron 任务
    echo "删除旧的 Cron 任务..."
    crontab -l | grep -v "github_pull_train.sh" | crontab -
fi

# 安装新的 Cron 任务（30分钟间隔）
echo "安装新的 Cron 任务（30分钟间隔）..."
CRON_JOB="*/$CHECK_INTERVAL * * * * $SCRIPT_DIR/github_pull_train.sh >> $CRON_LOG 2>&1"

# 添加到 crontab
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron 任务安装完成"
echo ""
echo "Cron 任务内容："
echo "  $CRON_JOB"
echo ""
echo "运行时间：每 30 分钟一次（00分, 30分）"
echo ""

# 显示当前 crontab
echo "当前 crontab："
crontab -l
echo ""

# 显示下次运行时间
echo "下次运行时间："
echo "  $(date -d '+30 minutes' '+%Y-%m-%d %H:%M:%S')"
echo ""

# 测试运行
echo "========================================="
echo "测试运行"
echo "========================================="
echo ""
read -p "是否立即测试运行？(y/n): " test_run

if [ "$test_run" = "y" ]; then
    echo "执行测试运行..."
    "$SCRIPT_DIR/github_pull_train.sh"
    echo ""
    echo "测试运行完成，查看日志:"
    echo "  tail -f $TRAINING_LOG"
fi

echo ""
echo "========================================="
echo "安装完成！"
echo "========================================="
echo ""
echo "Cron 任务：每 30 分钟运行一次"
echo ""
echo "查看日志："
echo "  Cron 日志: tail -f $CRON_LOG"
echo "  训练日志: tail -f $TRAINING_LOG"
echo ""
echo "手动触发训练："
echo "  cd $SCRIPT_DIR"
echo "  ./github_pull_train.sh"
echo ""
echo "管理 Cron 任务："
echo "  查看任务: crontab -l"
echo "  删除任务: crontab -e (删除对应行)"
echo ""
