"""What the reminder engine hands to whatever delivers a reminder.

Stage 4 implements `Notifier` with the shared Discord service's client; until then only the
tests' fake does. A notice carries a retry key, a task id, the task's plain-text title and fixed
text: nothing else leaves the app.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Notice:
    key: str
    task_id: str
    title: str
    text: str


class NotifierError(Exception):
    """The notice was not delivered. The caller sends it again later with the same key."""


class Notifier(Protocol):
    def send(self, notice: Notice) -> None:
        """Deliver once per key: a repeated key must not post a second message."""
