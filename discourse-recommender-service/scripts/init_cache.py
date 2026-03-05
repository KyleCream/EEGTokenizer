#!/usr/bin/env python3
"""
初始化分层缓存（高级版）
- 全局冷启动缓存（L1/L2/L3）
- （可选）初始领域缓存
"""
import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI, merge_and_deduplicate, sort_topics_by


def init_global_cache(config: Dict[str, Any], cache_dir: str):
    """初始化全局冷启动缓存"""
    print("\n[1/2] 初始化全局冷启动缓存...")
    api = DiscourseAPI(config)
    
    # L1: 全局热门
    top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
    l1_topics = sort_topics_by(top_topics, "like_count")[:50]
    l1_path = os.path.join(cache_dir, "global_l1_hot.json")
    save_cache(l1_path, {"updated_at": None, "topics": l1_topics})
    print(f"   L1（热门）: {len(l1_topics)} 帖")
    
    # L2: 全局分类池
    categories = api.get_categories()
    latest_topics = []
    for page in range(3):
        latest_topics.extend(api.get_latest_topics(page, per_page=30))
    
    l2_data = {}
    for cat in categories:
        cat_id = cat.get('id')
        cat_name = cat.get('name')
        cat_topics = [t for t in latest_topics if t.get('category_id') == cat_id]
        cat_topics = sort_topics_by(cat_topics, "posts_count")[:30]
        l2_data[str(cat_id)] = {"name": cat_name, "topics": cat_topics}
        print(f"   分类 {cat_name}: {len(cat_topics)} 帖")
    
    l2_path = os.path.join(cache_dir, "global_l2_category.json")
    save_cache(l2_path, {"updated_at": None, "categories": l2_data})
    
    # L3: 全局新鲜池
    fresh_topics = []
    for page in range(4):
        fresh_topics.extend(api.get_latest_topics(page, per_page=30))
    fresh_topics = merge_and_deduplicate([fresh_topics])
    fresh_topics = sort_topics_by(fresh_topics, "created_at", reverse=True)[:100]
    l3_path = os.path.join(cache_dir, "global_l3_fresh.json")
    save_cache(l3_path, {"updated_at": None, "topics": fresh_topics})
    print(f"   L3（新鲜）: {len(fresh_topics)} 帖")


def main():
    parser = argparse.ArgumentParser(description="初始化缓存（高级版）")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    parser.add_argument("--global-only", action="store_true", help="仅初始化全局缓存（冷启动用）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    
    print("="*60)
    print("初始化 Discourse 推荐服务缓存（高级版）")
    print("="*60)
    
    config = load_config(args.config)
    
    init_global_cache(config, cache_dir)
    
    if not args.global_only:
        print("\n⚠️ 领域缓存将在首次聚类后初始化")
        print("   运行: python3 scripts/cluster_domains.py --config config/config.json")
    
    print("\n" + "="*60)
    print("✅ 缓存初始化完成！")
    print("="*60)


if __name__ == "__main__":
    main()
