"""Test fixtures."""

import os
import sys
import tempfile
import pytest

# Set test env vars before any app imports
os.environ["BOT_TOKEN"] = "test:token"
os.environ["AMAZON_TAG"] = "test-20"
os.environ["AMAZON_DOMAIN"] = "amazon.com"
os.environ["SHOPEE_AFF_ID"] = "test_shopee"
os.environ["LAZADA_AFF_ID"] = "test_lazada"
os.environ["ALIEXPRESS_AFF_ID"] = "test_ali"
os.environ["TIKTOK_AFF_ID"] = "test_tiktok"
os.environ["BOT_LANGUAGE"] = "zh"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import AppConfig, BotConfig, PlatformConfig, DatabaseConfig
from app.platforms.registry import PlatformRegistry
from app.services.database import Database
from app.services.cache import LinkCache
from app.services.rate_limiter import RateLimiter
from app.services.exporter import StatsExporter
from app.services.formatter import MessageFormatter


@pytest.fixture
def config():
    return AppConfig.from_env()


@pytest.fixture
def platform_config():
    return PlatformConfig.from_env()


@pytest.fixture
def registry(platform_config):
    return PlatformRegistry(platform_config)


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def tmp_cache(tmp_path):
    cache_path = str(tmp_path / "cache.db")
    cache = LinkCache(cache_path, ttl_hours=1)
    yield cache
    cache.close()


@pytest.fixture
def rate_limiter():
    return RateLimiter(max_per_minute=5, burst=3)


@pytest.fixture
def exporter(tmp_db):
    return StatsExporter(tmp_db)


@pytest.fixture
def formatter():
    return MessageFormatter(lang="zh")


@pytest.fixture
def formatter_en():
    return MessageFormatter(lang="en")
