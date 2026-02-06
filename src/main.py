#!/usr/bin/env python3
"""
Bluefin AlphaLend Position Monitor
Entry point for the monitoring application
"""
import asyncio
import sys

from .services import Monitor


async def main():
    """Main entry point"""
    monitor = Monitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "check":
            await monitor.check_and_alert()

        elif command == "report":
            await monitor.generate_daily_report()

        elif command == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 15
            await monitor.run_continuous(interval)

        else:
            print(f"Unknown command: {command}")
            print_usage()
    else:
        print_usage()


def print_usage():
    """Print usage information"""
    print("Usage:")
    print("  python -m src.main check          - Check position (logs + alerts if needed)")
    print("  python -m src.main report         - Generate daily report")
    print("  python -m src.main monitor [mins] - Continuous monitoring")


if __name__ == "__main__":
    asyncio.run(main())
