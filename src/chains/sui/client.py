"""SUI RPC client with fallback support."""
import logging
import ssl
from typing import Any

import aiohttp
import certifi

from ...config import ChainConfig

logger = logging.getLogger(__name__)


class SuiClient:
    """SUI blockchain RPC client with automatic endpoint fallback."""

    def __init__(self, config: ChainConfig) -> None:
        self.endpoints = list(config.rpc_endpoints)
        self.timeout = config.rpc_timeout
        self.current_rpc_index = 0

    async def rpc_call(self, method: str, params: list[Any]) -> dict[str, Any]:
        """Make RPC call with fallback to alternative endpoints."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        last_error: Exception | None = None
        for attempt in range(len(self.endpoints)):
            rpc_index = (self.current_rpc_index + attempt) % len(self.endpoints)
            rpc_url = self.endpoints[rpc_index]

            try:
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        rpc_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        result = await response.json()
                        if "error" in result:
                            raise RuntimeError(f"RPC Error: {result['error']}")

                        if rpc_index != self.current_rpc_index:
                            logger.info("Switched to RPC endpoint: %s", rpc_url)
                            self.current_rpc_index = rpc_index

                        return result.get("result", {})
            except Exception as e:
                last_error = e
                logger.warning("RPC endpoint %s failed: %s", rpc_url, e)
                if attempt < len(self.endpoints) - 1:
                    logger.info("Trying next endpoint...")
                continue

        raise RuntimeError(f"All RPC endpoints failed. Last error: {last_error}")

    async def get_owned_objects(self, wallet_address: str) -> list[dict[str, Any]]:
        """Get all objects owned by the wallet (paginated)."""
        all_objects: list[dict[str, Any]] = []
        cursor = None

        try:
            while True:
                result = await self.rpc_call(
                    "suix_getOwnedObjects",
                    [
                        wallet_address,
                        {
                            "filter": None,
                            "options": {
                                "showType": True,
                                "showContent": True,
                                "showOwner": True,
                            },
                        },
                        cursor,
                        50,
                    ],
                )

                data = result.get("data", [])
                all_objects.extend(data)

                cursor = result.get("nextCursor")
                has_next = result.get("hasNextPage", False)

                if not has_next or not cursor:
                    break

            return all_objects
        except Exception as e:
            logger.error("Error fetching owned objects: %s", e)
            return []

    async def get_object(self, object_id: str) -> dict[str, Any]:
        """Get detailed information about an object."""
        try:
            return await self.rpc_call(
                "sui_getObject",
                [
                    object_id,
                    {"showType": True, "showContent": True, "showOwner": True},
                ],
            )
        except Exception as e:
            logger.error("Error fetching object %s: %s", object_id, e)
            return {}

    async def get_dynamic_fields(self, object_id: str) -> list[dict[str, Any]]:
        """Get dynamic fields of an object."""
        try:
            result = await self.rpc_call(
                "suix_getDynamicFields", [object_id, None, None]
            )
            return result.get("data", [])
        except Exception as e:
            logger.error("Error fetching dynamic fields: %s", e)
            return []

    async def get_dynamic_field_object(
        self, parent_id: str, key_type: str, key_value: str
    ) -> dict[str, Any]:
        """Get a specific dynamic field object."""
        try:
            result = await self.rpc_call(
                "suix_getDynamicFieldObject",
                [parent_id, {"type": key_type, "value": key_value}],
            )
            return result.get("data", {})
        except Exception as e:
            logger.error("Error fetching dynamic field object: %s", e)
            return {}
