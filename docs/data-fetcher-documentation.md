# NFL Stats Data Fetcher - Lambda Documentation

**Last Updated:** October 10, 2025
**Lambda Function:** `nfl-stats-data-fetcher`
**Version:** 1.2.0

---

## Overview

The Data Fetcher Lambda is responsible for retrieving NFL player statistics from nflreadpy (nflverse) and storing them in S3. It runs automatically on a schedule and can be invoked manually for backfills or testing.

---

## Invocation Schedule

### Automated Triggers

| Trigger | Schedule | Description |
|---------|----------|-------------|
| **EventBridge Rule** | Daily at 00:00 UTC (8:00 PM ET) | Fetches latest week's data |
| Rule Name | `DailyDataFetchRule` | Defined in CDK stack |
| Enabled | ✅ Yes | Active since deployment |

**Why midnight UTC?**
- Most games finish by 11:00 PM ET Sunday/Monday
- nflverse updates data overnight
- Ensures fresh data available by morning

### Manual Invocation

```bash
# Fetch current season (default behavior)
aws lambda invoke \
  --function-name nfl-stats-data-fetcher \
  --profile LeBlanc-Cloud-sso \
  response.json

# View response
cat response.json | jq
```

**Common manual invocation scenarios:**
- After Thursday Night Football (to get Week N+1 early data)
- Data validation failures (re-fetch after fixing issues)
- Testing after code changes
- Backfilling historical seasons (future capability)

---

## Data Fetching Process

### Step 1: Determine Current Season/Week

```python
current_season = get_current_season()  # Based on current date
current_week = get_current_nfl_week()  # Days since season start ÷ 7
```

**Season Logic:**
- Jan-Apr: Previous year (e.g., Jan 2025 = 2024 season)
- May-Dec: Current year (e.g., Oct 2025 = 2025 season)

**Week Logic:**
- Season starts: ~September 7
- Week = (days_since_start ÷ 7) + 1
- **Updated 10/10/2025:** Now uses max available week from data (not calculation)

### Step 2: Fetch Data from nflreadpy

**Data Sources:**

| Dataset | Function | Description | Availability |
|---------|----------|-------------|--------------|
| **Player Stats** | `nfl.load_player_stats([season])` | Weekly offensive/defensive stats | ✅ 2025 available |
| **Schedules** | `nfl.load_schedules([season])` | Game schedule, scores, dates | ✅ 2025 available |
| **Injuries** | `nfl.load_injuries([season])` | Injury reports by week | ❌ 2025 NOT available |
| **Projections** | `nfl.load_ff_rankings()` | Expert consensus rankings | ✅ Current week only |

**Fallback Logic:**
1. Try current season (2025)
2. If fails → Fall back to 2024
3. If injuries missing → Use empty DataFrame (graceful degradation)

### Step 3: Data Processing

**Per Week:**

1. **Filter weekly data** from full season dataset
2. **Join projections** (current week only, by player_id)
   - Cast projection `id` to string to match `player_id`
   - Add fields: `ecr`, `best`, `worst`, `sd`
3. **Enrich with team/game data**
4. **Transform to JSON**
5. **Validate schema** (inline validation before S3 write)
6. **Write to S3** if validation passes

**Aggregated Data:**
- **Teams:** Aggregate stats by team
- **Games:** Schedule with scores, betting lines, weather

### Step 4: Data Validation

**Before S3 Write (Inline Validation):**
- Check required fields present
- Verify player count thresholds (playoff-aware)
- Validate stat ranges (allow negative for sacks/fumbles)
- Skip writing if validation fails

**After S3 Write (Daily Validator):**
- Runs at 01:00 UTC (1 hour after fetch)
- Comprehensive schema validation
- Generates audit reports

---

## S3 Data Structure

### Weekly Stats

```
s3://nfl-stats-{account}-{region}/stats/weekly/season/{season}/week/{week}/data.json
```

**Example:**
```
stats/weekly/season/2025/week/1/data.json
stats/weekly/season/2025/week/2/data.json
stats/weekly/season/2025/week/6/data.json  ← Latest
```

