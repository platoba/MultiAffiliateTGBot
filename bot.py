"""
Multi-Platform Affiliate Telegram Bot
支持 Amazon / Shopee / Lazada / AliExpress / TikTok Shop
自动将产品链接转换为联盟推广链接
"""

import re
import os
import time
import json
import requests
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

# ============================================================
# 配置
# ============================================================
TOKEN = os.environ.get("BOT_TOKEN", "")
DEV_CHAT_ID = os.environ.get("DEV_CHAT_ID", "")

# 各平台联盟标签
AMAZON_TAG = os.environ.get("AMAZON_TAG", "")
AMAZON_DOMAIN = os.environ.get("AMAZON_DOMAIN", "amazon.com")
SHOPEE_AFF_ID = os.environ.get("SHOPEE_AFF_ID", "")
LAZADA_AFF_ID = os.environ.get("LAZADA_AFF_ID", "")
ALIEXPRESS_AFF_ID = os.environ.get("ALIEXPRESS_AFF_ID", "")
TIKTOK_AFF_ID = os.environ.get("TIKTOK_AFF_ID", "")

if not TOKEN:
    raise ValueError("未设置 BOT_TOKEN!")

API_URL = f"https://api.telegram.org/bot{TOKEN}"

# ============================================================
# 平台检测正则
# ============================================================
AMAZON_DOMAINS = [
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it",
    "amazon.es", "amazon.co.jp", "amazon.ca", "amazon.com.au", "amazon.in",
    "amazon.com.br", "amazon.com.mx", "amazon.sg", "amazon.ae", "amazon.sa",
    "amazon.nl", "amazon.pl", "amazon.se", "amazon.com.tr", "amazon.eg",
]
AMAZON_SHORT = ["amzn.to", "amzn.eu", "amzn.asia", "a.co"]
ASIN_PATTERN = re.compile(r"(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")

SHOPEE_DOMAINS = [
    "shopee.sg", "shopee.co.th", "shopee.vn", "shopee.ph",
    "shopee.com.my", "shopee.co.id", "shopee.com.br", "shopee.tw",
    "shopee.com.mx", "shopee.com.co", "shopee.cl", "shopee.pl",
]
SHOPEE_PATTERN = re.compile(r"(?:product/|i\.)(\d+)\.(\d+)")

LAZADA_DOMAINS = [
    "lazada.sg", "lazada.com.my", "lazada.co.th", "lazada.vn",
    "lazada.co.id", "lazada.com.ph",
]
LAZADA_PATTERN = re.compile(r"-i(\d+)(?:-s\d+)?\.html")

ALIEXPRESS_DOMAINS = ["aliexpress.com", "aliexpress.ru", "aliexpress.us"]
ALIEXPRESS_SHORT = ["s.click.aliexpress.com", "a.aliexpress.com"]
ALIEXPRESS_PATTERN = re.compile(r"item/(\d+)\.html|/(\d{8,15})")

TIKTOK_SHOP_DOMAINS = ["shop.tiktok.com", "tiktokshop.com"]

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


# ============================================================
# Telegram API
# ============================================================
def tg_get(method, params=None):
    try:
        r = requests.get(f"{API_URL}/{method}", params=params, timeout=35)
        return r.json()
    except Exception as e:
        print(f"[API错误] {method}: {e}")
        return None


