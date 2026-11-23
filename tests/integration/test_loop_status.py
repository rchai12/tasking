"""Phase 5f: each pass of the loop is recorded in one stored row, with each half's failures."""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

import pytest

from docket import clock, core, ids, reminders
from docket.deadlines import Deadline
from docket.store import Store, StoreError
from tests.loop_cases import AT, T0, ZONE, Ticker
from tests.notifier_cases import FakeNotifier, Killed, SyntheticBug

MARK = "Phase 5f given test: remove this marker when the loop records its status"
NY = "America/New_York"
COLUMNS = "number, pass_at, sent, digest, reminders_failures, digest_failures, skipped"
SOUND = (1, "2026-11-20T16:00:00.000000+00:00", 0, 0, 0, 0, "[]")


def status(
    pass_at: datetime,
    sent: int,
    digest: bool,
    reminders_failures: int,
    digest_failures: int,
    skipped: tuple[str, ...] = (),
):
    from docket.store import LoopStatus

    return LoopStatus(
        pass_at=pass_at,
        sent=sent,
        digest=digest,
        reminders_failures=reminders_failures,
        digest_failures=digest_failures,
        skipped=skipped,
    )


def raw(opened: Store) -> list[tuple]:
    return [tuple(row) for row in opened._connection.execute(f"SELECT {COLUMNS} FROM loop_status")]


def plant(opened: Store, row: tuple) -> None:
    opened._connection.execute(
        f"INSERT INTO loop_status ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)", row
    )


def counted(monkeypatch: pytest.MonkeyPatch, ticker: Ticker) -> None:
    keys = iter(f"k{n}" for n in range(1, 100))
    monkeypatch.setattr(clock, "now", ticker.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))


def loop(opened: Store, ticker: Ticker, notifier: FakeNotifier | None = None) -> int:
    return reminders.run_loop(opened, notifier or FakeNotifier(), zone=ZONE, at=AT, stop=ticker)


def failing_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args, **kwargs):
        raise SyntheticBug()

    monkeypatch.setattr(reminders, "send_digest", broken)


@pytest.mark.parametrize(
    "row",
    [
        (2, *SOUND[1:]),
        (1, SOUND[1], -1, *SOUND[3:]),
        (1, SOUND[1], "many", *SOUND[3:]),
        (1, SOUND[1], 0, 2, *SOUND[4:]),
        (1, SOUND[1], 0, 0, -1, 0, "[]"),
        (1, SOUND[1], 0, 0, 0, -1, "[]"),
        (1, *SOUND[1:6], "{}"),
        (1, *SOUND[1:6], "not json"),
    ],
    ids=[
        "second-row",
        "negative-sent",
        "text-sent",
        "digest-two",
        "negative-reminders",
        "negative-digest",
        "object-skipped",
        "unparsed-skipped",
    ],
)
def test_the_status_table_refuses_a_bad_row(tmp_path, row: tuple) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        if row[0] == 2:
            plant(opened, SOUND)
        with pytest.raises(sqlite3.IntegrityError):
            plant(opened, row)


def test_the_status_row_is_never_removed(tmp_path) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        plant(opened, SOUND)
        with pytest.raises(sqlite3.IntegrityError, match="loop status is never removed"):
            opened._connection.execute("DELETE FROM loop_status")
        assert raw(opened) == [SOUND]


def test_a_saved_status_replaces_the_one_row(tmp_path) -> None:
    first = status(T0, 3, True, 0, 0)
    second = status(T0 + timedelta(seconds=30), 2, True, 0, 3, ("t2", "t5"))
    with Store(tmp_path / "docket.sqlite3") as opened:
        assert opened.loop_status() is None
        with opened.transaction():
            opened.save_loop_status(first)
        assert opened.loop_status() == first
        with opened.transaction():
            opened.save_loop_status(second)
        assert opened.loop_status() == second
        assert raw(opened) == [(1, "2026-11-20T16:00:30.000000+00:00", 2, 1, 0, 3, '["t2","t5"]')]


