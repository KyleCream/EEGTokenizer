#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI, merge_and_deduplicate, sort_topics_by


def main():
    parser = argparse.ArgumentParser(description="初始化全局缓存")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    
    print("="*60)
    print("初始化全局缓存")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    print("\n[1/3] L1: 全局热门池...")
    top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
    l1_topics = sort_topics_by(top_topics, "like_count")[:50]
    save_cache(os.path.join(cache_dir, "global_l1_hot.json"), {"topics": l1_topics})
    print(f"   {len(l1_topics)} 帖")
    
    print("\n[2/3] L2: 全局分类池...")
    categories = api.get_categories()
    latest = []
    for page in range(3):
        latest.extend(api.get_latest_topics(page, per_page=30))
    
    l2_data = {}
    for cat in categories:
        cat_id = cat.get('id')
        cat_name = cat.get('name')
        cat_topics = [t for t in latest if t.get('category_id') == cat_id]
        cat_topics = sort_topics_by(cat_topics, "posts_count")[:30]
        l2_data[str(cat_id)] = {"name": cat_name, "topics": cat_topics}
        print(f"   {cat_name}: {len(cat_topics)} 帖")
    
    save_cache(os.path.join(cache_dir, "global_l2_category.json"), {"categories": l2_data})
    
    print("\n[3/3] L3: 全局新鲜池...")
    fresh = []
    for page in range(4):
        fresh.extend(api.get_latest_topics(page, per_page=30))
    fresh = merge_and_deduplicate([fresh])
    fresh = sort_topics_by(fresh, "created_at", reverse=True)[:100]
    save_cache(os.path.join(cache_dir, "global_l3_fresh.json"), {"topics": fresh})
    print(f"   {len(fresh)} 帖")
    
    print("\n" + "="*60)
    print("✅ 全局缓存初始化完成！")
    print("="*60)


if __name__ == "__main__":
    main()
