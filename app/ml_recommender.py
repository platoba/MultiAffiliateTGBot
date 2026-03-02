"""
ML-based Product Recommendation Engine
基于机器学习的产品推荐引擎
"""
import sqlite3
from typing import List, Dict, Tuple
from collections import Counter, defaultdict
import math

class MLRecommender:
    """协同过滤推荐引擎"""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
    
    def get_user_history(self, user_id: int, limit: int = 50) -> List[str]:
        """获取用户历史转换记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_url FROM conversions 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (user_id, limit))
        urls = [row[0] for row in cursor.fetchall()]
        conn.close()
        return urls
    
    def extract_category(self, url: str) -> str:
        """从URL提取商品类别（简化版）"""
        keywords = {
            'electronics': ['phone', 'laptop', 'tablet', 'camera', 'headphone'],
            'fashion': ['dress', 'shirt', 'shoes', 'bag', 'watch'],
            'home': ['furniture', 'kitchen', 'decor', 'bedding'],
            'beauty': ['makeup', 'skincare', 'perfume', 'cosmetic'],
            'sports': ['fitness', 'yoga', 'running', 'gym', 'sport']
        }
        
        url_lower = url.lower()
        for category, words in keywords.items():
            if any(word in url_lower for word in words):
                return category
        return 'general'
    
    def get_similar_users(self, user_id: int, top_n: int = 10) -> List[Tuple[int, float]]:
        """找到相似用户（基于Jaccard相似度）"""
        user_history = set(self.get_user_history(user_id))
        if not user_history:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT user_id FROM conversions WHERE user_id != ?", (user_id,))
        other_users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        similarities = []
        for other_user in other_users[:100]:  # 限制计算量
            other_history = set(self.get_user_history(other_user, 30))
            if not other_history:
                continue
            
            intersection = len(user_history & other_history)
            union = len(user_history | other_history)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0.1:  # 相似度阈值
                similarities.append((other_user, similarity))
        
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_n]
    
    def recommend_products(self, user_id: int, limit: int = 5) -> List[Dict]:
        """推荐产品"""
        # 1. 基于用户历史的类别偏好
        user_history = self.get_user_history(user_id)
        user_categories = [self.extract_category(url) for url in user_history]
        category_counts = Counter(user_categories)
        
        # 2. 找到相似用户
        similar_users = self.get_similar_users(user_id)
        
        # 3. 收集候选产品
        candidate_scores = defaultdict(float)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for similar_user_id, similarity in similar_users:
            cursor.execute("""
                SELECT original_url, COUNT(*) as freq 
                FROM conversions 
                WHERE user_id = ? 
                GROUP BY original_url 
                ORDER BY freq DESC 
                LIMIT 20
            """, (similar_user_id,))
            
            for url, freq in cursor.fetchall():
                if url not in user_history:  # 排除已转换过的
                    category = self.extract_category(url)
                    category_boost = 1.5 if category in category_counts else 1.0
                    candidate_scores[url] += similarity * freq * category_boost
        
        conn.close()
        
        # 4. 排序并返回
        recommendations = sorted(
            candidate_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:limit]
        
        return [
            {
                'url': url,
                'score': score,
                'category': self.extract_category(url),
                'reason': 'Similar users also liked'
            }
            for url, score in recommendations
        ]
    
    def get_trending_products(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """获取热门产品"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_url, COUNT(*) as conversion_count,
                   COUNT(DISTINCT user_id) as unique_users
            FROM conversions
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
            GROUP BY original_url
            HAVING conversion_count >= 3
            ORDER BY conversion_count DESC, unique_users DESC
            LIMIT ?
        """, (hours, limit))
        
        trending = []
        for url, conv_count, unique_users in cursor.fetchall():
            trending.append({
                'url': url,
                'conversions': conv_count,
                'unique_users': unique_users,
                'category': self.extract_category(url),
                'reason': f'🔥 {conv_count} conversions in {hours}h'
            })
        
        conn.close()
        return trending
