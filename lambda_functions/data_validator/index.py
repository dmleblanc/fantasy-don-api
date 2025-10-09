"""
NFL Stats Data Validator Lambda
Validates S3 bucket data structure and quality
"""

import json
import os
import boto3
from datetime import datetime, timezone
from validators import S3DataValidator
from schema import S3Schema

s3_client = boto3.client('s3')


def handler(event, context):
    """
    Validates S3 bucket data structure and quality

    Event params:
    - validation_level: "quick" | "standard" | "comprehensive" (default: standard)
    - seasons: [2023, 2024, 2025] (optional, defaults to [2024, 2025])
    - save_report: true/false (default: true)
    """

    bucket_name = os.environ.get('BUCKET_NAME', 'nfl-stats-923890204996-us-east-1')
    validation_level = event.get('validation_level', 'standard')
    seasons = event.get('seasons', [2024, 2025])
    save_report = event.get('save_report', True)

    print(f"=== NFL Stats Data Validator ===")
    print(f"Validation Level: {validation_level}")
    print(f"Seasons: {seasons}")
    print(f"Bucket: {bucket_name}")

    validator = S3DataValidator(bucket_name)
    schema = S3Schema()

    # === QUICK VALIDATIONS (< 10 seconds) ===
    print("\n--- Running Quick Validations ---")

    # 1. Check metadata exists and is valid
    print("Checking metadata...")
    if validator.validate_file_exists("stats/metadata.json"):
        validator.validate_file_structure("stats/metadata.json", schema.METADATA_REQUIRED_FIELDS)
        validator.validate_metadata_consistency()

    # 2. Check current week injury data exists
    print("Checking current injury data...")
    validator.validate_file_exists("stats/injuries/current-week/latest.json")

    if validation_level == "quick":
        return generate_response(validator, save_report)

    # === STANDARD VALIDATIONS (< 60 seconds) ===
    print("\n--- Running Standard Validations ---")

    for season in seasons:
        expected_weeks = schema.WEEKS_PER_SEASON.get(season, 22)
        print(f"\nValidating season {season} (expecting {expected_weeks} weeks)...")

        # 3. Check season completeness
        validator.validate_season_completeness(season, expected_weeks)

        # 4. Validate sample weeks (first and last)
        sample_weeks = [1]
        if expected_weeks > 1:
            sample_weeks.append(expected_weeks)

        for week in sample_weeks:
            s3_key = f"stats/weekly/season/{season}/week/{week}/data.json"
            print(f"  Validating week {week}...")

            if validator.validate_file_exists(s3_key):
                validator.validate_file_structure(s3_key, schema.WEEKLY_STATS_TOP_LEVEL)
                validator.validate_player_data_schema(s3_key, schema.WEEKLY_STATS_REQUIRED_FIELDS)

                # Use dynamic min players based on week (accounts for playoffs)
                min_players = schema.get_min_players_for_week(week)
                validator.validate_player_count(s3_key, min_players)
                validator.validate_stat_ranges(s3_key, schema.STAT_RANGES)

        # 5. Check data freshness for current season
        if season == max(seasons):
            latest_week = expected_weeks
            s3_key = f"stats/weekly/season/{season}/week/{latest_week}/data.json"
            validator.validate_data_freshness(s3_key, schema.DATA_FRESHNESS_WARNING_HOURS)

    if validation_level == "standard":
        return generate_response(validator, save_report)

    # === COMPREHENSIVE VALIDATIONS (< 5 minutes) ===
    print("\n--- Running Comprehensive Validations ---")

    for season in seasons:
        expected_weeks = schema.WEEKS_PER_SEASON.get(season, 22)
        print(f"\nComprehensive validation for season {season}...")

        # 6. Validate ALL weeks
        for week in range(1, expected_weeks + 1):
            s3_key = f"stats/weekly/season/{season}/week/{week}/data.json"

            if validator.validate_file_exists(s3_key):
                # Use dynamic min players based on week (accounts for playoffs)
                min_players = schema.get_min_players_for_week(week)
                validator.validate_player_count(s3_key, min_players)
                validator.validate_stat_ranges(s3_key, schema.STAT_RANGES)

            # Also check injury data if available
            injury_key = f"stats/injuries/season/{season}/week/{week}/final.json"
            try:
                s3_client.head_object(Bucket=bucket_name, Key=injury_key)
                validator.info.append({
                    'rule': 'injury_data_available',
                    'severity': 'INFO',
                    'message': f"Injury data available for week {week}",
                    'path': injury_key
                })
            except:
                pass  # Injury data optional

    return generate_response(validator, save_report)


def generate_response(validator: S3DataValidator, save_report: bool = True) -> dict:
    """Generate Lambda response with audit report"""
    report = validator.generate_audit_report()

    # Print summary
    print("\n=== Validation Summary ===")
    print(f"Status: {report['summary']['status']}")
    print(f"Violations: {report['summary']['total_violations']}")
    print(f"Warnings: {report['summary']['total_warnings']}")
    print(f"Checks Passed: {report['summary']['total_checks']}")

    # Print violations
    if report['violations']:
        print("\n--- Violations ---")
        for v in report['violations'][:10]:
            print(f"  ❌ {v['message']}")

    # Print warnings
    if report['warnings']:
        print("\n--- Warnings ---")
        for w in report['warnings'][:5]:
            print(f"  ⚠️  {w['message']}")

    # Save report to S3
    report_s3_key = None
    if save_report:
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')
        report_s3_key = f"audit-reports/{timestamp}.json"

        s3_client.put_object(
            Bucket=validator.bucket,
            Key=report_s3_key,
            Body=json.dumps(report, indent=2),
            ContentType='application/json'
        )
        print(f"\n✅ Audit report saved to: s3://{validator.bucket}/{report_s3_key}")

    # Return response
    return {
        'statusCode': 200 if report['summary']['status'] == 'PASS' else 500,
        'body': json.dumps({
            'status': report['summary']['status'],
            'summary': report['summary'],
            'report_s3_key': report_s3_key,
            'violations': report['violations'],
            'warnings': report['warnings'][:10]  # First 10 warnings
        }, indent=2)
    }
