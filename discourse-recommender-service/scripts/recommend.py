#!/usr/bin/env python3
"""
从分层缓存中推荐帖子
- 合并 L1（热门）+ L2（分类）+ L3（新鲜）
- 简单排序，去重，输出 Top N
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache


def load_all_caches(cache_dir: str) -> Dict[str, Any]:
    """加载所有分层缓存"""
    l1 = load_cache(os.path.join(cache_dir, "l1_hot.json")) or {"topics": []}
    l2 = load_cache(os.path.join(cache_dir, "l2_category.json")) or {"categories": {}}
    l3 = load_cache(os.path.join(cache_dir, "l3_fresh.json")) or {"topics": []}
    return {
        "l1": l1,
        "l2": l2,
        "l3": l3
    }


def collect_candidates(caches: Dict[str, Any]) -> List[Dict]:
    """从各层收集候选帖子"""
    candidates = []
    
    # L1: 热门池
    candidates.extend(caches["l1"].get("topics", []))
    
    # L2: 分类池（合并所有分类）
    for cat_id, cat_data in caches["l2"].get("categories", {}).items():
        candidates.extend(cat_data.get("topics", []))
    
    # L3: 新鲜池
    candidates.extend(caches["l3"].get("topics", []))
    
    return candidates


def deduplicate_and_rank(topics: List[Dict]) -> List[Dict]:
    """去重并简单排序"""
    seen_ids = set()
    unique_topics = []
    
    for topic in topics:
        tid = topic.get("id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique_topics.append(topic)
    
    # 简单排序：新鲜度（默认按原顺序） + 热度
    def score(topic: Dict) -> float:
        likes = topic.get("like_count", 0)
        posts = topic.get("posts_count", 0)
        return (likes * 2) + posts
    
    unique_topics.sort(key=score, reverse=True)
    return unique_topics


def print_recommendations(topics: List[Dict], base_url: str, top_k: int):
    """打印推荐结果"""
    print("\n" + "="*80)
    print("🎯 为您推荐的帖子".center(80))
    print("="*80)
    
    for i, topic in enumerate(topics[:top_k], 1):
        title = topic.get('title', '无标题')
        topic_id = topic.get('id')
        url = f"{base_url}/t/{topic_id}"
        posts_count = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        views = topic.get('views', 0)
        
        print(f"\n{i}. {title}")
        print(f"   💬 回复: {posts_count} | ❤️ 点赞: {likes} | 👁️ 浏览: {views}")
        print(f"   🔗 链接: {url}")
    
    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description="从分层缓存推荐帖子")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--username", required=True, help="目标用户名")
    parser.add_argument("--top", type=int, default=10, help="推荐数量")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    parser.add_argument("--output", help="输出推荐结果到 JSON 文件（可选）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    cache_dir = os.path.join(skill_dir, "cache")
    
    print("="*60)
    print("Discourse 推荐服务")
    print("="*60)
    print(f"目标用户: {args.username}")
    print(f"推荐数量: {args.top}")
    
    config = load_config(args.config)
    caches = load_all_caches(cache_dir)
    
    print(f"\n加载缓存:")
    print(f"  L1（热门）: {len(caches['l1'].get('topics', []))} 帖")
    print(f"  L2（分类）: {len(caches['l2'].get('categories', {}))} 个分类")
    print(f"  L3（新鲜）: {len(caches['l3'].get('topics', []))} 帖")
    
    candidates = collect_candidates(caches)
    print(f"\n候选池: {len(candidates)} 帖")
    
    ranked = deduplicate_and_rank(candidates)
    print(f"去重后: {len(ranked)} 帖")
    
    print_recommendations(ranked, config["discourse_url"], args.top)
    
    if args.output:
        result = {
            "username": args.username,
            "generated_at": None,
            "recommendations": [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "url": f"{config['discourse_url']}/t/{t.get('id')}",
                    "likes": t.get("like_count", 0),
                    "posts": t.get("posts_count", 0)
                }
                for t in ranked[:args.top]
            ]
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")
    
    print("\n" + "="*60)
    print("✅ 推荐完成！")
    print("="*60)


if __name__ == "__main__":
    main()
