#!/usr/bin/env python3
import json
import os
import requests
from pathlib import Path


def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cache(cache_path, data):
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


class DiscourseAPI:
    def __init__(self, config):
        self.base_url = config['discourse_url'].rstrip('/')
        self.api_key = config['api_key']
        self.api_username = config['api_username']
        self.headers = {
            "Api-Key": self.api_key,
            "Api-Username": self.api_username,
            "Accept": "application/json"
        }
    
    def _get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_latest_topics(self, page=0, per_page=30):
        data = self._get("/latest.json", params={'page': page, 'per_page': per_page})
        return data.get('topic_list', {}).get('topics', [])
    
    def get_top_topics(self, period="weekly"):
        data = self._get(f"/top/{period}.json")
        return data.get('topic_list', {}).get('topics', [])
    
    def get_categories(self):
        data = self._get("/categories.json")
        return data.get('category_list', {}).get('categories', [])


def merge_and_deduplicate(topics_list):
    seen_ids = set()
    unique_topics = []
    for topics in topics_list:
        for topic in topics:
            tid = topic.get('id')
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                unique_topics.append(topic)
    return unique_topics


def sort_topics_by(topics, key, reverse=True):
    return sorted(topics, key=lambda t: t.get(key, 0), reverse=reverse)


if __name__ == "__main__":
    print("工具函数模块")
