"""Amazon affiliate link handler."""

import re
from urllib.parse import urlparse
from .base import BasePlatform, ConversionResult


class AmazonHandler(BasePlatform):
    name = "amazon"
    emoji = "🛒"
    domains = [
        "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it",
        "amazon.es", "amazon.co.jp", "amazon.ca", "amazon.com.au", "amazon.in",
        "amazon.com.br", "amazon.com.mx", "amazon.sg", "amazon.ae", "amazon.sa",
        "amazon.nl", "amazon.pl", "amazon.se", "amazon.com.tr", "amazon.eg",
    ]
    short_domains = ["amzn.to", "amzn.eu", "amzn.asia", "a.co"]
    commission_rates = {
        "Luxury Beauty": "10%",
        "Amazon Coins": "10%",
        "Digital Music": "5%",
        "Physical Music": "5%",
        "Handmade": "5%",
        "Digital Videos": "5%",
        "Clothing": "4%",
        "Amazon Devices": "4%",
        "Headphones": "3%",
        "Beauty": "3%",
        "Electronics": "1-3%",
        "Default": "1-4%",
    }

    ASIN_PATTERN = re.compile(r"(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")

    def __init__(self, tag: str = "", domain: str = "amazon.com"):
        self.tag = tag
        self.domain = domain.replace("www.", "")

    def convert(self, url: str) -> ConversionResult:
        if not self.tag:
            return ConversionResult(
                platform=self.name,
                original_url=url,
                error="⚠️ 未配置 AMAZON_TAG",
            )

        # Expand short URLs
        if self._is_short_url(url):
            expanded = self.expand_short_url(url)
            if expanded:
                url = expanded
            else:
                return ConversionResult(
                    platform=self.name,
                    original_url=url,
                    error="⚠️ Amazon短链接展开失败",
                )

        match = self.ASIN_PATTERN.search(url)
        if match:
            asin = match.group(1)
            # Detect the actual domain from URL
            parsed = urlparse(url)
            host = parsed.netloc.lower().replace("www.", "")
            actual_domain = self.domain
            for d in self.domains:
                if d in host:
                    actual_domain = d
                    break

            aff_url = f"https://www.{actual_domain}/dp/{asin}?tag={self.tag}"
            return ConversionResult(
                platform=self.name,
                original_url=url,
                affiliate_url=aff_url,
                product_id=asin,
                estimated_commission="1-10%",
            )

        return ConversionResult(
            platform=self.name,
            original_url=url,
            error="⚠️ 无法提取Amazon ASIN",
        )

    def extract_asin(self, url: str) -> str | None:
        """Extract ASIN from URL."""
        match = self.ASIN_PATTERN.search(url)
        return match.group(1) if match else None
