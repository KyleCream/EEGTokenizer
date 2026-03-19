# nit 服务器配置文件（GitHub + Cron 方案）
# 请根据实际情况修改以下配置

# ==================== GitHub 配置 ====================
# GitHub 仓库配置

# GitHub 仓库 URL
GITHUB_REPO="https://github.com/KyleCream/EEGTokenizer.git"

# 本地项目路径
PROJECT_DIR="$HOME/EEGTokenizer"

# Git 分支
GIT_BRANCH="main"

# ==================== Python 环境配置 ====================
# Python 环境配置

# Conda 环境名称
CONDA_ENV_NAME="mamba_cuda121"

# Python 解释器路径（如果 conda 不可用，使用绝对路径）
PYTHON_PATH="$HOME/conda/envs/$CONDA_ENV_NAME/bin/python"

# 激活 Conda 环境的脚本（根据系统调整）
# 对于 bash：
CONDA_INIT="$HOME/conda/etc/profile.d/conda.sh"
# 对于 zsh：
# CONDA_INIT="$HOME/conda/etc/profile.d/zsh.sh"

# ==================== 训练配置 ====================
# 训练相关配置

# 训练脚本路径（相对于 PROJECT_DIR）
TRAIN_SCRIPT="train.py"

# 训练配置文件
TRAIN_CONFIG="eegtokenizer_v2/configs/experiments.yaml::adc_4bit"

# 其他训练参数
TRAIN_ARGS="--config $TRAIN_CONFIG"

# ==================== 数据配置 ====================
# 数据集配置

# 数据目录
DATA_DIR="/home/zengkai/model_compare/data/BNCI2014_001"

# 被试 ID
SUBJECT_ID="A01"

# 时间窗口（秒）
WIN_TMIN=0.0
WIN_TMAX=1.0

# ==================== 日志配置 ====================
# 日志配置

# 训练日志目录 (与 train.py 保持一致)
LOG_DIR="$PROJECT_DIR/eegtokenizer_v2/logs"
mkdir -p "$LOG_DIR"

# 训练日志文件
TRAINING_LOG="$LOG_DIR/train_$(date +%Y%m%d).log"

# Cron 日志文件 (独立存放)
CRON_LOG="$HOME/eeg-auto-logs/cron_$(date +%Y%m%d).log"
mkdir -p "$HOME/eeg-auto-logs"

# ==================== Cron 配置 ====================
# Cron 轮询配置

# 检查间隔（分钟）
CHECK_INTERVAL=30

# ==================== 使用说明 ====================
# 1. 修改上面的配置（特别是 GITHUB_REPO 和 PROJECT_DIR）
# 2. 确保 Git 已配置并可以访问 GitHub
# 3. 设置 Cron：
#    crontab -e
#    添加：*/30 * * * * /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh >> /home/zengkai/eeg-auto-logs/cron.log 2>&1
# 4. 查看日志：
#    tail -f ~/eeg-auto-logs/training_*.log
#    tail -f ~/eeg-auto-logs/cron.log
