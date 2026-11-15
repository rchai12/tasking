# Phase 2e: Phase tooling

## Goal

Cut what the coder and the verifier read and print in every phase, as their notes found (`docs/coder-token-use.md`, `docs/verification-process.md`). Four tools:

- `scripts/check.py --quiet` keeps each step's output in a log file and prints only the tables, the summary and the failing step's last lines.
- `scripts/accept.py` runs a spec's Acceptance commands and searches, or a guide's gates and searches, and prints one short digest.
- `scripts/spot_check.py` applies one exact change to a module, runs the deciding test, restores the module and prints a one-line verdict.
- `scripts/progress.py` writes the progress entry in its checked form.

The logic of the last three lives in `docket.acceptance`, `docket.spotcheck` and `docket.reports`, covered and critical. The scripts stay thin. Pointing the `phase-coder` and `phase-verifier` skills, the conventions and the guide generator at these tools is the architect's work after this phase passes.

Sections: `tooling`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 732, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reports_put.py --ignore=tests/unit/test_spotcheck.py --ignore=tests/unit/test_acceptance.py --ignore=tests/unit/test_check_quiet.py --ignore=tests/unit/test_acceptance_script.py --ignore=tests/unit/test_spotcheck_script.py --ignore=tests/unit/test_progress_script.py` must show `732 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-15.

- **pytest's one-line output** (`-q --tb=line`): a failed test prints `<path>.py:<line>: <message>` with the whole message (an assertion's both sides, `KeyError: 'l1'`, `Failed: DID NOT RAISE ValueError`). The short summary line (`FAILED ... - ...`) cuts the message to the terminal width. A raised exception also prints an `E   <message>` line, before the path line. Exit codes: 0 passed, 1 a test failed, 2 a collection error (an `E   ModuleNotFoundError: ...` line, no path line), 4 an unknown test id (`ERROR: not found: ...`), 5 no tests collected.
- **`docket.reports.parse_progress`** reads an entry whose list is written `  - None` back as `("None",)`. It accepts more than one empty line between entries. It refuses an entry with an empty title, an empty `New public names`, an empty list item (`  - `), or a line break inside a field, with one `Problem` each.
- **`scripts/check.py`** has no tests of its own, and coverage (`--cov=docket`) doesn't measure `scripts/`. Its `main(argv, run)` takes the command runner, so a test can replace it. The given `tests/support.load_script(name)` loads `scripts/<name>.py` as a module, so a test can call its `main`.
- **The two document shapes.** A spec's commands are the backticked first cell of each row of the table under `## Acceptance`, and the lines of the `zsh` block under its `### Searches`, written as they run. A guide's are the backticked cell of each row under `## 2. Gates` (labels `G1`, ...) and `## 5. Searches` (labels `Q1`, ...), with every `|` inside a command written `\|`. Every committed spec from 1a to 2d has this shape (the probe reads them all).
- **The shell.** Spec commands are written for zsh (`/bin/zsh`), from the repository root. `tempfile.gettempdir()` is the user's own temporary folder under `/var/folders/`, outside the repository.

## Owner's decisions

Decided 2026-11-14:

- **All four tools in one phase**: `check.py --quiet`, the acceptance digest, the spot-check runner and the progress appender.
- **Phase id 2e**, before Stage 3.
- **The verifier still judges each spot check.** The runner prints the result; the verifier decides whether it is a finding or a note.
- Earlier: the coder and the verifier work through the `phase-coder` and `phase-verifier` skills.

## Architect's decisions

- **The logic is in `src/docket/`**, where coverage measures it: `docket.acceptance` (new), `docket.spotcheck` (new) and `docket.reports` (extended). The scripts parse arguments, run commands, print and exit, as `scripts/check_reports.py` does. `acceptance.py` and `spotcheck.py` are critical modules, with `reports.py` (already critical): a slip in them hides a failure from both agents, or leaves a source file changed.
- **The digest doesn't judge "Must show"**: it prints each command's deciding line. The agent compares it with the table, so a reworded cell can't make the script pass something.
- **Logs stay outside the repository**, in `tempfile.gettempdir()`: `docket-check/` for `check.py --quiet`, `docket-accept-<phase id>/` for `accept.py`, each overridable with `--log-dir`. Each run overwrites its files.
- **A spot check changes only a file under `src/`**, never a test or a given file. It restores the file from the bytes it read, in a `finally`, and refuses a change whose old text doesn't match exactly once, before writing.
- **No clock in the tooling**: `progress.py` takes the entry's date as `--date`.
- **Without `--quiet`, `check.py` prints exactly as today.**

