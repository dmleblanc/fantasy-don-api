"""
S3 Persistence Layer for Insights Engine
Handles reading weekly stats and writing insights to S3
"""

import json
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from botocore.exceptions import ClientError


class S3Persistence:
    """Manages all S3 read/write operations for insights engine"""

    def __init__(self, bucket_name: str, data_prefix: str = "stats/"):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name
        self.data_prefix = data_prefix
        self.insights_prefix = "insights/"

    # === READ OPERATIONS ===

    def read_weekly_stats(self, season: int, week: int) -> Optional[Dict[str, Any]]:
        """
        Read weekly player stats from S3
        Path: stats/weekly/season/{season}/week/{week}/data.json
        """
        key = f"{self.data_prefix}weekly/season/{season}/week/{week}/data.json"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Read weekly stats for S{season}W{week}: {len(data.get('data', []))} players")
            return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"⚠ No weekly stats found for S{season}W{week} (key: {key})")
                return None
            raise

    def read_multiple_weeks(self, season: int, weeks: List[int]) -> Dict[int, Optional[Dict]]:
        """
        Read multiple weeks of data in parallel
        Returns: {week: data} mapping
        """
        results = {}
        for week in weeks:
            results[week] = self.read_weekly_stats(season, week)
        return results

    def read_season_totals(self, season: int) -> Optional[Dict[str, Any]]:
        """
        Read aggregated season totals
        Path: stats/aggregated/season/{season}/season-totals.json
        """
        key = f"{self.data_prefix}aggregated/season/{season}/season-totals.json"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"⚠ No season totals found for S{season}")
                return None
            raise

    def read_player_delta_history(self, player_id: str, season: int) -> Optional[Dict[str, Any]]:
        """
        Read historical delta data for a player
        Path: insights/season/{season}/deltas/{player_id}.json
        """
        key = f"{self.insights_prefix}season/{season}/deltas/{player_id}.json"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # First time tracking this player - return empty structure
                return {
                    'player_id': player_id,
                    'season': season,
                    'weekly_snapshots': [],
                    'deltas': [],
                    'last_updated': datetime.utcnow().isoformat()
                }
            raise

    def read_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Read metadata file to get current season/week
        Path: stats/metadata.json
        """
        key = f"{self.data_prefix}metadata.json"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"⚠ No metadata file found")
                return None
            raise

    # === WRITE OPERATIONS ===

    def write_insights(self, insights_data: Dict[str, Any], season: int, week: int):
        """
        Write weekly insights to S3
        Path: insights/season/{season}/week/{week}/insights.json
        """
        key = f"{self.insights_prefix}season/{season}/week/{week}/insights.json"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(insights_data, indent=2),
                ContentType='application/json'
            )
            print(f"✓ Wrote insights for S{season}W{week} to s3://{self.bucket_name}/{key}")
        except Exception as e:
            print(f"✗ Failed to write insights: {e}")
            raise

    def write_player_delta(self, delta_data: Dict[str, Any], player_id: str, season: int):
        """
        Write player delta history to S3
        Path: insights/season/{season}/deltas/{player_id}.json
        """
        key = f"{self.insights_prefix}season/{season}/deltas/{player_id}.json"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(delta_data, indent=2),
                ContentType='application/json'
            )
        except Exception as e:
            print(f"✗ Failed to write player delta for {player_id}: {e}")
            raise

    def write_superlatives(self, superlatives: List[Dict], season: int, week: int):
        """
        Write weekly superlatives to dedicated file
        Path: insights/season/{season}/week/{week}/superlatives.json
        """
        key = f"{self.insights_prefix}season/{season}/week/{week}/superlatives.json"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps({
                    'season': season,
                    'week': week,
                    'superlatives': superlatives,
                    'timestamp': datetime.utcnow().isoformat()
                }, indent=2),
                ContentType='application/json'
            )
            print(f"✓ Wrote {len(superlatives)} superlatives for S{season}W{week}")
        except Exception as e:
            print(f"✗ Failed to write superlatives: {e}")
            raise

    def write_latest_insights(self, insights_data: Dict[str, Any]):
        """
        Write latest insights to a convenience endpoint
        Path: insights/latest.json
        """
        key = f"{self.insights_prefix}latest.json"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(insights_data, indent=2),
                ContentType='application/json'
            )
            print(f"✓ Wrote latest insights snapshot")
        except Exception as e:
            print(f"✗ Failed to write latest insights: {e}")
            raise

    # === UTILITY OPERATIONS ===

    def check_week_exists(self, season: int, week: int) -> bool:
        """Check if weekly stats exist for given season/week"""
        key = f"{self.data_prefix}weekly/season/{season}/week/{week}/data.json"
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def get_available_weeks(self, season: int) -> List[int]:
        """Get list of available weeks for a season"""
        prefix = f"{self.data_prefix}weekly/season/{season}/week/"
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            weeks = []
            for prefix_info in response.get('CommonPrefixes', []):
                # Extract week number from path like "stats/weekly/season/2024/week/1/"
                week_path = prefix_info['Prefix'].rstrip('/')
                week = int(week_path.split('/')[-1])
                weeks.append(week)
            return sorted(weeks)
        except Exception as e:
            print(f"✗ Failed to list available weeks: {e}")
            return []
