"""Shopee affiliate link handler."""

import re
from urllib.parse import quote
from .base import BasePlatform, ConversionResult


class ShopeeHandler(BasePlatform):
    name = "shopee"
    emoji = "🧡"
    domains = [
        "shopee.sg", "shopee.co.th", "shopee.vn", "shopee.ph",
        "shopee.com.my", "shopee.co.id", "shopee.com.br", "shopee.tw",
        "shopee.com.mx", "shopee.com.co", "shopee.cl", "shopee.pl",
    ]
    short_domains = ["shope.ee"]
    commission_rates = {
        "Electronics": "2-5%",
        "Fashion": "5-10%",
        "Home & Living": "3-8%",
        "Default": "2-10%",
    }

    PRODUCT_PATTERN = re.compile(r"(?:product/|i\.)(\d+)[./](\d+)")

    def __init__(self, aff_id: str = ""):
        self.aff_id = aff_id

    def convert(self, url: str) -> ConversionResult:
        if not self.aff_id:
            return ConversionResult(
                platform=self.name,
                original_url=url,
                error="⚠️ 未配置 SHOPEE_AFF_ID",
            )

        match = self.PRODUCT_PATTERN.search(url)
        product_id = f"{match.group(1)}.{match.group(2)}" if match else None

        aff_url = f"https://shope.ee/aff?aff_id={self.aff_id}&url={quote(url)}"
        return ConversionResult(
            platform=self.name,
            original_url=url,
            affiliate_url=aff_url,
            product_id=product_id,
            estimated_commission="2-10%",
        )
