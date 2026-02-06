"""AlphaLend position fetching service"""
from typing import Dict, List

from ..config import (
    ALPHALEND_PACKAGE_ID,
    POSITIONS_TABLE_ID,
    MARKETS_TABLE_ID,
    USD_PRECISION,
)
from ..models import PositionData
from ..rpc import SuiClient


class PositionService:
    """Fetch and parse AlphaLend positions"""

    def __init__(self, sui_client: SuiClient):
        self.sui_client = sui_client

    async def get_position_capabilities(self, wallet_address: str) -> List[str]:
        """Find position capability objects for AlphaLend"""
        objects = await self.sui_client.get_owned_objects(wallet_address)
        position_caps = []

        for obj in objects:
            obj_type = obj.get("data", {}).get("type", "")
            object_id = obj.get("data", {}).get("objectId", "")

            type_lower = obj_type.lower()
            if (
                "positioncap" in type_lower
                or "position_cap" in type_lower
                or ALPHALEND_PACKAGE_ID in obj_type
            ):
                if object_id:
                    position_caps.append(object_id)

        return position_caps

    async def get_position_data(self, position_id: str) -> Dict:
        """Fetch position data from the protocol's positions table"""
        try:
            result = await self.sui_client.get_dynamic_field_object(
                POSITIONS_TABLE_ID,
                "0x2::object::ID",
                position_id
            )

            if not result:
                print(f"No position data found for {position_id}")
                return {}

            content = result.get("content", {})
            fields = content.get("fields", {})
            position = fields.get("value", {}).get("fields", {})

            return position
        except Exception as e:
            print(f"Error fetching position data: {e}")
            return {}

    async def get_market_info(self, market_id: int) -> Dict:
        """Fetch market info to get coin type and decimals"""
        try:
            result = await self.sui_client.get_dynamic_field_object(
                MARKETS_TABLE_ID,
                "u64",
                str(market_id)
            )

            if not result:
                return {}

            content = result.get("content", {})
            fields = content.get("fields", {})
            market = fields.get("value", {}).get("fields", {})

            return market
        except Exception as e:
            print(f"Error fetching market {market_id}: {e}")
            return {}

    async def fetch_positions(self, wallet_address: str) -> List[PositionData]:
        """Fetch all lending positions for a wallet"""
        print(f"Checking positions for wallet: {wallet_address}")

        position_caps = await self.get_position_capabilities(wallet_address)
        print(f"Found {len(position_caps)} position capabilities")

        positions = []

        for cap_id in position_caps:
            details = await self.sui_client.get_object(cap_id)
            cap_content = details.get("data", {}).get("content", {}).get("fields", {})
            position_id = cap_content.get("position_id")

            if not position_id:
                print(f"  No position_id found in PositionCap {cap_id}")
                continue

            print(f"\n--- Fetching position data for {position_id} ---")

            position_data = await self.get_position_data(position_id)

            if not position_data:
                print(f"  Could not fetch position data")
                continue

            position = await self._parse_position_data(position_data, position_id)
            if position:
                positions.append(position)

        return positions

    async def _parse_position_data(
        self, position_data: Dict, position_id: str
    ) -> PositionData:
        """Parse raw position data into PositionData object"""
        # Extract USD values (stored with 18 decimal precision)
        total_collateral_usd_raw = int(
            position_data.get("total_collateral_usd", {})
            .get("fields", {})
            .get("value", "0")
        )
        total_loan_usd_raw = int(
            position_data.get("total_loan_usd", {})
            .get("fields", {})
            .get("value", "0")
        )
        liquidation_value_raw = int(
            position_data.get("liquidation_value", {})
            .get("fields", {})
            .get("value", "0")
        )
        safe_collateral_usd_raw = int(
            position_data.get("safe_collateral_usd", {})
            .get("fields", {})
            .get("value", "0")
        )

        # Convert to actual USD values
        total_collateral_usd = total_collateral_usd_raw / USD_PRECISION
        total_loan_usd = total_loan_usd_raw / USD_PRECISION
        liquidation_value = liquidation_value_raw / USD_PRECISION
        safe_collateral_usd = safe_collateral_usd_raw / USD_PRECISION

        # Calculate LTV and health factor
        ltv = (total_loan_usd / total_collateral_usd * 100) if total_collateral_usd > 0 else 0
        health_factor = (liquidation_value / total_loan_usd) if total_loan_usd > 0 else float('inf')

        # Get position health status
        is_healthy = position_data.get("is_position_healthy", True)
        is_liquidatable = position_data.get("is_position_liquidatable", False)

        # Parse collaterals and loans
        collaterals = position_data.get("collaterals", {}).get("fields", {}).get("contents", [])
        loans = position_data.get("loans", [])

        # Build collateral summary
        collateral_summary = []
        for c in collaterals:
            market_id = int(c.get("fields", {}).get("key", 0))
            market_info = await self.get_market_info(market_id)
            coin_type = market_info.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
            token_symbol = coin_type.split("::")[-1] if "::" in coin_type else coin_type
            collateral_summary.append(f"{token_symbol} (market {market_id})")

        # Build loan summary
        loan_summary = []
        for loan in loans:
            loan_fields = loan.get("fields", {})
            coin_type = loan_fields.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
            token_symbol = coin_type.split("::")[-1] if "::" in coin_type else coin_type
            loan_summary.append(f"{token_symbol}")

        # Calculate liquidation threshold
        liquidation_threshold = (
            (liquidation_value / total_collateral_usd * 100)
            if total_collateral_usd > 0
            else 0
        )

        # Print detailed position info
        print(f"\n{'='*60}")
        print(f"POSITION SUMMARY")
        print(f"{'='*60}")
        print(f"  Position ID: {position_id}")
        print(f"  Collateral Assets: {', '.join(collateral_summary) if collateral_summary else 'N/A'}")
        print(f"  Borrowed Assets: {', '.join(loan_summary) if loan_summary else 'N/A'}")
        print(f"  ")
        print(f"  Total Collateral:     ${total_collateral_usd:,.2f}")
        print(f"  Safe Collateral:      ${safe_collateral_usd:,.2f}")
        print(f"  Liquidation Value:    ${liquidation_value:,.2f}")
        print(f"  Total Borrowed:       ${total_loan_usd:,.2f}")
        print(f"  ")
        print(f"  LTV:                  {ltv:.2f}%")
        print(f"  Health Factor:        {health_factor:.4f}")
        print(f"  Liquidation Threshold: {liquidation_threshold:.2f}%")
        print(f"  ")
        print(f"  Position Healthy:     {'Yes' if is_healthy else 'NO!'}")
        print(f"  Liquidatable:         {'YES - DANGER!' if is_liquidatable else 'No'}")
        print(f"{'='*60}")

        return PositionData(
            collateral_value=total_collateral_usd,
            borrowed_value=total_loan_usd,
            ltv=ltv,
            health_factor=health_factor,
            liquidation_threshold=liquidation_threshold,
            asset=", ".join(collateral_summary) if collateral_summary else "N/A",
            borrowed_asset=", ".join(loan_summary) if loan_summary else "N/A"
        )
