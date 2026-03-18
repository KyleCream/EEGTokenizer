# nit 服务器配置文件
# 请根据实际情况修改以下配置

# ==================== 云服务器配置 ====================
# 云服务器信息（必须修改！）

# 云服务器的公网 IP 或域名
CLOUD_SERVER="root@123.45.67.89"     # 必须修改为你的云服务器 IP

# 云服务器 SSH 端口（通常为 22）
CLOUD_SSH_PORT=22

# ==================== 隧道配置 ====================
# 反向隧道配置

# 在云服务器上映射的端口（建议 3000-4000）
TUNNEL_PORT=3022

# ==================== 本地配置 ====================
# nit 本地配置

# 当前用户名
REMOTE_USER="your_username"          # 必须修改为 nit 上的用户名

# ==================== 使用说明 ====================
# 1. 修改上面的配置（特别是 CLOUD_SERVER 和 REMOTE_USER）
# 2. 在云服务器上添加 nit 的 SSH 公钥：
#    - 在 nit 上运行：cat ~/.ssh/id_rsa.pub
#    - 复制公钥
#    - 在云服务器上运行：nano ~/.ssh/authorized_keys
#    - 粘贴公钥
# 3. 启动隧道：
#    cd ~/eeg-auto-iteration/nit-server/scripts
#    ./tunnel_manager.sh start
# 4. 检查状态：
#    ./tunnel_manager.sh status
# 5. 查看日志：
#    ./tunnel_manager.sh log
# 6. 设置开机自启（可选）：
#    crontab -e
#    添加：@reboot sleep 30 && /home/your_username/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh start
