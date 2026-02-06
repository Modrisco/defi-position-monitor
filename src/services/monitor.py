"""Main monitoring orchestration service"""
import asyncio
from datetime import datetime
from typing import List

from ..config import (
    WALLET_ADDRESS,
    LTV_WARNING_THRESHOLD,
    LTV_CRITICAL_THRESHOLD,
)
from ..models import PositionData
from ..rpc import SuiClient
from ..notifications import TelegramNotifier, EmailNotifier
from .price_service import PriceService
from .position_service import PositionService


class Monitor:
    """Orchestrates position monitoring and alerting"""

    def __init__(
        self,
        wallet_address: str = None,
        ltv_warning_threshold: float = None,
        ltv_critical_threshold: float = None,
    ):
        self.wallet_address = wallet_address or WALLET_ADDRESS
        self.ltv_warning_threshold = ltv_warning_threshold or LTV_WARNING_THRESHOLD
        self.ltv_critical_threshold = ltv_critical_threshold or LTV_CRITICAL_THRESHOLD

        # Initialize services
        self.sui_client = SuiClient()
        self.price_service = PriceService()
        self.position_service = PositionService(self.sui_client)
        self.telegram = TelegramNotifier()
        self.email = EmailNotifier()

    def _format_wallet(self) -> str:
        """Format wallet address for display"""
        return f"{self.wallet_address[:10]}...{self.wallet_address[-6:]}"

    def _get_status(self, ltv: float) -> str:
        """Get status emoji based on LTV"""
        if ltv >= self.ltv_critical_threshold:
            return "🚨 CRITICAL"
        elif ltv >= self.ltv_warning_threshold:
            return "⚠️ WARNING"
        return "✅ Healthy"

    def _build_log_message(self, position: PositionData) -> str:
        """Build log message for Telegram"""
        status = self._get_status(position.ltv)
        return f"""
📊 <b>Bluefin Position Check</b>

<b>Status:</b> {status}

<b>Collateral Assets:</b> {position.asset}
<b>Collateral Value:</b> ${position.collateral_value:,.2f}

<b>Borrowed Assets:</b> {position.borrowed_asset}
<b>Borrowed Value:</b> ${position.borrowed_value:,.2f}

<b>LTV:</b> {position.ltv:.2f}%
<b>Health Factor:</b> {position.health_factor:.2f}
<b>Liquidation Threshold:</b> {position.liquidation_threshold:.2f}%

Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """

    def _build_critical_alert(self, position: PositionData) -> str:
        """Build critical alert message"""
        return f"""
🚨 <b>CRITICAL ALERT: High LTV Ratio!</b>

<b>Collateral:</b> {position.asset}
<b>Collateral Value:</b> ${position.collateral_value:,.2f}

<b>Borrowed:</b> {position.borrowed_asset}
<b>Borrowed Value:</b> ${position.borrowed_value:,.2f}

<b>LTV:</b> {position.ltv:.2f}%
<b>Health Factor:</b> {position.health_factor:.2f}
<b>Liquidation Threshold:</b> {position.liquidation_threshold:.2f}%

⚠️ ACTION REQUIRED: Add more collateral or repay debt immediately!

Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """

    def _build_warning_alert(self, position: PositionData) -> str:
        """Build warning alert message"""
        return f"""
⚠️ <b>WARNING: Elevated LTV Ratio</b>

<b>Collateral:</b> {position.asset}
<b>Collateral Value:</b> ${position.collateral_value:,.2f}

<b>Borrowed:</b> {position.borrowed_asset}
<b>Borrowed Value:</b> ${position.borrowed_value:,.2f}

<b>LTV:</b> {position.ltv:.2f}%
<b>Health Factor:</b> {position.health_factor:.2f}
<b>Liquidation Threshold:</b> {position.liquidation_threshold:.2f}%

Consider adding collateral or reducing your borrowed amount.

Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """

    async def check_and_alert(self):
        """Check positions, send logs, and send alerts if needed"""
        # Fetch current prices from Pyth
        prices = await self.price_service.fetch_prices()

        # Fetch positions with real-time price calculation
        positions = await self.position_service.fetch_positions(self.wallet_address, prices)

        if not positions:
            log_msg = f"""
📊 <b>Bluefin Position Check</b>

No active positions found.

Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
            await self.telegram.send_log(log_msg, silent=False)
            return

        for position in positions:
            print(f"\nPosition Status:")
            print(f"  Collateral Value: ${position.collateral_value:.2f}")
            print(f"  Borrowed Value: ${position.borrowed_value:.2f}")
            print(f"  LTV: {position.ltv:.2f}%")
            print(f"  Health Factor: {position.health_factor:.2f}")
            print(f"  Liquidation Threshold: {position.liquidation_threshold:.2f}%")

            # Always send log to logs bot
            log_msg = self._build_log_message(position)
            await self.telegram.send_log(log_msg, silent=False)

            # Send alert only when thresholds exceeded
            if position.ltv >= self.ltv_critical_threshold:
                alert_msg = self._build_critical_alert(position)
                await self.email.send_alert("🚨 CRITICAL: Liquidation Risk!", alert_msg)
                await self.telegram.send_alert(alert_msg)

            elif position.ltv >= self.ltv_warning_threshold:
                alert_msg = self._build_warning_alert(position)
                await self.email.send_alert("⚠️ WARNING: High LTV", alert_msg)
                await self.telegram.send_alert(alert_msg)

    async def generate_daily_report(self):
        """Generate and send daily position report via Telegram alert bot"""
        prices = await self.price_service.fetch_prices()
        positions = await self.position_service.fetch_positions(self.wallet_address, prices)

        if not positions:
            report = f"""
📋 <b>Daily Bluefin AlphaLend Report</b>

No active positions found.

Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
        else:
            position_lines = ""
            for i, position in enumerate(positions, 1):
                status = self._get_status(position.ltv)
                position_lines += f"""
<b>Position {i}:</b> {status}
  Collateral: {position.asset} — ${position.collateral_value:,.2f}
  Borrowed: {position.borrowed_asset} — ${position.borrowed_value:,.2f}
  LTV: {position.ltv:.2f}%
  Health Factor: {position.health_factor:.2f}
  Liquidation Threshold: {position.liquidation_threshold:.2f}%
"""

            report = f"""
📋 <b>Daily Bluefin AlphaLend Report</b>
{position_lines}
Wallet: <code>{self._format_wallet()}</code>
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """

        await self.telegram.send_alert(report)
        print(report)

    async def run_continuous(self, check_interval_minutes: int = 15):
        """Run continuous monitoring loop"""
        print(f"Starting continuous monitoring (checking every {check_interval_minutes} minutes)")

        while True:
            try:
                await self.check_and_alert()
                await asyncio.sleep(check_interval_minutes * 60)
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
