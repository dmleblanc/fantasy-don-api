# NFL Stats Pipeline Scripts

Utility scripts for monitoring and managing the NFL stats data pipeline.

## check-runs

Quick utility to view EventBridge scheduled run history.

### Usage

```bash
# Check last 24 hours (default)
./scripts/check-runs

# Check last 48 hours
./scripts/check-runs 48

# Check last week
./scripts/check-runs 168
```

### What It Shows

1. **Data Fetcher Invocations**
   - All Lambda runs triggered by EventBridge (daily at midnight UTC)
   - Duration, memory usage, success/failure status
   - Request IDs for debugging

2. **Data Validator Invocations**
   - All validation runs (daily at 1am UTC)
   - Performance metrics
   - Request IDs

3. **Latest S3 File Updates**
   - When `stats/latest.json` was last updated
   - When metadata was last updated
   - File sizes and ages

4. **Recent Validation Reports**
   - Last 7 validation audit reports
   - Pass/fail status
   - Number of violations and warnings

### Example Output

```
================================================================================
NFL STATS PIPELINE - SCHEDULED RUN HISTORY
================================================================================

📊 DATA FETCHER (EventBridge: Daily at midnight UTC)
--------------------------------------------------------------------------------
Found 3 invocations in last 24 hours:

  1. ✅ 2025-10-09 13:48:57.697
     Duration: 3513.08 ms | Memory: 293 MB
     Request ID: d57fcf22-d831-471f-8a91-ac1c82674266

  2. ✅ 2025-10-09 02:18:10.432
     Duration: 2871.21 ms | Memory: 294 MB
     Request ID: d3dcd1df-321b-4794-9a65-547c55a30b01

  3. ✅ 2025-10-09 00:00:20.653
     Duration: 3155.05 ms | Memory: 293 MB
     Request ID: 0c3d9a7d-3336-4539-8815-6ee070ba4977


🔍 DATA VALIDATOR (EventBridge: Daily at 1am UTC)
--------------------------------------------------------------------------------
Found 1 invocations in last 24 hours:

  1. ✅ 2025-10-09 01:00:27.227
     Duration: 3158.88 ms | Memory: 95 MB
     Request ID: b6b33bae-6b97-470f-997a-6330f9cf42a5


📁 LATEST S3 FILE UPDATES
--------------------------------------------------------------------------------
  ✓ stats/latest.json
    Updated: 2025-10-09 13:48:58 UTC (0d 0h 4m ago)
    Size: 3736.8 KB


📋 RECENT VALIDATION REPORTS
--------------------------------------------------------------------------------
Last 1 validation reports:

  1. ✅ 2025-10-09T01:00:27.100026+00:00
     Violations: 0 | Warnings: 1
     File: audit-reports/2025-10-09-010027.json

================================================================================
```

### Automated Schedule

The pipeline runs automatically via EventBridge:

| Time (UTC) | Lambda | Description |
|------------|--------|-------------|
| 12:00 AM | Data Fetcher | Fetches latest NFL stats, validates, updates S3 |
| 1:00 AM | Data Validator | Validates all S3 data, saves audit report |

### Troubleshooting

**No invocations found:**
- Check if more than 24 hours since last run
- Try increasing hours: `./scripts/check-runs 48`

**Error accessing logs:**
- Ensure AWS credentials are configured
- Run `aws sso login --profile LeBlanc-Cloud-sso`

**S3 files show errors:**
- Check if data fetcher ran successfully
- View full logs: `aws logs tail /aws/lambda/nfl-stats-data-fetcher --profile LeBlanc-Cloud-sso`

## Advanced Usage

Use the Python script directly for more options:

```bash
# Custom AWS profile
python scripts/check_scheduled_runs.py --profile my-profile --hours 72

# Help
python scripts/check_scheduled_runs.py --help
```