**Format:**
```json
{
  "data": {
    "players": [
      {
        "player_id": "00-0038120",
        "player_name": "B.Hall",
        "week": 1,
        "rushing_yards": 107,
        "receiving_yards": 38,
        "fantasy_points_ppr": 16.5,
        "ecr": 12,  // Expert consensus ranking (if current week)
        // ... 80+ more fields
      }
    ]
  },
  "metadata": {
    "player_count": 1071,
    "fetch_date": "2025-10-09"
  }
}
```

### Latest Stats (Auto-Updated)

```
s3://nfl-stats-{account}-{region}/stats/latest.json
```

**Purpose:** Quick access to most recent week
**Updated:** Every time fetcher runs
**Contains:** Same structure as weekly data (most recent week only)

### Aggregated Data

```
stats/aggregated/season/{season}/teams.json    ← Team-level stats
stats/aggregated/season/{season}/games.json    ← All games (272 for full season)
```

### Metadata

```
stats/metadata.json
```

**Contents:**
```json
{
  "timestamp": "2025-10-10T12:08:32.775628+00:00",
  "current_season": 2025,
  "current_week": 6,
  "weeks_available": [1, 2, 3, 4, 5, 6],
  "last_updated": "2025-10-10T12:08:32.775628+00:00"
}
```

**Uses:**
- API reads this to determine current week
- Validation checks completeness
- Monitoring tools track freshness

---

## Data Flow Diagram

```
┌─────────────────────────────────────────┐
│  EventBridge (Daily 00:00 UTC)          │
│  OR Manual Invocation                   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Lambda: nfl-stats-data-fetcher         │
│  - Determine current season/week        │
│  - Fetch from nflreadpy                 │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Data Processing                        │
│  - Filter by week                       │
│  - Join projections (current week)      │
│  - Enrich with team/game data           │
│  - Transform to JSON                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Inline Validation                      │
│  - Schema check                         │
│  - Player count thresholds              │
│  - Stat ranges                          │
└────────────────┬────────────────────────┘
                 │
                 ▼
         ┌───────┴────────┐
         │  Valid?        │
         └───────┬────────┘
                 │
        ┌────────┴─────────┐
        │ YES              │ NO
        ▼                  ▼
┌──────────────────┐  ┌─────────────────┐
│  Write to S3     │  │  Skip & Log     │
│  - Weekly data   │  │  - Error logged │
│  - Latest data   │  │  - Lambda fails │
│  - Teams/Games   │  └─────────────────┘
│  - Metadata      │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  EventBridge (Daily 01:00 UTC)          │
│  Triggers: Data Validator Lambda        │
│  - Reads from S3                        │
│  - Validates schema                     │
│  - Generates audit reports              │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  CloudFront CDN                         │
│  - Caches API responses (1 hour)        │
│  - Serves to clients                    │
│  - Compresses (18MB → 2.8MB)            │
└─────────────────────────────────────────┘
```

---

## Recent Data Fetches

### Week 6 (Thursday Night Football)
- **Date:** October 10, 2025 12:08 UTC
- **Triggered By:** Manual invocation
- **Result:** ✅ Success
- **Data Written:**
  - `stats/weekly/season/2025/week/6/data.json` (67 players)
  - `stats/latest.json` (updated to week 6)
  - `stats/metadata.json` (current_week: 6)

### Week 5
- **Date:** October 9, 2025 00:00 UTC
- **Triggered By:** EventBridge schedule
- **Result:** ✅ Success
- **Data Written:**
  - `stats/weekly/season/2025/week/5/data.json` (961 players)
  - Full aggregated data for season

### Historical Pattern
- **Daily fetches:** Running since deployment
- **Success rate:** ~99% (occasional nflverse API issues)
- **Average duration:** 45-90 seconds
- **Memory usage:** ~500-800 MB (peak during polars processing)

---

## Monitoring & Troubleshooting

### Check Recent Invocations

```bash
# Using built-in monitoring script
./scripts/check-runs 24  # Last 24 hours

# Direct CloudWatch query
aws logs tail /aws/lambda/nfl-stats-data-fetcher \
  --profile LeBlanc-Cloud-sso \
  --since 1h
```

### Common Issues

**Issue 1: Missing 2025 injury data**
- **Cause:** nflverse hasn't published 2025 injury data yet
- **Resolution:** Graceful fallback to empty DataFrame
- **Status:** Working as designed ✅

