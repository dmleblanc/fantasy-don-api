import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client("s3")


def get_metadata(bucket_name: str, prefix: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve metadata about current NFL season/week from S3.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix

    Returns:
        Metadata dict or None if not found
    """
    try:
        metadata_key = f"{prefix}metadata.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No metadata found at {metadata_key}")
            return None
        raise


def get_weekly_stats(bucket_name: str, prefix: str, season: int, week: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve NFL stats for a specific week from S3.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        season: NFL season year
        week: NFL week number

    Returns:
        Weekly stats data or None if not found
    """
    try:
        week_key = f"{prefix}weekly/season/{season}/week/{week}/data.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=week_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No data found for season {season} week {week}")
            return None
        raise


def get_latest_stats(bucket_name: str, prefix: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the latest NFL stats from S3 (current week).
    Reads from stats/latest.json which contains the most recent week's data.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix

    Returns:
        Latest stats data or None if not found
    """
    try:
        # Try to read from latest.json first (most efficient)
        latest_key = f"{prefix}latest.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=latest_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            # Fallback: read from metadata and get current week
            print("latest.json not found, falling back to metadata lookup")
            metadata = get_metadata(bucket_name, prefix)
            if not metadata:
                return None

            season = metadata.get("current_season")
            week = metadata.get("current_week")

            if not season or not week:
                return None

            # Get the current week's data
            return get_weekly_stats(bucket_name, prefix, season, week)

        # Other errors - raise them
        print(f"Error retrieving latest stats: {e}")
        return None


def get_stats_by_date(bucket_name: str, prefix: str, date_str: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve NFL stats for a specific date.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        date_str: Date in YYYY-MM-DD format

    Returns:
        Stats data for the date or None if not found
    """
    try:
        # Parse date
        date = datetime.strptime(date_str, "%Y-%m-%d")
        search_prefix = f"{prefix}{date.year}/{date.month:02d}/{date.day:02d}/"

        # List objects for that date
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=search_prefix)

        if "Contents" not in response or len(response["Contents"]) == 0:
            return None

        # Get the most recent file for that date
        latest_object = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)[0]

        # Retrieve the object
        obj_response = s3_client.get_object(Bucket=bucket_name, Key=latest_object["Key"])
        data = json.loads(obj_response["Body"].read().decode("utf-8"))

        return data

    except ValueError as e:
        print(f"Invalid date format: {date_str}")
        raise
    except ClientError as e:
        print(f"Error retrieving stats for date {date_str}: {e}")
        raise


def filter_player_stats(data: Dict[str, Any], player_id: str) -> Optional[Dict[str, Any]]:
    """
    Filter stats data for a specific player.

    Args:
        data: Full stats data
        player_id: Player ID to filter for

    Returns:
        Player-specific stats or None if not found
    """
    players = data.get("data", {}).get("players", [])

    for player in players:
        if str(player.get("id")) == player_id or player.get("name", "").lower() == player_id.lower():
            return {
                "timestamp": data.get("timestamp"),
                "player": player,
                "metadata": data.get("metadata"),
            }

    return None


def filter_team_stats(data: Dict[str, Any], team_id: str) -> Optional[Dict[str, Any]]:
    """
    Filter stats data for a specific team.

    Args:
        data: Full stats data
        team_id: Team ID or abbreviation to filter for

    Returns:
        Team-specific stats or None if not found
    """
    teams = data.get("data", {}).get("teams", [])

    for team in teams:
        if (
            str(team.get("id")) == team_id
            or team.get("abbreviation", "").lower() == team_id.lower()
            or team.get("name", "").lower() == team_id.lower()
        ):
            return {
                "timestamp": data.get("timestamp"),
                "team": team,
                "metadata": data.get("metadata"),
            }

    return None


