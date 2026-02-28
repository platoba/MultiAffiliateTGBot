"""AliExpress affiliate link handler."""

import re
from urllib.parse import quote
from .base import BasePlatform, ConversionResult


class AliExpressHandler(BasePlatform):
    name = "aliexpress"
    emoji = "🔴"
    domains = ["aliexpress.com", "aliexpress.ru", "aliexpress.us"]
    short_domains = ["s.click.aliexpress.com", "a.aliexpress.com"]
    commission_rates = {
        "Electronics": "3-7%",
        "Clothing": "5-9%",
        "Home": "3-7%",
        "Toys": "5-9%",
        "Default": "3-9%",
    }

    ITEM_PATTERN = re.compile(r"item/(\d+)\.html|/(\d{8,15})")

    def __init__(self, aff_id: str = ""):
        self.aff_id = aff_id

    def convert(self, url: str) -> ConversionResult:
        if not self.aff_id:
            return ConversionResult(
                platform=self.name,
                original_url=url,
                error="⚠️ 未配置 ALIEXPRESS_AFF_ID",
            )

        # Expand short URLs
        if self._is_short_url(url):
            expanded = self.expand_short_url(url)
            if expanded:
                url = expanded

        match = self.ITEM_PATTERN.search(url)
        product_id = (match.group(1) or match.group(2)) if match else None

        aff_url = f"https://s.click.aliexpress.com/e/{self.aff_id}?url={quote(url)}"
        return ConversionResult(
            platform=self.name,
            original_url=url,
            affiliate_url=aff_url,
            product_id=product_id,
            estimated_commission="3-9%",
        )
