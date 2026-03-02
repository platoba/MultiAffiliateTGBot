"""
价格监控服务测试
"""
import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from app.services.price_monitor import PriceMonitor


@pytest.fixture
def temp_db(tmp_path):
    """临时数据库"""
    db_path = tmp_path / "test_price_monitor.db"
    return str(db_path)


@pytest.fixture
def monitor(temp_db):
    """价格监控器实例"""
    return PriceMonitor(db_path=temp_db)


def test_init_db(monitor, temp_db):
    """测试数据库初始化"""
    assert os.path.exists(temp_db)
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # 检查表是否创建
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('price_watches', 'price_history')
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    assert 'price_watches' in tables
    assert 'price_history' in tables
    
    conn.close()


def test_add_watch(monitor):
    """测试添加价格监控"""
    result = monitor.add_watch(
        user_id=12345,
        product_url="https://amazon.com/product/123",
        affiliate_url="https://amazon.com/product/123?tag=test",
        platform="amazon",
        product_title="Test Product",
        current_price=99.99,
        notify_threshold=0.1
    )
    
    assert result is True
    
    # 验证数据
    watches = monitor.get_user_watches(12345)
    assert len(watches) == 1
    assert watches[0]['product_title'] == "Test Product"
    assert watches[0]['current_price'] == 99.99


def test_get_user_watches(monitor):
    """测试获取用户监控列表"""
    # 添加多个监控
    monitor.add_watch(12345, "url1", "aff1", "amazon", "Product 1", 10.0)
    monitor.add_watch(12345, "url2", "aff2", "shopee", "Product 2", 20.0)
    monitor.add_watch(67890, "url3", "aff3", "lazada", "Product 3", 30.0)
    
    # 获取用户12345的监控
    watches = monitor.get_user_watches(12345)
    assert len(watches) == 2
    
    # 获取用户67890的监控
    watches = monitor.get_user_watches(67890)
    assert len(watches) == 1
    assert watches[0]['platform'] == 'lazada'


def test_remove_watch(monitor):
    """测试移除价格监控"""
    # 添加监控
    monitor.add_watch(12345, "url1", "aff1", "amazon", "Product 1", 10.0)
    watches = monitor.get_user_watches(12345)
    watch_id = watches[0]['id']
    
    # 移除监控
    result = monitor.remove_watch(12345, watch_id)
    assert result is True
    
    # 验证已移除
    watches = monitor.get_user_watches(12345, active_only=True)
    assert len(watches) == 0
    
    # 包含非活跃的
    watches = monitor.get_user_watches(12345, active_only=False)
    assert len(watches) == 1


def test_duplicate_watch(monitor):
    """测试重复添加监控"""
    # 第一次添加
    monitor.add_watch(12345, "url1", "aff1", "amazon", "Product 1", 10.0)
    
    # 第二次添加相同URL（应该替换）
    monitor.add_watch(12345, "url1", "aff1", "amazon", "Product 1 Updated", 15.0)
    
    watches = monitor.get_user_watches(12345)
    assert len(watches) == 1
    assert watches[0]['current_price'] == 15.0


def test_check_prices_empty(monitor):
    """测试空监控列表的价格检查"""
    notifications = monitor.check_prices()
    assert notifications == []


def test_price_history(monitor):
    """测试价格历史记录"""
    # 添加监控
    monitor.add_watch(12345, "url1", "aff1", "amazon", "Product 1", 100.0)
    watches = monitor.get_user_watches(12345)
    watch_id = watches[0]['id']
    
    # 获取历史（应该有初始价格）
    history = monitor.get_price_history(watch_id)
    assert len(history) >= 1
    assert history[0]['price'] == 100.0


def test_notify_threshold(monitor):
    """测试通知阈值"""
    # 添加监控，阈值5%
    monitor.add_watch(
        user_id=12345,
        product_url="url1",
        affiliate_url="aff1",
        platform="amazon",
        current_price=100.0,
        notify_threshold=0.05
    )
    
    watches = monitor.get_user_watches(12345)
    assert watches[0]['notify_threshold'] == 0.05
