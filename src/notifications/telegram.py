"""Telegram notification service"""
import ssl
import aiohttp
import certifi

from ..config import TELEGRAM_ALERT_BOT_TOKEN, TELEGRAM_LOG_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramNotifier:
    """Send notifications via Telegram bots"""

    def __init__(self):
        self.alert_bot_token = TELEGRAM_ALERT_BOT_TOKEN
        self.log_bot_token = TELEGRAM_LOG_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID

    async def _send_message(
        self, message: str, bot_token: str, silent: bool = False
    ) -> bool:
        """Send Telegram message using specified bot"""
        if not bot_token or not self.chat_id:
            print("Telegram credentials not configured")
            return False

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_notification": silent
        }

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return True
                else:
                    print(f"Failed to send Telegram message: {response.status}")
                    return False

    async def send_alert(self, message: str) -> bool:
        """Send critical alert (unmuted bot)"""
        if await self._send_message(message, self.alert_bot_token, silent=False):
            print("Telegram alert sent")
            return True
        return False

    async def send_log(self, message: str, silent: bool = True) -> bool:
        """Send log message (logs bot)"""
        if await self._send_message(message, self.log_bot_token, silent=silent):
            print("Telegram log sent")
            return True
        return False
