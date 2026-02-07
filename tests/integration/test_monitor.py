"""Integration tests for the Monitor service — full flow with mocked I/O."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig
from src.models import PositionData
from src.services.monitor import Monitor


@pytest.fixture()
def monitor(sample_app_config: AppConfig) -> Monitor:
    return Monitor(sample_app_config)


class TestCheckAndAlert:
    @pytest.mark.asyncio
    async def test_healthy_position_sends_log_only(
        self, monitor: Monitor, sample_position: PositionData
    ) -> None:
        """A healthy position (LTV 50%) should send a log but no alert."""
        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {"SUI": 3.50, "USDC": 1.0}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = [sample_position]
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.check_and_alert()

        # Should have called send_log (for the position log)
        mock_notifier.send_log.assert_called()
        log_msg = mock_notifier.send_log.call_args[0][0]
        assert "test-wallet" in log_msg
        assert "alphalend" in log_msg
        assert "SUI" in log_msg
        assert "Healthy" in log_msg
        # Should NOT have called send_alert (LTV 50% < 70%)
        mock_notifier.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_position_sends_alert(
        self, monitor: Monitor
    ) -> None:
        """A critical position (LTV 85%) should trigger an alert."""
        critical_position = PositionData(
            collateral_value=10000.0,
            borrowed_value=8500.0,
            ltv=85.0,
            health_factor=1.0,
            liquidation_threshold=85.0,
            asset="SUI",
            borrowed_asset="USDC",
            protocol_name="alphalend",
            wallet_label="test-wallet",
        )

        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {"SUI": 3.50}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = [critical_position]
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.check_and_alert()

        mock_notifier.send_alert.assert_called_once()
        call_args = mock_notifier.send_alert.call_args
        assert "CRITICAL" in call_args.kwargs.get("subject", call_args[1].get("subject", ""))
        alert_msg = call_args[0][0]
        assert "test-wallet" in alert_msg
        assert "alphalend" in alert_msg

    @pytest.mark.asyncio
    async def test_warning_position_sends_alert(self, monitor: Monitor) -> None:
        """A warning position (LTV 75%) should trigger a warning alert."""
        warning_position = PositionData(
            collateral_value=10000.0,
            borrowed_value=7500.0,
            ltv=75.0,
            health_factor=1.13,
            liquidation_threshold=85.0,
            asset="SUI",
            borrowed_asset="USDC",
            protocol_name="alphalend",
            wallet_label="test-wallet",
        )

        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = [warning_position]
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.check_and_alert()

        mock_notifier.send_alert.assert_called_once()
        call_args = mock_notifier.send_alert.call_args
        assert "WARNING" in call_args.kwargs.get("subject", call_args[1].get("subject", ""))
        alert_msg = call_args[0][0]
        assert "test-wallet" in alert_msg
        assert "alphalend" in alert_msg

    @pytest.mark.asyncio
    async def test_no_positions_sends_log(self, monitor: Monitor) -> None:
        """When no positions found, send a log message with wallet/protocol context."""
        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = []
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.check_and_alert()

        mock_notifier.send_log.assert_called_once()
        call_msg = mock_notifier.send_log.call_args[0][0]
        assert "No active positions" in call_msg
        assert "test-wallet" in call_msg
        assert "alphalend" in call_msg


class TestGenerateDailyReport:
    @pytest.mark.asyncio
    async def test_report_with_positions(
        self, monitor: Monitor, sample_position: PositionData
    ) -> None:
        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = [sample_position]
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.generate_daily_report()

        mock_notifier.send_alert.assert_called_once()
        report = mock_notifier.send_alert.call_args[0][0]
        assert "Daily DeFi Position Report" in report
        assert "test-wallet" in report
        assert "SUI" in report
        assert "alphalend" in report
        assert "Healthy" in report

    @pytest.mark.asyncio
    async def test_report_no_positions(self, monitor: Monitor) -> None:
        mock_oracle = AsyncMock()
        mock_oracle.fetch_prices.return_value = {}
        monitor._oracle = mock_oracle

        mock_adapter = AsyncMock()
        mock_adapter.fetch_positions.return_value = []
        monitor._adapters["alphalend"] = mock_adapter

        mock_notifier = AsyncMock()
        monitor._notifiers = [mock_notifier]

        await monitor.generate_daily_report()

        mock_notifier.send_alert.assert_called_once()
        report = mock_notifier.send_alert.call_args[0][0]
        assert "No active positions" in report


class TestFormatHelpers:
    def test_format_wallet_long(self, monitor: Monitor) -> None:
        result = Monitor._format_wallet("0x1234567890abcdef1234567890")
        assert result == "0x12345678...567890"

    def test_format_wallet_short(self, monitor: Monitor) -> None:
        result = Monitor._format_wallet("0x123")
        assert result == "0x123"

    def test_get_status_healthy(self, monitor: Monitor) -> None:
        assert "Healthy" in monitor._get_status(50.0)

    def test_get_status_warning(self, monitor: Monitor) -> None:
        assert "WARNING" in monitor._get_status(75.0)

    def test_get_status_critical(self, monitor: Monitor) -> None:
        assert "CRITICAL" in monitor._get_status(85.0)
