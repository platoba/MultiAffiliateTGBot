"""
测试推荐引擎
"""
import pytest
import sqlite3
import os
from app.recommendation_engine import RecommendationEngine

@pytest.fixture
def temp_db(tmp_path):
    """临时数据库"""
    db_path = tmp_path / "test_recommendations.db"
    return str(db_path)

@pytest.fixture
def engine(temp_db):
    """推荐引擎实例"""
    return RecommendationEngine(db_path=temp_db)

def test_init_tables(engine, temp_db):
    """测试表初始化"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    assert 'user_interactions' in tables
    assert 'product_features' in tables
    
    conn.close()

def test_record_interaction(engine, temp_db):
    """测试记录交互"""
    engine.record_interaction(
        user_id=123,
        product_url="https://amazon.com/product/B08XYZ",
        platform="amazon",
        action="click"
    )
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_interactions WHERE user_id=123")
    row = cursor.fetchone()
    
    assert row is not None
    assert row[1] == 123  # user_id
    assert row[3] == "amazon"  # platform
    assert row[4] == "click"  # action
    
    conn.close()

def test_extract_keywords(engine):
    """测试关键词提取"""
    url = "https://amazon.com/wireless-headphones-bluetooth-noise-cancelling"
    keywords = engine.extract_keywords(url)
    
    assert 'wireless' in keywords
    assert 'headphones' in keywords
    assert 'bluetooth' in keywords
    assert 'amazon' not in keywords  # 应该被过滤

def test_get_user_preferences(engine):
    """测试获取用户偏好"""
    # 添加测试数据
    engine.record_interaction(123, "https://amazon.com/headphones", "amazon", "click")
    engine.record_interaction(123, "https://shopee.com/earbuds", "shopee", "convert")
    engine.record_interaction(123, "https://amazon.com/speakers", "amazon", "watch")
    
    prefs = engine.get_user_preferences(123)
    
    assert 'amazon' in prefs['platforms']
    assert len(prefs['keywords']) > 0
    assert len(prefs['urls']) > 0

def test_get_similar_users(engine):
    """测试相似用户查找"""
    # 用户1和用户2有共同产品
    common_url = "https://amazon.com/popular-product"
    engine.record_interaction(1, common_url, "amazon", "click")
    engine.record_interaction(2, common_url, "amazon", "click")
    engine.record_interaction(2, "https://shopee.com/other", "shopee", "click")
    
    similar = engine.get_similar_users(1)
    
    assert 2 in similar

def test_recommend_products_cold_start(engine):
    """测试冷启动推荐"""
    # 新用户没有历史
    recommendations = engine.recommend_products(999)
    
    assert isinstance(recommendations, list)
    # 冷启动可能返回空列表

def test_recommend_products_with_history(engine):
    """测试有历史的推荐"""
    # 用户1的历史
    engine.record_interaction(1, "https://amazon.com/product-a", "amazon", "click")
    engine.record_interaction(1, "https://amazon.com/product-b", "amazon", "convert")
    
    # 用户2（相似用户）的历史
    engine.record_interaction(2, "https://amazon.com/product-a", "amazon", "click")
    engine.record_interaction(2, "https://amazon.com/product-c", "amazon", "click")
    
    recommendations = engine.recommend_products(1, limit=5)
    
    assert isinstance(recommendations, list)
    # 应该推荐product-c（相似用户喜欢的）
    if recommendations:
        assert any('product-c' in r['url'] for r in recommendations)

def test_get_recommendation_stats(engine):
    """测试推荐统计"""
    engine.record_interaction(123, "https://amazon.com/test", "amazon", "click")
    engine.record_interaction(123, "https://shopee.com/test", "shopee", "click")
    engine.record_interaction(123, "https://amazon.com/test2", "amazon", "convert")
    
    stats = engine.get_recommendation_stats(123)
    
    assert stats['total_interactions'] == 3
    assert stats['top_platform'] == 'amazon'
    assert stats['has_enough_data'] is True

def test_recommend_products_limit(engine):
    """测试推荐数量限制"""
    # 添加大量数据
    for i in range(20):
        engine.record_interaction(1, f"https://amazon.com/product-{i}", "amazon", "click")
        engine.record_interaction(2, f"https://amazon.com/product-{i}", "amazon", "click")
    
    engine.record_interaction(2, "https://amazon.com/new-product", "amazon", "click")
    
    recommendations = engine.recommend_products(1, limit=3)
    
    assert len(recommendations) <= 3
