# Changelog

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
