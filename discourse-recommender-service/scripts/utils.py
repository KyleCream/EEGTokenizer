#!/usr/bin/env python3
"""
工具函数模块 - 配置、缓存、API、TF-IDF、BM25 等
"""
import re
import math
import json
import os
import requests
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple, Set


def load_config(config_path):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cache(cache_path, data):
    """保存缓存到 JSON 文件"""
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(cache_path):
    """从 JSON 文件加载缓存"""
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


class DiscourseAPI:
    """Discourse API 客户端"""
    
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


def sort_topics_by(topics, key, reverse=True):
    return sorted(topics, key=lambda t: t.get(key, 0), reverse=reverse)


def send_discourse_pm(topics, base_url, api_key, api_username, target_username, top_k=5):
    """发送 Discourse 站内信"""
    import requests
    
    pm_content = "## 🤖 为你推荐的帖子\n\n"
    
    for i, topic in enumerate(topics[:top_k], 1):
        title = topic.get('title', '无标题')
        topic_id = topic.get('id')
        url = f"{base_url}/t/{topic_id}"
        posts = topic.get('posts_count', 0)
        likes = topic.get('like_count', 0)
        
        reasons = []
        if likes > 0:
            reasons.append(f"点赞 {likes}")
        if posts > 0:
            reasons.append(f"回复 {posts}")
        if likes + posts > 5:
            reasons.append("热度不错")
        if not reasons:
            reasons.append("综合推荐")
        
        pm_content += f"{i}. **[{title}]({url})**\n"
        pm_content += f"   - 回复: {posts} | 点赞: {likes}\n"
        pm_content += f"   - 理由: {', '.join(reasons)}\n\n"
    
    pm_content += "\n---\n*由 OpenClaw 自动推荐*"
    
    headers = {
        "Api-Key": api_key,
        "Api-Username": api_username,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    pm_data = {
        "title": "🤖 为你推荐的帖子",
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

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("⚠️ jieba 未安装，将使用简单分词")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn 未安装，将使用简单 TF-IDF 实现")


class StopWords:
    """停用词管理"""
    
    @staticmethod
    def get_default() -> Set[str]:
        """获取默认停用词表"""
        return {
            # 中文停用词
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
            '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
            '看', '好', '自己', '这', '那', '有', '吗', '吧', '啊', '呢', '呀', '什么',
            '这个', '那个', '只是', '还是', '可以', '因为', '所以', '但是', '如果', '或者',
            # 英文停用词
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought', 'used',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under',
            'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
            'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
            'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at',
            'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through',
            # 其他
            'http', 'https', 'www', 'com', 'cn', 'net', 'org'
        }


class TextCleaner:
    """文本清洗"""
    
    @staticmethod
    def clean(text: str) -> str:
        """清洗文本"""
        if not text:
            return ""
        
        # 移除 URL
        text = re.sub(r'https?://\S+', '', text)
        
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除特殊字符，保留中文、英文、数字
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text


class Tokenizer:
    """分词器"""
    
    def __init__(self, stop_words: Set[str] = None):
        self.stop_words = stop_words or StopWords.get_default()
    
    def tokenize(self, text: str) -> List[str]:
        """分词"""
        text = TextCleaner.clean(text)
        if not text:
            return []
        
        if JIEBA_AVAILABLE:
            # 使用 jieba 分词
            words = list(jieba.cut(text))
        else:
            # 简单分词：按空格和标点分割
            words = re.findall(r'[\w\u4e00-\u9fff]+', text)
        
        # 过滤停用词和短词
        filtered_words = [
            word for word in words
            if word.lower() not in self.stop_words
            and len(word) > 1
        ]
        
        return filtered_words


class TFIDF:
    """TF-IDF 实现"""
    
    def __init__(self, tokenizer: Tokenizer = None):
        self.tokenizer = tokenizer or Tokenizer()
        self.vocab = {}
        self.idf = {}
        self.doc_count = 0
    
    def fit(self, documents: List[str]):
        """训练 TF-IDF"""
        self.doc_count = len(documents)
        
        # 统计词频
        df = defaultdict(int)
        all_words = set()
        
        for doc in documents:
            words = self.tokenizer.tokenize(doc)
            unique_words = set(words)
            for word in unique_words:
                df[word] += 1
                all_words.add(word)
        
        # 构建词汇表
        self.vocab = {word: idx for idx, word in enumerate(sorted(all_words))}
        
        # 计算 IDF
        for word, freq in df.items():
            # IDF = log(N / (df + 1)) + 1
            self.idf[word] = math.log(self.doc_count / (freq + 1)) + 1
    
    def transform(self, text: str) -> Dict[str, float]:
        """转换文本为 TF-IDF 向量（返回词权重字典）"""
        words = self.tokenizer.tokenize(text)
        if not words:
            return {}
        
        # 计算 TF
        tf = Counter(words)
        max_freq = max(tf.values()) if tf else 1
        
        # 计算 TF-IDF
        tfidf = {}
        for word, freq in tf.items():
            if word in self.idf:
                # TF = 0.5 + 0.5 * (freq / max_freq)
                normalized_tf = 0.5 + 0.5 * (freq / max_freq)
                tfidf[word] = normalized_tf * self.idf[word]
        
        return tfidf
    
    def get_top_keywords(self, text: str, top_n: int = 20) -> List[Tuple[str, float]]:
        """获取文本的 Top N 关键词"""
        tfidf = self.transform(text)
        sorted_keywords = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
        return sorted_keywords[:top_n]


class BM25:
    """BM25 相关性排序算法"""
    
    def __init__(self, tokenizer: Tokenizer = None, k1: float = 1.5, b: float = 0.75):
        self.tokenizer = tokenizer or Tokenizer()
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.corpus_tokens = []
        self.doc_lengths = []
        self.avg_doc_len = 0
        self.df = defaultdict(int)
        self.idf = {}
    
    def fit(self, documents: List[str]):
        """训练 BM25"""
        self.corpus = documents
        self.corpus_tokens = []
        self.doc_lengths = []
        
        # 分词并统计
        for doc in documents:
            tokens = self.tokenizer.tokenize(doc)
            self.corpus_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            
            # 统计文档频率
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.df[token] += 1
        
        # 计算平均文档长度
        self.avg_doc_len = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        
        # 计算 IDF
        N = len(documents)
        for token, freq in self.df.items():
            self.idf[token] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)
    
    def score(self, query: str, doc_idx: int) -> float:
        """计算查询与文档的 BM25 分数"""
        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return 0.0
        
        doc_tokens = self.corpus_tokens[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        
        score = 0.0
        token_counts = Counter(doc_tokens)
        
        for token in query_tokens:
            if token not in self.idf:
                continue
            
            idf = self.idf[token]
            freq = token_counts.get(token, 0)
            
            # BM25 公式
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
            
            score += idf * (numerator / denominator)
        
        return score
    
    def rank(self, query: str, top_n: int = 10) -> List[Tuple[int, float]]:
        """对所有文档排序"""
        scores = []
        for idx in range(len(self.corpus)):
            score = self.score(query, idx)
            if score > 0:
                scores.append((idx, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


class CollaborativeFiltering:
    """协同过滤（基于用户相似度）"""
    
    def __init__(self):
        self.user_item_matrix = defaultdict(lambda: defaultdict(float))
        self.user_similarity = {}
    
    def add_interaction(self, user_id: str, item_id: str, weight: float = 1.0):
        """添加用户-物品交互"""
        self.user_item_matrix[user_id][item_id] += weight
    
    def compute_user_similarity(self, user_id: str) -> Dict[str, float]:
        """计算用户相似度（余弦相似度）"""
        if user_id not in self.user_item_matrix:
            return {}
        
        similarity = {}
        user_items = self.user_item_matrix[user_id]
        
        for other_user, other_items in self.user_item_matrix.items():
            if other_user == user_id:
                continue
            
            # 计算交集
            common_items = set(user_items.keys()) & set(other_items.keys())
            if not common_items:
                continue
            
            # 余弦相似度
            dot_product = sum(user_items[item] * other_items[item] for item in common_items)
            norm1 = math.sqrt(sum(v * v for v in user_items.values()))
            norm2 = math.sqrt(sum(v * v for v in other_items.values()))
            
            if norm1 > 0 and norm2 > 0:
                similarity[other_user] = dot_product / (norm1 * norm2)
        
        # 按相似度排序
        self.user_similarity[user_id] = dict(sorted(similarity.items(), key=lambda x: x[1], reverse=True))
        return self.user_similarity[user_id]
    
    def recommend(self, user_id: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """推荐物品"""
        if user_id not in self.user_item_matrix:
            return []
        
        if user_id not in self.user_similarity:
            self.compute_user_similarity(user_id)
        
        user_items = set(self.user_item_matrix[user_id].keys())
        similar_users = self.user_similarity[user_id]
        
        # 聚合相似用户的物品
        item_scores = defaultdict(float)
        for other_user, sim in similar_users.items():
            for item, weight in self.user_item_matrix[other_user].items():
                if item not in user_items:
                    item_scores[item] += sim * weight
        
        # 排序
        sorted_items = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:top_n]
