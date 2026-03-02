# Changelog v3.1.0

## 🧠 ML-Powered Recommendation Engine (2026-03-02)

### New Features

#### 1. Collaborative Filtering Recommender (`app/ml_recommender.py`)
- **Smart Recommendations** based on user similarity
  - Jaccard similarity algorithm for finding like-minded users
  - Category-aware boosting (1.5x for preferred categories)
  - Excludes already-converted products
  - Configurable similarity threshold (0.1 default)
  
- **Trending Products** with time-window analysis
  - Minimum 3 conversions required
  - Ranked by conversion count + unique users
  - Configurable time window (1h - 7 days)
  - Real-time SQL aggregation

- **Automatic Category Detection**
  - 5 major categories: Electronics, Fashion, Home, Beauty, Sports
  - Keyword-based URL parsing
  - Fallback to 'general' category

#### 2. New Bot Commands
- `/smart_recommend` - Get personalized recommendations from similar users
- `/trending [hours]` - View hot products (default: 24h window)

#### 3. Algorithm Details
- **User History Depth:** Last 50 conversions per user
- **Similarity Pool:** Top 100 active users
- **Recommendation Limit:** 5 products per request
- **Trending Limit:** 10 products per request

### Technical Implementation

**Files Added:**
- `app/ml_recommender.py` - Core ML recommendation engine
- `tests/test_ml_recommender.py` - 5 comprehensive tests
- `README_ML_FEATURES.md` - Full documentation

**Database Queries:**
- User history: `SELECT original_url FROM conversions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?`
- Trending: `SELECT original_url, COUNT(*) FROM conversions WHERE timestamp > datetime('now', '-X hours') GROUP BY original_url`

**Performance:**
- Similarity calculation: O(n) where n = active users
- Recommendation generation: < 100ms typical
- Trending query: Single indexed SQL query

### Testing
```bash
pytest tests/test_ml_recommender.py -v
# 5 passed, 1 warning in 0.01s
```

**Test Coverage:**
- ✅ Category extraction (electronics, fashion, home, beauty, sports)
- ✅ User history retrieval
- ✅ Similar user discovery (Jaccard similarity)
- ✅ Product recommendations (collaborative filtering)
- ✅ Trending products (time-window aggregation)

### Usage Examples

**Smart Recommendations:**
```
User: /smart_recommend

Bot: 🧠 智能推荐 / Smart Recommendations:

基于相似用户偏好 / Based on similar users

1. 📱 ELECTRONICS
   https://amazon.com/wireless-earbuds...
   📊 匹配度 / Match: 2.45
   💡 Similar users also liked
```

**Trending Products:**
```
User: /trending 48

Bot: 🔥 热门产品 / Trending Products (48h)

1. 📱 ELECTRONICS
   https://amazon.com/gaming-laptop...
   🔥 12 conversions in 48h
   👥 8 unique users
```

### Data Requirements
- Smart Recommend: Minimum 5 user conversions
- Trending: Minimum 3 conversions per product
- Category Boost: Minimum 3 conversions in category

### Privacy & Security
- ✅ All computations local (no external APIs)
- ✅ User data stays in SQLite database
- ✅ Anonymous similarity calculations
- ✅ No PII in recommendations

### Future Roadmap
- [ ] Content-based filtering (product descriptions)
- [ ] Hybrid recommendations (collaborative + content)
- [ ] Real-time price drop alerts for recommended products
- [ ] A/B testing framework
- [ ] User feedback loop (like/dislike buttons)
- [ ] Deep learning embeddings (product2vec)

---

**Version:** v3.1.0  
**Release Date:** 2026-03-02  
**Tests:** 5/5 passed  
**Lines of Code:** ~200 (ml_recommender.py) + ~100 (tests)
