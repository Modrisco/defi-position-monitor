"""Pyth Network price oracle service."""
import logging
import ssl

import aiohttp
import certifi

from ..config import PythConfig

logger = logging.getLogger(__name__)


class PythOracle:
    """Fetch prices from Pyth Network oracle."""

    def __init__(self, config: PythConfig) -> None:
        self.hermes_url = config.hermes_url
        self.price_feeds = dict(config.feeds)

    async def fetch_prices(self, symbols: list[str] | None = None) -> dict[str, float]:
        """Fetch current prices from Pyth Network.

        Args:
            symbols: Optional list of symbols to fetch. If None, fetches all
                     configured feeds.
        """
        prices: dict[str, float] = {}

        feeds = self.price_feeds
        if symbols is not None:
            feeds = {k: v for k, v in self.price_feeds.items() if k in symbols}

        feed_ids = list(set(feeds.values()))
        if not feed_ids:
            return prices

        query_params = "&".join([f"ids[]={fid}" for fid in feed_ids])
        url = f"{self.hermes_url}?{query_params}"

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(
                            "Error fetching prices from Pyth: HTTP %s", response.status
                        )
                        return prices

                    data = await response.json()
                    parsed = data.get("parsed", [])

                    # Create reverse mapping from feed ID to asset names
                    id_to_assets: dict[str, list[str]] = {}
                    for asset, feed_id in feeds.items():
                        if feed_id not in id_to_assets:
                            id_to_assets[feed_id] = []
                        id_to_assets[feed_id].append(asset)

                    for item in parsed:
                        feed_id = item.get("id")
                        price_data = item.get("price", {})
                        price_raw = int(price_data.get("price", 0))
                        expo = int(price_data.get("expo", 0))

                        price = price_raw * (10**expo)

                        if feed_id in id_to_assets:
                            for asset in id_to_assets[feed_id]:
                                prices[asset] = price

                    logger.info("Fetched prices from Pyth Network:")
                    for asset, price in sorted(prices.items()):
                        logger.info("  %s: $%.4f", asset, price)

        except Exception as e:
            logger.error("Error fetching prices from Pyth: %s", e)

        return prices
