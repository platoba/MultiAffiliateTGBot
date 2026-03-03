"""Tests for platform handlers."""

from app.platforms.amazon import AmazonHandler
from app.platforms.shopee import ShopeeHandler
from app.platforms.lazada import LazadaHandler
from app.platforms.aliexpress import AliExpressHandler
from app.platforms.tiktok import TikTokHandler
from app.platforms.base import ConversionResult


class TestAmazonHandler:
    def setup_method(self):
        self.handler = AmazonHandler(tag="test-20", domain="amazon.com")

    def test_matches_amazon_com(self):
        assert self.handler.matches("https://www.amazon.com/dp/B09V3KXJPB")

    def test_matches_amazon_de(self):
        assert self.handler.matches("https://www.amazon.de/dp/B09V3KXJPB")

    def test_matches_amazon_co_jp(self):
        assert self.handler.matches("https://www.amazon.co.jp/dp/B09V3KXJPB")

    def test_matches_short_url(self):
        assert self.handler.matches("https://amzn.to/3abc123")

    def test_matches_a_co(self):
        assert self.handler.matches("https://a.co/d/abc123")

    def test_no_match_google(self):
        assert not self.handler.matches("https://www.google.com")

    def test_convert_standard_dp(self):
        result = self.handler.convert("https://www.amazon.com/dp/B09V3KXJPB")
        assert result.success
        assert "tag=test-20" in result.affiliate_url
        assert "B09V3KXJPB" in result.affiliate_url
        assert result.product_id == "B09V3KXJPB"

    def test_convert_gp_product(self):
        result = self.handler.convert("https://www.amazon.com/gp/product/B09V3KXJPB")
        assert result.success
        assert "B09V3KXJPB" in result.affiliate_url

    def test_convert_no_asin(self):
        result = self.handler.convert("https://www.amazon.com/s?k=headphones")
        assert not result.success
        assert "ASIN" in result.error

    def test_convert_no_tag(self):
        handler = AmazonHandler(tag="", domain="amazon.com")
        result = handler.convert("https://www.amazon.com/dp/B09V3KXJPB")
        assert not result.success
        assert "AMAZON_TAG" in result.error

    def test_extract_asin(self):
        assert self.handler.extract_asin("https://www.amazon.com/dp/B09V3KXJPB") == "B09V3KXJPB"
        assert self.handler.extract_asin("https://www.amazon.com/gp/aw/d/B09V3KXJPB") == "B09V3KXJPB"
        assert self.handler.extract_asin("https://www.amazon.com/s?k=test") is None

    def test_convert_preserves_domain(self):
        result = self.handler.convert("https://www.amazon.de/dp/B09V3KXJPB")
        assert result.success
        assert "amazon.de" in result.affiliate_url

    def test_commission_rates_exist(self):
        assert len(self.handler.commission_rates) > 0
        assert "Default" in self.handler.commission_rates


class TestShopeeHandler:
    def setup_method(self):
        self.handler = ShopeeHandler(aff_id="test_shopee")

    def test_matches_shopee_sg(self):
        assert self.handler.matches("https://shopee.sg/product/123/456")

    def test_matches_shopee_vn(self):
        assert self.handler.matches("https://shopee.vn/product/123/456")

    def test_matches_shopee_tw(self):
        assert self.handler.matches("https://shopee.tw/product/123/456")

    def test_no_match(self):
        assert not self.handler.matches("https://www.ebay.com")

    def test_convert_with_product_id(self):
        result = self.handler.convert("https://shopee.sg/product/123/456")
        assert result.success
        assert "aff_id=test_shopee" in result.affiliate_url
        assert result.product_id == "123.456"

    def test_convert_i_dot_format(self):
        result = self.handler.convert("https://shopee.sg/i.123.456")
        assert result.success
        assert result.product_id == "123.456"

    def test_convert_no_aff_id(self):
        handler = ShopeeHandler(aff_id="")
        result = handler.convert("https://shopee.sg/product/123/456")
        assert not result.success

    def test_convert_no_product_pattern(self):
        result = self.handler.convert("https://shopee.sg/search?q=phone")
        assert result.success  # Still wraps URL even without product ID
        assert result.product_id is None


class TestLazadaHandler:
    def setup_method(self):
        self.handler = LazadaHandler(aff_id="test_lazada")

    def test_matches_lazada_sg(self):
        assert self.handler.matches("https://www.lazada.sg/products/test-i123456.html")

    def test_matches_lazada_ph(self):
        assert self.handler.matches("https://www.lazada.com.ph/products/test.html")

    def test_convert_with_product_id(self):
        result = self.handler.convert("https://www.lazada.sg/products/test-i123456.html")
        assert result.success
        assert "test_lazada" in result.affiliate_url
        assert result.product_id == "123456"

    def test_convert_no_aff_id(self):
        handler = LazadaHandler(aff_id="")
        result = handler.convert("https://www.lazada.sg/products/test.html")
        assert not result.success

    def test_convert_no_product_pattern(self):
        result = self.handler.convert("https://www.lazada.sg/catalog/?q=phone")
        assert result.success
        assert result.product_id is None


class TestAliExpressHandler:
    def setup_method(self):
        self.handler = AliExpressHandler(aff_id="test_ali")

    def test_matches_aliexpress(self):
        assert self.handler.matches("https://www.aliexpress.com/item/1234567890.html")

    def test_matches_aliexpress_ru(self):
        assert self.handler.matches("https://aliexpress.ru/item/1234567890.html")

    def test_matches_short_url(self):
        assert self.handler.matches("https://s.click.aliexpress.com/e/abc123")

    def test_convert_standard(self):
        result = self.handler.convert("https://www.aliexpress.com/item/1234567890.html")
        assert result.success
        assert "test_ali" in result.affiliate_url
        assert result.product_id == "1234567890"

    def test_convert_no_aff_id(self):
        handler = AliExpressHandler(aff_id="")
        result = handler.convert("https://www.aliexpress.com/item/1234567890.html")
        assert not result.success

    def test_convert_numeric_id(self):
        result = self.handler.convert("https://www.aliexpress.com/1234567890123")
        assert result.success


class TestTikTokHandler:
    def setup_method(self):
        self.handler = TikTokHandler(aff_id="test_tiktok")

    def test_matches_shop(self):
        assert self.handler.matches("https://shop.tiktok.com/view/product/123")

    def test_matches_tiktokshop(self):
        assert self.handler.matches("https://tiktokshop.com/product/123")

    def test_no_match(self):
        assert not self.handler.matches("https://www.tiktok.com/@user/video/123")

    def test_convert(self):
        result = self.handler.convert("https://shop.tiktok.com/view/product/123")
        assert result.success
        assert "aff_id=test_tiktok" in result.affiliate_url

    def test_convert_with_existing_params(self):
        result = self.handler.convert("https://shop.tiktok.com/view/product/123?region=US")
        assert result.success
        assert "&aff_id=" in result.affiliate_url

    def test_convert_no_aff_id(self):
        handler = TikTokHandler(aff_id="")
        result = handler.convert("https://shop.tiktok.com/view/product/123")
        assert not result.success


class TestConversionResult:
    def test_success(self):
        r = ConversionResult(platform="amazon", original_url="url", affiliate_url="aff")
        assert r.success

    def test_failure(self):
        r = ConversionResult(platform="amazon", original_url="url", error="bad")
        assert not r.success

    def test_with_product_id(self):
        r = ConversionResult(platform="amazon", original_url="url", affiliate_url="aff", product_id="B123")
        assert r.product_id == "B123"
