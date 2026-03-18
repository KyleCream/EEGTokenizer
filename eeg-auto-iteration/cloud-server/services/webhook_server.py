#!/usr/bin/env python3
"""
EEGTokenizer Webhook 接收服务
接收来自课题组服务器的训练完成通知，并通过飞书提醒
"""

from flask import Flask, request, jsonify
import logging
from datetime import datetime
import json
import subprocess
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/.openclaw/workspace/ssh-webhook-integration/logs/webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5000'))
OPENCLAW_SESSION = os.getenv('OPENCLAW_SESSION', 'default')


def send_feishu_notification(message_data):
    """
    发送飞书通知（支持错误日志高亮显示）
    """
    try:
        # 构建消息
        title = message_data.get('title', '🔬 EEGTokenizer 训练通知')
        status = message_data.get('status', 'unknown')
        project = message_data.get('project', 'EEGTokenizer')
        message = message_data.get('message', '')
        details = message_data.get('details', {})

        # 根据状态设置不同的样式
        status_icons = {
            'started': '🚀',
            'success': '✅',
            'failed': '❌',
            'unknown': '❓'
        }
        status_icon = status_icons.get(status, '❓')

        # 格式化消息
        feishu_msg = f"""{status_icon} {title}

📊 项目：{project}
📈 状态：{status}
⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📝 {message}
"""

        # 添加关键信息
        if 'run_id' in details:
            feishu_msg += f"\n🆔 运行 ID: {details['run_id']}"

        if 'duration_formatted' in details:
            feishu_msg += f"\n⏱️ 耗时: {details['duration_formatted']}"

        if 'exit_code' in details:
            feishu_msg += f"\n🔴 退出码: {details['exit_code']}"

        if 'remote_hostname' in details:
            feishu_msg += f"\n🖥️ 主机: {details['remote_hostname']}"

        if 'command' in details:
            feishu_msg += f"\n💻 命令: {details['command']}"

        # 如果有错误日志，高亮显示
        if 'error_log' in details and details['error_log']:
            feishu_msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 错误日志：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{details['error_log'][:2000]}  # 限制长度
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 建议检查：
1. 查看完整日志：/root/.openclaw/workspace/ssh-webhook-integration/logs/
2. 修复代码后重新运行
3. 使用 AUTO_SYNC=false 跳过同步（如果代码已是最新）
"""

        # 如果失败但没有错误日志，显示调试信息
        elif status == 'failed' and 'error' in details:
            feishu_msg += f"""
❌ 错误信息：{details.get('error', '未知错误')}

🔍 调试建议：
• 检查训练命令是否正确
• 查看日志文件获取详细错误
• 确认 nit 上的代码版本
"""

        # 如果成功，显示简要信息
        elif status == 'success':
            if 'log_file' in details:
                feishu_msg += f"\n📄 日志: {details['log_file']}"

        logger.info(f"准备发送飞书通知: {title}")

        # 将通知写入队列文件，由另一个进程处理
        notification_queue = '/root/.openclaw/workspace/ssh-webhook-integration/logs/notification_queue.jsonl'
        with open(notification_queue, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'message': feishu_msg
            }, ensure_ascii=False) + '\n')

        logger.info("通知已加入队列")
        return True

    except Exception as e:
        logger.error(f"发送飞书通知失败: {e}", exc_info=True)
        return False


@app.route('/webhook/eegtokenizer', methods=['POST', 'GET'])
def eegtokenizer_webhook():
    """接收 EEGTokenizer 训练完成通知"""

    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'service': 'EEGTokenizer Webhook Receiver',
            'version': '1.0.0',
            'endpoints': {
                'POST /webhook/eegtokenizer': '接收训练完成通知'
            }
        })

    try:
        data = request.get_json()

        if not data:
            logger.warning("收到空的 POST 请求")
            return jsonify({'error': 'No JSON data provided'}), 400

        logger.info(f"收到 webhook: {json.dumps(data, ensure_ascii=False)}")

        # 解析数据
        event_type = data.get('event', 'training_completed')
        status = data.get('status', 'unknown')
        message = data.get('message', '')
        details = data.get('details', {})

        # 发送飞书通知
        notification_sent = send_feishu_notification({
            'title': f"🔬 EEGTokenizer {event_type}",
            'status': status,
            'project': data.get('project', 'EEGTokenizer'),
            'message': message,
            'details': details
        })

        return jsonify({
            'status': 'success',
            'notification_sent': notification_sent,
            'received_at': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"处理 webhook 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'service': 'EEGTokenizer Webhook Server',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    logger.info(f"启动 Webhook 服务器，端口: {WEBHOOK_PORT}")
    app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)
