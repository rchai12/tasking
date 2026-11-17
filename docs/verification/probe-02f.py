"""Finite identity/retry matrix; synthetic ASGI requests and temporary databases only."""

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
BODY = {
    "source": "email",
    "title": "Synthetic probe task",
    "deadline": None,
    "provider": "gmail",
    "message_id": "probe/1",
    "link": "https://mail.example/probe/1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": "probe/2",
    "link": "https://mail.example/probe/2",
}
# An agent key exists first. HTTP may neither replay it nor create an agent task.
CASES = (
    ("agent", "task", "shared", 422, {"error": "invalid_client"}),
    ("other", "task", "shared", 422, {"error": "invalid_client"}),
    ("email", "task", "shared", 201, {"id": "t2"}),
    ("agent", "task", "shared", 422, {"error": "invalid_client"}),
    ("email", "task", "shared", 200, {"id": "t2"}),
    ("other", "link", "follow", 422, {"error": "invalid_client"}),
    ("email", "link", "follow", 201, {"id": "l1"}),
    ("agent", "link", "follow", 422, {"error": "invalid_client"}),
    ("email", "link", "follow", 200, {"id": "l1"}),
)
assert [case[3] for case in CASES].count(422) == 5
assert [case[3] for case in CASES].count(201) == 2
assert [case[3] for case in CASES].count(200) == 2
assert {case[0] for case in CASES} == {"email", "agent", "other"}
print("oracle: ok")


def check(label, action):
    global FAILURES
    try:
        action()
    except Exception as error:
        FAILURES += 1
        print(f"{label}: FAIL ({type(error).__name__})")
    else:
        print(f"{label}: ok")


def matrix():
    from fastapi.testclient import TestClient

    from docket import core
    from docket.store import Store
    from docket.web import create_app

    for order in (("email", "agent", "other"), ("other", "agent", "email")):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "docket.sqlite3"
            with patch("docket.clock.now", return_value=datetime(2026, 11, 17, 14, tzinfo=UTC)):
                with Store(path) as store:
                    made = core.create_task_once(
                        store,
                        client="agent",
                        key="shared",
                        request={"title": "Agent probe"},
                        title="Agent probe",
                        source="agent",
                    )
                    assert made.task.id == "t1"
                tokens = {f"synthetic-{name}": name for name in order}
                app = create_app(open_store=lambda path=path: Store(path), tokens=tokens, port=8767)
                with TestClient(app, base_url="http://127.0.0.1:8767") as client:
                    for step, (identity, kind, key, status, result) in enumerate(CASES):
                        response = client.post(
                            "/tasks" if kind == "task" else "/tasks/t2/links",
                            json=BODY if kind == "task" else LINK,
                            headers={
                                "Authorization": f"Bearer synthetic-{identity}",
                                "Idempotency-Key": key,
                            },
                        )
                        found = (response.status_code, response.json())
                        if found != (status, result):
                            print(
                                f"  step {step}, {identity} {kind}: "
                                f"expected {(status, result)}, found {found}"
                            )
                            raise AssertionError
                        assert response.headers["cache-control"] == "no-store"
                # Reopen the file: rejected identities left no retry keys or extra rows.
                with Store(path) as store:
                    assert [(t.id, t.source) for t in store.tasks()] == [
                        ("t1", "agent"),
                        ("t2", "email"),
                    ]
                    assert [row.id for row in store.links("t2")] == ["l1"]
                    assert len(store.audit("t1")) == 1
                    assert len(store.audit("t2")) == 1
                    assert store.request_key("agent", "shared").task_id == "t1"
                    assert store.request_key("email", "shared").task_id == "t2"
                    assert store.request_key("agent", "follow") is None
                    assert store.request_key("other", "shared") is None
                    assert store.request_key("other", "follow") is None


def required_identity():
    import inspect

    from docket.intake import accept_link, accept_task

    for function in (accept_task, accept_link):
        parameter = inspect.signature(function).parameters["client"]
        assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


if not ORACLE_ONLY:
    check("identity and retry matrix survives reopen in both token orders", matrix)
    check("intake never supplies an implicit identity", required_identity)
print(f"FAILURES {FAILURES}")
sys.exit(bool(FAILURES))
