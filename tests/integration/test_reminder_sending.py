import inspect
import multiprocessing
from datetime import datetime

import pytest

from docket import core
from docket.notifier import Notice, NotifierError
from docket.store import Store
from tests.notifier_cases import (
    FakeNotifier,
    Killed,
    SyntheticBug,
    at,
    due_in,
    rows,
    send_in_child,
    work_in,
)
from tests.support import fixed_ids, fixed_times


def moment(minutes: float) -> datetime:
    return datetime.fromisoformat(at(minutes))


def create(opened: Store, title: str = "Synthetic task", **fields) -> None:
    core.create_task(opened, title=title, source="owner", **fields)


def test_the_engine_names_and_notifier_contract() -> None:
    import dataclasses

    from docket import notifier, reminders

    assert reminders.CLAIM_MINUTES == 5
    assert list(inspect.signature(reminders.send_due).parameters) == ["store", "notifier"]
    assert list(inspect.signature(reminders.notice_text).parameters) == ["kind", "missed"]
    assert [field.name for field in dataclasses.fields(Notice)] == [
        "key",
        "task_id",
        "title",
        "text",
    ]
    assert issubclass(NotifierError, Exception)
    assert list(inspect.signature(notifier.Notifier.send).parameters) == ["self", "notice"]


@pytest.mark.parametrize(
    "kind,missed,text",
    [
        ("start", 0, "Time to start."),
        ("before", 1, "Are you working on this?"),
        ("due_soon", 0, "This is due soon."),
        ("due", 1, "This is now due."),
        ("late", 0, "This is late."),
        ("late", 2, "Missed while docket was offline: 2 reminders.\nThis is late."),
        ("before", 7, "Missed while docket was offline: 7 reminders.\nAre you working on this?"),
    ],
    ids=["start", "before", "due-soon", "due", "late", "missed-two", "missed-seven"],
)
def test_notice_text_is_fixed_per_kind_with_a_missed_line_from_two(kind, missed, text) -> None:
    from docket import reminders

    assert reminders.notice_text(kind, missed) == text


def test_deadlines_one_two_and_three_minutes_out_fire_in_order_once(tmp_path, monkeypatch) -> None:
    from docket import reminders
    from docket.store import Post

    fixed_times(monkeypatch, at(0), at(0), at(0), at(0), at(1.5), at(2.5), at(3.5), at(3.5))
    fixed_ids(monkeypatch, "k1", "k2", "k3", "k4", "k5", "k6")
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        create(opened, "Synthetic one", deadline=due_in(1))
        create(opened, "Synthetic two", deadline=due_in(2))
        create(opened, "Synthetic three", deadline=due_in(3))
        sent = [reminders.send_due(opened, notifier) for _ in range(5)]
        assert sent == [3, 1, 1, 1, 0]
        assert (
            notifier.delivered
            == notifier.attempts
            == [
                Notice("k1", "t1", "Synthetic one", "This is due soon."),
                Notice("k2", "t2", "Synthetic two", "This is due soon."),
                Notice("k3", "t3", "Synthetic three", "This is due soon."),
                Notice("k4", "t1", "Synthetic one", "This is now due."),
                Notice("k5", "t2", "Synthetic two", "This is now due."),
                Notice("k6", "t3", "Synthetic three", "This is now due."),
            ]
        )
        assert opened.posts("t1") == [
            Post("p1", "t1", "k1", "due_soon", 0, ("r1",), moment(0), moment(0), moment(0)),
            Post("p4", "t1", "k4", "due", 1, ("r2",), moment(1.5), moment(1.5), moment(1.5)),
        ]
        first = opened.reminders("t1")[:3]
        assert [(row.claimed_at, row.sent_at) for row in first] == [
            (moment(0), moment(0)),
            (moment(1.5), moment(1.5)),
            (None, None),
        ]


