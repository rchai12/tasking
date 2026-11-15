from docket.acceptance import Row, digest, read_rows

TWO_TABLES = """\
## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest -q` | `1 passed` |
| no command here | nothing |

| Command | Must show |
|---|---|
| `git status --short` | paths |
| `.venv/bin/python -m coverage report` | `100%` |

```zsh

git grep -n x -- src

```
## Next
"""
FIRST = """\
== tests (tooling)
Sections:
  tooling        10 passed    0 failed    0 skipped

== tests
Sections:
  tooling        10 passed    0 failed    0 skipped
  core          722 passed    0 failed    0 skipped

Summary:
  tests (tooling): passed
  tests: passed
All checks passed.
"""


def test_two_tables_skip_each_header_and_numbering_carries_on() -> None:
    assert read_rows(TWO_TABLES, "Acceptance") == [
        Row("A1", ".venv/bin/python -m pytest -q"),
        Row("A2", "git status --short"),
        Row("A3", ".venv/bin/python -m coverage report"),
        Row("Q1", "git grep -n x -- src"),
    ]


def test_a_first_run_keeps_both_section_tables() -> None:
    found = digest(Row("A1", ".venv/bin/python scripts/check.py --first tooling"), FIRST, 0)
    assert found == [
        "A1: All checks passed.",
        "  Sections:",
        "    tooling        10 passed    0 failed    0 skipped",
        "  Sections:",
        "    tooling        10 passed    0 failed    0 skipped",
        "    core          722 passed    0 failed    0 skipped",
    ]


def test_section_lines_that_end_the_output_are_kept() -> None:
    output = "Sections:\n  core            1 passed    0 failed    0 skipped\n"
    assert digest(Row("A1", ".venv/bin/python scripts/check.py --section core"), output, 0) == [
        "A1:   core            1 passed    0 failed    0 skipped",
        "  Sections:",
        "    core            1 passed    0 failed    0 skipped",
    ]


def test_trailing_spaces_on_a_logged_line_are_cut() -> None:
    output = "src/docket/web.py:3:import x   \n"
    assert digest(Row("Q1", "git grep -n x -- src"), output, 0) == [
        "Q1: 1 line",
        "  src/docket/web.py:3:import x",
    ]
