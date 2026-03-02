# Changelog

## v3.0.0 (2026-03-01)

### 🛡️ Fraud Detection Engine (`app/services/fraud_detector.py`)
- Multi-signal click fraud analysis with risk scoring (0-100)
- 6 detection modules: velocity flood, bot signature matching (25+ patterns), duplicate click fingerprinting, geographic anomaly (impossible travel), regular interval detection (bot automation), suspicious referrer checking
- Risk levels: clean → low → medium → high → critical
- Auto-actions: allow / flag / throttle / block / quarantine
- In-memory click buffer for real-time velocity checks
- Blocked user persistence with optional expiry
- Fraud event database with evidence trail
- Daily fraud statistics aggregation
- Top offenders ranking and comprehensive reports
- Configurable thresholds (velocity window, dedup window, block/throttle scores)
- 53 tests covering all detection modules

### 📊 Analytics Dashboard (`app/services/analytics_dashboard.py`)
- Revenue summary with hourly/daily/weekly/monthly granularity
- Platform comparison (side-by-side metrics, peak hours, top products, market share %)
- Trending products analysis (by clicks, conversions, revenue, unique users)
- Geographic breakdown (per-country clicks, users, dominant platform)
- User segmentation engine (power/active/casual/dormant)
- Growth metrics (period-over-period: clicks, conversions, revenue, users with trend arrows)
- 24-hour and 7-day heatmaps for optimal timing
- Conversion funnel analysis (impressions→clicks→conversions→revenue with rate calculations)
- Top users leaderboard
- Multi-format report generation (TEXT with emoji, JSON structured, CSV tabular)
- 47 tests covering all analytics functions

### 🔔 Notification Engine (`app/services/notification_engine.py`)
- 9 default milestone alerts (First Click → $1,000 Revenue) with deduplication
- Anomaly detection using Welford's online algorithm (z-score based spike/drop alerts)
- Daily and weekly performance digest generation
- Goal management system (create/update/complete/delete with progress tracking)
- Smart notification delivery with handler registration
- Quiet hours / DND mode (configurable time range with timezone offset)
- Urgent priority bypasses quiet hours
- Deduplication window (configurable, default 24h)
- Notification lifecycle: pending → sent → read → dismissed
- Batch send support
- History, unread, and statistics queries
- SQLite persistence for notifications, milestones, goals, and anomaly baselines
- 48 tests covering milestones, anomalies, digests, goals, delivery, and edge cases

### 📈 Numbers
- Tests: 330 → 478 (+148 new tests across 3 test files)
- New code: ~2,100 lines (3 modules + 3 test files)
- All 478 tests passing

## v2.0.0 (2026-02-28)

### 🏗️ Architecture
- Modular architecture: `app/config.py` + `app/platforms/` + `app/services/`
- Platform handlers: Amazon, Shopee, Lazada, AliExpress, TikTok as separate classes
- `PlatformRegistry` for centralized URL detection and dispatch
- `ConversionResult` dataclass with product_id and commission estimates

### 🗄️ Database
- SQLite-backed analytics replacing JSON file storage
- User tracking with first_seen/last_seen
- Group chat statistics
- Daily conversion trends
- User block/unblock management
- Group enable/disable management

### ⚡ Performance
- `LinkCache` with TTL-based SQLite caching
- `RateLimiter` with token-bucket algorithm and burst protection
- Max links per message configurable

### 🌍 Features
- Multi-language support (Chinese zh, English en)
- Commission rate display per platform
- CSV/JSON data export
- Rich analytics reports with bar charts
- `/report`, `/export`, `/commission`, `/mystats` commands
- Centralized configuration via `AppConfig.from_env()`

### 🧪 Testing
- 100+ tests across 9 test files
- Tests for: config, platforms (5), registry, database, cache, rate limiter, exporter, formatter, legacy

### 🐳 DevOps
- Enhanced Docker Compose with test runner
- GitHub Actions CI: lint + test (3.9/3.11/3.12) + Docker build
- Makefile with test-cov target
- pyproject.toml with full tool config

## v1.0.0 (2026-02-27)

- Initial release: 5-platform affiliate link conversion
- Basic JSON analytics
- 27 tests
