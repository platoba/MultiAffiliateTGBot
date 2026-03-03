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


# ============ 价格监控功能 ============
from app.services.price_monitor import PriceMonitor

price_monitor = PriceMonitor()


@bot.message_handler(commands=['watch'])
def handle_watch_command(message):
    """添加价格监控"""
    user_id = message.from_user.id
    
    # 检查是否在回复消息
    if not message.reply_to_message:
        bot.reply_to(message, "❌ 请回复包含产品链接的消息来添加价格监控")
        return
    
    # 从回复的消息中提取链接
    original_text = message.reply_to_message.text or ""
    urls = extract_urls(original_text)
    
    if not urls:
        bot.reply_to(message, "❌ 未找到产品链接")
        return
    
    # 只监控第一个链接
    url = urls[0]
    
    # 检测平台
    platform_handler = None
    for handler in platform_handlers:
        if handler.can_handle(url):
            platform_handler = handler
            break
    
    if not platform_handler:
        bot.reply_to(message, "❌ 不支持该平台的价格监控")
        return
    
    # 转换为联盟链接
    result = platform_handler.convert(url)
    
    if result.success:
        # 添加监控
        success = price_monitor.add_watch(
            user_id=user_id,
            product_url=url,
            affiliate_url=result.affiliate_url,
            platform=result.platform,
            product_title=result.product_title,
            notify_threshold=0.05  # 默认5%降价通知
        )
        
        if success:
            bot.reply_to(
                message,
                f"✅ 已添加价格监控\n\n"
                f"🏷️ {result.product_title or '产品'}\n"
                f"📊 平台: {result.platform_emoji} {result.platform}\n"
                f"🔔 降价5%时将通知您\n\n"
                f"使用 /mywatches 查看所有监控"
            )
        else:
            bot.reply_to(message, "❌ 添加监控失败，请稍后重试")
    else:
        bot.reply_to(message, f"❌ 链接转换失败: {result.error}")


@bot.message_handler(commands=['mywatches'])
def handle_mywatches_command(message):
    """查看我的价格监控"""
    user_id = message.from_user.id
    watches = price_monitor.get_user_watches(user_id)
    
    if not watches:
        bot.reply_to(message, "📭 您还没有添加任何价格监控\n\n使用 /watch 回复产品链接来添加监控")
        return
    
    response = "📊 您的价格监控列表:\n\n"
    
    for i, watch in enumerate(watches, 1):
        title = watch['product_title'] or '未知产品'
        platform = watch['platform']
        price = watch['current_price']
        original = watch['original_price']
        
        response += f"{i}. {title}\n"
        response += f"   平台: {platform}\n"
        
        if price and original:
            change = ((price - original) / original) * 100
            if change < 0:
                response += f"   价格: {price} {watch['currency']} (↓ {abs(change):.1f}%)\n"
            elif change > 0:
                response += f"   价格: {price} {watch['currency']} (↑ {change:.1f}%)\n"
            else:
                response += f"   价格: {price} {watch['currency']}\n"
        
        response += f"   ID: {watch['id']}\n\n"
    
    response += "使用 /unwatch <ID> 移除监控"
    
    bot.reply_to(message, response)


@bot.message_handler(commands=['unwatch'])
def handle_unwatch_command(message):
    """移除价格监控"""
    user_id = message.from_user.id
    
    # 解析命令参数
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ 请提供监控ID\n\n用法: /unwatch <ID>")
        return
    
    try:
        watch_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ 无效的监控ID")
        return
    
    # 移除监控
    success = price_monitor.remove_watch(user_id, watch_id)
    
    if success:
        bot.reply_to(message, f"✅ 已移除监控 #{watch_id}")
    else:
        bot.reply_to(message, f"❌ 移除失败，请检查ID是否正确")


def extract_urls(text):
    """从文本中提取URL"""
    import re
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)

# ============ 推荐引擎集成 ============
from app.recommendation_engine import RecommendationEngine

# 初始化推荐引擎
recommendation_engine = RecommendationEngine()

@bot.message_handler(commands=['recommend'])
def handle_recommend(message):
    """推荐产品命令"""
    user_id = message.from_user.id
    
    # 获取推荐统计
    stats = recommendation_engine.get_recommendation_stats(user_id)
    
    if not stats['has_enough_data']:
        bot.reply_to(message, 
            "🤖 推荐引擎需要更多数据\n"
            "Recommendation engine needs more data\n\n"
            f"当前交互次数 / Current interactions: {stats['total_interactions']}\n"
            "需要至少3次交互 / Need at least 3 interactions\n\n"
            "💡 发送更多产品链接来训练推荐系统\n"
            "Send more product links to train the system"
        )
        return
    
    # 获取推荐
    recommendations = recommendation_engine.recommend_products(user_id, limit=5)
    
    if not recommendations:
        bot.reply_to(message, 
            "😅 暂时没有推荐\n"
            "No recommendations available yet\n\n"
            "继续使用机器人，我们会学习你的偏好！\n"
            "Keep using the bot, we'll learn your preferences!"
        )
        return
    
    # 构建推荐消息
    response = "🎯 为你推荐 / Recommendations for you:\n\n"
    
    for i, rec in enumerate(recommendations, 1):
        platform_emoji = {
            'amazon': '🛒',
            'shopee': '🧡',
            'lazada': '💜',
            'aliexpress': '🔴',
            'tiktok': '🎵'
        }.get(rec['platform'], '🔗')
        
        reason_text = {
            'similar_users': '相似用户喜欢 / Similar users liked',
            'trending': '热门产品 / Trending'
        }.get(rec['reason'], '推荐 / Recommended')
        
        response += f"{i}. {platform_emoji} {rec['platform'].upper()}\n"
        response += f"   {rec['url']}\n"
        response += f"   📊 {reason_text} (score: {rec['score']})\n\n"
    
    response += f"💡 基于你的 {stats['total_interactions']} 次交互\n"
    response += f"Based on your {stats['total_interactions']} interactions"
    
    bot.reply_to(message, response)

