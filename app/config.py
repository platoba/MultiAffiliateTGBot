"""
Centralized configuration management.
All settings loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotConfig:
    """Telegram bot configuration."""
    token: str = ""
    dev_chat_id: str = ""
    language: str = "zh"  # zh or en
    max_links_per_message: int = 10
    rate_limit_per_minute: int = 30
    cache_ttl_hours: int = 24

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            token=os.environ.get("BOT_TOKEN", ""),
            dev_chat_id=os.environ.get("DEV_CHAT_ID", ""),
            language=os.environ.get("BOT_LANGUAGE", "zh"),
            max_links_per_message=int(os.environ.get("MAX_LINKS_PER_MSG", "10")),
            rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MIN", "30")),
            cache_ttl_hours=int(os.environ.get("CACHE_TTL_HOURS", "24")),
        )


@dataclass
class PlatformConfig:
    """Affiliate platform credentials."""
    amazon_tag: str = ""
    amazon_domain: str = "amazon.com"
    shopee_aff_id: str = ""
    lazada_aff_id: str = ""
    aliexpress_aff_id: str = ""
    tiktok_aff_id: str = ""

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        return cls(
            amazon_tag=os.environ.get("AMAZON_TAG", ""),
            amazon_domain=os.environ.get("AMAZON_DOMAIN", "amazon.com"),
            shopee_aff_id=os.environ.get("SHOPEE_AFF_ID", ""),
            lazada_aff_id=os.environ.get("LAZADA_AFF_ID", ""),
            aliexpress_aff_id=os.environ.get("ALIEXPRESS_AFF_ID", ""),
            tiktok_aff_id=os.environ.get("TIKTOK_AFF_ID", ""),
        )

    def active_platforms(self) -> list[str]:
        """Return list of configured platform names."""
        platforms = []
        if self.amazon_tag:
            platforms.append("amazon")
        if self.shopee_aff_id:
            platforms.append("shopee")
        if self.lazada_aff_id:
            platforms.append("lazada")
        if self.aliexpress_aff_id:
            platforms.append("aliexpress")
        if self.tiktok_aff_id:
            platforms.append("tiktok")
        return platforms

    def platform_display(self) -> list[str]:
        """Return formatted display strings for active platforms."""
        mapping = {
            "amazon": f"Amazon ({self.amazon_tag})",
            "shopee": f"Shopee ({self.shopee_aff_id})",
            "lazada": f"Lazada ({self.lazada_aff_id})",
            "aliexpress": f"AliExpress ({self.aliexpress_aff_id})",
            "tiktok": f"TikTok ({self.tiktok_aff_id})",
        }
        return [mapping[p] for p in self.active_platforms()]


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_path: str = "./data/affiliate.db"
    data_dir: str = "./data"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        data_dir = os.environ.get("DATA_DIR", "./data")
        db_path = os.environ.get("DB_PATH", f"{data_dir}/affiliate.db")
        return cls(db_path=db_path, data_dir=data_dir)


@dataclass
class AppConfig:
    """Root application config."""
    bot: BotConfig = field(default_factory=BotConfig)
    platforms: PlatformConfig = field(default_factory=PlatformConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            bot=BotConfig.from_env(),
            platforms=PlatformConfig.from_env(),
            database=DatabaseConfig.from_env(),
        )
