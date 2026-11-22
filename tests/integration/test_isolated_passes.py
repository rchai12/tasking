"""Phase 5e: one bad row silences only its task, and an emptied digest is never sent."""

import dataclasses
from datetime import UTC, date, datetime, timedelta

import pytest

from docket import clock, core, ids, reminders
from docket.deadlines import Deadline
from docket.store import Store
from tests.loop_cases import AT, T0, ZONE, text
from tests.notifier_cases import FakeNotifier, SyntheticBug

MARK = "Phase 5e given test: remove this marker when each task's pass is isolated"
BEFORE = "Are you working on this?"
# A naive time: the store refuses to decode it.
NAIVE = "2026-11-20T16:00:00"


class Clock:
    def __init__(self) -> None:
        self.at = T0

    def now(self) -> datetime:
        return self.at


@pytest.fixture
def moment(monkeypatch: pytest.MonkeyPatch) -> Clock:
    keys = iter(f"k{n}" for n in range(1, 100))
    held = Clock()
    monkeypatch.setattr(clock, "now", held.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))
    return held


def task_due_in(opened: Store, minutes: int) -> str:
    deadline = Deadline(T0 + timedelta(minutes=minutes), "UTC", True)
    return core.create_task(
        opened, title="Synthetic pass task", source="owner", deadline=deadline
    ).id


def one_pass(opened: Store, notifier: FakeNotifier) -> reminders.PassResult:
    return reminders.run_pass(opened, notifier, zone=ZONE, at=AT)


def instant(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds")


def plant_reminder(opened: Store, task: int, *, fire_at: datetime, planned_at: str, claimed=None):
    """Insert a reminder row directly; the plan columns cannot be changed once written."""
    return opened._connection.execute(
        "INSERT INTO reminders (task, kind, fire_at, planned_at, claimed_at) "
        "VALUES (?, 'before', ?, ?, ?)",
        (task, instant(fire_at), planned_at, claimed),
    ).lastrowid


def plant_post(opened: Store, task: int) -> None:
    """A claimable post with an undecodable queued time, holding one live reminder."""
    reminder = plant_reminder(
        opened,
        task,
        fire_at=T0 + timedelta(days=1),
        planned_at=instant(T0),
        claimed=instant(T0),
    )
    post = opened._connection.execute(
        "INSERT INTO posts (task, key, kind, missed, queued_at) "
        "VALUES (?, 'planted-key-5e', 'before', 0, ?)",
        (task, NAIVE),
    ).lastrowid
    opened._connection.execute(
        "INSERT INTO post_reminders (post, reminder) VALUES (?, ?)", (post, reminder)
    )


def count(opened: Store, sql: str) -> int:
    return opened._connection.execute(sql).fetchone()[0]


def test_a_bad_reminder_row_silences_only_its_task(tmp_path, moment: Clock) -> None:
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        for _ in range(3):
            task_due_in(opened, 120)
        bad = plant_reminder(opened, 2, fire_at=T0 + timedelta(hours=1), planned_at=NAIVE)
        moment.at = T0 + timedelta(hours=1)
        assert one_pass(opened, notifier) == reminders.PassResult(2, False, (), ("t2",))
        assert [text(sent) for sent in notifier.delivered] == [
            ("k1", "t1", BEFORE),
            ("k2", "t3", BEFORE),
        ]
        assert count(opened, "SELECT count(*) FROM posts WHERE task = 2") == 0
        assert count(opened, "SELECT count(*) FROM reminders WHERE claimed_at IS NOT NULL") == 2
        opened._connection.execute(
            "UPDATE reminders SET voided_at = ? WHERE number = ?", (instant(T0), bad)
        )
        moment.at += timedelta(seconds=30)
        assert one_pass(opened, notifier) == reminders.PassResult(1, False, (), ())
        assert text(notifier.delivered[-1]) == ("k3", "t2", BEFORE)


def test_a_bad_task_row_silences_only_its_task(tmp_path, moment: Clock) -> None:
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 120)
        task_due_in(opened, 120)
        opened._connection.execute("UPDATE tasks SET created_at = ? WHERE number = 1", (NAIVE,))
        moment.at = T0 + timedelta(hours=1)
        # The digest still reads every open task, so its half fails alone (out of scope).
        assert one_pass(opened, notifier) == reminders.PassResult(1, False, ("digest",), ("t1",))
        # t1's retry key was drawn before its transaction rolled back, and is never stored.
        assert [text(sent) for sent in notifier.delivered] == [("k2", "t2", BEFORE)]
        assert count(opened, "SELECT count(*) FROM posts WHERE task = 1") == 0


