#!/usr/bin/env python3
"""
推荐完成后更新用户画像（有机结合新旧版）
"""
import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache
from interactive_recommend import get_user_profile, save_user_profile


def update_profile_with_recommendations(profile, recommended_posts, user_feedback=None):
    """根据推荐结果更新用户画像（有机结合新旧版）"""
    interests = profile.setdefault("interests", {})
    keywords = interests.setdefault("keywords", [])
    domain_ids = interests.setdefault("domain_ids", [])
    recent_topics = interests.setdefault("recent_topics", [])
    interaction_history = profile.setdefault("interaction_history", [])
    recommendation_history = profile.setdefault("recommendation_history", [])
    
    # 记录推荐历史
    recommendation_entry = {
        "timestamp": recommendation_history[-1]["timestamp"] if recommendation_history else None,
        "recommended_post_ids": [p.get("id") for p in recommended_posts],
        "feedback": user_feedback
    }
    recommendation_history.append(recommendation_entry)
    
    # 保留最近 50 条推荐历史
    if len(recommendation_history) > 50:
        recommendation_history = recommendation_history[-50:]
    
    # ========== 从推荐帖子中提取信息 ==========
    
    # 1. 提取领域ID（新版核心：记录用户感兴趣的领域）
    recommended_domain_ids = set()
    for post in recommended_posts:
        domain_id = post.get("_domain_id")
        if domain_id and domain_id not in recommended_domain_ids:
            recommended_domain_ids.add(domain_id)
    
    # 更新用户感兴趣的领域（如果有新领域，加入）
    for domain_id in recommended_domain_ids:
        if domain_id not in domain_ids:
            domain_ids.append(domain_id)
    
    # 只保留最近 10 个领域
    if len(domain_ids) > 10:
        domain_ids = domain_ids[-10:]
    
    # 2. 提取关键词（旧版逻辑）
    common_tech_keywords = ["ai", "coding", "代码", "编程", "github", "git", "项目", "开源", 
                           "python", "javascript", "机器学习", "深度学习", "神经网络",
                           "music", "音乐", "blockchain", "区块链", "cloud", "云原生",
                           "rust", "web", "前端", "后端", "api", "工具", "prompt"]
    
    for post in recommended_posts[:3]:  # 只看前 3 个
        title = post.get("title", "")
        for keyword in common_tech_keywords:
            if keyword.lower() in title.lower() and keyword not in keywords:
                keywords.append(keyword)
    
    # 只保留最近 30 个关键词
    if len(keywords) > 30:
        keywords = keywords[-30:]
    
    # 3. 更新最近浏览的帖子
    for post in recommended_posts:
        post_id = post.get("id")
        if post_id and post_id not in recent_topics:
            recent_topics.append(post_id)
    
    # 只保留最近 30 个浏览记录
    if len(recent_topics) > 30:
        recent_topics = recent_topics[-30:]
    
    return profile


def main():
    parser = argparse.ArgumentParser(description="推荐完成后更新用户画像（有机结合新旧版）")
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
    print("📝 更新用户画像（有机结合新旧版）")
    print("="*70)
    
    # ========== 步骤 1：加载用户画像 ==========
    print(f"\n👤 加载用户画像: {args.username}")
    profile = get_user_profile(skill_dir, args.username)
    
    # ========== 步骤 2：加载推荐数据 ==========
    recommended_posts = []
    target_domain_ids = []
    
    if args.temp_file and os.path.exists(args.temp_file):
        temp_data = load_cache(args.temp_file)
        recommended_posts = temp_data.get("recommended_posts", [])
        target_domain_ids = temp_data.get("target_domain_ids", [])
        print(f"   ✅ 从临时文件加载了 {len(recommended_posts)} 个推荐帖子")
    else:
        # 尝试默认临时文件位置
        temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
        if os.path.exists(temp_file):
            temp_data = load_cache(temp_file)
            recommended_posts = temp_data.get("recommended_posts", [])
            target_domain_ids = temp_data.get("target_domain_ids", [])
            print(f"   ✅ 从默认临时文件加载了 {len(recommended_posts)} 个推荐帖子")
    
    if not recommended_posts:
        print("   ⚠️  没有找到推荐数据")
        return
    
    # ========== 步骤 3：更新用户画像 ==========
    print("\n🔄 更新用户画像...")
    updated_profile = update_profile_with_recommendations(
        profile, 
        recommended_posts, 
        args.feedback
    )
    
    # ========== 步骤 4：保存用户画像 ==========
    save_user_profile(skill_dir, args.username, updated_profile)
    print("   ✅ 用户画像已更新")
    
    # ========== 步骤 5：显示更新摘要 ==========
    print("\n" + "="*70)
    print("📊 更新摘要")
    print("="*70)
    
    interests = updated_profile.get("interests", {})
    keywords = interests.get("keywords", [])
    domain_ids = interests.get("domain_ids", [])
    recent_topics = interests.get("recent_topics", [])
    rec_history = updated_profile.get("recommendation_history", [])
    
    print(f"\n👤 用户: {args.username}")
    print(f"🎯 感兴趣领域: {len(domain_ids)} 个")
    if domain_ids:
        print(f"   {', '.join(domain_ids)}")
    print(f"📚 兴趣关键词: {len(keywords)} 个")
    if keywords:
        print(f"   {', '.join(keywords[-10:])}")  # 显示最近 10 个
    print(f"📖 最近浏览: {len(recent_topics)} 个帖子")
    print(f"📋 推荐历史: {len(rec_history)} 次")
    
    # ========== 步骤 6：清理临时文件 ==========
    temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
    if os.path.exists(temp_file):
        os.remove(temp_file)
        print(f"\n🧹 临时文件已清理")
    
    print("\n" + "="*70)
    print("✅ 用户画像更新完成！")
    print("="*70)


if __name__ == "__main__":
    main()
