# Fantasy Don API - Directory Structure

## Overview

This project is an AWS CDK-based infrastructure for NFL fantasy football data fetching, validation, insights generation, and API serving.

## Root Directory

```
fantasy-don-api/
├── README.md                   # Project overview and setup instructions
├── app.py                      # CDK app entry point
├── cdk.json                    # CDK configuration
├── pyproject.toml              # Python project configuration
├── requirements.txt            # CDK/dev dependencies
├── .gitignore                  # Git ignore rules
├── infrastructure/             # CDK stack definitions
├── lambda_functions/           # Lambda function source code
├── docs/                       # Project documentation
└── scripts/                    # Utility scripts
```

## Infrastructure (`infrastructure/`)

CDK stack definition for AWS resources:

```
infrastructure/
├── __init__.py
└── fantasy_don_stack.py        # Main CDK stack
    ├── S3 Buckets
    ├── Lambda Functions (4)
    ├── API Gateway
    ├── CloudFront Distribution
    └── EventBridge Rules
```

## Lambda Functions (`lambda_functions/`)

### 1. Data Fetcher (`data_fetcher/`)
Fetches NFL stats from nflreadpy and stores in S3.

```
data_fetcher/
├── index.py                    # Lambda handler
├── utils.py                    # Helper functions
├── validation.py               # Data validation
├── requirements.txt            # Dependencies (nflreadpy, polars, boto3)
└── Dockerfile                  # Container image definition
```

**Trigger:** EventBridge (daily at 00:00 UTC)
**Output:** `s3://bucket/stats/weekly/season/{season}/week/{week}/data.json`

### 2. Data Validator (`data_validator/`)
Validates data quality and generates audit reports.

```
data_validator/
├── index.py                    # Lambda handler
├── schema.py                   # JSON schemas
├── validators.py               # Validation logic
└── requirements.txt            # Dependencies (jsonschema, boto3)
```

**Trigger:** EventBridge (daily at 01:00 UTC, after data fetch)
**Output:** `s3://bucket/stats/validation/`

### 3. Insights Engine (`insights_engine/`)
Generates week-over-week insights and superlatives.

```
insights_engine/
├── index.py                    # Lambda handler
├── models.py                   # Data models (PlayerInsight, TrendData, etc.)
├── persistence.py              # S3 read/write operations
├── calculators/
│   ├── player_insights.py      # Player trend calculations
│   ├── team_insights.py        # Team trend calculations
│   ├── defense_insights.py     # Defense vulnerability calculations
│   └── superlatives.py         # League-wide awards (target share gainers, etc.)
├── requirements.txt            # Dependencies (boto3)
└── Dockerfile                  # Container image definition
```

**Trigger:** EventBridge (daily at 00:15 UTC, 15 min after data fetch)
**Output:**
- `s3://bucket/insights/season/{season}/week/{week}/insights.json`
- `s3://bucket/insights/season/{season}/comparisons/{from}-to-{to}/`
- `s3://bucket/insights/latest.json`

### 4. API (`api/`)
REST API for serving stats and insights.

```
api/
├── index.py                    # Lambda handler with routing
├── utils.py                    # Helper functions
└── requirements.txt            # Dependencies (boto3)
```

