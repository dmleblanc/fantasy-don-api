"""
Generate insights for ALL week combinations in a season

This script pre-calculates insights for every possible week pairing:
- Consecutive: 1→2, 2→3, 3→4, etc.
- 2-week gaps: 1→3, 2→4, 3→5, etc.
- Multi-week: 1→7, 2→7, 3→7, etc.

Storage structure:
s3://bucket/insights/season/{season}/comparisons/{week_from}-to-{week_to}/
"""

import os
import sys
import json
from itertools import combinations
from typing import List, Tuple
import boto3

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from persistence import S3Persistence
from models import InsightsOutput
from calculators.player_insights import PlayerInsightsCalculator
from calculators.team_insights import TeamInsightsCalculator
from calculators.superlatives import SuperlativesCalculator


def get_all_week_combinations(available_weeks: List[int]) -> List[Tuple[int, int]]:
    """
    Generate all possible week combinations where week_from < week_to

    Args:
        available_weeks: List of available weeks

    Returns:
        List of (week_from, week_to) tuples
    """
    # Get all pairs where from < to
    all_pairs = []
    for i, week_from in enumerate(available_weeks):
        for week_to in available_weeks[i+1:]:
            all_pairs.append((week_from, week_to))

    return all_pairs


def calculate_comparison_insights(
    persistence: S3Persistence,
    season: int,
    week_from: int,
    week_to: int
) -> InsightsOutput:
    """
    Calculate insights comparing two specific weeks

    Args:
        persistence: S3 persistence layer
        season: Season year
        week_from: Starting week (baseline)
        week_to: Ending week (current)

    Returns:
        InsightsOutput with comparison data
    """
    print(f"\n{'='*80}")
    print(f"Comparing Week {week_from} → Week {week_to} (Δ {week_to - week_from} weeks)")
    print(f"{'='*80}")

    # Initialize calculators
    player_calc = PlayerInsightsCalculator()
    team_calc = TeamInsightsCalculator()
    superlatives_calc = SuperlativesCalculator()

    # Read both weeks
    from_data = persistence.read_weekly_stats(season, week_from)
    to_data = persistence.read_weekly_stats(season, week_to)

    if not from_data or not to_data:
        raise Exception(f"Missing data for week {week_from} or {week_to}")

    # Extract player lists
    if isinstance(from_data.get('data'), dict):
        from_players = from_data.get('data', {}).get('players', [])
    else:
        from_players = from_data.get('data', [])

    if isinstance(to_data.get('data'), dict):
        to_players = to_data.get('data', {}).get('players', [])
    else:
        to_players = to_data.get('data', [])

    from_players_map = {p['player_id']: p for p in from_players}
    to_players_map = {p['player_id']: p for p in to_players}

    print(f"From Week {week_from}: {len(from_players)} players")
    print(f"To Week {week_to}: {len(to_players)} players")

    # Calculate player insights (comparing from → to)
    player_insights = []
    for player_id, player_to in to_players_map.items():
        player_from = from_players_map.get(player_id)

        # For this comparison, treat week_from as "previous" and week_to as "current"
        insight = player_calc.calculate_player_insights(
            player_current=player_to,
            player_previous=player_from,
            player_history=[player_from, player_to] if player_from else [player_to],
            season=season,
            week=week_to  # Use week_to as the "current" week
        )

        player_insights.append(insight)

    # Calculate team insights
    team_insights = []
    teams = set(p.get('team') for p in to_players if p.get('team'))

    for team in teams:
        team_players_from = [p for p in from_players if p.get('team') == team]
        team_players_to = [p for p in to_players if p.get('team') == team]

        team_from = team_calc.aggregate_team_stats_from_players(team_players_from, team)
        team_to = team_calc.aggregate_team_stats_from_players(team_players_to, team)

        insight = team_calc.calculate_team_insights(
            team=team,
            team_current=team_to,
            team_previous=team_from,
            team_history=[team_from, team_to] if team_from else [team_to],
            players_current=team_players_to,
            players_previous=team_players_from,
            season=season,
            week=week_to
        )

        team_insights.append(insight)

    # Generate superlatives
    superlatives = superlatives_calc.generate_all_superlatives(
        player_insights, season, week_to
    )

    # Build output
    output = InsightsOutput(
        season=season,
        week=week_to,  # "Current" week in the comparison
        player_insights=[p.to_dict() for p in player_insights],
        team_insights=[t.to_dict() for t in team_insights],
        defense_insights=[],
        superlatives=[s.to_dict() for s in superlatives],
        metadata={
            'comparison_type': 'week_to_week',
            'week_from': week_from,
            'week_to': week_to,
            'week_delta': week_to - week_from,
            'total_players': len(player_insights),
            'total_teams': len(team_insights),
            'total_superlatives': len(superlatives),
        }
    )

    print(f"✓ Generated {len(player_insights)} player insights")
    print(f"✓ Generated {len(team_insights)} team insights")
    print(f"✓ Generated {len(superlatives)} superlatives")

    return output