def test_saving_needs_a_transaction_and_a_utc_time(tmp_path) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        with pytest.raises(StoreError) as outside:
            opened.save_loop_status(status(T0, 0, False, 0, 0))
        with opened.transaction(), pytest.raises(StoreError) as naive:
            opened.save_loop_status(status(datetime(2026, 11, 20, 16), 0, False, 0, 0))
        assert (str(outside.value), str(naive.value)) == (
            "a write needs a transaction",
            "an instant must be in UTC",
        )
        assert raw(opened) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"sent": -1},
        {"sent": True},
        {"reminders_failures": -1},
        {"digest_failures": 1.5},
        {"digest": 1},
        {"skipped": ("x1",)},
        {"skipped": ["t1"]},
    ],
    ids=[
        "negative-sent",
        "bool-sent",
        "negative-reminders",
        "fractional-digest",
        "int-digest",
        "not-a-task-id",
        "list-skipped",
    ],
)
def test_a_bad_status_is_refused_before_it_is_written(tmp_path, fields: dict) -> None:
    import dataclasses

    bad = dataclasses.replace(status(T0, 0, False, 0, 0), **fields)
    with Store(tmp_path / "docket.sqlite3") as opened:
        with opened.transaction(), pytest.raises(StoreError) as raised:
            opened.save_loop_status(bad)
        assert (str(raised.value), raw(opened)) == ("invalid loop status", [])


@pytest.mark.parametrize(
    "row",
    [
        (1, "2026-11-20T16:00:00", *SOUND[2:]),
        (1, "soon", *SOUND[2:]),
        (1, *SOUND[1:6], '["x1"]'),
        (1, *SOUND[1:6], "[7]"),
    ],
    ids=["naive-time", "unparsed-time", "not-a-task-id", "number-id"],
)
def test_a_bad_stored_status_raises_a_constant_error(tmp_path, row: tuple) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        plant(opened, row)
        with pytest.raises(StoreError) as raised:
            opened.loop_status()
        assert str(raised.value) == "invalid stored loop status"


@pytest.mark.parametrize(
    ("previous", "result", "counts"),
    [
        (None, (2, True, (), ()), (0, 0)),
        (None, (0, False, ("reminders", "digest"), ()), (1, 1)),
        ((3, 4), (1, False, (), ()), (0, 0)),
        ((3, 4), (0, False, ("reminders",), ()), (4, 0)),
        ((3, 4), (1, False, ("digest",), ()), (0, 5)),
        ((3, 4), (0, False, ("reminders", "digest"), ()), (4, 5)),
        ((3, 4), (1, True, (), ("t2",)), (4, 0)),
    ],
    ids=[
        "first-ok",
        "first-both-fail",
        "ok-resets",
        "reminders-fail",
        "digest-fails",
        "both-fail",
        "a-skip-fails-reminders",
    ],
)
def test_next_status_counts_each_half(previous, result, counts) -> None:
    before = None if previous is None else status(T0, 9, True, *previous, ("t9",))
    at = T0 + timedelta(seconds=30)
    found = reminders.next_status(before, reminders.PassResult(*result), at)
    assert found == status(at, result[0], result[1], *counts, result[3])


def test_the_loop_records_each_pass_after_it_runs(tmp_path, monkeypatch) -> None:
    ticker = Ticker(3)
    counted(monkeypatch, ticker)
    failing_digest(monkeypatch)
    seen = []
    with Store(tmp_path / "docket.sqlite3") as opened:
        for index in range(3):
            ticker.between[index] = lambda: seen.append(opened.loop_status())
        assert loop(opened, ticker) == 3
    assert seen == [
        status(T0, 0, False, 0, 1),
        status(T0 + timedelta(seconds=30), 0, False, 0, 2),
        status(T0 + timedelta(seconds=60), 0, False, 0, 3),
    ]


def test_the_loop_reads_the_clock_once_more_per_pass_to_record_it(tmp_path, monkeypatch) -> None:
    ticker = Ticker(3)
    counted(monkeypatch, ticker)
    with Store(tmp_path / "docket.sqlite3") as opened:
        assert loop(opened, ticker) == 3
        assert opened.loop_status() == status(T0 + timedelta(seconds=60), 0, False, 0, 0)
    assert ticker.reads == 9


def test_the_counts_carry_on_across_a_restart(tmp_path, monkeypatch) -> None:
    path = tmp_path / "docket.sqlite3"
    first = Ticker(2)
    counted(monkeypatch, first)
    failing_digest(monkeypatch)
    with Store(path) as opened:
        loop(opened, first)
    again = Ticker(1, T0 + timedelta(minutes=10))
    monkeypatch.setattr(clock, "now", again.now)
    with Store(path) as opened:
        loop(opened, again)
        assert opened.loop_status() == status(T0 + timedelta(minutes=10), 0, False, 0, 3)
    monkeypatch.undo()
    healthy = Ticker(1, T0 + timedelta(minutes=20))
    counted(monkeypatch, healthy)
    with Store(path) as opened:
        loop(opened, healthy)
        assert opened.loop_status() == status(T0 + timedelta(minutes=20), 0, False, 0, 0)


