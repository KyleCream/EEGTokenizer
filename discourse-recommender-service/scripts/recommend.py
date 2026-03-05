#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache, save_cache


def main():
    parser = argparse.ArgumentParser(description="从多领域缓存推荐")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--domain", help="指定领域 ID（可选，默认从所有领域推荐）")
    parser.add_argument("--top", type=int, default=5, help="推荐数量")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    domains_dir = os.path.join(skill_dir, "domains")
    
    print("="*60)
    print("Discourse 推荐服务（多领域）")
    print("="*60)
    
    config = load_config(args.config)
    
    domains_data = load_cache(os.path.join(skill_dir, "domains.json")) or {"domains": []}
    all_domains = domains_data.get("domains", [])
    
    if args.domain:
        target_domain_ids = [args.domain]
    else:
        target_domain_ids = [d["id"] for d in all_domains]
    
    print(f"\n从 {len(target_domain_ids)} 个领域加载候选...")
    
    candidates = []
    for domain_id in target_domain_ids:
        domain_dir = os.path.join(domains_dir, f"domain_{domain_id}")
        if not os.path.exists(domain_dir):
            continue
        
        l1 = load_cache(os.path.join(domain_dir, "l1_hot.json")) or {"topics": []}
        candidates.extend(l1.get("topics", []))
        
        l3 = load_cache(os.path.join(domain_dir, "l3_fresh.json")) or {"topics": []}
        candidates.extend(l3.get("topics", []))
    
    seen_ids = set()
    unique = []
    for topic in candidates:
        tid = topic.get("id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique.append(topic)
    
    def score(topic):
        return (topic.get("like_count", 0) * 2) + topic.get("posts_count", 0)
    
    unique.sort(key=score, reverse=True)
    
    print(f"\n候选: {len(candidates)} 帖，去重后: {len(unique)} 帖")
    
    print("\n" + "="*80)
    print("🎯 为您推荐的帖子".center(80))
    print("="*80)
    
    for i, topic in enumerate(unique[:args.top], 1):
        title = topic.get('title', '无标题')
        topic_id = topic.get('id')
        url = f"{config['discourse_url']}/t/{topic_id}"
        posts = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        
        reasons = []
        if likes > 0:
            reasons.append(f"点赞 {likes}")
        if posts > 0:
            reasons.append(f"回复 {posts}")
        if likes + posts > 5:
            reasons.append("热度不错")
        if not reasons:
            reasons.append("综合推荐")
        
        print(f"\n{i}. {title}")
        print(f"   🔗 {url}")
        print(f"   💡 理由: {', '.join(reasons)}")
    
    print("\n" + "="*80)
    print("✅ 推荐完成！")
    print("="*80)


if __name__ == "__main__":
    main()
