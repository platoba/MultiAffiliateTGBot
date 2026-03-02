# ML-Powered Recommendation Features

## 🧠 New Commands

### `/smart_recommend` - Collaborative Filtering Recommendations
Get personalized product recommendations based on similar users' preferences.

**How it works:**
- Analyzes your conversion history
- Finds users with similar tastes (Jaccard similarity)
- Recommends products they liked but you haven't seen
- Category-aware boosting for better relevance

**Example:**
```
/smart_recommend
```

**Response:**
```
🧠 智能推荐 / Smart Recommendations:

基于相似用户偏好 / Based on similar users

1. 📱 ELECTRONICS
   https://amazon.com/wireless-earbuds...
   📊 匹配度 / Match: 2.45
   💡 Similar users also liked

2. 👗 FASHION
   https://shopee.com/summer-dress...
   📊 匹配度 / Match: 1.89
   💡 Similar users also liked
```

### `/trending [hours]` - Hot Products
See what products are trending across all users.

**Parameters:**
- `hours` (optional): Time window (1-168 hours, default: 24)

**Example:**
```
/trending 48
```

**Response:**
```
🔥 热门产品 / Trending Products (48h)

1. 📱 ELECTRONICS
   https://amazon.com/gaming-laptop...
   🔥 12 conversions in 48h
   👥 8 unique users

2. 💄 BEAUTY
   https://shopee.com/skincare-set...
   🔥 9 conversions in 48h
   👥 7 unique users
```

## 🎯 Algorithm Details

### Collaborative Filtering
- **Similarity Metric:** Jaccard Index
- **Threshold:** 0.1 minimum similarity
- **User Pool:** Top 100 most active users
- **History Depth:** Last 50 conversions per user

### Category Detection
Automatic category extraction from URLs:
- 📱 Electronics: phone, laptop, tablet, camera, headphone
- 👗 Fashion: dress, shirt, shoes, bag, watch
- 🏠 Home: furniture, kitchen, decor, bedding
- 💄 Beauty: makeup, skincare, perfume, cosmetic
- ⚽ Sports: fitness, yoga, running, gym, sport

### Trending Algorithm
- Minimum 3 conversions required
- Ranked by: conversion count → unique users
- Configurable time window (1h - 7 days)

## 📊 Data Requirements

| Feature | Minimum Data |
|---------|--------------|
| Smart Recommend | 5+ user conversions |
| Trending | 3+ conversions per product |
| Category Boost | 3+ conversions in category |

## 🔒 Privacy

- All recommendations are computed locally
- No external API calls
- User data stays in your SQLite database
- Similarity calculations are anonymous

## 🚀 Performance

- Similarity calculation: O(n) where n = active users
- Recommendation generation: < 100ms for typical datasets
- Trending query: Single SQL query with indexes

## 📈 Future Enhancements

- [ ] Content-based filtering (product descriptions)
- [ ] Hybrid recommendations (collaborative + content)
- [ ] Real-time price drop alerts for recommended products
- [ ] A/B testing framework for recommendation quality
- [ ] User feedback loop (like/dislike buttons)
