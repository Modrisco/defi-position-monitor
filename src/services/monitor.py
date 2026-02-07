"""Generic monitoring orchestration — iterates wallets x protocols."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import AppConfig
from ..chains.sui import SuiClient
from ..interfaces.notifier import Notifier
from ..interfaces.price_oracle import PriceOracle
from ..interfaces.protocol_adapter import ProtocolAdapter
from ..models import AssetDetail, PositionData
from ..notifications import EmailNotifier, TelegramNotifier
from ..oracles import PythOracle
from ..protocols.alphalend import AlphaLendAdapter

logger = logging.getLogger(__name__)

# Registry of protocol adapter factories keyed by protocol name.
_PROTOCOL_FACTORIES: dict[str, Any] = {
    "alphalend": lambda client, cfg: AlphaLendAdapter(client, cfg),
}


class Monitor:
    """Orchestrates position monitoring and alerting across wallets and protocols."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._thresholds = config.monitor.thresholds

        # Build chain clients
        self._chain_clients: dict[str, SuiClient] = {}
        for chain_name, chain_cfg in config.chains.items():
            self._chain_clients[chain_name] = SuiClient(chain_cfg)

        # Build protocol adapters
        self._adapters: dict[str, ProtocolAdapter] = {}
        for proto_name, proto_cfg in config.protocols.items():
            chain_client = self._chain_clients[proto_cfg.chain]
            factory = _PROTOCOL_FACTORIES.get(proto_name)
            if factory:
                self._adapters[proto_name] = factory(chain_client, proto_cfg)
            else:
                logger.warning("No adapter factory for protocol '%s'", proto_name)

        # Build price oracle
        self._oracle: PriceOracle = PythOracle(config.price_oracle.pyth)

        # Build notifiers
        self._notifiers: list[Notifier] = []
        if config.notifications.telegram.enabled:
            self._notifiers.append(
                TelegramNotifier(config.notifications.telegram)
            )
        if config.notifications.email.enabled:
            self._notifiers.append(EmailNotifier(config.notifications.email))

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_wallet(address: str) -> str:
        if len(address) > 16:
            return f"{address[:10]}...{address[-6:]}"
        return address

    def _get_status(self, ltv: float) -> str:
        if ltv >= self._thresholds.ltv_critical:
            return "🚨 CRITICAL"
        if ltv >= self._thresholds.ltv_warning:
            return "⚠️ WARNING"
        return "✅ Healthy"

    @staticmethod
    def _now_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _asset_symbols(assets: tuple[AssetDetail, ...]) -> str:
        """Return comma-separated asset symbols, e.g. 'USDC, XBTC'."""
        return ", ".join(a.symbol for a in assets) if assets else "—"

    def _build_log_message(
        self,
        position: PositionData,
        wallet_label: str,
        proto_name: str,
        chain: str,
    ) -> str:
        status = self._get_status(position.ltv)
        collateral_syms = self._asset_symbols(position.collateral_assets)
        borrowed_syms = self._asset_symbols(position.borrowed_assets)
        return (
            f"📊 {wallet_label} · {proto_name} · {chain.upper()}\n"
            f"\n"
            f"{status}\n"
            f"\n"
            f"Collateral: {collateral_syms} — ${position.collateral_value:,.2f}\n"
            f"Borrowed: {borrowed_syms} — ${position.borrowed_value:,.2f}\n"
            f"LTV: {position.ltv:.2f}% · HF: {position.health_factor:.2f}\n"
            f"\n"
            f"{self._now_str()} UTC"
        )

    def _build_critical_alert(
        self,
        position: PositionData,
        wallet_address: str,
        wallet_label: str,
        proto_name: str,
        chain: str,
    ) -> str:
        collateral_syms = self._asset_symbols(position.collateral_assets)
        borrowed_syms = self._asset_symbols(position.borrowed_assets)
        return (
            f"🚨 CRITICAL — LTV {position.ltv:.2f}%\n"
            f"\n"
            f"{wallet_label} · {proto_name} · {chain.upper()}\n"
            f"\n"
            f"Collateral: {collateral_syms}\n"
            f"  ${position.collateral_value:,.2f}\n"
            f"\n"
            f"Borrowed: {borrowed_syms}\n"
            f"  ${position.borrowed_value:,.2f}\n"
            f"\n"
            f"Health Factor: {position.health_factor:.2f}\n"
            f"Liquidation Threshold: {position.liquidation_threshold:.2f}%\n"
            f"\n"
            f"⚠️ Add collateral or repay debt immediately!\n"
            f"\n"
            f"Wallet: {self._format_wallet(wallet_address)}\n"
            f"{self._now_str()} UTC"
        )

    def _build_warning_alert(
        self,
        position: PositionData,
        wallet_address: str,
        wallet_label: str,
        proto_name: str,
        chain: str,
    ) -> str:
        collateral_syms = self._asset_symbols(position.collateral_assets)
        borrowed_syms = self._asset_symbols(position.borrowed_assets)
        return (
            f"⚠️ WARNING — LTV {position.ltv:.2f}%\n"
            f"\n"
            f"{wallet_label} · {proto_name} · {chain.upper()}\n"
            f"\n"
            f"Collateral: {collateral_syms}\n"
            f"  ${position.collateral_value:,.2f}\n"
            f"\n"
            f"Borrowed: {borrowed_syms}\n"
            f"  ${position.borrowed_value:,.2f}\n"
            f"\n"
            f"Health Factor: {position.health_factor:.2f}\n"
            f"Liquidation Threshold: {position.liquidation_threshold:.2f}%\n"
            f"\n"
            f"Consider adding collateral or reducing borrowed amount.\n"
            f"\n"
            f"Wallet: {self._format_wallet(wallet_address)}\n"
            f"{self._now_str()} UTC"
        )

    # ------------------------------------------------------------------
    # Notification dispatch
    # ------------------------------------------------------------------

    async def _send_log(self, message: str, silent: bool = False) -> None:
        for notifier in self._notifiers:
            try:
                await notifier.send_log(message, silent=silent)
            except Exception as e:
                logger.error("Notifier send_log failed: %s", e)

    async def _send_alert(self, message: str, subject: str = "") -> None:
        for notifier in self._notifiers:
            try:
                await notifier.send_alert(message, subject=subject)
            except Exception as e:
                logger.error("Notifier send_alert failed: %s", e)

    # ------------------------------------------------------------------
    # Core workflows
    # ------------------------------------------------------------------

    async def check_and_alert(self) -> None:
        """Check all wallet×protocol positions and send alerts when needed."""
        prices = await self._oracle.fetch_prices()

        for wallet_cfg in self._config.wallets:
            for proto_name in wallet_cfg.protocols:
                adapter = self._adapters.get(proto_name)
                if not adapter:
                    continue

                positions = await adapter.fetch_positions(
                    wallet_cfg.address, prices
                )

                if not positions:
                    log_msg = (
                        f"📊 {wallet_cfg.label} · {proto_name} · {wallet_cfg.chain.upper()}\n"
                        f"\n"
                        f"No active positions found.\n"
                        f"\n"
                        f"{self._now_str()} UTC"
                    )
                    await self._send_log(log_msg, silent=False)
                    continue

                for position in positions:
                    logger.info(
                        "Position — %s · %s · Collateral: $%.2f  Borrowed: $%.2f  LTV: %.2f%%  HF: %.2f",
                        wallet_cfg.label,
                        proto_name,
                        position.collateral_value,
                        position.borrowed_value,
                        position.ltv,
                        position.health_factor,
                    )

                    log_msg = self._build_log_message(
                        position, wallet_cfg.label, proto_name, wallet_cfg.chain,
                    )
                    await self._send_log(log_msg, silent=False)

                    if position.ltv >= self._thresholds.ltv_critical:
                        alert_msg = self._build_critical_alert(
                            position, wallet_cfg.address,
                            wallet_cfg.label, proto_name, wallet_cfg.chain,
                        )
                        await self._send_alert(
                            alert_msg, subject="🚨 CRITICAL: Liquidation Risk!"
                        )
                    elif position.ltv >= self._thresholds.ltv_warning:
                        alert_msg = self._build_warning_alert(
                            position, wallet_cfg.address,
                            wallet_cfg.label, proto_name, wallet_cfg.chain,
                        )
                        await self._send_alert(
                            alert_msg, subject="⚠️ WARNING: High LTV"
                        )

    async def generate_daily_report(self) -> None:
        """Generate and send daily position report grouped by wallet → protocol."""
        prices = await self._oracle.fetch_prices()

        sections: list[str] = []
        has_positions = False

        for wallet_cfg in self._config.wallets:
            wallet_lines: list[str] = []

            for proto_name in wallet_cfg.protocols:
                adapter = self._adapters.get(proto_name)
                if not adapter:
                    continue

                positions = await adapter.fetch_positions(
                    wallet_cfg.address, prices
                )

                for position in positions:
                    has_positions = True
                    status = self._get_status(position.ltv)
                    wallet_lines.append(
                        f"{proto_name} · {status}\n"
                        f"  Collateral: ${position.collateral_value:,.2f}\n"
                        f"  Borrowed: ${position.borrowed_value:,.2f}\n"
                        f"  LTV: {position.ltv:.2f}% · HF: {position.health_factor:.2f}"
                    )

            if wallet_lines:
                header = f"━━ {wallet_cfg.label} ({wallet_cfg.chain.upper()}) ━━"
                sections.append(header + "\n\n" + "\n\n".join(wallet_lines))

        body = "\n\n".join(sections) if sections else "No active positions found."

        report = (
            f"📋 Daily DeFi Position Report\n"
            f"\n"
            f"{body}\n"
            f"\n"
            f"{self._now_str()} UTC"
        )

        await self._send_alert(report)
        logger.info("Daily report sent")

    async def run_continuous(self, check_interval_minutes: int | None = None) -> None:
        """Run continuous monitoring loop."""
        interval = check_interval_minutes or self._config.monitor.check_interval_minutes
        logger.info(
            "Starting continuous monitoring (checking every %d minutes)", interval
        )

        while True:
            try:
                await self.check_and_alert()
                await asyncio.sleep(interval * 60)
            except Exception as e:
                logger.error("Error in monitoring loop: %s", e)
                await asyncio.sleep(60)
