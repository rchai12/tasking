from datetime import datetime

import pytest

from docket import core
from docket.notifier import Notice
from docket.store import Store, StoreError
from tests.notifier_cases import FakeNotifier, Killed, at, due_in, work_in
from tests.support import fixed_ids, fixed_times


def moment(minutes: float) -> datetime:
    return datetime.fromisoformat(at(minutes))


def test_nothing_due_uses_no_id_and_a_later_pass_claims_the_stale_post(
    tmp_path, monkeypatch
) -> None:
    from docket import reminders

    fixed_times(monkeypatch, at(0), at(0))
    fixed_ids(monkeypatch)
    notifier = FakeNotifier()
    with Store(tmp_path / "idle.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=due_in(24 * 60))
        assert reminders.send_due(opened, notifier) == 0
    assert notifier.attempts == []

    path = tmp_path / "stale.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(6))
    fixed_ids(monkeypatch, "k1")
    crashed = FakeNotifier()
    crashed.before = Killed()
    with Store(path) as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=due_in(30))
        with pytest.raises(Killed):
            reminders.send_due(opened, crashed)
    resent = FakeNotifier()
    with Store(path) as restarted:
        assert reminders.send_due(restarted, resent) == 1
        post = restarted.posts("t1")[0]
        assert (post.key, post.claimed_at, post.sent_at) == ("k1", moment(6), moment(6))
    assert resent.delivered == [Notice("k1", "t1", "Synthetic task", "This is due soon.")]


def test_a_partly_voided_post_keeps_its_kind_and_marks_only_live_reminders(
    tmp_path, monkeypatch
) -> None:
    from docket import reminders

    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, at(0), at(0), at(1), at(6))
    fixed_ids(monkeypatch, "k1")
    crashed = FakeNotifier()
    crashed.before = Killed()
    with Store(path) as opened:
        core.create_task(
            opened,
            title="Synthetic task",
            source="owner",
            deadline=due_in(-10),
            work=work_in(-60),
        )
        with pytest.raises(Killed):
            reminders.send_due(opened, crashed)
        queued = opened.posts("t1")[0]
    with Store(path) as restarted:
        core.edit_task(restarted, "t1", actor="owner", deadline=None)
        assert reminders.send_due(restarted, FakeNotifier()) == 1
        post = restarted.posts("t1")[0]
        assert (post.kind, post.missed, post.key) == (queued.kind, queued.missed, "k1")
        assert [(row.id, row.sent_at, row.voided_at) for row in restarted.reminders("t1")] == [
            ("r1", moment(6), None),
            ("r2", None, moment(1)),
            ("r3", None, moment(1)),
            ("r4", None, moment(1)),
            ("r5", None, moment(1)),
            ("r6", None, moment(1)),
            ("r7", None, moment(1)),
            ("r8", None, moment(1)),
            ("r9", None, moment(1)),
        ]


def test_a_notifier_error_on_the_first_post_still_sends_the_second(tmp_path, monkeypatch) -> None:
    from docket import reminders

    fixed_times(monkeypatch, at(0), at(0), at(0))
    fixed_ids(monkeypatch, "k1", "k2")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic one", source="owner", deadline=due_in(30))
        core.create_task(opened, title="Synthetic two", source="owner", deadline=due_in(30))
        assert reminders.send_due(opened, notifier) == 1
        assert opened.posts("t1")[0].sent_at is None
        assert opened.posts("t2")[0].sent_at == moment(0)
    assert notifier.delivered == [Notice("k2", "t2", "Synthetic two", "This is due soon.")]


def test_a_resent_notice_uses_the_title_at_resend(tmp_path, monkeypatch) -> None:
    from docket import reminders

    fixed_times(monkeypatch, at(0), at(0), at(1), at(1.5))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=due_in(30))
        assert reminders.send_due(opened, notifier) == 0
        core.edit_task(opened, "t1", actor="owner", title="Synthetic renamed")
        assert reminders.send_due(opened, notifier) == 1
    assert notifier.delivered == [Notice("k1", "t1", "Synthetic renamed", "This is due soon.")]


def test_marking_a_post_with_no_reminders_sets_only_the_post(tmp_path) -> None:
    from tests.notifier_cases import NOW

    later = NOW.replace(minute=15)
    with Store(tmp_path / "docket.sqlite3") as opened:
        with opened.transaction():
            opened.insert_task(
                title="Synthetic task",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=NOW,
            )
        opened._connection.execute(
            "INSERT INTO posts (task, key, kind, missed, queued_at) VALUES (1, 'k1', 'due', 0, ?)",
            (NOW.isoformat(),),
        )
        with opened.transaction():
            opened.mark_post_sent("p1", at=later)
        post = opened.posts("t1")[0]
        assert (post.sent_at, post.reminder_ids) == (later, ())


def test_a_missing_queued_time_is_an_invalid_stored_post_time(tmp_path) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        opened._connection.execute(
            "CREATE TEMP TABLE post_times ("
            "number, task, key, kind, missed, queued_at, claimed_at, sent_at)"
        )
        opened._connection.execute(
            "INSERT INTO post_times VALUES (1, 1, 'k1', 'due', 0, NULL, NULL, NULL)"
        )
        row = opened._connection.execute("SELECT * FROM post_times").fetchone()
        with pytest.raises(StoreError, match="invalid stored post time: p1"):
            opened._post_from(row)
