"""
Player Insights Calculator
Calculates volume trends, efficiency trends, and 3-week trends for players
"""

from typing import Dict, List, Optional, Tuple
import statistics
from models import PlayerInsight, VolumeTrends, EfficiencyTrends, TrendData


class PlayerInsightsCalculator:
    """Calculates insights for individual players"""

    def __init__(self):
        pass

    def calculate_player_insights(
        self,
        player_current: Dict,
        player_previous: Optional[Dict],
        player_history: List[Dict],
        season: int,
        week: int
    ) -> PlayerInsight:
        """
        Calculate comprehensive insights for a single player

        Args:
            player_current: Current week stats
            player_previous: Previous week stats (None if week 1)
            player_history: List of last 3 weeks [week-2, week-1, current]
            season: Current season
            week: Current week

        Returns:
            PlayerInsight object with all calculated trends
        """
        insight = PlayerInsight(
            player_id=player_current.get('player_id', ''),
            player_name=player_current.get('player_name', ''),
            position=player_current.get('position', ''),
            team=player_current.get('team', ''),
            week=week,
            season=season
        )

        # Calculate volume trends
        insight.volume_trends = self._calculate_volume_trends(
            player_current, player_previous, player_history
        )

        # Calculate efficiency trends
        insight.efficiency_trends = self._calculate_efficiency_trends(
            player_current, player_previous, player_history
        )

        # Calculate week-over-week deltas
        if player_previous:
            insight.touches_delta = self._calculate_touches_delta(
                player_current, player_previous
            )
            insight.fantasy_points_delta = (
                player_current.get('fantasy_points_ppr', 0) -
                player_previous.get('fantasy_points_ppr', 0)
            )

        return insight

    def _calculate_volume_trends(
        self,
        current: Dict,
        previous: Optional[Dict],
        history: List[Dict]
    ) -> VolumeTrends:
        """Calculate volume-related trends (target %, snap %, touches)"""

        volume_trends = VolumeTrends()

        # Target Share (USER'S SPECIFIC REQUEST)
        if current.get('target_share') is not None:
            volume_trends.target_share = self._calculate_trend(
                current_value=current.get('target_share', 0),
                previous_value=previous.get('target_share') if previous else None,
                history_values=[h.get('target_share', 0) for h in history if h.get('target_share') is not None],
                metric_name='target_share'
            )

        # Snap Share (NOTE: snap_pct not available in load_player_stats, would need load_snap_counts)
        # Skipping for now, can be added in Phase 2 by joining snap count data
        # if current.get('offense_pct') is not None:
        #     volume_trends.snap_share = self._calculate_trend(...)
        pass  # Placeholder for future snap share implementation

        # Touch Share (carries + targets / team total)
        # Note: This requires team-level aggregation, placeholder for now
        current_touches = (current.get('carries', 0) + current.get('targets', 0))
        if current_touches > 0:
            volume_trends.touch_share = TrendData(
                current_value=current_touches,
            )

        # Carries
        if current.get('carries') is not None:
            volume_trends.carries = self._calculate_trend(
                current_value=current.get('carries', 0),
                previous_value=previous.get('carries') if previous else None,
                history_values=[h.get('carries', 0) for h in history if h.get('carries') is not None],
                metric_name='carries'
            )

        # Targets
        if current.get('targets') is not None:
            volume_trends.targets = self._calculate_trend(
                current_value=current.get('targets', 0),
                previous_value=previous.get('targets') if previous else None,
                history_values=[h.get('targets', 0) for h in history if h.get('targets') is not None],
                metric_name='targets'
            )

        return volume_trends

    def _calculate_efficiency_trends(
        self,
        current: Dict,
        previous: Optional[Dict],
        history: List[Dict]
    ) -> EfficiencyTrends:
        """Calculate efficiency-related trends"""

        efficiency_trends = EfficiencyTrends()

        # Yards per carry
        if current.get('carries', 0) > 0:
            ypc_current = current.get('rushing_yards', 0) / current.get('carries', 1)
            ypc_previous = None
            if previous and previous.get('carries', 0) > 0:
                ypc_previous = previous.get('rushing_yards', 0) / previous.get('carries', 1)

            ypc_history = []
            for h in history:
                if h.get('carries', 0) > 0:
                    ypc_history.append(h.get('rushing_yards', 0) / h.get('carries', 1))

            efficiency_trends.yards_per_carry = self._calculate_trend(
                current_value=ypc_current,
                previous_value=ypc_previous,
                history_values=ypc_history,
                metric_name='yards_per_carry'
            )

        # Yards per target
        if current.get('targets', 0) > 0:
            ypt_current = current.get('receiving_yards', 0) / current.get('targets', 1)
            ypt_previous = None
            if previous and previous.get('targets', 0) > 0:
                ypt_previous = previous.get('receiving_yards', 0) / previous.get('targets', 1)

            ypt_history = []
            for h in history:
                if h.get('targets', 0) > 0:
                    ypt_history.append(h.get('receiving_yards', 0) / h.get('targets', 1))

            efficiency_trends.yards_per_target = self._calculate_trend(
                current_value=ypt_current,
                previous_value=ypt_previous,
                history_values=ypt_history,
                metric_name='yards_per_target'
            )

        # Catch rate
        if current.get('targets', 0) > 0:
            catch_rate_current = current.get('receptions', 0) / current.get('targets', 1)
            catch_rate_previous = None
            if previous and previous.get('targets', 0) > 0:
                catch_rate_previous = previous.get('receptions', 0) / previous.get('targets', 1)

            catch_rate_history = []
            for h in history:
                if h.get('targets', 0) > 0:
                    catch_rate_history.append(h.get('receptions', 0) / h.get('targets', 1))

            efficiency_trends.catch_rate = self._calculate_trend(
                current_value=catch_rate_current,
                previous_value=catch_rate_previous,
                history_values=catch_rate_history,
                metric_name='catch_rate'
            )

        # Yards per reception
        if current.get('receptions', 0) > 0:
            ypr_current = current.get('receiving_yards', 0) / current.get('receptions', 1)
            ypr_previous = None
            if previous and previous.get('receptions', 0) > 0:
                ypr_previous = previous.get('receiving_yards', 0) / previous.get('receptions', 1)

            ypr_history = []
            for h in history:
                if h.get('receptions', 0) > 0:
                    ypr_history.append(h.get('receiving_yards', 0) / h.get('receptions', 1))

            efficiency_trends.yards_per_reception = self._calculate_trend(
                current_value=ypr_current,
                previous_value=ypr_previous,
                history_values=ypr_history,
                metric_name='yards_per_reception'
            )

        # Fantasy points per touch
        total_touches = current.get('carries', 0) + current.get('receptions', 0)
        if total_touches > 0:
            fppt_current = current.get('fantasy_points_ppr', 0) / total_touches
            fppt_previous = None
            if previous:
                prev_touches = previous.get('carries', 0) + previous.get('receptions', 0)
                if prev_touches > 0:
                    fppt_previous = previous.get('fantasy_points_ppr', 0) / prev_touches

            fppt_history = []
            for h in history:
                h_touches = h.get('carries', 0) + h.get('receptions', 0)
                if h_touches > 0:
                    fppt_history.append(h.get('fantasy_points_ppr', 0) / h_touches)

            efficiency_trends.fantasy_points_per_touch = self._calculate_trend(
                current_value=fppt_current,
                previous_value=fppt_previous,
                history_values=fppt_history,
                metric_name='fantasy_points_per_touch'
            )

        return efficiency_trends

    def _calculate_trend(
        self,
        current_value: float,
        previous_value: Optional[float],
        history_values: List[float],
        metric_name: str
    ) -> TrendData:
        """
        Calculate comprehensive trend data including:
        - Week-over-week delta
        - 3-week trend direction
        - Linear regression slope
        - Projected next week value
        """
        trend = TrendData(current_value=current_value)

        # Week-over-week delta
        if previous_value is not None:
            trend.previous_value = previous_value
            trend.delta = current_value - previous_value
            if previous_value != 0:
                trend.delta_pct = (trend.delta / previous_value) * 100

        # 3-week trend analysis
        if len(history_values) >= 3:
            trend.three_week_values = history_values[-3:]

            # Calculate slope using linear regression
            slope, projected = self._calculate_linear_regression(history_values[-3:])
            trend.slope = slope
            trend.projected_next = projected

            # Determine trend direction
            if slope > 0.05:  # Arbitrary threshold, can be tuned
                trend.trend_direction = "rising"
            elif slope < -0.05:
                trend.trend_direction = "falling"
            else:
                trend.trend_direction = "stable"

        return trend

    def _calculate_linear_regression(
        self,
        values: List[float]
    ) -> Tuple[float, float]:
        """
        Calculate linear regression slope and projected next value

        Returns:
            (slope, projected_next_value)
        """
        if len(values) < 2:
            return 0.0, values[-1] if values else 0.0

        n = len(values)
        x_values = list(range(n))

        # Calculate means
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(values)

        # Calculate slope
        numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0, values[-1]

        slope = numerator / denominator

        # Calculate intercept
        intercept = y_mean - slope * x_mean

        # Project next value (x = n)
        projected_next = slope * n + intercept

        return slope, max(0, projected_next)  # Don't project negative values

    def _calculate_touches_delta(self, current: Dict, previous: Dict) -> int:
        """Calculate total touches delta (carries + receptions)"""
        current_touches = current.get('carries', 0) + current.get('receptions', 0)
        previous_touches = previous.get('carries', 0) + previous.get('receptions', 0)
        return current_touches - previous_touches

    def get_top_gainers_by_metric(
        self,
        insights: List[PlayerInsight],
        metric_path: str,
        top_n: int = 10
    ) -> List[PlayerInsight]:
        """
        Get top N players by a specific metric delta

        Args:
            insights: List of all player insights
            metric_path: Dot-notation path to metric (e.g., "volume_trends.target_share.delta")
            top_n: Number of top players to return

        Example:
            get_top_gainers_by_metric(insights, "volume_trends.target_share.delta", 10)
        """
        def get_nested_value(obj, path: str):
            """Navigate nested object by dot-notation path"""
            parts = path.split('.')
            current = obj
            for part in parts:
                if hasattr(current, part):
                    current = getattr(current, part)
                elif isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current

        # Filter out players without the metric
        players_with_metric = [
            (insight, get_nested_value(insight, metric_path))
            for insight in insights
        ]
        players_with_metric = [
            (insight, value) for insight, value in players_with_metric
            if value is not None
        ]

        # Sort by metric value (descending)
        players_with_metric.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        return [insight for insight, _ in players_with_metric[:top_n]]
