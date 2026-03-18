#!/bin/bash
###############################################################################
# nit 环境检测脚本
# 用法：在 nit 上运行此脚本，将结果发送给小k
#
# 功能：
#   1. 检测 Python 环境
#   2. 检测 PyTorch 版本和 CUDA 支持
#   3. 检测 GPU 状态
#   4. 检测已安装的依赖包
#   5. 生成环境报告
###############################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_section() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 输出文件
OUTPUT_FILE="$HOME/nit_environment_report.txt"

# 开始检测
log_section "🔍 nit 环境检测报告"
echo "检测时间: $(date)" | tee "$OUTPUT_FILE"
echo "主机名: $(hostname)" | tee -a "$OUTPUT_FILE"
echo "用户: $(whoami)" | tee -a "$OUTPUT_FILE"
echo "" | tee -a "$OUTPUT_FILE"

# 1. 系统信息
log_section "1️⃣ 系统信息"
{
    echo "操作系统: $(uname -s)"
    echo "内核版本: $(uname -r)"
    echo "架构: $(uname -m)"
    echo "CPU 核心数: $(nproc)"
    echo "总内存: $(free -h | awk '/^Mem:/ {print $2}')"
    echo "可用内存: $(free -h | awk '/^Mem:/ {print $7}')"
} | tee -a "$OUTPUT_FILE"
echo ""

# 2. Python 环境
log_section "2️⃣ Python 环境"
{
    echo "Python 版本:"
    python3 --version 2>&1 || python --version 2>&1 || echo "未找到 Python"
    echo ""
    echo "Python 路径:"
    which python3 2>&1 || which python 2>&1 || echo "未找到 Python"
    echo ""
    echo "pip 版本:"
    pip3 --version 2>&1 || pip --version 2>&1 || echo "未找到 pip"
    echo ""
    echo "虚拟环境:"
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "当前在虚拟环境中: $VIRTUAL_ENV"
    else
        echo "当前不在虚拟环境中"
    fi
} | tee -a "$OUTPUT_FILE"
echo ""

# 3. PyTorch 环境
log_section "3️⃣ PyTorch 环境"
{
    echo "检查 PyTorch..."
    if python3 -c "import torch; print('PyTorch 版本:', torch.__version__)" 2>/dev/null || \
       python -c "import torch; print('PyTorch 版本:', torch.__version__)" 2>/dev/null; then
        echo "✓ PyTorch 已安装"
        echo ""
        echo "PyTorch 详细信息:"
        python3 -c "
import torch
print('  版本:', torch.__version__)
print('  CUDA 可用:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('  CUDA 版本:', torch.version.cuda)
    print('  cuDNN 版本:', torch.backends.cudnn.version())
    print('  GPU 数量:', torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        print(f'  GPU {i}: {torch.cuda.get_device_name(i)}')
        print(f'    显存: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB')
" 2>/dev/null || python -c "
import torch
print('  版本:', torch.__version__)
print('  CUDA 可用:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('  CUDA 版本:', torch.version.cuda)
    print('  GPU 数量:', torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        print(f'  GPU {i}: {torch.cuda.get_device_name(i)}')
" 2>/dev/null
    else
        echo "✗ PyTorch 未安装"
    fi
} | tee -a "$OUTPUT_FILE"
echo ""

# 4. GPU 状态（使用 nvidia-smi）
log_section "4️⃣ GPU 状态"
{
    if command -v nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU 信息:"
        nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.free,memory.used --format=csv,noheader 2>/dev/null || nvidia-smi 2>/dev/null
        echo ""
        echo "当前 GPU 进程:"
        nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null || echo "无活跃 GPU 进程"
    else
        echo "✗ 未找到 nvidia-smi（可能没有 GPU 或驱动未安装）"
    fi
} | tee -a "$OUTPUT_FILE"
echo ""

# 5. 常用依赖包
log_section "5️⃣ 常用依赖包"
{
    echo "检查常用包..."
    for pkg in numpy pandas scipy scikit-learn matplotlib tensorflow jupyter; do
        if python3 -c "import $pkg" 2>/dev/null || python -c "import $pkg" 2>/dev/null; then
            version=$(python3 -c "import $pkg; print($pkg.__version__)" 2>/dev/null || python -c "import $pkg; print($pkg.__version__)" 2>/dev/null)
            echo "  ✓ $pkg: $version"
        else
            echo "  ✗ $pkg: 未安装"
        fi
    done
} | tee -a "$OUTPUT_FILE"
echo ""

# 6. Git 配置
log_section "6️⃣ Git 配置"
{
    echo "Git 版本:"
    git --version 2>&1 || echo "未安装 Git"
    echo ""
    if [ -d ~/EEGTokenizer ]; then
        echo "EEGTokenizer 仓库状态:"
        cd ~/EEGTokenizer
        echo "  分支: $(git branch --show-current)"
        echo "  最后提交: $(git log -1 --oneline)"
    else
        echo "EEGTokenizer 仓库: 未找到"
    fi
} | tee -a "$OUTPUT_FILE"
echo ""

# 7. SSH 密钥
log_section "7️⃣ SSH 配置"
{
    echo "SSH 公钥:"
    if [ -f ~/.ssh/id_rsa.pub ]; then
        cat ~/.ssh/id_rsa.pub
    elif [ -f ~/.ssh/id_ed25519.pub ]; then
        cat ~/.ssh/id_ed25519.pub
    else
        echo "未找到 SSH 公钥"
    fi
} | tee -a "$OUTPUT_FILE"
echo ""

# 8. 网络
log_section "8️⃣ 网络配置"
{
    echo "GitHub 连接测试:"
    if ssh -T git@github.com 2>&1 | grep -q "successfull\|authenticated"; then
        echo "  ✓ 可以连接到 GitHub"
    else
        echo "  ⚠ GitHub 连接可能有问题"
    fi
    echo ""
    echo "外网 IP:"
    curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "无法获取"
} | tee -a "$OUTPUT_FILE"
echo ""

# 完成
log_section "✅ 检测完成"
log_info "环境报告已保存到: $OUTPUT_FILE"
echo ""
log_info "请将此报告发送给小k，以便配置训练环境"
echo ""

# 显示报告摘要
log_info "报告摘要："
cat "$OUTPUT_FILE"
