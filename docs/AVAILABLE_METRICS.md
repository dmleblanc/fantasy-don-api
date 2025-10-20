# Available Metrics for Insights Engine

Based on nflreadpy `load_player_stats()` columns (as of inspection on 2025-10-17)

## ✅ FULLY AVAILABLE - Can Calculate Immediately

### Volume Trends
- **Target Share** (`target_share`) - ✓ **USER'S PRIMARY REQUEST**
  - Week-over-week delta
  - 3-week trend analysis
  - League-wide rankings
- **Carries** (`carries`)
- **Targets** (`targets`)
- **Receptions** (`receptions`)
- **Air Yards Share** (`air_yards_share`)
- **Touch Share** (calculated: `carries + receptions`)

### Efficiency Trends
- **Yards Per Carry** (calculated: `rushing_yards / carries`)
- **Yards Per Target** (calculated: `receiving_yards / targets`)
- **Catch Rate** (calculated: `receptions / targets`)
- **Yards Per Reception** (calculated: `receiving_yards / receptions`)
- **Fantasy Points Per Touch** (calculated: `fantasy_points_ppr / (carries + receptions)`)
- **PACR** (`pacr` - Player Air Conversion Ratio)
- **RACR** (`racr` - Receiver Air Conversion Ratio)
- **WOPR** (`wopr` - Weighted Opportunity Rating)

### Fantasy Performance
- **Fantasy Points PPR** (`fantasy_points_ppr`)
- **Fantasy Points Standard** (`fantasy_points`)

### Defensive Stats (for Defense Insights)
- **Sacks** (`def_sacks`)
- **Interceptions** (`def_interceptions`)
- **Tackles Solo** (`def_tackles_solo`)
- **Tackles Assist** (`def_tackle_assists`)
- **Tackles for Loss** (`def_tackles_for_loss`)
- **QB Hits** (`def_qb_hits`)
- **Pass Defended** (`def_pass_defended`)

## ⚠️ REQUIRES ADDITIONAL DATA SOURCE

### Snap Share Metrics
- **Snap Percentage** - Available in `load_snap_counts()` as `offense_pct`
  - Requires joining snap_counts data with player_stats
  - Can be added in Phase 2

## 🎯 Superlatives We Can Calculate

Based on available fields, here are the superlatives we can generate:

### Volume Superlatives
1. **Target Share Gainers/Losers** ✓ (USER REQUEST)
2. **Air Yards Share Gainers/Losers** ✓
3. **Touch Gainers/Losers** (carries + receptions) ✓
4. **Target Gainers/Losers** ✓
5. **Carry Gainers/Losers** ✓

### Efficiency Superlatives
6. **Yards Per Carry Improvers** ✓
7. **Catch Rate Improvers** ✓
8. **Yards Per Target Improvers** ✓
9. **WOPR Gainers** (Weighted Opportunity Rating) ✓

### Fantasy Performance Superlatives
10. **Fantasy Points Gainers/Losers** ✓
11. **Fantasy Points Per Touch Improvers** ✓

### Trend-Based Superlatives (3-week trends)
12. **Hottest Players** (rising 3-week trends) ✓
13. **Coldest Players** (falling 3-week trends) ✓
14. **Breakout Candidates** (sharp upward trajectory) ✓

## 📝 Implementation Notes

1. **Phase 1** (Current): Implement all ✓ metrics using `load_player_stats()` only
2. **Phase 2** (Future): Add snap share metrics by joining `load_snap_counts()`
3. **Data Source**: All calculations use data from `stats/weekly/season/{season}/week/{week}/data.json`
4. **Target Share**: This is the primary user request and is fully available!