def test_a_skipped_task_counts_against_the_reminders_half(tmp_path, monkeypatch) -> None:
    ticker = Ticker(2)
    counted(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        for _ in range(2):
            deadline = Deadline(T0 + timedelta(hours=2), "UTC", True)
            core.create_task(
                opened, title="Synthetic status task", source="owner", deadline=deadline
            )
        opened._connection.execute(
            "INSERT INTO reminders (task, kind, fire_at, planned_at) VALUES (1, 'before', ?, ?)",
            ("2026-11-20T17:00:00.000000+00:00", "2026-11-20T16:00:00"),
        )
        ticker.moment = T0 + timedelta(hours=1)
        assert loop(opened, ticker, notifier) == 2
        assert opened.loop_status() == status(
            T0 + timedelta(hours=1, seconds=30), 0, False, 2, 0, ("t1",)
        )
    assert [sent.task_id for sent in notifier.delivered] == ["t2"]


def test_a_bad_stored_status_starts_the_counts_again(tmp_path, monkeypatch) -> None:
    ticker = Ticker(1)
    counted(monkeypatch, ticker)
    failing_digest(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as opened:
        plant(opened, (1, "2026-11-20T16:00:00", 0, 0, 7, 7, "[]"))
        loop(opened, ticker)
        assert opened.loop_status() == status(T0, 0, False, 0, 1)


def test_a_failed_status_write_never_stops_the_loop(tmp_path, monkeypatch) -> None:
    def broken(self, found) -> None:
        raise SyntheticBug()

    ticker = Ticker(3)
    counted(monkeypatch, ticker)
    with Store(tmp_path / "docket.sqlite3") as opened:
        monkeypatch.setattr(Store, "save_loop_status", broken)
        assert loop(opened, ticker) == 3
        assert raw(opened) == []
    assert ticker.waits == [30, 30, 30]


def test_a_crash_while_recording_is_not_caught(tmp_path, monkeypatch) -> None:
    def killed(self, found) -> None:
        raise Killed()

    ticker = Ticker(3)
    counted(monkeypatch, ticker)
    with Store(tmp_path / "docket.sqlite3") as opened:
        monkeypatch.setattr(Store, "save_loop_status", killed)
        with pytest.raises(Killed):
            loop(opened, ticker)
    assert ticker.waits == []


def test_the_stale_bound_is_five_minutes() -> None:
    from docket import domain

    assert domain.LOOP_STALE_MINUTES == 5


@pytest.mark.parametrize(
    ("found", "seconds", "lines"),
    [
        (None, 30, ["Reminder loop: no pass recorded yet"]),
        (
            (3, True, 0, 0, ()),
            30,
            [
                "Reminder loop: running, last pass Fri Nov 20 11:00 EST",
                "Reminders: ok, 3 sent",
                "Digest: ok, sent",
            ],
        ),
        (
            (0, False, 0, 0, ()),
            30,
            [
                "Reminder loop: running, last pass Fri Nov 20 11:00 EST",
                "Reminders: ok, 0 sent",
                "Digest: ok",
            ],
        ),
        (
            (1, False, 1, 4, ("t2", "t5")),
            30,
            [
                "Reminder loop: running, last pass Fri Nov 20 11:00 EST",
                "Reminders: failing for 1 pass, 1 sent",
                "Digest: failing for 4 passes",
                "Skipped tasks: t2, t5",
            ],
        ),
        (
            (0, False, 0, 0, ()),
            300,
            [
                "Reminder loop: running, last pass Fri Nov 20 11:00 EST",
                "Reminders: ok, 0 sent",
                "Digest: ok",
            ],
        ),
        (
            (0, False, 2, 0, ()),
            301,
            [
                "Reminder loop: not running, last pass Fri Nov 20 11:00 EST",
                "Reminders: failing for 2 passes, 0 sent",
                "Digest: ok",
            ],
        ),
    ],
    ids=["none", "all-ok", "no-digest", "failing", "five-minutes", "stale"],
)
def test_loop_status_lines(found, seconds: int, lines: list[str]) -> None:
    from docket import views

    stored = None if found is None else status(T0, *found)
    now = T0 + timedelta(seconds=seconds)
    assert views.loop_status_lines(stored, NY, now) == lines


def test_a_bare_pass_records_nothing_and_reads_the_clock_twice(tmp_path, monkeypatch) -> None:
    """A guard: only `run_loop` records, so a loop pass reads the clock exactly once more."""
    ticker = Ticker(0)
    counted(monkeypatch, ticker)
    with Store(tmp_path / "docket.sqlite3") as opened:
        reminders.run_pass(opened, FakeNotifier(), zone=ZONE, at=AT)
        with closing(sqlite3.connect(tmp_path / "docket.sqlite3")) as other:
            assert other.execute("SELECT count(*) FROM loop_status").fetchone() == (0,)
    assert ticker.reads == 2
