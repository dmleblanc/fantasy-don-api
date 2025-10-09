"""
S3 Bucket Schema Definition
Defines the expected structure of the NFL stats S3 bucket
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class S3Schema:
    """Expected S3 bucket structure and validation rules"""

    # === PATH PATTERNS ===
    WEEKLY_STATS_PATTERN = "stats/weekly/season/{season}/week/{week}/data.json"
    SEASON_TOTALS_PATTERN = "stats/aggregated/season/{season}/season-totals.json"
    TEAMS_PATTERN = "stats/aggregated/season/{season}/teams.json"
    GAMES_PATTERN = "stats/aggregated/season/{season}/games.json"
    INJURY_CURRENT_PATTERN = "stats/injuries/current-week/latest.json"
    INJURY_WEEKLY_PATTERN = "stats/injuries/season/{season}/week/{week}/final.json"
    METADATA_PATTERN = "stats/metadata.json"

    # === EXPECTED SEASONS AND WEEKS ===
    VALID_SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]

    # Number of weeks expected per season (regular + playoffs)
    WEEKS_PER_SEASON: Dict[int, int] = None

    def __post_init__(self):
        self.WEEKS_PER_SEASON = {
            2020: 21,  # 17 regular + 4 playoff weeks
            2021: 22,  # 18 regular + 4 playoff weeks
            2022: 22,
            2023: 22,
            2024: 22,
            2025: 5,   # Current season - partial data
        }

    # === REQUIRED FIELDS PER DATA TYPE ===

    # Weekly player stats required fields
    WEEKLY_STATS_REQUIRED_FIELDS = [
        "player_id",
        "player_name",
        "position",
        "team",
        "week"
    ]

    # Weekly stats top-level structure
    WEEKLY_STATS_TOP_LEVEL = ["data", "metadata", "season", "week", "timestamp"]

    # Injury data required fields
    INJURY_REQUIRED_FIELDS = [
        "gsis_id",
        "full_name",
        "report_status"
    ]

    # Metadata required fields
    METADATA_REQUIRED_FIELDS = [
        "timestamp",
        "current_season",
        "current_week",
        "weeks_available"
    ]

    # === VALIDATION THRESHOLDS ===

    # Minimum players per week (catches truncation issues)
    MIN_PLAYERS_PER_WEEK = 800
    MIN_PLAYERS_WILDCARD = 300   # Week 19: 4 games = ~200 players
    MIN_PLAYERS_DIVISIONAL = 150  # Week 20: 2 games = ~100 players
    MIN_PLAYERS_CONFERENCE = 100  # Week 21: 2 games = ~100 players
    MIN_PLAYERS_SUPERBOWL = 50    # Week 22: 1 game = ~70 players

    # Playoff weeks (weeks 19-22)
    PLAYOFF_WEEKS = [19, 20, 21, 22]

    # Maximum age of data in hours before warning
    DATA_FRESHNESS_WARNING_HOURS = 168  # 1 week

    # Stat range validations (catches data corruption)
    # Allow small negative values for legitimate NFL stats (sacks, fumbles, etc.)
    STAT_RANGES = {
        "fantasy_points_ppr": (-10, 100),    # Can be negative due to fumbles
        "passing_yards": (0, 600),           # Record: 554 (Brady)
        "passing_tds": (0, 10),              # Record: 7 (multiple)
        "rushing_yards": (-10, 300),         # Can be negative (sacks, fumbles)
        "rushing_tds": (0, 6),               # Record: 6 (multiple)
        "receptions": (0, 25),               # Record: 23 (Marshall)
        "receiving_yards": (-10, 350),       # Can be negative (catches behind LOS)
        "receiving_tds": (0, 6),             # Record: 5 (multiple)
        "targets": (0, 30),                  # Record: 24 (Beckham)
    }

    @staticmethod
    def get_min_players_for_week(week: int) -> int:
        """Get minimum expected players based on week (accounts for playoffs)"""
        if week == 22:
            return S3Schema.MIN_PLAYERS_SUPERBOWL
        elif week == 21:
            return S3Schema.MIN_PLAYERS_CONFERENCE
        elif week == 20:
            return S3Schema.MIN_PLAYERS_DIVISIONAL
        elif week == 19:
            return S3Schema.MIN_PLAYERS_WILDCARD
        else:
            return S3Schema.MIN_PLAYERS_PER_WEEK
