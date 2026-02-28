"""Tests for platform registry."""

import pytest


class TestPlatformRegistry:
    def test_detect_amazon(self, registry):
        handler = registry.detect("https://www.amazon.com/dp/B09V3KXJPB")
        assert handler is not None
        assert handler.name == "amazon"

    def test_detect_shopee(self, registry):
        handler = registry.detect("https://shopee.sg/product/123/456")
        assert handler is not None
        assert handler.name == "shopee"

    def test_detect_lazada(self, registry):
        handler = registry.detect("https://www.lazada.sg/products/test-i123.html")
        assert handler is not None
        assert handler.name == "lazada"

    def test_detect_aliexpress(self, registry):
        handler = registry.detect("https://www.aliexpress.com/item/123.html")
        assert handler is not None
        assert handler.name == "aliexpress"

    def test_detect_tiktok(self, registry):
        handler = registry.detect("https://shop.tiktok.com/product/123")
        assert handler is not None
        assert handler.name == "tiktok"

    def test_detect_unknown(self, registry):
        handler = registry.detect("https://www.google.com")
        assert handler is None

    def test_convert_amazon(self, registry):
        result = registry.convert("https://www.amazon.com/dp/B09V3KXJPB")
        assert result is not None
        assert result.success
        assert "tag=test-20" in result.affiliate_url

    def test_convert_unknown(self, registry):
        result = registry.convert("https://www.google.com")
        assert result is None

    def test_extract_urls(self, registry):
        text = "Check https://www.amazon.com/dp/B123 and https://shopee.sg/product/1/2"
        urls = registry.extract_urls(text)
        assert len(urls) == 2

    def test_extract_urls_empty(self, registry):
        assert registry.extract_urls("no links here") == []

    def test_process_message(self, registry):
        text = "Buy https://www.amazon.com/dp/B09V3KXJPB for $20"
        results = registry.process_message(text)
        assert len(results) == 1
        assert results[0].success

    def test_process_message_multiple(self, registry):
        text = "https://www.amazon.com/dp/B09V3KXJPB https://shopee.sg/product/1/2"
        results = registry.process_message(text)
        assert len(results) == 2

    def test_process_message_max_links(self, registry):
        text = " ".join([f"https://shopee.sg/product/{i}/1" for i in range(20)])
        results = registry.process_message(text, max_links=3)
        assert len(results) == 3

    def test_process_message_empty(self, registry):
        assert registry.process_message("") == []
        assert registry.process_message(None) == []

    def test_process_message_no_ecommerce(self, registry):
        assert registry.process_message("https://www.google.com") == []

    def test_get_handler(self, registry):
        handler = registry.get_handler("amazon")
        assert handler is not None
        assert handler.name == "amazon"

    def test_get_handler_unknown(self, registry):
        assert registry.get_handler("ebay") is None

    def test_platform_names(self, registry):
        names = registry.platform_names
        assert "amazon" in names
        assert "shopee" in names
        assert len(names) == 5

    def test_platform_emojis(self, registry):
        emojis = registry.platform_emojis
        assert emojis["amazon"] == "🛒"
        assert emojis["shopee"] == "🧡"
