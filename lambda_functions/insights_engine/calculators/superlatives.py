"""
Superlatives Calculator
Generates league-wide awards and rankings (e.g., "Biggest Target Share Gainer")
"""

from typing import List, Dict, Optional
from models import Superlative, PlayerInsight


class SuperlativesCalculator:
    """Calculates league-wide superlatives and awards"""

    def __init__(self):
        pass

    def generate_all_superlatives(
        self,
        player_insights: List[PlayerInsight],
        season: int,
        week: int
    ) -> List[Superlative]:
        """
        Generate all superlatives for a given week

        Returns:
            List of Superlative objects
        """
        superlatives = []

        # Volume-based superlatives
        superlatives.extend(self._target_share_superlatives(player_insights, season, week))
        # snap_share_superlatives - skip for now (requires load_snap_counts data)
        superlatives.extend(self._touches_superlatives(player_insights, season, week))

        # Efficiency-based superlatives
        superlatives.extend(self._efficiency_superlatives(player_insights, season, week))

        # Fantasy points superlatives
        superlatives.extend(self._fantasy_points_superlatives(player_insights, season, week))

        return superlatives

    def _target_share_superlatives(
        self,
        insights: List[PlayerInsight],
        season: int,
        week: int
    ) -> List[Superlative]:
        """USER'S SPECIFIC REQUEST: Target share gainers/losers"""
        superlatives = []

        # Filter players with target share delta
        players_with_delta = [
            insight for insight in insights
            if (insight.volume_trends and
                insight.volume_trends.target_share and
                insight.volume_trends.target_share.delta is not None)
        ]

        if not players_with_delta:
            return superlatives

        # Sort by delta (descending)
        players_with_delta.sort(
            key=lambda x: x.volume_trends.target_share.delta,
            reverse=True
        )

        # Top 3 gainers
        for rank, insight in enumerate(players_with_delta[:3], start=1):
            delta = insight.volume_trends.target_share.delta
            superlatives.append(Superlative(
                category="volume",
                subcategory="target_share",
                award_name=f"Target Share Gainer (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=delta,
                metric_name="target_share_delta",
                week=week,
                season=season,
                rank=rank
            ))

        # Top 3 losers
        losers = players_with_delta[-3:]
        losers.reverse()  # Worst first
        for rank, insight in enumerate(losers, start=1):
            delta = insight.volume_trends.target_share.delta
            superlatives.append(Superlative(
                category="volume",
                subcategory="target_share",
                award_name=f"Target Share Loser (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=delta,
                metric_name="target_share_delta",
                week=week,
                season=season,
                rank=rank
            ))

        return superlatives

    # def _snap_share_superlatives - REMOVED (snap_pct not available in load_player_stats)
    # Can be added in Phase 2 by joining load_snap_counts() data

    def _touches_superlatives(
        self,
        insights: List[PlayerInsight],
        season: int,
        week: int
    ) -> List[Superlative]:
        """Total touches gainers/losers"""
        superlatives = []

        # Filter players with touches delta
        players_with_delta = [
            insight for insight in insights
            if insight.touches_delta is not None
        ]

        if not players_with_delta:
            return superlatives

        # Sort by delta (descending)
        players_with_delta.sort(key=lambda x: x.touches_delta, reverse=True)

        # Top 3 gainers
        for rank, insight in enumerate(players_with_delta[:3], start=1):
            superlatives.append(Superlative(
                category="volume",
                subcategory="touches",
                award_name=f"Touches Gainer (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=insight.touches_delta,
                metric_name="touches_delta",
                week=week,
                season=season,
                rank=rank
            ))

        return superlatives

    def _efficiency_superlatives(
        self,
        insights: List[PlayerInsight],
        season: int,
        week: int
    ) -> List[Superlative]:
        """Efficiency metric superlatives (YPC, catch rate, etc.)"""
        superlatives = []

        # Yards per carry improvements
        ypc_improvers = [
            insight for insight in insights
            if (insight.efficiency_trends and
                insight.efficiency_trends.yards_per_carry and
                insight.efficiency_trends.yards_per_carry.delta is not None and
                insight.efficiency_trends.yards_per_carry.delta > 0)
        ]
        ypc_improvers.sort(
            key=lambda x: x.efficiency_trends.yards_per_carry.delta,
            reverse=True
        )

        for rank, insight in enumerate(ypc_improvers[:3], start=1):
            delta = insight.efficiency_trends.yards_per_carry.delta
            superlatives.append(Superlative(
                category="efficiency",
                subcategory="yards_per_carry",
                award_name=f"YPC Improver (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=delta,
                metric_name="yards_per_carry_delta",
                week=week,
                season=season,
                rank=rank
            ))

        # Catch rate improvements
        catch_rate_improvers = [
            insight for insight in insights
            if (insight.efficiency_trends and
                insight.efficiency_trends.catch_rate and
                insight.efficiency_trends.catch_rate.delta is not None and
                insight.efficiency_trends.catch_rate.delta > 0)
        ]
        catch_rate_improvers.sort(
            key=lambda x: x.efficiency_trends.catch_rate.delta,
            reverse=True
        )

        for rank, insight in enumerate(catch_rate_improvers[:3], start=1):
            delta = insight.efficiency_trends.catch_rate.delta
            superlatives.append(Superlative(
                category="efficiency",
                subcategory="catch_rate",
                award_name=f"Catch Rate Improver (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=delta,
                metric_name="catch_rate_delta",
                week=week,
                season=season,
                rank=rank
            ))

        return superlatives

    def _fantasy_points_superlatives(
        self,
        insights: List[PlayerInsight],
        season: int,
        week: int
    ) -> List[Superlative]:
        """Fantasy points delta superlatives"""
        superlatives = []

        # Filter players with fantasy points delta
        players_with_delta = [
            insight for insight in insights
            if insight.fantasy_points_delta is not None
        ]

        if not players_with_delta:
            return superlatives

        # Sort by delta (descending)
        players_with_delta.sort(key=lambda x: x.fantasy_points_delta, reverse=True)

        # Top 3 gainers
        for rank, insight in enumerate(players_with_delta[:3], start=1):
            superlatives.append(Superlative(
                category="fantasy_performance",
                subcategory="fantasy_points_ppr",
                award_name=f"Fantasy Points Gainer (Rank {rank})",
                player_id=insight.player_id,
                player_name=insight.player_name,
                position=insight.position,
                team=insight.team,
                value=insight.fantasy_points_delta,
                metric_name="fantasy_points_delta",
                week=week,
                season=season,
                rank=rank
            ))

        return superlatives

    def get_superlatives_by_category(
        self,
        superlatives: List[Superlative],
        category: str,
        subcategory: Optional[str] = None
    ) -> List[Superlative]:
        """
        Filter superlatives by category and optional subcategory

        Args:
            superlatives: All superlatives
            category: Main category ("volume", "efficiency", "fantasy_performance")
            subcategory: Optional subcategory ("target_share", "snap_share", etc.)
        """
        filtered = [s for s in superlatives if s.category == category]

        if subcategory:
            filtered = [s for s in filtered if s.subcategory == subcategory]

        return filtered

    def get_player_awards(
        self,
        superlatives: List[Superlative],
        player_id: str
    ) -> List[Superlative]:
        """Get all awards for a specific player"""
        return [s for s in superlatives if s.player_id == player_id]
