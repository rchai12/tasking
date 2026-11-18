"""Offline properties for the shared creation path and retry representation."""

import argparse
import ast
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from docket import clock, core
from docket.store import Store

AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
CASES = [
    ({"z": None, "a": "Café 雪"}, '{"a":"Café 雪","z":null}'),
    ({"a": [True, False, None]}, '{"a":[true,false,null]}'),
    ({"z": {"b": 2, "a": 1}}, '{"z":{"a":1,"b":2}}'),
]


def oracle() -> None:
    for value, expected in CASES:
        assert (
            json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) == expected
        )
    assert '{"x":true}' != '{"x":1}'
    assert '{"x":null}' != "{}"


def codec(_root: Path) -> None:
    from docket.serialization import canonical_json

    for value, expected in CASES:
        assert canonical_json(value) == expected, "canonical bytes changed"


def shared(_root: Path) -> None:
    tree = ast.parse(inspect.getsource(core))
    inserts = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "insert_task"
    ]
    assert len(inserts) == 1, f"expected one core insertion site; got {len(inserts)}"


def persistence(root: Path) -> None:
    path = root / "docket.sqlite3"
    with patch.object(clock, "now", return_value=AT):
        with Store(path) as store:
            for key in ("one", "two", "three"):
                core.create_task_once(
                    store,
                    client="agent",
                    key=key,
                    request={"z": None, "a": "雪"},
                    title="Synthetic task",
                    source="agent",
                )
            core.change_state(store, "t2", "done", actor="owner")
        with Store(path) as store:
            before = store.tasks(), [store.audit(task) for task in ("t1", "t2", "t3")]
            for key, task_id, state in (
                ("one", "t1", "open"),
                ("two", "t2", "done"),
                ("three", "t3", "open"),
            ):
                result = core.create_task_once(
                    store,
                    client="agent",
                    key=key,
                    request={"a": "雪", "z": None},
                    title="Synthetic task",
                    source="agent",
                )
                assert (result.task.id, result.task.state, result.changed) == (
                    task_id,
                    state,
                    False,
                )
                try:
                    core.create_task_once(
                        store,
                        client="agent",
                        key=key,
                        request={"a": "雪"},
                        title="Synthetic task",
                        source="agent",
                    )
                except core.CoreError as error:
                    assert error.code == "key_reused"
                else:
                    raise AssertionError(f"changed body accepted for {key}")
            assert (store.tasks(), [store.audit(task) for task in ("t1", "t2", "t3")]) == before


class InterruptedWrite(Exception):
    pass


def rollback(root: Path) -> None:
    path = root / "docket.sqlite3"
    original = Store.insert_request_key

    def interrupt(self, **fields):
        original(self, **fields)
        raise InterruptedWrite

    with patch.object(clock, "now", return_value=AT):
        with Store(path) as store:
            with patch.object(Store, "insert_request_key", interrupt):
                try:
                    core.create_task_once(
                        store,
                        client="agent",
                        key="one",
                        request={},
                        title="Synthetic task",
                        source="agent",
                    )
                except InterruptedWrite:
                    pass
                else:
                    raise AssertionError("forced interruption not reached")
        with Store(path) as store:
            assert store.tasks() == []
            assert store.audit("t1") == []
            assert store.request_key("agent", "one") is None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("canonical oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("canonical codec", codec),
            ("shared creation", shared),
            ("restart replay", persistence),
            ("atomic rollback", rollback),
        ):
            with TemporaryDirectory() as folder:
                try:
                    check(Path(folder))
                    print(f"{name} ok")
                except Exception as error:
                    print(f"{name} FAIL: {type(error).__name__}: {error}")
                    failures += 1
    print(f"FAILURES {failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
