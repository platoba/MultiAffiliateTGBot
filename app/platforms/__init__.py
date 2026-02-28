"""Platform-specific affiliate link handlers."""

from .amazon import AmazonHandler
from .shopee import ShopeeHandler
from .lazada import LazadaHandler
from .aliexpress import AliExpressHandler
from .tiktok import TikTokHandler
from .registry import PlatformRegistry

__all__ = [
    "AmazonHandler", "ShopeeHandler", "LazadaHandler",
    "AliExpressHandler", "TikTokHandler", "PlatformRegistry",
]
