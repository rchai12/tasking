"""In-memory MCP calls, a counting clock and a seeded store for the Phase 6a tool tests.

The MCP SDK and the phase's modules are imported inside the functions, so this file imports
before they exist.
"""

import asyncio
from datetime import UTC, datetime

from docket import config, core
from docket.deadlines import Deadline, WorkTime
from docket.store import open_store

HOME = "America/New_York"
NOW = datetime(2026, 11, 20, 15, tzinfo=UTC)


def at(text: str) -> datetime:
    """A UTC instant from an ISO date and time without an offset."""
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


class Clock:
    """The fixed clock: `reads` counts the calls to `now`."""

    def __init__(self, moment: datetime = NOW) -> None:
        self.moment = moment
        self.reads = 0

    def now(self) -> datetime:
        self.reads += 1
        return self.moment


def server():
    """The docket MCP server, built from the test's settings."""
    from docket.mcp_server import server as module

    return module.build_server(config.get_settings())


def listed(built) -> list:
    from mcp.client import Client

    async def run() -> list:
        async with Client(built) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())


def call(built, name: str, arguments: dict):
    from mcp.client import Client

    async def run():
        async with Client(built) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def refusal(result) -> tuple:
    """A tool result as (is_error, structured content, texts), for literal comparison."""
    return (result.is_error, result.structured_content, [part.text for part in result.content])


def add(store, title: str, deadline_at: str | None = None, time_given: bool = True, work=None):
    deadline = None if deadline_at is None else Deadline(at(deadline_at), HOME, time_given)
    return core.create_task(store, title=title, source="owner", deadline=deadline, work=work)


def seed() -> None:
    """Nine tasks, all made at NOW (10:00 in New York on 2026-11-20).

    t1 open, no deadline       t2 open, 17:00 default today, with a work time
    t3 in progress, 09:00      t4 open, 22:30 tonight (already 2026-11-21 in UTC)
    t5 open, tomorrow 10:00    t6 done, yesterday 17:00
    t7 cancelled, today 15:00  t8 open, yesterday 17:00
    t9 open, due exactly NOW
    """
    with open_store(config.get_settings()) as store:
        add(store, "Synthetic no deadline")
        add(
            store,
            "Synthetic due at five",
            "2026-11-20T22:00",
            time_given=False,
            work=WorkTime(at("2026-11-20T19:00"), 45, HOME),
        )
        add(store, "Synthetic started late", "2026-11-20T14:00")
        add(store, "Synthetic tonight", "2026-11-21T03:30")
        add(store, "Synthetic tomorrow", "2026-11-21T15:00")
        add(store, "Synthetic done", "2026-11-19T22:00")
        add(store, "Synthetic cancelled", "2026-11-20T20:00")
        add(store, "Synthetic yesterday", "2026-11-19T22:00")
        add(store, "Synthetic due now", "2026-11-20T15:00")
        core.change_state(store, "t3", "start", actor="owner")
        core.change_state(store, "t6", "done", actor="owner")
        core.change_state(store, "t7", "cancel", actor="owner")
