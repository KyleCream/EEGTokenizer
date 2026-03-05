#!/usr/bin/env python3
"""
Webhook 处理器
- 接收 Discourse topic_created 事件
- 更新 L3 全局新鲜池
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache, save_cache


def main():
    parser = argparse.ArgumentParser(description="处理 Discourse Webhook")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--payload", required=True, help="Webhook payload JSON 文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    l3_path = os.path.join(cache_dir, "l3_fresh.json")
    
    print("="*60)
    print("处理 Discourse Webhook")
    print("="*60)
    
    # 加载 payload
    with open(args.payload, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    # 检查事件类型
    event_type = payload.get("topic", {}).get("event") or payload.get("event")
    topic = payload.get("topic", {})
    
    if event_type != "topic_created" and not topic.get("id"):
        print("⚠️ 不是 topic_created 事件，跳过")
        return
    
    print(f"\n新帖子: {topic.get('title')}")
    print(f"话题 ID: {topic.get('id')}")
    
    # 加载 L3 缓存
    l3_data = load_cache(l3_path)
    if not l3_data:
        print("⚠️ L3 缓存不存在，跳过")
        return
    
    topics = l3_data.get("topics", [])
    
    # 检查是否已存在
    topic_id = topic.get("id")
    exists = any(t.get("id") == topic_id for t in topics)
    
    if exists:
        print("⚠️ 话题已在缓存中，跳过")
        return
    
    # 添加到开头（最新）
    topics.insert(0, topic)
    
    # 限制数量（100帖）
    if len(topics) > 100:
        topics = topics[:100]
    
    # 保存
    l3_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    l3_data["topics"] = topics
    save_cache(l3_path, l3_data)
    
    print(f"✅ 已添加到 L3 新鲜池（当前 {len(topics)} 帖）")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
