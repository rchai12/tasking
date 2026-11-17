import asyncio
import sqlite3
import threading
from pathlib import Path

import pytest

from docket import core, web
from docket import store as store_module
from docket.store import Store
from tests.http_cases import BODY, LINK, NOW, Exchange, Opened, encoded
from tests.support import fixed_times


def seed_link(path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    if kind == "link":
        fixed_times(monkeypatch, NOW)
        with Store(path) as store:
            core.create_task(store, title="Synthetic HTTP task", source="owner")


@pytest.mark.parametrize("kind", ["task", "link"])
@pytest.mark.parametrize("identity", ["email", "agent"])
def test_open_intake_and_close_share_one_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, identity: str
) -> None:
    loop_thread = threading.get_ident()
    opened = Opened(tmp_path / "docket.sqlite3", loop_thread=loop_thread)
    seed_link(opened.path, monkeypatch, kind)
    if identity == "email":
        fixed_times(monkeypatch, NOW)
    else:
        fixed_times(monkeypatch)
    intake = web.accept_task if kind == "task" else web.accept_link
    seen = []

    def recorded(*args, **kwargs):
        assert kwargs["client"] == identity
        seen.append((threading.get_ident(), kwargs["client"], kwargs["key"], kwargs["body"]))
        return intake(*args, **kwargs)

    monkeypatch.setattr(web, "accept_task" if kind == "task" else "accept_link", recorded)
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": identity}, port=8767)
    response = asyncio.run(
        Exchange(
            app,
            [encoded(BODY if kind == "task" else LINK)],
            path="/tasks" if kind == "task" else "/tasks/t1/links",
        ).run()
    )
    if identity == "email":
        assert response[:2] == (201, {"id": "t1" if kind == "task" else "l1"})
    else:
        assert response[:2] == (422, {"error": "invalid_client"})
    assert len(opened.opens) == 1
    assert opened.closes == opened.opens
    assert opened.opens[0] != loop_thread
    assert seen == [(opened.opens[0], identity, "task-key", BODY if kind == "task" else LINK)]


class IntakeBroke(Exception):
    pass


@pytest.mark.parametrize("kind", ["task", "link"])
def test_intake_failure_closes_the_worker_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    loop_thread = threading.get_ident()
    opened = Opened(tmp_path / "docket.sqlite3", loop_thread=loop_thread)
    seed_link(opened.path, monkeypatch, kind)
    fixed_times(monkeypatch)

    def broken(*args, **kwargs):
        assert threading.get_ident() != loop_thread
        raise IntakeBroke

    monkeypatch.setattr(web, "accept_task" if kind == "task" else "accept_link", broken)
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    exchange = Exchange(
        app,
        [encoded(BODY if kind == "task" else LINK)],
        path="/tasks" if kind == "task" else "/tasks/t1/links",
    )
    with pytest.raises(IntakeBroke):
        asyncio.run(exchange.run())
    assert len(opened.opens) == 1
    assert opened.closes == opened.opens
    assert opened.opens[0] != loop_thread
    with Store(opened.path) as store:
        assert store.links("t1") == []
        assert store.request_key("email", "task-key") is None
        assert len(store.tasks()) == (1 if kind == "link" else 0)


def test_write_lock_does_not_block_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path):
        pass
    connect = sqlite3.connect
    writer = connect(path, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    fixed_times(monkeypatch, NOW)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        entered = asyncio.Event()
        observed = []

        class Tracked(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                assert threading.get_ident() != loop_thread, "SQL executed on the event loop"
                observed.append(sql)
                if sql == "BEGIN IMMEDIATE":
                    loop.call_soon_threadsafe(entered.set)
                return super().execute(sql, *args, **kwargs)

        monkeypatch.setattr(
            store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
        )
        opened = Opened(path, loop_thread=loop_thread)
        app = web.create_app(
            open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767
        )
        request = asyncio.create_task(Exchange(app, [encoded(BODY)]).run())
        waiting = asyncio.create_task(entered.wait())
        try:
            done, _ = await asyncio.wait(
                {request, waiting}, timeout=2, return_when=asyncio.FIRST_COMPLETED
            )
            if request in done:
                await request
                raise AssertionError("request finished before the held lock was released")
            assert waiting in done, "worker did not attempt its write"
            # The writer still holds the real SQLite lock while this coroutine progresses.
            for _ in range(3):
                await asyncio.sleep(0)
            assert not request.done()
            assert "PRAGMA busy_timeout = 5000" in observed
            writer.execute("ROLLBACK")
            response = await asyncio.wait_for(request, timeout=2)
            assert response[:2] == (201, {"id": "t1"})
            assert len(opened.opens) == 1
            assert opened.closes == opened.opens
        finally:
            if writer.in_transaction:
                writer.execute("ROLLBACK")
            waiting.cancel()
            if not request.done():
                request.cancel()
            await asyncio.gather(waiting, request, return_exceptions=True)

    try:
        asyncio.run(run())
    finally:
        writer.close()


def test_retries_get_distinct_connections_and_one_audit_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    loop_thread = threading.get_ident()
    opened = Opened(tmp_path / "docket.sqlite3", loop_thread=loop_thread)
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)

    async def run() -> None:
        for status in (201, 200):
            response = await Exchange(app, [encoded(BODY)]).run()
            assert response[:2] == (status, {"id": "t1"})

    asyncio.run(run())
    assert len(opened.opens) == 2
    assert opened.closes == opened.opens
    with Store(opened.path) as store:
        assert [task.id for task in store.tasks()] == ["t1"]
        assert len(store.audit("t1")) == 1
