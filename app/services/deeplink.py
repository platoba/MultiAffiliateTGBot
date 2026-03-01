"""
Smart deep linking service.

Generates platform-aware deep links with:
- App-to-web fallback (app:// → https:// graceful degradation)
- UTM campaign parameter builder
- Region/locale detection and redirect
- QR code data generation
- Branded short link structure
- Click-through tracking IDs
"""

import hashlib
import time
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse


@dataclass
class UTMParams:
    """UTM campaign tracking parameters."""
    source: str = ""
    medium: str = "affiliate"
    campaign: str = ""
    term: str = ""
    content: str = ""

    def to_dict(self) -> dict:
        result = {}
        if self.source:
            result["utm_source"] = self.source
        if self.medium:
            result["utm_medium"] = self.medium
        if self.campaign:
            result["utm_campaign"] = self.campaign
        if self.term:
            result["utm_term"] = self.term
        if self.content:
            result["utm_content"] = self.content
        return result

    def is_valid(self) -> bool:
        """UTM requires at least source and medium."""
        return bool(self.source and self.medium)


@dataclass
class DeepLinkResult:
    """Result of deep link generation."""
    web_url: str
    app_url: Optional[str] = None
    fallback_url: Optional[str] = None
    qr_data: Optional[str] = None
    tracking_id: str = ""
    platform: str = ""
    region: str = ""
    utm: Optional[UTMParams] = None
    short_code: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def has_app_link(self) -> bool:
        return self.app_url is not None

    def to_dict(self) -> dict:
        return {
            "web_url": self.web_url,
            "app_url": self.app_url,
            "fallback_url": self.fallback_url,
            "qr_data": self.qr_data,
            "tracking_id": self.tracking_id,
            "platform": self.platform,
            "region": self.region,
            "short_code": self.short_code,
            "created_at": self.created_at,
        }


# Platform app scheme mappings
APP_SCHEMES = {
    "amazon": {
        "scheme": "com.amazon.mobile.shopping",
        "intent": "android-app://com.amazon.mobile.shopping/amazon/{path}",
        "universal": "https://www.amazon.{tld}/dp/{product_id}",
    },
    "shopee": {
        "scheme": "shopee",
        "intent": "shopee://product/{shop_id}/{item_id}",
        "universal": "https://shopee.{tld}/product/{shop_id}/{item_id}",
    },
    "lazada": {
        "scheme": "lazada",
        "intent": "lazada://product/{product_id}",
        "universal": "https://www.lazada.{tld}/products/{product_id}.html",
    },
    "aliexpress": {
        "scheme": "aliexpress",
        "intent": "aliexpress://product/detail?productId={product_id}",
        "universal": "https://www.aliexpress.com/item/{product_id}.html",
    },
    "tiktok": {
        "scheme": "snssdk1233",
        "intent": "snssdk1233://product/detail?id={product_id}",
        "universal": "https://shop.tiktok.com/view/product/{product_id}",
    },
}

# Region detection by TLD
REGION_MAP = {
    "com": "US", "co.uk": "UK", "de": "DE", "fr": "FR",
    "it": "IT", "es": "ES", "co.jp": "JP", "ca": "CA",
    "com.au": "AU", "in": "IN", "com.mx": "MX", "com.br": "BR",
    "sg": "SG", "my": "MY", "th": "TH", "ph": "PH",
    "tw": "TW", "vn": "VN", "id": "ID", "co.id": "ID",
    "com.sg": "SG", "com.my": "MY", "com.th": "TH",
    "com.ph": "PH", "co.th": "TH",
}


