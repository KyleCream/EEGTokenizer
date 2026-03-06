#!/usr/bin/env python3
"""
交互式推荐脚本 - 与用户交互后生成推荐（有机结合新旧版）
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
            "domain_ids": [],  # 用户感兴趣的领域ID列表
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


def load_domains(skill_dir):
    """加载领域定义"""
    domains_file = os.path.join(skill_dir, "domains.json")
    if os.path.exists(domains_file):
        return load_cache(domains_file)
    return {"domains": []}


def load_posts_from_domains(skill_dir, domain_ids):
    """从指定领域加载帖子（L1 热门池 + L3 新鲜池）"""
    domains_dir = os.path.join(skill_dir, "domains")
    all_posts = []
    
    if not os.path.exists(domains_dir):
        return all_posts
    
    for domain_id in domain_ids:
        domain_dir = os.path.join(domains_dir, f"domain_{domain_id}")
        if not os.path.exists(domain_dir):
            continue
        
        # 加载 L1 热门池
        l1_file = os.path.join(domain_dir, "l1_hot.json")
        if os.path.exists(l1_file):
            data = load_cache(l1_file)
            posts = data.get("topics", [])
            # 标记来源
            for post in posts:
                post["_domain_id"] = domain_id
                post["_pool"] = "L1"
            all_posts.extend(posts)
        
        # 加载 L3 新鲜池
        l3_file = os.path.join(domain_dir, "l3_fresh.json")
        if os.path.exists(l3_file):
            data = load_cache(l3_file)
            posts = data.get("topics", [])
            # 标记来源
            for post in posts:
                post["_domain_id"] = domain_id
                post["_pool"] = "L3"
            all_posts.extend(posts)
    
    return all_posts


def score_posts_by_preferences(posts, profile):
    """根据用户偏好给帖子打分（有机结合新旧版）"""
    preferences = profile.get("preferences", {})
    freshness_weight = preferences.get("freshness_weight", 0.3)
    popularity_weight = preferences.get("popularity_weight", 0.4)
    personalization_weight = preferences.get("personalization_weight", 0.3)
    
    interests = profile.get("interests", {})
    user_keywords = [k.lower() for k in interests.get("keywords", [])]
    recent_topic_ids = set(interests.get("recent_topics", []))
    
    scored = []
    for post in posts:
        score = 0.0
        post_id = post.get("id")
        title = post.get("title", "").lower()
        
        # 1. 热门度（来自旧版）
        popularity_score = (post.get("like_count", 0) * 2) + post.get("posts_count", 0)
        score += popularity_score * popularity_weight
        
        # 2. 新颖性（不推荐最近看过的）
        if post_id in recent_topic_ids:
            score -= 50
        
        # 3. 个性化匹配（关键词匹配）
        keyword_match = sum(1 for kw in user_keywords if kw in title)
        score += keyword_match * 10 * personalization_weight
        
        # 4. L1 池优先（热门池）
        if post.get("_pool") == "L1":
            score += 5
        
        scored.append((post, score))
    
    # 按分数排序
    scored.sort(key=lambda x: x[1], reverse=True)
    return [post for post, score in scored if score > -100]


def update_profile_with_keywords(profile, keywords):
    """根据用户输入的关键词更新用户画像"""
    interests = profile.setdefault("interests", {})
    profile_keywords = interests.setdefault("keywords", [])
    
    # 添加新关键词
    for keyword in keywords:
        keyword = keyword.strip()
        if keyword and keyword not in profile_keywords:
            profile_keywords.append(keyword)
    
    # 只保留最近 30 个关键词
    if len(profile_keywords) > 30:
        profile_keywords = profile_keywords[-30:]
    
    return profile


def main():
    parser = argparse.ArgumentParser(description="交互式推荐 - 数据准备阶段（有机结合新旧版）")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--keywords", help="推荐关键词（逗号分隔，用于更新用户画像）")
    parser.add_argument("--domain-ids", help="指定领域ID（逗号分隔，可选，默认从用户画像获取）")
    parser.add_argument("--skill-dir", help="Skill 目录路径")
    parser.add_argument("--top", type=int, default=5, help="推荐数量")
    parser.add_argument("--output", help="输出推荐结果到 JSON 文件")
    
    args = parser.parse_args()
    
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = Path(SCRIPT_DIR).parent
    
    print("="*70)
    print("🤖 Discourse 交互式推荐 - 数据准备阶段（有机结合新旧版）")
    print("="*70)
    
    # ========== 步骤 1：加载领域定义 ==========
    print(f"\n📚 加载领域定义...")
    domains_data = load_domains(skill_dir)
    all_domains = domains_data.get("domains", [])
    print(f"   ✅ 已加载 {len(all_domains)} 个领域")
    for domain in all_domains:
        print(f"   - 领域 {domain['id']}: {domain['name']}")
    
    # ========== 步骤 2：加载/创建用户画像 ==========
    print(f"\n👤 加载用户画像: {args.username}")
    profile = get_user_profile(skill_dir, args.username)
    print(f"   ✅ 用户画像已加载（创建时间: {profile.get('created_at', '新用户')}）")
    
    # ========== 步骤 3：处理输入关键词（更新用户画像） ==========
    input_keywords = []
    if args.keywords:
        input_keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
        print(f"\n🔍 输入关键词: {', '.join(input_keywords)}")
        # 更新用户画像，加入这些关键词
        profile = update_profile_with_keywords(profile, input_keywords)
        save_user_profile(skill_dir, args.username, profile)
        print(f"   ✅ 用户画像已更新（关键词已加入）")
    
    # ========== 步骤 4：确定要从哪些领域获取帖子 ==========
    target_domain_ids = []
    if args.domain_ids:
        # 用户指定了领域
        target_domain_ids = [d.strip() for d in args.domain_ids.split(",") if d.strip()]
        print(f"\n🎯 使用指定领域: {', '.join(target_domain_ids)}")
    else:
        # 从用户画像获取感兴趣的领域
        interests = profile.get("interests", {})
        target_domain_ids = interests.get("domain_ids", [])
        if target_domain_ids:
            print(f"\n🎯 从用户画像获取领域: {', '.join(target_domain_ids)}")
        else:
            # 新用户，从所有领域获取
            target_domain_ids = [d["id"] for d in all_domains]
            print(f"\n🎯 新用户，从所有领域获取: {', '.join(target_domain_ids)}")
    
    # ========== 步骤 5：从目标领域加载候选帖子（L1 + L3） ==========
    print(f"\n📦 从领域加载候选帖子...")
    candidate_posts = load_posts_from_domains(skill_dir, target_domain_ids)
    print(f"   ✅ 加载了 {len(candidate_posts)} 个候选帖子")
    
    # 去重
    seen_ids = set()
    unique_posts = []
    for post in candidate_posts:
        post_id = post.get("id")
        if post_id and post_id not in seen_ids:
            seen_ids.add(post_id)
            unique_posts.append(post)
    
    print(f"   🧹 去重后: {len(unique_posts)} 个帖子")
    
    # ========== 步骤 6：根据用户偏好排序（有机结合新旧版） ==========
    print(f"\n📊 根据用户偏好排序...")
    ranked_posts = score_posts_by_preferences(unique_posts, profile)
    final_posts = ranked_posts[:args.top]
    print(f"   ✅ 精选 Top {len(final_posts)} 个帖子")
    
    # ========== 步骤 7：输出结果 ==========
    result = {
        "username": args.username,
        "input_keywords": input_keywords,
        "target_domain_ids": target_domain_ids,
        "recommendations": final_posts,
        "generated_at": datetime.now().isoformat()
    }
    
    if args.output:
        save_cache(args.output, result)
        print(f"\n💾 推荐结果已保存到: {args.output}")
    
    # 显示推荐列表（供 agent 使用）
    print("\n" + "="*70)
    print("📋 推荐列表（供 agent 编写推荐理由）")
    print("="*70)
    
    config = load_config(args.config)
    for i, post in enumerate(final_posts, 1):
        post_id = post.get("id")
        title = post.get("title")
        slug = post.get("slug", "topic")
        url = f"{config['discourse_url']}/t/{slug}/{post_id}"
        domain_id = post.get("_domain_id", "?")
        pool = post.get("_pool", "?")
        
        print(f"\n{i}. {title}")
        print(f"   🔗 {url}")
        print(f"   📌 来源: 领域 {domain_id}, {pool} 池")
        print(f"   数据: id={post_id}, likes={post.get('like_count', 0)}, replies={post.get('posts_count', 0)}")
    
    print("\n" + "="*70)
    print("✅ 数据准备完成！请 agent 编写推荐理由并发送给用户")
    print("="*70)
    
    # 保存临时数据供后续更新画像使用
    temp_file = os.path.join(skill_dir, f"temp_{args.username}_recommendation.json")
    save_cache(temp_file, {
        "recommended_posts": final_posts,
        "input_keywords": input_keywords,
        "target_domain_ids": target_domain_ids
    })
    print(f"\n📝 临时数据已保存，用于后续更新用户画像")


if __name__ == "__main__":
    main()
