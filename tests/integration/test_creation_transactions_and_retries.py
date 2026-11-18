import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.deadlines import Deadline, WorkTime
from docket.store import Store
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
REQUEST = {"z": None, "a": {"y": "雪", "x": True}}
DUE = Deadline(datetime(2026, 11, 20, 22, tzinfo=UTC), "America/New_York", True)
LATE = WorkTime(datetime(2026, 11, 20, 22, tzinfo=UTC), 60, "America/New_York")
EMAIL = {
    "provider": "gmail",
    "message_id": "synthetic/雪",
    "link": "https://mail.example/雪",
}


def test_one_transaction_holds_creation_and_the_helper_does_not_nest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW)
    depth = 0
    entered: list[str] = []
    writes: list[str] = []
    original = Store.transaction

    @contextmanager
    def tracked(self: Store):
        nonlocal depth
        assert depth == 0
        depth += 1
        entered.append("transaction")
        try:
            with original(self):
                yield
        finally:
            depth -= 1

    def watch(label: str, method):
        def wrapped(self: Store, *args: object, **kwargs: object):
            assert depth == 1
            writes.append(label)
            return method(self, *args, **kwargs)

        return wrapped

    monkeypatch.setattr(Store, "transaction", tracked)
    monkeypatch.setattr(Store, "insert_task", watch("task", Store.insert_task))
    monkeypatch.setattr(Store, "append_audit", watch("audit", Store.append_audit))
    monkeypatch.setattr(Store, "insert_request_key", watch("key", Store.insert_request_key))
    with Store(tmp_path / "docket.sqlite3") as store:
        entered.clear()
        writes.clear()
        core.create_task(store, title="Synthetic plain task", source="owner")
        assert entered == ["transaction"]
        assert writes == ["task", "audit"]
        entered.clear()
        writes.clear()
        made = core.create_task_once(
            store,
            client="agent",
            key="synthetic-create",
            request=REQUEST,
            title="Synthetic keyed task",
            source="agent",
        )
        assert made.changed is True
        assert entered == ["transaction"]
        assert writes == ["task", "audit", "key"]
        entered.clear()
        writes.clear()
        again = core.create_task_once(
            store,
            client="agent",
            key="synthetic-create",
            request={"a": {"x": True, "y": "雪"}, "z": None},
            title="Synthetic keyed task",
            source="agent",
        )
        assert (again.changed, again.task.id) == (False, made.task.id)
        assert entered == ["transaction"]
        assert writes == []
        entered.clear()
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.create_task_once(
                store,
                client="agent",
                key="synthetic-create",
                request={"a": {"x": 1, "y": "雪"}, "z": None},
                title="Synthetic keyed task",
                source="agent",
            )
        assert entered == ["transaction"]
        assert writes == []
        assert [task.id for task in store.tasks()] == ["t1", made.task.id]


@pytest.mark.parametrize(
    ("client", "key", "title", "source", "code"),
    [
        (["email"], "", "  ", "email", "invalid_client"),
        ("agent", "", "  ", "agent", "invalid_key"),
        ("agent", "synthetic-create", "  ", "camera", "invalid_title"),
        ("agent", "synthetic-create", "Synthetic task", "email", "invalid_source"),
    ],
    ids=["client", "key", "title", "source"],
)
def test_refusals_keep_their_order_and_read_no_clock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: object,
    key: object,
    title: object,
    source: str,
    code: str,
) -> None:
    fixed_times(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        with pytest.raises(core.CoreError, match=f"^{code}$"):
            core.create_task_once(
                store,
                client=client,
                key=key,
                request=REQUEST,
                title=title,
                source=source,
                deadline=DUE,
                work=LATE,
                provider=None,
                message_id="synthetic/missing",
                link="https://mail.example/missing",
            )
        assert store.tasks() == []
        assert store.request_key("agent", "synthetic-create") is None
        assert store.request_key("email", "synthetic-create") is None


def test_a_task_key_and_a_link_key_cannot_cross(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        made = core.create_task_once(
            store,
            client="email",
            key="synthetic-task",
            request={**REQUEST, **EMAIL, "source": "email", "title": "Synthetic email task"},
            title="Synthetic email task",
            source="email",
            **EMAIL,
        )
        core.add_link(
            store,
            made.task.id,
            client="email",
            key="synthetic-link",
            request=EMAIL,
            **EMAIL,
        )
        before = _rows(path)
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.create_task_once(
                store,
                client="email",
                key="synthetic-link",
                request=EMAIL,
                title="Synthetic email task",
                source="email",
                **EMAIL,
            )
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.add_link(
                store,
                made.task.id,
                client="email",
                key="synthetic-task",
                request=EMAIL,
                **EMAIL,
            )
        assert store.task("t1").state == "open"
        assert len(store.audit("t1")) == 1
        assert [item.id for item in store.links("t1")] == ["l1"]
        assert _rows(path) == before


def test_reopening_replays_a_stored_unicode_key_without_rewriting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        task = core.create_task(store, title="Synthetic stored task", source="agent")
        with store.transaction():
            store.insert_request_key(
                client="agent",
                key="synthetic-stored",
                request=REQUEST,
                task_id=task.id,
                link_id=None,
                at=AT,
            )
    stored = _rows(path)
    with Store(path) as store:
        outcome = core.create_task_once(
            store,
            client="agent",
            key="synthetic-stored",
            request={"a": {"x": True, "y": "雪"}, "z": None},
            title="Synthetic stored task",
            source="agent",
        )
        assert (outcome.changed, outcome.task.id, outcome.task.state) == (False, "t1", "open")
        assert len(store.audit("t1")) == 1
        assert [item.id for item in store.tasks()] == ["t1"]
    assert _rows(path) == stored


def _rows(path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(path) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("tasks", "audit_log", "links", "request_keys")
        }
