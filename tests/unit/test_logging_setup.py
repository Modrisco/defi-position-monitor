"""Unit tests for logging configuration."""
from __future__ import annotations

import logging

from src.logging_setup import configure_logging


class TestConfigureLogging:
    def test_sets_info_level(self) -> None:
        configure_logging("INFO")
        assert logging.getLogger().level == logging.INFO

    def test_sets_debug_level(self) -> None:
        configure_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_silences_aiohttp(self) -> None:
        configure_logging("DEBUG")
        assert logging.getLogger("aiohttp").level == logging.WARNING

    def test_invalid_level_defaults_to_info(self) -> None:
        configure_logging("NONEXISTENT")
        assert logging.getLogger().level == logging.INFO
