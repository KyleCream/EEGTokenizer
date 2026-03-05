#!/usr/bin/env python3
"""
帖子召回模块 - 混合版（Tags为主）
召回策略优先级：Tags匹配 > 分类匹配 > 作者匹配 > 小k关键词 > 热门保底
"""
import sys
import os
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_profile import InterestProfile


class RecallStrategy:
    """召回策略基类"""
    
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        raise NotImplementedError


class TagMatchStrategy(RecallStrategy):
    """Tags 匹配召回（主策略，权重最高）"""
    
    def __init__(self, weight: float = 6.0):
        super().__init__("Tags 匹配", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        if not profile.tag_preference:
            return results
        
        for idx, topic in enumerate(topics):
            topic_tags = set(topic.get('tags', []))
            matched_tags = []
            score = 0.0
            
            for tag, tag_weight in profile.tag_preference.items():
                if tag in topic_tags:
                    matched_tags.append(tag)
                    score += tag_weight
            
            if score > 0:
                reason = f"Tags 匹配: {', '.join(matched_tags[:3])}"
                results.append((idx, score * self.weight, reason))
        
        return results


class HumanKeywordStrategy(RecallStrategy):
    """小k补充关键词匹配（辅策略）"""
    
    def __init__(self, weight: float = 3.0):
        super().__init__("小k关键词", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        if not profile.human_keywords:
            return results
        
        keywords = {kw.lower() for kw in profile.human_keywords}
        
        for idx, topic in enumerate(topics):
            title = topic.get('title', '').lower()
            matched = []
            
            for kw in keywords:
                if kw in title:
                    matched.append(kw)
            
            if matched:
                reason = f"小k关键词: {', '.join(matched[:3])}"
                results.append((idx, len(matched) * self.weight, reason))
        
        return results


class CategoryMatchStrategy(RecallStrategy):
    """分类匹配召回"""
    
    def __init__(self, weight: float = 2.5):
        super().__init__("分类匹配", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        if not profile.category_preference:
            return results
        
        for idx, topic in enumerate(topics):
            category_id = topic.get('category_id')
            
            if category_id in profile.category_preference:
                score = profile.category_preference[category_id]
                results.append((idx, score * self.weight, "分类偏好"))
        
        return results


class AuthorMatchStrategy(RecallStrategy):
    """作者匹配召回"""
    
    def __init__(self, weight: float = 1.5):
        super().__init__("作者匹配", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        if not profile.author_preference:
            return results
        
        for idx, topic in enumerate(topics):
            author = topic.get('last_poster', {}).get('username')
            
            if author in profile.author_preference:
                score = profile.author_preference[author]
                results.append((idx, score * self.weight, "作者偏好"))
        
        return results


class KeywordFallbackStrategy(RecallStrategy):
    """关键词提取（保底策略）"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__("关键词保底", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        if not profile.keywords or profile.tag_preference:
            return results
        
        keywords = set(profile.keywords.keys())
        
        for idx, topic in enumerate(topics):
            title = topic.get('title', '').lower()
            matched = []
            score = 0.0
            
            for kw in keywords:
                if kw.lower() in title:
                    matched.append(kw)
                    score += profile.keywords.get(kw, 1.0)
            
            if matched:
                reason = f"关键词保底: {', '.join(matched[:3])}"
                results.append((idx, score * self.weight, reason))
        
        return results


class HotTopicStrategy(RecallStrategy):
    """热门话题召回（保底）"""
    
    def __init__(self, weight: float = 0.8):
        super().__init__("热门话题", weight)
    
    def recall(self, profile: InterestProfile, topics: List[Dict]) -> List[Tuple[int, float, str]]:
        results = []
        
        for idx, topic in enumerate(topics):
            posts_count = topic.get('posts_count', 0)
            likes = topic.get('like_count', 0)
            hot_score = (posts_count * 0.5) + (likes * 0.3)
            
            if hot_score > 0:
                results.append((idx, hot_score * self.weight, "热度不错"))
        
        return results


class PostRecaller:
    """帖子召回器（混合版）"""
    
    def __init__(self, profile: InterestProfile, categories: List[Dict]):
        self.profile = profile
        self.categories = categories
        self.category_id_to_name = {cat['id']: cat['name'] for cat in categories}
        
        self.strategies = [
            TagMatchStrategy(weight=6.0),
            CategoryMatchStrategy(weight=2.5),
            AuthorMatchStrategy(weight=1.5),
            HumanKeywordStrategy(weight=3.0),
            KeywordFallbackStrategy(weight=1.0),
            HotTopicStrategy(weight=0.8),
        ]
    
    def recall(self, topics: List[Dict], top_k: int = 100) -> List[Dict]:
        print(f"开始召回候选话题 (从 {len(topics)} 个话题中)...")
        
        topic_scores = defaultdict(float)
        topic_strategies = defaultdict(dict)
        topic_reasons = defaultdict(list)
        
        for strategy in self.strategies:
            results = strategy.recall(self.profile, topics)
            
            for idx, score, reason in results:
                topic_scores[idx] += score
                topic_strategies[idx][strategy.name] = (score, reason)
                topic_reasons[idx].append(reason)
        
        recalled = []
        for idx, total_score in topic_scores.items():
            topic = topics[idx]
            topic_id = topic.get('id')
            if topic_id in self.profile.seen_topic_ids:
                total_score *= 0.3
            
            recalled.append({
                'topic': topic,
                'topic_idx': idx,
                'score': total_score,
                'strategies': topic_strategies[idx],
                'reasons': topic_reasons[idx]
            })
        
        recalled.sort(key=lambda x: x['score'], reverse=True)
        recalled = recalled[:top_k]
        
        print(f"召回完成: {len(recalled)} 个候选话题")
        
        print("\n召回策略统计:")
        strategy_counts = defaultdict(int)
        for item in recalled:
            for strategy_name in item['strategies'].keys():
                strategy_counts[strategy_name] += 1
        
        for strategy in self.strategies:
            count = strategy_counts.get(strategy.name, 0)
            print(f"  {strategy.name}: {count} 个话题")
        
        return recalled


if __name__ == "__main__":
    print("帖子召回模块 - 混合版（Tags为主）")
    print("召回优先级: Tags匹配 > 分类/作者 > 小k关键词 > 关键词保底 > 热门保底")
