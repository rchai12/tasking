import asyncio
from pathlib import Path

import pytest
from starlette.requests import Request

from docket import core, web
from docket.store import Store
from tests.http_cases import BODY, HEADERS, LINK, NOW, Exchange, Opened, encoded
from tests.support import fixed_times


@pytest.mark.parametrize("path", ["/tasks", "/tasks/t1/links"], ids=["task", "link"])
@pytest.mark.parametrize("layout", ["one", "split", "unicode-bytes"])
def test_oversized_stream_stops_before_another_chunk(
    tmp_path: Path, path: str, layout: str
) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    if layout == "one":
        chunks, reads = [b"x" * 65537, b"unread"], 1
    elif layout == "split":
        chunks, reads = [b" " * 65536, b"x", b"unread"], 2
    else:
        chunks, reads = [b"\xc3\xa9" * 32769, b"unread"], 1
    exchange = Exchange(app, chunks, path=path, stop_after=reads)
    status, body, headers = asyncio.run(exchange.run())
    assert (status, body) == (413, {"error": "too_large"})
    assert headers["cache-control"] == "no-store"
    assert exchange.reads == reads
    assert opened.opens == []
    assert not opened.path.exists()


@pytest.mark.parametrize(
    "length_header", [None, "1", "999999"], ids=["absent", "understated", "overstated"]
)
@pytest.mark.parametrize("kind", ["task", "link"])
def test_exact_limit_uses_actual_bytes_not_content_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, length_header: str | None, kind: str
) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    if kind == "link":
        fixed_times(monkeypatch, NOW)
        with Store(opened.path) as store:
            core.create_task(store, title="Synthetic HTTP task", source="owner")
    fixed_times(monkeypatch, NOW)
    payload = encoded(BODY if kind == "task" else LINK)
    exact = payload + b" " * (65536 - len(payload))
    assert len(exact) == 65536
    sent = dict(HEADERS)
    if length_header is not None:
        sent["content-length"] = length_header
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    exchange = Exchange(
        app,
        [b"", exact[:13], exact[13:], b""],
        path="/tasks" if kind == "task" else "/tasks/t1/links",
        headers=sent,
    )
    status, body, headers = asyncio.run(exchange.run())
    assert (status, body) == (201, {"id": "t1" if kind == "task" else "l1"})
    assert headers["cache-control"] == "no-store"
    assert exchange.reads == 4
    assert len(opened.opens) == 1
    assert opened.closes == opened.opens


def test_utf8_character_may_span_body_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    payload = encoded({**BODY, "title": "Café"})
    cut = payload.index(b"\xc3") + 1
    response = asyncio.run(Exchange(app, [payload[:cut], payload[cut:]]).run())
    assert response[:2] == (201, {"id": "t1"})
    with Store(opened.path) as store:
        assert store.task("t1").title == "Café"


class UnboundedReadCalled(Exception):
    pass


def test_route_never_uses_request_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise UnboundedReadCalled

    monkeypatch.setattr(Request, "body", forbidden)
    fixed_times(monkeypatch, NOW)
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    response = asyncio.run(Exchange(app, [encoded(BODY)]).run())
    assert response[:2] == (201, {"id": "t1"})
    assert calls == []


@pytest.mark.parametrize(
    ("headers", "path", "status", "error"),
    [
        ({"host": "wrong.example"}, "/tasks", 400, "wrong_host"),
        (HEADERS, "/unknown", 404, "not_found"),
        ({}, "/tasks", 401, "unauthorized"),
    ],
    ids=["host", "route", "authentication"],
)
def test_early_refusals_do_not_read_a_stream(
    tmp_path: Path, headers: dict[str, str], path: str, status: int, error: str
) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    exchange = Exchange(app, [b"x" * 65537, b"unread"], headers=headers, path=path, stop_after=0)
    found = asyncio.run(exchange.run())
    assert found[:2] == (status, {"error": error})
    assert found[2]["cache-control"] == "no-store"
    assert exchange.reads == 0
    assert opened.opens == []


@pytest.mark.parametrize(
    ("chunks", "key", "status", "error"),
    [
        ([b" " * 65536, b"x"], None, 413, "too_large"),
        ([b"{"], None, 400, "missing_key"),
        ([b"{"], "k", 422, "invalid_json"),
        ([b"\xff"], "k", 422, "invalid_json"),
        ([b""], "k", 422, "invalid_json"),
    ],
    ids=["size-before-key", "key-before-json", "json", "utf8", "empty"],
)
def test_streaming_preserves_size_key_and_json_order(
    tmp_path: Path, chunks: list[bytes], key: str | None, status: int, error: str
) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-email-token": "email"}, port=8767)
    sent = {"authorization": HEADERS["authorization"]}
    if key is not None:
        sent["idempotency-key"] = key
    exchange = Exchange(app, chunks, headers=sent)
    found = asyncio.run(exchange.run())
    assert found[:2] == (status, {"error": error})
    assert opened.opens == []
