#!/usr/bin/env python3
"""
Market Diagnostic CLI

Command-line interface for the market diagnostic system.
Provides access to diagnostic reports, knowledge base queries, and visualizations.

Usage:
    python -m platform.market_diagnostic.cli run --date 2026-04-25
    python -m platform.market_diagnostic.cli query --regime trend_risk_on_growth
    python -m platform.market_diagnostic.cli timeline --days 30
    python -m platform.market_diagnostic.cli strategies
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def cmd_run(args) -> int:
    """Run the diagnostic engine and generate a report."""
    try:
        from platform.market_diagnostic.engine import MarketDiagnosticEngine
        from platform.market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
        from platform.market_diagnostic.reports.json_exporter import DiagnosticJsonExporter
        from platform.market_diagnostic.knowledge_base_manager import KnowledgeBaseManager

        print(f"[CLI] Running diagnostic for date: {args.date or 'today'}")

        # Try to get data manager
        data_manager = None
        try:
            from daily_stock_analysis.src.data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except ImportError:
            pass

        engine = MarketDiagnosticEngine(data_manager)
        report, markdown = engine.run(date=args.date)

        # Export outputs
        output_dir = args.output or "./output"
        os.makedirs(output_dir, exist_ok=True)

        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        regime = report.composite_regime

        # Save JSON
        json_exporter = DiagnosticJsonExporter()
        json_path = os.path.join(output_dir, f"{date_str}_{regime}_report.json")
        json_exporter.save_to_file(report, json_path)
        print(f"[CLI] JSON report saved: {json_path}")

        # Save Markdown
        md_renderer = DiagnosticMarkdownRenderer()
        md_path = os.path.join(output_dir, f"{date_str}_{regime}_report.md")
        md_renderer.save_to_file(report, md_path)
        print(f"[CLI] Markdown report saved: {md_path}")

        # Save to knowledge base
        kb = KnowledgeBaseManager()
        report_dict = json_exporter.to_dict(report)
        saved_files = kb.save_report(report_dict, date=date_str)
        print(f"[CLI] Knowledge base updated: {saved_files}")

        # Print summary
        print("\n" + "="*60)
        print("Diagnostic Summary")
        print("="*60)
        print(f"Date: {report.date}")
        print(f"Regime: {report.composite_regime}")
        print(f"Confidence: {report.confidence:.0%}")
        print(f"One-sentence: {report.one_sentence_summary}")
        print("="*60)

        return 0

    except Exception as exc:
        print(f"[CLI] Error running diagnostic: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_query(args) -> int:
    """Query the knowledge base for historical reports."""
    try:
        from platform.market_diagnostic.knowledge_base_manager import KnowledgeBaseManager, ReportQuery

        kb = KnowledgeBaseManager()

        query = ReportQuery(
            start_date=args.start_date,
            end_date=args.end_date,
            regime=args.regime,
            min_confidence=args.min_confidence,
            trend_state=args.trend_state,
            breadth_state=args.breadth_state,
            sentiment_state=args.sentiment_state,
            risk_state=args.risk_state,
        )

        results = kb.query_reports(query)

        print(f"[CLI] Found {len(results)} matching reports")
        print()

        if args.format == "summary":
            for r in results:
                print(
                    f"  {r.get('date', 'N/A')} | "
                    f"{r.get('composite_regime', 'N/A'):30s} | "
                    f"conf={r.get('confidence', 0):.0%} | "
                    f"{r.get('one_sentence_summary', '')[:50]}"
                )
        elif args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))

        return 0

    except Exception as exc:
        print(f"[CLI] Error querying reports: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_timeline(args) -> int:
    """Generate regime timeline visualization."""
    try:
        from platform.market_diagnostic.knowledge_base_manager import KnowledgeBaseManager

        kb = KnowledgeBaseManager()

        end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start_date or (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

        timeline_text = kb.generate_regime_timeline_ascii(
            start_date=start_date,
            end_date=end_date,
            width=args.width,
        )

        print(timeline_text)

        print()
        dist_text = kb.generate_regime_distribution_text(
            start_date=start_date,
            end_date=end_date,
        )
        print(dist_text)

        return 0

    except Exception as exc:
        print(f"[CLI] Error generating timeline: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_stats(args) -> int:
    """Show regime statistics."""
    try:
        from platform.market_diagnostic.knowledge_base_manager import KnowledgeBaseManager

        kb = KnowledgeBaseManager()

        stats = kb.get_regime_stats(
            start_date=args.start_date,
            end_date=args.end_date,
        )

        print("[CLI] Regime Statistics")
        print("="*70)
        print(f"{'Regime':30s} {'Count':>6} {'Avg Conf':>8} {'Avg Score':>9} {'Date Range'}")
        print("-"*70)

        for stat in stats:
            date_range = f"{stat.date_range[0][:10]} ~ {stat.date_range[1][:10]}"
            print(
                f"{stat.regime:30s} "
                f"{stat.count:>6} "
                f"{stat.avg_confidence:>8.0%} "
                f"{stat.avg_regime_score:>9.1f} "
                f"{date_range}"
            )

        return 0

    except Exception as exc:
        print(f"[CLI] Error showing stats: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_strategies(args) -> int:
    """Show strategy mapping for a regime."""
    try:
        from platform.market_diagnostic.strategy_mapping import (
            get_regime_recommendation,
            get_regime_summary_table,
        )

        if args.regime:
            rec = get_regime_recommendation(args.regime)
            if rec:
                print(f"[CLI] Strategy mapping for: {rec.display_name}")
                print("="*60)
                print(f"Description: {rec.description}")
                print()
                print("Allocations:")
                for a in rec.allocations:
                    weight_pct = a.allocation_weight * 100
                    print(f"  - {a.strategy_group}: {weight_pct:.0f}% (risk: {a.risk_level})")
                print()
                print(f"Suitable investors: {', '.join(rec.suitable_investors)}")
                print(f"Expected return: {rec.expected_return}")
            else:
                print(f"[CLI] Unknown regime: {args.regime}")
                return 1
        else:
            summary = get_regime_summary_table()
            print("[CLI] All Regime Strategy Mappings")
            print("="*80)
            print(f"{'Regime':25s} {'Display Name':20s} {'Strategies':>12} {'Investors'}")
            print("-"*80)
            for row in summary:
                print(
                    f"{row['regime']:25s} "
                    f"{row['display_name']:20s} "
                    f"{row['strategy_count']:>12}    "
                    f"{row['suitable_investors']}"
                )

        return 0

    except Exception as exc:
        print(f"[CLI] Error showing strategies: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Market Diagnostic CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run diagnostic and generate report")
    run_parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    run_parser.add_argument("--output", help="Output directory")

    # query command
    query_parser = subparsers.add_parser("query", help="Query historical reports")
    query_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    query_parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    query_parser.add_argument("--regime", help="Regime filter")
    query_parser.add_argument("--min-confidence", type=float, help="Minimum confidence")
    query_parser.add_argument("--trend-state", help="Trend state filter")
    query_parser.add_argument("--breadth-state", help="Breadth state filter")
    query_parser.add_argument("--sentiment-state", help="Sentiment state filter")
    query_parser.add_argument("--risk-state", help="Risk state filter")
    query_parser.add_argument("--format", choices=["summary", "json"], default="summary")

    # timeline command
    timeline_parser = subparsers.add_parser("timeline", help="Show regime timeline")
    timeline_parser.add_argument("--days", type=int, default=30, help="Days to look back")
    timeline_parser.add_argument("--width", type=int, default=80, help="Display width")
    timeline_parser.add_argument("--start-date", help="Start date override")
    timeline_parser.add_argument("--end-date", help="End date override")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show regime statistics")
    stats_parser.add_argument("--start-date", help="Start date")
    stats_parser.add_argument("--end-date", help="End date")

    # strategies command
    strategies_parser = subparsers.add_parser("strategies", help="Show strategy mappings")
    strategies_parser.add_argument("--regime", help="Specific regime (optional)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "timeline":
        return cmd_timeline(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "strategies":
        return cmd_strategies(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())