#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache


def main():
    parser = argparse.ArgumentParser(description="从全局缓存推荐")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--top", type=int, default=5, help="推荐数量")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    
    print("="*60)
    print("Discourse 推荐服务")
    print("="*60)
    
    config = load_config(args.config)
    
    candidates = []
    
    l1 = load_cache(os.path.join(cache_dir, "global_l1_hot.json")) or {"topics": []}
    candidates.extend(l1.get("topics", []))
    
    l2 = load_cache(os.path.join(cache_dir, "global_l2_category.json")) or {"categories": {}}
    for cat_data in l2.get("categories", {}).values():
        candidates.extend(cat_data.get("topics", []))
    
    l3 = load_cache(os.path.join(cache_dir, "global_l3_fresh.json")) or {"topics": []}
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