def test_a_work_time_start_reminder_fires_once(tmp_path, monkeypatch) -> None:
    from docket import reminders

    fixed_times(monkeypatch, at(0), at(0), at(10), at(10.5))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        create(opened, deadline=due_in(24 * 60), work=work_in(10))
        assert [reminders.send_due(opened, notifier) for _ in range(3)] == [0, 1, 0]
    assert notifier.delivered == [Notice("k1", "t1", "Synthetic task", "Time to start.")]


def test_reminders_that_came_due_while_down_become_one_status_message(
    tmp_path, monkeypatch
) -> None:
    from docket import reminders
    from docket.store import Post

    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(270), at(301))
    fixed_ids(monkeypatch, "k1", "k2")
    notifier = FakeNotifier()
    with Store(path) as opened:
        create(opened, deadline=due_in(120))
    before = {table: rows(path, table) for table in ("tasks", "audit_log", "links", "request_keys")}
    with Store(path) as opened:
        assert [reminders.send_due(opened, notifier) for _ in range(2)] == [1, 1]
        assert notifier.delivered == [
            Notice(
                "k1",
                "t1",
                "Synthetic task",
                "Missed while docket was offline: 5 reminders.\nThis is late.",
            ),
            Notice("k2", "t1", "Synthetic task", "This is late."),
        ]
        assert opened.posts("t1") == [
            Post(
                "p1",
                "t1",
                "k1",
                "late",
                5,
                ("r1", "r2", "r3", "r4", "r5"),
                moment(270),
                moment(270),
                moment(270),
            ),
            Post("p2", "t1", "k2", "late", 1, ("r6",), moment(301), moment(301), moment(301)),
        ]
        sent = [row.sent_at for row in opened.reminders("t1")]
        assert sent == [moment(270)] * 5 + [moment(301), None, None, None]
    assert {table: rows(path, table) for table in before} == before


@pytest.mark.parametrize("case", ["created", "reopened", "mixed"])
def test_slots_already_past_when_planned_are_not_counted_as_missed(
    tmp_path, monkeypatch, case
) -> None:
    from docket import reminders

    notifier = FakeNotifier()
    fixed_ids(monkeypatch, "k1")
    with Store(tmp_path / "docket.sqlite3") as opened:
        if case == "created":
            fixed_times(monkeypatch, at(0), at(0))
            create(opened, deadline=due_in(-180))
            expected = ("This is late.", ("r1", "r2", "r3", "r4", "r5"))
        elif case == "reopened":
            fixed_times(monkeypatch, at(0), at(1), at(270), at(270))
            create(opened, deadline=due_in(120))
            core.change_state(opened, "t1", "done", actor="owner")
            core.change_state(opened, "t1", "reopen", actor="owner")
            expected = ("This is late.", ("r10", "r11", "r12", "r13"))
        else:
            fixed_times(monkeypatch, at(0), at(330))
            create(opened, deadline=due_in(-180))
            expected = (
                "Missed while docket was offline: 2 reminders.\nThis is late.",
                ("r1", "r2", "r3", "r4", "r5", "r6", "r7"),
            )
        assert reminders.send_due(opened, notifier) == 1
        assert [(notice.key, notice.text) for notice in notifier.delivered] == [("k1", expected[0])]
        assert opened.posts("t1")[0].reminder_ids == expected[1]


def test_a_failed_send_is_retried_next_pass_with_the_same_key(tmp_path, monkeypatch) -> None:
    from docket import reminders

    fixed_times(monkeypatch, at(0), at(0), at(0.5))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        create(opened, deadline=due_in(30))
        assert reminders.send_due(opened, notifier) == 0
        post = opened.posts("t1")[0]
        assert (post.claimed_at, post.sent_at) == (None, None)
        assert reminders.send_due(opened, notifier) == 1
        post = opened.posts("t1")[0]
        assert (post.queued_at, post.claimed_at, post.sent_at) == (
            moment(0),
            moment(0.5),
            moment(0.5),
        )
    assert [notice.key for notice in notifier.attempts] == ["k1", "k1"]
    assert notifier.delivered == [Notice("k1", "t1", "Synthetic task", "This is due soon.")]


