import asyncio
import json
from pathlib import Path

import pytest

from docket import web
from tests.http_cases import BODY, Exchange, Opened, encoded

TOKEN = "synthetic-token-marker-2h"
TITLE = "synthetic-title-marker-2h"
REFERENCE = "synthetic-reference-marker-2h"


class ReceiveBroke(Exception):
    pass


class FactoryBroke(Exception):
    pass


def test_receive_failure_propagates_before_a_store_opens(tmp_path: Path) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    exchange = Exchange(app, [encoded(BODY)])

    async def broken() -> dict:
        raise ReceiveBroke

    exchange.receive = broken  # type: ignore[method-assign]
    with pytest.raises(BaseExceptionGroup) as raised:
        asyncio.run(exchange.run())
    assert len(raised.value.exceptions) == 1
    assert isinstance(raised.value.exceptions[0], ReceiveBroke)
    assert exchange.reads == 0
    assert opened.opens == []
    assert not opened.path.exists()
    assert _statuses(exchange) == [500]


def test_store_factory_failure_propagates_without_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[bool] = []

    def unused(*args: object, **kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(web, "accept_task", unused)

    def factory() -> None:
        raise FactoryBroke

    app = web.create_app(open_store=factory, tokens={"synthetic-email-token": "email"}, port=8767)
    exchange = Exchange(app, [encoded(BODY)])
    with pytest.raises(FactoryBroke):
        asyncio.run(exchange.run())
    assert called == []
    assert not (tmp_path / "docket.sqlite3").exists()
    assert _statuses(exchange) == [500]


def _statuses(exchange: Exchange) -> list[int]:
    return [
        message["status"]
        for message in exchange.messages
        if message["type"] == "http.response.start"
    ]


def test_oversized_refusal_returns_only_the_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={TOKEN: "email"}, port=8767)
    payload = json.dumps(
        {**BODY, "title": TITLE, "message_id": REFERENCE, "link": REFERENCE},
        separators=(",", ":"),
    ).encode()
    chunk = payload + b"x" * (web.MAX_BODY + 1 - len(payload))
    assert len(chunk) > web.MAX_BODY
    exchange = Exchange(
        app,
        [chunk, b"unread"],
        headers={"authorization": f"Bearer {TOKEN}", "idempotency-key": "k"},
        stop_after=1,
    )
    with caplog.at_level(0):
        status, body, headers = asyncio.run(exchange.run())
    assert (status, body) == (413, {"error": "too_large"})
    assert headers["cache-control"] == "no-store"
    captured = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    shown = json.dumps(body) + json.dumps(headers)
    for marker in (TOKEN, TITLE, REFERENCE):
        assert marker not in shown
        assert marker not in captured.out
        assert marker not in captured.err
        assert marker not in logged
    assert opened.opens == []
    assert not opened.path.exists()
