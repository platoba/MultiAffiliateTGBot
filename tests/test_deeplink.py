"""Tests for deep link generator."""

import pytest
from app.services.deeplink import (
    DeepLinkGenerator,
    DeepLinkResult,
    UTMParams,
    APP_SCHEMES,
    REGION_MAP,
)


@pytest.fixture
def generator():
    return DeepLinkGenerator(base_domain="test.link", default_utm_source="telegram")


class TestUTMParams:
    def test_to_dict_full(self):
        utm = UTMParams(source="tg", medium="affiliate", campaign="test", term="kw", content="v1")
        d = utm.to_dict()
        assert d["utm_source"] == "tg"
        assert d["utm_medium"] == "affiliate"
        assert d["utm_campaign"] == "test"
        assert d["utm_term"] == "kw"
        assert d["utm_content"] == "v1"

    def test_to_dict_partial(self):
        utm = UTMParams(source="tg", medium="affiliate")
        d = utm.to_dict()
        assert "utm_source" in d
        assert "utm_medium" in d
        assert "utm_campaign" not in d
        assert "utm_term" not in d

    def test_to_dict_empty(self):
        utm = UTMParams(source="", medium="")
        assert utm.to_dict() == {}

    def test_is_valid(self):
        assert UTMParams(source="tg", medium="aff").is_valid()
        # Default medium is "affiliate", so source-only is valid
        assert UTMParams(source="tg").is_valid()
        assert not UTMParams(source="", medium="aff").is_valid()
        assert not UTMParams(source="", medium="").is_valid()


class TestDeepLinkResult:
    def test_has_app_link(self):
        r = DeepLinkResult(web_url="https://test.com", app_url="app://test")
        assert r.has_app_link

    def test_no_app_link(self):
        r = DeepLinkResult(web_url="https://test.com")
        assert not r.has_app_link

    def test_to_dict(self):
        r = DeepLinkResult(
            web_url="https://test.com",
            app_url="app://test",
            tracking_id="abc123",
            platform="amazon",
            region="US",
            short_code="xyzw",
        )
        d = r.to_dict()
        assert d["web_url"] == "https://test.com"
        assert d["app_url"] == "app://test"
        assert d["tracking_id"] == "abc123"
        assert d["platform"] == "amazon"
        assert d["region"] == "US"
        assert d["short_code"] == "xyzw"


class TestDeepLinkGenerator:
    def test_generate_basic(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            product_id="B08N5WRWNW",
        )
        assert isinstance(result, DeepLinkResult)
        assert "utm_source=telegram" in result.web_url
        assert result.platform == "amazon"
        assert result.tracking_id
        assert result.short_code

    def test_generate_empty_url_raises(self, generator):
        with pytest.raises(ValueError):
            generator.generate(url="", platform="amazon")

    def test_generate_with_custom_utm(self, generator):
        utm = UTMParams(source="email", medium="newsletter", campaign="summer2026")
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            utm=utm,
        )
        assert "utm_source=email" in result.web_url
        assert "utm_medium=newsletter" in result.web_url
        assert "utm_campaign=summer2026" in result.web_url

    def test_generate_with_app_link(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            product_id="B08N5WRWNW",
            include_app_link=True,
        )
        assert result.app_url is not None
        assert result.fallback_url is not None

    def test_generate_without_app_link(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            include_app_link=False,
        )
        assert result.app_url is None

    def test_generate_with_qr(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            include_qr=True,
        )
        assert result.qr_data is not None
        assert "test.link" in result.qr_data

    def test_generate_without_qr(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            include_qr=False,
        )
        assert result.qr_data is None

    def test_generate_unknown_platform(self, generator):
        result = generator.generate(
            url="https://unknown.com/product/123",
            platform="unknown",
        )
        assert result.app_url is None
        assert result.web_url is not None

    def test_region_detection_us(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
        )
        assert result.region == "US"

    def test_region_detection_uk(self, generator):
        result = generator.generate(
            url="https://www.amazon.co.uk/dp/B08N5WRWNW",
            platform="amazon",
        )
        assert result.region == "UK"

    def test_region_detection_jp(self, generator):
        result = generator.generate(
            url="https://www.amazon.co.jp/dp/B08N5WRWNW",
            platform="amazon",
        )
        assert result.region == "JP"

    def test_region_detection_de(self, generator):
        result = generator.generate(
            url="https://www.amazon.de/dp/B08N5WRWNW",
            platform="amazon",
        )
        assert result.region == "DE"

    def test_region_detection_shopee_sg(self, generator):
        result = generator.generate(
            url="https://shopee.sg/product/123/456",
            platform="shopee",
        )
        assert result.region == "SG"

    def test_region_detection_global(self, generator):
        result = generator.generate(
            url="https://www.aliexpress.ru/item/123.html",
            platform="aliexpress",
        )
        assert result.region == "GLOBAL"

    def test_campaign_name_in_utm(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            campaign_name="black_friday_2026",
        )
        assert "utm_campaign=black_friday_2026" in result.web_url

    def test_auto_campaign_name(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
        )
        assert "utm_campaign=amazon_us" in result.web_url

    def test_tracking_id_unique(self, generator):
        r1 = generator.generate(url="https://a.com/1", platform="amazon")
        r2 = generator.generate(url="https://a.com/2", platform="amazon")
        assert r1.tracking_id != r2.tracking_id

    def test_short_code_generated(self, generator):
        result = generator.generate(url="https://a.com/1", platform="amazon")
        assert len(result.short_code) == 8

    def test_utm_preserves_existing_params(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW?ref=test",
            platform="amazon",
        )
        assert "ref=test" in result.web_url
        assert "utm_source=telegram" in result.web_url


