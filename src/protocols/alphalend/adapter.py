"""AlphaLend protocol adapter — fetches and parses lending positions."""
from __future__ import annotations

import logging
from typing import Any

from ...config import ProtocolConfig
from ...interfaces.chain import ChainClient
from ...models import AssetDetail, PositionData
from . import parser

logger = logging.getLogger(__name__)


class AlphaLendAdapter:
    """Fetch and parse AlphaLend positions on SUI."""

    def __init__(self, chain_client: ChainClient, config: ProtocolConfig) -> None:
        self._client = chain_client
        self._config = config
        self._package_id = config.contracts.get("package_id", "")
        self._positions_table_id = config.contracts.get("positions_table_id", "")
        self._markets_table_id = config.contracts.get("markets_table_id", "")
        self._market_cache: dict[int, dict[str, Any]] = {}

    @property
    def protocol_name(self) -> str:
        return "alphalend"

    async def _get_position_capabilities(self, wallet_address: str) -> list[str]:
        """Find PositionCap objects for AlphaLend in the wallet."""
        objects = await self._client.get_owned_objects(wallet_address)
        caps: list[str] = []

        for obj in objects:
            obj_type = obj.get("data", {}).get("type", "")
            object_id = obj.get("data", {}).get("objectId", "")

            type_lower = obj_type.lower()
            if (
                "positioncap" in type_lower
                or "position_cap" in type_lower
                or self._package_id in obj_type
            ):
                if object_id:
                    caps.append(object_id)

        return caps

    async def _get_position_data(self, position_id: str) -> dict[str, Any]:
        """Fetch position data from the protocol's positions table."""
        try:
            result = await self._client.get_dynamic_field_object(
                self._positions_table_id, "0x2::object::ID", position_id
            )
            if not result:
                logger.warning("No position data found for %s", position_id)
                return {}

            content = result.get("content", {})
            fields = content.get("fields", {})
            return fields.get("value", {}).get("fields", {})
        except Exception as e:
            logger.error("Error fetching position data: %s", e)
            return {}

    async def _get_market_info(self, market_id: int) -> dict[str, Any]:
        """Fetch market info (with caching)."""
        if market_id in self._market_cache:
            return self._market_cache[market_id]

        try:
            result = await self._client.get_dynamic_field_object(
                self._markets_table_id, "u64", str(market_id)
            )
            if not result:
                return {}

            content = result.get("content", {})
            fields = content.get("fields", {})
            market = fields.get("value", {}).get("fields", {})

            self._market_cache[market_id] = market
            return market
        except Exception as e:
            logger.error("Error fetching market %s: %s", market_id, e)
            return {}

    async def fetch_positions(
        self, wallet_address: str, prices: dict[str, float]
    ) -> list[PositionData]:
        """Fetch all lending positions for a wallet with real-time pricing."""
        logger.info("Checking AlphaLend positions for wallet: %s", wallet_address)

        position_caps = await self._get_position_capabilities(wallet_address)
        logger.info("Found %d position capabilities", len(position_caps))

        positions: list[PositionData] = []

        for cap_id in position_caps:
            details = await self._client.get_object(cap_id)
            cap_content = (
                details.get("data", {}).get("content", {}).get("fields", {})
            )
            position_id = cap_content.get("position_id")

            if not position_id:
                logger.debug("No position_id found in PositionCap %s", cap_id)
                continue

            logger.info("Fetching position data for %s", position_id)

            position_data = await self._get_position_data(position_id)
            if not position_data:
                logger.warning("Could not fetch position data for %s", position_id)
                continue

            position = await self._parse_position(position_data, position_id, prices)
            if position:
                positions.append(position)

        return positions

    async def _parse_position(
        self,
        position_data: dict[str, Any],
        position_id: str,
        prices: dict[str, float],
    ) -> PositionData | None:
        """Parse raw position data into a PositionData model."""
        token_decimals = self._config.token_decimals
        token_aliases = self._config.token_aliases
        liquidation_threshold = self._config.liquidation_threshold

        # Parse collaterals
        collaterals_raw = (
            position_data.get("collaterals", {})
            .get("fields", {})
            .get("contents", [])
        )
        collateral_details: list[dict[str, Any]] = []
        total_collateral_usd = 0.0

        for entry in collaterals_raw:
            market_id = int(entry.get("fields", {}).get("key", 0))
            market_info = await self._get_market_info(market_id)
            detail = parser.parse_collateral_entry(
                entry, market_info, prices, token_decimals, token_aliases
            )
            collateral_details.append(detail)
            total_collateral_usd += detail["usd_value"]

        # Parse loans
        loans_raw = position_data.get("loans", [])
        loan_details: list[dict[str, Any]] = []
        total_loan_usd = 0.0

        for entry in loans_raw:
            detail = parser.parse_loan_entry(
                entry, prices, token_decimals, token_aliases
            )
            loan_details.append(detail)
            total_loan_usd += detail["usd_value"]

        ltv = parser.calc_ltv(total_collateral_usd, total_loan_usd)
        health_factor = parser.calc_health_factor(
            total_collateral_usd, total_loan_usd, liquidation_threshold
        )

        is_healthy = position_data.get("is_position_healthy", True)
        is_liquidatable = position_data.get("is_position_liquidatable", False)

        # Log position summary
        logger.info("=" * 60)
        logger.info("POSITION SUMMARY (Real-time prices)")
        logger.info("=" * 60)
        logger.info("  Position ID: %s", position_id)
        logger.info("  Collateral Assets:")
        for d in collateral_details:
            logger.info(
                "    - %s: %.6f x $%.2f = $%.2f",
                d["symbol"], d["amount"], d["price"], d["usd_value"],
            )
        logger.info("  Total Collateral:     $%.2f", total_collateral_usd)
        logger.info("  Borrowed Assets:")
        for d in loan_details:
            logger.info(
                "    - %s: %.6f x $%.2f = $%.2f",
                d["symbol"], d["amount"], d["price"], d["usd_value"],
            )
        logger.info("  Total Borrowed:       $%.2f", total_loan_usd)
        logger.info("  LTV:                  %.2f%%", ltv)
        logger.info("  Health Factor:        %.4f", health_factor)
        logger.info("  Liquidation Threshold: %.2f%%", liquidation_threshold)
        logger.info("  Position Healthy:     %s", "Yes" if is_healthy else "NO!")
        logger.info(
            "  Liquidatable:         %s",
            "YES - DANGER!" if is_liquidatable else "No",
        )
        logger.info("=" * 60)

        return PositionData(
            collateral_value=total_collateral_usd,
            borrowed_value=total_loan_usd,
            ltv=ltv,
            health_factor=health_factor,
            liquidation_threshold=liquidation_threshold,
            asset=parser.build_asset_summary(collateral_details),
            borrowed_asset=parser.build_asset_summary(loan_details),
            protocol_name=self.protocol_name,
            collateral_assets=tuple(
                AssetDetail(
                    symbol=d["symbol"],
                    amount=d["amount"],
                    price=d["price"],
                    usd_value=d["usd_value"],
                )
                for d in collateral_details
            ),
            borrowed_assets=tuple(
                AssetDetail(
                    symbol=d["symbol"],
                    amount=d["amount"],
                    price=d["price"],
                    usd_value=d["usd_value"],
                )
                for d in loan_details
            ),
        )
