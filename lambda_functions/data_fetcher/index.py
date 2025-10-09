import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError
import time
import polars as pl

# Import NFL data library and utilities
print(f"Checking for nflreadpy...")

try:
    import nflreadpy as nfl
    NFL_DATA_AVAILABLE = True
    print(f"SUCCESS: nflreadpy loaded from {nfl.__file__}")
    print(f"nflreadpy version: {getattr(nfl, '__version__', 'unknown')}")
except ImportError as e:
    print(f"ERROR: Failed to import nflreadpy: {e}")
    NFL_DATA_AVAILABLE = False
except Exception as e:
    print(f"UNEXPECTED ERROR importing nflreadpy: {e}")
    NFL_DATA_AVAILABLE = False

from utils import (
    transform_weekly_data_to_players,
    aggregate_team_stats,
    transform_schedule_to_games,
    get_current_season,
    get_current_nfl_week,
    dataframe_to_dict_list,
)
from validation import DataValidator

s3_client = boto3.client("s3")


def get_nfl_stats_with_retry(max_retries: int = 3) -> Dict[str, Any]:
    """
    Fetch NFL statistics with retry logic.

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        Dict containing NFL stats data
    """
    for attempt in range(max_retries):
        try:
            return get_nfl_stats()
        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                # Exponential backoff
                sleep_time = 2 ** attempt
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                raise


