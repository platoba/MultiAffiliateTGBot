"""
智能推荐引擎 - 基于用户行为的产品推荐
Recommendation Engine - Product recommendations based on user behavior
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from collections import Counter

class RecommendationEngine:
    """基于协同过滤和内容相似度的推荐引擎"""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """初始化推荐相关表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 用户产品交互表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                action TEXT NOT NULL,  -- 'click', 'convert', 'watch'
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT  -- JSON格式存储额外信息
            )
        """)
        
        # 产品特征表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_features (
                product_url TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                category TEXT,
                keywords TEXT,  -- 逗号分隔
                price_range TEXT,  -- 'low', 'mid', 'high'
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_interaction(self, user_id: int, product_url: str, 
                          platform: str, action: str, metadata: Optional[str] = None):
        """记录用户交互"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_interactions (user_id, product_url, platform, action, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, product_url, platform, action, metadata))
        
        conn.commit()
        conn.close()
    
    def extract_keywords(self, url: str) -> List[str]:
        """从URL提取关键词"""
        # 简单的关键词提取（实际应用中可以更复杂）
        keywords = re.findall(r'[a-zA-Z]{3,}', url.lower())
        # 过滤常见词
        stopwords = {'http', 'https', 'www', 'com', 'item', 'product', 'shop', 'amazon', 'shopee', 'lazada', 'aliexpress', 'tiktok'}
        return [k for k in keywords if k not in stopwords]
    
    def get_user_preferences(self, user_id: int, days: int = 30) -> Dict:
        """获取用户偏好"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # 获取用户交互历史
        cursor.execute("""
            SELECT platform, product_url, action
            FROM user_interactions
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        """, (user_id, since))
        
        interactions = cursor.fetchall()
        conn.close()
        
        if not interactions:
            return {'platforms': [], 'keywords': [], 'urls': []}
        
        # 统计平台偏好
        platforms = Counter([i[0] for i in interactions])
        
        # 提取关键词
        all_keywords = []
        for _, url, _ in interactions:
            all_keywords.extend(self.extract_keywords(url))
        keywords = Counter(all_keywords).most_common(10)
        
        # 高权重交互的URL
        high_value_urls = [url for _, url, action in interactions 
                          if action in ('convert', 'watch')]
        
        return {
            'platforms': [p for p, _ in platforms.most_common(3)],
            'keywords': [k for k, _ in keywords],
            'urls': high_value_urls[:5]
        }
    
    def get_similar_users(self, user_id: int, limit: int = 10) -> List[int]:
        """找到相似用户（协同过滤）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取目标用户的产品集合
        cursor.execute("""
            SELECT DISTINCT product_url
            FROM user_interactions
            WHERE user_id = ?
        """, (user_id,))
        
        user_products = set(row[0] for row in cursor.fetchall())
        
        if not user_products:
            conn.close()
            return []
        
        # 找到有交集的其他用户
        cursor.execute("""
            SELECT user_id, COUNT(DISTINCT product_url) as overlap
            FROM user_interactions
            WHERE product_url IN ({})
            AND user_id != ?
            GROUP BY user_id
            ORDER BY overlap DESC
            LIMIT ?
        """.format(','.join('?' * len(user_products))), 
        (*user_products, user_id, limit))
        
        similar_users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return similar_users
    
    def recommend_products(self, user_id: int, limit: int = 5) -> List[Dict]:
        """为用户推荐产品"""
        preferences = self.get_user_preferences(user_id)
        
        if not preferences['platforms']:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 策略1: 基于相似用户的推荐
        similar_users = self.get_similar_users(user_id, limit=10)
        
        if similar_users:
            # 获取相似用户最近交互的产品（排除当前用户已交互的）
            cursor.execute("""
                SELECT ui.product_url, ui.platform, COUNT(*) as score
                FROM user_interactions ui
                WHERE ui.user_id IN ({})
                AND ui.product_url NOT IN (
                    SELECT product_url FROM user_interactions WHERE user_id = ?
                )
                AND ui.timestamp > datetime('now', '-7 days')
                GROUP BY ui.product_url
                ORDER BY score DESC, ui.timestamp DESC
                LIMIT ?
            """.format(','.join('?' * len(similar_users))), 
            (*similar_users, user_id, limit))
            
            recommendations = []
            for url, platform, score in cursor.fetchall():
                recommendations.append({
                    'url': url,
                    'platform': platform,
                    'score': score,
                    'reason': 'similar_users'
                })
        else:
            recommendations = []
        
        # 策略2: 基于平台偏好的热门产品
        if len(recommendations) < limit and preferences['platforms']:
            cursor.execute("""
                SELECT product_url, platform, COUNT(*) as popularity
                FROM user_interactions
                WHERE platform IN ({})
                AND product_url NOT IN (
                    SELECT product_url FROM user_interactions WHERE user_id = ?
                )
                AND timestamp > datetime('now', '-3 days')
                GROUP BY product_url
                ORDER BY popularity DESC
                LIMIT ?
            """.format(','.join('?' * len(preferences['platforms']))),
            (*preferences['platforms'], user_id, limit - len(recommendations)))
            
            for url, platform, popularity in cursor.fetchall():
                recommendations.append({
                    'url': url,
                    'platform': platform,
                    'score': popularity,
                    'reason': 'trending'
                })
        
        conn.close()
        return recommendations[:limit]
    
    def get_recommendation_stats(self, user_id: int) -> Dict:
        """获取推荐统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总交互次数
        cursor.execute("""
            SELECT COUNT(*) FROM user_interactions WHERE user_id = ?
        """, (user_id,))
        total_interactions = cursor.fetchone()[0]
        
        # 最活跃平台
        cursor.execute("""
            SELECT platform, COUNT(*) as cnt
            FROM user_interactions
            WHERE user_id = ?
            GROUP BY platform
            ORDER BY cnt DESC
            LIMIT 1
        """, (user_id,))
        
        top_platform = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_interactions': total_interactions,
            'top_platform': top_platform[0] if top_platform else None,
            'has_enough_data': total_interactions >= 3
        }
