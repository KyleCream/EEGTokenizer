#!/usr/bin/env python3
"""
推荐完成后更新用户画像
"""
import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache
from interactive_recommend import get_user_profile, save_user_profile, update_profile_with_feedback


def main():
    parser = argparse.ArgumentParser(description="推荐完成后更新用户画像")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    parser.add_argument("--feedback", help="用户反馈（可选）")
    parser.add_argument("--temp-file", help="临时推荐数据文件路径（可选）")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*70)
    print("📝 更新用户画像")
    print("="*70)
    
    # 1. 获取用户画像
    print(f"\n👤 加载用户画像: {args.username}")
    profile = get_user_profile(skill_dir, args.username)
    
    # 2. 加载推荐数据
    recommended_posts = []
    if args.temp_file and os.path.exists(args.temp_file):
        temp_data = load_cache(args.temp_file)
        recommended_posts = temp_data.get("recommended_posts", [])
        print(f"   ✅ 从临时文件加载了 {len(recommended_posts)} 个推荐帖子")
    else:
        # 尝试默认临时文件位置
        temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
        if os.path.exists(temp_file):
            temp_data = load_cache(temp_file)
            recommended_posts = temp_data.get("recommended_posts", [])
            print(f"   ✅ 从默认临时文件加载了 {len(recommended_posts)} 个推荐帖子")
    
    if not recommended_posts:
        print("   ⚠️  没有找到推荐数据")
        return
    
    # 3. 更新用户画像
    print("\n🔄 更新用户画像...")
    updated_profile = update_profile_with_feedback(
        profile, 
        recommended_posts, 
        args.feedback
    )
    
    # 4. 保存用户画像
    save_user_profile(skill_dir, args.username, updated_profile)
    print("   ✅ 用户画像已更新")
    
    # 5. 显示更新摘要
    print("\n" + "="*70)
    print("📊 更新摘要")
    print("="*70)
    
    interests = updated_profile.get("interests", {})
    keywords = interests.get("keywords", [])
    recent_topics = interests.get("recent_topics", [])
    rec_history = updated_profile.get("recommendation_history", [])
    
    print(f"\n👤 用户: {args.username}")
    print(f"📚 兴趣关键词: {len(keywords)} 个")
    if keywords:
        print(f"   {', '.join(keywords[-10:])}")  # 显示最近 10 个
    print(f"📖 最近浏览: {len(recent_topics)} 个帖子")
    print(f"📋 推荐历史: {len(rec_history)} 次")
    
    # 6. 清理临时文件
    temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
    if os.path.exists(temp_file):
        os.remove(temp_file)
        print(f"\n🧹 临时文件已清理")
    
    print("\n" + "="*70)
    print("✅ 用户画像更新完成！")
    print("="*70)


if __name__ == "__main__":
    main()
