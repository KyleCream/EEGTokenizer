#!/usr/bin/env python3
"""
初始化分层缓存
- L1: 全局热门池（50帖）
- L2: 分类池（每类 30帖）
- L3: 全局新鲜池（100帖）
"""
import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI, merge_and_deduplicate, sort_topics_by


def main():
    parser = argparse.ArgumentParser(description="初始化分层缓存")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    
    print("="*60)
    print("初始化 Discourse 推荐服务分层缓存")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    # ========== L1: 全局热门池 ==========
    print("\n[1/3] 构建 L1: 全局热门池（50帖）...")
    top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
    l1_topics = sort_topics_by(top_topics, "like_count")[:50]
    l1_path = os.path.join(cache_dir, "l1_hot.json")
    save_cache(l1_path, {
        "updated_at": None,
        "topics": l1_topics
    })
    print(f"   保存: {len(l1_topics)} 帖")
    
    # ========== L2: 分类池 ==========
    print("\n[2/3] 构建 L2: 分类池（每类 30帖）...")
    categories = api.get_categories()
    l2_data = {}
    
    latest_topics = []
    for page in range(3):
        latest_topics.extend(api.get_latest_topics(page, per_page=30))
    
    for cat in categories:
        cat_id = cat.get('id')
        cat_name = cat.get('name')
        cat_topics = [t for t in latest_topics if t.get('category_id') == cat_id]
        cat_topics = sort_topics_by(cat_topics, "posts_count")[:30]
        l2_data[str(cat_id)] = {
            "name": cat_name,
            "topics": cat_topics
        }
        print(f"   分类 {cat_name}: {len(cat_topics)} 帖")
    
    l2_path = os.path.join(cache_dir, "l2_category.json")
    save_cache(l2_path, {
        "updated_at": None,
        "categories": l2_data
    })
    
    # ========== L3: 全局新鲜池 ==========
    print("\n[3/3] 构建 L3: 全局新鲜池（100帖）...")
    fresh_topics = []
    for page in range(4):
        fresh_topics.extend(api.get_latest_topics(page, per_page=30))
    
    fresh_topics = merge_and_deduplicate([fresh_topics])
    fresh_topics = sort_topics_by(fresh_topics, "created_at", reverse=True)[:100]
    
    l3_path = os.path.join(cache_dir, "l3_fresh.json")
    save_cache(l3_path, {
        "updated_at": None,
        "topics": fresh_topics
    })
    print(f"   保存: {len(fresh_topics)} 帖")
    
    print("\n" + "="*60)
    print("✅ 分层缓存初始化完成！")
    print("="*60)


if __name__ == "__main__":
    main()
