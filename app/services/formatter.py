"""
Message formatter for multi-language support.
Supports Chinese (zh) and English (en).
"""

from typing import Optional


STRINGS = {
    "zh": {
        "affiliate_link_single": "🔗 联盟链接:",
        "affiliate_link_multi": "🔗 联盟链接 ({count}个):",
        "commission_hint": "💰 预估佣金: {rate}",
        "error_rate_limited": "⚠️ 操作太频繁，请 {seconds:.0f} 秒后再试",
        "error_blocked": "🚫 你已被封禁",
        "error_group_disabled": "🚫 本群已禁用链接转换",
        "no_stats": "📊 暂无统计数据",
        "no_user_stats": "📊 你还没有转换过链接",
        "start_greeting": (
            "👋 多平台联盟链接机器人\n\n"
            "📌 发送任意电商平台的产品链接，自动转换为联盟推广链接。\n\n"
            "✅ 已启用平台:\n{platforms}\n\n"
            "支持: Amazon / Shopee / Lazada / AliExpress / TikTok Shop\n"
            "发送 /help 查看详情 | /stats 查看统计 | /mystats 个人统计"
        ),
        "help_text": (
            "📖 使用帮助\n\n"
            "直接发送产品链接即可，支持:\n"
            "🛒 Amazon — 全球站点 + 短链(amzn.to/a.co)\n"
            "🧡 Shopee — 东南亚/台湾/巴西/墨西哥\n"
            "💜 Lazada — 东南亚6国\n"
            "🔴 AliExpress — 全球\n"
            "🎵 TikTok Shop — 全球\n\n"
            "💡 一条消息可包含多个链接（最多{max_links}个），自动识别平台。\n"
            "💡 支持私聊和群聊。\n\n"
            "📊 命令:\n"
            "/stats — 总统计\n"
            "/mystats — 个人统计\n"
            "/report — 详细报告\n"
            "/export — 导出数据 (CSV)\n"
            "/commission — 佣金费率表"
        ),
        "commission_table_header": "💰 各平台佣金费率参考\n",
        "export_empty": "📭 暂无可导出的数据",
        "export_header": "📁 最近{days}天的转换数据",
    },
    "en": {
        "affiliate_link_single": "🔗 Affiliate Link:",
        "affiliate_link_multi": "🔗 Affiliate Links ({count}):",
        "commission_hint": "💰 Est. Commission: {rate}",
        "error_rate_limited": "⚠️ Too many requests, retry in {seconds:.0f}s",
        "error_blocked": "🚫 You are blocked",
        "error_group_disabled": "🚫 Link conversion disabled in this group",
        "no_stats": "📊 No stats yet",
        "no_user_stats": "📊 You haven't converted any links yet",
        "start_greeting": (
            "👋 Multi-Platform Affiliate Bot\n\n"
            "📌 Send any product link to auto-convert to affiliate links.\n\n"
            "✅ Active Platforms:\n{platforms}\n\n"
            "Supports: Amazon / Shopee / Lazada / AliExpress / TikTok Shop\n"
            "/help for details | /stats for analytics | /mystats personal"
        ),
        "help_text": (
            "📖 Help\n\n"
            "Just send a product link. Supported:\n"
            "🛒 Amazon — Global + short links\n"
            "🧡 Shopee — SEA/Taiwan/Brazil/Mexico\n"
            "💜 Lazada — 6 SEA countries\n"
            "🔴 AliExpress — Global\n"
            "🎵 TikTok Shop — Global\n\n"
            "💡 Up to {max_links} links per message.\n"
            "💡 Works in private and group chats.\n\n"
            "📊 Commands:\n"
            "/stats — Overall stats\n"
            "/mystats — Personal stats\n"
            "/report — Detailed report\n"
            "/export — Export data (CSV)\n"
            "/commission — Commission rates"
        ),
        "commission_table_header": "💰 Commission Rate Reference\n",
        "export_empty": "📭 No data to export",
        "export_header": "📁 Conversion data (last {days} days)",
    },
}


class MessageFormatter:
    """Format bot messages with i18n support."""

    def __init__(self, lang: str = "zh"):
        self.lang = lang if lang in STRINGS else "zh"

    def get(self, key: str, **kwargs) -> str:
        """Get a localized string."""
        template = STRINGS[self.lang].get(key, STRINGS["zh"].get(key, key))
        if kwargs:
            return template.format(**kwargs)
        return template

    def format_results(self, results: list, show_commission: bool = True) -> Optional[str]:
        """Format conversion results into a reply message."""
        if not results:
            return None

        parts = []
        for r in results:
            if r.success:
                line = f"{r.platform_emoji if hasattr(r, 'platform_emoji') else '📌'} {r.affiliate_url}"
                if show_commission and r.estimated_commission:
                    line += f"\n  💰 ~{r.estimated_commission}"
                parts.append(line)
            elif r.error:
                parts.append(f"⚠️ {r.error}")

        if not parts:
            return None

        if len(parts) == 1:
            header = self.get("affiliate_link_single")
        else:
            header = self.get("affiliate_link_multi", count=len(parts))

        return header + "\n\n" + "\n\n".join(parts)

    def format_commission_table(self, handlers: list) -> str:
        """Format commission rates for all platforms."""
        lines = [self.get("commission_table_header")]
        for handler in handlers:
            if handler.commission_rates:
                lines.append(f"\n{handler.emoji} {handler.name.upper()}")
                for category, rate in handler.commission_rates.items():
                    lines.append(f"  • {category}: {rate}")
        return "\n".join(lines)
