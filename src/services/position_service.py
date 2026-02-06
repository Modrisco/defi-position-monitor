"""AlphaLend position fetching service"""
from typing import Dict, List

from ..config import (
    ALPHALEND_PACKAGE_ID,
    POSITIONS_TABLE_ID,
    MARKETS_TABLE_ID,
    TOKEN_DECIMALS,
)
from ..models import PositionData
from ..rpc import SuiClient


class PositionService:
    """Fetch and parse AlphaLend positions"""

    def __init__(self, sui_client: SuiClient):
        self.sui_client = sui_client
        # Cache market info to avoid repeated fetches
        self._market_cache: Dict[int, Dict] = {}

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
        """Fetch market info to get coin type (with caching)"""
        if market_id in self._market_cache:
            return self._market_cache[market_id]

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

            self._market_cache[market_id] = market
            return market
        except Exception as e:
            print(f"Error fetching market {market_id}: {e}")
            return {}

    def _get_token_symbol(self, coin_type: str) -> str:
        """Extract token symbol from coin type string"""
        if "::" in coin_type:
            return coin_type.split("::")[-1].upper()
        return coin_type.upper()

    def _get_decimals(self, token_symbol: str) -> int:
        """Get token decimals from config"""
        return TOKEN_DECIMALS.get(token_symbol, 9)  # Default to 9 (SUI standard)

    async def fetch_positions(
        self, wallet_address: str, prices: Dict[str, float]
    ) -> List[PositionData]:
        """Fetch all lending positions for a wallet with real-time price calculation"""
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

            position = await self._parse_position_data(position_data, position_id, prices)
            if position:
                positions.append(position)

        return positions

    async def _parse_position_data(
        self, position_data: Dict, position_id: str, prices: Dict[str, float]
    ) -> PositionData:
        """Parse raw position data into PositionData object with real-time prices"""

        # Parse collaterals with real-time price calculation
        # Note: collaterals are stored as shares (xtokens), need to multiply by xtoken_ratio
        collaterals = position_data.get("collaterals", {}).get("fields", {}).get("contents", [])
        collateral_details = []
        total_collateral_usd = 0.0

        for c in collaterals:
            market_id = int(c.get("fields", {}).get("key", 0))
            shares = int(c.get("fields", {}).get("value", 0))

            market_info = await self.get_market_info(market_id)
            coin_type = market_info.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
            token_symbol = self._get_token_symbol(coin_type)
            decimals = self._get_decimals(token_symbol)

            # Get xtoken_ratio to convert shares to actual tokens
            xtoken_ratio_raw = market_info.get("xtoken_ratio", 10**18)
            if isinstance(xtoken_ratio_raw, dict):
                xtoken_ratio = int(xtoken_ratio_raw.get("fields", {}).get("value", 10**18))
            else:
                xtoken_ratio = int(xtoken_ratio_raw)

            # Actual amount = shares × xtoken_ratio / 10^18 / 10^decimals
            amount = (shares * xtoken_ratio) / (10**18) / (10**decimals)

            # Get price (try exact match, then common aliases)
            price = prices.get(token_symbol, 0)
            if price == 0 and token_symbol == "XBTC":
                price = prices.get("BTC", 0)

            usd_value = amount * price
            total_collateral_usd += usd_value

            collateral_details.append({
                "symbol": token_symbol,
                "market_id": market_id,
                "amount": amount,
                "price": price,
                "usd_value": usd_value
            })

        # Parse loans with real-time price calculation
        # Note: loan amount is the actual borrowed amount (not shares)
        loans = position_data.get("loans", [])
        loan_details = []
        total_loan_usd = 0.0

        for loan in loans:
            loan_fields = loan.get("fields", {})
            raw_amount = int(loan_fields.get("amount", 0))

            coin_type = loan_fields.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
            token_symbol = self._get_token_symbol(coin_type)
            decimals = self._get_decimals(token_symbol)

            # Convert raw amount to actual amount
            amount = raw_amount / (10**decimals)

            # Get price
            price = prices.get(token_symbol, 0)

            usd_value = amount * price
            total_loan_usd += usd_value

            loan_details.append({
                "symbol": token_symbol,
                "amount": amount,
                "price": price,
                "usd_value": usd_value
            })

        # Calculate LTV and health factor
        ltv = (total_loan_usd / total_collateral_usd * 100) if total_collateral_usd > 0 else 0

        # For liquidation threshold, use the on-chain value as reference
        # Typically around 85-90% for most assets
        liquidation_threshold = 85.0  # Default, could be made per-asset

        # Health factor = (collateral * liquidation_threshold) / borrowed
        health_factor = (
            (total_collateral_usd * liquidation_threshold / 100) / total_loan_usd
            if total_loan_usd > 0
            else float('inf')
        )

        # Get position health status from on-chain data
        is_healthy = position_data.get("is_position_healthy", True)
        is_liquidatable = position_data.get("is_position_liquidatable", False)

        # Build summaries for display
        collateral_summary = [
            f"{d['symbol']} ({d['amount']:.4f} @ ${d['price']:,.2f})"
            for d in collateral_details
        ]
        loan_summary = [
            f"{d['symbol']} ({d['amount']:.4f} @ ${d['price']:,.2f})"
            for d in loan_details
        ]

        # Print detailed position info
        print(f"\n{'='*60}")
        print(f"POSITION SUMMARY (Real-time prices)")
        print(f"{'='*60}")
        print(f"  Position ID: {position_id}")
        print(f"  ")
        print(f"  Collateral Assets:")
        for d in collateral_details:
            print(f"    - {d['symbol']}: {d['amount']:.6f} × ${d['price']:,.2f} = ${d['usd_value']:,.2f}")
        print(f"  Total Collateral:     ${total_collateral_usd:,.2f}")
        print(f"  ")
        print(f"  Borrowed Assets:")
        for d in loan_details:
            print(f"    - {d['symbol']}: {d['amount']:.6f} × ${d['price']:,.2f} = ${d['usd_value']:,.2f}")
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
