#!/usr/bin/env python3
"""
领域聚类 + agent 审核
- 收集所有用户画像
- 简单基于分类偏好的聚类（placeholder，可替换为 K-Means）
- 生成待审核文件
- agent 审核后应用
"""
import argparse
import json
import os
import sys
import time
import shutil
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache, DiscourseAPI, sort_topics_by


def collect_all_profiles(profiles_dir):
    """收集所有用户画像"""
    profiles = []
    if os.path.exists(profiles_dir):
        for filename in os.listdir(profiles_dir):
            if filename.endswith('.json'):
                path = os.path.join(profiles_dir, filename)
                profile = load_cache(path)
                if profile:
                    profiles.append(profile)
    return profiles


def simple_cluster_by_category(categories, profiles):
    """简单聚类：基于分类偏好（placeholder，可升级为 K-Means）"""
    domains = []
    
    for cat in categories:
        cat_id = cat.get('id')
        domains.append({
            "id": str(cat_id),
            "name": cat.get('name'),
            "categories": [cat_id],
            "keywords": []
        })
    
    return domains


def initialize_domain_cache(skill_dir, domain, all_topics, top_topics):
    """初始化单个领域的 L1/L3 缓存"""
    domain_id = domain["id"]
    domain_dir = os.path.join(skill_dir, "domains", f"domain_{domain_id}")
    domain_cats = set(domain.get("categories", []))
    
    if os.path.exists(domain_dir):
        shutil.rmtree(domain_dir)
    os.makedirs(domain_dir, exist_ok=True)
    
    domain_topics = [t for t in all_topics if t.get('category_id') in domain_cats]
    
    # L1: 领域热门
    domain_l1 = [t for t in top_topics if t.get('category_id') in domain_cats]
    domain_l1 += sort_topics_by(domain_topics, "like_count")
    domain_l1 = sort_topics_by(domain_l1, "like_count")[:50]
    save_cache(os.path.join(domain_dir, "l1_hot.json"), {"topics": domain_l1})
    
    # L3: 领域新鲜
    domain_l3 = sort_topics_by(domain_topics, "created_at", reverse=True)[:100]
    save_cache(os.path.join(domain_dir, "l3_fresh.json"), {"topics": domain_l3})
    
    return len(domain_l1), len(domain_l3)


def main():
    parser = argparse.ArgumentParser(description="领域聚类 + agent 审核")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    parser.add_argument("--output", help="输出待审核文件路径")
    parser.add_argument("--approve", help="应用已审核的文件")
    parser.add_argument("--num-domains", type=int, default=5, help="目标领域数（默认 5）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    profiles_dir = os.path.join(skill_dir, "profiles")
    domains_dir = os.path.join(skill_dir, "domains")
    
    print("="*60)
    print("Discourse 推荐服务 - 领域聚类")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    if args.approve:
        # 应用已审核的领域
        print(f"\n应用已审核的领域: {args.approve}")
        with open(args.approve, 'r', encoding='utf-8') as f:
            approved = json.load(f)
        
        domains = approved.get('domains', [])
        user_domains = approved.get('user_domains', {})
        
        # 获取全站帖子用于初始化领域缓存
        print("\n获取全站帖子...")
        all_topics = []
        for page in range(4):
            all_topics.extend(api.get_latest_topics(page, per_page=30))
        top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
        
        # 初始化每个领域的缓存
        print(f"\n初始化 {len(domains)} 个领域缓存...")
        for domain in domains:
            l1_count, l3_count = initialize_domain_cache(skill_dir, domain, all_topics, top_topics)
            print(f"  - {domain['name']}: L1={l1_count}, L3={l3_count}")
        
        # 保存领域定义和用户-领域映射
        save_cache(os.path.join(skill_dir, "domains.json"), {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "domains": domains
        })
        save_cache(os.path.join(skill_dir, "user_domains.json"), user_domains)
        
        print(f"\n✅ 已应用 {len(domains)} 个领域")
        print(f"✅ 已保存 {len(user_domains)} 个用户的领域映射")
        print("\n" + "="*60)
        return
    
    # 聚类模式
    categories = api.get_categories()
    profiles = collect_all_profiles(profiles_dir)
    
    print(f"\n收集到 {len(profiles)} 个用户画像")
    if not profiles:
        print("\n⚠️ 没有用户画像，使用分类作为初始领域")
    
    # 简单聚类：当前用分类，后续可替换为 K-Means
    domains = simple_cluster_by_category(categories, profiles)
    
    # 简单用户-领域映射（placeholder）
    user_domains = {}
    for profile in profiles:
        username = profile.get('username', 'unknown')
        user_cats = profile.get('category_preference', {})
        top_cats = sorted(user_cats.items(), key=lambda x: x[1], reverse=True)[:2]
        user_domains[username] = [str(cat_id) for cat_id, _ in top_cats] if top_cats else [d['id'] for d in domains[:2]]
    
    # 生成待审核文件
    audit_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "num_profiles": len(profiles),
        "domains": domains,
        "user_domains": user_domains,
        "instructions": """请审核领域划分：
1. 检查每个领域的 name/keywords/categories 是否合理
2. 可以修改领域名称、关键词、分类
3. 检查 user_domains，用户分配的领域是否合理
4. 修改后保存，用 --approve 应用"""
    }
    
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(skill_dir, f"pending_audit_{int(time.time())}.json")
    
    save_cache(output_path, audit_data)
    
    print(f"\n✅ 待审核文件已生成: {output_path}")
    print("\n下一步:")
    print(f"1. agent 审核该文件")
    print(f"2. 运行: python3 scripts/cluster_domains.py --config config/config.json --approve {output_path}")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
