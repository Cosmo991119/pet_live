"""
Notification layer for pet agent messages.

Message generation and message delivery are separate responsibilities. The
first implementation prints to the console; Telegram can be added later by
implementing the same send interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv


class Notifier(ABC):
    """Base interface for message delivery channels."""

    @abstractmethod
    def send(
        self,
        pet_id: int,
        message: str,
        severity: str = "normal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Deliver one pet message."""


class ConsoleNotifier(Notifier):
    """Print pet messages to stdout for local debugging."""

    def send(
        self,
        pet_id: int,
        message: str,
        severity: str = "normal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [pet_id={pet_id}] [{severity}] {message}")
        if metadata:
            print(f"[metadata] {metadata}")


class TelegramNotifier(Notifier):
    """Send pet messages through Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        if not bot_token.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not chat_id.strip():
            raise ValueError("TELEGRAM_CHAT_ID is required")
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(
        self,
        pet_id: int,
        message: str,
        severity: str = "normal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        prefix = "!" if severity == "attention" else ""
        text = f"{prefix}{message}"
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Telegram sendMessage failed") from None


def notifier_from_env() -> Notifier:
    """Create the configured notifier for local/dev runtime."""
    load_dotenv()
    channel = os.getenv("PET_AGENT_NOTIFIER", "console").lower()
    if channel == "telegram":
        return TelegramNotifier(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )
    return ConsoleNotifier()


def notify_event_message(
    notifier: Notifier,
    pet_id: int,
    message_result: dict[str, Any],
) -> None:
    """Send a structured event-message result through a notifier."""
    message = message_result["message"]
    notifier.send(
        pet_id=pet_id,
        message=message["message"],
        severity=message.get("severity", "normal"),
        metadata={
            "facts_used": message.get("facts_used", []),
            "internal_signal": message.get("internal_signal"),
            "model_name": message_result.get("model_name"),
            "prompt_version": message_result.get("prompt_version"),
        },
    )
