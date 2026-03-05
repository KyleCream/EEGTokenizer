#!/usr/bin/env python3
"""
从用户所属领域推荐帖子（高级版）
- 查用户所属领域
- 从这些领域的 L1/L2/L3 中合并候选
- 去重、排序、输出 Top N
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, load_cache, save_cache, sort_topics_by


def get_user_domain_ids(username: str, user_domains_path: str) -> List[str]:
    """获取用户所属的领域 ID 列表"""
    user_domains = load_cache(user_domains_path) or {}
    return user_domains.get(username, [])


def load_domain_candidates(skill_dir: str, domain_ids: List[str]) -> List[Dict]:
    """从指定领域加载候选帖子"""
    candidates = []
    
    for domain_id in domain_ids:
        domain_dir = os.path.join(skill_dir, "domains", f"domain_{domain_id}")
        
        l1_path = os.path.join(domain_dir, "l1_hot.json")
        l1 = load_cache(l1_path) or {"topics": []}
        candidates.extend(l1.get("topics", []))
        
        l2_path = os.path.join(domain_dir, "l2_category.json")
        l2 = load_cache(l2_path) or {"categories": {}}
        for cat_data in l2.get("categories", {}).values():
            candidates.extend(cat_data.get("topics", []))
        
        l3_path = os.path.join(domain_dir, "l3_fresh.json")
        l3 = load_cache(l3_path) or {"topics": []}
        candidates.extend(l3.get("topics", []))
    
    return candidates


def load_global_candidates(skill_dir: str) -> List[Dict]:
    """加载全局冷启动候选"""
    cache_dir = os.path.join(skill_dir, "cache")
    candidates = []
    
    l1_path = os.path.join(cache_dir, "global_l1_hot.json")
    l1 = load_cache(l1_path) or {"topics": []}
    candidates.extend(l1.get("topics", []))
    
    l2_path = os.path.join(cache_dir, "global_l2_category.json")
    l2 = load_cache(l2_path) or {"categories": {}}
    for cat_data in l2.get("categories", {}).values():
        candidates.extend(cat_data.get("topics", []))
    
    l3_path = os.path.join(cache_dir, "global_l3_fresh.json")
    l3 = load_cache(l3_path) or {"topics": []}
    candidates.extend(l3.get("topics", []))
    
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
    parser = argparse.ArgumentParser(description="从用户所属领域推荐帖子（高级版）")
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
    
    print("="*60)
    print("Discourse 推荐服务（高级版）")
    print("="*60)
    print(f"目标用户: {args.username}")
    print(f"推荐数量: {args.top}")
    
    config = load_config(args.config)
    
    # 先尝试用领域模式
    user_domains_path = os.path.join(skill_dir, "user_domains.json")
    domain_ids = get_user_domain_ids(args.username, user_domains_path)
    
    if domain_ids:
        print(f"\n用户所属领域: {domain_ids}")
        candidates = load_domain_candidates(skill_dir, domain_ids)
        print(f"从领域加载候选: {len(candidates)} 帖")
    else:
        print(f"\n⚠️ 用户无领域映射，使用全局冷启动缓存")
        candidates = load_global_candidates(skill_dir)
        print(f"从全局加载候选: {len(candidates)} 帖")
    
    ranked = deduplicate_and_rank(candidates)
    print(f"去重后: {len(ranked)} 帖")
    
    print_recommendations(ranked, config["discourse_url"], args.top)
    
    if args.output:
        result = {
            "username": args.username,
            "generated_at": None,
            "domains": domain_ids,
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
