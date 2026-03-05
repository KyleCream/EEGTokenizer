#!/usr/bin/env python3
import requests
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

class DiscourseDataCollector:
    def __init__(self, base_url: str, api_key: str, api_username: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_username = api_username
        self.headers = {
            "Api-Key": api_key,
            "Api-Username": api_username,
            "Accept": "application/json"
        }
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_user_activity(self, username: str) -> List[Dict]:
        print(f"获取用户 {username} 的活动记录...")
        try:
            endpoint = f"/u/{username}/activity.json"
            data = self._get(endpoint)
            if isinstance(data, list):
                return data
            else:
                return data.get('user_actions', [])
        except Exception as e:
            print(f"  ⚠️ 获取用户活动失败，使用空列表: {e}")
            return []
    
    def get_latest_topics(self, page: int = 0) -> List[Dict]:
        print(f"获取最新话题 (第 {page+1} 页)...")
        endpoint = "/latest.json"
        data = self._get(endpoint, params={'page': page})
        return data.get('topic_list', {}).get('topics', [])
    
    def get_top_topics(self, period: str = "weekly") -> List[Dict]:
        print(f"获取 {period} 热门话题...")
        endpoint = f"/top/{period}.json"
        data = self._get(endpoint)
        return data.get('topic_list', {}).get('topics', [])
    
    def get_categories(self) -> List[Dict]:
        print("获取分类列表...")
        try:
            endpoint = "/categories.json"
            data = self._get(endpoint)
            return data.get('category_list', {}).get('categories', [])
        except Exception as e:
            print(f"  ⚠️ 获取分类失败（可能权限问题），使用空列表: {e}")
            return []
    
    def collect_all_data(self, username: str, max_topics: int = 100) -> Dict:
        print("="*60)
        print("Discourse 数据收集器")
        print("="*60)
        
        categories = self.get_categories()
        user_activity = self.get_user_activity(username)
        
        latest_topics = []
        users_map = {}
        
        for page in range(2):
            data = self._get("/latest.json", params={'page': page})
            if data:
                latest_topics.extend(data.get('topic_list', {}).get('topics', []))
                for user in data.get('users', []):
                    users_map[user.get('id')] = user
            time.sleep(0.5)
        
        top_data = self._get("/top/weekly.json")
        if top_data:
            top_topics = top_data.get('topic_list', {}).get('topics', [])
            for user in top_data.get('users', []):
                users_map[user.get('id')] = user
        else:
            top_topics = []
        
        all_topics = []
        seen_ids = set()
        for topic in latest_topics + top_topics:
            tid = topic.get('id')
            if tid not in seen_ids:
                seen_ids.add(tid)
                all_topics.append(topic)
        
        all_topics = all_topics[:max_topics]
        
        print(f"\n✅ 数据收集完成!")
        print(f"   用户活动: {len(user_activity)} 条")
        print(f"   帖子总数: {len(all_topics)} 个")
        print(f"   分类数: {len(categories)} 个")
        print(f"   用户数: {len(users_map)} 个")
        
        return {
            "collect_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user": {
                "activity": user_activity,
                "topics": []
            },
            "topics": all_topics,
            "categories": categories,
            "users": users_map
        }

def main():
    parser = argparse.ArgumentParser(description="收集 Discourse 数据（混合版）")
    parser.add_argument("--url", default="https://zyt.discourse.diy", help="论坛地址")
    parser.add_argument("--api-key", default="0955e767959917cf2dad58a53b676cac93ccba34975330f1b42acd38ae952bbb", help="API Key")
    parser.add_argument("--api-username", default="Kayle", help="API 用户名")
    parser.add_argument("--username", required=True, help="要分析的用户名")
    parser.add_argument("--output", required=True, help="输出文件路径 (JSON)")
    parser.add_argument("--max-topics", type=int, default=100, help="最多收集多少帖子")
    
    args = parser.parse_args()
    
    collector = DiscourseDataCollector(args.url, args.api_key, args.api_username)
    data = collector.collect_all_data(args.username, args.max_topics)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 数据已保存到: {output_path}")

if __name__ == "__main__":
    main()
