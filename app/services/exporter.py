"""
Export stats to CSV and JSON formats.
"""

import csv
import json
import io

from .database import Database


class StatsExporter:
    """Export conversion statistics in various formats."""

    def __init__(self, db: Database):
        self.db = db

    def to_csv(self, days: int = 30) -> str:
        """Export conversions as CSV string."""
        data = self.db.export_conversions(days)
        if not data:
            return ""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "platform", "user_id", "username", "chat_id", "chat_title",
            "original_url", "affiliate_url", "product_id", "created_at",
        ])
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue()

    def to_json(self, days: int = 30) -> str:
        """Export conversions as JSON string."""
        data = self.db.export_conversions(days)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def summary_report(self) -> str:
        """Generate a comprehensive text summary report."""
        stats = self.db.get_total_stats()
        top_users = self.db.get_top_users(5)
        daily = self.db.get_daily_stats(7)
        groups = self.db.get_group_stats()

        EMOJI = {
            "amazon": "🛒", "shopee": "🧡", "lazada": "💜",
            "aliexpress": "🔴", "tiktok": "🎵",
        }

        lines = [
            "📊 联盟转换报告",
            f"{'='*30}",
            "",
            f"🔗 总转换: {stats['total']}",
            f"📅 今日: {stats['today']}",
            f"📆 本周: {stats['this_week']}",
            "",
        ]

        # Platform breakdown
        if stats["by_platform"]:
            lines.append("📦 平台分布:")
            for p, c in stats["by_platform"].items():
                emoji = EMOJI.get(p, "📌")
                pct = c / stats["total"] * 100 if stats["total"] > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"  {emoji} {p}: {c} ({pct:.1f}%) {bar}")
            lines.append("")

        # Top users
        if top_users:
            lines.append("👥 活跃用户 Top 5:")
            for i, u in enumerate(top_users, 1):
                lines.append(f"  {i}. {u['username']}: {u['total_conversions']} 次")
            lines.append("")

        # Daily trend
        if daily:
            lines.append("📈 近7天趋势:")
            max_cnt = max(d["cnt"] for d in daily) if daily else 1
            for d in daily:
                bar_len = int(d["cnt"] / max(max_cnt, 1) * 15)
                bar = "▓" * bar_len
                lines.append(f"  {d['day']}: {bar} {d['cnt']}")
            lines.append("")

        # Group stats
        if groups:
            lines.append("💬 群组统计:")
            for g in groups[:5]:
                status = "✅" if g.get("is_enabled") else "🚫"
                title = g.get("chat_title", "Unknown")
                lines.append(f"  {status} {title}: {g['total_conversions']} 次")

        return "\n".join(lines)

    def user_report(self, user_id: int) -> str:
        """Generate report for a specific user."""
        stats = self.db.get_user_stats(user_id)
        if not stats:
            return "📊 你还没有转换过链接"

        EMOJI = {
            "amazon": "🛒", "shopee": "🧡", "lazada": "💜",
            "aliexpress": "🔴", "tiktok": "🎵",
        }

        lines = [
            f"📊 {stats['username']} 的统计",
            "",
            f"🔗 总转换: {stats['total_conversions']} 次",
            f"📅 首次使用: {stats.get('first_seen', 'N/A')[:10]}",
            f"🕐 最近使用: {stats.get('last_seen', 'N/A')[:10]}",
        ]

        if stats.get("by_platform"):
            lines.append("")
            lines.append("📦 平台分布:")
            for p, c in sorted(stats["by_platform"].items(), key=lambda x: -x[1]):
                emoji = EMOJI.get(p, "📌")
                lines.append(f"  {emoji} {p}: {c} 次")

        return "\n".join(lines)