## Requirements

1. **`src/docket/reports.py`**:
   - `ENTRY_MESSAGE = "the entry does not match the progress form"`.
   - `format_entry(entry: ProgressEntry) -> str` writes the entry in the form `docs/phase-conventions.md` gives. Each line ends with `\n`, an empty `deviations` or `follow_ups` is written `  - None`, and `line` is ignored.
   - `put_entry(text: str, entry: ProgressEntry) -> str` returns the progress log with the entry put in. If a line starts with `## Phase <entry.phase>: `, that entry (up to the next `## ` line) is replaced in place, keeping one empty line before the next entry. Otherwise the entry is appended after the text's trailing line breaks are cut, with one empty line between. When `parse_progress` reports any problem in the result, it raises `ValueError(ENTRY_MESSAGE)`.
2. **`scripts/progress.py`** `main(argv: list[str] | None = None) -> int`:
   - Options: `--file` (default `<repository>/docs/progress.md`), `--phase`, `--title`, `--date` (ISO date), `--tests-before`, `--tests-after`, `--given`, `--names`, `--changed`, and `--deviation` and `--follow-up`, each repeatable and in order. All but `--file`, `--deviation` and `--follow-up` are required.
   - It writes `put_entry`'s result to the file and prints `Progress entry for Phase <id> written.`. On `ValueError` it prints `Error: <message>` to stderr, exits 2 and leaves the file unchanged.
3. **`src/docket/spotcheck.py`**:
   - `MATCH_MESSAGE = "the old text must match exactly once"`; `class SpotError(Exception)`.
   - `mutate(text, old, new) -> str` replaces the one match, or raises `SpotError(f"{MATCH_MESSAGE}: found {count}")`.
   - `spot_check(path: Path, old: str, new: str, run: Callable[[], tuple[int, str]]) -> str` reads the file's bytes and mutates its UTF-8 text (a `SpotError` leaves the file unwritten and `run` uncalled). It writes the changed text, calls `run()`, restores the original bytes in a `finally`, and returns `verdict(output, code)`.
4. **`verdict(output: str, code: int) -> str`**:
   - code 0: `passes`;
   - code 1: `fails: <message>`, the message taken from the first `<path>.py:<line>: <message>` line, else from the first `E   ` line, else just `fails`;
   - code 2: `error: <the first E line's message>`, or `error: collection` when there is none;
   - code 4 or 5: `no test ran`;
   - any other code: `error: exit <code>`.

   A message is cut to 140 characters, followed by `...` when it was longer.
5. **`scripts/spot_check.py`** `main(argv: list[str] | None = None, run=<the real runner>) -> int`:
   - Arguments: the module path relative to `--root` (default the repository), `--old`, `--new`, `--test` and optional `--row`.
   - A module whose resolved path isn't inside `<root>/src` prints `Error: the module must be under src/` to stderr and exits 2. A `SpotError` prints `Error: <message>` and exits 2. In both cases nothing runs.
   - Otherwise it prints the verdict (after `<row> ` when given) and exits 0 when the verdict starts with `fails`, 1 otherwise.
   - `run(test, cwd) -> tuple[int, str]`. The real one runs `<this python> -m pytest <test> -q --tb=line --no-cov -p no:cacheprovider` in `cwd` with `PYTHONDONTWRITEBYTECODE=1`, stdout and stderr together, and a 300-second limit (a timeout answers `(124, "timed out")`).