def get_nfl_stats() -> Dict[str, Any]:
    """
    Fetch NFL statistics using nfl_data_py library.

    Fetches:
    - Weekly player stats for current season
    - Team schedules and records
    - Game results

    Returns:
        Dict containing NFL stats data
    """
    print("Fetching NFL statistics...")

    if not NFL_DATA_AVAILABLE:
        # Return placeholder data if library not available
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "placeholder",
            "data": {
                "players": [],
                "teams": [],
                "games": [],
            },
            "metadata": {
                "fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "season": get_current_season(),
                "week": get_current_nfl_week(),
                "error": "nflreadpy not available",
            },
        }

    try:
        current_season = get_current_season()
        current_week = get_current_nfl_week()

        print(f"Current calculated season: {current_season}, week {current_week}")

        # Try to fetch current season data, with graceful fallback for missing datasets
        try:
            print(f"Attempting to fetch {current_season} season data...")
            weekly_data = nfl.load_player_stats([current_season])
            schedules = nfl.load_schedules([current_season])
            fetch_season = current_season
            print(f"SUCCESS: Fetched {current_season} player stats and schedules")

            # Try to load injuries for current season, fallback to empty if not available
            try:
                injuries = nfl.load_injuries([current_season])
                print(f"SUCCESS: Fetched {current_season} injury data")
            except Exception as injury_error:
                print(f"WARNING: {current_season} injury data not available ({str(injury_error)}), using empty dataset")
                injuries = pl.DataFrame()  # Empty dataframe

            # Projections are always current week regardless of season
            projections = nfl.load_ff_rankings()

        except Exception as e:
            print(f"WARNING: {current_season} core data not available ({str(e)}), falling back to 2024")
            fetch_season = 2024
            weekly_data = nfl.load_player_stats([fetch_season])
            schedules = nfl.load_schedules([fetch_season])
            injuries = nfl.load_injuries([fetch_season])
            projections = nfl.load_ff_rankings()

        # Transform data - return raw weekly data to split by week later
        print("Transforming data...")

        # Get list of unique weeks from the data
        weeks = sorted(weekly_data['week'].unique().to_list()) if not weekly_data.is_empty() else []
        print(f"Found weeks: {weeks}")

        # Process injury data by week
        injury_data_by_week = {}
        if not injuries.is_empty():
            print(f"Processing {len(injuries)} injury records")
            for week in weeks:
                week_injuries = injuries.filter(pl.col('week') == week)
                injury_data_by_week[week] = week_injuries

        # Process projection data - these are current week rankings without week/season columns
        # Only apply to the current week since they represent current expert consensus
        projection_data_by_week = {}
        if not projections.is_empty() and current_week is not None:
            print(f"Processing {len(projections)} projection records for current week {current_week}")
            # Only add projections for the current week
            if current_week in weeks:
                projection_data_by_week[current_week] = projections

        # Create data structure with weekly splits
        weekly_splits = {}
        for week in weeks:
            week_data = weekly_data.filter(pl.col('week') == week)
            week_injuries = injury_data_by_week.get(week)
            week_projections = projection_data_by_week.get(week)

            # Start with base player data
            enriched_data = week_data

            # Join injury data to player stats
            if week_injuries is not None and not week_injuries.is_empty():
                enriched_data = enriched_data.join(
                    week_injuries.select([
                        'gsis_id',
                        'report_status',
                        'report_primary_injury',
                        'report_secondary_injury',
                        'practice_status',
                        'date_modified'
                    ]),
                    left_on='player_id',
                    right_on='gsis_id',
                    how='left'
                )

            # Join projection data to player stats
            # Projections use 'id' not 'player_id', and 'ecr' (expert consensus ranking)
            # Cast id to string to match player_id type
            if week_projections is not None and not week_projections.is_empty():
                enriched_data = enriched_data.join(
                    week_projections.select([
                        pl.col('id').cast(pl.Utf8).alias('id'),
                        'ecr',  # expert consensus ranking
                        'best',  # best ranking
                        'worst',  # worst ranking
                        'sd'  # standard deviation of rankings
                    ]),
                    left_on='player_id',
                    right_on='id',
                    how='left',
                    suffix='_ranking'
                )

            players = transform_weekly_data_to_players(enriched_data, include_all_weeks=False)
            weekly_splits[week] = {
                "players": players,
                "week": week,
                "player_count": len(players)
            }
            print(f"Week {week}: {len(players)} players")

        # Also create aggregated data (teams and games don't vary by week)
        teams = aggregate_team_stats(weekly_data, schedules)
        games = transform_schedule_to_games(schedules)

        print(f"Fetched {len(teams)} teams, {len(games)} games across {len(weeks)} weeks")

        # Process injury data for storage
        injury_snapshots = {}
        for week in weeks:
            week_injuries = injury_data_by_week.get(week)
            if week_injuries is not None and not week_injuries.is_empty():
                injury_snapshots[week] = dataframe_to_dict_list(week_injuries)

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "nflreadpy",
            "weekly_data": weekly_splits,  # Separate data for each week (with injuries joined)
            "aggregated_data": {
                "teams": teams,
                "games": games,
            },
            "injury_data": injury_snapshots,  # Raw injury data by week
            "metadata": {
                "fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "season": fetch_season,
                "current_week": current_week,
                "weeks_available": weeks,
                "team_count": len(teams),
                "game_count": len(games),
            },
        }

        return data

    except Exception as e:
        print(f"Error fetching NFL stats: {str(e)}")
        # Return error data structure
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "nflreadpy",
            "data": {
                "players": [],
                "teams": [],
                "games": [],
            },
            "metadata": {
                "fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "season": get_current_season(),
                "week": get_current_nfl_week(),
                "error": str(e),
            },
        }


