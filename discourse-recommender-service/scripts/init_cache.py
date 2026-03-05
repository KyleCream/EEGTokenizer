#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI, sort_topics_by


def main():
    parser = argparse.ArgumentParser(description="初始化多领域缓存（分类为领域）")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    domains_dir = os.path.join(skill_dir, "domains")
    
    print("="*60)
    print("初始化多领域缓存（分类为领域）")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    categories = api.get_categories()
    print(f"\n发现 {len(categories)} 个分类（作为领域）")
    
    latest_topics = []
    for page in range(3):
        latest_topics.extend(api.get_latest_topics(page, per_page=30))
    
    top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
    
    for cat in categories:
        cat_id = cat.get('id')
        cat_name = cat.get('name')
        domain_dir = os.path.join(domains_dir, f"domain_{cat_id}")
        
        print(f"\n领域: {cat_name} (id: {cat_id})")
        
        if os.path.exists(domain_dir):
            shutil.rmtree(domain_dir)
        os.makedirs(domain_dir, exist_ok=True)
        
        cat_topics = [t for t in latest_topics if t.get('category_id') == cat_id]
        
        # L1: 领域热门（从全站热门中筛选 + 该分类热门）
        domain_hot = [t for t in top_topics if t.get('category_id') == cat_id]
        domain_hot += sort_topics_by(cat_topics, "like_count")
        domain_hot = sort_topics_by(domain_hot, "like_count")[:50]
        save_cache(os.path.join(domain_dir, "l1_hot.json"), {"topics": domain_hot})
        print(f"  L1（热门）: {len(domain_hot)} 帖")
        
        # L3: 领域新鲜（该分类最新）
        domain_fresh = sort_topics_by(cat_topics, "created_at", reverse=True)[:100]
        save_cache(os.path.join(domain_dir, "l3_fresh.json"), {"topics": domain_fresh})
        print(f"  L3（新鲜）: {len(domain_fresh)} 帖")
    
    save_cache(os.path.join(skill_dir, "domains.json"), {
        "domains": [{"id": str(c.get('id')), "name": c.get('name')} for c in categories]
    })
    
    print("\n" + "="*60)
    print(f"✅ 已初始化 {len(categories)} 个领域缓存")
    print("="*60)


if __name__ == "__main__":
    main()