6. **`src/docket/acceptance.py`**:
   - `HEADING_MESSAGE = "no such heading"`; `MAX_DETAIL = 20`; `@dataclass(frozen=True) class Row: label: str; command: str`.
   - `read_rows(markdown: str, heading: str) -> list[Row]` reads the section from the line `## <heading>` up to the next line starting with `## `. A missing heading raises `ValueError(f"{HEADING_MESSAGE}: {heading}")`.
   - In each table, the first two lines (the header and the separator) are skipped. Every other row with a backticked span gives one `Row`: the command is the first span with `\|` turned into `|`. The label is the row's first cell when that cell isn't backticked; otherwise it is `A<n>`, numbering such rows from 1. A row with no span is skipped.
   - Each non-empty line inside a fenced code block gives `Row("Q<n>", <the line as written>)`, numbered from 1.
   - Rows keep their order in the document.
7. **`digest(row: Row, output: str, code: int) -> list[str]`** and **`accept(rows, run: Callable[[str], tuple[int, str]], log_dir: Path) -> list[str]`**:
   - `digest` works on the output's non-empty lines, with trailing spaces cut:
     - a command containing `scripts/check.py` gives its last line, then every `Sections:` line and the two-space-indented lines after it;
     - a command starting with `git status`, `git diff` or `git grep` gives `empty`, `1 line` or `<n> lines`, then every line;
     - any other command gives its last line, or `empty`.
   - The first line is `<label>: <that>`, followed by ` (exit <code>)` unless the code is 0, or 1 for a `git grep`. Detail lines follow with two spaces before each. After `MAX_DETAIL` of them comes `  ... <n> more lines in the log`.
   - `accept` makes `log_dir` (parents included). For each row in order, it calls `run(row.command)`, writes `<log_dir>/<label>.log` as `$ <command>\n<output>`, and collects the digest. It ends with `Logs: <log_dir>`.
8. **`scripts/accept.py`** `main(argv: list[str] | None = None, run=<the real runner>) -> int`:
   - Options: `--phase` (a phase id as `docket.reports` checks it, else `Error: <PHASE_MESSAGE>` and exit 2), `--guide`, `--root` (default the repository) and `--log-dir`.
   - It reads the one file `docs/phases/phase-<id padded>-*.md`, or `docs/verification/phase-<id padded>-*.md` with `--guide`. With none, or more than one, it prints `Error: no spec for phase <id>` (`no guide` with `--guide`) and exits 2.
   - The rows are the spec's `Acceptance` rows, or the guide's `2. Gates` rows then its `5. Searches` rows. It prints `accept`'s lines and exits 0.
   - `run(command, cwd)`. The real one runs `/bin/zsh -c <command>` in `--root`, stdout and stderr together, with a 1800-second limit (a timeout answers `(124, "timed out")`).
9. **`scripts/check.py --quiet`** (with `--log-dir`, default `<tempfile.gettempdir()>/docket-check`, made if missing):
   - Each command step's output goes to a log file in that folder: `lint.log`, `format.log`, `tests-first.log` (the `--first` run), `tests.log`, or `section.log` (`--section`).
   - `run` is called as `run(command, cwd, log)`, and the real `run_command` writes stdout and stderr to `log` when it isn't `None`.
   - Quiet prints no `== <step>` lines. It prints only:
     - the `Sections:` tables;
     - the critical coverage gaps;
     - for a failed step with a log, `Last 20 lines of <log>:` and those lines;
     - the summary and its last line, or for `--section` its `Section <name>: ...` line;
     - then `Logs: <folder>`.
   - Without `--quiet`, output and behaviour are as today, with `run(command, cwd, None)`.
10. **Boundaries**: `docket.acceptance` and `docket.spotcheck` start no process, print nothing, and read no clock or environment; the runners are passed in. Each script ends with `if __name__ == "__main__":` and `sys.exit(main())`, as `scripts/check_reports.py` does.

