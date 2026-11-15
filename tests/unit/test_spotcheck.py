from pathlib import Path

import pytest

from docket.spotcheck import MATCH_MESSAGE, SpotError, mutate, spot_check, verdict

MODULE = 'HOST = "127.0.0.1"\nPORT = 8767\n'
ASSERTION = """\
      {'host': '0.0.0.0'} != {'host': '127.0.0.1'}
      Use -v to get more diff
/work/tests/unit/test_x.py:3: AssertionError: assert {'host': '0.0.0.0'} == {'host': '127.0.0.1'}
=========================== short test summary info ============================
FAILED tests/unit/test_x.py::test_eq - AssertionError: assert {'host': '0.0.0.0'} == {'h...
1 failed in 0.00s
"""
RAISED = """\
=================================== FAILURES ===================================
E   KeyError: 'l1'
/work/tests/unit/test_x.py:5: KeyError: 'l1'
=========================== short test summary info ============================
FAILED tests/unit/test_x.py::test_raises - KeyError: 'l1'
1 failed in 0.00s
"""
COLLECTION = """\
    import nope
E   ModuleNotFoundError: No module named 'nope'
=========================== short test summary info ============================
ERROR tests/unit/test_bad.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.03s
"""
LONG = "/work/t.py:9: AssertionError: assert " + "x" * 200 + "\n1 failed in 0.01s\n"


@pytest.mark.parametrize(
    ("old", "found"),
    [("8768", 0), ('"', 2)],
    ids=["missing", "twice"],
)
def test_the_old_text_must_match_once(old: str, found: int) -> None:
    assert mutate(MODULE, '"127.0.0.1"', '"0.0.0.0"') == 'HOST = "0.0.0.0"\nPORT = 8767\n'
    with pytest.raises(SpotError) as raised:
        mutate(MODULE, old, "x")
    assert str(raised.value) == f"{MATCH_MESSAGE}: found {found}"
    assert MATCH_MESSAGE == "the old text must match exactly once"


@pytest.mark.parametrize(
    ("output", "code", "expected"),
    [
        ("1 passed in 0.01s\n", 0, "passes"),
        (
            ASSERTION,
            1,
            "fails: AssertionError: assert {'host': '0.0.0.0'} == {'host': '127.0.0.1'}",
        ),
        (RAISED, 1, "fails: KeyError: 'l1'"),
        (
            "E   Failed: DID NOT RAISE ValueError\n1 failed\n",
            1,
            "fails: Failed: DID NOT RAISE ValueError",
        ),
        ("1 failed in 0.01s\n", 1, "fails"),
        (LONG, 1, "fails: AssertionError: assert " + "x" * 117 + "..."),
        (COLLECTION, 2, "error: ModuleNotFoundError: No module named 'nope'"),
        ("1 error in 0.01s\n", 2, "error: collection"),
        ("ERROR: not found: /work/t.py::test_missing\nno tests ran in 0.00s\n", 4, "no test ran"),
        ("no tests ran in 0.00s\n", 5, "no test ran"),
        ("timed out", 124, "error: exit 124"),
    ],
    ids=[
        "passes",
        "assertion",
        "raised",
        "did-not-raise",
        "no-detail",
        "long",
        "collection",
        "collection-no-detail",
        "unknown-test",
        "none-collected",
        "other-exit",
    ],
)
def test_the_verdict_is_one_line(output: str, code: int, expected: str) -> None:
    assert verdict(output, code) == expected


def test_the_test_runs_on_the_changed_module_and_it_is_restored(tmp_path: Path) -> None:
    module = tmp_path / "web.py"
    module.write_text(MODULE, encoding="utf-8")
    seen: list[str] = []

    def run() -> tuple[int, str]:
        seen.append(module.read_text(encoding="utf-8"))
        return 1, RAISED

    assert spot_check(module, "8767", "9000", run) == "fails: KeyError: 'l1'"
    assert seen == ['HOST = "127.0.0.1"\nPORT = 9000\n']
    assert module.read_text(encoding="utf-8") == MODULE


class RunnerBroke(Exception):
    pass


def test_the_module_is_restored_when_the_run_raises(tmp_path: Path) -> None:
    module = tmp_path / "web.py"
    module.write_text(MODULE, encoding="utf-8")

    def run() -> tuple[int, str]:
        raise RunnerBroke

    with pytest.raises(RunnerBroke):
        spot_check(module, "8767", "9000", run)
    assert module.read_text(encoding="utf-8") == MODULE


def test_a_text_that_does_not_match_changes_nothing(tmp_path: Path) -> None:
    module = tmp_path / "web.py"
    module.write_text(MODULE, encoding="utf-8")
    ran: list[bool] = []
    with pytest.raises(SpotError):
        spot_check(module, "8768", "9000", lambda: (ran.append(True), (0, ""))[1])
    assert (module.read_text(encoding="utf-8"), ran) == (MODULE, [])
