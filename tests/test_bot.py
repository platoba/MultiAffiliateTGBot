"""Tests for MultiAffiliateTGBot."""

import os
import sys

# Set test env vars before importing
os.environ["BOT_TOKEN"] = "test:token"
os.environ["AMAZON_TAG"] = "test-20"
os.environ["SHOPEE_AFF_ID"] = "test_shopee"
os.environ["LAZADA_AFF_ID"] = "test_lazada"
os.environ["ALIEXPRESS_AFF_ID"] = "test_ali"
os.environ["TIKTOK_AFF_ID"] = "test_tiktok"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot import detect_platform, make_amazon_affiliate, process_message, URL_PATTERN


class TestPlatformDetection:
    def test_amazon_com(self):
        assert detect_platform("https://www.amazon.com/dp/B09V3KXJPB") == "amazon"

    def test_amazon_short(self):
        assert detect_platform("https://amzn.to/3abc123") == "amazon"

    def test_amazon_de(self):
        assert detect_platform("https://www.amazon.de/dp/B09V3KXJPB") == "amazon"

    def test_shopee(self):
        assert detect_platform("https://shopee.sg/product/123/456") == "shopee"

    def test_lazada(self):
        assert detect_platform("https://www.lazada.sg/products/test-i123456.html") == "lazada"

    def test_aliexpress(self):
        assert detect_platform("https://www.aliexpress.com/item/1234567890.html") == "aliexpress"

    def test_tiktok_shop(self):
        assert detect_platform("https://shop.tiktok.com/view/product/123") == "tiktok"

    def test_unknown(self):
        assert detect_platform("https://www.google.com") is None

    def test_ebay_not_supported(self):
        assert detect_platform("https://www.ebay.com/itm/123") is None


class TestAmazonAffiliate:
    def test_standard_dp_link(self):
        url = "https://www.amazon.com/dp/B09V3KXJPB"
        result, error = make_amazon_affiliate(url)
        assert result is not None
        assert "tag=test-20" in result
        assert "B09V3KXJPB" in result
        assert error is None

    def test_gp_product_link(self):
        url = "https://www.amazon.com/gp/product/B09V3KXJPB"
        result, error = make_amazon_affiliate(url)
        assert result is not None
        assert "B09V3KXJPB" in result

    def test_no_asin(self):
        url = "https://www.amazon.com/s?k=headphones"
        result, error = make_amazon_affiliate(url)
        assert result is None
        assert "ASIN" in error


class TestProcessMessage:
    def test_single_amazon_link(self):
        text = "Check this out https://www.amazon.com/dp/B09V3KXJPB"
        result = process_message(text)
        assert result is not None
        assert "联盟链接" in result
        assert "tag=test-20" in result

    def test_no_links(self):
        assert process_message("Hello world") is None

    def test_non_ecommerce_link(self):
        assert process_message("https://www.google.com") is None

    def test_multiple_links(self):
        text = "https://www.amazon.com/dp/B09V3KXJPB and https://shopee.sg/product/123/456"
        result = process_message(text)
        assert result is not None
        assert "2个" in result

    def test_empty_message(self):
        assert process_message("") is None
        assert process_message(None) is None


class TestURLPattern:
    def test_extracts_urls(self):
        text = "Buy here: https://www.amazon.com/dp/B09V3KXJPB for $20"
        urls = URL_PATTERN.findall(text)
        assert len(urls) == 1
        assert "amazon.com" in urls[0]

    def test_multiple_urls(self):
        text = "https://a.com https://b.com"
        urls = URL_PATTERN.findall(text)
        assert len(urls) == 2