11. **Progress entry** for `## Phase 2e: Phase tooling (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_reports_put.py` | 9 tests from 5 functions (requirement 1) |
| `tests/unit/test_spotcheck.py` | 16 tests from 5 functions (requirements 3 and 4) |
| `tests/unit/test_acceptance.py` | 13 tests from 6 functions (requirements 6 and 7) |
| `tests/unit/test_check_quiet.py` | 4 tests from 4 functions (requirement 9; the last checks that output without `--quiet` is unchanged and passes today) |
| `tests/unit/test_acceptance_script.py` | 5 tests from 3 functions (requirement 8) |
| `tests/unit/test_spotcheck_script.py` | 5 tests from 3 functions (requirement 5) |
| `tests/unit/test_progress_script.py` | 3 tests from 3 functions (requirement 2) |
| `tests/support.py` | edited: `load_script(name)` added |
| `tests/sections.toml` | edited: the new test files are in the `tooling` section |
| `scripts/critical_modules.txt` | edited: `acceptance.py` and `spotcheck.py` added |
| `docs/verification/probe-02e.py` | The verifier's probe |

Given test count: **55** (the seven new files).

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test. Name them so `tests/sections.toml` puts them in `tooling` (for example `tests/unit/test_acceptance_more.py`).

- **`digest` of a `check.py --first` run**: both `Sections:` tables appear in the details, the first-run table first.
- **`read_rows` with two tables in one section**: the second table's header and separator are skipped too, and the `A<n>` numbering carries on.
- **`put_entry` on a log with no trailing line break**: the entry still follows one empty line.
- **`verdict` for an `E   ` line with trailing spaces**: the spaces are cut.

## Scope

| Path | Change |
|---|---|
| `src/docket/acceptance.py` | create |
| `src/docket/spotcheck.py` | create |
| `scripts/accept.py` | create |
| `scripts/spot_check.py` | create |
| `scripts/progress.py` | create |
| `src/docket/reports.py` | edit: `ENTRY_MESSAGE`, `format_entry`, `put_entry` |
| `scripts/check.py` | edit: `--quiet`, `--log-dir`, the `log` argument of `run` |
| `tests/unit/test_*_more.py` | create: your tests |
| `docs/progress.md` | append your entry |

## Out of scope

- Changing the `phase-coder` or `phase-verifier` skills, `docs/phase-conventions.md` or the architect's tools to use these scripts. That is the architect's work after this phase.
- Judging a "Must show" cell, colours, JSON output, running rows in parallel, or a `-vv` option on the spot-check runner.
- A spot check on a file outside `src/`, more than one change per run, or a run that leaves the change in place.
- A default date for `progress.py`, or reading the clock in the tooling.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Never change a real source file for good**: tests of `spot_check` and `spot_check.py` use files under `tmp_path`; the only real run is the probe's, on a temporary project.
- **Never write the real `docs/progress.md` from a test**: always pass `--file` under `tmp_path`.
- **No network**: the runners start local processes only; tests replace them.
- **Error messages are constant text plus identifiers** (a count, a phase id, a heading), never a module's text or a command's output.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reports_put.py --ignore=tests/unit/test_spotcheck.py --ignore=tests/unit/test_acceptance.py --ignore=tests/unit/test_check_quiet.py --ignore=tests/unit/test_acceptance_script.py --ignore=tests/unit/test_spotcheck_script.py --ignore=tests/unit/test_progress_script.py` (before you start) | `732 passed` |
| `.venv/bin/python scripts/check.py --first tooling` | last line `All checks passed.`; summary lists `tests (tooling): passed`; at least 787 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_reports_put.py tests/unit/test_spotcheck.py tests/unit/test_acceptance.py tests/unit/test_check_quiet.py tests/unit/test_acceptance_script.py tests/unit/test_spotcheck_script.py tests/unit/test_progress_script.py --no-cov -q` | `55 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/acceptance.py,src/docket/spotcheck.py,src/docket/reports.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02e.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2e: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2e` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_reports_put.py tests/unit/test_spotcheck.py tests/unit/test_acceptance.py tests/unit/test_check_quiet.py tests/unit/test_acceptance_script.py tests/unit/test_spotcheck_script.py tests/unit/test_progress_script.py tests/support.py tests/sections.toml scripts/critical_modules.txt docs/verification/probe-02e.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/acceptance.py src/docket/spotcheck.py src/docket/reports.py
git grep --untracked -n -E 'import subprocess|from subprocess|os\.system|os\.popen' -- src
```