def test_a_bad_post_row_silences_only_its_task(tmp_path, moment: Clock) -> None:
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 120)
        task_due_in(opened, 120)
        plant_post(opened, 1)
        moment.at = T0 + timedelta(hours=1)
        assert one_pass(opened, notifier) == reminders.PassResult(1, False, (), ("t1",))
        assert [text(sent) for sent in notifier.delivered] == [("k2", "t2", BEFORE)]
        assert count(opened, "SELECT count(*) FROM posts WHERE task = 1") == 1
        assert count(opened, "SELECT count(*) FROM posts WHERE claimed_at IS NOT NULL") == 1


def test_an_unexpected_error_still_fails_the_whole_half(tmp_path, moment, monkeypatch) -> None:
    def broken(self, at, *, task_id=None):
        raise SyntheticBug()

    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 120)
        moment.at = T0 + timedelta(hours=1)
        monkeypatch.setattr(Store, "due_reminders", broken)
        assert one_pass(opened, notifier) == reminders.PassResult(0, False, ("reminders",), ())
        assert notifier.delivered == []


def test_the_send_order_stays_by_post_number(tmp_path, moment: Clock) -> None:
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 150)
        task_due_in(opened, 120)
        moment.at = T0 + timedelta(hours=1)
        notifier.fail = 1
        reminders.send_due(opened, notifier)
        moment.at = T0 + timedelta(minutes=90)
        assert reminders.send_due(opened, notifier) == 2
        assert [text(sent) for sent in notifier.delivered] == [
            ("k1", "t2", BEFORE),
            ("k2", "t1", BEFORE),
        ]


def test_pending_task_ids_read_no_row_times(tmp_path, moment: Clock) -> None:
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 120)
        task_due_in(opened, 300)
        task_due_in(opened, 90)
        moment.at = T0 + timedelta(minutes=30)
        early = moment.at - timedelta(minutes=5)
        assert opened.pending_task_ids(at=moment.at, stale_before=early) == ["t3"]
        notifier.fail = 1
        reminders.send_due(opened, notifier)
        moment.at = T0 + timedelta(hours=1)
        plant_reminder(opened, 1, fire_at=T0 + timedelta(hours=1), planned_at=NAIVE)
        stale = moment.at - timedelta(minutes=reminders.CLAIM_MINUTES)
        assert opened.pending_task_ids(at=moment.at, stale_before=stale) == ["t1", "t3"]


def test_due_reminders_and_claims_narrow_to_one_task(tmp_path, moment: Clock) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        task_due_in(opened, 120)
        task_due_in(opened, 120)
        moment.at = T0 + timedelta(hours=1)
        due = opened.due_reminders(moment.at, task_id="t2")
        assert [(row.id, row.task_id, row.kind) for row in due] == [("r10", "t2", "before")]
        with opened.transaction():
            for task_id in ("t1", "t2"):
                rows = opened.due_reminders(moment.at, task_id=task_id)
                opened.queue_post(
                    task_id,
                    tuple(row.id for row in rows),
                    key=f"key-{task_id}",
                    kind="before",
                    missed=0,
                    at=moment.at,
                )
            claimed = opened.claim_posts(
                at=moment.at, stale_before=moment.at - timedelta(minutes=5), task_id="t2"
            )
        assert [(post.id, post.task_id) for post in claimed] == [("p2", "t2")]
        assert count(opened, "SELECT count(*) FROM posts WHERE claimed_at IS NOT NULL") == 1


def test_an_emptied_digest_is_marked_sent_without_a_send(tmp_path, monkeypatch) -> None:
    created = datetime(2026, 11, 19, 17, tzinfo=UTC)
    held = Clock()
    held.at = created
    monkeypatch.setattr(clock, "now", held.now)
    monkeypatch.setattr(ids, "new_id", lambda: "digest-key-5e")
    claim = Store.claim_digest

    def claim_then_end(self, *args, **kwargs):
        found = claim(self, *args, **kwargs)
        self._connection.execute("UPDATE tasks SET state = 'done' WHERE number = 1")
        return found

    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        deadline = Deadline(datetime(2026, 11, 19, 18, tzinfo=UTC), "UTC", True)
        core.create_task(opened, title="Synthetic overdue task", source="owner", deadline=deadline)
        held.at = T0
        monkeypatch.setattr(Store, "claim_digest", claim_then_end)
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is False
        assert notifier.attempts == []
        assert opened.digest(date(2026, 11, 20)).sent_at == T0
        monkeypatch.undo()
        monkeypatch.setattr(clock, "now", held.now)
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is False
        assert notifier.attempts == []


def test_a_pass_result_names_no_skipped_task_by_default() -> None:
    assert [field.name for field in dataclasses.fields(reminders.PassResult)] == [
        "sent",
        "digest",
        "failed",
        "skipped",
    ]
    assert reminders.PassResult(1, False, ()).skipped == ()
    assert reminders.PassResult(0, False, (), ("t4",)).skipped == ("t4",)
