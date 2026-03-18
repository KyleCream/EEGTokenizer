# 云服务器配置文件
# 请根据实际情况修改以下配置

# ==================== nit 服务器配置 ====================
# nit 服务器通过 SSH 反向隧道连接到云服务器

# 隧道配置
NIT_SSH_PORT=3022                    # nit 隧道端口（云服务器上的监听端口）

# ==================== 代码仓库配置 ====================
REPO_URL="https://github.com/KyleCream/EEGTokenizer.git"
REPO_DIR="~/EEGTokenizer"            # nit 上的代码目录
REPO_BRANCH="main"                   # 分支名称

# ==================== Webhook 配置 ====================
WEBHOOK_URL="http://localhost:5000/webhook/eegtokenizer"
WEBHOOK_PORT=5000

# ==================== 日志配置 ====================
LOG_DIR="/root/.openclaw/workspace/eeg-auto-iteration/logs"

# ==================== 训练配置 ====================
PROJECT_NAME="EEGTokenizer"
AUTO_SYNC=true                      # 是否自动同步代码（默认 true）

# ==================== 使用说明 ====================
# 1. 修改上面的配置
# 2. 运行训练：
#    cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
#    ./run_training.sh "cd ~/EEGTokenizer && python train.py"
#
# 3. 自动迭代：
#    ./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3
#
# 4. 快速同步代码：
#    ./sync_code.sh /path/to/local/code