def write_comparison_insights(
    persistence: S3Persistence,
    output: InsightsOutput,
    season: int,
    week_from: int,
    week_to: int
):
    """
    Write comparison insights to S3 with special path structure

    Path: insights/season/{season}/comparisons/{week_from}-to-{week_to}/
    """
    s3_client = boto3.client('s3')
    bucket_name = persistence.bucket_name

    # Insights file
    insights_key = f"insights/season/{season}/comparisons/{week_from}-to-{week_to}/insights.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=insights_key,
        Body=json.dumps(output.to_dict(), indent=2),
        ContentType='application/json'
    )
    print(f"✓ Wrote insights to s3://{bucket_name}/{insights_key}")

    # Superlatives file
    superlatives_key = f"insights/season/{season}/comparisons/{week_from}-to-{week_to}/superlatives.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=superlatives_key,
        Body=json.dumps({
            'season': season,
            'week_from': week_from,
            'week_to': week_to,
            'week_delta': week_to - week_from,
            'superlatives': output.superlatives,
            'timestamp': output.generated_at
        }, indent=2),
        ContentType='application/json'
    )
    print(f"✓ Wrote superlatives to s3://{bucket_name}/{superlatives_key}")


def generate_all_season_comparisons(season: int, bucket_name: str):
    """
    Generate insights for ALL week combinations in a season

    Args:
        season: Season year
        bucket_name: S3 bucket name
    """
    persistence = S3Persistence(bucket_name, "stats/")

    # Get available weeks
    available_weeks = persistence.get_available_weeks(season)
    print(f"\n{'='*80}")
    print(f"GENERATING ALL INSIGHTS COMPARISONS FOR {season} SEASON")
    print(f"{'='*80}")
    print(f"Available weeks: {available_weeks}")

    # Get all combinations
    all_combinations = get_all_week_combinations(available_weeks)
    print(f"Total combinations to process: {len(all_combinations)}")
    print(f"\nCombinations:")
    for week_from, week_to in all_combinations:
        print(f"  Week {week_from} → {week_to} (Δ {week_to - week_from})")

    # Process each combination
    results = []
    for i, (week_from, week_to) in enumerate(all_combinations, 1):
        try:
            print(f"\n[{i}/{len(all_combinations)}] Processing Week {week_from} → {week_to}...")

            output = calculate_comparison_insights(
                persistence, season, week_from, week_to
            )

            write_comparison_insights(
                persistence, output, season, week_from, week_to
            )

            results.append({
                'week_from': week_from,
                'week_to': week_to,
                'status': 'success',
                'insights': len(output.player_insights),
                'superlatives': len(output.superlatives)
            })

        except Exception as e:
            print(f"✗ Error processing Week {week_from} → {week_to}: {e}")
            results.append({
                'week_from': week_from,
                'week_to': week_to,
                'status': 'error',
                'error': str(e)
            })

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - successful
    print(f"Total combinations processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if failed > 0:
        print(f"\nFailed combinations:")
        for r in results:
            if r['status'] == 'error':
                print(f"  Week {r['week_from']} → {r['week_to']}: {r['error']}")

    # Write summary file
    summary_key = f"insights/season/{season}/comparisons/summary.json"
    s3_client = boto3.client('s3')
    s3_client.put_object(
        Bucket=bucket_name,
        Key=summary_key,
        Body=json.dumps({
            'season': season,
            'available_weeks': available_weeks,
            'total_combinations': len(all_combinations),
            'results': results,
            'successful': successful,
            'failed': failed
        }, indent=2),
        ContentType='application/json'
    )
    print(f"\n✓ Wrote summary to s3://{bucket_name}/{summary_key}")


if __name__ == "__main__":
    import sys

    # Set up AWS profile
    os.environ['AWS_PROFILE'] = 'LeBlanc-Cloud-sso'

    # Configuration
    BUCKET_NAME = 'nfl-stats-923890204996-us-east-1'
    SEASON = 2025

    if len(sys.argv) > 1:
        SEASON = int(sys.argv[1])

    generate_all_season_comparisons(SEASON, BUCKET_NAME)
