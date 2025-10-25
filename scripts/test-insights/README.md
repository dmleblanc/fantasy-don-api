# Insights Engine Local Testing

Test the insights engine Lambda function locally before deploying.

## Prerequisites

```bash
# Ensure you're logged into AWS
aws sso login --profile LeBlanc-Cloud-sso

# Install dependencies (from lambda_functions/insights_engine/)
pip install -r ../../lambda_functions/insights_engine/requirements.txt
pip install boto3
```

## Usage

### Basic Test (Week-over-Week)
```bash
python test_insights_local.py --from-week 6 --to-week 7
```

### Longer Period Comparison
```bash
python test_insights_local.py --from-week 1 --to-week 7
```

### Filter by Position
```bash
# Show only wide receivers
python test_insights_local.py --from-week 6 --to-week 7 --position WR

# Show only running backs
python test_insights_local.py --from-week 6 --to-week 7 --position RB
```

### Show Superlatives
```bash
python test_insights_local.py --from-week 6 --to-week 7 --show-superlatives
```

### Limit Results
```bash
# Show only top 5 players
python test_insights_local.py --from-week 6 --to-week 7 --limit 5
```

### Different Season
```bash
python test_insights_local.py --season 2024 --from-week 10 --to-week 11
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--season` | NFL season year | 2025 |
| `--from-week` | Starting week (required) | - |
| `--to-week` | Ending week (required) | - |
| `--limit` | Number of players to display | 10 |
| `--position` | Filter by position (QB, RB, WR, TE) | All |
| `--show-superlatives` | Display league-wide superlatives | False |
| `--profile` | AWS profile to use | LeBlanc-Cloud-sso |

## Output Files

All test runs automatically generate timestamped reports in the `outputs/` directory:

**Text Report:** `insights_test_{season}_week{from}-to-{to}_{timestamp}.txt`
- Human-readable formatted output
- Includes all displayed player insights and superlatives

**JSON Report:** `insights_test_{season}_week{from}-to-{to}_{timestamp}.json`
- Complete raw response data
- Useful for debugging or further analysis

**Example filenames:**
```
outputs/insights_test_2025_week6-to-7_20251025_143052.txt
outputs/insights_test_2025_week6-to-7_20251025_143052.json
outputs/insights_test_2025_week6-to-7_WR_20251025_143125.txt  # With position filter
```

The `outputs/` directory is excluded from git via `.gitignore`.

## Output Format

The script displays:

### Player Insights
- **Player Name** (Team - Position)
- **Volume Trends**: Target share, carries, targets with deltas
- **Production Trends**: Fantasy points, yards per touch with deltas
- **Flags**: Breakout candidate, bust risk, trending indicators

### Superlatives (if enabled)
- Grouped by category
- Top performers with values and descriptions

## Example Output

```
🏈 Testing Insights Engine
Season: 2025
Comparison: Week 6 → Week 7
================================================================================

📊 Player Insights (showing 10 of 243)
================================================================================

Ja'Marr Chase (CIN - WR)
  Volume Trends:
    Target Share: 31.6% (Δ +21.1%)
    Targets: 12.0 (Δ +8.0)
  Production Trends:
    Fantasy Points (PPR): 28.4 (Δ +15.2)
  Flags: 🚀 BREAKOUT | 📈 TRENDING UP

...

================================================================================
✅ Test completed successfully!

📝 Reports saved:
   Text: /path/to/outputs/insights_test_2025_week6-to-7_20251025_143052.txt
   JSON: /path/to/outputs/insights_test_2025_week6-to-7_20251025_143052.json
```

## Troubleshooting

**AWS Credentials Error:**
```bash
aws sso login --profile LeBlanc-Cloud-sso
```

**Module Not Found Error:**
```bash
# Install dependencies
pip install boto3 polars
```

**No Data Found:**
- Verify the specified weeks have data in S3
- Check bucket: `s3://nfl-stats-923890204996-us-east-1/stats/season/{season}/week/{week}/`
