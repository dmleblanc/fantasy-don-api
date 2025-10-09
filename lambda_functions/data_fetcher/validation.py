"""
Inline data validation for data fetcher
Validates data structure before writing to S3
"""

from typing import Dict, List, Any, Tuple


class DataValidator:
    """Validates NFL stats data before writing to S3"""

    # Required fields for weekly player data
    REQUIRED_PLAYER_FIELDS = [
        "player_id",
        "player_name",
        "position",
        "team",
        "week"
    ]

    # Stat range validations (catches data corruption)
    # Allow small negative values for legitimate NFL stats
    STAT_RANGES = {
        "fantasy_points_ppr": (-10, 100),
        "passing_yards": (0, 600),
        "passing_tds": (0, 10),
        "rushing_yards": (-20, 300),  # Allow for bad sacks
        "rushing_tds": (0, 6),
        "receptions": (0, 25),
        "receiving_yards": (-20, 350),
        "receiving_tds": (0, 6),
        "targets": (0, 30),
    }

    # Minimum players per week by week type
    MIN_PLAYERS_REGULAR = 800
    MIN_PLAYERS_WILDCARD = 300   # Week 19
    MIN_PLAYERS_DIVISIONAL = 150  # Week 20
    MIN_PLAYERS_CONFERENCE = 100  # Week 21
    MIN_PLAYERS_SUPERBOWL = 50    # Week 22

    @staticmethod
    def get_min_players_for_week(week: int) -> int:
        """Get minimum expected players based on week"""
        if week == 22:
            return DataValidator.MIN_PLAYERS_SUPERBOWL
        elif week == 21:
            return DataValidator.MIN_PLAYERS_CONFERENCE
        elif week == 20:
            return DataValidator.MIN_PLAYERS_DIVISIONAL
        elif week == 19:
            return DataValidator.MIN_PLAYERS_WILDCARD
        else:
            return DataValidator.MIN_PLAYERS_REGULAR

    @staticmethod
    def validate_weekly_data(data: Dict[str, Any], week: int) -> Tuple[bool, List[str]]:
        """
        Validate weekly player data before writing to S3

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check top-level structure
        if 'data' not in data:
            errors.append("Missing 'data' key in top-level structure")
            return False, errors

        if 'players' not in data['data']:
            errors.append("Missing 'players' key in data structure")
            return False, errors

        players = data['data']['players']

        # Check player count
        player_count = len(players)
        min_expected = DataValidator.get_min_players_for_week(week)

        if player_count < min_expected:
            errors.append(
                f"Only {player_count} players found (expected {min_expected}+ for week {week})"
            )

        # Check required fields on sample players
        if players:
            sample_player = None
            for p in players[:10]:
                if p and isinstance(p, dict):
                    sample_player = p
                    break

            if sample_player:
                missing_fields = [
                    field for field in DataValidator.REQUIRED_PLAYER_FIELDS
                    if field not in sample_player
                ]
                if missing_fields:
                    errors.append(f"Players missing required fields: {missing_fields}")

                # Check stat ranges on first 100 players
                outlier_count = 0
                for player in players[:100]:
                    if not player or not isinstance(player, dict):
                        continue

                    for stat, (min_val, max_val) in DataValidator.STAT_RANGES.items():
                        value = player.get(stat)
                        if value is not None and (value < min_val or value > max_val):
                            outlier_count += 1
                            if outlier_count <= 3:  # Only log first 3
                                errors.append(
                                    f"Unusual {stat} for {player.get('player_name', 'Unknown')}: "
                                    f"{value} (expected {min_val}-{max_val})"
                                )

                # Too many outliers suggests data corruption
                if outlier_count > 20:
                    errors.append(
                        f"WARNING: {outlier_count} stat outliers found - possible data corruption"
                    )

        # Validation passes if no critical errors (player count warnings are OK)
        # Only fail on structural issues or extreme outliers
        critical_errors = [e for e in errors if 'missing' in e.lower() or 'corruption' in e.lower()]

        is_valid = len(critical_errors) == 0

        return is_valid, errors

    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate metadata structure

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        required_fields = ["current_season", "current_week", "weeks_available"]

        for field in required_fields:
            if field not in metadata:
                errors.append(f"Metadata missing required field: {field}")

        # Validate weeks_available is a list
        if "weeks_available" in metadata:
            if not isinstance(metadata["weeks_available"], list):
                errors.append("weeks_available must be a list")
            elif len(metadata["weeks_available"]) == 0:
                errors.append("weeks_available is empty")

        is_valid = len(errors) == 0
        return is_valid, errors
