"""
智能推荐引擎 - 基于用户历史行为推荐相关产品
"""
import sqlite3
from typing import List, Dict, Optional
from collections import Counter
import re

class RecommendationEngine:
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化推荐系统数据表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interests (
                user_id INTEGER,
                category TEXT,
                platform TEXT,
                interest_score REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, category, platform)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_keywords (
                product_url TEXT PRIMARY KEY,
                keywords TEXT,
                platform TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def extract_keywords(self, url: str) -> List[str]:
        """从URL中提取产品关键词"""
        # 移除协议和域名
        clean_url = re.sub(r'https?://[^/]+/', '', url)
        # 提取可能的产品词
        words = re.findall(r'[a-zA-Z]{3,}', clean_url.lower())
        # 过滤常见无意义词
        stopwords = {'www', 'com', 'item', 'product', 'detail', 'shop', 'store'}
        return [w for w in words if w not in stopwords][:5]
    
    def update_user_interest(self, user_id: int, url: str, platform: str):
        """更新用户兴趣画像"""
        keywords = self.extract_keywords(url)
        if not keywords:
            return
        
        # 简单分类：取第一个关键词作为类别
        category = keywords[0]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 增加兴趣分数
        cursor.execute("""
            INSERT INTO user_interests (user_id, category, platform, interest_score)
            VALUES (?, ?, ?, 1.0)
            ON CONFLICT(user_id, category, platform) 
            DO UPDATE SET 
                interest_score = interest_score + 0.5,
                last_updated = CURRENT_TIMESTAMP
        """, (user_id, category, platform))
        
        # 存储产品关键词
        cursor.execute("""
            INSERT OR REPLACE INTO product_keywords (product_url, keywords, platform)
            VALUES (?, ?, ?)
        """, (url, ','.join(keywords), platform))
        
        conn.commit()
        conn.close()
    
    def get_recommendations(self, user_id: int, limit: int = 5) -> List[Dict]:
        """获取个性化推荐"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取用户top兴趣
        cursor.execute("""
            SELECT category, platform, interest_score
            FROM user_interests
            WHERE user_id = ?
            ORDER BY interest_score DESC, last_updated DESC
            LIMIT 3
        """, (user_id,))
        
        interests = cursor.fetchall()
        if not interests:
            conn.close()
            return []
        
        # 基于兴趣查找相似产品
        recommendations = []
        for category, platform, score in interests:
            cursor.execute("""
                SELECT DISTINCT pk.product_url, pk.platform, pk.keywords
                FROM product_keywords pk
                WHERE pk.keywords LIKE ?
                AND pk.platform = ?
                AND pk.product_url NOT IN (
                    SELECT url FROM link_cache WHERE user_id = ?
                )
                LIMIT ?
            """, (f'%{category}%', platform, user_id, limit))
            
            recommendations.extend([
                {
                    'url': row[0],
                    'platform': row[1],
                    'keywords': row[2],
                    'relevance_score': score
                }
                for row in cursor.fetchall()
            ])
        
        conn.close()
        
        # 按相关度排序并去重
        seen = set()
        unique_recs = []
        for rec in sorted(recommendations, key=lambda x: x['relevance_score'], reverse=True):
            if rec['url'] not in seen:
                seen.add(rec['url'])
                unique_recs.append(rec)
                if len(unique_recs) >= limit:
                    break
        
        return unique_recs
    
    def get_trending_products(self, platform: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """获取热门产品（基于转换频率）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT lc.url, lc.platform, COUNT(*) as conversion_count
            FROM link_cache lc
            WHERE lc.created_at >= datetime('now', '-7 days')
        """
        params = []
        
        if platform:
            query += " AND lc.platform = ?"
            params.append(platform)
        
        query += """
            GROUP BY lc.url, lc.platform
            ORDER BY conversion_count DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'url': row[0],
                'platform': row[1],
                'conversion_count': row[2]
            }
            for row in results
        ]
