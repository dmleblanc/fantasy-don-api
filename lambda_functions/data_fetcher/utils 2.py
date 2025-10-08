"""
Utility functions for NFL stats data fetcher.

Helper functions for:
- Data validation
- Data transformation from polars DataFrames to JSON
- NFL stats parsing
- Season/week calculations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import polars as pl


def validate_stats_data(data: Dict[str, Any]) -> bool:
    """
    Validate NFL stats data structure.

    Args:
        data: Stats data to validate

    Returns:
        True if valid, False otherwise
    """
    required_keys = ["timestamp", "data", "metadata"]
    return all(key in data for key in required_keys)


def dataframe_to_dict_list(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert polars DataFrame to list of dictionaries with proper type handling.

    Args:
        df: Polars DataFrame

    Returns:
        List of dictionaries with JSON-serializable types
    """
    if df is None or df.is_empty():
        return []

    # Convert to list of dicts (polars handles null values properly)
    return df.to_dicts()


def transform_weekly_data_to_players(weekly_df: pl.DataFrame) -> List[Dict[str, Any]]:
    """
    Transform weekly player DataFrame into standardized player format.

    Groups by player_id to return latest week stats for each player.
    This keeps the response size manageable (< 6MB Lambda limit).

    Note: All weekly data is still stored in S3, just grouped here for /latest endpoint.

    Args:
        weekly_df: DataFrame from nflreadpy.import_weekly_data()

    Returns:
        List of player dictionaries (one per player, latest week only)
    """
    if weekly_df is None or weekly_df.is_empty():
        return []

    # Group by player to get latest week stats (keeps response < 6MB)
    latest_week = weekly_df.group_by('player_id').last()

    return dataframe_to_dict_list(latest_week)


def aggregate_team_stats(weekly_df: pl.DataFrame, schedules_df: pl.DataFrame) -> List[Dict[str, Any]]:
    """
    Aggregate team-level statistics from player and schedule data.

    Args:
        weekly_df: Weekly player stats DataFrame
        schedules_df: Schedule DataFrame

    Returns:
        List of team statistics dictionaries
    """
    if schedules_df is None or schedules_df.is_empty():
        return []

    # Get unique teams from schedule
    teams = set()
    if 'home_team' in schedules_df.columns:
        teams.update(schedules_df['home_team'].unique().to_list())
    if 'away_team' in schedules_df.columns:
        teams.update(schedules_df['away_team'].unique().to_list())

    team_stats = []
    for team in teams:
        if team is None:
            continue

        # Filter for team games
        team_games = schedules_df.filter(
            (pl.col('home_team') == team) | (pl.col('away_team') == team)
        )

        # Calculate wins/losses
        wins = 0
        losses = 0

        for row in team_games.iter_rows(named=True):
            home_score = row.get('home_score')
            away_score = row.get('away_score')

            if home_score is not None and away_score is not None:
                if row['home_team'] == team:
                    if home_score > away_score:
                        wins += 1
                    else:
                        losses += 1
                else:
                    if away_score > home_score:
                        wins += 1
                    else:
                        losses += 1

        team_stats.append({
            'team_abbr': team,
            'wins': wins,
            'losses': losses,
            'games_played': wins + losses
        })

    return team_stats


def transform_schedule_to_games(schedules_df: pl.DataFrame) -> List[Dict[str, Any]]:
    """
    Transform schedule DataFrame to standardized game format.

    Args:
        schedules_df: DataFrame from nflreadpy.import_schedules()

    Returns:
        List of game dictionaries
    """
    if schedules_df is None or schedules_df.is_empty():
        return []

    return dataframe_to_dict_list(schedules_df)


def get_current_season() -> int:
    """
    Get current NFL season year.

    NFL season spans two calendar years, starting in September.

    Returns:
        Current season year
    """
    now = datetime.now()
    if now.month >= 9:  # Season starts in September
        return now.year
    else:
        return now.year - 1


def get_current_nfl_week() -> Optional[int]:
    """
    Estimate current NFL week based on date.

    NFL season typically starts first Thursday after Labor Day (early September).
    Regular season is 18 weeks.

    Returns:
        Estimated current week (1-18) or None if offseason
    """
    now = datetime.now()
    year = get_current_season()

    # NFL season roughly starts first week of September
    # This is an approximation - actual week should come from schedule data
    season_start = datetime(year, 9, 7)  # Approximate start

    if now < season_start:
        return None  # Offseason

    # Calculate weeks since season start
    delta = now - season_start
    week = (delta.days // 7) + 1

    if week > 18:
        return None  # Postseason/offseason

    return week
