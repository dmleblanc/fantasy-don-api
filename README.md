# Fantasy Don API

> NFL Fantasy Football Data Pipeline and Insights Engine built with AWS CDK

[![AWS CDK](https://img.shields.io/badge/AWS-CDK-orange)](https://aws.amazon.com/cdk/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Table of Contents

1. [Overview](#1-overview)
   - 1.1 [Architecture](#11-architecture)
   - 1.2 [Key Features](#12-key-features)
   - 1.3 [Components](#13-components)
2. [Getting Started](#2-getting-started)
   - 2.1 [Prerequisites](#21-prerequisites)
   - 2.2 [Installation](#22-installation)
   - 2.3 [Deployment](#23-deployment)
3. [API Reference](#3-api-reference)
   - 3.1 [Base URL](#31-base-url)
   - 3.2 [Stats Endpoints](#32-stats-endpoints)
   - 3.3 [Insights Endpoints](#33-insights-endpoints)
   - 3.4 [Superlatives Endpoints](#34-superlatives-endpoints)
   - 3.5 [Metadata Endpoints](#35-metadata-endpoints)
   - 3.6 [Injury Endpoints](#36-injury-endpoints)
   - 3.7 [Games Endpoints](#37-games-endpoints)
4. [Data Structure](#4-data-structure)
   - 4.1 [S3 Storage Layout](#41-s3-storage-layout)
   - 4.2 [Response Formats](#42-response-formats)
5. [Insights Engine](#5-insights-engine)
   - 5.1 [What is the Insights Engine?](#51-what-is-the-insights-engine)
   - 5.2 [Available Insights](#52-available-insights)
   - 5.3 [Week Comparisons](#53-week-comparisons)
6. [Development](#6-development)
   - 6.1 [Project Structure](#61-project-structure)
   - 6.2 [Local Testing](#62-local-testing)
   - 6.3 [Adding Features](#63-adding-features)
7. [Operations](#7-operations)
   - 7.1 [Monitoring](#71-monitoring)
   - 7.2 [Manual Invocation](#72-manual-invocation)
   - 7.3 [Troubleshooting](#73-troubleshooting)
8. [Cost & Performance](#8-cost--performance)
   - 8.1 [Cost Estimation](#81-cost-estimation)
   - 8.2 [Performance Optimization](#82-performance-optimization)
9. [Security](#9-security)
10. [Context Sharing Prompt](#10-context-sharing-prompt)
11. [Resources](#11-resources)

---

## 1. Overview

### 1.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EventBridge Scheduler                            │
│  00:00 UTC (Data Fetch) | 00:15 UTC (Insights) | 01:00 UTC (Validation) │
└──────────┬───────────────────────┬────────────────────────┬──────────────┘
           │                       │                        │
           ▼                       ▼                        ▼
    ┌─────────────┐        ┌──────────────┐       ┌─────────────────┐
    │ Data Fetcher│        │   Insights   │       │  Data Validator │
    │   Lambda    │        │    Engine    │       │     Lambda      │
    └──────┬──────┘        └──────┬───────┘       └────────┬────────┘
           │                      │                         │
           └──────────────┬───────┴─────────────────────────┘
                          ▼
                   ┌──────────────┐
                   │  S3 Bucket   │
                   │  NFL Stats & │
                   │   Insights   │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  API Lambda  │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ API Gateway  │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  CloudFront  │
                   │     CDN      │
                   └──────────────┘
```

### 1.2 Key Features

- ✅ **Automated Data Collection**: Daily NFL stats fetching via nflreadpy
- ✅ **Insights Engine**: Week-over-week player analysis and trend detection
- ✅ **Target Share Tracking**: Monitor receiving opportunity changes
- ✅ **Superlatives**: League-wide top performers and biggest movers
- ✅ **Week Comparisons**: Pre-calculated insights for all week pairs (1→2, 1→7, 5→6, etc.)
- ✅ **Data Validation**: Automated quality checks and audit reports
- ✅ **REST API**: Fast, cached access via CloudFront CDN
- ✅ **Infrastructure as Code**: Fully automated AWS deployment via CDK

### 1.3 Components

| Component | Purpose | Trigger | Runtime |
|-----------|---------|---------|---------|
| **Data Fetcher** | Fetch NFL stats from nflreadpy | Daily 00:00 UTC | 2-3 min |
| **Insights Engine** | Generate week-over-week insights | Daily 00:15 UTC | 30-60 sec |
| **Data Validator** | Validate data quality | Daily 01:00 UTC | 10-20 sec |
| **API Lambda** | Serve data via REST API | On HTTP request | <100ms |
| **CloudFront** | CDN caching layer | On HTTP request | <50ms |

---

## 2. Getting Started

### 2.1 Prerequisites

- **AWS Account** with appropriate permissions
- **Python 3.11+** installed
- **AWS CLI** configured with credentials
- **AWS CDK CLI**: `npm install -g aws-cdk`
- **Git** for version control

### 2.2 Installation

**Step 1: Clone Repository**
```bash
git clone https://github.com/yourusername/fantasy-don-api.git
cd fantasy-don-api
```

**Step 2: Create Virtual Environment**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

**Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
pip install -e .
```

**Step 4: Configure AWS**
```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1)
```

**Step 5: Bootstrap CDK (First Time Only)**
```bash
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

### 2.3 Deployment

**Deploy Stack**
```bash
cdk deploy
```

**Outputs** (save these):
- `CloudFrontURL` - Your API base URL
- `ApiEndpoint` - API Gateway URL (use CloudFront instead)
- `StatsBucketName` - S3 bucket name
- `DataFetcherFunctionName` - Data fetcher Lambda
- `InsightsEngineFunctionName` - Insights engine Lambda

**View Changes Before Deployment**
```bash
cdk diff
```

**Destroy Stack**
```bash
cdk destroy
```

---

## 3. API Reference

### 3.1 Base URL

**Production (CloudFront CDN - Recommended)**
```
https://{cloudfront-id}.cloudfront.net
```

**Direct (API Gateway)**
```
https://{api-id}.execute-api.us-east-1.amazonaws.com/prod
```

**Example**
```bash
export API_URL="https://d1a2b3c4d5e6f7.cloudfront.net"
```

### 3.2 Stats Endpoints

#### 3.2.1 GET /stats/latest
Get the most recent week's NFL stats.

**Request**
```bash
curl $API_URL/stats/latest
```

**Response**
```json
{
  "timestamp": "2025-10-18T00:00:19Z",
  "season": 2025,
  "week": 7,
  "data": {
    "players": [
      {
        "player_id": "00-0036900",
        "player_name": "J.Chase",
        "position": "WR",
        "team": "CIN",
        "targets": 9,
        "receptions": 7,
        "receiving_yards": 125,
        "receiving_tds": 2,
        "fantasy_points_ppr": 32.5,
        "target_share": 0.511
      }
    ]
  },
  "metadata": {
    "total_players": 1014,
    "fetch_date": "2025-10-18"
  }
}
```

#### 3.2.2 GET /stats/week/{week}
Get stats for a specific week (current season).

**Request**
```bash
curl $API_URL/stats/week/6
```

#### 3.2.3 GET /stats/season/{season}/week/{week}
Get stats for a specific season and week.

**Request**
```bash
curl $API_URL/stats/season/2024/week/17
```

#### 3.2.4 GET /stats/player/{player_id}
Get stats for a specific player (latest week).

**Request**
```bash
curl $API_URL/stats/player/00-0036900
```

**Response**
```json
{
  "player_id": "00-0036900",
  "player_name": "J.Chase",
  "position": "WR",
  "team": "CIN",
  "season": 2025,
  "week": 7,
  "stats": {
    "targets": 9,
    "receptions": 7,
    "receiving_yards": 125,
    "fantasy_points_ppr": 32.5
  }
}
```

#### 3.2.5 GET /stats/team/{team_id}
Get stats for all players on a team.

**Request**
```bash
curl $API_URL/stats/team/CIN
```

### 3.3 Insights Endpoints

#### 3.3.1 GET /insights/latest
Get the latest weekly insights (current week).

**Request**
```bash
curl $API_URL/insights/latest
```

**Response**
```json
{
  "season": 2025,
  "week": 7,
  "generated_at": "2025-10-18T00:15:07Z",
  "player_insights": [
    {
      "player_id": "00-0036900",
      "player_name": "J.Chase",
      "position": "WR",
      "team": "CIN",
      "volume_trends": {
        "target_share": {
          "current_value": 0.511,
          "previous_value": 0.300,
          "delta": 0.211,
          "delta_pct": 70.4,
          "three_week_values": [0.25, 0.30, 0.511],
          "trend_direction": "rising",
          "slope": 0.131,
          "projected_next": 0.615
        }
      },
      "fantasy_points_delta": 13.0
    }
  ],
  "metadata": {
    "total_players": 72,
    "total_superlatives": 17
  }
}
```

#### 3.3.2 GET /insights/week/{week}
Get insights for a specific week (current season).

**Request**
```bash
curl $API_URL/insights/week/6
```

#### 3.3.3 GET /insights/season/{season}/week/{week}
Get insights for a specific season and week.

**Request**
```bash
curl $API_URL/insights/season/2025/week/7
```

#### 3.3.4 GET /insights/player/{player_id}
Get insights for a specific player (latest week).

**Request**
```bash
curl $API_URL/insights/player/00-0036900
```

### 3.4 Superlatives Endpoints

#### 3.4.1 GET /superlatives/latest
Get the latest weekly superlatives (top gainers/losers).

**Request**
```bash
curl $API_URL/superlatives/latest
```

**Response**
```json
{
  "season": 2025,
  "week": 7,
  "superlatives": [
    {
      "category": "volume",
      "subcategory": "target_share",
      "award_name": "Target Share Gainer (Rank 1)",
      "player_id": "00-0036900",
      "player_name": "J.Chase",
      "position": "WR",
      "team": "CIN",
      "value": 0.211,
      "metric_name": "target_share_delta",
      "rank": 1
    }
  ]
}
```

#### 3.4.2 GET /superlatives/week/{week}
Get superlatives for a specific week.

**Request**
```bash
curl $API_URL/superlatives/week/6
```

#### 3.4.3 GET /superlatives/season/{season}/week/{week}
Get superlatives for a specific season and week.

**Request**
```bash
curl $API_URL/superlatives/season/2025/week/7
```

### 3.5 Metadata Endpoints

#### 3.5.1 GET /week/current
Get current NFL season and week.

**Request**
```bash
curl $API_URL/week/current
```

**Response**
```json
{
  "season": 2025,
  "week": 7,
  "timestamp": "2025-10-18T00:00:19Z"
}
```

### 3.6 Injury Endpoints

#### 3.6.1 GET /injuries/current
Get current injury report.

**Request**
```bash
curl $API_URL/injuries/current
```

#### 3.6.2 GET /injuries/changes
Get injury status changes from yesterday.

**Request**
```bash
curl $API_URL/injuries/changes
```

#### 3.6.3 GET /injuries/week/{week}
Get injury report for a specific week.

**Request**
```bash
curl $API_URL/injuries/week/7
```

### 3.7 Games Endpoints

#### 3.7.1 GET /games/season/{season}
Get all games for a specific season.

**Request**
```bash
curl $API_URL/games/season/2025
```

---

## 4. Data Structure

### 4.1 S3 Storage Layout

```
s3://nfl-stats-{account}-us-east-1/
│
├── stats/
│   ├── metadata.json                 # Current season/week info
│   ├── latest.json                   # Latest week snapshot
│   │
│   ├── weekly/
│   │   └── season/{season}/
│   │       └── week/{week}/
│   │           └── data.json         # Player stats for the week
│   │
│   ├── aggregated/
│   │   └── season/{season}/
│   │       └── season-totals.json    # Season-wide aggregates
│   │
│   ├── injuries/
│   │   ├── current-week/
│   │   │   ├── latest.json
│   │   │   └── changes.json
│   │   └── season/{season}/week/{week}/
│   │       └── final.json
│   │
│   └── validation/
│       └── audit-{timestamp}.json    # Data quality reports
│
└── insights/
    ├── latest.json                   # Latest insights snapshot
    │
    └── season/{season}/
        ├── week/{week}/
        │   ├── insights.json         # Weekly insights
        │   └── superlatives.json     # Weekly top performers
        │
        ├── comparisons/
        │   ├── summary.json          # All available comparisons
        │   └── {from}-to-{to}/       # e.g., 5-to-6, 1-to-7
        │       ├── insights.json     # Comparison insights
        │       └── superlatives.json # Comparison top movers
        │
        └── deltas/
            └── {player_id}.json      # Historical player deltas
```

### 4.2 Response Formats

**Stats Response**
```json
{
  "timestamp": "ISO-8601 datetime",
  "season": 2025,
  "week": 7,
  "data": {
    "players": [...],
    "teams": [...],
    "games": [...]
  },
  "metadata": {...}
}
```

**Insights Response**
```json
{
  "season": 2025,
  "week": 7,
  "generated_at": "ISO-8601 datetime",
  "player_insights": [...],
  "team_insights": [...],
  "superlatives": [...],
  "metadata": {...}
}
```

---

## 5. Insights Engine

### 5.1 What is the Insights Engine?

The **Insights Engine** analyzes week-over-week changes in player performance, identifying trends, breakouts, and fades. It generates:

- **Volume Trends**: Target share, carries, targets, touches
- **Efficiency Trends**: YPC, catch rate, yards per target
- **3-Week Trends**: Linear regression for projections
- **Superlatives**: League-wide top gainers/losers

### 5.2 Available Insights

| Insight Type | Metrics | Description |
|--------------|---------|-------------|
| **Volume Trends** | Target share, carries, targets, air yards share | Opportunity-based metrics |
| **Efficiency Trends** | YPC, catch rate, yards/target, fantasy points/touch | Performance-based metrics |
| **Fantasy Performance** | PPR points delta, weekly ranking | Scoring changes |
| **3-Week Trends** | Linear regression slope, projection | Predictive analysis |

**Example: Target Share Insight**
```json
{
  "target_share": {
    "current_value": 0.511,
    "previous_value": 0.300,
    "delta": 0.211,           // +21.1% increase!
    "delta_pct": 70.4,
    "three_week_values": [0.25, 0.30, 0.511],
    "trend_direction": "rising",
    "slope": 0.131,
    "projected_next": 0.615   // Projected for next week
  }
}
```

### 5.3 Week Comparisons

The system pre-calculates insights for **ALL possible week pairs**:

**For 7 weeks: 21 comparisons**
- Consecutive: 1→2, 2→3, 3→4, 4→5, 5→6, 6→7
- 2-week gaps: 1→3, 2→4, 3→5, 4→6, 5→7
- Multi-week: 1→4, 1→5, 1→6, 1→7, etc.

**For 18 weeks: 153 comparisons**

**Formula**: `n × (n - 1) / 2`

**Access Comparisons**
```bash
# Week 5 to 6 comparison
curl $API_URL/insights/comparisons/season/2025/5/to/6

# Full season (Week 1 to 7)
curl $API_URL/insights/comparisons/season/2025/1/to/7
```

**Use Cases**:
- "Who's trending up this week?" → Week 6→7
- "Biggest risers over last month?" → Week 3→7
- "Season-long breakouts?" → Week 1→7

---

## 6. Development

### 6.1 Project Structure

```
fantasy-don-api/
├── README.md                          # This file
├── app.py                             # CDK app entry point
├── cdk.json                           # CDK configuration
├── pyproject.toml                     # Python project config
├── requirements.txt                   # CDK dependencies
│
├── docs/                              # Documentation
│   ├── DIRECTORY_STRUCTURE.md         # Project structure guide
│   ├── INSIGHTS_ENGINE.md             # Insights engine details
│   ├── INSIGHTS_COMPARISONS.md        # Week comparisons guide
│   └── AVAILABLE_METRICS.md           # nflreadpy metrics reference
│
├── infrastructure/
│   ├── __init__.py
│   └── fantasy_don_stack.py           # CDK stack definition
│
├── lambda_functions/
│   ├── data_fetcher/                  # NFL stats fetcher
│   │   ├── index.py
│   │   ├── utils.py
│   │   ├── validation.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── data_validator/                # Data quality validator
│   │   ├── index.py
│   │   ├── schema.py
│   │   ├── validators.py
│   │   └── requirements.txt
│   │
│   ├── insights_engine/               # Insights generator
│   │   ├── index.py
│   │   ├── models.py
│   │   ├── persistence.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── calculators/
│   │       ├── player_insights.py
│   │       ├── team_insights.py
│   │       ├── defense_insights.py
│   │       └── superlatives.py
│   │
│   └── api/                           # REST API
│       ├── index.py
│       ├── utils.py
│       └── requirements.txt
│
└── scripts/                           # Utility scripts
    ├── check_scheduled_runs.py        # Monitor EventBridge
    └── generate_all_combinations.py   # Generate week comparisons
```

### 6.2 Local Testing

**Test Data Fetcher**
```bash
cd lambda_functions/data_fetcher
python -c "from index import handler; handler({}, {})"
```

**Test Insights Engine**
```bash
cd lambda_functions/insights_engine
export BUCKET_NAME=nfl-stats-123456-us-east-1
python -c "from index import handler; handler({}, {})"
```

**Test API Lambda**
```bash
cd lambda_functions/api
python -c "from index import handler; import json; print(json.dumps(handler({'httpMethod': 'GET', 'path': '/stats/latest'}, {}), indent=2))"
```

**Generate All Week Comparisons**
```bash
python scripts/generate_all_combinations.py 2025
```

### 6.3 Adding Features

**Add New API Endpoint**

1. **Add route in CDK** (`infrastructure/fantasy_don_stack.py`):
```python
new_resource = api.root.add_resource("new-endpoint")
new_resource.add_method("GET", lambda_integration)
```

2. **Add handler in API Lambda** (`lambda_functions/api/index.py`):
```python
elif "/new-endpoint" in path:
    data = get_new_data()
    return create_response(200, data)
```

3. **Deploy**:
```bash
cdk deploy
```

**Add New Insight Calculator**

1. **Create calculator** (`lambda_functions/insights_engine/calculators/new_insight.py`)
2. **Import in main handler** (`lambda_functions/insights_engine/index.py`)
3. **Call in `generate_insights()` function**
4. **Deploy**:
```bash
cdk deploy
```

---

## 7. Operations

### 7.1 Monitoring

**View Lambda Logs**
```bash
# Data Fetcher
aws logs tail /aws/lambda/nfl-stats-data-fetcher --follow

# Insights Engine
aws logs tail /aws/lambda/nfl-insights-engine --follow

# API Lambda
aws logs tail /aws/lambda/nfl-stats-api --follow

# Data Validator
aws logs tail /aws/lambda/nfl-stats-data-validator --follow
```

**Check S3 Contents**
```bash
aws s3 ls s3://nfl-stats-{account}-us-east-1/stats/ --recursive
```

**Monitor Scheduled Runs**
```bash
./scripts/check-runs
```

**CloudWatch Metrics**
- Lambda: Invocations, Duration, Errors, Throttles
- API Gateway: Request count, Latency, 4xx/5xx errors
- CloudFront: Cache hit ratio, Origin latency

### 7.2 Manual Invocation

**Trigger Data Fetcher**
```bash
aws lambda invoke \
  --function-name nfl-stats-data-fetcher \
  --payload '{}' \
  response.json
```

**Trigger Insights Engine**
```bash
aws lambda invoke \
  --function-name nfl-insights-engine \
  --payload '{}' \
  response.json
```

**Trigger Data Validator**
```bash
aws lambda invoke \
  --function-name nfl-stats-data-validator \
  --payload '{"validation_level": "comprehensive", "seasons": [2024, 2025]}' \
  response.json
```

### 7.3 Troubleshooting

**Issue: CDK Deploy Fails**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Re-bootstrap CDK
cdk bootstrap

# Check diff before deploying
cdk diff
```

**Issue: Lambda Timeout**
```bash
# Increase timeout in CDK stack
timeout=Duration.minutes(5)

# Check CloudWatch Logs for errors
aws logs filter-pattern /aws/lambda/nfl-insights-engine --pattern "ERROR"
```

**Issue: S3 Access Denied**
- Verify IAM roles have S3 permissions (auto-configured by CDK)
- Check bucket name in environment variables

**Issue: API Returns Stale Data**
- CloudFront cache is 1 hour
- Invalidate cache:
```bash
aws cloudfront create-invalidation \
  --distribution-id {DISTRIBUTION_ID} \
  --paths "/*"
```

---

## 8. Cost & Performance

### 8.1 Cost Estimation

**Monthly Costs (Low-Moderate Usage)**

| Service | Usage | Cost |
|---------|-------|------|
| **S3** | 5GB storage, 10k reads/month | $0.12 |
| **Lambda** | Data Fetcher: 30 invokes × 2 min, Insights: 30 × 1 min, API: 100k invokes | $1.50 |
| **API Gateway** | 100k requests | $0.35 |
| **CloudFront** | 100k requests, 10GB transfer | $1.20 |
| **EventBridge** | 90 rules/month | Free |
| **CloudWatch** | Logs: 1GB ingestion | $0.50 |
| **Total** | | **~$3.67/month** |

**Cost Optimization Tips**:
- CloudFront caching reduces Lambda invocations by 90%+
- ARM64 architecture saves 20% on Lambda costs
- S3 Intelligent-Tiering for automatic storage optimization

### 8.2 Performance Optimization

**Current Performance**:
- API Latency: <50ms (CloudFront cache hit)
- API Latency: <100ms (Lambda cold start)
- Data Fetch: ~2-3 minutes
- Insights Generation: ~30-60 seconds

**Optimization Strategies**:
- CloudFront caching (1-hour TTL)
- ARM64 Lambda architecture
- S3 path optimization for fast lookups
- Pre-calculated week comparisons

---

## 9. Security

- ✅ **S3 Encryption**: Server-side encryption at rest
- ✅ **IAM Roles**: Least-privilege permissions for all Lambdas
- ✅ **No Public Access**: S3 buckets block all public access
- ✅ **CloudFront**: DDoS protection via AWS Shield
- ✅ **API Gateway**: Rate limiting and throttling
- ✅ **Secrets**: No hardcoded credentials, use IAM roles
- ✅ **VPC**: Optional VPC deployment for additional isolation

**Security Best Practices**:
- Rotate AWS credentials regularly
- Enable CloudTrail for audit logging
- Use AWS WAF for advanced API protection
- Implement API keys or Cognito for authentication

---

## 10. Context Sharing Prompt

Use this prompt when sharing context from this repository to other projects:

```
I'm working with the Fantasy Don API, an NFL fantasy football data pipeline built on AWS CDK. Here's the key context:

**Project Overview:**
- Automated NFL stats fetching using nflreadpy
- Insights engine for week-over-week player analysis
- REST API with CloudFront CDN
- Infrastructure: 4 Lambdas (Data Fetcher, Insights Engine, Data Validator, API)
- Storage: S3 with organized stats/ and insights/ prefixes
- Scheduling: EventBridge triggers at 00:00, 00:15, 01:00 UTC daily

**Key Components:**
1. Data Fetcher: Fetches NFL stats daily, stores in S3
2. Insights Engine: Generates player insights, target share tracking, superlatives
3. API Lambda: Serves data via REST API
4. CloudFront: CDN caching layer

**Data Structure:**
- Stats: s3://bucket/stats/weekly/season/{season}/week/{week}/data.json
- Insights: s3://bucket/insights/season/{season}/week/{week}/insights.json
- Comparisons: s3://bucket/insights/season/{season}/comparisons/{from}-to-{to}/

**Tech Stack:**
- AWS: CDK, Lambda (ARM64), S3, API Gateway, CloudFront, EventBridge
- Python 3.11+
- nflreadpy for NFL data
- boto3 for AWS SDK

**Key Features:**
- Target share delta tracking (week-over-week)
- 153 pre-calculated week comparisons (for 18-week season)
- Linear regression for 3-week trends
- Superlatives: top gainers/losers across all metrics

**API Endpoints:**
- GET /stats/latest - Latest week stats
- GET /insights/latest - Latest insights
- GET /superlatives/latest - Top performers
- GET /insights/comparisons/season/{season}/{from}/to/{to} - Week comparisons

**Documentation:**
- Full README: /README.md
- Directory Structure: /docs/DIRECTORY_STRUCTURE.md
- Insights Engine: /docs/INSIGHTS_ENGINE.md
- Week Comparisons: /docs/INSIGHTS_COMPARISONS.md

**Current State:**
- Deployed to AWS
- Running in production
- 7 weeks of 2025 season data available
- All 21 week comparisons pre-calculated

**What I need help with:**
[Describe your specific question or task here]
```

---

## 11. Resources

### Documentation
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [nflreadpy Documentation](https://github.com/nflverse/nflreadpy)
- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)

### Project Documentation
- [Directory Structure Guide](docs/DIRECTORY_STRUCTURE.md)
- [Insights Engine Overview](docs/INSIGHTS_ENGINE.md)
- [Week Comparisons Guide](docs/INSIGHTS_COMPARISONS.md)
- [Available Metrics Reference](docs/AVAILABLE_METRICS.md)

### Community
- [GitHub Repository](https://github.com/yourusername/fantasy-don-api)
- [Issue Tracker](https://github.com/yourusername/fantasy-don-api/issues)
- [Discussions](https://github.com/yourusername/fantasy-don-api/discussions)

### License
MIT License - See [LICENSE](LICENSE) for details.

---

**Last Updated**: October 2025
**Version**: 2.0.0
**Maintainer**: David LeBlanc
