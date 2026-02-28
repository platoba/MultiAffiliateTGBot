"""TikTok Shop affiliate link handler."""

from .base import BasePlatform, ConversionResult


class TikTokHandler(BasePlatform):
    name = "tiktok"
    emoji = "🎵"
    domains = ["shop.tiktok.com", "tiktokshop.com"]
    short_domains = []
    commission_rates = {
        "Beauty": "5-20%",
        "Fashion": "5-15%",
        "Electronics": "2-10%",
        "Default": "2-20%",
    }

    def __init__(self, aff_id: str = ""):
        self.aff_id = aff_id

    def convert(self, url: str) -> ConversionResult:
        if not self.aff_id:
            return ConversionResult(
                platform=self.name,
                original_url=url,
                error="⚠️ 未配置 TIKTOK_AFF_ID",
            )

        sep = "&" if "?" in url else "?"
        aff_url = f"{url}{sep}aff_id={self.aff_id}"
        return ConversionResult(
            platform=self.name,
            original_url=url,
            affiliate_url=aff_url,
            estimated_commission="2-20%",
        )
