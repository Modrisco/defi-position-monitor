"""Chain client protocol — blockchain RPC abstraction."""
from typing import Any, Protocol


class ChainClient(Protocol):
    """Abstract interface for blockchain RPC interactions."""

    async def get_owned_objects(self, wallet_address: str) -> list[dict[str, Any]]: ...

    async def get_object(self, object_id: str) -> dict[str, Any]: ...

    async def get_dynamic_field_object(
        self, parent_id: str, key_type: str, key_value: str
    ) -> dict[str, Any]: ...