class TestBatchGeneration:
    def test_generate_batch(self, generator):
        urls = [
            {"url": "https://www.amazon.com/dp/B08N5WRWNW", "platform": "amazon", "product_id": "B08N5WRWNW"},
            {"url": "https://shopee.sg/product/123/456", "platform": "shopee"},
        ]
        results = generator.generate_batch(urls, campaign_name="test_batch")
        assert len(results) == 2
        assert results[0].platform == "amazon"
        assert results[1].platform == "shopee"

    def test_batch_skips_invalid(self, generator):
        urls = [
            {"url": "", "platform": "amazon"},  # Invalid
            {"url": "https://a.com/1", "platform": "amazon"},  # Valid
        ]
        results = generator.generate_batch(urls)
        assert len(results) == 1

    def test_batch_empty(self, generator):
        assert generator.generate_batch([]) == []


class TestRedirectAndComparison:
    def test_build_redirect_url(self, generator):
        url = generator.build_redirect_url("abc123", "https://amazon.com/dp/B123")
        assert "test.link" in url
        assert "abc123" in url

    def test_build_comparison_link(self, generator):
        result = generator.build_comparison_link("B08N5WRWNW", ["amazon", "aliexpress"])
        assert "amazon" in result
        assert "aliexpress" in result
        assert "app" in result["amazon"]
        assert "web" in result["amazon"]

    def test_comparison_unknown_platform(self, generator):
        result = generator.build_comparison_link("123", ["unknown"])
        assert result == {}


class TestProductIdExtraction:
    def test_amazon_dp(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://www.amazon.com/dp/B08N5WRWNW", "amazon"
        )
        assert pid == "B08N5WRWNW"

    def test_amazon_gp(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://www.amazon.com/gp/product/B08N5WRWNW", "amazon"
        )
        assert pid == "B08N5WRWNW"

    def test_shopee_product(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://shopee.sg/product/123/456", "shopee"
        )
        assert pid is not None

    def test_aliexpress_item(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://www.aliexpress.com/item/1005001234567.html", "aliexpress"
        )
        assert pid == "1005001234567"

    def test_lazada_product(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://www.lazada.sg/products/product-name-i12345.html", "lazada"
        )
        assert pid == "12345"

    def test_tiktok_product(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://shop.tiktok.com/view/product/123456", "tiktok"
        )
        assert pid == "123456"

    def test_unknown_platform(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://example.com/product/123", "unknown"
        )
        assert pid is None

    def test_no_match(self):
        pid = DeepLinkGenerator.extract_product_id(
            "https://www.amazon.com/", "amazon"
        )
        assert pid is None


class TestAppSchemes:
    def test_all_platforms_have_schemes(self):
        for platform in ["amazon", "shopee", "lazada", "aliexpress", "tiktok"]:
            assert platform in APP_SCHEMES
            assert "scheme" in APP_SCHEMES[platform]
            assert "intent" in APP_SCHEMES[platform]
            assert "universal" in APP_SCHEMES[platform]

    def test_region_map_coverage(self):
        assert len(REGION_MAP) > 15
        assert REGION_MAP["com"] == "US"
        assert REGION_MAP["co.uk"] == "UK"
        assert REGION_MAP["co.jp"] == "JP"


class TestAppLinkGeneration:
    def test_amazon_app_link(self, generator):
        result = generator.generate(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            platform="amazon",
            product_id="B08N5WRWNW",
        )
        assert result.app_url is not None
        assert "B08N5WRWNW" in result.app_url

    def test_shopee_app_link(self, generator):
        result = generator.generate(
            url="https://shopee.sg/product/123/456",
            platform="shopee",
            product_id="456",
        )
        assert result.app_url is not None

    def test_aliexpress_app_link(self, generator):
        result = generator.generate(
            url="https://www.aliexpress.com/item/123.html",
            platform="aliexpress",
            product_id="123",
        )
        assert result.app_url is not None
        assert "123" in result.app_url

    def test_no_app_link_for_unknown(self, generator):
        result = generator.generate(
            url="https://unknown.com/product/1",
            platform="unknown",
        )
        assert result.app_url is None
        assert result.fallback_url is None
