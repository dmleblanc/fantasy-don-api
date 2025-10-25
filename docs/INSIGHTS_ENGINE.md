# NFL Insights Engine

## Overview

The NFL Insights Engine is a serverless Lambda function that generates persistent week-over-week insights for NFL fantasy football data. It analyzes player, team, and defense statistics to identify trends, calculate deltas, and generate league-wide superlatives.

## Architecture

```
EventBridge (00:15 UTC) → Insights Engine Lambda → S3 (insights/)
                                ↓
                       Reads: stats/weekly/
                       Writes: insights/season/{season}/week/{week}/
```

## Features

### 1. Player Insights
- **Volume Trends**: Target share, carries, targets, air yards share
- **Efficiency Trends**: YPC, catch rate, yards per target, fantasy points per touch
- **Week-over-Week Deltas**: Quantify changes between consecutive weeks
- **3-Week Trends**: Linear regression analysis to identify rising/falling patterns

### 2. Team Insights
- **Pace/Volume**: Plays per game, pass rate trends
- **Personnel Usage**: RB committee entropy, WR target distribution

### 3. Defense Insights
- **Position Vulnerability**: Points allowed vs QB/RB/WR/TE
- **Defensive Performance**: Sacks, interceptions, tackles (future phase)

### 4. Superlatives (League-Wide Awards)
- Target Share Gainers/Losers (TOP 3)
- Touches Gainers (TOP 3)
- Efficiency Improvers (YPC, Catch Rate)
- Fantasy Points Gainers (TOP 3)

## Data Sources

**Primary**: nflreadpy `load_player_stats()` (114 columns available)

**Key Metrics Used**:
- ✓ `target_share` (USER'S PRIMARY REQUEST)
- ✓ `air_yards_share`
- ✓ `carries`, `targets`, `receptions`
- ✓ `fantasy_points_ppr`
- ✓ `rushing_yards`, `receiving_yards`, `passing_yards`
- ✓ `rushing_tds`, `receiving_tds`, `passing_tds`

**Not Currently Used** (requires additional data source):
- `snap_pct` (available via `load_snap_counts()` - Phase 2)

## File Structure

```
insights_engine/
├── index.py                     # Main Lambda handler
├── models.py                    # Data models (PlayerInsight, TrendData, etc.)
├── persistence.py               # S3 read/write operations
├── calculators/
│   ├── player_insights.py       # Player trend calculations
│   ├── team_insights.py         # Team trend calculations
│   ├── defense_insights.py      # Defense vulnerability calculations
│   └── superlatives.py          # League-wide awards generation
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
├── AVAILABLE_METRICS.md         # Documentation of available metrics
└── README.md                    # This file
```

## S3 Storage Structure

### Inputs (Read)
```
stats/
├── metadata.json                # Current season/week
└── weekly/
    └── season/{season}/
        └── week/{week}/
            └── data.json        # Player stats
```

### Outputs (Write)
```
insights/
├── latest.json                  # Latest insights snapshot
├── season/{season}/
│   ├── deltas/
│   │   └── {player_id}.json    # Historical player deltas
│   └── week/{week}/
│       ├── insights.json        # Full insights package
│       └── superlatives.json   # Weekly superlatives
```

## API Endpoints

All endpoints are served via the existing API Lambda:

### Insights
- `GET /insights/latest` - Latest weekly insights
- `GET /insights/week/{week}` - Insights for specific week (current season)
- `GET /insights/season/{season}/week/{week}` - Insights for specific season/week
- `GET /insights/player/{player_id}` - Player-specific insights

### Superlatives
- `GET /superlatives/latest` - Latest superlatives
- `GET /superlatives/week/{week}` - Superlatives for specific week
- `GET /superlatives/season/{season}/week/{week}` - Superlatives for specific season/week

## Execution Flow

1. **Triggered**: EventBridge at 00:15 UTC daily (15 min after data fetcher)
2. **Read Metadata**: Determine current season/week
3. **Fetch Historical Data**: Load last 3 weeks (N, N-1, N-2)
4. **Calculate Insights**:
   - Player insights (volume, efficiency, trends)
   - Team insights (pace, personnel)
   - Generate superlatives
5. **Write to S3**:
   - Weekly insights package
   - Superlatives file
   - Latest snapshot
   - Player delta history (future)

## User's Primary Request: Target Share Delta

The engine calculates week-over-week changes in target share for all players:

```json
{
  "player_id": "00-0038120",
  "player_name": "Justin Jefferson",
  "volume_trends": {
    "target_share": {
      "current_value": 0.28,
      "previous_value": 0.22,
      "delta": +0.06,
      "delta_pct": +27.3,
      "three_week_values": [0.19, 0.22, 0.28],
      "trend_direction": "rising",
      "slope": 0.045,
      "projected_next": 0.32
    }
  }
}
```

**Superlatives Generated**:
- "Target Share Gainer (Rank 1)" - Biggest increase in target share
- "Target Share Loser (Rank 1)" - Biggest decrease in target share

## Deployment

### Infrastructure
Defined in `infrastructure/fantasy_don_stack.py`:
- Lambda: `nfl-insights-engine` (Docker image, ARM64, 512MB, 5min timeout)
- EventBridge: Daily trigger at 00:15 UTC
- Permissions: S3 read/write access to stats bucket

### Deploy Command
```bash
cdk deploy
```

## Future Enhancements (Phase 2)

1. **Snap Share Metrics**: Join `load_snap_counts()` data
2. **Historical Delta Storage**: Persistent player delta files
3. **Defense Matchup Analysis**: Requires game schedule data
4. **Advanced Superlatives**: Breakout candidates, trend-based awards
5. **Predictive Projections**: Next week value predictions

## Example Usage

### Get Latest Insights
```bash
curl https://cloudfront-url/insights/latest
```

### Get Target Share Gainers
```bash
curl https://cloudfront-url/superlatives/latest | jq '.superlatives[] | select(.subcategory == "target_share")'
```

### Get Player Insights
```bash
curl https://cloudfront-url/insights/player/00-0038120
```

## Monitoring

- CloudWatch Logs: `/aws/lambda/nfl-insights-engine`
- Metrics: Invocations, Duration, Errors
- S3 Outputs: Check `insights/latest.json` timestamp

## Notes

- Insights are cached at CloudFront edge with 1-hour TTL
- Data updates daily at 00:15 UTC
- Requires at least 2 weeks of data for delta calculations
- Requires 3 weeks of data for trend analysis
