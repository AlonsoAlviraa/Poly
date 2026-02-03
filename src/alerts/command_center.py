import logging
import os
from typing import Optional

from src.alerts.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class CommandCenterNotifier:
    """
    Simple command center that routes INFO/ALERT/TRADE messages
    to Telegram and optionally Discord via webhook.
    """

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
    ):
        self.telegram = TelegramNotifier(telegram_token, telegram_chat_id)
        self.discord_webhook_url = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    def _send_discord(self, content: str) -> bool:
        if not self.discord_webhook_url:
            logger.debug("[DISCORD DISABLED] No webhook configured.")
            return False
        try:
            import httpx

            with httpx.Client(timeout=10) as client:
                response = client.post(self.discord_webhook_url, json={"content": content})
                response.raise_for_status()
            return True
        except Exception as exc:
            logger.error(f"Discord send error: {exc}")
            return False

    def _send_all(self, message: str) -> None:
        self.telegram.send_message(message)
        self._send_discord(message)

    def send_info(self, message: str) -> None:
        self._send_all(f"ℹ️ {message}")

    def send_alert(self, message: str) -> None:
        self._send_all(f"🚨 {message}")

    def send_trade(self, message: str) -> None:
        self._send_all(f"✅ {message}")
