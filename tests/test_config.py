"""Tests for configuration module."""

import os
import pytest


class TestBotConfig:
    def test_from_env(self, config):
        assert config.bot.token == "test:token"
        assert config.bot.language == "zh"
        assert config.bot.max_links_per_message == 10
        assert config.bot.rate_limit_per_minute == 30

    def test_defaults(self):
        from app.config import BotConfig
        cfg = BotConfig()
        assert cfg.token == ""
        assert cfg.language == "zh"
        assert cfg.cache_ttl_hours == 24


class TestPlatformConfig:
    def test_from_env(self, platform_config):
        assert platform_config.amazon_tag == "test-20"
        assert platform_config.shopee_aff_id == "test_shopee"
        assert platform_config.lazada_aff_id == "test_lazada"
        assert platform_config.aliexpress_aff_id == "test_ali"
        assert platform_config.tiktok_aff_id == "test_tiktok"

    def test_active_platforms(self, platform_config):
        active = platform_config.active_platforms()
        assert "amazon" in active
        assert "shopee" in active
        assert len(active) == 5

    def test_platform_display(self, platform_config):
        display = platform_config.platform_display()
        assert any("Amazon" in d for d in display)
        assert any("Shopee" in d for d in display)

    def test_no_platforms_configured(self):
        from app.config import PlatformConfig
        cfg = PlatformConfig()
        assert cfg.active_platforms() == []
        assert cfg.platform_display() == []


class TestDatabaseConfig:
    def test_from_env(self, config):
        assert "affiliate.db" in config.database.db_path

    def test_custom_data_dir(self):
        os.environ["DATA_DIR"] = "/tmp/test_aff"
        from app.config import DatabaseConfig
        cfg = DatabaseConfig.from_env()
        assert "/tmp/test_aff" in cfg.db_path
        os.environ["DATA_DIR"] = "./data"


class TestAppConfig:
    def test_from_env(self, config):
        assert isinstance(config.bot, object)
        assert isinstance(config.platforms, object)
        assert isinstance(config.database, object)