def get_injury_data(bucket_name: str, prefix: str, data_type: str = "latest") -> Optional[Dict[str, Any]]:
    """
    Retrieve injury data from S3.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        data_type: Type of injury data - "latest", "changes", or "week/{week}"

    Returns:
        Injury data or None if not found
    """
    try:
        if data_type == "latest":
            injury_key = f"{prefix}injuries/current-week/latest.json"
        elif data_type == "changes":
            injury_key = f"{prefix}injuries/current-week/changes.json"
        elif data_type.startswith("week/"):
            # Get metadata to find season
            metadata = get_metadata(bucket_name, prefix)
            if not metadata:
                return None
            season = metadata.get("current_season")
            week = data_type.split("/")[1]
            injury_key = f"{prefix}injuries/season/{season}/week/{week}/final.json"
        else:
            return None

        response = s3_client.get_object(Bucket=bucket_name, Key=injury_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No injury data found at {injury_key}")
            return None
        raise


def get_insights(bucket_name: str, prefix: str, season: int, week: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve insights for a specific week from S3.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        season: NFL season year
        week: NFL week number

    Returns:
        Insights data or None if not found
    """
    try:
        insights_key = f"insights/season/{season}/week/{week}/insights.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=insights_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No insights found for season {season} week {week}")
            return None
        raise


def get_latest_insights(bucket_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve latest insights from S3.

    Args:
        bucket_name: S3 bucket name

    Returns:
        Latest insights data or None if not found
    """
    try:
        insights_key = "insights/latest.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=insights_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print("No latest insights found")
            return None
        raise


def get_superlatives(bucket_name: str, season: int, week: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve superlatives for a specific week from S3.

    Args:
        bucket_name: S3 bucket name
        season: NFL season year
        week: NFL week number

    Returns:
        Superlatives data or None if not found
    """
    try:
        superlatives_key = f"insights/season/{season}/week/{week}/superlatives.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=superlatives_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No superlatives found for season {season} week {week}")
            return None
        raise


def get_comparison_insights(bucket_name: str, season: int, week_from: int, week_to: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve pre-calculated insights comparing two weeks.

    Args:
        bucket_name: S3 bucket name
        season: NFL season year
        week_from: Starting week
        week_to: Ending week

    Returns:
        Comparison insights data or None if not found
    """
    try:
        insights_key = f"insights/season/{season}/comparisons/{week_from}-to-{week_to}/insights.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=insights_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No comparison insights found for S{season} W{week_from}→W{week_to}")
            return None
        raise


def get_comparison_superlatives(bucket_name: str, season: int, week_from: int, week_to: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve pre-calculated superlatives comparing two weeks.

    Args:
        bucket_name: S3 bucket name
        season: NFL season year
        week_from: Starting week
        week_to: Ending week

    Returns:
        Comparison superlatives data or None if not found
    """
    try:
        superlatives_key = f"insights/season/{season}/comparisons/{week_from}-to-{week_to}/superlatives.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=superlatives_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No comparison superlatives found for S{season} W{week_from}→W{week_to}")
            return None
        raise


def get_comparisons_summary(bucket_name: str, season: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve summary of all available week comparisons for a season.

    Args:
        bucket_name: S3 bucket name
        season: NFL season year

    Returns:
        Summary data with all available comparisons
    """
    try:
        summary_key = f"insights/season/{season}/comparisons/summary.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=summary_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No comparisons summary found for S{season}")
            return None
        raise


def filter_player_insights(insights_data: Dict[str, Any], player_id: str) -> Optional[Dict[str, Any]]:
    """
    Filter insights data to get a specific player's insights.

    Args:
        insights_data: Full insights data
        player_id: Player ID to filter for

    Returns:
        Player-specific insights or None if not found
    """
    player_insights = insights_data.get("player_insights", [])
    for insight in player_insights:
        if insight.get("player_id") == player_id:
            return {
                "season": insights_data.get("season"),
                "week": insights_data.get("week"),
                "player_insight": insight
            }
    return None


def get_current_week_info() -> Dict[str, Any]:
    """
    Get current NFL week and season information from metadata.

    Returns:
        Dict with current season, week, and metadata
    """
    bucket_name = os.environ.get("BUCKET_NAME", "nfl-stats")
    prefix = os.environ.get("DATA_PREFIX", "stats/")

    # Read from metadata file (source of truth)
    metadata = get_metadata(bucket_name, prefix)

    if metadata:
        season = metadata.get("current_season")
        week = metadata.get("current_week")
    else:
        # Fallback to calculation if metadata not available
        from utils import get_current_season, get_current_nfl_week
        season = get_current_season()
        week = get_current_nfl_week()

    return {
        "season": season,
        "week": week,
        "is_regular_season": week is not None and week <= 18,
        "season_start_date": f"{season}-09-07",  # Approximate start
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_games_data(bucket_name: str, prefix: str, season: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve game schedule data for a season from S3.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        season: NFL season year

    Returns:
        Games data or None if not found
    """
    try:
        games_key = f"{prefix}aggregated/season/{season}/games.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=games_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"No games data found at {games_key}")
            return None
        raise


def get_available_weeks_for_season(bucket_name: str, prefix: str, season: int) -> list:
    """
    Get list of available weeks for a given season by listing S3 objects.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        season: NFL season year

    Returns:
        List of available week numbers
    """
    try:
        season_prefix = f"{prefix}weekly/season/{season}/week/"
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=season_prefix, Delimiter='/')

        weeks = []
        if 'CommonPrefixes' in response:
            for obj in response['CommonPrefixes']:
                # Extract week number from prefix like "stats/weekly/season/2025/week/5/"
                week_str = obj['Prefix'].rstrip('/').split('/')[-1]
                try:
                    weeks.append(int(week_str))
                except ValueError:
                    continue

        return sorted(weeks)
    except ClientError as e:
        print(f"Error listing weeks for season {season}: {e}")
        return []


def aggregate_season_stats(bucket_name: str, prefix: str, season: int, weeks: list) -> Dict[str, Any]:
    """
    Aggregate player stats across multiple weeks in a season.

    Sums all counting stats (yards, TDs, attempts, etc.) for each player.
    Averages are calculated from the summed totals.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 key prefix
        season: NFL season year
        weeks: List of week numbers to aggregate

    Returns:
        Dict with aggregated player stats
    """
    from collections import defaultdict

    # Fields to sum across weeks
    summed_fields = [
        "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
        "sacks_suffered", "sack_yards_lost", "sack_fumbles", "sack_fumbles_lost",
        "passing_air_yards", "passing_yards_after_catch", "passing_first_downs",
        "passing_2pt_conversions", "carries", "rushing_yards", "rushing_tds",
        "rushing_fumbles", "rushing_fumbles_lost", "rushing_first_downs",
        "rushing_2pt_conversions", "receptions", "targets", "receiving_yards",
        "receiving_tds", "receiving_fumbles", "receiving_fumbles_lost",
        "receiving_air_yards", "receiving_yards_after_catch", "receiving_first_downs",
        "receiving_epa", "receiving_2pt_conversions", "racr", "target_share",
        "air_yards_share", "wopr", "special_teams_tds", "fantasy_points",
        "fantasy_points_ppr"
    ]

    player_aggregates = defaultdict(lambda: {
        "weeks_played": 0,
        "teams": set(),
        "positions": set(),
    })

    # Fetch and aggregate data from each week
    for week in weeks:
        week_data = get_weekly_stats(bucket_name, prefix, season, week)
        if not week_data:
            continue

        players = week_data.get("data", {}).get("players", [])

        for player in players:
            player_id = player.get("player_id")
            if not player_id:
                continue

            agg = player_aggregates[player_id]

            # Store player identity info (from most recent week)
            if agg["weeks_played"] == 0:
                agg["player_id"] = player_id
                agg["player_name"] = player.get("player_name")
                agg["player_display_name"] = player.get("player_display_name")
                agg["position"] = player.get("position")
                agg["position_group"] = player.get("position_group")
                agg["headshot_url"] = player.get("headshot_url")

            # Track weeks played and teams
            agg["weeks_played"] += 1
            if player.get("team"):
                agg["teams"].add(player.get("team"))
            if player.get("position"):
                agg["positions"].add(player.get("position"))

            # Sum all counting stats
            for field in summed_fields:
                value = player.get(field)
                if value is not None and value != "":
                    if field not in agg:
                        agg[field] = 0
                    agg[field] += float(value) if isinstance(value, (int, float, str)) and value != "" else 0

    # Convert to list and clean up
    aggregated_players = []
    for player_id, agg in player_aggregates.items():
        # Convert sets to comma-separated strings
        agg["teams"] = ",".join(sorted(agg["teams"]))
        agg["positions"] = ",".join(sorted(agg["positions"]))

        # Calculate per-game averages for key stats
        if agg["weeks_played"] > 0:
            agg["passing_yards_per_game"] = round(agg.get("passing_yards", 0) / agg["weeks_played"], 2)
            agg["rushing_yards_per_game"] = round(agg.get("rushing_yards", 0) / agg["weeks_played"], 2)
            agg["receiving_yards_per_game"] = round(agg.get("receiving_yards", 0) / agg["weeks_played"], 2)
            agg["fantasy_points_per_game"] = round(agg.get("fantasy_points_ppr", 0) / agg["weeks_played"], 2)

        aggregated_players.append(agg)

    # Sort by fantasy points (descending)
    aggregated_players.sort(key=lambda x: x.get("fantasy_points_ppr", 0), reverse=True)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "weeks_aggregated": weeks,
        "data": {
            "players": aggregated_players
        },
        "metadata": {
            "player_count": len(aggregated_players),
            "weeks_included": len(weeks),
            "aggregation_type": "sum"
        }
    }


def create_response(status_code: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Create API Gateway response.

    Args:
        status_code: HTTP status code
        body: Response body (will be JSON stringified)
        headers: Optional additional headers

    Returns:
        API Gateway response dict
    """
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body) if not isinstance(body, str) else body,
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for NFL Stats API.

    Routes:
        GET /stats/latest - Get latest week stats (current week)
        GET /stats/season-totals - Get aggregated stats for all weeks in current season
        GET /stats/season/{season}/totals - Get aggregated stats for specific season
        GET /stats/week/{week} - Get stats for specific week (current season)
        GET /stats/season/{season}/week/{week} - Get stats for specific season and week
        GET /stats/{date} - Get stats for specific date (YYYY-MM-DD) [DEPRECATED]
        GET /stats/player/{player_id} - Get player-specific stats from latest week
        GET /stats/team/{team_id} - Get team-specific stats
        GET /week/current - Get current NFL week and season
        GET /injuries/current - Get current injury report
        GET /injuries/changes - Get injury status changes from yesterday
        GET /injuries/week/{week} - Get injury report for specific week
        GET /games/season/{season} - Get all games for a specific season
        GET /insights/latest - Get latest weekly insights
        GET /insights/week/{week} - Get insights for specific week (current season)
        GET /insights/season/{season}/week/{week} - Get insights for specific season/week
        GET /insights/player/{player_id} - Get player-specific insights from latest week
        GET /superlatives/latest - Get latest superlatives
        GET /superlatives/week/{week} - Get superlatives for specific week (current season)
        GET /superlatives/season/{season}/week/{week} - Get superlatives for specific season/week

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    print(f"API request: {json.dumps(event)}")

    bucket_name = os.environ.get("BUCKET_NAME")
    data_prefix = os.environ.get("DATA_PREFIX", "stats/")

    if not bucket_name:
        return create_response(500, {"error": "BUCKET_NAME environment variable not set"})

    try:
        # Parse request
        http_method = event.get("httpMethod", "GET")
        path = event.get("path", "")
        path_parameters = event.get("pathParameters", {}) or {}

        print(f"Method: {http_method}, Path: {path}, Params: {path_parameters}")

        # Route handling
        if "/week/current" in path:
            # Get current NFL week info (no S3 access needed)
            week_info = get_current_week_info()
            return create_response(200, week_info)

        elif "/injuries/current" in path:
            # Get current injury report
            injury_data = get_injury_data(bucket_name, data_prefix, "latest")
            if injury_data:
                return create_response(200, injury_data)
            else:
                return create_response(404, {"error": "No injury data available"})

        elif "/injuries/changes" in path:
            # Get injury status changes
            changes_data = get_injury_data(bucket_name, data_prefix, "changes")
            if changes_data:
                return create_response(200, changes_data)
            else:
                return create_response(404, {"error": "No injury changes detected today"})

        elif "/injuries/week/" in path:
            # Get injury report for specific week
            week = path_parameters.get("week")
            if not week:
                return create_response(400, {"error": "Week number required"})

            injury_data = get_injury_data(bucket_name, data_prefix, f"week/{week}")
            if injury_data:
                return create_response(200, injury_data)
            else:
                return create_response(404, {"error": f"No injury data found for week {week}"})

        elif "/games/season/" in path:
            # Get all games for a specific season
            season = path_parameters.get("season")
            if not season:
                return create_response(400, {"error": "Season required"})

            try:
                season = int(season)
            except ValueError:
                return create_response(400, {"error": "Invalid season format"})

            games_data = get_games_data(bucket_name, data_prefix, season)
            if games_data:
                return create_response(200, games_data)
            else:
                return create_response(404, {"error": f"No games found for season {season}"})

        elif "/stats/season-totals" in path:
            # Get aggregated stats for all weeks in current season
            metadata = get_metadata(bucket_name, data_prefix)
            if not metadata:
                return create_response(404, {"error": "Metadata not available"})

            season = metadata.get("current_season")
            weeks_available = metadata.get("weeks_available", [])

            if not weeks_available:
                return create_response(404, {"error": "No weekly data available"})

            # Aggregate across all available weeks
            aggregated_data = aggregate_season_stats(bucket_name, data_prefix, season, weeks_available)
            return create_response(200, aggregated_data)

        elif "/stats/season/" in path and "/totals" in path:
            # Get aggregated stats for specific season
            season = path_parameters.get("season")
            if not season:
                return create_response(400, {"error": "Season required"})

            try:
                season_int = int(season)
            except ValueError:
                return create_response(400, {"error": "Season must be a number"})

            # Get available weeks for this season from S3
            weeks_available = get_available_weeks_for_season(bucket_name, data_prefix, season_int)

            if not weeks_available:
                return create_response(404, {"error": f"No data available for season {season}"})

            # Aggregate across all available weeks for this season
            aggregated_data = aggregate_season_stats(bucket_name, data_prefix, season_int, weeks_available)
            return create_response(200, aggregated_data)

        elif "/stats/season/" in path and "/week/" in path:
            # Get stats for specific season and week
            season = path_parameters.get("season")
            week = path_parameters.get("week")

            if not season or not week:
                return create_response(400, {"error": "Season and week required"})

            try:
                season_int = int(season)
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Season and week must be numbers"})

            data = get_weekly_stats(bucket_name, data_prefix, season_int, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No stats found for season {season} week {week}"})

        elif "/stats/week/" in path:
            # Get stats for specific week (current season)
            week = path_parameters.get("week")
            if not week:
                return create_response(400, {"error": "Week number required"})

            try:
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Week must be a number"})

            # Get current season from metadata
            metadata = get_metadata(bucket_name, data_prefix)
            if not metadata:
                return create_response(404, {"error": "Metadata not available"})

            season = metadata.get("current_season")
            data = get_weekly_stats(bucket_name, data_prefix, season, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No stats found for week {week}"})

        elif "/stats/latest" in path:
            # Get latest stats (current week)
            data = get_latest_stats(bucket_name, data_prefix)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": "No stats data available"})

        elif "/stats/player/" in path:
            # Get player-specific stats from latest week
            player_id = path_parameters.get("player_id")
            if not player_id:
                return create_response(400, {"error": "Player ID required"})

            latest_data = get_latest_stats(bucket_name, data_prefix)
            if not latest_data:
                return create_response(404, {"error": "No stats data available"})

            player_data = filter_player_stats(latest_data, player_id)
            if player_data:
                return create_response(200, player_data)
            else:
                return create_response(404, {"error": f"Player {player_id} not found"})

        elif "/stats/team/" in path:
            # Get team-specific stats
            team_id = path_parameters.get("team_id")
            if not team_id:
                return create_response(400, {"error": "Team ID required"})

            latest_data = get_latest_stats(bucket_name, data_prefix)
            if not latest_data:
                return create_response(404, {"error": "No stats data available"})

            team_data = filter_team_stats(latest_data, team_id)
            if team_data:
                return create_response(200, team_data)
            else:
                return create_response(404, {"error": f"Team {team_id} not found"})

        # === INSIGHTS ENDPOINTS ===
        elif "/insights/latest" in path:
            # Get latest insights
            data = get_latest_insights(bucket_name)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": "No insights available"})

        elif "/insights/season/" in path and "/week/" in path:
            # Get insights for specific season/week
            season = path_parameters.get("season")
            week = path_parameters.get("week")
            if not season or not week:
                return create_response(400, {"error": "Season and week required"})

            try:
                season_int = int(season)
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Season and week must be numbers"})

            data = get_insights(bucket_name, data_prefix, season_int, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No insights found for season {season} week {week}"})

        elif "/insights/week/" in path:
            # Get insights for specific week (current season)
            week = path_parameters.get("week")
            if not week:
                return create_response(400, {"error": "Week number required"})

            try:
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Week must be a number"})

            # Get current season from metadata
            metadata = get_metadata(bucket_name, data_prefix)
            if not metadata:
                return create_response(404, {"error": "Metadata not available"})

            season = metadata.get("current_season")
            data = get_insights(bucket_name, data_prefix, season, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No insights found for week {week}"})

        elif "/insights/player/" in path:
            # Get player-specific insights from latest week
            player_id = path_parameters.get("player_id")
            if not player_id:
                return create_response(400, {"error": "Player ID required"})

            latest_insights = get_latest_insights(bucket_name)
            if not latest_insights:
                return create_response(404, {"error": "No insights available"})

            player_insights = filter_player_insights(latest_insights, player_id)
            if player_insights:
                return create_response(200, player_insights)
            else:
                return create_response(404, {"error": f"Player {player_id} not found in insights"})

        # === SUPERLATIVES ENDPOINTS ===
        elif "/superlatives/latest" in path:
            # Get latest superlatives
            metadata = get_metadata(bucket_name, data_prefix)
            if not metadata:
                return create_response(404, {"error": "Metadata not available"})

            season = metadata.get("current_season")
            week = metadata.get("current_week")
            data = get_superlatives(bucket_name, season, week)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": "No superlatives available"})

        elif "/superlatives/season/" in path and "/week/" in path:
            # Get superlatives for specific season/week
            season = path_parameters.get("season")
            week = path_parameters.get("week")
            if not season or not week:
                return create_response(400, {"error": "Season and week required"})

            try:
                season_int = int(season)
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Season and week must be numbers"})

            data = get_superlatives(bucket_name, season_int, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No superlatives found for season {season} week {week}"})

        elif "/superlatives/week/" in path:
            # Get superlatives for specific week (current season)
            week = path_parameters.get("week")
            if not week:
                return create_response(400, {"error": "Week number required"})

            try:
                week_int = int(week)
            except ValueError:
                return create_response(400, {"error": "Week must be a number"})

            # Get current season from metadata
            metadata = get_metadata(bucket_name, data_prefix)
            if not metadata:
                return create_response(404, {"error": "Metadata not available"})

            season = metadata.get("current_season")
            data = get_superlatives(bucket_name, season, week_int)
            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No superlatives found for week {week}"})

        elif path_parameters.get("date"):
            # Get stats by date (DEPRECATED - kept for backward compatibility)
            date_str = path_parameters.get("date")
            data = get_stats_by_date(bucket_name, data_prefix, date_str)

            if data:
                return create_response(200, data)
            else:
                return create_response(404, {"error": f"No stats found for date {date_str}"})

        else:
            return create_response(400, {"error": "Invalid endpoint"})

    except ValueError as e:
        return create_response(400, {"error": f"Invalid request: {str(e)}"})
    except Exception as e:
        print(f"Error processing request: {e}")
        return create_response(500, {"error": "Internal server error", "details": str(e)})