**Trigger:** API Gateway (HTTP requests)
**Endpoints:** See [API Documentation](#api-endpoints)

## Documentation (`docs/`)

```
docs/
├── DIRECTORY_STRUCTURE.md      # This file
├── INSIGHTS_ENGINE.md          # Insights engine overview
├── INSIGHTS_COMPARISONS.md     # Week comparison insights
├── AVAILABLE_METRICS.md        # Available metrics from nflreadpy
└── data-fetcher-documentation.md  # Data fetcher details
```

## Scripts (`scripts/`)

Utility scripts for management and testing:

```
scripts/
├── README.md                              # Scripts overview
├── check_scheduled_runs.py                # Monitor EventBridge triggers
├── check-runs                             # Shell wrapper for monitoring
└── generate_all_combinations.py          # Generate all week comparisons
```

### Usage Examples

```bash
# Monitor scheduled Lambda runs
./scripts/check-runs

# Generate all week comparison insights
python3 scripts/generate_all_combinations.py 2025
```

## S3 Storage Structure

```
s3://nfl-stats-{account}-us-east-1/
├── stats/
│   ├── metadata.json                      # Current season/week
│   ├── latest.json                        # Latest week data
│   ├── weekly/
│   │   └── season/{season}/
│   │       └── week/{week}/
│   │           └── data.json              # Player stats
│   ├── aggregated/
│   │   └── season/{season}/
│   │       └── season-totals.json         # Season aggregates
│   └── validation/
│       └── audit-{timestamp}.json         # Validation reports
│
└── insights/
    ├── latest.json                        # Latest insights
    └── season/{season}/
        ├── week/{week}/
        │   ├── insights.json              # Weekly insights
        │   └── superlatives.json          # Weekly superlatives
        ├── comparisons/
        │   ├── summary.json               # All comparisons summary
        │   └── {from}-to-{to}/
        │       ├── insights.json          # Comparison insights
        │       └── superlatives.json      # Comparison superlatives
        └── deltas/
            └── {player_id}.json           # Historical player deltas
```

## API Endpoints

### Stats Endpoints
- `GET /stats/latest` - Latest week stats
- `GET /stats/week/{week}` - Stats for specific week
- `GET /stats/season/{season}/week/{week}` - Stats for specific season/week
- `GET /stats/player/{player_id}` - Player-specific stats
- `GET /stats/team/{team_id}` - Team-specific stats

### Insights Endpoints
- `GET /insights/latest` - Latest weekly insights
- `GET /insights/week/{week}` - Insights for specific week
- `GET /insights/season/{season}/week/{week}` - Insights for specific season/week
- `GET /insights/player/{player_id}` - Player-specific insights

### Superlatives Endpoints
- `GET /superlatives/latest` - Latest superlatives
- `GET /superlatives/week/{week}` - Superlatives for specific week
- `GET /superlatives/season/{season}/week/{week}` - Superlatives for specific season/week

### Metadata Endpoints
- `GET /week/current` - Current NFL week and season

### Injury Endpoints
- `GET /injuries/current` - Current injury report
- `GET /injuries/changes` - Injury status changes
- `GET /injuries/week/{week}` - Injury report for specific week

### Games Endpoints
- `GET /games/season/{season}` - All games for a season

## Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy stack
cdk deploy

# Destroy stack
cdk destroy
```

## Key Features

### 1. Data Fetching
- Daily automated fetch from nflreadpy
- Stores player stats, team stats, schedules, injuries
- Handles 2024 and 2025 seasons

### 2. Data Validation
- Schema validation for all data files
- Audit trail for data quality
- Automated alerts for issues

### 3. Insights Generation
- **Target share tracking** (week-over-week deltas)
- Volume trends (carries, targets, touches)
- Efficiency trends (YPC, catch rate, etc.)
- 3-week trend analysis with linear regression
- League-wide superlatives (top gainers/losers)
- **All week comparisons** pre-calculated (21 for 7 weeks, 153 for 18 weeks)

### 4. API Serving
- REST API via API Gateway
- CloudFront CDN caching (1-hour TTL)
- Optimized for sub-100ms responses

## Development

### Local Testing

```bash
# Test insights engine locally
cd lambda_functions/insights_engine
python3 -c "from index import handler; handler({}, {})"

# Generate all week comparisons
python3 scripts/generate_all_combinations.py 2025
```

### Adding New Endpoints

1. Add helper function in `lambda_functions/api/index.py`
2. Add routing logic in `handler()` function
3. Add API Gateway resource in `infrastructure/fantasy_don_stack.py`
4. Deploy with `cdk deploy`

## Monitoring

- CloudWatch Logs: `/aws/lambda/{function-name}`
- Metrics: Lambda invocations, duration, errors
- S3 Objects: Monitor data freshness via `metadata.json`

## Cost Optimization

- ARM64 Lambda architecture (20% cheaper)
- CloudFront caching reduces Lambda invocations
- S3 Intelligent-Tiering for storage
- EventBridge for precise scheduling

## Security

- IAM roles with least-privilege permissions
- S3 bucket encryption at rest
- API Gateway with CloudFront for DDoS protection
- No public S3 bucket access
