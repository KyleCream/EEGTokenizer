#!/usr/bin/env python3
"""
排序精排模块 - 混合版
包含相关性、新鲜度、热度、多样性等多目标排序，支持 Discourse 站内信推送
"""
import sys
import os
import time
import requests
import json
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_profile import InterestProfile

DISCOURSE_URL = "https://zyt.discourse.diy"
API_KEY = "0955e767959917cf2dad58a53b676cac93ccba34975330f1b42acd38ae952bbb"
API_USERNAME = "Kayle"


class Reranker:
    """重排器"""
    
    def __init__(self, profile: InterestProfile, users_map: Dict[int, Dict] = None):
        self.profile = profile
        self.users_map = users_map or {}
        self.now = time.time()
    
    def _get_author_name(self, topic: Dict) -> str:
        """从 topic 中获取作者名"""
        # 优先用 last_poster_username
        username = topic.get('last_poster_username')
        if username:
            return username
        
        # 尝试从 posters 数组获取
        posters = topic.get('posters', [])
        if posters:
            first_poster = posters[0]
            user_id = first_poster.get('user_id')
            if user_id and user_id in self.users_map:
                return self.users_map[user_id].get('username', '未知')
        
        return "未知"
    
    def _calculate_freshness_score(self, topic: Dict) -> float:
        created_at = topic.get('created_at')
        if not created_at:
            return 0.5
        
        try:
            if created_at.endswith('Z'):
                created_at = created_at.replace('Z', '+00:00')
            dt = datetime.fromisoformat(created_at)
            topic_timestamp = dt.timestamp()
            hours_ago = (self.now - topic_timestamp) / 3600
            
            if hours_ago < 24:
                return 1.0
            elif hours_ago < 72:
                return 1.0 - (hours_ago - 24) / (72 - 24) * 0.3
            elif hours_ago < 168:
                return 0.7 - (hours_ago - 72) / (168 - 72) * 0.3
            elif hours_ago < 720:
                return 0.4 - (hours_ago - 168) / (720 - 168) * 0.3
            else:
                return 0.05
        except:
            return 0.5
    
    def _calculate_hot_score(self, topic: Dict) -> float:
        posts_count = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        views = topic.get('views', 0)
        
        posts_score = min(posts_count / 50.0, 1.0)
        likes_score = min(likes / 100.0, 1.0)
        views_score = min(views / 10000.0, 1.0)
        
        return (posts_score * 0.4) + (likes_score * 0.35) + (views_score * 0.25)
    
    def _calculate_diversity_penalty(self, topic: Dict, selected_topics: List[Dict]) -> float:
        category_id = topic.get('category_id')
        author = self._get_author_name(topic)
        
        category_count = 0
        author_count = 0
        
        for selected in selected_topics:
            if selected.get('category_id') == category_id:
                category_count += 1
            if self._get_author_name(selected) == author:
                author_count += 1
        
        penalty = 0.0
        if category_count >= 2:
            penalty += (category_count - 1) * 0.25
        if author_count >= 1:
            penalty += author_count * 0.2
        
        return min(penalty, 0.8)
    
    def rerank(self, recalled_items: List[Dict], top_k: int = 10) -> List[Dict]:
        print(f"开始重排候选话题 (从 {len(recalled_items)} 个中选 Top {top_k})...")
        
        print("\n[1/2] 多目标打分...")
        for item in recalled_items:
            topic = item['topic']
            base_score = item['score']
            freshness = self._calculate_freshness_score(topic)
            hot_score = self._calculate_hot_score(topic)
            item['freshness_score'] = freshness
            item['hot_score'] = hot_score
            item['first_stage_score'] = base_score * (0.5 + 0.3 * freshness + 0.15 * hot_score + 0.05)
        
        recalled_items.sort(key=lambda x: x['first_stage_score'], reverse=True)
        
        print("\n[2/2] 贪心选择，保证多样性...")
        selected = []
        remaining = recalled_items.copy()
        
        while len(selected) < top_k and remaining:
            best_item = None
            best_final_score = -1.0
            best_idx = -1
            
            for idx, item in enumerate(remaining):
                topic = item['topic']
                first_stage_score = item['first_stage_score']
                diversity_penalty = self._calculate_diversity_penalty(topic, [s['topic'] for s in selected])
                final_score = first_stage_score * (1 - diversity_penalty)
                
                if final_score > best_final_score:
                    best_final_score = final_score
                    best_item = item
                    best_idx = idx
            
            if best_item:
                best_item['final_score'] = best_final_score
                selected.append(best_item)
                remaining.pop(best_idx)
            else:
                break
        
        print("\n生成推荐理由...")
        final_results = []
        for item in selected:
            topic = item['topic']
            reason_parts = item.get('reasons', [])
            if item.get('freshness_score', 0) > 0.7:
                reason_parts.append("很新鲜")
            if item.get('hot_score', 0) > 0.5:
                reason_parts.append("热度不错")
            if item.get('diversity_penalty', 0) > 0:
                reason_parts.append("强相关")
            
            item['reason_text'] = "、".join(reason_parts[:5]) if reason_parts else "综合推荐"
            item['author_name'] = self._get_author_name(topic)
            final_results.append(item)
        
        print(f"重排完成: 选出 {len(final_results)} 个推荐帖子")
        return final_results


