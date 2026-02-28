"""Tests for stats exporter."""

import pytest


class TestStatsExporter:
    def test_to_csv_empty(self, exporter):
        csv = exporter.to_csv()
        assert csv == ""

    def test_to_csv_with_data(self, exporter, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url1", "aff1")
        tmp_db.record_conversion("shopee", 2, "User2", 0, "", "url2", "aff2")
        csv = exporter.to_csv()
        assert "platform" in csv  # Header
        assert "amazon" in csv
        assert "shopee" in csv

    def test_to_json_empty(self, exporter):
        j = exporter.to_json()
        assert j == "[]"

    def test_to_json_with_data(self, exporter, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff")
        j = exporter.to_json()
        assert "amazon" in j
        assert "url" in j

    def test_summary_report_empty(self, exporter):
        report = exporter.summary_report()
        assert "总转换: 0" in report

    def test_summary_report_with_data(self, exporter, tmp_db):
        for i in range(5):
            tmp_db.record_conversion("amazon", 1, "PowerUser", 0, "", f"url{i}", f"aff{i}")
        tmp_db.record_conversion("shopee", 2, "User2", -100, "TestGroup", "url", "aff")
        report = exporter.summary_report()
        assert "总转换: 6" in report
        assert "amazon" in report
        assert "PowerUser" in report

    def test_user_report_empty(self, exporter):
        report = exporter.user_report(999)
        assert "还没有" in report

    def test_user_report_with_data(self, exporter, tmp_db):
        tmp_db.record_conversion("amazon", 42, "TestUser", 0, "", "url", "aff")
        report = exporter.user_report(42)
        assert "TestUser" in report
        assert "总转换: 1" in report

    def test_csv_days_filter(self, exporter, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff")
        csv_30 = exporter.to_csv(days=30)
        csv_0 = exporter.to_csv(days=0)
        assert len(csv_30) >= len(csv_0)