**Issue 2: Week calculation off by 1**
- **Cause:** Date-based calculation vs actual data available
- **Resolution:** Changed to use max(weeks_available) from data
- **Fixed:** October 10, 2025

**Issue 3: Validation failures**
- **Cause:** Playoff weeks have fewer players
- **Resolution:** Added playoff-aware thresholds
- **Fixed:** October 9, 2025

### Validation Thresholds

| Week Type | Min Players | Example Weeks |
|-----------|-------------|---------------|
| Regular Season | 800 | Weeks 1-18 |
| Wild Card | 300 | Week 19 |
| Divisional | 150 | Week 20 |
| Conference | 100 | Week 21 |
| Super Bowl | 50 | Week 22 |

---

## Configuration

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `BUCKET_NAME` | `nfl-stats-{account}-{region}` | S3 bucket for data storage |
| `DATA_PREFIX` | `stats/` | S3 key prefix |

### Lambda Settings

| Setting | Value | Reason |
|---------|-------|--------|
| **Runtime** | Python 3.11 (Container) | nflreadpy requires polars |
| **Architecture** | ARM64 | Avoid polars illegal instruction errors |
| **Memory** | 2048 MB | Polars DataFrame processing |
| **Timeout** | 5 minutes | Complex data transformations |
| **Storage** | 512 MB | Default |

### Deployment

```bash
# Deploy changes
cdk deploy --profile LeBlanc-Cloud-sso

# The Lambda is containerized, so changes require:
# 1. Update lambda_functions/data_fetcher/index.py
# 2. CDK synth builds new Docker image
# 3. CDK deploy pushes to ECR and updates Lambda
```

---

## Data Retention

### S3 Lifecycle Rules

| Data Type | Transition | Archive |
|-----------|------------|---------|
| Weekly stats | → Intelligent Tiering after 30 days | → Glacier after 90 days |
| Latest data | No transition | N/A |
| Metadata | No transition | N/A |

### Versioning

- **S3 Versioning:** ✅ Enabled
- **Purpose:** Recover from accidental overwrites
- **Retention:** Previous versions retained per bucket policy

---

## Future Enhancements

### Planned

1. **Historical Backfill**
   - Add `season` parameter to Lambda event
   - Invoke for seasons 2020-2024
   - Populate S3 for ML training data

2. **Incremental Updates**
   - Detect which weeks need updates (stat corrections)
   - Only fetch/write changed data
   - Reduce processing time

3. **Data Quality Metrics**
   - Track validation pass/fail rates
   - Alert on anomalies (sudden player count drops)
   - Monitor nflverse API availability

### Under Consideration

- Real-time updates (fetch after each game completes)
- Play-by-play data integration
- Advanced stats (EPA, CPOE, etc.) enrichment

---

## References

- **nflverse Documentation:** https://github.com/nflverse/nflverse-data
- **nfl_data_py GitHub:** https://github.com/nflverse/nfl_data_py
- **CDK Stack:** `infrastructure/fantasy_don_stack.py`
- **Lambda Code:** `lambda_functions/data_fetcher/index.py`
- **Validation Schema:** `lambda_functions/data_fetcher/validation.py`

---

## Change Log

### October 10, 2025
- ✅ Fixed current_week calculation to use max(weeks_available)
- ✅ Updated API Lambda to read current_week from metadata
- ✅ Added Week 6 (Thursday Night Football) data

### October 9, 2025
- ✅ Added inline validation before S3 writes
- ✅ Implemented playoff-aware player count thresholds
- ✅ Fixed stat ranges to allow negative values
- ✅ Deployed validation Lambda with daily schedule

### October 8, 2025
- ✅ Added projection data (expert consensus rankings)
- ✅ Implemented graceful fallback for missing injury data
- ✅ Fixed projection column mappings (id → player_id)

### September 30, 2025
- 🚀 Initial deployment
- ✅ EventBridge schedule configured (daily 00:00 UTC)
- ✅ S3 bucket created with lifecycle rules
- ✅ CloudFront CDN configured

---

**Document Maintained By:** Fantasy Don API Team
**Next Review:** November 1, 2025