def print_recommendations(recommendations: List[Dict], base_url: str):
    """打印推荐结果"""
    print("\n" + "="*80)
    print("🎯 为您推荐的帖子".center(80))
    print("="*80)
    
    for i, item in enumerate(recommendations, 1):
        topic = item['topic']
        title = topic.get('title', '无标题')
        topic_id = topic.get('id')
        url = f"{base_url}/t/{topic_id}"
        author = item.get('author_name', '未知')
        posts_count = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        views = topic.get('views', 0)
        
        print(f"\n{i}. {title}")
        print(f"   👤 作者: {author}")
        print(f"   💬 回复: {posts_count} | ❤️ 点赞: {likes} | 👁️ 浏览: {views}")
        print(f"   🔗 链接: {url}")
        print(f"   💡 理由: {item.get('reason_text', '综合推荐')}")
        print(f"   📊 得分: {item.get('final_score', 0):.2f}")
    
    print("\n" + "="*80)


def send_discourse_pm(recommendations: List[Dict], base_url: str, target_username: str = "Kayle"):
    """通过 Discourse 站内信发送推荐"""
    print("\n[推送] 发送 Discourse 站内信...")
    
    # 构建站内信内容
    pm_content = "## 🤖 小k为你推荐的帖子\n\n"
    
    for i, item in enumerate(recommendations, 1):
        topic = item['topic']
        title = topic.get('title', '无标题')
        topic_id = topic.get('id')
        url = f"{base_url}/t/{topic_id}"
        author = item.get('author_name', '未知')
        posts_count = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        reason = item.get('reason_text', '综合推荐')
        
        pm_content += f"{i}. **[{title}]({url})**\n"
        pm_content += f"   - 作者: {author}\n"
        pm_content += f"   - 回复: {posts_count} | 点赞: {likes}\n"
        pm_content += f"   - 理由: {reason}\n\n"
    
    pm_content += "\n---\n*由小k自动推荐*"
    
    # 发送站内信
    headers = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    pm_data = {
        "title": "🤖 小k为你推荐的帖子",
        "raw": pm_content,
        "target_recipients": target_username,
        "archetype": "private_message"
    }
    
    try:
        response = requests.post(f"{base_url}/posts.json", headers=headers, json=pm_data)
        if response.status_code == 200:
            result = response.json()
            topic_id = result.get('topic_id')
            print(f"✅ 站内信发送成功！")
            print(f"   链接: {base_url}/t/{topic_id}")
            return True
        else:
            print(f"❌ 站内信发送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 站内信发送异常: {e}")
        return False


if __name__ == "__main__":
    print("排序精排模块 - 混合版")
    print("包含多目标排序、作者名解析、Discourse 站内信推送")
