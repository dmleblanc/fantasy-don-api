"""
Defense Insights Calculator
Calculates defensive vulnerability and performance trends
"""

from typing import Dict, List, Optional
from models import DefenseInsight, TrendData


class DefenseInsightsCalculator:
    """Calculates insights for NFL defenses"""

    def __init__(self):
        pass

    def calculate_defense_insights(
        self,
        team: str,
        opponent_players_current: List[Dict],
        opponent_players_previous: Optional[List[Dict]],
        opponent_players_history: List[List[Dict]],
        season: int,
        week: int
    ) -> DefenseInsight:
        """
        Calculate defensive vulnerability insights

        Args:
            team: Defense team abbreviation
            opponent_players_current: Opponent players who played against this defense (current week)
            opponent_players_previous: Opponent players from previous week
            opponent_players_history: 3 weeks of opponent players
            season: Current season
            week: Current week

        Returns:
            DefenseInsight object with vulnerability trends
        """
        insight = DefenseInsight(
            team=team,
            week=week,
            season=season
        )

        # Calculate points allowed by position
        insight.points_allowed_vs_qb = self._calculate_points_allowed_by_position(
            opponent_players_current,
            opponent_players_previous,
            opponent_players_history,
            'QB'
        )

        insight.points_allowed_vs_rb = self._calculate_points_allowed_by_position(
            opponent_players_current,
            opponent_players_previous,
            opponent_players_history,
            'RB'
        )

        insight.points_allowed_vs_wr = self._calculate_points_allowed_by_position(
            opponent_players_current,
            opponent_players_previous,
            opponent_players_history,
            'WR'
        )

        insight.points_allowed_vs_te = self._calculate_points_allowed_by_position(
            opponent_players_current,
            opponent_players_previous,
            opponent_players_history,
            'TE'
        )

        return insight

    def _calculate_points_allowed_by_position(
        self,
        current_opponents: List[Dict],
        previous_opponents: Optional[List[Dict]],
        history_opponents: List[List[Dict]],
        position: str
    ) -> TrendData:
        """
        Calculate fantasy points allowed to a specific position

        Returns average points allowed per game to this position
        """
        # Current week: total fantasy points scored by this position against this defense
        current_position_players = [
            p for p in current_opponents
            if p.get('position') == position
        ]
        current_points = sum(
            p.get('fantasy_points_ppr', 0) for p in current_position_players
        )

        # Previous week
        previous_points = None
        if previous_opponents:
            previous_position_players = [
                p for p in previous_opponents
                if p.get('position') == position
            ]
            previous_points = sum(
                p.get('fantasy_points_ppr', 0) for p in previous_position_players
            )

        # Historical (3 weeks)
        history_points = []
        for week_opponents in history_opponents:
            week_position_players = [
                p for p in week_opponents
                if p.get('position') == position
            ]
            week_points = sum(
                p.get('fantasy_points_ppr', 0) for p in week_position_players
            )
            if week_points > 0:
                history_points.append(week_points)

        trend = TrendData(current_value=current_points)
        if previous_points is not None:
            trend.previous_value = previous_points
            trend.delta = current_points - previous_points
            if previous_points != 0:
                trend.delta_pct = (trend.delta / previous_points) * 100

        if len(history_points) >= 3:
            trend.three_week_values = history_points[-3:]

        return trend

    def aggregate_defensive_stats_from_players(
        self,
        players: List[Dict],
        team: str
    ) -> Dict:
        """
        Aggregate defensive stats from defensive player data
        (sacks, interceptions, tackles, etc.)

        Args:
            players: All players on the defense
            team: Defense team abbreviation

        Returns:
            Aggregated defensive stats
        """
        defensive_players = [
            p for p in players
            if p.get('team') == team and p.get('position') in ['LB', 'DB', 'DL', 'DE', 'DT', 'CB', 'S']
        ]

        if not defensive_players:
            return {}

        # Aggregate defensive stats
        defense_stats = {
            'team': team,
            'sacks': 0,
            'interceptions': 0,
            'tackles_solo': 0,
            'tackles_assist': 0,
            'forced_fumbles': 0,
        }

        for player in defensive_players:
            defense_stats['sacks'] += player.get('def_sacks', 0)
            defense_stats['interceptions'] += player.get('def_interceptions', 0)
            defense_stats['tackles_solo'] += player.get('def_tackles_solo', 0)
            defense_stats['tackles_assist'] += player.get('def_tackles_assist', 0)
            defense_stats['forced_fumbles'] += player.get('def_forced_fumbles', 0)

        return defense_stats

    def get_defense_vs_position_matchups(
        self,
        all_defenses: List[DefenseInsight],
        position: str
    ) -> List[Dict]:
        """
        Get best/worst defensive matchups for a specific position

        Args:
            all_defenses: List of all defense insights
            position: Position to analyze ('QB', 'RB', 'WR', 'TE')

        Returns:
            Sorted list of {team, points_allowed, trend} for matchups
        """
        matchups = []

        for defense in all_defenses:
            points_trend = None

            if position == 'QB' and defense.points_allowed_vs_qb:
                points_trend = defense.points_allowed_vs_qb
            elif position == 'RB' and defense.points_allowed_vs_rb:
                points_trend = defense.points_allowed_vs_rb
            elif position == 'WR' and defense.points_allowed_vs_wr:
                points_trend = defense.points_allowed_vs_wr
            elif position == 'TE' and defense.points_allowed_vs_te:
                points_trend = defense.points_allowed_vs_te

            if points_trend:
                matchups.append({
                    'team': defense.team,
                    'points_allowed': points_trend.current_value,
                    'trend_direction': points_trend.trend_direction,
                    'delta': points_trend.delta
                })

        # Sort by points allowed (descending = worst defenses first)
        matchups.sort(key=lambda x: x['points_allowed'], reverse=True)

        return matchups
