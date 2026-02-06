"""Pyth Network price oracle service"""
import ssl
from typing import Dict
import aiohttp
import certifi

from ..config import PYTH_HERMES_URL, PYTH_PRICE_FEEDS


class PriceService:
    """Fetch prices from Pyth Network oracle"""

    def __init__(self):
        self.hermes_url = PYTH_HERMES_URL
        self.price_feeds = PYTH_PRICE_FEEDS

    async def fetch_prices(self) -> Dict[str, float]:
        """Fetch current prices from Pyth Network"""
        prices = {}

        feed_ids = list(set(self.price_feeds.values()))
        query_params = "&".join([f"ids[]={fid}" for fid in feed_ids])
        url = f"{self.hermes_url}?{query_params}"

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
                    for asset, feed_id in self.price_feeds.items():
                        if feed_id not in id_to_assets:
                            id_to_assets[feed_id] = []
                        id_to_assets[feed_id].append(asset)

                    # Extract prices
                    for item in parsed:
                        feed_id = item.get("id")
                        price_data = item.get("price", {})
                        price_raw = int(price_data.get("price", 0))
                        expo = int(price_data.get("expo", 0))

                        price = price_raw * (10 ** expo)

                        if feed_id in id_to_assets:
                            for asset in id_to_assets[feed_id]:
                                prices[asset] = price

                    print(f"\n--- Fetched prices from Pyth Network ---")
                    for asset, price in sorted(prices.items()):
                        print(f"  {asset}: ${price:,.4f}")

        except Exception as e:
            print(f"Error fetching prices from Pyth: {e}")

        return prices
