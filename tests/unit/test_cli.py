"""Unit tests for CLI argument parsing."""
from __future__ import annotations

import pytest

from src.cli import build_parser


class TestBuildParser:
    def test_check_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check"])
        assert args.command == "check"

    def test_report_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["report"])
        assert args.command == "report"

    def test_monitor_command_default_interval(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["monitor"])
        assert args.command == "monitor"
        assert args.interval is None

    def test_monitor_command_custom_interval(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["monitor", "10"])
        assert args.command == "monitor"
        assert args.interval == 10

    def test_config_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--config", "/tmp/c.yaml", "check"])
        assert args.config == "/tmp/c.yaml"

    def test_log_level_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--log-level", "DEBUG", "check"])
        assert args.log_level == "DEBUG"

    def test_no_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