@pytest.mark.parametrize("crash", ["before-send", "after-send", "unexpected-error"])
def test_a_crash_mid_send_resends_once_with_the_same_key_after_five_minutes(
    tmp_path, monkeypatch, crash
) -> None:
    from docket import reminders

    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(5), at(5.5), at(6))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    raised = {"before-send": Killed, "after-send": Killed, "unexpected-error": SyntheticBug}[crash]
    if crash == "after-send":
        notifier.after = Killed()
    else:
        notifier.before = raised()
    with Store(path) as opened:
        create(opened, deadline=due_in(30))
        with pytest.raises(raised):
            reminders.send_due(opened, notifier)
    with Store(path) as restarted:
        assert restarted.posts("t1")[0].claimed_at == moment(0)
        assert [reminders.send_due(restarted, notifier) for _ in range(3)] == [0, 1, 0]
        assert restarted.posts("t1")[0].sent_at == moment(5.5)
    assert [notice.key for notice in notifier.attempts] == ["k1", "k1"]
    assert notifier.delivered == [Notice("k1", "t1", "Synthetic task", "This is due soon.")]


def test_a_second_loop_during_a_send_sends_nothing(tmp_path, monkeypatch) -> None:
    from docket import reminders

    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(0), at(0.5))
    fixed_ids(monkeypatch, "k1")
    first, second = FakeNotifier(), FakeNotifier()
    inner: list[int] = []
    with Store(path) as one, Store(path) as two:
        create(one, deadline=due_in(30))
        first.during = lambda: inner.append(reminders.send_due(two, second))
        assert reminders.send_due(one, first) == 1
        assert reminders.send_due(two, second) == 0
    assert inner == [0]
    assert second.attempts == []
    assert [notice.key for notice in first.delivered] == ["k1"]


def test_two_processes_send_each_due_reminder_once(tmp_path, monkeypatch) -> None:
    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(0))
    with Store(path) as opened:
        for title in ("Synthetic one", "Synthetic two", "Synthetic three"):
            create(opened, title, deadline=due_in(30))
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    messages = ctx.Queue()
    workers = [
        ctx.Process(target=send_in_child, args=(str(path), at(0), prefix, start, messages))
        for prefix in ("a", "b")
    ]
    try:
        for worker in workers:
            worker.start()
        start.set()
        results = sorted([messages.get(timeout=15), messages.get(timeout=15)])
        assert [result[:2] for result in results] == [("ok", 0), ("ok", 3)]
        assert results[0][2] == []
        assert sorted(results[1][2]) in (["a1", "a2", "a3"], ["b1", "b2", "b3"])
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)
        messages.close()
        messages.join_thread()
    with Store(path) as reopened:
        posts = [post for task in ("t1", "t2", "t3") for post in reopened.posts(task)]
        assert [(post.id, post.sent_at) for post in posts] == [
            ("p1", moment(0)),
            ("p2", moment(0)),
            ("p3", moment(0)),
        ]


@pytest.mark.parametrize("action", ["done", "cancel"])
def test_a_task_ended_after_a_crashed_send_is_not_resent(tmp_path, monkeypatch, action) -> None:
    from docket import reminders

    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(1), at(6), at(200))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.before = Killed()
    with Store(path) as opened:
        create(opened, deadline=due_in(30))
        with pytest.raises(Killed):
            reminders.send_due(opened, notifier)
    with Store(path) as restarted:
        core.change_state(restarted, "t1", action, actor="owner")
        assert [reminders.send_due(restarted, notifier) for _ in range(2)] == [0, 0]
        assert restarted.posts("t1")[0].sent_at is None
        assert all(row.voided_at == moment(1) for row in restarted.reminders("t1"))
    assert len(notifier.attempts) == 1
    assert notifier.delivered == []
