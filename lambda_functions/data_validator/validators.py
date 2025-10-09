"""
S3 Data Validators
Functions to validate data quality and structure
"""

import boto3
import json
from typing import List, Dict, Any
from datetime import datetime, timezone
from botocore.exceptions import ClientError


class S3DataValidator:
    """Validates S3 bucket data structure and quality"""

    def __init__(self, bucket_name: str):
        self.s3 = boto3.client('s3')
        self.bucket = bucket_name
        self.violations = []
        self.warnings = []
        self.info = []

    # === STRUCTURAL VALIDATIONS ===

    def validate_file_exists(self, s3_key: str) -> bool:
        """Check if expected file exists in S3"""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            self.info.append({
                'rule': 'file_exists',
                'severity': 'INFO',
                'message': f"File exists: {s3_key}",
                'path': s3_key
            })
            return True
        except ClientError:
            self.violations.append({
                'rule': 'file_exists',
                'severity': 'ERROR',
                'message': f"Missing expected file: {s3_key}",
                'path': s3_key
            })
            return False

    def validate_season_completeness(self, season: int, expected_weeks: int) -> bool:
        """Ensure all weeks exist for a season"""
        missing_weeks = []

        for week in range(1, expected_weeks + 1):
            s3_key = f"stats/weekly/season/{season}/week/{week}/data.json"
            try:
                self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            except ClientError:
                missing_weeks.append(week)

        if missing_weeks:
            self.violations.append({
                'rule': 'season_completeness',
                'severity': 'ERROR',
                'message': f"Season {season} missing weeks: {missing_weeks}",
                'season': season,
                'missing_weeks': missing_weeks
            })
            return False

        self.info.append({
            'rule': 'season_completeness',
            'severity': 'INFO',
            'message': f"Season {season} complete: {expected_weeks} weeks",
            'season': season
        })
        return True

    def validate_file_structure(self, s3_key: str, expected_keys: List[str]) -> bool:
        """Validate JSON file has expected top-level structure"""
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            data = json.loads(obj['Body'].read().decode('utf-8'))

            missing_keys = [k for k in expected_keys if k not in data]

            if missing_keys:
                self.violations.append({
                    'rule': 'file_structure',
                    'severity': 'ERROR',
                    'message': f"File missing top-level keys: {missing_keys}",
                    'path': s3_key,
                    'missing_keys': missing_keys
                })
                return False

            return True
        except json.JSONDecodeError as e:
            self.violations.append({
                'rule': 'file_structure',
                'severity': 'ERROR',
                'message': f"Invalid JSON: {str(e)}",
                'path': s3_key
            })
            return False
        except Exception as e:
            self.violations.append({
                'rule': 'file_structure',
                'severity': 'ERROR',
                'message': f"Failed to read file: {str(e)}",
                'path': s3_key
            })
            return False

    # === DATA QUALITY VALIDATIONS ===

    def validate_player_data_schema(self, s3_key: str, required_fields: List[str]) -> bool:
        """Ensure player data has all required fields"""
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            data = json.loads(obj['Body'].read().decode('utf-8'))

            # Check first player for schema
            players = data.get('data', {}).get('players', [])

            if not players:
                self.warnings.append({
                    'rule': 'player_data_schema',
                    'severity': 'WARNING',
                    'message': f"No players found in file",
                    'path': s3_key
                })
                return False

            # Check first non-null player
            sample_player = None
            for player in players[:10]:  # Check first 10 to find valid sample
                if player and isinstance(player, dict):
                    sample_player = player
                    break

            if not sample_player:
                self.violations.append({
                    'rule': 'player_data_schema',
                    'severity': 'ERROR',
                    'message': f"No valid player records found",
                    'path': s3_key
                })
                return False

            missing_fields = [f for f in required_fields if f not in sample_player]

            if missing_fields:
                self.violations.append({
                    'rule': 'player_data_schema',
                    'severity': 'ERROR',
                    'message': f"Players missing required fields: {missing_fields}",
                    'path': s3_key,
                    'missing_fields': missing_fields
                })
                return False

            return True
        except Exception as e:
            self.violations.append({
                'rule': 'player_data_schema',
                'severity': 'ERROR',
                'message': f"Failed to validate schema: {str(e)}",
                'path': s3_key
            })
            return False

    def validate_data_freshness(self, s3_key: str, max_age_hours: int = 24) -> bool:
        """Check if data is fresh (recently updated)"""
        try:
            obj = self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            last_modified = obj['LastModified']
            age = datetime.now(timezone.utc) - last_modified

            age_hours = age.total_seconds() / 3600

            if age_hours > max_age_hours:
                self.warnings.append({
                    'rule': 'data_freshness',
                    'severity': 'WARNING',
                    'message': f"Data is {int(age_hours)} hours old (max: {max_age_hours})",
                    'path': s3_key,
                    'age_hours': round(age_hours, 1)
                })
                return False

            return True
        except Exception as e:
            self.violations.append({
                'rule': 'data_freshness',
                'severity': 'ERROR',
                'message': f"Failed to check freshness: {str(e)}",
                'path': s3_key
            })
            return False

    # === BUSINESS LOGIC VALIDATIONS ===

    def validate_player_count(self, s3_key: str, min_players: int = 800) -> bool:
        """Ensure reasonable number of players (catch truncation issues)"""
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            data = json.loads(obj['Body'].read().decode('utf-8'))

            player_count = len(data.get('data', {}).get('players', []))

            if player_count < min_players:
                self.violations.append({
                    'rule': 'player_count',
                    'severity': 'ERROR',
                    'message': f"Only {player_count} players found (expected {min_players}+)",
                    'path': s3_key,
                    'actual_count': player_count,
                    'expected_min': min_players
                })
                return False

            self.info.append({
                'rule': 'player_count',
                'severity': 'INFO',
                'message': f"Player count OK: {player_count} players",
                'path': s3_key,
                'player_count': player_count
            })
            return True
        except Exception as e:
            self.violations.append({
                'rule': 'player_count',
                'severity': 'ERROR',
                'message': f"Failed to validate player count: {str(e)}",
                'path': s3_key
            })
            return False

    def validate_stat_ranges(self, s3_key: str, stat_ranges: Dict[str, tuple]) -> bool:
        """Validate stats are within reasonable ranges (catch data corruption)"""
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            data = json.loads(obj['Body'].read().decode('utf-8'))

            players = data.get('data', {}).get('players', [])
            outliers = []

            for player in players:
                if not player or not isinstance(player, dict):
                    continue

                for stat, (min_val, max_val) in stat_ranges.items():
                    value = player.get(stat)
                    if value is not None and (value < min_val or value > max_val):
                        outliers.append({
                            'player': player.get('player_name', 'Unknown'),
                            'stat': stat,
                            'value': value,
                            'expected_range': f"{min_val}-{max_val}"
                        })

            if outliers:
                # Only warn for first 5 outliers
                for outlier in outliers[:5]:
                    self.warnings.append({
                        'rule': 'stat_ranges',
                        'severity': 'WARNING',
                        'message': f"Unusual {outlier['stat']}: {outlier['player']} = {outlier['value']} (expected {outlier['expected_range']})",
                        'path': s3_key,
                        'player': outlier['player'],
                        'stat': outlier['stat'],
                        'value': outlier['value']
                    })

            return True
        except Exception as e:
            self.violations.append({
                'rule': 'stat_ranges',
                'severity': 'ERROR',
                'message': f"Failed to validate stat ranges: {str(e)}",
                'path': s3_key
            })
            return False

    def validate_metadata_consistency(self) -> bool:
        """Ensure metadata matches actual data in bucket"""
        try:
            # Read metadata
            metadata_obj = self.s3.get_object(Bucket=self.bucket, Key='stats/metadata.json')
            metadata = json.loads(metadata_obj['Body'].read().decode('utf-8'))

            claimed_season = metadata.get('current_season')
            claimed_weeks = metadata.get('weeks_available', [])

            # Verify claimed weeks actually exist
            missing_claimed_weeks = []
            for week in claimed_weeks:
                s3_key = f"stats/weekly/season/{claimed_season}/week/{week}/data.json"
                try:
                    self.s3.head_object(Bucket=self.bucket, Key=s3_key)
                except ClientError:
                    missing_claimed_weeks.append(week)

            if missing_claimed_weeks:
                self.violations.append({
                    'rule': 'metadata_consistency',
                    'severity': 'ERROR',
                    'message': f"Metadata claims weeks {missing_claimed_weeks} exist but files not found",
                    'claimed_season': claimed_season,
                    'missing_weeks': missing_claimed_weeks
                })
                return False

            return True
        except Exception as e:
            self.violations.append({
                'rule': 'metadata_consistency',
                'severity': 'ERROR',
                'message': f"Failed to validate metadata: {str(e)}"
            })
            return False

    # === AUDIT REPORT GENERATION ===

    def generate_audit_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report"""
        status = 'PASS' if len(self.violations) == 0 else 'FAIL'

        return {
            'audit_timestamp': datetime.now(timezone.utc).isoformat(),
            'bucket': self.bucket,
            'summary': {
                'total_violations': len(self.violations),
                'total_warnings': len(self.warnings),
                'total_checks': len(self.info),
                'status': status
            },
            'violations': self.violations,
            'warnings': self.warnings,
            'checks_passed': self.info
        }
