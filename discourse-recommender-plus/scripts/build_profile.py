#!/usr/bin/env python3
"""
兴趣画像构建模块 - 混合版（Tags为主 + 小k分析 + 关键词保底）
"""
import sys
import os
import json
from typing import Dict, List, Any, Set, Tuple
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import Tokenizer, TFIDF, BM25, StopWords


class InterestProfile:
    """兴趣画像（混合版）"""
    
    def __init__(self):
        # Tags 偏好（主，权重60%）
        self.tag_preference: Dict[str, float] = {}
        
        # 分类偏好
        self.category_preference: Dict[int, float] = {}
        
        # 作者偏好
        self.author_preference: Dict[str, float] = {}
        
        # 小k补充关键词（辅，权重30%）
        self.human_keywords: List[str] = []
        
        # 关键词提取（保底，权重10%）
        self.keywords: Dict[str, float] = {}
        
        # 已看过的话题
        self.seen_topic_ids: Set[int] = set()
        
        # 时间偏好
        self.time_preference = {
            'hour': Counter(),
            'day': Counter(),
        }
        
        # 互动模式
        self.interaction_patterns = {
            'view': 0,
            'like': 0,
            'reply': 0,
            'create': 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'tag_preference': self.tag_preference,
            'category_preference': self.category_preference,
            'author_preference': self.author_preference,
            'human_keywords': self.human_keywords,
            'keywords': self.keywords,
            'seen_topic_ids': list(self.seen_topic_ids),
            'time_preference': {
                'hour': dict(self.time_preference['hour']),
                'day': dict(self.time_preference['day']),
            },
            'interaction_patterns': self.interaction_patterns,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InterestProfile':
        """从字典加载"""
        profile = cls()
        profile.tag_preference = data.get('tag_preference', {})
        profile.category_preference = data.get('category_preference', {})
        profile.author_preference = data.get('author_preference', {})
        profile.human_keywords = data.get('human_keywords', [])
        profile.keywords = data.get('keywords', {})
        profile.seen_topic_ids = set(data.get('seen_topic_ids', []))
        
        tp = data.get('time_preference', {})
        profile.time_preference['hour'] = Counter(tp.get('hour', {}))
        profile.time_preference['day'] = Counter(tp.get('day', {}))
        
        profile.interaction_patterns = data.get('interaction_patterns', profile.interaction_patterns)
        
        return profile


class ProfileBuilder:
    """兴趣画像构建器（混合版）"""
    
    def __init__(self):
        self.tokenizer = Tokenizer()
        self.tfidf = TFIDF(self.tokenizer)
    
    def _parse_time(self, time_str: str) -> Tuple[int, int]:
        """解析时间字符串"""
        try:
            if time_str.endswith('Z'):
                time_str = time_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(time_str)
            return dt.hour, dt.weekday()
        except:
            return -1, -1
    
    def _analyze_user_activity(self, activity: List[Dict], profile: InterestProfile):
        """分析用户活动记录"""
        print("分析用户活动记录...")
        
        for action in activity:
            action_type = action.get('action_type', '')
            if action_type == 1:
                profile.interaction_patterns['like'] += 1
            elif action_type == 2:
                profile.interaction_patterns['reply'] += 1
            elif action_type in (4, 5):
                profile.interaction_patterns['create'] += 1
            else:
                profile.interaction_patterns['view'] += 1
            
            topic_id = action.get('topic_id')
            if topic_id:
                profile.seen_topic_ids.add(topic_id)
            
            created_at = action.get('created_at')
            if created_at:
                hour, day = self._parse_time(created_at)
                if hour >= 0:
                    profile.time_preference['hour'][hour] += 1
                if day >= 0:
                    profile.time_preference['day'][day] += 1
    
    def _extract_from_interacted_topics(self, topics: List[Dict], profile: InterestProfile):
        """从用户互动过的帖子中提取信息"""
        print("从互动过的帖子中提取 Tags、分类、作者...")
        
        tag_counter = Counter()
        category_counter = Counter()
        author_counter = Counter()
        
        for topic in topics:
            topic_id = topic.get('id')
            if topic_id not in profile.seen_topic_ids:
                continue
            
            # Tags 统计
            tags = topic.get('tags', [])
            for tag in tags:
                tag_counter[tag] += 1
            
            # 分类统计
            category_id = topic.get('category_id')
            if category_id:
                category_counter[category_id] += 1
            
            # 作者统计
            author = topic.get('last_poster', {}).get('username')
            if author:
                author_counter[author] += 1
        
        # 归一化 Tags
        if tag_counter:
            max_tag = max(tag_counter.values())
            profile.tag_preference = {tag: cnt / max_tag for tag, cnt in tag_counter.most_common(20)}
        
        # 归一化分类
        if category_counter:
            max_cat = max(category_counter.values())
            profile.category_preference = {cid: cnt / max_cat for cid, cnt in category_counter.items()}
        
        # 归一化作者
        if author_counter:
            max_author = max(author_counter.values())
            profile.author_preference = {author: cnt / max_author for author, cnt in author_counter.most_common(10)}
    
    def _extract_keywords_fallback(self, topics: List[Dict], profile: InterestProfile):
        """关键词提取（保底，仅当Tags不足时使用）"""
        if profile.tag_preference:
            print("Tags 数据充足，跳过关键词保底提取")
            return
        
        print("Tags 数据不足，启用关键词保底提取...")
        
        user_texts = []
        for topic in topics:
            topic_id = topic.get('id')
            if topic_id in profile.seen_topic_ids:
                title = topic.get('title', '')
                user_texts.append(title)
        
        if user_texts:
            all_texts = [t.get('title', '') for t in topics[:100]]
            self.tfidf.fit(all_texts)
            combined_text = ' '.join(user_texts)
            keywords = self.tfidf.get_top_keywords(combined_text, top_n=30)
            profile.keywords = dict(keywords)
    
    def build(self, user_data: Dict[str, Any], forum_topics: List[Dict]) -> InterestProfile:
        """构建用户兴趣画像（混合版）"""
        print("="*60)
        print("开始构建用户兴趣画像（混合版）")
        print("="*60)
        
        profile = InterestProfile()
        
        activity = user_data.get('activity', [])
        if activity:
            self._analyze_user_activity(activity, profile)
        
        self._extract_from_interacted_topics(forum_topics, profile)
        
        self._extract_keywords_fallback(forum_topics, profile)
        
        print("\n" + "="*60)
        print("兴趣画像构建完成！")
        print("="*60)
        print(f"  - Tags 偏好: {len(profile.tag_preference)} 个")
        print(f"  - 分类偏好: {len(profile.category_preference)} 个")
        print(f"  - 作者偏好: {len(profile.author_preference)} 个")
        print(f"  - 已看话题: {len(profile.seen_topic_ids)} 个")
        if profile.keywords:
            print(f"  - 保底关键词: {len(profile.keywords)} 个")
        
        return profile
    
    def export_for_human_analysis(self, profile: InterestProfile, topics: List[Dict], output_path: str):
        """导出数据供人工分析"""
        print(f"\n导出数据供人工分析到: {output_path}")
        
        # 找出用户互动过的帖子详情
        interacted_topics = []
        for topic in topics:
            if topic.get('id') in profile.seen_topic_ids:
                interacted_topics.append({
                    'id': topic.get('id'),
                    'title': topic.get('title'),
                    'tags': topic.get('tags', []),
                    'category_id': topic.get('category_id'),
                    'category_name': topic.get('category_name', ''),
                    'author': topic.get('last_poster', {}).get('username', ''),
                    'like_count': topic.get('like_count', 0),
                    'posts_count': topic.get('posts_count', 0),
                })
        
        export_data = {
            'profile_summary': profile.to_dict(),
            'interacted_topics': interacted_topics[:50],
            'all_tags': list({tag for t in topics for tag in t.get('tags', [])}),
            'instructions': '''请分析后补充：
1. human_keywords: 你认为用户感兴趣的补充关键词（列表）
2. adjustments: 对 tag/category/author 权重的调整建议（可选）
3. notes: 其他观察到的用户偏好''',
        }
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已导出，等待小k分析...")


if __name__ == "__main__":
    print("兴趣画像构建模块 - 混合版（Tags为主）")
