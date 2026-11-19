"""A fake clock and stop for the Phase 3e reminder loop tests."""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta

T0 = datetime(2026, 11, 20, 16, tzinfo=UTC)
ZONE = "UTC"
AT = time(7)


class Ticker:
    """The loop's clock and stop at once: each wait moves the clock on by its timeout.

    `is_set` is true once `passes` waits have happened, so a loop runs `passes` passes.
    `between[n]` runs inside the n-th wait (0-based), after the clock has moved on.
    `reads` counts clock reads; `waits` records each timeout.
    """

    def __init__(self, passes: int, moment: datetime = T0) -> None:
        self.moment = moment
        self.passes = passes
        self.waits: list[float] = []
        self.reads = 0
        self.between: dict[int, Callable[[], None]] = {}

    def now(self) -> datetime:
        self.reads += 1
        return self.moment

    def is_set(self) -> bool:
        return len(self.waits) >= self.passes

    def wait(self, timeout: float) -> bool:
        index = len(self.waits)
        self.waits.append(timeout)
        self.moment += timedelta(seconds=timeout)
        if index in self.between:
            self.between[index]()
        return self.is_set()


def text(sent) -> tuple:
    """A notice as (key, task id, text) and a digest as (key, heading), for literal lists."""
    if hasattr(sent, "task_id"):
        return (sent.key, sent.task_id, sent.text)
    return (sent.key, sent.heading)
