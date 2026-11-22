# Verification guide: Phase 5c (Import direction)

Spec: `docs/phases/phase-05c-import-direction.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 5c: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05c-import-direction.md tests/integration/test_import_direction.py docs/verification/probe-05c.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05c-import-direction.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5c --guide` runs them and the searches, one line each. Given test count: 11.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_import_direction.py` | at least 1896 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1907 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_import_direction.py --no-cov -q` | `11 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/reminder_plan.py,src/docket/reminders.py,src/docket/store.py,src/docket/_store_migrate.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05c.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5c: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5c` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-05c.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/schema.py src/docket/domain.py src/docket/deadlines.py src/docket/cli.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_import_direction.py` | `0	6	tests/integration/test_import_direction.py` (the markers, nothing else) |
| G10 | `git diff HEAD --numstat -- scripts/critical_modules.txt src/docket/core.py` | `1	0	scripts/critical_modules.txt` and `1	1	src/docket/core.py` |
| G11 | `git status --short` | only the Scope paths |
| G12 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (no package added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `_store_migrate.py`, the backfill | import `docket.reminders` inside the backfill and plan through it | `tests/integration/test_import_direction.py::test_no_docket_import_is_hidden_in_a_function_or_a_type_check` | only the `cli.py` MCP import | `assert [('_store_mig...rver.server')] == [('cli.py', '...rver.server')]` |
| S2 | `store.py`, the planner import | import `PlannedReminder` from `docket.reminders` at module top | `tests/integration/test_import_direction.py::test_every_module_imports_alone_in_a_fresh_interpreter` | `{}` (every module imports) | `assert {'docket._sto...ore.py)', ...} == {}` |
| S3 | `reminder_plan.py`, its imports | add `from docket.store import Task` | `tests/integration/test_import_direction.py::test_the_planner_imports_only_deadlines_and_domain` | `['docket.deadlines', 'docket.domain']` | `assert ['docket.dead...docket.store'] == ['docket.dead...ocket.domain']` |
| S4 | `core.py`, the planner import | import `plan_reminders` from `docket.reminders` | `tests/integration/test_import_direction.py::test_core_and_the_store_plan_through_the_planner_module` | no `docket.reminders` import | `AssertionError: docket.core` |
| S5 | `views.py`, the notice table | change the late notice to `This is late!` | `tests/integration/test_reminder_sending.py::test_notice_text_is_fixed_per_kind_with_a_missed_line_from_two[late]` | `This is late.` | `assert 'This is late!' == 'This is late.'` |
| S6 | `reminders.py`, the `views` import | keep a local `notice_text` instead of importing it | `tests/integration/test_import_direction.py::test_moved_names_stay_reachable_from_reminders[notice_text-views]` | the same object | `assert <function notice_text at 0x...> is <function notice_text at 0x...>` |
| S7 | `views.py`, its imports | add `reminders` to `from docket import domain` | `tests/integration/test_import_direction.py::test_the_import_graph_has_no_cycle` | no cycle | `AssertionError: docket.views -> docket.reminders -> docket.views` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05c.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It starts fresh interpreters that import every ordered pair of `store`, `_store_migrate`, `reminders`, `reminder_plan`, `views` and `core`, and four full shuffles of every module (seeds 5, 17, 29, 41). It then extracts `src` from the spec commit with `git archive` and compares, case by case, 120 seeded plans (seeds 3, 13, 31; deadlines and work times either side of both 2026-11-01 and 2027-03-14 New York changes, ended states included), every notice kind with 0 to 3 missed, and headings for 0 to 3 tasks, between the spec commit's `reminders` and the current code. Last it checks that the moved names in `reminders` are the objects of their new modules. It needs the spec commit in the history.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/reminder_plan.py src/docket/reminders.py src/docket/store.py src/docket/_store_migrate.py src/docket/views.py` |
| Q5 | no TYPE_CHECKING block hides an import | `git grep --untracked -n -E 'TYPE_CHECKING' -- src` |
| Q6 | the planner's users and the text's new home never import reminders | `git grep --untracked -n -E 'from docket\.reminders import\|from docket import .*reminders([^_A-Za-z]\|$)' -- src/docket/core.py src/docket/store.py src/docket/_store_migrate.py src/docket/reminder_plan.py src/docket/views.py` |
| Q7 | reminders.py defines none of the moved names itself | `git grep --untracked -n -E '_NOTICE\|def (notice_text\|digest_heading\|plan_reminders)\(\|class PlannedReminder' -- src/docket/reminders.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- `Plannable` as a `Protocol` with properties or plain annotated attributes; the planner's private kind order and hour step under any private names.
- The re-exports in `reminders` written as `import X as X`, as one `from ... import` line with an `__all__`, or used in the module so that `ruff` keeps them.
- The moved text placed anywhere in `views.py`, and `reminders` importing `views` as a module or importing its names.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05c-import-direction.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5c`), then run `.venv/bin/python scripts/check_reports.py --phase 5c`; it must print `Reports OK.`
