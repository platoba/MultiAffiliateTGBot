"""Platform registry - central dispatcher for URL detection and conversion."""

import re
from typing import Optional
from ..config import PlatformConfig
from .base import BasePlatform, ConversionResult
from .amazon import AmazonHandler
from .shopee import ShopeeHandler
from .lazada import LazadaHandler
from .aliexpress import AliExpressHandler
from .tiktok import TikTokHandler

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


class PlatformRegistry:
    """Registry of all platform handlers."""

    def __init__(self, config: PlatformConfig):
        self.handlers: list[BasePlatform] = [
            AmazonHandler(tag=config.amazon_tag, domain=config.amazon_domain),
            ShopeeHandler(aff_id=config.shopee_aff_id),
            LazadaHandler(aff_id=config.lazada_aff_id),
            AliExpressHandler(aff_id=config.aliexpress_aff_id),
            TikTokHandler(aff_id=config.tiktok_aff_id),
        ]
        self._handler_map = {h.name: h for h in self.handlers}

    def detect(self, url: str) -> Optional[BasePlatform]:
        """Detect which platform a URL belongs to."""
        for handler in self.handlers:
            if handler.matches(url):
                return handler
        return None

    def convert(self, url: str) -> Optional[ConversionResult]:
        """Convert a URL to affiliate link."""
        handler = self.detect(url)
        if handler:
            return handler.convert(url)
        return None

    def extract_urls(self, text: str) -> list[str]:
        """Extract all URLs from text."""
        return URL_PATTERN.findall(text)

    def process_message(self, text: str, max_links: int = 10) -> list[ConversionResult]:
        """Process a message and return conversion results."""
        if not text:
            return []
        urls = self.extract_urls(text)
        results = []
        for url in urls[:max_links]:
            result = self.convert(url)
            if result:
                results.append(result)
        return results

    def get_handler(self, platform: str) -> Optional[BasePlatform]:
        """Get handler by platform name."""
        return self._handler_map.get(platform)

    @property
    def platform_names(self) -> list[str]:
        return [h.name for h in self.handlers]

    @property
    def platform_emojis(self) -> dict[str, str]:
        return {h.name: h.emoji for h in self.handlers}
