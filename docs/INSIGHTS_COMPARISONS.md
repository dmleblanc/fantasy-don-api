# NFL Insights: Week Comparisons (All Combinations)

## Overview

The insights engine now **pre-calculates ALL possible week comparisons** for a season, not just consecutive weeks. This provides comprehensive historical analysis across any time period.

## What Gets Pre-Calculated

For a season with 7 weeks, we generate **21 unique comparisons**:

### Consecutive Weeks (6 comparisons)
- Week 1 → 2, 2 → 3, 3 → 4, 4 → 5, 5 → 6, 6 → 7

### 2-Week Gaps (5 comparisons)
- Week 1 → 3, 2 → 4, 3 → 5, 4 → 6, 5 → 7

### 3-Week Gaps (4 comparisons)
- Week 1 → 4, 2 → 5, 3 → 6, 4 → 7

### 4-Week Gaps (3 comparisons)
- Week 1 → 5, 2 → 6, 3 → 7

### 5-Week Gaps (2 comparisons)
- Week 1 → 6, 2 → 7

### 6-Week Gaps (1 comparison)
- Week 1 → 7

**Total for 18-week season: 153 comparisons**

## Storage Structure

```
s3://bucket/insights/season/{season}/comparisons/
├── summary.json                    # Overview of all available comparisons
├── 1-to-2/
│   ├── insights.json               # Full player/team insights
│   └── superlatives.json           # Top gainers/losers
├── 1-to-3/
│   ├── insights.json
│   └── superlatives.json
├── 5-to-6/
│   ├── insights.json
│   └── superlatives.json
└── ... (all 21 combinations for 7 weeks)
```

## Example: Pre-Calculated Insights

### Week 5 → Week 6 (Consecutive)
**Top Target Share Gainers:**
1. J.Smith-Njigba (WR, SEA): **+27.7%**
2. G.Wilson (WR, NYJ): **+27.3%**
3. J.Williams (WR, DET): **+21.6%**

### Week 1 → Week 7 (Full Season)
**Top Target Share Gainers:**
1. Ja'Marr Chase (WR, CIN): **+29.4%** (biggest gainer from week 1 to now!)
2. J.Warren (RB, PIT): **+8.3%**
3. P.Freiermuth (TE, PIT): **+7.8%**

### Week 5 → Week 7 (2-Week Gap)
**Top Target Share Gainers:**
1. Ja'Marr Chase (WR, CIN): **+26.1%**
2. T.Higgins (WR, CIN): **+4.7%**

## API Endpoints (Coming Soon)

```bash
# Get comparison summary for a season
GET /insights/comparisons/season/{season}

# Get insights comparing two weeks
GET /insights/comparisons/season/{season}/{week_from}/to/{week_to}

# Get superlatives comparing two weeks
GET /superlatives/comparisons/season/{season}/{week_from}/to/{week_to}

# Examples:
GET /insights/comparisons/season/2025/5/to/6    # Week 5 → 6
GET /insights/comparisons/season/2025/1/to/7    # Full season
GET /superlatives/comparisons/season/2025/3/to/7  # Mid-season to latest
```

## Use Cases

### 1. Consecutive Week Trends
**Question:** "Who's trending up this week?"
- Compare Week 6 → 7
- See immediate week-over-week changes

### 2. Multi-Week Breakouts
**Question:** "Who's emerged over the last month?"
- Compare Week 3 → 7 (4 weeks)
- Identify sustained performance changes

### 3. Full Season Analysis
**Question:** "Who's the biggest riser since week 1?"
- Compare Week 1 → 7 (full season)
- See **Ja'Marr Chase: +29.4% target share**

### 4. Injury Recovery Tracking
**Question:** "How's player X performing 3 weeks post-injury?"
- Compare Week 2 → 5
- Track recovery trajectory

### 5. Mid-Season Reset
**Question:** "What's changed since the bye week?"
- Compare Week 5 → 7
- Analyze post-bye performance

## Data Included in Each Comparison

For each comparison (e.g., Week 5 → Week 6):

### Player Insights
- **Target Share Delta**: Previous → Current (your specific request!)
- **Touches Delta**: Carries + Receptions change
- **Air Yards Share Delta**: Receiving opportunities
- **Efficiency Metrics**: YPC, catch rate, yards per target
- **Fantasy Points Delta**: PPR scoring changes

### Team Insights
- **Pace Changes**: Plays per game trends
- **Pass Rate**: Shift in offensive philosophy
- **Personnel Usage**: RB committee, WR target distribution

### Superlatives (Top 3 each)
- Target Share Gainers & Losers
- Touches Gainers
- Efficiency Improvers (YPC, Catch Rate)
- Fantasy Points Gainers

## Generation Script

Run the script to pre-calculate all comparisons:

```bash
python3 lambda_functions/insights_engine/generate_all_combinations.py 2025
```

This processes all week pairs and stores results in S3.

## Performance

- **7 weeks**: 21 comparisons (~30 seconds)
- **18 weeks**: 153 comparisons (~3-4 minutes)
- **Storage**: ~2MB per comparison × 153 = ~306MB for full season

## Formula: Total Comparisons

For **n** weeks:
```
Total Comparisons = n × (n - 1) / 2
```

Examples:
- 7 weeks: 7 × 6 / 2 = **21 comparisons**
- 10 weeks: 10 × 9 / 2 = **45 comparisons**
- 18 weeks: 18 × 17 / 2 = **153 comparisons**

## Key Insights from 2025 Data

### Biggest Season-Long Gainer (Week 1 → 7)
**Ja'Marr Chase**: +29.4% target share
- Week 1: 22.0%
- Week 7: 51.1%
- Consistent upward trajectory

### Biggest Week-Over-Week Gainer (Week 5 → 6)
**J.Smith-Njigba**: +27.7% target share
- Week 5: Unknown
- Week 6: Breakout performance

### Biggest Week-Over-Week Drop (Week 6 → 7)
**D.Metcalf**: -15.9% target share
- Week 6: 31.0%
- Week 7: 15.2%
- Potential injury or game script change

## Next Steps

1. ✅ Pre-calculate all comparisons (COMPLETE)
2. ⏳ Add API endpoints to CDK stack
3. ⏳ Add CloudFront caching for comparisons
4. ⏳ Create Lambda to auto-generate on new week data
5. ⏳ Add comparison query builder UI

## Notes

- Comparisons are directional: Week 5 → 6 treats Week 5 as baseline
- All metrics calculate delta from `week_from` to `week_to`
- Superlatives rank players within that specific comparison
- Each comparison is independent (not cumulative)
