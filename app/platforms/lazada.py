"""Lazada affiliate link handler."""

import re
from urllib.parse import quote
from .base import BasePlatform, ConversionResult


class LazadaHandler(BasePlatform):
    name = "lazada"
    emoji = "💜"
    domains = [
        "lazada.sg", "lazada.com.my", "lazada.co.th", "lazada.vn",
        "lazada.co.id", "lazada.com.ph",
    ]
    short_domains = []
    commission_rates = {
        "Electronics": "1-5%",
        "Fashion": "5-12%",
        "Home & Living": "3-8%",
        "Default": "1-12%",
    }

    PRODUCT_PATTERN = re.compile(r"-i(\d+)(?:-s\d+)?\.html")

    def __init__(self, aff_id: str = ""):
        self.aff_id = aff_id

    def convert(self, url: str) -> ConversionResult:
        if not self.aff_id:
            return ConversionResult(
                platform=self.name,
                original_url=url,
                error="⚠️ 未配置 LAZADA_AFF_ID",
            )

        match = self.PRODUCT_PATTERN.search(url)
        product_id = match.group(1) if match else None

        aff_url = f"https://c.lazada.com/t/c.{self.aff_id}?url={quote(url)}"
        return ConversionResult(
            platform=self.name,
            original_url=url,
            affiliate_url=aff_url,
            product_id=product_id,
            estimated_commission="1-12%",
        )
