"""Notifier protocol — notification channel abstraction."""
from typing import Protocol


class Notifier(Protocol):
    """Abstract interface for sending notifications."""

    async def send_alert(self, message: str, subject: str = "") -> bool: ...

    async def send_log(self, message: str, silent: bool = True) -> bool: ...
