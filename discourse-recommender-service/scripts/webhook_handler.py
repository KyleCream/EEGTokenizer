#!/usr/bin/env python3
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
    parser = argparse.ArgumentParser(description="Webhook 更新对应领域 L3")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--payload", required=True, help="Webhook payload")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*60)
    print("处理 Webhook（多领域）")
    print("="*60)
    
    with open(args.payload, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    topic = payload.get("topic", {})
    if not topic.get("id"):
        print("⚠️ 无效话题，跳过")
        return
    
    topic_cat_id = topic.get('category_id')
    print(f"\n新帖子: {topic.get('title')}")
    print(f"分类 ID: {topic_cat_id}")
    
    if topic_cat_id:
        domain_dir = os.path.join(skill_dir, "domains", f"domain_{topic_cat_id}")
        if os.path.exists(domain_dir):
            l3_path = os.path.join(domain_dir, "l3_fresh.json")
            l3 = load_cache(l3_path) or {"topics": []}
            topics = l3.get("topics", [])
            
            topic_id = topic.get("id")
            if not any(t.get("id") == topic_id for t in topics):
                topics.insert(0, topic)
                if len(topics) > 100:
                    topics = topics[:100]
                
                l3["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                l3["topics"] = topics
                save_cache(l3_path, l3)
                print(f"✅ 已更新领域 {topic_cat_id} 的 L3（当前 {len(topics)} 帖）")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
