#!/usr/bin/env python3
"""
工具函数模块（高级版）
- 配置加载
- 缓存读写（全局+领域）
- Discourse API 调用
- 领域相关工具
"""
import json
import os
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cache(cache_path: str, data: Any):
    """保存缓存到 JSON 文件"""
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(cache_path: str) -> Optional[Any]:
    """从 JSON 文件加载缓存"""
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_domain_dir(base_dir: str, domain_id: str) -> str:
    """获取领域目录路径"""
    return os.path.join(base_dir, "domains", f"domain_{domain_id}")


def get_profile_path(base_dir: str, username: str) -> str:
    """获取用户画像文件路径"""
    return os.path.join(base_dir, "profiles", f"{username}.json")


class DiscourseAPI:
    """Discourse API 客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config['discourse_url'].rstrip('/')
        self.api_key = config['api_key']
        self.api_username = config['api_username']
        self.headers = {
            "Api-Key": self.api_key,
            "Api-Username": self.api_username,
            "Accept": "application/json"
        }
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_latest_topics(self, page: int = 0, per_page: int = 30) -> List[Dict]:
        """获取最新话题"""
        data = self._get("/latest.json", params={'page': page, 'per_page': per_page})
        return data.get('topic_list', {}).get('topics', [])
    
    def get_top_topics(self, period: str = "weekly") -> List[Dict]:
        """获取热门话题"""
        data = self._get(f"/top/{period}.json")
        return data.get('topic_list', {}).get('topics', [])
    
    def get_categories(self) -> List[Dict]:
        """获取分类列表"""
        data = self._get("/categories.json")
        return data.get('category_list', {}).get('categories', [])
    
    def get_topic(self, topic_id: int) -> Dict:
        """获取单个话题详情"""
        return self._get(f"/t/{topic_id}.json")


def merge_and_deduplicate(topics_list: List[List[Dict]]) -> List[Dict]:
    """合并多个话题列表并去重"""
    seen_ids = set()
    unique_topics = []
    for topics in topics_list:
        for topic in topics:
            tid = topic.get('id')
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                unique_topics.append(topic)
    return unique_topics


def sort_topics_by(topics: List[Dict], key: str, reverse: bool = True) -> List[Dict]:
    """按指定字段排序话题"""
    return sorted(topics, key=lambda t: t.get(key, 0), reverse=reverse)


def extract_topic_features(topic: Dict) -> List[str]:
    """从话题中提取特征（tags, 分类, 标题关键词）"""
    features = []
    
    tags = topic.get('tags', [])
    features.extend(tags)
    
    category_id = topic.get('category_id')
    if category_id:
        features.append(f"cat:{category_id}")
    
    title = topic.get('title', '')
    features.extend(title.split()[:5])
    
    return features


if __name__ == "__main__":
    print("工具函数模块（高级版）")
