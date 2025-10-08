"""
Utility functions for NFL Stats API Lambda.

Helper functions for:
- Query parameter parsing
- Response formatting
- Caching logic
- Data aggregation
- Season/week calculations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


def parse_date_range(start_date: str, end_date: str) -> List[str]:
    """
    Generate list of dates between start and end.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of date strings in YYYY-MM-DD format
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates


def aggregate_player_stats(stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate player stats across multiple data points.

    Args:
        stats_list: List of player stat dictionaries

    Returns:
        Aggregated stats
    """
    # Implement aggregation logic based on your needs
    # Example: sum totals, calculate averages, etc.
    return {
        "aggregated": True,
        "count": len(stats_list),
        "stats": stats_list,
    }


def format_api_response(data: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Format data for API response with consistent structure.

    Args:
        data: Data to return
        metadata: Optional metadata to include

    Returns:
        Formatted response dict
    """
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if metadata:
        response["metadata"] = metadata

    return response


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
