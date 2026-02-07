"""Command-line interface for the DeFi position monitor."""
from __future__ import annotations

import argparse
import asyncio
import sys

from .config import load_config
from .logging_setup import configure_logging
from .services import Monitor


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse CLI parser."""
    parser = argparse.ArgumentParser(
        prog="defi-position-monitor",
        description="Universal DeFi position monitor",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: config.yaml in project root)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Single position check with alerts")
    sub.add_parser("report", help="Generate daily position report")

    monitor_parser = sub.add_parser("monitor", help="Continuous monitoring loop")
    monitor_parser.add_argument(
        "interval",
        nargs="?",
        type=int,
        default=None,
        help="Check interval in minutes (overrides config)",
    )

    return parser


async def _run(args: argparse.Namespace) -> None:
    """Execute the selected command."""
    configure_logging(args.log_level)
    config = load_config(args.config)
    monitor = Monitor(config)

    if args.command == "check":
        await monitor.check_and_alert()
    elif args.command == "report":
        await monitor.generate_daily_report()
    elif args.command == "monitor":
        await monitor.run_continuous(args.interval)
    else:
        build_parser().print_help()
        sys.exit(1)


def main() -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    asyncio.run(_run(args))
