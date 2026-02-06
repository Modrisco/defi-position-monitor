"""SUI RPC client with fallback support"""
import ssl
from typing import Dict, List
import aiohttp
import certifi

from ..config import SUI_RPC_ENDPOINTS


class SuiClient:
    """SUI blockchain RPC client with automatic endpoint fallback"""

    def __init__(self):
        self.current_rpc_index = 0
        self.endpoints = SUI_RPC_ENDPOINTS

    async def rpc_call(self, method: str, params: List) -> Dict:
        """Make RPC call to SUI node with fallback to alternative endpoints"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        last_error = None
        for attempt in range(len(self.endpoints)):
            rpc_index = (self.current_rpc_index + attempt) % len(self.endpoints)
            rpc_url = self.endpoints[rpc_index]

            try:
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        rpc_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        result = await response.json()
                        if "error" in result:
                            raise Exception(f"RPC Error: {result['error']}")

                        if rpc_index != self.current_rpc_index:
                            print(f"Switched to RPC endpoint: {rpc_url}")
                            self.current_rpc_index = rpc_index

                        return result.get("result", {})
            except Exception as e:
                last_error = e
                print(f"RPC endpoint {rpc_url} failed: {e}")
                if attempt < len(self.endpoints) - 1:
                    print(f"Trying next endpoint...")
                continue

        raise Exception(f"All RPC endpoints failed. Last error: {last_error}")

    async def get_owned_objects(self, wallet_address: str) -> List[Dict]:
        """Get all objects owned by the wallet"""
        all_objects = []
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
                                "showOwner": True
                            }
                        },
                        cursor,
                        50
                    ]
                )

                data = result.get("data", [])
                all_objects.extend(data)

                cursor = result.get("nextCursor")
                has_next = result.get("hasNextPage", False)

                if not has_next or not cursor:
                    break

            return all_objects
        except Exception as e:
            print(f"Error fetching owned objects: {e}")
            return []

    async def get_object(self, object_id: str) -> Dict:
        """Get detailed information about an object"""
        try:
            result = await self.rpc_call(
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
        """Get dynamic fields of an object"""
        try:
            result = await self.rpc_call(
                "suix_getDynamicFields",
                [object_id, None, None]
            )
            return result.get("data", [])
        except Exception as e:
            print(f"Error fetching dynamic fields: {e}")
            return []

    async def get_dynamic_field_object(
        self, parent_id: str, key_type: str, key_value: str
    ) -> Dict:
        """Get a specific dynamic field object"""
        try:
            result = await self.rpc_call(
                "suix_getDynamicFieldObject",
                [parent_id, {"type": key_type, "value": key_value}]
            )
            return result.get("data", {})
        except Exception as e:
            print(f"Error fetching dynamic field object: {e}")
            return {}
