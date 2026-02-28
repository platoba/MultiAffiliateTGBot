"""Tests for legacy bot.py compatibility."""

import os
import sys
import pytest

# Ensure env vars are set
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("AMAZON_TAG", "test-20")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot import detect_platform, make_amazon_affiliate, process_message, URL_PATTERN


class TestLegacyPlatformDetection:
    def test_amazon_com(self):
        assert detect_platform("https://www.amazon.com/dp/B09V3KXJPB") == "amazon"

    def test_amazon_short(self):
        assert detect_platform("https://amzn.to/3abc123") == "amazon"

    def test_shopee(self):
        assert detect_platform("https://shopee.sg/product/123/456") == "shopee"

    def test_lazada(self):
        assert detect_platform("https://www.lazada.sg/products/test-i123456.html") == "lazada"

    def test_aliexpress(self):
        assert detect_platform("https://www.aliexpress.com/item/1234567890.html") == "aliexpress"

    def test_tiktok(self):
        assert detect_platform("https://shop.tiktok.com/view/product/123") == "tiktok"

    def test_unknown(self):
        assert detect_platform("https://www.google.com") is None


class TestLegacyAmazonAffiliate:
    def test_standard_dp(self):
        result, error = make_amazon_affiliate("https://www.amazon.com/dp/B09V3KXJPB")
        assert result is not None
        assert "tag=test-20" in result

    def test_no_asin(self):
        result, error = make_amazon_affiliate("https://www.amazon.com/s?k=test")
        assert result is None
        assert "ASIN" in error


class TestLegacyProcessMessage:
    def test_single_link(self):
        result = process_message("https://www.amazon.com/dp/B09V3KXJPB")
        assert result is not None
        assert "联盟链接" in result

    def test_no_links(self):
        assert process_message("Hello") is None

    def test_empty(self):
        assert process_message("") is None
        assert process_message(None) is None


class TestLegacyURLPattern:
    def test_extract(self):
        urls = URL_PATTERN.findall("Buy https://amazon.com/dp/B123 now")
        assert len(urls) == 1
