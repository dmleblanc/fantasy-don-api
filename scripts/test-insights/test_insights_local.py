#!/usr/bin/env python3
"""
Local test script for insights engine Lambda function.
Tests insights generation between two specific weeks.

Usage:
    python test_insights_local.py --season 2025 --from-week 6 --to-week 7
    python test_insights_local.py --season 2025 --from-week 1 --to-week 7 --limit 5
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, List
from datetime import datetime

# Add lambda function to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda_functions/insights_engine'))

from index import handler
from models import InsightsOutput


def format_player_insight(insight: Dict[str, Any]) -> str:
    """Format a single player insight for display."""
    player = insight.get('player_name', 'Unknown')
    team = insight.get('team', 'UNK')
    position = insight.get('position', 'UNK')

    output = [f"\n{player} ({team} - {position})"]

    # Volume trends
    volume = insight.get('volume_trends', {})
    if volume:
        output.append("  Volume Trends:")

        if volume.get('target_share'):
            ts = volume['target_share']
            output.append(f"    Target Share: {ts.get('current_value', 0):.1%} "
                         f"(Δ {ts.get('delta', 0):+.1%})")

        if volume.get('carries'):
            carries = volume['carries']
            output.append(f"    Carries: {carries.get('current_value', 0):.0f} "
                         f"(Δ {carries.get('delta', 0):+.0f})")

        if volume.get('targets'):
            targets = volume['targets']
            output.append(f"    Targets: {targets.get('current_value', 0):.0f} "
                         f"(Δ {targets.get('delta', 0):+.0f})")

    # Production trends
    production = insight.get('production_trends', {})
    if production:
        output.append("  Production Trends:")

        if production.get('fantasy_points_ppr'):
            fp = production['fantasy_points_ppr']
            output.append(f"    Fantasy Points (PPR): {fp.get('current_value', 0):.1f} "
                         f"(Δ {fp.get('delta', 0):+.1f})")

        if production.get('yards_per_touch'):
            ypt = production['yards_per_touch']
            output.append(f"    Yards/Touch: {ypt.get('current_value', 0):.2f} "
                         f"(Δ {ypt.get('delta', 0):+.2f})")

    # Key flags
    flags = []
    if insight.get('breakout_candidate'):
        flags.append("🚀 BREAKOUT")
    if insight.get('bust_risk'):
        flags.append("⚠️  BUST RISK")
    if insight.get('trending_up'):
        flags.append("📈 TRENDING UP")
    if insight.get('trending_down'):
        flags.append("📉 TRENDING DOWN")

    if flags:
        output.append(f"  Flags: {' | '.join(flags)}")

    return '\n'.join(output)


def format_superlative(superlative: Dict[str, Any]) -> str:
    """Format a single superlative for display."""
    category = superlative.get('category', 'Unknown')
    player = superlative.get('player_name', 'Unknown')
    team = superlative.get('team', 'UNK')
    value = superlative.get('value', 0)
    metric = superlative.get('metric', '')

    # Format value based on metric type
    if 'percentage' in metric.lower() or 'share' in metric.lower() or 'rate' in metric.lower():
        value_str = f"{value:.1%}"
    elif 'points' in metric.lower() or 'yards' in metric.lower():
        value_str = f"{value:.1f}"
    else:
        value_str = f"{value:.2f}"

    return f"  • {player} ({team}): {value_str} - {superlative.get('description', '')}"


def write_output_report(args: argparse.Namespace, body: Dict[str, Any],
                       formatted_output: str) -> str:
    """Write test output to timestamped file in outputs directory."""
    # Create outputs directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(script_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    position_suffix = f"_{args.position}" if args.position else ""
    filename = f"insights_test_{args.season}_week{args.from_week}-to-{args.to_week}{position_suffix}_{timestamp}.txt"
    filepath = os.path.join(outputs_dir, filename)

    # Write formatted output
    with open(filepath, 'w') as f:
        f.write(formatted_output)

    # Also write raw JSON
    json_filename = filename.replace('.txt', '.json')
    json_filepath = os.path.join(outputs_dir, json_filename)
    with open(json_filepath, 'w') as f:
        json.dump(body, f, indent=2)

    return filepath, json_filepath


def main():
    parser = argparse.ArgumentParser(description='Test insights engine locally')
    parser.add_argument('--season', type=int, default=2025, help='Season year (default: 2025)')
    parser.add_argument('--from-week', type=int, required=True, help='Starting week')
    parser.add_argument('--to-week', type=int, required=True, help='Ending week')
    parser.add_argument('--limit', type=int, default=10, help='Number of player insights to show (default: 10)')
    parser.add_argument('--position', type=str, help='Filter by position (QB, RB, WR, TE)')
    parser.add_argument('--show-superlatives', action='store_true', help='Show superlatives')
    parser.add_argument('--profile', type=str, default='LeBlanc-Cloud-sso',
                       help='AWS profile to use (default: LeBlanc-Cloud-sso)')

    args = parser.parse_args()

    # Set AWS profile
    os.environ['AWS_PROFILE'] = args.profile

    # Set Lambda environment variables
    os.environ['BUCKET_NAME'] = 'nfl-stats-923890204996-us-east-1'
    os.environ['DATA_PREFIX'] = 'stats/'

    print(f"🏈 Testing Insights Engine")
    print(f"Season: {args.season}")
    print(f"Comparison: Week {args.from_week} → Week {args.to_week}")
    print("=" * 80)

    # Create Lambda event
    event = {
        'season': args.season,
        'week_from': args.from_week,
        'week_to': args.to_week
    }

    # Call handler
    try:
        response = handler(event, None)

        if response.get('statusCode') != 200:
            print(f"❌ Error: {response.get('body')}")
            return 1

        body = json.loads(response['body'])

        # Build formatted output
        output_lines = []
        output_lines.append(f"🏈 Testing Insights Engine")
        output_lines.append(f"Season: {args.season}")
        output_lines.append(f"Comparison: Week {args.from_week} → Week {args.to_week}")
        output_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append("=" * 80)

        # Display player insights
        players = body.get('players', [])
        output_lines.append(f"\n📊 Player Insights (showing {args.limit} of {len(players)})")
        output_lines.append("=" * 80)

        # Filter by position if specified
        if args.position:
            players = [p for p in players if p.get('position') == args.position.upper()]
            output_lines.append(f"Filtered to position: {args.position.upper()}")

        # Sort by target share delta (descending)
        players_sorted = sorted(
            players,
            key=lambda x: x.get('volume_trends', {}).get('target_share', {}).get('delta', -999),
            reverse=True
        )

        for player in players_sorted[:args.limit]:
            output_lines.append(format_player_insight(player))

        # Display superlatives if requested
        if args.show_superlatives:
            superlatives = body.get('superlatives', [])
            if superlatives:
                output_lines.append(f"\n🏆 Superlatives ({len(superlatives)} total)")
                output_lines.append("=" * 80)

                # Group by category
                by_category: Dict[str, List[Dict]] = {}
                for sup in superlatives:
                    category = sup.get('category', 'Other')
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(sup)

                for category, items in sorted(by_category.items()):
                    output_lines.append(f"\n{category}:")
                    for item in items[:3]:  # Show top 3 per category
                        output_lines.append(format_superlative(item))

        output_lines.append("\n" + "=" * 80)
        output_lines.append("✅ Test completed successfully!")

        formatted_output = '\n'.join(output_lines)

        # Print to console
        print(formatted_output)

        # Write to file
        txt_path, json_path = write_output_report(args, body, formatted_output)
        print(f"\n📝 Reports saved:")
        print(f"   Text: {txt_path}")
        print(f"   JSON: {json_path}")

        return 0

    except Exception as e:
        print(f"❌ Error running insights engine: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
