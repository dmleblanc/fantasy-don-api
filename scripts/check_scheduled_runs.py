#!/usr/bin/env python3
"""
Check EventBridge Scheduled Invocations
Shows past automated runs of data fetcher and validator lambdas
"""

import boto3
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import argparse


class ScheduledRunChecker:
    def __init__(self, profile: str = "LeBlanc-Cloud-sso"):
        self.session = boto3.Session(profile_name=profile)
        self.logs_client = self.session.client('logs')
        self.lambda_client = self.session.client('lambda')

    def get_lambda_invocations(self, function_name: str, hours: int = 24) -> List[Dict]:
        """Get Lambda invocations from CloudWatch Logs"""
        log_group = f"/aws/lambda/{function_name}"

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        try:
            # Query CloudWatch Logs Insights
            query = """
            fields @timestamp, @message, @requestId
            | filter @type = "REPORT"
            | sort @timestamp desc
            | limit 50
            """

            response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )

            query_id = response['queryId']

            # Wait for query to complete
            import time
            max_attempts = 30
            for _ in range(max_attempts):
                result = self.logs_client.get_query_results(queryId=query_id)
                if result['status'] == 'Complete':
                    return self._parse_log_results(result['results'])
                time.sleep(0.5)

            return []

        except Exception as e:
            print(f"Error querying logs for {function_name}: {e}")
            return []

    def _parse_log_results(self, results: List) -> List[Dict]:
        """Parse CloudWatch Logs Insights results"""
        invocations = []

        for result in results:
            fields = {item['field']: item['value'] for item in result}

            # Parse REPORT line
            message = fields.get('@message', '')
            if 'Duration' in message and 'Billed Duration' in message:
                # Extract metrics from REPORT line
                parts = message.split('\t')
                metrics = {}
                for part in parts:
                    if ':' in part:
                        key, value = part.split(':', 1)
                        metrics[key.strip()] = value.strip()

                invocations.append({
                    'timestamp': fields.get('@timestamp'),
                    'request_id': fields.get('@requestId'),
                    'duration': metrics.get('Duration', 'N/A'),
                    'billed_duration': metrics.get('Billed Duration', 'N/A'),
                    'memory_used': metrics.get('Max Memory Used', 'N/A'),
                    'status': metrics.get('Status', 'success')
                })

        return invocations

    def get_latest_s3_files(self, bucket: str = "nfl-stats-923890204996-us-east-1") -> Dict:
        """Get last modified times for key S3 files"""
        s3_client = self.session.client('s3')
        files_to_check = [
            'stats/latest.json',
            'stats/metadata.json',
            'stats/weekly/season/2025/week/5/data.json'
        ]

        file_info = {}
        for key in files_to_check:
            try:
                response = s3_client.head_object(Bucket=bucket, Key=key)
                file_info[key] = {
                    'last_modified': response['LastModified'],
                    'size': response['ContentLength']
                }
            except Exception as e:
                file_info[key] = {'error': str(e)}

        return file_info

    def check_validation_reports(self, bucket: str = "nfl-stats-923890204996-us-east-1", days: int = 7) -> List[Dict]:
        """Get recent validation audit reports"""
        s3_client = self.session.client('s3')

        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix='audit-reports/',
                MaxKeys=50
            )

            reports = []
            for obj in response.get('Contents', []):
                # Parse timestamp from filename: audit-reports/2025-10-08-175546.json
                key = obj['Key']
                if key.endswith('.json'):
                    try:
                        # Download and parse report
                        report_obj = s3_client.get_object(Bucket=bucket, Key=key)
                        report_data = json.loads(report_obj['Body'].read().decode('utf-8'))

                        reports.append({
                            'filename': key,
                            'timestamp': report_data.get('audit_timestamp'),
                            'status': report_data.get('summary', {}).get('status'),
                            'violations': report_data.get('summary', {}).get('total_violations', 0),
                            'warnings': report_data.get('summary', {}).get('total_warnings', 0)
                        })
                    except:
                        pass

            # Sort by timestamp descending
            reports.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return reports[:days]

        except Exception as e:
            print(f"Error checking validation reports: {e}")
            return []

    def display_summary(self, hours: int = 24):
        """Display comprehensive summary of scheduled runs"""
        print("=" * 80)
        print("NFL STATS PIPELINE - SCHEDULED RUN HISTORY")
        print("=" * 80)
        print()

        # Data Fetcher invocations
        print("📊 DATA FETCHER (EventBridge: Daily at midnight UTC)")
        print("-" * 80)
        fetcher_runs = self.get_lambda_invocations('nfl-stats-data-fetcher', hours)

        if fetcher_runs:
            print(f"Found {len(fetcher_runs)} invocations in last {hours} hours:\n")
            for i, run in enumerate(fetcher_runs[:10], 1):
                timestamp = run['timestamp']
                status_icon = "✅" if run['status'] == 'success' else "❌"
                print(f"  {i}. {status_icon} {timestamp}")
                print(f"     Duration: {run['duration']} | Memory: {run['memory_used']}")
                print(f"     Request ID: {run['request_id']}")
                print()
        else:
            print("  No invocations found in the specified time range")
            print()

        # Data Validator invocations
        print()
        print("🔍 DATA VALIDATOR (EventBridge: Daily at 1am UTC)")
        print("-" * 80)
        validator_runs = self.get_lambda_invocations('nfl-data-validator', hours)

        if validator_runs:
            print(f"Found {len(validator_runs)} invocations in last {hours} hours:\n")
            for i, run in enumerate(validator_runs[:10], 1):
                timestamp = run['timestamp']
                status_icon = "✅" if run['status'] == 'success' else "❌"
                print(f"  {i}. {status_icon} {timestamp}")
                print(f"     Duration: {run['duration']} | Memory: {run['memory_used']}")
                print(f"     Request ID: {run['request_id']}")
                print()
        else:
            print("  No invocations found in the specified time range")
            print()

        # Latest S3 file updates
        print()
        print("📁 LATEST S3 FILE UPDATES")
        print("-" * 80)
        s3_files = self.get_latest_s3_files()

        for key, info in s3_files.items():
            if 'error' in info:
                print(f"  ❌ {key}: {info['error']}")
            else:
                last_mod = info['last_modified']
                size_kb = info['size'] / 1024
                age = datetime.now(timezone.utc) - last_mod
                age_str = f"{age.days}d {age.seconds//3600}h {(age.seconds//60)%60}m ago"
                print(f"  ✓ {key}")
                print(f"    Updated: {last_mod.strftime('%Y-%m-%d %H:%M:%S UTC')} ({age_str})")
                print(f"    Size: {size_kb:.1f} KB")
                print()

        # Validation reports
        print()
        print("📋 RECENT VALIDATION REPORTS")
        print("-" * 80)
        reports = self.check_validation_reports(days=7)

        if reports:
            print(f"Last {len(reports)} validation reports:\n")
            for i, report in enumerate(reports, 1):
                status_icon = "✅" if report['status'] == 'PASS' else "❌"
                print(f"  {i}. {status_icon} {report['timestamp']}")
                print(f"     Violations: {report['violations']} | Warnings: {report['warnings']}")
                print(f"     File: {report['filename']}")
                print()
        else:
            print("  No validation reports found")
            print()

        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Check EventBridge scheduled run history for NFL stats pipeline'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to look back (default: 24)'
    )
    parser.add_argument(
        '--profile',
        type=str,
        default='LeBlanc-Cloud-sso',
        help='AWS profile to use (default: LeBlanc-Cloud-sso)'
    )

    args = parser.parse_args()

    checker = ScheduledRunChecker(profile=args.profile)
    checker.display_summary(hours=args.hours)


if __name__ == "__main__":
    main()
