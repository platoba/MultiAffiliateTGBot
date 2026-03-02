"""
价格监控服务
监控已转换的产品链接价格变化，并在价格下降时通知用户
"""
import sqlite3
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class PriceMonitor:
    """价格监控器"""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化价格监控表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_url TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                product_title TEXT,
                current_price REAL,
                original_price REAL,
                currency TEXT DEFAULT 'USD',
                last_check TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notify_threshold REAL DEFAULT 0.05,
                is_active INTEGER DEFAULT 1,
                UNIQUE(user_id, product_url)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                price REAL NOT NULL,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (watch_id) REFERENCES price_watches(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watches_user 
            ON price_watches(user_id, is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watches_check 
            ON price_watches(last_check, is_active)
        """)
        
        conn.commit()
        conn.close()
    
    def add_watch(
        self,
        user_id: int,
        product_url: str,
        affiliate_url: str,
        platform: str,
        product_title: Optional[str] = None,
        current_price: Optional[float] = None,
        notify_threshold: float = 0.05
    ) -> bool:
        """添加价格监控"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO price_watches 
                (user_id, product_url, affiliate_url, platform, product_title, 
                 current_price, original_price, last_check, notify_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, product_url, affiliate_url, platform, product_title,
                current_price, current_price, datetime.now(), notify_threshold
            ))
            
            watch_id = cursor.lastrowid
            
            if current_price:
                cursor.execute("""
                    INSERT INTO price_history (watch_id, price)
                    VALUES (?, ?)
                """, (watch_id, current_price))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加价格监控失败: {e}")
            return False
    
    def get_user_watches(self, user_id: int, active_only: bool = True) -> List[Dict]:
        """获取用户的价格监控列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT id, product_url, affiliate_url, platform, product_title,
                   current_price, original_price, currency, last_check,
                   notify_threshold, created_at
            FROM price_watches
            WHERE user_id = ?
        """
        
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        watches = []
        for row in rows:
            watches.append({
                'id': row[0],
                'product_url': row[1],
                'affiliate_url': row[2],
                'platform': row[3],
                'product_title': row[4],
                'current_price': row[5],
                'original_price': row[6],
                'currency': row[7],
                'last_check': row[8],
                'notify_threshold': row[9],
                'created_at': row[10]
            })
        
        return watches
    
    def remove_watch(self, user_id: int, watch_id: int) -> bool:
        """移除价格监控"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE price_watches 
                SET is_active = 0
                WHERE id = ? AND user_id = ?
            """, (watch_id, user_id))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"移除价格监控失败: {e}")
            return False
    
    def check_prices(self, max_checks: int = 50) -> List[Dict]:
        """检查价格变化（返回需要通知的记录）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取需要检查的监控（超过1小时未检查）
        one_hour_ago = datetime.now() - timedelta(hours=1)
        cursor.execute("""
            SELECT id, user_id, product_url, affiliate_url, platform,
                   current_price, notify_threshold
            FROM price_watches
            WHERE is_active = 1 
            AND (last_check IS NULL OR last_check < ?)
            ORDER BY last_check ASC
            LIMIT ?
        """, (one_hour_ago, max_checks))
        
        watches = cursor.fetchall()
        conn.close()
        
        notifications = []
        
        for watch in watches:
            watch_id, user_id, product_url, affiliate_url, platform, old_price, threshold = watch
            
            # 模拟价格检查（实际应该爬取真实价格）
            # 这里简化处理，实际需要针对不同平台实现爬虫
            new_price = self._fetch_price(product_url, platform)
            
            if new_price and old_price:
                price_drop = (old_price - new_price) / old_price
                
                if price_drop >= threshold:
                    notifications.append({
                        'watch_id': watch_id,
                        'user_id': user_id,
                        'product_url': product_url,
                        'affiliate_url': affiliate_url,
                        'platform': platform,
                        'old_price': old_price,
                        'new_price': new_price,
                        'drop_percent': price_drop * 100
                    })
            
            # 更新检查时间和价格
            self._update_watch_price(watch_id, new_price)
        
        return notifications
    
    def _fetch_price(self, url: str, platform: str) -> Optional[float]:
        """获取产品价格（简化版，实际需要针对平台实现）"""
        # 这里返回None表示暂不支持自动抓取
        # 实际实现需要针对每个平台编写爬虫逻辑
        return None
    
    def _update_watch_price(self, watch_id: int, new_price: Optional[float]):
        """更新监控价格和检查时间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if new_price:
            cursor.execute("""
                UPDATE price_watches
                SET current_price = ?, last_check = ?
                WHERE id = ?
            """, (new_price, datetime.now(), watch_id))
            
            cursor.execute("""
                INSERT INTO price_history (watch_id, price)
                VALUES (?, ?)
            """, (watch_id, new_price))
        else:
            cursor.execute("""
                UPDATE price_watches
                SET last_check = ?
                WHERE id = ?
            """, (datetime.now(), watch_id))
        
        conn.commit()
        conn.close()
    
    def get_price_history(self, watch_id: int, days: int = 30) -> List[Dict]:
        """获取价格历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute("""
            SELECT price, checked_at
            FROM price_history
            WHERE watch_id = ? AND checked_at >= ?
            ORDER BY checked_at ASC
        """, (watch_id, cutoff))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'price': row[0], 'checked_at': row[1]} for row in rows]
