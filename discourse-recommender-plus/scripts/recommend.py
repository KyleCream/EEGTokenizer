#!/usr/bin/env python3
"""
主推荐脚本 - 混合版（Tags为主 + 小k分析）
整合所有模块：数据收集 → 画像构建 → [可选: 小k分析] → 召回 → 排序 → 呈现
"""
import argparse
import json
import os
import sys
import time
from typing import Dict, List, Any
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from collect_data import DiscourseDataCollector
from build_profile import ProfileBuilder, InterestProfile
from recall import PostRecaller
from rank import Reranker, print_recommendations, send_discourse_pm

DISCOURSE_URL = "https://zyt.discourse.diy"
API_KEY = "0955e767959917cf2dad58a53b676cac93ccba34975330f1b42acd38ae952bbb"
API_USERNAME = "Kayle"

SKILL_DIR = os.path.dirname(SCRIPT_DIR)
CACHE_DIR = os.path.join(SKILL_DIR, "cache")


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def load_cache(cache_key: str, max_age_seconds: int = 3600) -> Any:
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < max_age_seconds:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None


def save_cache(cache_key: str, data: Any):
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    def convert_sets(obj):
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: convert_sets(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_sets(item) for item in obj]
        elif hasattr(obj, 'to_dict'):
            return convert_sets(obj.to_dict())
        else:
            return obj
    
    data = convert_sets(data)
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Discourse 论坛个性化推荐系统（混合版）")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--top", type=int, default=10, help="推荐数量")
    parser.add_argument("--update-only", action="store_true", help="只更新数据和画像，不推荐")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存")
    parser.add_argument("--cache-age", type=int, default=3600, help="缓存有效期（秒）")
    parser.add_argument("--human-analysis", action="store_true", help="导出数据供人工分析，不直接推荐")
    parser.add_argument("--profile", help="使用包含人工分析的画像文件")
    parser.add_argument("--send-pm", action="store_true", help="通过 Discourse 站内信发送推荐")
    
    args = parser.parse_args()
    
    print("="*80)
    print("🚀 Discourse 个性化推荐系统（混合版 - Tags为主）".center(80))
    print("="*80)
    print(f"目标用户: {args.username}")
    print(f"论坛地址: {DISCOURSE_URL}")
    print()
    
    # ========== 1. 数据收集 ==========
    print("[步骤 1/5] 数据收集")
    print("-" * 60)
    
    cache_key_data = f"data_{args.username}"
    if not args.no_cache:
        cached_data = load_cache(cache_key_data, args.cache_age)
        if cached_data:
            print("✅ 使用缓存数据")
            data = cached_data
        else:
            collector = DiscourseDataCollector(DISCOURSE_URL, API_KEY, API_USERNAME)
            data = collector.collect_all_data(args.username, max_topics=200)
            save_cache(cache_key_data, data)
    else:
        collector = DiscourseDataCollector(DISCOURSE_URL, API_KEY, API_USERNAME)
        data = collector.collect_all_data(args.username, max_topics=200)
        save_cache(cache_key_data, data)
    
    if args.update_only:
        print("\n✅ 数据已更新，退出")
        return
    
    # ========== 2. 兴趣画像构建 ==========
    print("\n[步骤 2/5] 兴趣画像构建")
    print("-" * 60)
    
    if args.profile:
        print(f"使用外部画像文件: {args.profile}")
        with open(args.profile, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
        profile = InterestProfile.from_dict(profile_data)
    else:
        cache_key_profile = f"profile_{args.username}"
        if not args.no_cache:
            cached_profile = load_cache(cache_key_profile, args.cache_age)
            if cached_profile:
                print("✅ 使用缓存画像")
                profile = InterestProfile.from_dict(cached_profile)
            else:
                profile_builder = ProfileBuilder()
                profile = profile_builder.build(data['user'], data['topics'])
                save_cache(cache_key_profile, profile.to_dict())
        else:
            profile_builder = ProfileBuilder()
            profile = profile_builder.build(data['user'], data['topics'])
            save_cache(cache_key_profile, profile.to_dict())
    
    # ========== 2a. 导出供小k分析 ==========
    if args.human_analysis:
        print("\n[模式] 导出供小k分析")
        print("-" * 60)
        
        profile_builder = ProfileBuilder()
        analysis_file = os.path.join(SKILL_DIR, f"human_analysis_{args.username}.json")
        profile_builder.export_for_human_analysis(profile, data['topics'], analysis_file)
        
        print(f"""
下一步请:
1. 打开并分析: {analysis_file}
2. 创建画像文件: profile_with_human_{args.username}.json
3. 运行: python3 scripts/recommend.py --username {args.username} --profile profile_with_human_{args.username}.json
        """)
        
        return
    
    # ========== 3. 召回 ==========
    print("\n[步骤 3/5] 帖子召回")
    print("-" * 60)
    
    all_topics = data['topics']
    seen_ids = set()
    unique_topics = []
    for topic in all_topics:
        tid = topic.get('id')
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique_topics.append(topic)
    
    recaller = PostRecaller(profile, data['categories'])
    recalled = recaller.recall(unique_topics, top_k=100)
    
    if not recalled:
        print("❌ 没有召回任何话题，退出")
        return
    
    # ========== 4. 排序 ==========
    print("\n[步骤 4/5] 排序精排")
    print("-" * 60)
    
    users_map = data.get('users', {})
    reranker = Reranker(profile, users_map)
    recommendations = reranker.rerank(recalled, top_k=args.top)
    
    if not recommendations:
        print("❌ 没有推荐结果，退出")
        return
    
    # ========== 5. 呈现 ==========
    print("\n[步骤 5/5] 推荐结果")
    print_recommendations(recommendations, DISCOURSE_URL)
    
    # ========== 6. Discourse 站内信推送 ==========
    if args.send_pm:
        send_discourse_pm(recommendations, DISCOURSE_URL, args.username)
    
    save_cache(f"recommendations_{args.username}", {
        'recommendations': [
            {
                'topic_id': item['topic'].get('id'),
                'title': item['topic'].get('title'),
                'url': f"{DISCOURSE_URL}/t/{item['topic'].get('id')}",
                'score': float(item.get('final_score', 0)),
                'reason': item.get('reason_text', '')
            }
            for item in recommendations
        ],
        'generated_at': time.time()
    })
    
    print("\n" + "="*80)
    print("✅ 推荐完成！".center(80))
    print("="*80)


if __name__ == "__main__":
    main()
