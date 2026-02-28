"""Tests for message formatter."""

import pytest
from app.platforms.base import ConversionResult


class TestMessageFormatter:
    def test_get_string_zh(self, formatter):
        assert "联盟链接" in formatter.get("affiliate_link_single")

    def test_get_string_en(self, formatter_en):
        assert "Affiliate" in formatter_en.get("affiliate_link_single")

    def test_get_with_params(self, formatter):
        result = formatter.get("affiliate_link_multi", count=3)
        assert "3" in result

    def test_format_results_single(self, formatter):
        results = [ConversionResult(
            platform="amazon", original_url="url",
            affiliate_url="https://amazon.com/dp/B123?tag=t",
            estimated_commission="3%"
        )]
        msg = formatter.format_results(results, show_commission=False)
        assert msg is not None
        assert "联盟链接" in msg

    def test_format_results_multiple(self, formatter):
        results = [
            ConversionResult(platform="amazon", original_url="url1", affiliate_url="aff1"),
            ConversionResult(platform="shopee", original_url="url2", affiliate_url="aff2"),
        ]
        msg = formatter.format_results(results, show_commission=False)
        assert "2个" in msg

    def test_format_results_empty(self, formatter):
        assert formatter.format_results([]) is None

    def test_format_results_with_errors(self, formatter):
        results = [ConversionResult(platform="amazon", original_url="url", error="bad")]
        msg = formatter.format_results(results, show_commission=False)
        assert "bad" in msg

    def test_format_commission_table(self, formatter):
        from app.platforms.amazon import AmazonHandler
        from app.platforms.shopee import ShopeeHandler
        handlers = [AmazonHandler(tag="t"), ShopeeHandler(aff_id="s")]
        table = formatter.format_commission_table(handlers)
        assert "AMAZON" in table
        assert "SHOPEE" in table
        assert "%" in table

    def test_rate_limited_message_zh(self, formatter):
        msg = formatter.get("error_rate_limited", seconds=30)
        assert "30" in msg

    def test_rate_limited_message_en(self, formatter_en):
        msg = formatter_en.get("error_rate_limited", seconds=30)
        assert "30" in msg

    def test_start_greeting(self, formatter):
        msg = formatter.get("start_greeting", platforms="Amazon, Shopee")
        assert "Amazon" in msg

    def test_help_text(self, formatter):
        msg = formatter.get("help_text", max_links=10)
        assert "10" in msg

    def test_fallback_to_zh(self):
        from app.services.formatter import MessageFormatter
        f = MessageFormatter(lang="nonexistent")
        assert f.lang == "zh"
