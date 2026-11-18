from pathlib import Path

import pytest

from docket_tools.acceptance import HEADING_MESSAGE, MAX_DETAIL, Row, accept, digest, read_rows

SPEC = """\
# Phase 9z: Example

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest -q --ignore=tests/x.py` (before you start) | `703 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.` |
| `.venv/bin/python -m coverage report --fail-under=100`, right after `check.py` | exit 0 |
| a row with no command | nothing |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'print\\(|logging' -- src
git grep --untracked -n -E 'ollama|openai' -- src
```

## Notes

| Note | Command |
|---|---|
| `git log` | not this section |
"""
GUIDE = """\
## 2. Gates

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python docs/verification/probe-09z.py` | `FAILURES 0` |
| G2 | `.venv/bin/python -m pip list --format=freeze \\| wc -l` | `41` |

## 5. Searches

| # | Rule | Command |
|---|---|---|
| Q1 | no model client | `git grep --untracked -n -E 'ollama\\|openai' -- src` |
"""
CHECK = """\
== lint
All checks passed!
== tests
........
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          673 passed    0 failed    0 skipped

Summary:
  lint: passed
  tests: passed
All checks passed.
"""


def test_a_spec_gives_its_acceptance_rows_and_searches() -> None:
    assert read_rows(SPEC, "Acceptance") == [
        Row("A1", ".venv/bin/python -m pytest -q --ignore=tests/x.py"),
        Row("A2", ".venv/bin/python scripts/check.py --first core"),
        Row("A3", ".venv/bin/python -m coverage report --fail-under=100"),
        Row("A4", "git status --short"),
        Row("Q1", "git grep --untracked -n -E 'print\\(|logging' -- src"),
        Row("Q2", "git grep --untracked -n -E 'ollama|openai' -- src"),
    ]


def test_a_guide_gives_its_labels_and_unescapes_pipes() -> None:
    assert read_rows(GUIDE, "2. Gates") + read_rows(GUIDE, "5. Searches") == [
        Row("G1", ".venv/bin/python docs/verification/probe-09z.py"),
        Row("G2", ".venv/bin/python -m pip list --format=freeze | wc -l"),
        Row("Q1", "git grep --untracked -n -E 'ollama|openai' -- src"),
    ]


def test_a_missing_heading_is_refused() -> None:
    with pytest.raises(ValueError) as raised:
        read_rows(SPEC, "Gates")
    assert str(raised.value) == "no such heading: Gates"
    assert (HEADING_MESSAGE, MAX_DETAIL) == ("no such heading", 20)


@pytest.mark.parametrize(
    ("row", "output", "code", "expected"),
    [
        (
            Row("A2", ".venv/bin/python scripts/check.py --first core"),
            CHECK,
            0,
            [
                "A2: All checks passed.",
                "  Sections:",
                "    tooling        59 passed    0 failed    0 skipped",
                "    core          673 passed    0 failed    0 skipped",
            ],
        ),
        (
            Row("A1", ".venv/bin/python -m pytest -q"),
            "....\n732 passed in 6.10s\n\n",
            0,
            ["A1: 732 passed in 6.10s"],
        ),
        (
            Row("A3", ".venv/bin/python -m coverage report"),
            "Name  Stmts\nTOTAL  10  2  80%\nCoverage failure: total of 80 is less than 100\n",
            2,
            ["A3: Coverage failure: total of 80 is less than 100 (exit 2)"],
        ),
        (Row("Q1", "git grep -n x -- src"), "", 1, ["Q1: empty"]),
        (
            Row("Q2", "git grep -n x -- src"),
            "src/docket/web.py:3:import x\n",
            0,
            ["Q2: 1 line", "  src/docket/web.py:3:import x"],
        ),
        (
            Row("A4", "git status --short"),
            " M src/docket/a.py\n?? src/docket/b.py\n",
            0,
            ["A4: 2 lines", "   M src/docket/a.py", "  ?? src/docket/b.py"],
        ),
        (Row("A5", "git diff HEAD --stat -- tests"), "", 0, ["A5: empty"]),
        (Row("A6", "grep -c x docs/progress.md"), "", 1, ["A6: empty (exit 1)"]),
    ],
    ids=["check", "pytest", "exit", "search-silent", "search-match", "status", "diff", "grep"],
)
def test_each_row_is_digested(row: Row, output: str, code: int, expected: list[str]) -> None:
    assert digest(row, output, code) == expected


def test_long_details_are_cut_with_a_count() -> None:
    output = "".join(f"src/docket/m{number}.py:1:x\n" for number in range(25))
    found = digest(Row("Q3", "git grep -n x -- src"), output, 0)
    assert found[0] == "Q3: 25 lines"
    assert found[1:3] == ["  src/docket/m0.py:1:x", "  src/docket/m1.py:1:x"]
    assert found[20:] == ["  src/docket/m19.py:1:x", "  ... 5 more lines in the log"]


def test_every_row_runs_in_order_and_is_logged(tmp_path: Path) -> None:
    ran: list[str] = []

    def run(command: str) -> tuple[int, str]:
        ran.append(command)
        return (0, "24 passed in 1.0s\n") if "pytest" in command else (0, "")

    rows = [Row("A1", ".venv/bin/python -m pytest -q"), Row("Q1", "git grep -n x -- src")]
    logs = tmp_path / "logs"
    assert accept(rows, run, logs) == ["A1: 24 passed in 1.0s", "Q1: empty", f"Logs: {logs}"]
    assert ran == [".venv/bin/python -m pytest -q", "git grep -n x -- src"]
    assert (logs / "A1.log").read_text(encoding="utf-8") == (
        "$ .venv/bin/python -m pytest -q\n24 passed in 1.0s\n"
    )
    assert (logs / "Q1.log").read_text(encoding="utf-8") == "$ git grep -n x -- src\n"
