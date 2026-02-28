"""Base class for platform handlers."""

import re
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ConversionResult:
    """Result of an affiliate link conversion."""
    platform: str
    original_url: str
    affiliate_url: Optional[str] = None
    error: Optional[str] = None
    product_id: Optional[str] = None
    estimated_commission: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.affiliate_url is not None


class BasePlatform(ABC):
    """Base class for all platform handlers."""

    name: str = ""
    emoji: str = ""
    domains: list[str] = []
    short_domains: list[str] = []

    # Commission rate ranges (approximate)
    commission_rates: dict[str, str] = {}

    def matches(self, url: str) -> bool:
        """Check if URL belongs to this platform."""
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return (
            any(d in host for d in self.domains) or
            any(d in host for d in self.short_domains)
        )

    @abstractmethod
    def convert(self, url: str) -> ConversionResult:
        """Convert URL to affiliate link."""
        ...

    def expand_short_url(self, url: str) -> Optional[str]:
        """Expand shortened URLs."""
        try:
            if not url.startswith("http"):
                url = "https://" + url
            r = requests.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return None

    def _is_short_url(self, url: str) -> bool:
        """Check if URL is a short link."""
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return any(d in host for d in self.short_domains)
