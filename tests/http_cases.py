"""Synthetic HTTP exchanges for Phase 2h; no sockets or real services."""

import asyncio
import json
import threading
from pathlib import Path

from fastapi import FastAPI

from docket.store import Store

NOW = "2026-11-17T14:00:00+00:00"
BODY = {
    "source": "email",
    "title": "Synthetic HTTP task",
    "deadline": None,
    "provider": "gmail",
    "message_id": "synthetic/1",
    "link": "https://mail.example/1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": "synthetic/2",
    "link": "https://mail.example/2",
}
HEADERS = {"authorization": "Bearer synthetic-email-token", "idempotency-key": "task-key"}


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Exchange:
    def __init__(
        self,
        app: FastAPI,
        chunks: list[bytes],
        *,
        path: str = "/tasks",
        headers: dict[str, str] | None = None,
        stop_after: int | None = None,
    ) -> None:
        self.app = app
        self.chunks = chunks
        self.path = path
        self.headers = {"host": "127.0.0.1:8767", **(HEADERS if headers is None else headers)}
        self.stop_after = stop_after
        self.reads = 0
        self.messages: list[dict] = []
        self.sent = asyncio.Event()

    async def receive(self) -> dict:
        if self.reads == len(self.chunks):
            await self.sent.wait()
            return {"type": "http.disconnect"}
        if self.stop_after is not None:
            assert self.reads < self.stop_after, "read an unnecessary body chunk"
        chunk = self.chunks[self.reads]
        self.reads += 1
        return {"type": "http.request", "body": chunk, "more_body": self.reads < len(self.chunks)}

    async def send(self, message: dict) -> None:
        self.messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            self.sent.set()

    async def run(self) -> tuple[int, dict, dict[str, str]]:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(key.encode(), value.encode()) for key, value in self.headers.items()],
            "server": ("127.0.0.1", 8767),
            "client": ("127.0.0.1", 1),
        }
        await self.app(scope, self.receive, self.send)
        start = next(
            message for message in self.messages if message["type"] == "http.response.start"
        )
        body = b"".join(
            message.get("body", b"")
            for message in self.messages
            if message["type"] == "http.response.body"
        )
        return (
            start["status"],
            json.loads(body),
            {key.decode(): value.decode() for key, value in start["headers"]},
        )


class Opened:
    def __init__(self, path: Path, *, loop_thread: int | None = None) -> None:
        self.path = path
        self.loop_thread = loop_thread
        self.opens: list[int] = []
        self.closes: list[int] = []

    def __call__(self) -> Store:
        thread = threading.get_ident()
        if self.loop_thread is not None:
            assert thread != self.loop_thread, "store opened on the event loop"
        store = Store(self.path)
        self.opens.append(thread)
        close = store.close

        def recorded() -> None:
            self.closes.append(threading.get_ident())
            close()

        store.close = recorded  # type: ignore[method-assign]
        return store
