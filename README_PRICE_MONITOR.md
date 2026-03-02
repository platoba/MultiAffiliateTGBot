# 价格监控功能 (v2.1)

## 新增功能

### 🔔 价格监控
自动监控已转换产品的价格变化，在价格下降时通知用户。

### 新增命令

| 命令 | 描述 |
|------|------|
| `/watch` | 回复包含产品链接的消息来添加价格监控 |
| `/mywatches` | 查看我的所有价格监控 |
| `/unwatch <ID>` | 移除指定ID的价格监控 |

### 使用示例

1. **添加监控**
   ```
   用户: https://amazon.com/product/123
   Bot: [转换为联盟链接]
   用户: /watch (回复Bot的消息)
   Bot: ✅ 已添加价格监控
   ```

2. **查看监控列表**
   ```
   用户: /mywatches
   Bot: 📊 您的价格监控列表:
        1. Product Name
           平台: amazon
           价格: $99.99 USD
           ID: 1
   ```

3. **移除监控**
   ```
   用户: /unwatch 1
   Bot: ✅ 已移除监控 #1
   ```

### 技术实现

- **数据库**: SQLite存储监控记录和价格历史
- **检查频率**: 每小时检查一次价格变化
- **通知阈值**: 默认降价5%时通知用户
- **价格历史**: 保留30天的价格变化记录

### 数据库结构

```sql
-- 价格监控表
CREATE TABLE price_watches (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_url TEXT NOT NULL,
    affiliate_url TEXT NOT NULL,
    platform TEXT NOT NULL,
    product_title TEXT,
    current_price REAL,
    original_price REAL,
    currency TEXT DEFAULT 'USD',
    last_check TIMESTAMP,
    notify_threshold REAL DEFAULT 0.05,
    is_active INTEGER DEFAULT 1
);

-- 价格历史表
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY,
    watch_id INTEGER NOT NULL,
    price REAL NOT NULL,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 未来扩展

- [ ] 实现各平台的价格爬虫
- [ ] 支持自定义通知阈值
- [ ] 价格趋势图表
- [ ] 历史最低价提醒
- [ ] 批量导入监控列表
