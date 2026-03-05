#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache, DiscourseAPI


def main():
    parser = argparse.ArgumentParser(description="简单分类领域初始化")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    parser.add_argument("--init", action="store_true", help="初始化分类领域")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*60)
    print("分类领域初始化")
    print("="*60)
    
    if not args.init:
        print("\n使用 --init 初始化分类领域")
        return
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    categories = api.get_categories()
    domains = []
    
    for cat in categories:
        domains.append({
            "id": str(cat.get('id')),
            "name": cat.get('name'),
            "categories": [cat.get('id')]
        })
    
    save_cache(os.path.join(skill_dir, "domains.json"), {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "domains": domains
    })
    
    print(f"\n✅ 已初始化 {len(domains)} 个分类领域")
    for d in domains:
        print(f"  - {d['name']} (id: {d['id']})")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
