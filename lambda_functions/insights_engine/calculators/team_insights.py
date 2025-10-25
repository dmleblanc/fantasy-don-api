"""
Team Insights Calculator
Calculates pace, volume, and personnel trends for teams
"""

from typing import Dict, List, Optional
from models import TeamInsight, TrendData
import math


class TeamInsightsCalculator:
    """Calculates insights for NFL teams"""

    def __init__(self):
        pass

    def calculate_team_insights(
        self,
        team: str,
        team_current: Dict,
        team_previous: Optional[Dict],
        team_history: List[Dict],
        players_current: List[Dict],
        players_previous: Optional[List[Dict]],
        season: int,
        week: int
    ) -> TeamInsight:
        """
        Calculate comprehensive insights for a single team

        Args:
            team: Team abbreviation
            team_current: Current week team-level stats
            team_previous: Previous week team stats
            team_history: List of last 3 weeks of team stats
            players_current: All players for this team (current week)
            players_previous: All players for this team (previous week)
            season: Current season
            week: Current week

        Returns:
            TeamInsight object with all calculated trends
        """
        insight = TeamInsight(
            team=team,
            week=week,
            season=season
        )

        # Calculate pace/volume trends
        if team_current:
            insight.plays_per_game = self._calculate_plays_per_game_trend(
                team_current, team_previous, team_history
            )
            insight.pass_rate = self._calculate_pass_rate_trend(
                team_current, team_previous, team_history
            )

        # Calculate personnel usage
        if players_current:
            insight.rb_committee_entropy = self._calculate_rb_committee_entropy(
                players_current
            )
            insight.wr_target_distribution = self._calculate_wr_target_distribution(
                players_current
            )

        return insight

    def _calculate_plays_per_game_trend(
        self,
        current: Dict,
        previous: Optional[Dict],
        history: List[Dict]
    ) -> TrendData:
        """Calculate plays per game trend"""
        # Approximate total plays from pass + rush attempts
        current_plays = (
            current.get('pass_attempts', 0) +
            current.get('rush_attempts', 0)
        )

        previous_plays = None
        if previous:
            previous_plays = (
                previous.get('pass_attempts', 0) +
                previous.get('rush_attempts', 0)
            )

        history_plays = []
        for h in history:
            h_plays = h.get('pass_attempts', 0) + h.get('rush_attempts', 0)
            if h_plays > 0:
                history_plays.append(h_plays)

        trend = TrendData(current_value=current_plays)
        if previous_plays:
            trend.previous_value = previous_plays
            trend.delta = current_plays - previous_plays
            if previous_plays != 0:
                trend.delta_pct = (trend.delta / previous_plays) * 100

        if len(history_plays) >= 3:
            trend.three_week_values = history_plays[-3:]

        return trend

    def _calculate_pass_rate_trend(
        self,
        current: Dict,
        previous: Optional[Dict],
        history: List[Dict]
    ) -> TrendData:
        """Calculate pass rate (pass attempts / total plays)"""
        pass_attempts = current.get('pass_attempts', 0)
        rush_attempts = current.get('rush_attempts', 0)
        total_plays = pass_attempts + rush_attempts

        current_pass_rate = 0.0
        if total_plays > 0:
            current_pass_rate = pass_attempts / total_plays

        previous_pass_rate = None
        if previous:
            prev_pass = previous.get('pass_attempts', 0)
            prev_rush = previous.get('rush_attempts', 0)
            prev_total = prev_pass + prev_rush
            if prev_total > 0:
                previous_pass_rate = prev_pass / prev_total

        history_pass_rates = []
        for h in history:
            h_pass = h.get('pass_attempts', 0)
            h_rush = h.get('rush_attempts', 0)
            h_total = h_pass + h_rush
            if h_total > 0:
                history_pass_rates.append(h_pass / h_total)

        trend = TrendData(current_value=current_pass_rate)
        if previous_pass_rate is not None:
            trend.previous_value = previous_pass_rate
            trend.delta = current_pass_rate - previous_pass_rate
            if previous_pass_rate != 0:
                trend.delta_pct = (trend.delta / previous_pass_rate) * 100

        if len(history_pass_rates) >= 3:
            trend.three_week_values = history_pass_rates[-3:]

        return trend

    def _calculate_rb_committee_entropy(self, players: List[Dict]) -> float:
        """
        Calculate entropy of RB touch distribution
        Higher entropy = more committee approach
        Lower entropy = bellcow back

        Uses Shannon entropy formula: H = -Σ(p * log2(p))
        """
        # Get all RBs on this team
        rbs = [p for p in players if p.get('position') == 'RB']

        if not rbs:
            return 0.0

        # Calculate total touches for each RB
        rb_touches = []
        total_touches = 0
        for rb in rbs:
            touches = rb.get('carries', 0) + rb.get('receptions', 0)
            if touches > 0:
                rb_touches.append(touches)
                total_touches += touches

        if total_touches == 0:
            return 0.0

        # Calculate Shannon entropy
        entropy = 0.0
        for touches in rb_touches:
            probability = touches / total_touches
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return round(entropy, 3)

    def _calculate_wr_target_distribution(self, players: List[Dict]) -> Dict[str, float]:
        """
        Calculate target distribution among WRs
        Returns: {player_name: target_share} for top 3 WRs
        """
        # Get all WRs on this team with targets
        wrs = [
            p for p in players
            if p.get('position') == 'WR' and p.get('targets', 0) > 0
        ]

        if not wrs:
            return {}

        # Calculate total WR targets
        total_wr_targets = sum(wr.get('targets', 0) for wr in wrs)

        if total_wr_targets == 0:
            return {}

        # Sort WRs by targets (descending)
        wrs_sorted = sorted(wrs, key=lambda x: x.get('targets', 0), reverse=True)

        # Return top 3 WRs
        distribution = {}
        for wr in wrs_sorted[:3]:
            player_name = wr.get('player_name', 'Unknown')
            target_share = wr.get('targets', 0) / total_wr_targets
            distribution[player_name] = round(target_share, 3)

        return distribution

    def aggregate_team_stats_from_players(
        self,
        players: List[Dict],
        team: str
    ) -> Dict:
        """
        Aggregate team-level stats from player data
        Useful when team-level data is not directly available
        """
        team_players = [p for p in players if p.get('team') == team]

        if not team_players:
            return {}

        # Aggregate team totals
        team_stats = {
            'team': team,
            'pass_attempts': 0,
            'rush_attempts': 0,
            'total_yards': 0,
            'total_tds': 0,
        }

        for player in team_players:
            # Pass attempts (only QBs)
            if player.get('position') == 'QB':
                team_stats['pass_attempts'] += player.get('attempts', 0)

            # Rush attempts (all positions)
            team_stats['rush_attempts'] += player.get('carries', 0)

            # Total yards
            team_stats['total_yards'] += player.get('passing_yards', 0)
            team_stats['total_yards'] += player.get('rushing_yards', 0)
            team_stats['total_yards'] += player.get('receiving_yards', 0)

            # Total TDs
            team_stats['total_tds'] += player.get('passing_tds', 0)
            team_stats['total_tds'] += player.get('rushing_tds', 0)
            team_stats['total_tds'] += player.get('receiving_tds', 0)

        return team_stats
