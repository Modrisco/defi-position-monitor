#!/usr/bin/env python3
"""
Bluefin AlphaLend Position Monitor
Monitors your lending positions on SUI chain and sends alerts for LTV/health factor changes
"""

import asyncio
import json
import os
import ssl
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import certifi
from dataclasses import dataclass
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class PositionData:
    """Data class for lending position"""
    collateral_value: float
    borrowed_value: float
    ltv: float
    health_factor: float
    liquidation_threshold: float
    asset: str
    borrowed_asset: str


class BluefinMonitor:
    """Monitor Bluefin AlphaLend positions"""

    # AlphaLend contract addresses on SUI mainnet
    LENDING_PROTOCOL_ID = "0x01d9cf05d65fa3a9bb7163095139120e3c4e414dfbab153a49779a7d14010b93"
    ALPHALEND_PACKAGE_ID = "0xd631cd66138909636fc3f73ed75820d0c5b76332d1644608ed1c85ea2b8219b4"
    POSITIONS_TABLE_ID = "0x9923cec7b613e58cc3feec1e8651096ad7970c0b4ef28b805c7d97fe58ff91ba"
    MARKETS_TABLE_ID = "0x2326d387ba8bb7d24aa4cfa31f9a1e58bf9234b097574afb06c5dfb267df4c2e"

    # Precision for USD values (18 decimals)
    USD_PRECISION = 10 ** 18

    # SUI RPC endpoints (you can use any provider)
    SUI_RPC_ENDPOINTS = [
        "https://fullnode.mainnet.sui.io:443",
        "https://sui-mainnet.nodeinfra.com",
        "https://sui-mainnet-endpoint.blockvision.org",
    ]
    
    def __init__(self, wallet_address: str, alert_email: Optional[str] = None, 
                 ltv_warning_threshold: float = 70.0, ltv_critical_threshold: float = 80.0):
        """
        Initialize the monitor
        
        Args:
            wallet_address: Your SUI wallet address
            alert_email: Email to send alerts to (optional)
            ltv_warning_threshold: LTV % to trigger warning
            ltv_critical_threshold: LTV % to trigger critical alert
        """
        self.wallet_address = wallet_address
        self.alert_email = alert_email
        self.ltv_warning_threshold = ltv_warning_threshold
        self.ltv_critical_threshold = ltv_critical_threshold
        self.rpc_url = self.SUI_RPC_ENDPOINTS[0]
        
    async def _rpc_call(self, method: str, params: List) -> Dict:
        """Make RPC call to SUI node"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        # Create SSL context using certifi's certificate bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(self.rpc_url, json=payload) as response:
                result = await response.json()
                if "error" in result:
                    raise Exception(f"RPC Error: {result['error']}")
                return result.get("result", {})
    
    async def get_owned_objects(self) -> List[Dict]:
        """Get all objects owned by the wallet"""
        all_objects = []
        cursor = None

        try:
            while True:
                result = await self._rpc_call(
                    "suix_getOwnedObjects",
                    [
                        self.wallet_address,
                        {
                            "filter": None,
                            "options": {
                                "showType": True,
                                "showContent": True,
                                "showOwner": True
                            }
                        },
                        cursor,
                        50  # limit per page
                    ]
                )

                data = result.get("data", [])
                all_objects.extend(data)

                # Check for more pages
                cursor = result.get("nextCursor")
                has_next = result.get("hasNextPage", False)

                if not has_next or not cursor:
                    break

            return all_objects
        except Exception as e:
            print(f"Error fetching owned objects: {e}")
            return []
    
    async def get_position_capabilities(self) -> List[str]:
        """Find position capability objects for AlphaLend"""
        objects = await self.get_owned_objects()
        position_caps = []

        for obj in objects:
            obj_type = obj.get("data", {}).get("type", "")
            object_id = obj.get("data", {}).get("objectId", "")

            # Look for AlphaLend position capability objects
            # Check for "positioncap" (no underscore) or the package ID
            type_lower = obj_type.lower()
            if "positioncap" in type_lower or "position_cap" in type_lower or self.ALPHALEND_PACKAGE_ID in obj_type:
                if object_id:
                    position_caps.append(object_id)

        return position_caps
    
    async def get_object_details(self, object_id: str) -> Dict:
        """Get detailed information about an object"""
        try:
            result = await self._rpc_call(
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
            return result
        except Exception as e:
            print(f"Error fetching object {object_id}: {e}")
            return {}
    
    async def get_dynamic_fields(self, object_id: str) -> List[Dict]:
        """Get dynamic fields of an object (useful for protocol state)"""
        try:
            result = await self._rpc_call(
                "suix_getDynamicFields",
                [object_id, None, None]
            )
            return result.get("data", [])
        except Exception as e:
            print(f"Error fetching dynamic fields: {e}")
            return []

    async def get_dynamic_field_object(self, parent_id: str, key_type: str, key_value: str) -> Dict:
        """Get a specific dynamic field object"""
        try:
            result = await self._rpc_call(
                "suix_getDynamicFieldObject",
                [parent_id, {"type": key_type, "value": key_value}]
            )
            return result.get("data", {})
        except Exception as e:
            print(f"Error fetching dynamic field object: {e}")
            return {}

    async def get_position_data(self, position_id: str) -> Dict:
        """Fetch position data from the protocol's positions table"""
        try:
            result = await self.get_dynamic_field_object(
                self.POSITIONS_TABLE_ID,
                "0x2::object::ID",
                position_id
            )

            if not result:
                print(f"No position data found for {position_id}")
                return {}

            # Extract the position value from the dynamic field
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
            result = await self.get_dynamic_field_object(
                self.MARKETS_TABLE_ID,
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
    
    async def calculate_position_metrics(self, collateral_amount: float, 
                                        borrowed_amount: float,
                                        collateral_price: float,
                                        borrow_price: float,
                                        liquidation_threshold: float = 85.0) -> PositionData:
        """
        Calculate position metrics
        
        Args:
            collateral_amount: Amount of collateral
            borrowed_amount: Amount borrowed
            collateral_price: Price of collateral asset
            borrow_price: Price of borrowed asset
            liquidation_threshold: Liquidation LTV threshold (default 85%)
        """
        collateral_value = collateral_amount * collateral_price
        borrowed_value = borrowed_amount * borrow_price
        
        if collateral_value == 0:
            ltv = 0
            health_factor = float('inf')
        else:
            ltv = (borrowed_value / collateral_value) * 100
            # Health factor = (collateral * liquidation_threshold) / borrowed
            health_factor = (collateral_value * (liquidation_threshold / 100)) / borrowed_value if borrowed_value > 0 else float('inf')
        
        return PositionData(
            collateral_value=collateral_value,
            borrowed_value=borrowed_value,
            ltv=ltv,
            health_factor=health_factor,
            liquidation_threshold=liquidation_threshold,
            asset="",
            borrowed_asset=""
        )
    
    # Pyth Network price feed IDs (mainnet)
    PYTH_PRICE_FEEDS = {
        "SUI": "23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744",
        "BTC": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
        "XBTC": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",  # XBTC uses BTC price
        "USDC": "eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a",
        "USDT": "2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b",
        "ETH": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    }
    PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"

    async def fetch_prices_from_pyth(self) -> Dict[str, float]:
        """
        Fetch current prices from Pyth Network oracle
        """
        prices = {}

        # Build query with all price feed IDs
        feed_ids = list(set(self.PYTH_PRICE_FEEDS.values()))  # unique IDs
        query_params = "&".join([f"ids[]={fid}" for fid in feed_ids])
        url = f"{self.PYTH_HERMES_URL}?{query_params}"

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"Error fetching prices from Pyth: HTTP {response.status}")
                        return prices

                    data = await response.json()
                    parsed = data.get("parsed", [])

                    # Create reverse mapping from feed ID to asset names
                    id_to_assets = {}
                    for asset, feed_id in self.PYTH_PRICE_FEEDS.items():
                        if feed_id not in id_to_assets:
                            id_to_assets[feed_id] = []
                        id_to_assets[feed_id].append(asset)

                    # Extract prices
                    for item in parsed:
                        feed_id = item.get("id")
                        price_data = item.get("price", {})
                        price_raw = int(price_data.get("price", 0))
                        expo = int(price_data.get("expo", 0))

                        # Calculate actual price
                        price = price_raw * (10 ** expo)

                        # Map to all assets using this feed
                        if feed_id in id_to_assets:
                            for asset in id_to_assets[feed_id]:
                                prices[asset] = price

                    print(f"\n--- Fetched prices from Pyth Network ---")
                    for asset, price in sorted(prices.items()):
                        print(f"  {asset}: ${price:,.4f}")

        except Exception as e:
            print(f"Error fetching prices from Pyth: {e}")

        return prices
    
    async def check_positions(self) -> List[PositionData]:
        """Check all lending positions"""
        print(f"Checking positions for wallet: {self.wallet_address}")

        # Get position capabilities
        position_caps = await self.get_position_capabilities()
        print(f"Found {len(position_caps)} position capabilities")

        # Get current prices
        prices = await self.fetch_prices_from_pyth()

        positions = []

        for cap_id in position_caps:
            # Get PositionCap details to extract position_id
            details = await self.get_object_details(cap_id)
            cap_content = details.get("data", {}).get("content", {}).get("fields", {})
            position_id = cap_content.get("position_id")

            if not position_id:
                print(f"  No position_id found in PositionCap {cap_id}")
                continue

            print(f"\n--- Fetching position data for {position_id} ---")

            # Fetch the actual position data from the positions table
            position_data = await self.get_position_data(position_id)

            if not position_data:
                print(f"  Could not fetch position data")
                continue

            # Extract USD values (stored with 18 decimal precision)
            total_collateral_usd_raw = int(position_data.get("total_collateral_usd", {}).get("fields", {}).get("value", "0"))
            total_loan_usd_raw = int(position_data.get("total_loan_usd", {}).get("fields", {}).get("value", "0"))
            liquidation_value_raw = int(position_data.get("liquidation_value", {}).get("fields", {}).get("value", "0"))
            safe_collateral_usd_raw = int(position_data.get("safe_collateral_usd", {}).get("fields", {}).get("value", "0"))

            # Convert to actual USD values
            total_collateral_usd = total_collateral_usd_raw / self.USD_PRECISION
            total_loan_usd = total_loan_usd_raw / self.USD_PRECISION
            liquidation_value = liquidation_value_raw / self.USD_PRECISION
            safe_collateral_usd = safe_collateral_usd_raw / self.USD_PRECISION

            # Calculate LTV and health factor
            ltv = (total_loan_usd / total_collateral_usd * 100) if total_collateral_usd > 0 else 0
            health_factor = (liquidation_value / total_loan_usd) if total_loan_usd > 0 else float('inf')

            # Get position health status from on-chain data
            is_healthy = position_data.get("is_position_healthy", True)
            is_liquidatable = position_data.get("is_position_liquidatable", False)

            # Parse collaterals and loans for display
            collaterals = position_data.get("collaterals", {}).get("fields", {}).get("contents", [])
            loans = position_data.get("loans", [])

            # Build collateral summary
            collateral_summary = []
            for c in collaterals:
                market_id = int(c.get("fields", {}).get("key", 0))
                amount = int(c.get("fields", {}).get("value", 0))
                market_info = await self.get_market_info(market_id)
                coin_type = market_info.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
                # Extract token symbol from coin type
                token_symbol = coin_type.split("::")[-1] if "::" in coin_type else coin_type
                collateral_summary.append(f"{token_symbol} (market {market_id})")

            # Build loan summary
            loan_summary = []
            for loan in loans:
                loan_fields = loan.get("fields", {})
                coin_type = loan_fields.get("coin_type", {}).get("fields", {}).get("name", "Unknown")
                token_symbol = coin_type.split("::")[-1] if "::" in coin_type else coin_type
                amount = int(loan_fields.get("amount", 0))
                loan_summary.append(f"{token_symbol}")

            # Calculate liquidation threshold from health factor
            # health_factor = liquidation_value / loan_usd
            # liquidation_threshold = (liquidation_value / collateral_usd) * 100
            liquidation_threshold = (liquidation_value / total_collateral_usd * 100) if total_collateral_usd > 0 else 0

            position = PositionData(
                collateral_value=total_collateral_usd,
                borrowed_value=total_loan_usd,
                ltv=ltv,
                health_factor=health_factor,
                liquidation_threshold=liquidation_threshold,
                asset=", ".join(collateral_summary) if collateral_summary else "N/A",
                borrowed_asset=", ".join(loan_summary) if loan_summary else "N/A"
            )
            positions.append(position)

            # Print detailed position info
            print(f"\n{'='*60}")
            print(f"POSITION SUMMARY")
            print(f"{'='*60}")
            print(f"  Position ID: {position_id}")
            print(f"  Collateral Assets: {position.asset}")
            print(f"  Borrowed Assets: {position.borrowed_asset}")
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

        return positions
    
    async def send_email_alert(self, subject: str, body: str):
        """Send email alert"""
        if not self.alert_email:
            print("No alert email configured, skipping email")
            return
        
        # Configure with your email settings
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        
        if not sender_email or not sender_password:
            print("Email credentials not configured")
            return
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = self.alert_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            print(f"Alert email sent to {self.alert_email}")
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    async def send_telegram_alert(self, message: str):
        """Send Telegram alert"""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not bot_token or not chat_id:
            print("Telegram credentials not configured")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    print("Telegram alert sent")
                else:
                    print(f"Failed to send Telegram alert: {response.status}")
    
    async def check_and_alert(self):
        """Check positions and send alerts if needed"""
        positions = await self.check_positions()
        
        for position in positions:
            print(f"\nPosition Status:")
            print(f"  Collateral Value: ${position.collateral_value:.2f}")
            print(f"  Borrowed Value: ${position.borrowed_value:.2f}")
            print(f"  LTV: {position.ltv:.2f}%")
            print(f"  Health Factor: {position.health_factor:.2f}")
            print(f"  Liquidation Threshold: {position.liquidation_threshold:.2f}%")
            
            # Check for alerts
            if position.ltv >= self.ltv_critical_threshold:
                alert_msg = f"""
🚨 CRITICAL ALERT: High LTV Ratio!

Your Bluefin AlphaLend position has reached a critical LTV level:
- Current LTV: {position.ltv:.2f}%
- Health Factor: {position.health_factor:.2f}
- Liquidation Threshold: {position.liquidation_threshold:.2f}%

⚠️ ACTION REQUIRED: Add more collateral or repay debt immediately to avoid liquidation!

Wallet: {self.wallet_address}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                await self.send_email_alert("🚨 CRITICAL: Liquidation Risk!", alert_msg)
                await self.send_telegram_alert(alert_msg)
                
            elif position.ltv >= self.ltv_warning_threshold:
                alert_msg = f"""
