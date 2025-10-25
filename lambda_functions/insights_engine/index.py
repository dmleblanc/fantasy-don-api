"""
NFL Insights Engine Lambda Handler
Generates week-over-week insights for players, teams, and defenses
Runs daily at 00:15 UTC (15 minutes after data fetcher)
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

# Local imports
from persistence import S3Persistence
from models import InsightsOutput
from calculators.player_insights import PlayerInsightsCalculator
from calculators.team_insights import TeamInsightsCalculator
from calculators.defense_insights import DefenseInsightsCalculator
from calculators.superlatives import SuperlativesCalculator


def handler(event, context):
    """
    Lambda handler for insights generation

    Triggered by EventBridge at 00:15 UTC daily
    Reads last 3 weeks of data, generates insights, writes to S3
    """
    print("=== NFL Insights Engine Started ===")
    print(f"Event: {json.dumps(event)}")

    # Initialize
    bucket_name = os.environ['BUCKET_NAME']
    data_prefix = os.environ.get('DATA_PREFIX', 'stats/')

    persistence = S3Persistence(bucket_name, data_prefix)

    # Check if event specifies custom weeks (for testing/comparisons)
    if event.get('week_from') and event.get('week_to'):
        # Custom week comparison mode
        current_season = event.get('season', 2025)
        week_from = event['week_from']
        week_to = event['week_to']
        print(f"Custom comparison mode: Season {current_season}, Week {week_from} → Week {week_to}")
    else:
        # Normal mode - use metadata to determine current week
        metadata = persistence.read_metadata()
        if not metadata:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'No metadata found - data fetcher may not have run yet'})
            }

        current_season = metadata.get('current_season')
        week_from = metadata.get('current_week') - 1  # Previous week
        week_to = metadata.get('current_week')  # Current week
        print(f"Processing insights for Season {current_season}, Week {week_to}")

    # Validate that weekly stats exist for both weeks
    if not persistence.check_week_exists(current_season, week_to):
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'No data found for S{current_season}W{week_to}'
            })
        }

    if not persistence.check_week_exists(current_season, week_from):
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'No data found for S{current_season}W{week_from}'
            })
        }

    try:
        # Generate insights
        insights_output = generate_insights(
            persistence,
            current_season,
            week_to,
            week_from
        )

        # Write insights to S3
        persistence.write_insights(
            insights_output.to_dict(),
            current_season,
            week_to
        )

        # Write superlatives separately
        persistence.write_superlatives(
            insights_output.superlatives,
            current_season,
            week_to
        )

        # Write latest snapshot
        persistence.write_latest_insights(insights_output.to_dict())

        print(f"✓ Insights generation complete:")
        print(f"  - {len(insights_output.player_insights)} player insights")
        print(f"  - {len(insights_output.team_insights)} team insights")
        print(f"  - {len(insights_output.defense_insights)} defense insights")
        print(f"  - {len(insights_output.superlatives)} superlatives")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Insights generated successfully',
                'season': current_season,
                'week_from': week_from,
                'week_to': week_to,
                'players': insights_output.player_insights,
                'teams': insights_output.team_insights,
                'defenses': insights_output.defense_insights,
                'superlatives': insights_output.superlatives,
                'stats': {
                    'player_insights': len(insights_output.player_insights),
                    'team_insights': len(insights_output.team_insights),
                    'defense_insights': len(insights_output.defense_insights),
                    'superlatives': len(insights_output.superlatives),
                }
            })
        }

    except Exception as e:
        print(f"✗ Error generating insights: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def generate_insights(
    persistence: S3Persistence,
    season: int,
    week_to: int,
    week_from: int = None
) -> InsightsOutput:
    """
    Main insights generation logic

    Compares week_from to week_to (or uses previous week if not specified)
    Reads up to 3 weeks of data for trend analysis
    Returns InsightsOutput
    """
    # Initialize calculators
    player_calc = PlayerInsightsCalculator()
    team_calc = TeamInsightsCalculator()
    defense_calc = DefenseInsightsCalculator()
    superlatives_calc = SuperlativesCalculator()

    # If week_from not specified, default to previous week
    if week_from is None:
        week_from = week_to - 1

    # Determine weeks to fetch (include week before week_from for trends)
    weeks_to_fetch = []
    if week_from >= 2:
        weeks_to_fetch = [week_from - 1, week_from, week_to]
    else:
        weeks_to_fetch = [week_from, week_to]

    # Deduplicate and sort
    weeks_to_fetch = sorted(list(set(weeks_to_fetch)))

    print(f"Fetching weeks: {weeks_to_fetch}")

    # Read weekly stats for all weeks
    weekly_data = persistence.read_multiple_weeks(season, weeks_to_fetch)

    # Extract current week and previous weeks
    current_data = weekly_data.get(week_to)
    previous_data = weekly_data.get(week_from)

    if not current_data:
        raise Exception(f"No data found for week {week_to}")

    if not previous_data:
        raise Exception(f"No data found for week {week_from}")

    # Extract player lists
    # Handle both old format (data: []) and new format (data: {players: []})
    if isinstance(current_data.get('data'), dict):
        current_players = current_data.get('data', {}).get('players', [])
    else:
        current_players = current_data.get('data', [])

    if previous_data:
        if isinstance(previous_data.get('data'), dict):
            previous_players = previous_data.get('data', {}).get('players', [])
        else:
            previous_players = previous_data.get('data', [])
    else:
        previous_players = []

    # Create player lookup maps
    current_players_map = {p['player_id']: p for p in current_players}
    previous_players_map = {p['player_id']: p for p in previous_players}

    # Build 3-week history for each player
    player_histories = {}
    for player_id in current_players_map.keys():
        history = []
        for w in weeks_to_fetch:
            week_data = weekly_data.get(w)
            if week_data:
                # Handle both old and new data formats
                if isinstance(week_data.get('data'), dict):
                    week_players = week_data.get('data', {}).get('players', [])
                else:
                    week_players = week_data.get('data', [])
                week_players_map = {p['player_id']: p for p in week_players}
                if player_id in week_players_map:
                    history.append(week_players_map[player_id])
        player_histories[player_id] = history

    print(f"Processing {len(current_players)} players...")

    # === GENERATE PLAYER INSIGHTS ===
    player_insights = []
    for player_id, player_current in current_players_map.items():
        player_previous = previous_players_map.get(player_id)
        player_history = player_histories.get(player_id, [])

        insight = player_calc.calculate_player_insights(
            player_current=player_current,
            player_previous=player_previous,
            player_history=player_history,
            season=season,
            week=week_to
        )

        player_insights.append(insight)

    # === GENERATE TEAM INSIGHTS ===
    team_insights = []
    teams = set(p.get('team') for p in current_players if p.get('team'))

    print(f"Processing {len(teams)} teams...")

    for team in teams:
        # Get all players for this team
        team_players_current = [p for p in current_players if p.get('team') == team]
        team_players_previous = [p for p in previous_players if p.get('team') == team]

        # Aggregate team-level stats from players
        team_current = team_calc.aggregate_team_stats_from_players(
            team_players_current, team
        )
        team_previous = team_calc.aggregate_team_stats_from_players(
            team_players_previous, team
        ) if team_players_previous else None

        # Build 3-week history for team
        team_history = []
        for w in weeks_to_fetch:
            week_data = weekly_data.get(w)
            if week_data:
                # Handle both old and new data formats
                if isinstance(week_data.get('data'), dict):
                    week_players = week_data.get('data', {}).get('players', [])
                else:
                    week_players = week_data.get('data', [])
                week_team_players = [p for p in week_players if p.get('team') == team]
                week_team_stats = team_calc.aggregate_team_stats_from_players(
                    week_team_players, team
                )
                if week_team_stats:
                    team_history.append(week_team_stats)

        insight = team_calc.calculate_team_insights(
            team=team,
            team_current=team_current,
            team_previous=team_previous,
            team_history=team_history,
            players_current=team_players_current,
            players_previous=team_players_previous,
            season=season,
            week=week_to
        )

        team_insights.append(insight)

    # === GENERATE DEFENSE INSIGHTS ===
    # For defenses, we need to track points allowed to opponent positions
    # This requires game data to know who played against whom
    # For now, we'll skip defense insights (can be added in Phase 3)
    defense_insights = []

    print("Defense insights skipped (requires game matchup data)")

    # === GENERATE SUPERLATIVES ===
    print("Generating superlatives...")
    superlatives = superlatives_calc.generate_all_superlatives(
        player_insights, season, week_to
    )

    # === BUILD OUTPUT ===
    output = InsightsOutput(
        season=season,
        week=week_to,
        player_insights=[p.to_dict() for p in player_insights],
        team_insights=[t.to_dict() for t in team_insights],
        defense_insights=[d.to_dict() for d in defense_insights],
        superlatives=[s.to_dict() for s in superlatives],
        metadata={
            'total_players': len(player_insights),
            'total_teams': len(team_insights),
            'total_defenses': len(defense_insights),
            'total_superlatives': len(superlatives),
            'weeks_analyzed': weeks_to_fetch,
        }
    )

    return output


# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {}
    test_context = {}

    # Set environment variables
    os.environ['BUCKET_NAME'] = 'nfl-stats-test-bucket'
    os.environ['DATA_PREFIX'] = 'stats/'

    result = handler(test_event, test_context)
    print(json.dumps(result, indent=2))
