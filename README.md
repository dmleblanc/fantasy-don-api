# Fantasy Don API

NFL Stats Data Pipeline built with AWS CDK (Python). This project fetches NFL statistics using the `nfl_stats_py` library, stores them in S3, and serves them via a REST API powered by API Gateway and Lambda.

## Architecture

```
┌─────────────────┐
│  EventBridge    │  (Daily at midnight UTC)
│   Cron Rule     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌─────────────────┐
│  Data Fetcher   │────────▶│   S3 Bucket     │
│     Lambda      │         │  (NFL Stats)    │
└─────────────────┘         └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │   API Lambda    │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  API Gateway    │
                            │   (REST API)    │
                            └─────────────────┘
```

### Components

1. **Data Fetcher Lambda** - Fetches NFL stats using `nfl_stats_py` and stores in S3
2. **S3 Bucket** - Stores historical and latest NFL stats data
3. **API Lambda** - Queries S3 and returns formatted data
4. **API Gateway** - REST API with multiple endpoints
5. **EventBridge** - Triggers data fetcher daily at midnight UTC

## Prerequisites

- Python 3.11 or higher
- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS account with appropriate permissions

## Installation

### 1. Clone and Setup

```bash
cd fantasy-don-api
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 3. Bootstrap CDK (First time only)

```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

## Deployment

### Deploy the Stack

```bash
cdk deploy
```

The deployment will output:
- **ApiEndpoint** - Your API Gateway URL
- **BucketName** - S3 bucket storing NFL stats
- **DataFetcherFunctionName** - Data fetcher Lambda function name
- **ApiLambdaFunctionName** - API Lambda function name

### View CloudFormation Template

```bash
cdk synth
```

### Destroy the Stack

```bash
cdk destroy
```

## API Endpoints

Base URL: `https://{api-id}.execute-api.{region}.amazonaws.com/prod`

### GET /stats/latest

Get the most recent NFL stats.

```bash
curl https://your-api-endpoint/prod/stats/latest
```

**Response:**
```json
{
  "timestamp": "2025-10-04T12:00:00Z",
  "data": {
    "players": [...],
    "teams": [...],
    "games": [...]
  },
  "metadata": {
    "fetch_date": "2025-10-04",
    "season": 2025
  }
}
```

### GET /stats/{date}

Get stats for a specific date (format: YYYY-MM-DD).

```bash
curl https://your-api-endpoint/prod/stats/2025-10-01
```

### GET /stats/player/{player_id}

Get stats for a specific player.

```bash
curl https://your-api-endpoint/prod/stats/player/12345
```

**Response:**
```json
{
  "timestamp": "2025-10-04T12:00:00Z",
  "player": {
    "id": "12345",
    "name": "Player Name",
    "stats": {...}
  },
  "metadata": {...}
}
```

### GET /stats/team/{team_id}

Get stats for a specific team (accepts ID, abbreviation, or name).

```bash
curl https://your-api-endpoint/prod/stats/team/KC
curl https://your-api-endpoint/prod/stats/team/chiefs
```

**Response:**
```json
{
  "timestamp": "2025-10-04T12:00:00Z",
  "team": {
    "id": "KC",
    "name": "Kansas City Chiefs",
    "stats": {...}
  },
  "metadata": {...}
}
```

## Manual Invocation

### Trigger Data Fetcher Manually

```bash
aws lambda invoke \
  --function-name nfl-stats-data-fetcher \
  --payload '{}' \
  response.json

cat response.json
```

### Test API Lambda Locally

```bash
cd lambda_functions/api
python -c "from index import handler; import json; print(json.dumps(handler({'httpMethod': 'GET', 'path': '/stats/latest'}, {}), indent=2))"
```

## Development

### Project Structure

```
fantasy-don-api/
├── app.py                          # CDK app entry point
├── cdk.json                        # CDK configuration
├── pyproject.toml                  # Python project config (includes nfl_stats_py)
├── requirements.txt                # CDK dependencies
├── infrastructure/
│   └── fantasy_don_stack.py        # Main CDK stack
├── lambda_functions/
│   ├── data_fetcher/
│   │   ├── index.py                # Fetcher handler
│   │   ├── requirements.txt        # nfl_stats_py dependency
│   │   └── utils.py                # Helper functions
│   └── api/
│       ├── index.py                # API handler
│       ├── requirements.txt        # API dependencies
│       └── utils.py                # Query helpers
└── tests/
    └── __init__.py
```

### Customizing the Data Fetcher

Edit `lambda_functions/data_fetcher/index.py` to customize how NFL stats are fetched:

```python
from nfl_stats_py import NFLStats

def get_nfl_stats() -> Dict[str, Any]:
    stats_client = NFLStats()

    data = {
        'players': stats_client.get_player_stats(),
        'teams': stats_client.get_team_stats(),
        'games': stats_client.get_game_stats(),
    }

    return data
```

### Modifying the Schedule

Edit `infrastructure/fantasy_don_stack.py` to change the EventBridge schedule:

```python
# Current: Daily at midnight UTC
schedule=events.Schedule.cron(minute="0", hour="0")

# Every 6 hours:
schedule=events.Schedule.cron(minute="0", hour="*/6")

# Weekdays only at 9 AM UTC:
schedule=events.Schedule.cron(minute="0", hour="9", week_day="MON-FRI")
```

### Adding New API Endpoints

Edit `infrastructure/fantasy_don_stack.py` to add new routes:

```python
# Add a new resource
season_resource = stats_resource.add_resource("season")
season_year_resource = season_resource.add_resource("{year}")
season_year_resource.add_method("GET", lambda_integration)
```

Then handle the new route in `lambda_functions/api/index.py`.

## Monitoring

### View Lambda Logs

```bash
# Data Fetcher logs
aws logs tail /aws/lambda/nfl-stats-data-fetcher --follow

# API Lambda logs
aws logs tail /aws/lambda/nfl-stats-api --follow
```

### View S3 Contents

```bash
aws s3 ls s3://nfl-stats-{account}-{region}/stats/ --recursive
```

### API Gateway Metrics

View in AWS Console:
- API Gateway → APIs → NFL Stats API → Dashboard
- Metrics: Request count, latency, errors

## Cost Estimation

Based on moderate usage:
- **S3**: ~$0.50/month (1GB storage, lifecycle policies)
- **Lambda**: ~$1.00/month (data fetcher runs daily, API calls minimal)
- **API Gateway**: ~$1.00/month (1M requests free tier)
- **EventBridge**: Free (included)

**Total**: ~$2-3/month for low-moderate usage

## Troubleshooting

### CDK Deploy Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Ensure CDK is bootstrapped
cdk bootstrap
```

### Lambda Function Errors

```bash
# Check recent errors
aws logs filter-pattern /aws/lambda/nfl-stats-data-fetcher --pattern "ERROR" --start-time -1h
```

### S3 Access Issues

Ensure Lambda execution roles have proper permissions (automatically configured by CDK).

### nfl_stats_py Not Found

The Lambda deployment packages dependencies automatically. Ensure `requirements.txt` is present in the Lambda function directory.

## Security

- S3 bucket has encryption enabled and blocks public access
- Lambda functions use IAM roles with least-privilege permissions
- API Gateway can be extended with API keys, Cognito, or Lambda authorizers
- All resources created within your AWS account

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

MIT License - feel free to use this project for your own purposes.

## Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [nfl_stats_py Documentation](https://pypi.org/project/nfl_stats_py/)
- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Lambda Documentation](https://docs.aws.amazon.com/lambda/)
