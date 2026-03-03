"""
测试推荐引擎
"""
import pytest
import sqlite3
import os
from app.recommendation_engine import RecommendationEngine

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_recommendations.db"
    return str(db_path)

@pytest.fixture
def engine(temp_db):
    eng = RecommendationEngine(db_path=temp_db)
    # 创建link_cache表用于测试
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS link_cache (
            user_id INTEGER,
            url TEXT,
            platform TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return eng

def test_extract_keywords(engine):
    url = "https://amazon.com/wireless-headphones-bluetooth-noise-cancelling/dp/B08XYZ"
    keywords = engine.extract_keywords(url)
    assert 'wireless' in keywords
    assert 'headphones' in keywords
    assert 'bluetooth' in keywords

def test_update_user_interest(engine):
    engine.update_user_interest(
        user_id=12345,
        url="https://shopee.com/gaming-laptop-rtx-4090",
        platform="shopee"
    )
    
    conn = sqlite3.connect(engine.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_interests WHERE user_id = 12345")
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[1] == 'gaming'  # category
    assert result[2] == 'shopee'  # platform

def test_get_recommendations(engine):
    # 模拟用户行为
    engine.update_user_interest(12345, "https://amazon.com/gaming-mouse", "amazon")
    engine.update_user_interest(12345, "https://amazon.com/gaming-keyboard", "amazon")
    
    # 添加相似产品
    conn = sqlite3.connect(engine.db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO product_keywords (product_url, keywords, platform)
        VALUES ('https://amazon.com/gaming-headset', 'gaming,headset', 'amazon')
    """)
    conn.commit()
    conn.close()
    
    recs = engine.get_recommendations(user_id=12345, limit=5)
    assert len(recs) > 0
    assert any('gaming' in rec['keywords'] for rec in recs)

def test_get_trending_products(engine):
    # 模拟多次转换
    conn = sqlite3.connect(engine.db_path)
    cursor = conn.cursor()
    
    for _ in range(5):
        cursor.execute("""
            INSERT INTO link_cache (user_id, url, platform)
            VALUES (?, ?, ?)
        """, (12345, "https://shopee.com/hot-product", "shopee"))
    
    conn.commit()
    conn.close()
    
    trending = engine.get_trending_products(limit=10)
    assert len(trending) > 0
    assert trending[0]['conversion_count'] == 5
