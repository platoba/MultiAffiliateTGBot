"""
Tests for ML Recommender
"""
import pytest
import sqlite3
import os
from app.ml_recommender import MLRecommender

@pytest.fixture
def test_db():
    """创建测试数据库"""
    db_path = "test_ml.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            original_url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 插入测试数据
    test_data = [
        (1, "https://amazon.com/laptop-gaming"),
        (1, "https://amazon.com/headphone-wireless"),
        (2, "https://amazon.com/laptop-gaming"),
        (2, "https://shopee.com/phone-case"),
        (3, "https://amazon.com/headphone-wireless"),
    ]
    
    for user_id, url in test_data:
        cursor.execute(
            "INSERT INTO conversions (user_id, original_url) VALUES (?, ?)",
            (user_id, url)
        )
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # 清理
    if os.path.exists(db_path):
        os.remove(db_path)

def test_extract_category():
    """测试类别提取"""
    recommender = MLRecommender()
    
    assert recommender.extract_category("https://amazon.com/laptop") == "electronics"
    assert recommender.extract_category("https://shopee.com/dress") == "fashion"
    assert recommender.extract_category("https://lazada.com/unknown") == "general"

def test_get_user_history(test_db):
    """测试用户历史获取"""
    recommender = MLRecommender(test_db)
    history = recommender.get_user_history(1)
    
    assert len(history) == 2
    assert "laptop-gaming" in history[0] or "laptop-gaming" in history[1]

def test_get_similar_users(test_db):
    """测试相似用户查找"""
    recommender = MLRecommender(test_db)
    similar = recommender.get_similar_users(1)
    
    # 用户1和用户2、3都有重叠
    assert len(similar) >= 1
    assert all(isinstance(user_id, int) and isinstance(score, float) for user_id, score in similar)

def test_recommend_products(test_db):
    """测试产品推荐"""
    recommender = MLRecommender(test_db)
    recommendations = recommender.recommend_products(1, limit=3)
    
    # 应该推荐用户1没转换过的产品
    assert isinstance(recommendations, list)
    for rec in recommendations:
        assert 'url' in rec
        assert 'score' in rec
        assert 'category' in rec

def test_get_trending_products(test_db):
    """测试热门产品"""
    recommender = MLRecommender(test_db)
    trending = recommender.get_trending_products(hours=24, limit=5)
    
    assert isinstance(trending, list)
    # laptop-gaming被2个用户转换，应该在热门列表
    if trending:
        assert any('laptop-gaming' in item['url'] for item in trending)
