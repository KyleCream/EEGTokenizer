#!/usr/bin/env python3
"""
Webhook 处理器（高级版）
- 接收 Discourse topic_created 事件
- 分类到相关领域
- 更新对应领域的 L3 新鲜池
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache, save_cache, extract_topic_features


def get_topic_domain_ids(topic: Dict, domains: List[Dict]) -> List[str]:
    """判断新帖属于哪些领域（简化版：匹配分类）"""
    topic_cat_id = str(topic.get('category_id', ''))
    matched_domains = []
    
    for domain in domains:
        domain_cats = domain.get('categories', [])
        if topic_cat_id in [str(c) for c in domain_cats]:
            matched_domains.append(domain['id'])
    
    # 如果没匹配到，返回前 2 个通用领域
    if not matched_domains and domains:
        matched_domains = [d['id'] for d in domains[:2]]
    
    return matched_domains


def main():
    parser = argparse.ArgumentParser(description="处理 Discourse Webhook（高级版）")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--payload", required=True, help="Webhook payload JSON 文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*60)
    print("处理 Discourse Webhook（高级版）")
    print("="*60)
    
    # 加载 payload
    with open(args.payload, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    topic = payload.get("topic", {})
    if not topic.get("id"):
        print("⚠️ 不是有效的话题事件，跳过")
        return
    
    print(f"\n新帖子: {topic.get('title')}")
    print(f"话题 ID: {topic.get('id')}")
    
    # 加载领域定义
    domains_path = os.path.join(skill_dir, "domains.json")
    domains_data = load_cache(domains_path)
    
    if not domains_data or not domains_data.get('domains'):
        print("\n⚠️ 无领域定义，使用全局缓存（冷启动）")
        # 冷启动：更新全局 L3
        global_l3_path = os.path.join(skill_dir, "cache", "global_l3_fresh.json")
        global_l3 = load_cache(global_l3_path) or {"topics": []}
        topics = global_l3.get("topics", [])
        
        topic_id = topic.get("id")
        if not any(t.get("id") == topic_id for t in topics):
            topics.insert(0, topic)
            if len(topics) > 100:
                topics = topics[:100]
        
        global_l3["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        global_l3["topics"] = topics
        save_cache(global_l3_path, global_l3)
        print(f"✅ 已添加到全局 L3（当前 {len(topics)} 帖）")
        return
    
    # 有领域定义，分发到领域
    domains = domains_data.get("domains", [])
    domain_ids = get_topic_domain_ids(topic, domains)
    
    print(f"\n匹配到领域: {domain_ids}")
    
    for domain_id in domain_ids:
        domain_dir = os.path.join(skill_dir, "domains", f"domain_{domain_id}")
        l3_path = os.path.join(domain_dir, "l3_fresh.json")
        l3_data = load_cache(l3_path) or {"topics": []}
        topics = l3_data.get("topics", [])
        
        topic_id = topic.get("id")
        if not any(t.get("id") == topic_id for t in topics):
            topics.insert(0, topic)
            if len(topics) > 100:
                topics = topics[:100]
            
            l3_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            l3_data["topics"] = topics
            save_cache(l3_path, l3_data)
            print(f"✅ 领域 {domain_id}: 已添加到 L3（当前 {len(topics)} 帖）")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
