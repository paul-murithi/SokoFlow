from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings


class MessageDeliveryError(RuntimeError):
    """Raised when a message cannot be delivered to the configured transport."""


class MessageSender(Protocol):
    def send_text(self, recipient: str, message_text: str) -> None:
        """Deliver a text message to the configured channel."""


@dataclass(frozen=True, slots=True)
class MockMessageSender:
    endpoint_url: str
    timeout_seconds: float = 5.0

    def send_text(self, recipient: str, message_text: str) -> None:
        try:
            httpx.post(
                self.endpoint_url,
                json={"recipient": recipient, "reply_text": message_text},
                timeout=self.timeout_seconds,
            ).raise_for_status()
        except httpx.HTTPError as exc:
            raise MessageDeliveryError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class WhatsAppMessageSender:
    endpoint_url: str
    token: str
    timeout_seconds: float = 5.0

    def send_text(self, recipient: str, message_text: str) -> None:
        # TODO: Implement the real WhatsApp delivery call when the production
        # channel contract is finalized.
        return None


def build_message_sender() -> MessageSender:
    backend = settings.sender_backend

    # TODO: Make configurable using a environment variable for local testing
    endpoint_url = os.getenv("MESSAGE_SENDER_URL", "http://localhost:8080")

    if backend == "mock":
        return MockMessageSender(endpoint_url=endpoint_url)

    if backend == "whatsapp":
        whatsapp_token = settings.whatsapp_access_token
        if whatsapp_token is None:
            raise ValueError("WhatsApp access token is not configured in settings.")

        return WhatsAppMessageSender(
            # TODO: Add configuring WhatsApp API in settings.
            endpoint_url="",
            token=whatsapp_token,
        )

    raise ValueError(f"Unknown sender backend: {backend}")
