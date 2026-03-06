#!/usr/bin/env python3
"""
交互式推荐脚本 - 与用户交互后生成推荐
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import load_config, save_cache, load_cache, DiscourseAPI


def get_user_profile(skill_dir, username):
    """获取用户画像，如果不存在则创建新的"""
    profiles_dir = os.path.join(skill_dir, "profiles")
    profile_file = os.path.join(profiles_dir, f"{username}.json")
    
    if os.path.exists(profile_file):
        return load_cache(profile_file)
    
    # 创建新用户画像
    new_profile = {
        "username": username,
        "created_at": datetime.now().isoformat(),
        "interests": {
            "keywords": [],
            "categories": [],
            "recent_topics": []
        },
        "preferences": {
            "freshness_weight": 0.3,
            "popularity_weight": 0.4,
            "personalization_weight": 0.3
        },
        "interaction_history": [],
        "recommendation_history": []
    }
    
    return new_profile


def save_user_profile(skill_dir, username, profile):
    """保存用户画像"""
    profiles_dir = os.path.join(skill_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    profile_file = os.path.join(profiles_dir, f"{username}.json")
    profile["updated_at"] = datetime.now().isoformat()
    save_cache(profile_file, profile)


def load_candidate_posts(skill_dir):
    """从所有领域缓存加载候选帖子"""
    domains_dir = os.path.join(skill_dir, "domains")
    all_posts = []
    
    if not os.path.exists(domains_dir):
        return all_posts
    
    for domain_dirname in os.listdir(domains_dir):
        domain_dir = os.path.join(domains_dir, domain_dirname)
        if not os.path.isdir(domain_dir):
            continue
        
        # 加载 L1 热门池
        l1_file = os.path.join(domain_dir, "l1_hot.json")
        if os.path.exists(l1_file):
            data = load_cache(l1_file)
            all_posts.extend(data.get("topics", []))
        
        # 加载 L3 新鲜池
        l3_file = os.path.join(domain_dir, "l3_fresh.json")
        if os.path.exists(l3_file):
            data = load_cache(l3_file)
            all_posts.extend(data.get("topics", []))
    
    # 去重
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        post_id = post.get("id")
        if post_id and post_id not in seen_ids:
            seen_ids.add(post_id)
            unique_posts.append(post)
    
    return unique_posts


def filter_posts_by_keywords(posts, keywords):
    """根据关键词过滤帖子"""
    if not keywords:
        return posts
    
    filtered = []
    for post in posts:
        title = post.get("title", "").lower()
        for keyword in keywords:
            if keyword.lower() in title:
                filtered.append(post)
                break
    
    return filtered


def score_posts(posts, profile):
    """根据用户画像给帖子打分"""
    user_keywords = [k.lower() for k in profile.get("interests", {}).get("keywords", [])]
    recent_topic_ids = set(profile.get("interests", {}).get("recent_topics", []))
    
    scored = []
    for post in posts:
        score = 0
        post_id = post.get("id")
        title = post.get("title", "").lower()
        
        # 1. 关键词匹配
        keyword_match = sum(1 for kw in user_keywords if kw in title)
        score += keyword_match * 10
        
        # 2. 热门度
        score += post.get("like_count", 0) * 2
        score += post.get("posts_count", 0)
        
        # 3. 新颖性（不推荐最近看过的）
        if post_id in recent_topic_ids:
            score -= 50
        
        scored.append((post, score))
    
    # 按分数排序
    scored.sort(key=lambda x: x[1], reverse=True)
    return [post for post, score in scored if score > 0]


def update_profile_with_feedback(profile, recommended_posts, user_feedback=None):
    """根据推荐结果和用户反馈更新用户画像"""
    interests = profile.setdefault("interests", {})
    keywords = interests.setdefault("keywords", [])
    recent_topics = interests.setdefault("recent_topics", [])
    interaction_history = profile.setdefault("interaction_history", [])
    recommendation_history = profile.setdefault("recommendation_history", [])
    
    # 记录推荐历史
    recommendation_entry = {
        "timestamp": datetime.now().isoformat(),
        "recommended_post_ids": [p.get("id") for p in recommended_posts],
        "feedback": user_feedback
    }
    recommendation_history.append(recommendation_entry)
    
    # 保留最近 50 条推荐历史
    if len(recommendation_history) > 50:
        recommendation_history = recommendation_history[-50:]
    
    # 从推荐帖子中提取关键词（简单版本）
    for post in recommended_posts[:3]:  # 只看前 3 个
        title = post.get("title", "")
        # 简单提取：如果标题里有常见关键词，加入用户兴趣
        common_tech_keywords = ["ai", "coding", "代码", "编程", "github", "git", "项目", "开源", 
                               "python", "javascript", "机器学习", "深度学习", "神经网络"]
        for keyword in common_tech_keywords:
            if keyword.lower() in title.lower() and keyword not in keywords:
                keywords.append(keyword)
    
    # 只保留最近 20 个关键词
    if len(keywords) > 20:
        keywords = keywords[-20:]
    
    # 更新最近浏览的帖子
    for post in recommended_posts:
        post_id = post.get("id")
        if post_id not in recent_topics:
            recent_topics.append(post_id)
    
    # 只保留最近 30 个浏览记录
    if len(recent_topics) > 30:
        recent_topics = recent_topics[-30:]
    
    return profile


def main():
    parser = argparse.ArgumentParser(description="交互式推荐 - 准备推荐数据")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--keywords", help="推荐关键词（逗号分隔）")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    parser.add_argument("--top", type=int, default=5, help="推荐数量")
    parser.add_argument("--output", help="输出推荐结果到 JSON 文件")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*70)
    print("🤖 Discourse 交互式推荐 - 数据准备阶段")
    print("="*70)
    
    # 1. 获取用户画像
    print(f"\n👤 加载用户画像: {args.username}")
    profile = get_user_profile(skill_dir, args.username)
    print(f"   ✅ 用户画像已加载（创建时间: {profile.get('created_at', '新用户')}）")
    
    # 2. 解析关键词
    keywords = []
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
        print(f"\n🔍 推荐关键词: {', '.join(keywords)}")
    
    # 合并用户画像中的关键词
    user_keywords = profile.get("interests", {}).get("keywords", [])
    all_keywords = list(set(keywords + user_keywords))
    if all_keywords:
        print(f"📚 所有关键词（含历史）: {', '.join(all_keywords)}")
    
    # 3. 加载候选帖子
    print("\n📦 加载候选帖子...")
    candidate_posts = load_candidate_posts(skill_dir)
    print(f"   ✅ 加载了 {len(candidate_posts)} 个候选帖子")
    
    # 4. 关键词过滤
    filtered_posts = filter_posts_by_keywords(candidate_posts, all_keywords)
    if filtered_posts:
        print(f"🎯 关键词匹配后: {len(filtered_posts)} 个帖子")
    else:
        print("⚠️  关键词未匹配到帖子，使用全部候选")
        filtered_posts = candidate_posts
    
    # 5. 根据用户画像排序
    print("\n📊 根据用户画像排序...")
    ranked_posts = score_posts(filtered_posts, profile)
    final_posts = ranked_posts[:args.top]
    print(f"   ✅ 精选 Top {len(final_posts)} 个帖子")
    
    # 6. 输出结果
    result = {
        "username": args.username,
        "keywords": keywords,
        "all_keywords": all_keywords,
        "recommendations": final_posts,
        "generated_at": datetime.now().isoformat()
    }
    
    if args.output:
        save_cache(args.output, result)
        print(f"\n💾 推荐结果已保存到: {args.output}")
    
    # 7. 显示推荐列表（供 agent 使用）
    print("\n" + "="*70)
    print("📋 推荐列表（供 agent 编写推荐理由）")
    print("="*70)
    
    for i, post in enumerate(final_posts, 1):
        post_id = post.get("id")
        title = post.get("title")
        slug = post.get("slug", "topic")
        config = load_config(args.config)
        url = f"{config['discourse_url']}/t/{slug}/{post_id}"
        
        print(f"\n{i}. {title}")
        print(f"   🔗 {url}")
        print(f"   数据: id={post_id}, likes={post.get('like_count', 0)}, replies={post.get('posts_count', 0)}")
    
    print("\n" + "="*70)
    print("✅ 数据准备完成！请 agent 编写推荐理由并发送给用户")
    print("="*70)
    
    # 8. 保存临时数据供后续更新画像使用
    temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
    save_cache(temp_file, {
        "recommended_posts": final_posts,
        "keywords": keywords
    })
    print(f"\n📝 临时数据已保存，用于后续更新用户画像")


if __name__ == "__main__":
    main()
