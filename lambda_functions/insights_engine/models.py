"""
Data Models for NFL Insights Engine
Defines structures for player, team, defense insights and superlatives
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class TrendData:
    """Represents a trend across multiple weeks"""
    current_value: float
    previous_value: Optional[float] = None
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    three_week_values: List[float] = field(default_factory=list)
    trend_direction: Optional[str] = None  # "rising", "falling", "stable"
    slope: Optional[float] = None
    projected_next: Optional[float] = None

    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class VolumeTrends:
    """Volume-related trends for a player"""
    target_share: Optional[TrendData] = None
    snap_share: Optional[TrendData] = None
    touch_share: Optional[TrendData] = None
    carries: Optional[TrendData] = None
    targets: Optional[TrendData] = None

    def to_dict(self) -> Dict:
        result = {}
        if self.target_share:
            result['target_share'] = self.target_share.to_dict()
        if self.snap_share:
            result['snap_share'] = self.snap_share.to_dict()
        if self.touch_share:
            result['touch_share'] = self.touch_share.to_dict()
        if self.carries:
            result['carries'] = self.carries.to_dict()
        if self.targets:
            result['targets'] = self.targets.to_dict()
        return result


@dataclass
class EfficiencyTrends:
    """Efficiency-related trends for a player"""
    yards_per_carry: Optional[TrendData] = None
    yards_per_target: Optional[TrendData] = None
    catch_rate: Optional[TrendData] = None
    yards_per_reception: Optional[TrendData] = None
    fantasy_points_per_touch: Optional[TrendData] = None

    def to_dict(self) -> Dict:
        result = {}
        if self.yards_per_carry:
            result['yards_per_carry'] = self.yards_per_carry.to_dict()
        if self.yards_per_target:
            result['yards_per_target'] = self.yards_per_target.to_dict()
        if self.catch_rate:
            result['catch_rate'] = self.catch_rate.to_dict()
        if self.yards_per_reception:
            result['yards_per_reception'] = self.yards_per_reception.to_dict()
        if self.fantasy_points_per_touch:
            result['fantasy_points_per_touch'] = self.fantasy_points_per_touch.to_dict()
        return result


@dataclass
class PlayerInsight:
    """Complete insight package for a player"""
    player_id: str
    player_name: str
    position: str
    team: str
    week: int
    season: int

    # Trend categories
    volume_trends: Optional[VolumeTrends] = None
    efficiency_trends: Optional[EfficiencyTrends] = None

    # Week-over-week summary
    touches_delta: Optional[int] = None
    fantasy_points_delta: Optional[float] = None

    # Rankings
    volume_rank_position: Optional[int] = None
    efficiency_rank_position: Optional[int] = None

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        result = {
            'player_id': self.player_id,
            'player_name': self.player_name,
            'position': self.position,
            'team': self.team,
            'week': self.week,
            'season': self.season,
            'timestamp': self.timestamp,
        }

        if self.volume_trends:
            result['volume_trends'] = self.volume_trends.to_dict()
        if self.efficiency_trends:
            result['efficiency_trends'] = self.efficiency_trends.to_dict()
        if self.touches_delta is not None:
            result['touches_delta'] = self.touches_delta
        if self.fantasy_points_delta is not None:
            result['fantasy_points_delta'] = self.fantasy_points_delta
        if self.volume_rank_position:
            result['volume_rank_position'] = self.volume_rank_position
        if self.efficiency_rank_position:
            result['efficiency_rank_position'] = self.efficiency_rank_position

        return result


@dataclass
class TeamInsight:
    """Complete insight package for a team"""
    team: str
    week: int
    season: int

    # Pace and volume trends
    plays_per_game: Optional[TrendData] = None
    pass_rate: Optional[TrendData] = None
    pace: Optional[TrendData] = None

    # Personnel usage
    rb_committee_entropy: Optional[float] = None  # How distributed RB touches are
    wr_target_distribution: Optional[Dict[str, float]] = None

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        result = {
            'team': self.team,
            'week': self.week,
            'season': self.season,
            'timestamp': self.timestamp,
        }

        if self.plays_per_game:
            result['plays_per_game'] = self.plays_per_game.to_dict()
        if self.pass_rate:
            result['pass_rate'] = self.pass_rate.to_dict()
        if self.pace:
            result['pace'] = self.pace.to_dict()
        if self.rb_committee_entropy is not None:
            result['rb_committee_entropy'] = self.rb_committee_entropy
        if self.wr_target_distribution:
            result['wr_target_distribution'] = self.wr_target_distribution

        return result


@dataclass
class DefenseInsight:
    """Complete insight package for a defense"""
    team: str
    week: int
    season: int

    # Position-specific vulnerability
    points_allowed_vs_qb: Optional[TrendData] = None
    points_allowed_vs_rb: Optional[TrendData] = None
    points_allowed_vs_wr: Optional[TrendData] = None
    points_allowed_vs_te: Optional[TrendData] = None

    # Pressure and coverage
    sacks_per_game: Optional[TrendData] = None
    interceptions_per_game: Optional[TrendData] = None

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        result = {
            'team': self.team,
            'week': self.week,
            'season': self.season,
            'timestamp': self.timestamp,
        }

        if self.points_allowed_vs_qb:
            result['points_allowed_vs_qb'] = self.points_allowed_vs_qb.to_dict()
        if self.points_allowed_vs_rb:
            result['points_allowed_vs_rb'] = self.points_allowed_vs_rb.to_dict()
        if self.points_allowed_vs_wr:
            result['points_allowed_vs_wr'] = self.points_allowed_vs_wr.to_dict()
        if self.points_allowed_vs_te:
            result['points_allowed_vs_te'] = self.points_allowed_vs_te.to_dict()
        if self.sacks_per_game:
            result['sacks_per_game'] = self.sacks_per_game.to_dict()
        if self.interceptions_per_game:
            result['interceptions_per_game'] = self.interceptions_per_game.to_dict()

        return result


@dataclass
class Superlative:
    """Represents a league-wide superlative/award"""
    category: str
    subcategory: str
    award_name: str
    player_id: str
    player_name: str
    position: str
    team: str
    value: float
    metric_name: str
    week: int
    season: int
    rank: int = 1  # 1 = winner, 2 = runner-up, etc.

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PlayerDelta:
    """Historical delta storage for a single player"""
    player_id: str
    player_name: str
    position: str
    season: int

    # Weekly snapshots
    weekly_snapshots: List[Dict[str, Any]] = field(default_factory=list)

    # Pre-calculated deltas
    deltas: List[Dict[str, Any]] = field(default_factory=list)

    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class InsightsOutput:
    """Complete output package for a week's insights"""
    season: int
    week: int
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    player_insights: List[Dict] = field(default_factory=list)
    team_insights: List[Dict] = field(default_factory=list)
    defense_insights: List[Dict] = field(default_factory=list)
    superlatives: List[Dict] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'season': self.season,
            'week': self.week,
            'generated_at': self.generated_at,
            'player_insights': self.player_insights,
            'team_insights': self.team_insights,
            'defense_insights': self.defense_insights,
            'superlatives': self.superlatives,
            'metadata': self.metadata,
        }
