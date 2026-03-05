#!/usr/bin/env python3
"""
为单个用户构建完整兴趣画像
- 收集用户活动
- 构建画像（Tags为主 + 关键词保底）
- 保存到 profiles/ 目录
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, DiscourseAPI
from build_profile import ProfileBuilder


def get_user_activity(api, username):
    """获取用户活动记录"""
    try:
        data = api._get(f"/u/{username}/activity.json")
        if isinstance(data, list):
            return data
        return data.get('user_actions', [])
    except Exception as e:
        print(f"⚠️ 获取用户活动失败: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="构建完整用户画像")
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
    print("构建完整用户画像")
    print("="*60)
    
    config = load_config(args.config)
    api = DiscourseAPI(config)
    
    print(f"\n目标用户: {args.username}")
    
    print("\n收集论坛帖子...")
    all_topics = []
    for page in range(3):
        all_topics.extend(api.get_latest_topics(page, per_page=30))
    top_topics = api.get_top_topics("weekly") + api.get_top_topics("monthly")
    all_topics.extend(top_topics)
    print(f"   收集到 {len(all_topics)} 个帖子")
    
    print("\n获取用户活动...")
    user_activity = get_user_activity(api, args.username)
    print(f"   活动记录: {len(user_activity)} 条")
    
    print("\n构建用户画像...")
    profile_builder = ProfileBuilder()
    profile = profile_builder.build(
        {"activity": user_activity, "topics": []},
        all_topics
    )
    
    profile_dict = profile.to_dict()
    profile_dict["username"] = args.username
    profile_dict["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    profile_path = os.path.join(profiles_dir, f"{args.username}.json")
    save_cache(profile_path, profile_dict)
    
    print(f"\n✅ 用户画像已保存到: {profile_path}")
    print(f"   Tags 偏好: {len(profile_dict.get('tag_preference', {}))} 个")
    print(f"   分类偏好: {len(profile_dict.get('category_preference', {}))} 个")
    print(f"   作者偏好: {len(profile_dict.get('author_preference', {}))} 个")
    print(f"   已看话题: {len(profile_dict.get('seen_topic_ids', []))} 个")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
