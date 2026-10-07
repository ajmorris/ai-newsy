"""Email send and clock seams.

Production uses Resend. Tests and dry runs use RecordingSender, which stores
messages and never contacts a provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Protocol


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    from_addr: str


class Sender(Protocol):
    def send(self, message: EmailMessage) -> bool:
        """Deliver one message. Return False when the provider rejects it."""


class Clock(Protocol):
    def now(self) -> datetime:
        """Timezone-aware current time."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class FrozenClock:
    moment: datetime

    def now(self) -> datetime:
        return self.moment


@dataclass
class RecordingSender:
    """Fake sender for tests. Records every message and never calls Resend."""

    sent: List[EmailMessage] = field(default_factory=list)
    fail_addresses: List[str] = field(default_factory=list)

    def send(self, message: EmailMessage) -> bool:
        if message.to in self.fail_addresses:
            return False
        self.sent.append(message)
        return True


class ResendSender:
    """Adapter over the Resend Python SDK."""

    def __init__(self, api_key: str = "", from_addr: str = "") -> None:
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self.from_addr = from_addr or os.getenv("EMAIL_FROM", "newsletter@example.com")

    def send(self, message: EmailMessage) -> bool:
        import resend

        resend.api_key = self.api_key
        from_addr = message.from_addr or self.from_addr
        resend.Emails.send(
            {
                "from": f"AI Newsy <{from_addr}>",
                "to": [message.to],
                "subject": message.subject,
                "html": message.html,
            }
        )
        return True
