#!/usr/bin/env python3
"""
领域聚类 + agent 审核
- 收集所有用户画像
- 自动聚类
- 生成待审核文件
- agent 审核后应用
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache


def collect_all_profiles(profiles_dir: str) -> List[Dict[str, Any]]:
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


def simple_cluster_profiles(profiles: List[Dict[str, Any]], num_domains: int = 5) -> List[Dict[str, Any]]:
    """简单的基于标签的聚类（placeholder，实际可用 K-Means）"""
    # 简化版：根据分类偏好分组
    domains = {}
    
    for profile in profiles:
        cats = profile.get('category_preference', {})
        for cat_id, weight in cats.items():
            if weight > 0.5:
                if cat_id not in domains:
                    domains[cat_id] = {
                        'id': str(cat_id),
                        'name': f"领域 {cat_id}",
                        'keywords': [],
                        'categories': [cat_id],
                        'profiles': []
                    }
                domains[cat_id]['profiles'].append(profile.get('username', 'unknown'))
    
    # 限制领域数
    domain_list = list(domains.values())[:num_domains]
    
    # 如果不够，补充通用领域
    while len(domain_list) < num_domains:
        domain_list.append({
            'id': f"general_{len(domain_list)}",
            'name': f"通用领域 {len(domain_list)}",
            'keywords': [],
            'categories': [],
            'profiles': []
        })
    
    return domain_list


def main():
    parser = argparse.ArgumentParser(description="领域聚类 + agent 审核")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径（默认自动检测）")
    parser.add_argument("--output", help="输出待审核文件路径")
    parser.add_argument("--approve", help="应用已审核的文件")
    parser.add_argument("--num-domains", type=int, default=5, help="领域数量（默认 5）")
    
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
    
    if args.approve:
        # 应用已审核的领域
        print(f"\n应用已审核的领域: {args.approve}")
        with open(args.approve, 'r', encoding='utf-8') as f:
            approved = json.load(f)
        
        domains = approved.get('domains', [])
        user_domains = approved.get('user_domains', {})
        
        # 保存领域定义
        save_cache(os.path.join(skill_dir, "domains.json"), {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "domains": domains
        })
        
        # 保存用户-领域映射
        save_cache(os.path.join(skill_dir, "user_domains.json"), user_domains)
        
        print(f"\n✅ 已应用 {len(domains)} 个领域")
        print(f"✅ 已保存 {len(user_domains)} 个用户的领域映射")
        return
    
    # 聚类模式
    config = load_config(args.config)
    
    print(f"\n收集用户画像...")
    profiles = collect_all_profiles(profiles_dir)
    print(f"   找到 {len(profiles)} 个用户画像")
    
    if not profiles:
        print("\n⚠️ 没有用户画像，无法聚类")
        print("   先运行推荐系统生成一些用户画像")
        return
    
    print(f"\n聚类领域（数量: {args.num_domains}）...")
    domains = simple_cluster_profiles(profiles, args.num_domains)
    print(f"   生成 {len(domains)} 个领域")
    
    # 生成用户-领域映射（简化版：随机分配）
    user_domains = {}
    for profile in profiles:
        username = profile.get('username', 'unknown')
        user_domains[username] = [d['id'] for d in domains[:2]]  # 每个用户先分配 2 个领域
    
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
