"""Synthetic upgrade and reference-policy properties; no network, settings or Keychain."""

import sqlite3
import sys
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FAILURES = 0
LEGACY = (
    ("message_id", "x" * 513),
    ("link", "x" * 2049),
    ("message_id", "unsafe\x7fcontrol"),
    ("link", "unsafe\u2060format"),
    ("message_id", "unsafe\u2028line"),
    ("link", "unsafe\u2029paragraph"),
)
assert len(LEGACY) == 6
assert unicodedata.category("\x7f") == "Cc"
assert unicodedata.category("\u2060") == "Cf"
assert unicodedata.category("\u2028") == "Zl"
assert unicodedata.category("\u2029") == "Zp"
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


def policy():
    from docket.references import valid_reference

    for value, cap, expected in (
        ("é" * 512, 512, True),
        ("é" * 513, 512, False),
        (" x ", 512, True),
        ("x" * 2048, 2048, True),
        ("x" * 2049, 2048, False),
        ("a\tbad", 512, False),
        ("a\x7fbad", 512, False),
        ("a\u2060bad", 512, False),
        ("a\u2028bad", 512, False),
        ("a\u2029bad", 512, False),
    ):
        assert valid_reference(value, cap) is expected


def upgrade():
    from docket.intake import accept_link, accept_task
    from docket.store import Store
    from tests.reference_cases import BODY, LINK, snapshot, version_two

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "docket.sqlite3"
        version_two(path)
        before = snapshot(path)
        with Store(path) as opened:
            assert snapshot(path) == before
            with patch("docket.clock.now", return_value=datetime(2026, 11, 17, 14, tzinfo=UTC)):
                task = accept_task(opened, client="email", key="task-key", body=BODY)
                link = accept_link(opened, "t1", client="email", key="link-key", body=LINK)
                assert (task.status, task.body) == (200, {"id": "t1"})
                assert (link.status, link.body) == (200, {"id": "l1"})
            assert snapshot(path) == before
        with Store(path):
            assert snapshot(path) == before
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA user_version").fetchone() == (3,)
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def invalid_upgrade():
    from docket.store import Store, StoreError
    from tests.reference_cases import snapshot, version_two

    for table, identifier in (("tasks", "t1"), ("links", "l1")):
        for field, value in LEGACY:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "docket.sqlite3"
                version_two(path)
                with sqlite3.connect(path) as db:
                    db.execute(f"UPDATE {table} SET {field}=? WHERE number=1", (value,))
                before = snapshot(path)
                try:
                    Store(path).close()
                except StoreError as error:
                    assert str(error) == f"invalid stored reference: {identifier} {field}"
                else:
                    print(f"  {identifier} {field}: expected refusal; upgrade succeeded")
                    raise AssertionError
                assert snapshot(path) == before
                with sqlite3.connect(path) as db:
                    assert db.execute("PRAGMA user_version").fetchone() == (2,)


if "--oracle-only" not in sys.argv:
    check("reference policy covers Unicode caps and all forbidden categories", policy)
    check("valid populated upgrade preserves rows and retry answers across reopen", upgrade)
    check(
        "12 invalid legacy cases refuse with only ID and field; data stays unchanged",
        invalid_upgrade,
    )
print(f"FAILURES {FAILURES}")
sys.exit(bool(FAILURES))
