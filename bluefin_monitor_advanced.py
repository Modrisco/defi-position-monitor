#!/usr/bin/env python3
"""
Enhanced Bluefin AlphaLend Position Monitor with Price Oracle Integration
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiohttp
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class PriceInfo:
    """Price information from oracle"""
    symbol: str
    price: float
    timestamp: int


@dataclass
class Position:
    """Lending position details"""
    collateral_asset: str
    collateral_amount: float
    collateral_value: float
    borrowed_asset: str
    borrowed_amount: float
    borrowed_value: float
    ltv: float
    health_factor: float
    liquidation_ltv: float


class PriceOracle:
    """Fetch prices from multiple sources"""
    
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    
    # CoinGecko IDs for common assets
    COIN_IDS = {
        "SUI": "sui",
        "USDC": "usd-coin",
        "USDT": "tether",
        "ETH": "ethereum",
        "BTC": "bitcoin",
        "WETH": "weth",
    }
    
    async def fetch_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch current prices from CoinGecko"""
        coin_ids = [self.COIN_IDS.get(symbol.upper()) for symbol in symbols if symbol.upper() in self.COIN_IDS]
        
        if not coin_ids:
            return {}
        
        url = f"{self.COINGECKO_API}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": "usd"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Convert back to symbol: price format
                        prices = {}
                        for symbol in symbols:
                            coin_id = self.COIN_IDS.get(symbol.upper())
                            if coin_id and coin_id in data:
                                prices[symbol.upper()] = data[coin_id]["usd"]
                        return prices
        except Exception as e:
            print(f"Error fetching prices: {e}")
        
        return {}


