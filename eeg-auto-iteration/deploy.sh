#!/bin/bash
###############################################################################
# 一键部署脚本 - 云服务器版本
# 用法：./deploy.sh
#
# 此脚本会自动完成云服务器上的所有部署步骤
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 root 权限运行此脚本"
    exit 1
fi

PROJECT_DIR="/root/.openclaw/workspace/eeg-auto-iteration"

log_info "========================================="
log_info "🚀 EEGTokenizer 自动回环系统部署"
log_info "========================================="
log_info "项目目录: ${PROJECT_DIR}"
log_info "========================================="

# Step 1: 安装依赖
log_step "Step 1/6: 安装系统依赖..."
yum install -y python3-pip jq git python3-flask 2>/dev/null || \
    apt-get install -y python3-pip jq git python3-flask 2>/dev/null

log_info "✓ 依赖安装完成"

# Step 2: 创建目录结构
log_step "Step 2/6: 创建目录结构..."
mkdir -p "${PROJECT_DIR}"/{cloud-server/{scripts,services,config},nit-server/{scripts,config},docs,logs}

log_info "✓ 目录结构创建完成"

# Step 3: 设置权限
log_step "Step 3/6: 设置脚本权限..."
chmod +x "${PROJECT_DIR}"/cloud-server/scripts/*.sh
chmod +x "${PROJECT_DIR}"/nit-server/scripts/*.sh

log_info "✓ 权限设置完成"

# Step 4: 复制服务文件
log_step "Step 4/6: 部署 webhook 服务..."

# 复制 webhook 服务器（如果存在）
if [ -f /root/.openclaw/workspace/ssh-webhook-integration/webhook_server.py ]; then
    cp /root/.openclaw/workspace/ssh-webhook-integration/webhook_server.py \
       "${PROJECT_DIR}/cloud-server/services/"
    cp /root/.openclaw/workspace/ssh-webhook-integration/notification_daemon.py \
       "${PROJECT_DIR}/cloud-server/services/"
    log_info "✓ Webhook 服务文件已复制"
else
    log_warn "未找到 webhook 服务文件，跳过..."
fi

# Step 5: 创建 systemd 服务
log_step "Step 5/6: 创建 systemd 服务..."

# 创建 webhook 服务
cat > /etc/systemd/system/eeg-webhook.service << 'EOF'
[Unit]
Description=EEGTokenizer Webhook Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/eeg-auto-iteration
Environment="WEBHOOK_PORT=5000"
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 创建通知守护进程服务
cat > /etc/systemd/system/eeg-notification.service << 'EOF'
[Unit]
Description=EEGTokenizer Notification Daemon
After=network.target eeg-webhook.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/eeg-auto-iteration
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/notification_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

log_info "✓ systemd 服务已创建"

# Step 6: 重载并启动服务
log_step "Step 6/6: 启动服务..."
systemctl daemon-reload

# 启动服务
if systemctl start eeg-webhook eeg-notification; then
    log_info "✓ 服务已启动"
else
    log_error "✗ 服务启动失败，请检查日志"
    exit 1
fi

# 设置开机自启
systemctl enable eeg-webhook eeg-notification 2>/dev/null || true

log_info "✓ 服务已设置为开机自启"

# 显示服务状态
log_info "========================================="
log_info "📊 服务状态"
log_info "========================================="
systemctl status eeg-webhook --no-pager | head -n 10
echo ""
systemctl status eeg-notification --no-pager | head -n 10

# 下一步提示
log_info "========================================="
log_info "✅ 云服务器部署完成！"
log_info "========================================="
echo ""
log_info "下一步："
echo ""
echo "1️⃣  配置 nit 服务器："
echo "   scp ${PROJECT_DIR}/nit-server/scripts/ your_username@nit:~/eeg-auto-iteration/"
echo ""
echo "2️⃣  测试隧道连接："
echo "   ssh -p 3022 localhost 'hostname'"
echo ""
echo "3️⃣  运行首次训练："
echo "   cd ${PROJECT_DIR}/cloud-server/scripts"
echo "   ./run_training.sh 'cd ~/EEGTokenizer && python train.py'"
echo ""
echo "详细文档："
echo "   ${PROJECT_DIR}/README.md"
echo "   ${PROJECT_DIR}/docs/DEPLOYMENT.md"
echo ""
log_info "========================================="
