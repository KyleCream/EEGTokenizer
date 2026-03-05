#!/usr/bin/env python3
"""
为单个用户构建兴趣画像
- 收集用户活动
- 构建画像
- 保存到 profiles/ 目录
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI


def get_user_activity(api, username):
    """获取用户活动记录"""
    try:
        data = api._get(f"/u/{username}.json")
        return []
    except:
        return []


def build_simple_profile(user_activity, topics):
    """简单构建用户画像（基于分类偏好）"""
    category_counts = Counter()
    
    seen_topic_ids = set()
    for action in user_activity:
        topic_id = action.get('topic_id')
        if topic_id:
            seen_topic_ids.add(topic_id)
    
    for topic in topics:
        if topic.get('id') in seen_topic_ids:
            cat_id = topic.get('category_id')
            if cat_id:
                category_counts[cat_id] += 1
    
    category_preference = {}
    if category_counts:
        max_count = max(category_counts.values())
        for cat_id, count in category_counts.items():
            category_preference[str(cat_id)] = count / max_count
    
    return {
        "username": None,
        "category_preference": category_preference,
        "seen_topic_ids": list(seen_topic_ids)
    }


def main():
    parser = argparse.ArgumentParser(description="构建用户画像")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--username", required=True, help="目标用户名")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    profiles_dir = os.path.join(skill_dir, "profiles")
    
    print("="*60)
    print("构建用户画像")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    print(f"\n目标用户: {args.username}")
    
    print("\n收集最新帖子...")
    all_topics = []
    for page in range(3):
        all_topics.extend(api.get_latest_topics(page, per_page=30))
    
    print("\n获取用户活动...")
    user_activity = get_user_activity(api, args.username)
    print(f"   活动记录: {len(user_activity)} 条")
    
    print("\n构建用户画像...")
    profile = build_simple_profile(user_activity, all_topics)
    profile["username"] = args.username
    profile["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    profile_path = os.path.join(profiles_dir, f"{args.username}.json")
    save_cache(profile_path, profile)
    
    print(f"\n✅ 用户画像已保存到: {profile_path}")
    print(f"   分类偏好: {profile.get('category_preference', {})}")
    print(f"   已看话题: {len(profile.get('seen_topic_ids', []))} 个")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