def detect_injury_changes(previous_injuries: List[Dict], current_injuries: List[Dict]) -> Dict[str, List]:
    """
    Detect changes in injury status between two snapshots.

    Args:
        previous_injuries: Yesterday's injury list
        current_injuries: Today's injury list

    Returns:
        Dict with categorized changes
    """
    changes = {
        "new_injuries": [],
        "cleared": [],
        "upgraded": [],
        "downgraded": [],
        "status_changed": []
    }

    # Create lookup maps by gsis_id
    prev_map = {inj.get('gsis_id'): inj for inj in previous_injuries if inj.get('gsis_id')}
    curr_map = {inj.get('gsis_id'): inj for inj in current_injuries if inj.get('gsis_id')}

    # Detect new injuries
    for player_id in curr_map:
        if player_id not in prev_map:
            changes["new_injuries"].append(curr_map[player_id])

    # Detect cleared players
    for player_id in prev_map:
        if player_id not in curr_map:
            changes["cleared"].append(prev_map[player_id])

    # Detect status changes for existing injuries
    practice_levels = {"DNP": 1, "Limited": 2, "Full": 3, "": 0, None: 0}

    for player_id in prev_map:
        if player_id in curr_map:
            prev = prev_map[player_id]
            curr = curr_map[player_id]

            # Practice status progression
            prev_level = practice_levels.get(prev.get('practice_status'), 0)
            curr_level = practice_levels.get(curr.get('practice_status'), 0)

            if curr_level > prev_level and prev_level > 0:
                changes["upgraded"].append({
                    "player": curr,
                    "from": prev.get('practice_status'),
                    "to": curr.get('practice_status')
                })
            elif curr_level < prev_level and curr_level > 0:
                changes["downgraded"].append({
                    "player": curr,
                    "from": prev.get('practice_status'),
                    "to": curr.get('practice_status')
                })

            # Report status changed
            if prev.get('report_status') != curr.get('report_status'):
                changes["status_changed"].append({
                    "player": curr,
                    "from": prev.get('report_status'),
                    "to": curr.get('report_status')
                })

    return changes


