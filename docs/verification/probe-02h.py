"""Synthetic ASGI stream and worker properties; no sockets or real services."""

import asyncio
import sys
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
FAILURES = 0
EXPECTED = ((201, {"id": "t1"}), (200, {"id": "t1"}), (201, {"id": "l1"}), (200, {"id": "l1"}))
assert len(b" " * 65536 + b"x") == 65537
assert len(b"\xc3\xa9" * 32769) == 65538
assert [status for status, _ in EXPECTED] == [201, 200, 201, 200]
print("oracle: ok")


def check(label: str, action: Callable[[], None]) -> None:
    global FAILURES
    try:
        action()
    except Exception as error:
        FAILURES += 1
        print(f"{label}: FAIL (observed {type(error).__name__})")
    else:
        print(f"{label}: ok")


def streams() -> None:
    from docket.web import create_app
    from tests.http_cases import Exchange, Opened

    layouts = (
        ([b"x" * 65537, b"unread"], 1),
        ([b" " * 65536, b"x", b"unread"], 2),
        ([b"\xc3\xa9" * 32769, b"unread"], 1),
    )
    for chunks, reads in layouts:
        with tempfile.TemporaryDirectory() as folder:
            opened = Opened(Path(folder) / "docket.sqlite3")
            app = create_app(
                open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767
            )
            exchange = Exchange(app, chunks, stop_after=reads)
            result = asyncio.run(exchange.run())
            assert result[:2] == (413, {"error": "too_large"})
            assert result[2]["cache-control"] == "no-store"
            assert exchange.reads == reads
            assert opened.opens == []
            assert not opened.path.exists()


def workers() -> None:
    from docket.store import Store
    from docket.web import create_app
    from tests.http_cases import BODY, LINK, Exchange, Opened, encoded

    with tempfile.TemporaryDirectory() as folder:
        opened = Opened(Path(folder) / "docket.sqlite3", loop_thread=threading.get_ident())
        app = create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)

        async def run() -> None:
            for step, expected in enumerate(EXPECTED):
                is_link = step >= 2
                result = await Exchange(
                    app,
                    [encoded(LINK if is_link else BODY)],
                    path="/tasks/t1/links" if is_link else "/tasks",
                    headers={
                        "authorization": "Bearer synthetic-email-token",
                        "idempotency-key": "link-key" if is_link else "task-key",
                    },
                ).run()
                if result[:2] != expected:
                    print(f"  step {step}: expected {expected}, found {result[:2]}")
                    raise AssertionError

        with patch("docket.clock.now", return_value=datetime(2026, 11, 17, 14, tzinfo=UTC)):
            asyncio.run(run())
        assert len(opened.opens) == 4
        assert opened.closes == opened.opens
        with Store(opened.path) as store:
            assert [task.id for task in store.tasks()] == ["t1"]
            assert [link.id for link in store.links("t1")] == ["l1"]
            assert len(store.audit("t1")) == 1


if "--oracle-only" not in sys.argv:
    check("oversize returns 413 after the decisive chunk; unread tail stays unread", streams)
    check("store lifetime stays off the event loop; task/link retries survive reopen", workers)
print(f"FAILURES {FAILURES}")
sys.exit(bool(FAILURES))
