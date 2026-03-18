#!/usr/bin/env python3
"""
通知队列处理守护进程
监控 notification_queue.jsonl 并通过 OpenClaw 发送飞书通知
"""

import time
import json
import os
import subprocess
import logging
from pathlib import Path

# 配置
QUEUE_FILE = Path('/root/.openclaw/workspace/ssh-webhook-integration/logs/notification_queue.jsonl')
PROCESSED_FILE = Path('/root/.openclaw/workspace/ssh-webhook-integration/logs/notification_queue_processed.jsonl')
CHECK_INTERVAL = 5  # 每 5 秒检查一次

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/.openclaw/workspace/ssh-webhook-integration/logs/daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def send_feishu_message(message):
    """
    通过 OpenClaw 发送飞书消息
    """
    try:
        # 使用 openclaw sessions_send 命令
        # 由于我们在后台运行，需要发送到主会话
        result = subprocess.run(
            ['openclaw', 'sessions', 'send', '--message', message],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("✅ 飞书消息发送成功")
            return True
        else:
            logger.error(f"❌ 发送失败: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ 发送飞书消息异常: {e}", exc_info=True)
        return False


def process_queue():
    """
    处理队列中的通知
    """
    if not QUEUE_FILE.exists():
        return

    # 读取所有未处理的行
    try:
        with open(QUEUE_FILE, 'r') as f:
            lines = f.readlines()

        if not lines:
            return

        logger.info(f"📦 发现 {len(lines)} 条待处理通知")

        # 处理每一行
        for line in lines:
            try:
                data = json.loads(line.strip())
                message = data.get('message', '')

                if not message:
                    continue

                # 发送消息
                if send_feishu_message(message):
                    # 记录到已处理文件
                    with open(PROCESSED_FILE, 'a') as pf:
                        pf.write(line)
                else:
                    logger.warning("⚠️ 消息发送失败，保留在队列中")

            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON 解析失败: {e}")
            except Exception as e:
                logger.error(f"❌ 处理通知失败: {e}", exc_info=True)

        # 清空已处理的消息
        if lines:
            with open(QUEUE_FILE, 'w') as f:
                f.write('')

            logger.info("✅ 队列处理完成")

    except Exception as e:
        logger.error(f"❌ 读取队列失败: {e}", exc_info=True)


def main():
    """
    主循环
    """
    logger.info("🚀 通知守护进程启动")
    logger.info(f"📥 队列文件: {QUEUE_FILE}")
    logger.info(f"⏱️ 检查间隔: {CHECK_INTERVAL}秒")

    # 确保目录存在
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            process_queue()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("🛑 收到退出信号，正在关闭...")
            break
        except Exception as e:
            logger.error(f"❌ 守护进程异常: {e}", exc_info=True)
            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
