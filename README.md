# Multi-Platform Affiliate Telegram Bot

🤖 A Telegram bot that automatically converts product links from **5 major e-commerce platforms** into affiliate links.

[English](#english) | [中文](#中文)

## English

### Supported Platforms

| Platform | Affiliate Program | Link Types |
|----------|------------------|------------|
| 🛒 Amazon | Amazon Associates | Standard URLs + short links (amzn.to, a.co) |
| 🧡 Shopee | Shopee Affiliate | All regional domains |
| 💜 Lazada | Lazada Affiliate | All 6 SEA countries |
| 🔴 AliExpress | AliExpress Portals | Standard + short links |
| 🎵 TikTok Shop | TikTok Affiliate | Shop links |

### Features

- ✅ Auto-detects platform from URL
- ✅ Handles multiple links in one message
- ✅ Expands short URLs (amzn.to, a.co, etc.)
- ✅ Works in private chats and groups
- ✅ Supports all regional domains (20+ Amazon, 12+ Shopee, 6 Lazada)
- ✅ Built-in conversion statistics (`/stats`)
- ✅ Zero dependencies beyond `requests`

### Quick Start

```bash
git clone https://github.com/platoba/MultiAffiliateTGBot.git
cd MultiAffiliateTGBot
cp .env.example .env
# Edit .env with your credentials
pip install -r requirements.txt
python bot.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Telegram Bot Token from @BotFather |
| `AMAZON_TAG` | ❌ | Amazon Associates tag (e.g., `yourtag-20`) |
| `AMAZON_DOMAIN` | ❌ | Amazon domain (default: `amazon.com`) |
| `SHOPEE_AFF_ID` | ❌ | Shopee Affiliate ID |
| `LAZADA_AFF_ID` | ❌ | Lazada Affiliate ID |
| `ALIEXPRESS_AFF_ID` | ❌ | AliExpress Affiliate ID |
| `TIKTOK_AFF_ID` | ❌ | TikTok Shop Affiliate ID |
| `DEV_CHAT_ID` | ❌ | Your Telegram chat ID for error alerts |

> Configure at least one platform to start earning commissions!

### Deploy (24/7)

```bash
# Using systemd
sudo cp multi-affiliate-bot.service /etc/systemd/system/
sudo systemctl enable multi-affiliate-bot
sudo systemctl start multi-affiliate-bot

# Using Docker
docker build -t affiliate-bot .
docker run -d --env-file .env affiliate-bot

# Using PM2
pm2 start bot.py --name affiliate-bot --interpreter python3
```

### Commission Rates

| Platform | Typical Rate | Cookie Duration |
|----------|-------------|-----------------|
| Amazon | 1-10% | 24 hours |
| Shopee | 5-15% | 7 days |
| Lazada | 5-12% | 7 days |
| AliExpress | 3-9% | 3 days |
| TikTok Shop | 5-20% | Varies |

---

## 中文

### 多平台联盟推广 Telegram 机器人

一个 Telegram 机器人，自动将 5 大电商平台的产品链接转换为联盟推广链接。

### 支持平台

| 平台 | 联盟计划 | 覆盖地区 |
|------|----------|----------|
| 🛒 Amazon | Amazon Associates | 全球20+站点 |
| 🧡 Shopee | Shopee联盟 | 东南亚/台湾/巴西/墨西哥 |
| 💜 Lazada | Lazada联盟 | 东南亚6国 |
| 🔴 AliExpress | 速卖通联盟 | 全球 |
| 🎵 TikTok Shop | TikTok联盟 | 全球 |

### 快速开始

```bash
git clone https://github.com/platoba/MultiAffiliateTGBot.git
cd MultiAffiliateTGBot
cp .env.example .env
# 编辑 .env 填入你的配置
pip install -r requirements.txt
python bot.py
```

### 使用方法

1. 创建 Telegram Bot（@BotFather → /newbot）
2. 注册各平台联盟计划，获取推广ID
3. 配置 `.env` 环境变量
4. 运行 `python bot.py`
5. 发送产品链接给Bot，自动返回联盟链接

### License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🔗 More Tools

- [Amazon-SP-API-Python](https://github.com/platoba/Amazon-SP-API-Python) - Modern Amazon SP-API client
- [Smart-Link-Shortener](https://github.com/platoba/Smart-Link-Shortener) - Self-hosted link shortener with analytics
- [AI-Listing-Writer](https://github.com/platoba/AI-Listing-Writer) - AI-powered product listing generator