def tg_send(chat_id, text, reply_to=None, parse_mode=None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_to:
        params["reply_to_message_id"] = reply_to
    if parse_mode:
        params["parse_mode"] = parse_mode
    return tg_get("sendMessage", params)


def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return tg_get("getUpdates", params)


# ============================================================
# URL工具
# ============================================================
def expand_short_url(url):
    """展开短链接"""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.head(url, allow_redirects=True, timeout=10)
        return r.url
    except Exception as e:
        print(f"[错误] 展开短链接失败: {url} | {e}")
        return ""


def detect_platform(url):
    """检测URL属于哪个平台"""
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    if any(d in host for d in AMAZON_DOMAINS) or any(d in host for d in AMAZON_SHORT):
        return "amazon"
    if any(d in host for d in SHOPEE_DOMAINS):
        return "shopee"
    if any(d in host for d in LAZADA_DOMAINS):
        return "lazada"
    if any(d in host for d in ALIEXPRESS_DOMAINS) or any(d in host for d in ALIEXPRESS_SHORT):
        return "aliexpress"
    if any(d in host for d in TIKTOK_SHOP_DOMAINS):
        return "tiktok"
    return None


# ============================================================
# 各平台联盟链接生成
# ============================================================
def make_amazon_affiliate(url):
    """Amazon: 提取ASIN，生成带tag的链接"""
    if not AMAZON_TAG:
        return None, "⚠️ 未配置 AMAZON_TAG"

    # 展开短链
    for domain in AMAZON_SHORT:
        if domain in url:
            expanded = expand_short_url(url)
            if expanded:
                url = expanded
            else:
                return None, "⚠️ Amazon短链接展开失败"
            break

    match = ASIN_PATTERN.search(url)
    if match:
        asin = match.group(1)
        domain = AMAZON_DOMAIN.replace("www.", "")
        return f"https://www.{domain}/dp/{asin}?tag={AMAZON_TAG}", None
    return None, "⚠️ 无法提取Amazon ASIN"


def make_shopee_affiliate(url):
    """Shopee: 通过联盟平台生成追踪链接"""
    if not SHOPEE_AFF_ID:
        return None, "⚠️ 未配置 SHOPEE_AFF_ID"

    match = SHOPEE_PATTERN.search(url)
    if match:
        # Shopee联盟链接格式
        parsed = urlparse(url)
        aff_url = f"https://shope.ee/aff?aff_id={SHOPEE_AFF_ID}&url={requests.utils.quote(url)}"
        return aff_url, None
    # 即使没匹配到product pattern，也尝试包装
    aff_url = f"https://shope.ee/aff?aff_id={SHOPEE_AFF_ID}&url={requests.utils.quote(url)}"
    return aff_url, None


def make_lazada_affiliate(url):
    """Lazada: 通过联盟平台生成追踪链接"""
    if not LAZADA_AFF_ID:
        return None, "⚠️ 未配置 LAZADA_AFF_ID"

    aff_url = f"https://c.lazada.com/t/c.{LAZADA_AFF_ID}?url={requests.utils.quote(url)}"
    return aff_url, None


def make_aliexpress_affiliate(url):
    """AliExpress: 通过联盟平台生成追踪链接"""
    if not ALIEXPRESS_AFF_ID:
        return None, "⚠️ 未配置 ALIEXPRESS_AFF_ID"

    # 展开短链
    for domain in ALIEXPRESS_SHORT:
        if domain in url:
            expanded = expand_short_url(url)
            if expanded:
                url = expanded
            break

    aff_url = f"https://s.click.aliexpress.com/e/{ALIEXPRESS_AFF_ID}?url={requests.utils.quote(url)}"
    return aff_url, None


def make_tiktok_affiliate(url):
    """TikTok Shop: 通过联盟平台生成追踪链接"""
    if not TIKTOK_AFF_ID:
        return None, "⚠️ 未配置 TIKTOK_AFF_ID"

    aff_url = f"{url}{'&' if '?' in url else '?'}aff_id={TIKTOK_AFF_ID}"
    return aff_url, None


PLATFORM_HANDLERS = {
    "amazon": ("🛒 Amazon", make_amazon_affiliate),
    "shopee": ("🧡 Shopee", make_shopee_affiliate),
    "lazada": ("💜 Lazada", make_lazada_affiliate),
    "aliexpress": ("🔴 AliExpress", make_aliexpress_affiliate),
    "tiktok": ("🎵 TikTok Shop", make_tiktok_affiliate),
}

PLATFORM_EMOJI = {
    "amazon": "🛒",
    "shopee": "🧡",
    "lazada": "💜",
    "aliexpress": "🔴",
    "tiktok": "🎵",
}


# ============================================================
# 消息处理
# ============================================================
def process_message(text):
    """处理消息，返回回复内容"""
    if not text:
        return None

    urls = URL_PATTERN.findall(text)
    if not urls:
        return None

    results = []
    for url in urls:
        platform = detect_platform(url)
        if not platform:
            continue

        emoji, handler = PLATFORM_HANDLERS[platform]
        aff_url, error = handler(url)
        if aff_url:
            results.append(f"{emoji} {aff_url}")
        elif error:
            results.append(f"{emoji} {error}")

    if not results:
        return None

    header = f"🔗 联盟链接 ({len(results)}个):\n\n" if len(results) > 1 else "🔗 联盟链接:\n\n"
    return header + "\n\n".join(results)


# ============================================================
# 统计
# ============================================================
stats = {"total": 0, "by_platform": {}}


def record_stat(platform):
    stats["total"] += 1
    stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1


# ============================================================
# 主循环
# ============================================================
def main():
    platforms = []
    if AMAZON_TAG:
        platforms.append(f"Amazon ({AMAZON_TAG})")
    if SHOPEE_AFF_ID:
        platforms.append(f"Shopee ({SHOPEE_AFF_ID})")
    if LAZADA_AFF_ID:
        platforms.append(f"Lazada ({LAZADA_AFF_ID})")
    if ALIEXPRESS_AFF_ID:
        platforms.append(f"AliExpress ({ALIEXPRESS_AFF_ID})")
    if TIKTOK_AFF_ID:
        platforms.append(f"TikTok ({TIKTOK_AFF_ID})")

    print(f"\n{'='*50}")
    print(f"  Multi-Platform Affiliate Telegram Bot")
    print(f"  已启用平台: {', '.join(platforms) if platforms else '无 (请配置环境变量)'}")
    print(f"{'='*50}")

    me = tg_get("getMe")
    if me and me.get("ok"):
        bot_name = me["result"]["username"]
        print(f"\n✅ @{bot_name} 已上线!")
        print(f"🤖 等待消息... Ctrl+C 停止\n")
    else:
        print("\n❌ 无法连接Telegram! 检查Token和网络。")
        return

    offset = None

    while True:
        try:
            result = get_updates(offset)
            if not result or not result.get("ok"):
                time.sleep(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                msg_id = msg.get("message_id")
                text = msg.get("text", "")
                user = msg.get("from", {}).get("first_name", "?")

                if text == "/start":
                    active = "\n".join(f"  • {p}" for p in platforms) if platforms else "  ⚠️ 未配置任何平台"
                    tg_send(chat_id,
                        f"👋 多平台联盟链接机器人\n\n"
                        f"📌 发送任意电商平台的产品链接，自动转换为联盟推广链接。\n\n"
                        f"✅ 已启用平台:\n{active}\n\n"
                        f"支持: Amazon / Shopee / Lazada / AliExpress / TikTok Shop\n"
                        f"发送 /help 查看详情 | /stats 查看统计",
                        msg_id)

                elif text == "/help":
                    tg_send(chat_id,
                        f"📖 使用帮助\n\n"
                        f"直接发送产品链接即可，支持:\n"
                        f"🛒 Amazon — 全球站点 + 短链(amzn.to/a.co)\n"
                        f"🧡 Shopee — 东南亚/台湾/巴西/墨西哥\n"
                        f"💜 Lazada — 东南亚6国\n"
                        f"🔴 AliExpress — 全球\n"
                        f"🎵 TikTok Shop — 全球\n\n"
                        f"💡 一条消息可包含多个链接，自动识别平台。\n"
                        f"💡 支持私聊和群聊。",
                        msg_id)

                elif text == "/stats":
                    if stats["total"] == 0:
                        tg_send(chat_id, "📊 暂无统计数据", msg_id)
                    else:
                        lines = [f"📊 转换统计\n\n总计: {stats['total']} 次\n"]
                        for p, c in sorted(stats["by_platform"].items(), key=lambda x: -x[1]):
                            emoji = PLATFORM_EMOJI.get(p, "")
                            lines.append(f"{emoji} {p}: {c} 次")
                        tg_send(chat_id, "\n".join(lines), msg_id)

                elif text and not text.startswith("/"):
                    reply = process_message(text)
                    if reply:
                        # 记录统计
                        for url in URL_PATTERN.findall(text):
                            p = detect_platform(url)
                            if p:
                                record_stat(p)
                        tg_send(chat_id, reply, msg_id)
                        print(f"[转换] {user}: {len(URL_PATTERN.findall(text))}个链接")

        except KeyboardInterrupt:
            print("\n\n👋 已停止!")
            break
        except Exception as e:
            print(f"[错误] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
