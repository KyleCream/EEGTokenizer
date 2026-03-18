#!/bin/bash
###############################################################################
# 智能训练启动脚本（nit 服务器版本）
# 用法：./smart_train.sh <训练命令>
#
# 功能：
#   1. 自动检测 Python 环境（虚拟环境 / conda）
#   2. 检查 GPU 是否空闲
#   3. GPU 空闲时自动运行训练
#   4. 完整的日志记录
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
PROJECT_DIR="${PROJECT_DIR:-$HOME/EEGTokenizer}"
VENV_NAME="${VENV_NAME:-venv}"
CONDA_ENV="${CONDA_ENV:-base}"
PYTHON_CMD="${PYTHON_CMD:-python3}"

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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查参数
if [ $# -lt 1 ]; then
    log_error "用法: $0 <训练命令>"
    echo ""
    echo "环境变量："
    echo "  PROJECT_DIR=xxx    项目目录（默认: ~/EEGTokenizer）"
    echo "  VENV_NAME=xxx      虚拟环境名称（默认: venv）"
    echo "  CONDA_ENV=xxx      Conda 环境名称（默认: base）"
    echo "  PYTHON_CMD=xxx     Python 命令（默认: python3）"
    echo ""
    echo "示例："
    echo "  $0 \"python train.py\""
    echo "  $0 \"CUDA_VISIBLE_DEVICES=0 python train.py --epochs 100\""
    exit 1
fi

TRAINING_CMD="$1"

log_info "========================================="
log_info "🚀 智能训练启动器"
log_info "========================================="
log_info "项目目录: ${PROJECT_DIR}"
log_info "训练命令: ${TRAINING_CMD}"
log_info "========================================="
echo ""

# Step 1: 检测并激活 Python 环境
log_step "Step 1/4: 检测 Python 环境"

# 检查是否在 conda 环境中
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    log_info "✓ 当前在 Conda 环境: $CONDA_DEFAULT_ENV"
elif [ -n "$VIRTUAL_ENV" ]; then
    log_info "✓ 当前在虚拟环境: $VIRTUAL_ENV"
else
    log_info "当前不在 Python 虚拟环境中"

    # 尝试激活虚拟环境
    if [ -f "${PROJECT_DIR}/${VENV_NAME}/bin/activate" ]; then
        log_info "找到虚拟环境: ${PROJECT_DIR}/${VENV_NAME}"
        log_info "正在激活..."
        source "${PROJECT_DIR}/${VENV_NAME}/bin/activate"
        log_info "✓ 虚拟环境已激活"
    elif command -v conda &> /dev/null; then
        log_info "找到 Conda，正在激活环境: $CONDA_ENV"
        eval "$(conda shell.bash hook)"
        conda activate "$CONDA_ENV"
        log_info "✓ Conda 环境已激活: $CONDA_DEFAULT_ENV"
    else
        log_warn "未找到虚拟环境，使用系统 Python"
    fi
fi

# 检查 PyTorch
log_info "检查 PyTorch..."
if python -c "import torch; print('PyTorch:', torch.__version__, '| CUDA:', torch.cuda.is_available())" 2>/dev/null; then
    log_info "✓ PyTorch 可用"
else
    log_error "✗ PyTorch 不可用，请检查环境"
    exit 1
fi

echo ""

# Step 2: 进入项目目录
log_step "Step 2/4: 进入项目目录"
if [ ! -d "$PROJECT_DIR" ]; then
    log_error "项目目录不存在: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
log_info "✓ 当前目录: $(pwd)"
echo ""

# Step 3: 检查 GPU 状态
log_step "Step 3/4: 检查 GPU 状态"

if command -v nvidia-smi &> /dev/null; then
    log_info "GPU 信息:"
    nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader | while IFS=',' read -r idx name mem_used mem_total util; do
        idx=$(echo "$idx" | xargs)
        name=$(echo "$name" | xargs)
        mem_used=$(echo "$mem_used" | xargs)
        mem_total=$(echo "$mem_total" | xargs)
        util=$(echo "$util" | xargs)
        mem_percent=$((mem_used * 100 / mem_total))

        if [ $mem_percent -lt 10 ] && [ $util -lt 10 ]; then
            log_info "  GPU $idx ($name): ✅ 空闲 (显存: ${mem_percent}%, 利用率: ${util}%)"
        else
            log_warn "  GPU $idx ($name): ⚠️  繁忙 (显存: ${mem_percent}%, 利用率: ${util}%)"
        fi
    done

    # 检查活跃进程
    processes=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null)
    if [ -n "$processes" ]; then
        log_warn "当前 GPU 进程:"
        echo "$processes" | while IFS=',' read -r pid name; do
            log_warn "  PID $pid: $name"
        done
    fi
else
    log_warn "未找到 nvidia-smi，跳过 GPU 检查"
fi

echo ""

# Step 4: 运行训练
log_step "Step 4/4: 运行训练"
log_info "开始执行: ${TRAINING_CMD}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 执行训练命令
if eval "$TRAINING_CMD"; then
    # 成功
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    HOURS=$((DURATION / 3600))
    MINUTES=$(((DURATION % 3600) / 60))
    SECONDS=$((DURATION % 60))

    echo ""
    log_info "========================================="
    log_info "🎉 训练成功完成！"
    log_info "========================================="
    log_info "总耗时: ${HOURS}h ${MINUTES}m ${SECONDS}s"
    log_info "========================================="

    exit 0
else
    # 失败
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    log_error "========================================="
    log_error "❌ 训练失败！"
    log_error "========================================="
    log_error "退出码: ${EXIT_CODE}"
    log_error "耗时: ${DURATION}秒"
    log_error "========================================="

    exit $EXIT_CODE
fi