# 在链接转换时记录交互
def record_link_interaction(user_id, original_url, platform):
    """记录链接交互"""
    try:
        recommendation_engine.record_interaction(
            user_id=user_id,
            product_url=original_url,
            platform=platform,
            action='click'
        )
    except Exception as e:
        logger.error(f"Failed to record interaction: {e}")


# ============ ML推荐引擎集成 ============
from app.ml_recommender import MLRecommender

ml_recommender = MLRecommender()

@bot.message_handler(commands=['smart_recommend'])
def handle_smart_recommend(message):
    """智能推荐命令（基于协同过滤）"""
    user_id = message.from_user.id
    
    # 获取个性化推荐
    recommendations = ml_recommender.recommend_products(user_id, limit=5)
    
    if not recommendations:
        bot.reply_to(message, 
            "🤖 智能推荐引擎需要更多数据\n"
            "Smart recommendation needs more data\n\n"
            "💡 继续使用机器人，我们会基于相似用户为你推荐！\n"
            "Keep using the bot, we'll recommend based on similar users!"
        )
        return
    
    # 构建推荐消息
    response = "🧠 智能推荐 / Smart Recommendations:\n\n"
    response += "基于相似用户偏好 / Based on similar users\n\n"
    
    for i, rec in enumerate(recommendations, 1):
        category_emoji = {
            'electronics': '📱',
            'fashion': '👗',
            'home': '🏠',
            'beauty': '💄',
            'sports': '⚽'
        }.get(rec['category'], '🔗')
        
        response += f"{i}. {category_emoji} {rec['category'].upper()}\n"
        response += f"   {rec['url'][:60]}...\n"
        response += f"   📊 匹配度 / Match: {rec['score']:.2f}\n"
        response += f"   💡 {rec['reason']}\n\n"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['trending'])
def handle_trending(message):
    """热门产品命令"""
    # 解析时间范围参数
    text = message.text.strip()
    parts = text.split()
    hours = 24  # 默认24小时
    
    if len(parts) > 1:
        try:
            hours = int(parts[1])
            if hours < 1 or hours > 168:  # 最多7天
                hours = 24
        except ValueError:
            pass
    
    trending = ml_recommender.get_trending_products(hours=hours, limit=10)
    
    if not trending:
        bot.reply_to(message, 
            f"📊 过去{hours}小时暂无热门产品\n"
            f"No trending products in the last {hours} hours\n\n"
            "💡 需要至少3次转换才会显示\n"
            "Need at least 3 conversions to show"
        )
        return
    
    # 构建热门消息
    response = f"🔥 热门产品 / Trending Products ({hours}h)\n\n"
    
    for i, item in enumerate(trending, 1):
        category_emoji = {
            'electronics': '📱',
            'fashion': '👗',
            'home': '🏠',
            'beauty': '💄',
            'sports': '⚽'
        }.get(item['category'], '🔗')
        
        response += f"{i}. {category_emoji} {item['category'].upper()}\n"
        response += f"   {item['url'][:60]}...\n"
        response += f"   {item['reason']}\n"
        response += f"   👥 {item['unique_users']} unique users\n\n"
    
    bot.reply_to(message, response)


# ========== 智能推荐功能 ==========
from app.recommendation_engine import RecommendationEngine

recommendation_engine = RecommendationEngine()

@bot.message_handler(commands=['recommend'])
def handle_recommend(message):
    """个性化推荐命令"""
    user_id = message.from_user.id
    
    recs = recommendation_engine.get_recommendations(user_id, limit=5)
    
    if not recs:
        bot.reply_to(message, "🤔 暂无推荐，请先浏览一些产品链接！")
        return
    
    response = "🎯 *为你推荐*\n\n"
    for i, rec in enumerate(recs, 1):
        response += f"{i}. {rec['platform'].upper()}\n"
        response += f"   🔗 {rec['url']}\n"
        response += f"   📌 {rec['keywords']}\n\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['trending'])
def handle_trending(message):
    """热门产品命令"""
    trending = recommendation_engine.get_trending_products(limit=10)
    
    if not trending:
        bot.reply_to(message, "📊 暂无热门产品数据")
        return
    
    response = "🔥 *本周热门产品*\n\n"
    for i, item in enumerate(trending, 1):
        response += f"{i}. {item['platform'].upper()} - {item['conversion_count']}次转换\n"
        response += f"   🔗 {item['url']}\n\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

# 在链接转换后更新用户兴趣
def update_interest_on_conversion(user_id: int, url: str, platform: str):
    """链接转换时更新用户兴趣"""
    try:
        recommendation_engine.update_user_interest(user_id, url, platform)
    except Exception as e:
        logger.error(f"Failed to update user interest: {e}")