def save_to_s3(data: Dict[str, Any], bucket_name: str, prefix: str) -> Dict[str, Any]:
    """
    Save NFL stats data to S3 with weekly organization.

    Stores each week's data separately for efficient querying:
    - stats/weekly/season/YYYY/week/W/data.json (player data for each week)
    - stats/aggregated/season/YYYY/teams.json (team stats)
    - stats/aggregated/season/YYYY/games.json (game schedules)
    - stats/metadata.json (current season/week info)

    Args:
        data: NFL stats data with weekly_data and aggregated_data
        bucket_name: S3 bucket name
        prefix: S3 key prefix

    Returns:
        Dict with keys for all saved S3 objects
    """
    now = datetime.now(timezone.utc)
    season = data.get("metadata", {}).get("season")
    saved_keys = {}

    try:
        # Save each week's player data separately
        weekly_data = data.get("weekly_data", {})
        validation_errors_all_weeks = []

        for week, week_info in weekly_data.items():
            week_payload = {
                "timestamp": now.isoformat(),
                "season": season,
                "week": week,
                "data": {
                    "players": week_info["players"]
                },
                "metadata": {
                    "player_count": week_info["player_count"],
                    "fetch_date": data.get("metadata", {}).get("fetch_date"),
                }
            }

            # VALIDATE DATA BEFORE WRITING TO S3
            is_valid, errors = DataValidator.validate_weekly_data(week_payload, week)

            if not is_valid:
                error_msg = f"Week {week} validation FAILED: {errors}"
                print(f"ERROR: {error_msg}")
                validation_errors_all_weeks.append(error_msg)
                # Skip writing invalid data to S3
                continue

            if errors:
                # Has warnings but passed validation
                print(f"Week {week} validation warnings: {errors}")

            # Data is valid - write to S3
            week_key = f"{prefix}weekly/season/{season}/week/{week}/data.json"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=week_key,
                Body=json.dumps(week_payload, indent=2),
                ContentType="application/json",
                Metadata={
                    "fetch_timestamp": now.isoformat(),
                    "data_type": "nfl_weekly_stats",
                    "season": str(season),
                    "week": str(week),
                },
            )
            saved_keys[f"week_{week}"] = week_key
            print(f"✓ Week {week} validated and saved to s3://{bucket_name}/{week_key}")

        # If any week failed validation, raise error
        if validation_errors_all_weeks:
            raise ValueError(f"Data validation failed for {len(validation_errors_all_weeks)} weeks: {validation_errors_all_weeks}")

        # Save aggregated data (teams and games)
        aggregated = data.get("aggregated_data", {})

        # Save teams
        teams_key = f"{prefix}aggregated/season/{season}/teams.json"
        teams_payload = {
            "timestamp": now.isoformat(),
            "season": season,
            "data": {
                "teams": aggregated.get("teams", [])
            },
            "metadata": {
                "team_count": len(aggregated.get("teams", [])),
                "fetch_date": data.get("metadata", {}).get("fetch_date"),
            }
        }
        s3_client.put_object(
            Bucket=bucket_name,
            Key=teams_key,
            Body=json.dumps(teams_payload, indent=2),
            ContentType="application/json",
            Metadata={
                "fetch_timestamp": now.isoformat(),
                "data_type": "nfl_team_stats",
                "season": str(season),
            },
        )
        saved_keys["teams"] = teams_key
        print(f"Saved teams data to s3://{bucket_name}/{teams_key}")

        # Save games
        games_key = f"{prefix}aggregated/season/{season}/games.json"
        games_payload = {
            "timestamp": now.isoformat(),
            "season": season,
            "data": {
                "games": aggregated.get("games", [])
            },
            "metadata": {
                "game_count": len(aggregated.get("games", [])),
                "fetch_date": data.get("metadata", {}).get("fetch_date"),
            }
        }
        s3_client.put_object(
            Bucket=bucket_name,
            Key=games_key,
            Body=json.dumps(games_payload, indent=2),
            ContentType="application/json",
            Metadata={
                "fetch_timestamp": now.isoformat(),
                "data_type": "nfl_game_schedule",
                "season": str(season),
            },
        )
        saved_keys["games"] = games_key
        print(f"Saved games data to s3://{bucket_name}/{games_key}")

        # Save injury data with daily snapshots
        injury_data = data.get("injury_data", {})
        current_week = data.get("metadata", {}).get("current_week")
        fetch_date = data.get("metadata", {}).get("fetch_date")

        for week, week_injuries in injury_data.items():
            # Save daily snapshot in current-week directory
            if week == current_week:
                # Try to fetch yesterday's snapshot for change detection
                previous_injuries = []
                try:
                    yesterday_key = f"{prefix}injuries/current-week/latest.json"
                    response = s3_client.get_object(Bucket=bucket_name, Key=yesterday_key)
                    yesterday_data = json.loads(response['Body'].read().decode('utf-8'))
                    previous_injuries = yesterday_data.get('data', {}).get('injuries', [])
                    print(f"Loaded {len(previous_injuries)} injuries from yesterday")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        print(f"Error loading previous injuries: {e}")
                    # No previous snapshot exists (first run)
                    print("No previous injury snapshot found - skipping change detection")

                # Detect changes
                changes = {}
                if previous_injuries:
                    changes = detect_injury_changes(previous_injuries, week_injuries)
                    print(f"Injury changes detected: {len(changes['new_injuries'])} new, "
                          f"{len(changes['cleared'])} cleared, "
                          f"{len(changes['upgraded'])} upgraded, "
                          f"{len(changes['downgraded'])} downgraded")

                snapshot_key = f"{prefix}injuries/current-week/{fetch_date}.json"
                snapshot_payload = {
                    "fetch_timestamp": now.isoformat(),
                    "fetch_date": fetch_date,
                    "season": season,
                    "week": week,
                    "data": {
                        "injuries": week_injuries
                    },
                    "changes": changes if changes else None,  # Include detected changes
                    "metadata": {
                        "injury_count": len(week_injuries),
                        "changes_detected": bool(changes)
                    }
                }
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=snapshot_key,
                    Body=json.dumps(snapshot_payload, indent=2),
                    ContentType="application/json",
                    Metadata={
                        "fetch_timestamp": now.isoformat(),
                        "data_type": "nfl_injuries_snapshot",
                        "season": str(season),
                        "week": str(week),
                    },
                )
                saved_keys[f"injury_snapshot_{week}"] = snapshot_key
                print(f"Saved injury snapshot for week {week} to s3://{bucket_name}/{snapshot_key}")

                # Also save as "latest" for current week
                latest_key = f"{prefix}injuries/current-week/latest.json"
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=latest_key,
                    Body=json.dumps(snapshot_payload, indent=2),
                    ContentType="application/json",
                )
                saved_keys["injury_latest"] = latest_key

                # Save changes separately for easy API access
                if changes and any(len(v) > 0 for v in changes.values()):
                    changes_key = f"{prefix}injuries/current-week/changes.json"
                    changes_payload = {
                        "fetch_timestamp": now.isoformat(),
                        "fetch_date": fetch_date,
                        "season": season,
                        "week": week,
                        "changes": changes
                    }
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=changes_key,
                        Body=json.dumps(changes_payload, indent=2),
                        ContentType="application/json",
                    )
                    saved_keys["injury_changes"] = changes_key
                    print(f"Saved injury changes to s3://{bucket_name}/{changes_key}")

            # Save final injury status for completed weeks
            final_key = f"{prefix}injuries/season/{season}/week/{week}/final.json"
            final_payload = {
                "timestamp": now.isoformat(),
                "season": season,
                "week": week,
                "data": {
                    "injuries": week_injuries
                },
                "metadata": {
                    "injury_count": len(week_injuries),
                    "fetch_date": fetch_date,
                }
            }
            s3_client.put_object(
                Bucket=bucket_name,
                Key=final_key,
                Body=json.dumps(final_payload, indent=2),
                ContentType="application/json",
                Metadata={
                    "fetch_timestamp": now.isoformat(),
                    "data_type": "nfl_injuries_final",
                    "season": str(season),
                    "week": str(week),
                },
            )
            saved_keys[f"injury_week_{week}"] = final_key
            print(f"Saved injury final for week {week} to s3://{bucket_name}/{final_key}")

        # Save metadata file for easy lookup of current season/week
        metadata_payload = {
            "timestamp": now.isoformat(),
            "current_season": season,
            "current_week": data.get("metadata", {}).get("current_week"),
            "weeks_available": data.get("metadata", {}).get("weeks_available", []),
            "last_updated": now.isoformat(),
        }

        # VALIDATE METADATA BEFORE WRITING TO S3
        is_valid, errors = DataValidator.validate_metadata(metadata_payload)

        if not is_valid:
            raise ValueError(f"Metadata validation FAILED: {errors}")

        if errors:
            print(f"Metadata validation warnings: {errors}")

        # Metadata is valid - write to S3
        metadata_key = f"{prefix}metadata.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(metadata_payload, indent=2),
            ContentType="application/json",
            Metadata={
                "fetch_timestamp": now.isoformat(),
                "data_type": "nfl_metadata",
            },
        )
        saved_keys["metadata"] = metadata_key
        print(f"✓ Metadata validated and saved to s3://{bucket_name}/{metadata_key}")

        return saved_keys

    except ClientError as e:
        print(f"Error saving to S3: {e}")
        raise


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for NFL stats data fetcher.

    Triggered by EventBridge daily schedule to fetch and store NFL stats.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response dict with status and details
    """
    print(f"Data fetcher invoked at {datetime.now(timezone.utc).isoformat()}")
    print(f"Event: {json.dumps(event)}")

    bucket_name = os.environ.get("BUCKET_NAME")
    data_prefix = os.environ.get("DATA_PREFIX", "stats/")

    if not bucket_name:
        raise ValueError("BUCKET_NAME environment variable not set")

    try:
        # Fetch NFL stats with retry logic
        print("Fetching NFL statistics...")
        stats_data = get_nfl_stats_with_retry(max_retries=3)

        # Save to S3
        print(f"Saving data to S3 bucket: {bucket_name}")
        saved_keys = save_to_s3(stats_data, bucket_name, data_prefix)

        response = {
            "statusCode": 200,
            "body": json.dumps({
                "message": "NFL stats fetched and stored successfully",
                "s3_keys": saved_keys,
                "bucket": bucket_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": stats_data.get("metadata", {}),
            })
        }

        print(f"Data fetch completed successfully. Saved {len(saved_keys)} S3 objects")
        return response

    except Exception as e:
        error_msg = f"Error fetching NFL stats: {str(e)}"
        print(error_msg)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Failed to fetch NFL stats",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        }