⚠️ WARNING: Elevated LTV Ratio

Your Bluefin AlphaLend position LTV is getting high:
- Current LTV: {position.ltv:.2f}%
- Health Factor: {position.health_factor:.2f}
- Liquidation Threshold: {position.liquidation_threshold:.2f}%

Consider adding collateral or reducing your borrowed amount.

Wallet: {self.wallet_address}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                await self.send_email_alert("⚠️ WARNING: High LTV", alert_msg)
                await self.send_telegram_alert(alert_msg)
    
    async def generate_daily_report(self):
        """Generate daily position report"""
        positions = await self.check_positions()
        
        report = f"""
📊 Daily Bluefin AlphaLend Report
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Wallet: {self.wallet_address}

{'='*50}
"""
        
        if not positions:
            report += "\nNo active positions found.\n"
        else:
            for i, position in enumerate(positions, 1):
                status = "✅ Safe"
                if position.ltv >= self.ltv_critical_threshold:
                    status = "🚨 CRITICAL"
                elif position.ltv >= self.ltv_warning_threshold:
                    status = "⚠️ WARNING"
                
                report += f"""
Position {i}: {status}
  Collateral: ${position.collateral_value:.2f}
  Borrowed: ${position.borrowed_value:.2f}
  LTV: {position.ltv:.2f}%
  Health Factor: {position.health_factor:.2f}
  Liquidation Threshold: {position.liquidation_threshold:.2f}%
"""
        
        report += "\n" + "="*50
        
        await self.send_email_alert("📊 Daily Bluefin Position Report", report)
        print(report)
        
        # Save to file
        with open(f"report_{datetime.now().strftime('%Y%m%d')}.txt", "w") as f:
            f.write(report)
    
    async def run_continuous_monitoring(self, check_interval_minutes: int = 15):
        """Run continuous monitoring loop"""
        print(f"Starting continuous monitoring (checking every {check_interval_minutes} minutes)")
        
        while True:
            try:
                await self.check_and_alert()
                await asyncio.sleep(check_interval_minutes * 60)
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


async def main():
    """Main function"""
    # Configuration
    WALLET_ADDRESS = os.getenv("SUI_WALLET_ADDRESS", "YOUR_WALLET_ADDRESS_HERE")
    ALERT_EMAIL = os.getenv("ALERT_EMAIL", "your-email@example.com")
    
    # Create monitor instance
    monitor = BluefinMonitor(
        wallet_address=WALLET_ADDRESS,
        alert_email=ALERT_EMAIL,
        ltv_warning_threshold=70.0,  # Warning at 70% LTV
        ltv_critical_threshold=80.0   # Critical at 80% LTV
    )
    
    # Choose operation mode
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            # One-time check
            await monitor.check_and_alert()
        elif sys.argv[1] == "report":
            # Generate daily report
            await monitor.generate_daily_report()
        elif sys.argv[1] == "monitor":
            # Continuous monitoring
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 15
            await monitor.run_continuous_monitoring(interval)
    else:
        print("Usage:")
        print("  python bluefin_monitor.py check          - One-time position check")
        print("  python bluefin_monitor.py report         - Generate daily report")
        print("  python bluefin_monitor.py monitor [mins] - Continuous monitoring")


if __name__ == "__main__":
    asyncio.run(main())