class DeepLinkGenerator:
    """Generate platform-aware deep links with tracking."""

    def __init__(self, base_domain: str = "aff.link", default_utm_source: str = "telegram"):
        self.base_domain = base_domain
        self.default_utm_source = default_utm_source
        self._link_counter = 0

    def generate(
        self,
        url: str,
        platform: str,
        product_id: str = "",
        utm: Optional[UTMParams] = None,
        include_app_link: bool = True,
        include_qr: bool = False,
        campaign_name: str = "",
    ) -> DeepLinkResult:
        """Generate a complete deep link package for a URL."""
        if not url:
            raise ValueError("URL cannot be empty")

        platform = platform.lower().strip()
        region = self._detect_region(url)
        tracking_id = self._generate_tracking_id(url, platform)
        short_code = self._generate_short_code(url)

        # Build UTM params
        if utm is None:
            utm = UTMParams(
                source=self.default_utm_source,
                medium="affiliate",
                campaign=campaign_name or f"{platform}_{region.lower()}",
            )

        # Add UTM to web URL
        web_url = self._append_utm(url, utm)

        # Generate app deep link
        app_url = None
        if include_app_link and platform in APP_SCHEMES:
            app_url = self._build_app_link(platform, product_id, region, url)

        # QR code data (the URL itself or a short redirect)
        qr_data = None
        if include_qr:
            qr_data = f"https://{self.base_domain}/{short_code}"

        # Fallback URL (web version without app-specific params)
        fallback_url = url if app_url else None

        return DeepLinkResult(
            web_url=web_url,
            app_url=app_url,
            fallback_url=fallback_url,
            qr_data=qr_data,
            tracking_id=tracking_id,
            platform=platform,
            region=region,
            utm=utm,
            short_code=short_code,
        )

    def generate_batch(
        self,
        urls: list[dict],
        campaign_name: str = "",
        include_app_link: bool = True,
    ) -> list[DeepLinkResult]:
        """Generate deep links for multiple URLs.

        Args:
            urls: List of dicts with 'url', 'platform', optional 'product_id'
            campaign_name: Campaign name for UTM
            include_app_link: Whether to include app deep links
        """
        results = []
        for item in urls:
            try:
                result = self.generate(
                    url=item["url"],
                    platform=item["platform"],
                    product_id=item.get("product_id", ""),
                    campaign_name=campaign_name,
                    include_app_link=include_app_link,
                )
                results.append(result)
            except (ValueError, KeyError):
                continue
        return results

    def build_redirect_url(self, short_code: str, target_url: str) -> str:
        """Build a branded redirect URL."""
        return f"https://{self.base_domain}/r/{short_code}?to={target_url}"

    def build_comparison_link(self, product_id: str, platforms: list[str]) -> dict:
        """Build links for the same product across multiple platforms."""
        result = {}
        for platform in platforms:
            if platform in APP_SCHEMES:
                scheme = APP_SCHEMES[platform]
                result[platform] = {
                    "app": scheme["intent"].format(
                        product_id=product_id,
                        path=f"dp/{product_id}",
                        shop_id="0",
                        item_id=product_id,
                    ),
                    "web": scheme["universal"].format(
                        product_id=product_id,
                        tld="com",
                        shop_id="0",
                        item_id=product_id,
                    ),
                }
        return result

    def _detect_region(self, url: str) -> str:
        """Detect region from URL's TLD."""
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")

        # Try matching longest TLD first
        for tld, region in sorted(REGION_MAP.items(), key=lambda x: -len(x[0])):
            if host.endswith(f".{tld}") or host == tld:
                return region

        return "GLOBAL"

    def _generate_tracking_id(self, url: str, platform: str) -> str:
        """Generate a unique tracking ID for this conversion."""
        self._link_counter += 1
        data = f"{url}:{platform}:{time.time()}:{self._link_counter}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_short_code(self, url: str) -> str:
        """Generate a short code for branded links."""
        h = hashlib.md5(f"{url}:{time.time()}".encode()).hexdigest()[:8]
        return h

    def _append_utm(self, url: str, utm: UTMParams) -> str:
        """Append UTM parameters to URL."""
        utm_dict = utm.to_dict()
        if not utm_dict:
            return url

        parsed = urlparse(url)
        existing = parse_qs(parsed.query)

        # Don't overwrite existing UTM params
        for key, value in utm_dict.items():
            if key not in existing:
                existing[key] = [value]

        # Rebuild query string
        query = urlencode(
            {k: v[0] if isinstance(v, list) else v for k, v in existing.items()}
        )
        return urlunparse(parsed._replace(query=query))

    def _build_app_link(
        self, platform: str, product_id: str, region: str, url: str
    ) -> Optional[str]:
        """Build platform-specific app deep link."""
        if platform not in APP_SCHEMES:
            return None

        scheme = APP_SCHEMES[platform]
        tld = "com"

        # Find TLD from region
        for t, r in REGION_MAP.items():
            if r == region:
                tld = t
                break

        try:
            return scheme["intent"].format(
                product_id=product_id or "0",
                path=f"dp/{product_id}" if product_id else "",
                tld=tld,
                shop_id="0",
                item_id=product_id or "0",
            )
        except (KeyError, IndexError):
            return None

    @staticmethod
    def extract_product_id(url: str, platform: str) -> Optional[str]:
        """Extract product ID from URL for various platforms."""
        platform = platform.lower()

        patterns = {
            "amazon": [
                r"/dp/([A-Z0-9]{10})",
                r"/gp/product/([A-Z0-9]{10})",
                r"/product/([A-Z0-9]{10})",
                r"/ASIN/([A-Z0-9]{10})",
            ],
            "shopee": [
                r"\.(\d+)\?",
                r"i\.(\d+\.\d+)",
                r"/product/(\d+)/(\d+)",
            ],
            "lazada": [
                r"-i(\d+)",
                r"products/.*-i(\d+)",
            ],
            "aliexpress": [
                r"/item/(\d+)",
                r"productId=(\d+)",
                r"/(\d+)\.html",
            ],
            "tiktok": [
                r"product/(\d+)",
                r"id=(\d+)",
            ],
        }

        for pattern in patterns.get(platform, []):
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None