class SuiRPCClient:
    """Enhanced SUI RPC client"""
    
    def __init__(self, rpc_url: str = "https://fullnode.mainnet.sui.io:443"):
        self.rpc_url = rpc_url
    
    async def call(self, method: str, params: List) -> Dict:
        """Make RPC call"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    result = await response.json()
                    if "error" in result:
                        raise Exception(f"RPC Error: {result['error']}")
                    return result.get("result", {})
            except asyncio.TimeoutError:
                raise Exception("RPC request timed out")
    
    async def get_objects_owned_by_address(self, address: str) -> List[Dict]:
        """Get all objects owned by address"""
        return await self.call(
            "suix_getOwnedObjects",
            [
                address,
                {
                    "filter": None,
                    "options": {
                        "showType": True,
                        "showContent": True,
                        "showOwner": True,
                        "showDisplay": False,
                    }
                },
                None,
                None
            ]
        )
    
    async def get_object(self, object_id: str) -> Dict:
        """Get object details"""
        return await self.call(
            "sui_getObject",
            [
                object_id,
                {
                    "showType": True,
                    "showContent": True,
                    "showOwner": True
                }
            ]
        )
    
    async def get_dynamic_fields(self, parent_id: str) -> List[Dict]:
        """Get dynamic fields"""
        return await self.call(
            "suix_getDynamicFields",
            [parent_id, None, None]
        )
    
    async def query_events(self, query: Dict) -> List[Dict]:
        """Query events"""
        return await self.call(
            "suix_queryEvents",
            [query, None, None, False]
        )


class BluefinPositionMonitor:
    """Enhanced Bluefin position monitoring"""
    
    # AlphaLend contract addresses
    ALPHALEND_PACKAGE_ID = "0xee754fc0c6d977403c9218cedbfffed033b4b42b50a65c2c3f1c7be13efeafd2"
    LENDING_PROTOCOL_ID = "0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93"
    
    # Default liquidation LTV for different assets (%)
    LIQUIDATION_LTVS = {
        "SUI": 85.0,
        "ETH": 82.5,
        "USDC": 90.0,
        "USDT": 90.0,
    }
    
    def __init__(self, wallet_address: str, rpc_url: str = None):
        self.wallet_address = wallet_address
        self.rpc = SuiRPCClient(rpc_url or "https://fullnode.mainnet.sui.io:443")
        self.price_oracle = PriceOracle()
        self.ltv_warning = float(os.getenv("LTV_WARNING_THRESHOLD", "70"))
        self.ltv_critical = float(os.getenv("LTV_CRITICAL_THRESHOLD", "80"))
    
    async def get_positions(self) -> List[Position]:
        """
        Fetch all lending positions
        This is a simplified version - you'll need to adapt based on actual contract structure
        """
        positions = []
        
        try:
            # Get objects owned by wallet
            owned_objects = await self.rpc.get_objects_owned_by_address(self.wallet_address)
            
            # Filter for AlphaLend position objects
            position_objects = []
            for obj in owned_objects.get("data", []):
                obj_type = obj.get("data", {}).get("type", "")
                if self.ALPHALEND_PACKAGE_ID in obj_type and "position" in obj_type.lower():
                    position_objects.append(obj)
            
            # Get current prices for all assets
            all_assets = set()
            for obj in position_objects:
                # Extract asset types from object type string
                # This will need to be adapted to actual type structure
                content = obj.get("data", {}).get("content", {})
                if content:
                    all_assets.update(["SUI", "USDC", "ETH", "USDT"])  # Common assets
            
            prices = await self.price_oracle.fetch_prices(list(all_assets))
            
            # Parse each position
            for pos_obj in position_objects:
                position = await self._parse_position_object(pos_obj, prices)
                if position:
                    positions.append(position)
        
        except Exception as e:
            print(f"Error fetching positions: {e}")
        
        return positions
    
    async def _parse_position_object(self, obj: Dict, prices: Dict[str, float]) -> Optional[Position]:
        """
        Parse position from object
        NOTE: This is a template - actual implementation depends on contract structure
        """
        try:
            content = obj.get("data", {}).get("content", {}).get("fields", {})
            
            # Example parsing (adjust based on actual structure)
            # You'll need to inspect actual objects to determine the correct field names
            collateral_asset = "SUI"  # Extract from type or content
            borrowed_asset = "USDC"   # Extract from type or content
            
            # Get amounts (these field names are examples)
            collateral_amount = float(content.get("collateral", 0)) / 1e9  # Adjust decimals
            borrowed_amount = float(content.get("borrowed", 0)) / 1e6     # Adjust decimals
            
            # Calculate values
            collateral_price = prices.get(collateral_asset, 0)
            borrowed_price = prices.get(borrowed_asset, 1)
            
            collateral_value = collateral_amount * collateral_price
            borrowed_value = borrowed_amount * borrowed_price
            
            # Calculate LTV and health factor
            ltv = (borrowed_value / collateral_value * 100) if collateral_value > 0 else 0
            liquidation_ltv = self.LIQUIDATION_LTVS.get(collateral_asset, 85.0)
            health_factor = (collateral_value * liquidation_ltv / 100) / borrowed_value if borrowed_value > 0 else float('inf')
            
            return Position(
                collateral_asset=collateral_asset,
                collateral_amount=collateral_amount,
                collateral_value=collateral_value,
                borrowed_asset=borrowed_asset,
                borrowed_amount=borrowed_amount,
                borrowed_value=borrowed_value,
                ltv=ltv,
                health_factor=health_factor,
                liquidation_ltv=liquidation_ltv
            )
        
        except Exception as e:
            print(f"Error parsing position: {e}")
            return None
    
    async def check_positions_and_alert(self) -> List[Tuple[Position, str]]:
        """Check positions and return alerts"""
        positions = await self.get_positions()
        alerts = []
        
        for position in positions:
            alert_level = None
            
            if position.ltv >= self.ltv_critical:
                alert_level = "CRITICAL"
            elif position.ltv >= self.ltv_warning:
                alert_level = "WARNING"
            
            if alert_level:
                alerts.append((position, alert_level))
        
        return alerts
    
    def format_position_report(self, position: Position) -> str:
        """Format position as readable text"""
        status = "✅ Healthy"
        if position.ltv >= self.ltv_critical:
            status = "🚨 CRITICAL"
        elif position.ltv >= self.ltv_warning:
            status = "⚠️ WARNING"
        
        return f"""
{status}
Collateral: {position.collateral_amount:.4f} {position.collateral_asset} (${position.collateral_value:.2f})
Borrowed: {position.borrowed_amount:.4f} {position.borrowed_asset} (${position.borrowed_value:.2f})
LTV: {position.ltv:.2f}% (Liquidation at {position.liquidation_ltv:.2f}%)
Health Factor: {position.health_factor:.3f}
"""


async def send_notification(message: str, method: str = "print"):
    """Send notification via specified method"""
    if method == "print":
        print(message)
    elif method == "email":
        # Implement email sending
        pass
    elif method == "telegram":
        # Implement Telegram sending
        pass


async def main():
    """Main monitoring function"""
    wallet = os.getenv("SUI_WALLET_ADDRESS")
    
    if not wallet:
        print("Error: SUI_WALLET_ADDRESS not set in .env file")
        return
    
    monitor = BluefinPositionMonitor(wallet)
    
    print(f"Monitoring wallet: {wallet}")
    print(f"Warning threshold: {monitor.ltv_warning}%")
    print(f"Critical threshold: {monitor.ltv_critical}%")
    print("-" * 60)
    
    # Check positions
    positions = await monitor.get_positions()
    
    if not positions:
        print("No active positions found")
        return
    
    print(f"\nFound {len(positions)} position(s):\n")
    
    for i, position in enumerate(positions, 1):
        print(f"Position {i}:")
        print(monitor.format_position_report(position))
    
    # Check for alerts
    alerts = await monitor.check_positions_and_alert()
    
    if alerts:
        print("\n" + "="*60)
        print("⚠️ ALERTS TRIGGERED ⚠️")
        print("="*60)
        
        for position, level in alerts:
            print(f"\n{level} - LTV: {position.ltv:.2f}%")
            print(f"Position: {position.collateral_asset} → {position.borrowed_asset}")
            print(f"Action: {'ADD COLLATERAL NOW!' if level == 'CRITICAL' else 'Monitor closely'}")


if __name__ == "__main__":
    asyncio.run(main())
