"""
Click tracking & analytics module.
Stores conversion stats in JSON (file-based) or Redis when available.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
STATS_FILE = DATA_DIR / "stats.json"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_stats() -> dict:
    _ensure_dir()
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"total": 0, "by_platform": {}, "by_user": {}, "daily": {}, "links": []}


def _save_stats(data: dict):
    _ensure_dir()
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_conversion(platform: str, user_id: int, username: str, original_url: str, affiliate_url: str):
    """Record a link conversion event."""
    stats = _load_stats()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    stats["total"] += 1
    stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

    uid = str(user_id)
    if uid not in stats["by_user"]:
        stats["by_user"][uid] = {"name": username, "count": 0}
    stats["by_user"][uid]["count"] += 1
    stats["by_user"][uid]["name"] = username

    stats["daily"][today] = stats["daily"].get(today, 0) + 1

    # Keep last 1000 links
    stats["links"].append({
        "platform": platform,
        "user": username,
        "original": original_url[:200],
        "affiliate": affiliate_url[:200],
        "time": now.isoformat(),
    })
    if len(stats["links"]) > 1000:
        stats["links"] = stats["links"][-1000:]

    _save_stats(stats)


def get_stats_summary() -> str:
    """Generate a formatted stats summary."""
    stats = _load_stats()
    if stats["total"] == 0:
        return "📊 暂无统计数据"

    EMOJI = {
        "amazon": "🛒", "shopee": "🧡", "lazada": "💜",
        "aliexpress": "🔴", "tiktok": "🎵",
    }

    lines = [f"📊 转换统计\n\n🔗 总计: {stats['total']} 次\n"]

    # Platform breakdown
    lines.append("📦 平台分布:")
    for p, c in sorted(stats["by_platform"].items(), key=lambda x: -x[1]):
        emoji = EMOJI.get(p, "📌")
        pct = c / stats["total"] * 100
        lines.append(f"  {emoji} {p}: {c} 次 ({pct:.0f}%)")

    # Top users
    if stats["by_user"]:
        lines.append("\n👥 活跃用户 Top 5:")
        top_users = sorted(stats["by_user"].items(), key=lambda x: -x[1]["count"])[:5]
        for i, (uid, info) in enumerate(top_users, 1):
            lines.append(f"  {i}. {info['name']}: {info['count']} 次")

    # Recent daily
    if stats["daily"]:
        lines.append("\n📅 近7天:")
        recent = sorted(stats["daily"].items())[-7:]
        for day, count in recent:
            lines.append(f"  {day}: {count} 次")

    return "\n".join(lines)


def get_user_stats(user_id: int) -> str:
    """Get stats for a specific user."""
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats["by_user"]:
        return "📊 你还没有转换过链接"

    info = stats["by_user"][uid]
    return f"📊 你的统计\n\n🔗 总转换: {info['count']} 次"
