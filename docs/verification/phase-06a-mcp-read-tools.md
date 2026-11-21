# Verification guide: Phase 6a (MCP read tools)

Spec: `docs/phases/phase-06a-mcp-read-tools.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/reads.py`
- `src/docket/mcp_server/server.py`
- `tests/unit/test_reads.py`
- `tests/integration/test_mcp_server_more.py`
- `grep -c "^## Phase 6a: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-06a-mcp-read-tools.md pyproject.toml src/docket/cli.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/mcp_cases.py tests/integration/test_mcp_server.py tests/integration/test_mcp_reads.py tests/e2e/test_cli_mcp.py docs/verification/probe-06a.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 6a --guide` runs them and the searches, one line each. Given test count: 40. The three given test files were committed with strict xfail markers so `main` stayed green; the spec has the coder delete them. HEAD has the markers and `b577343` does not, so G9 compares the other given files with HEAD and G10 compares the three test files with `b577343`. A given test still marked shows in G4 as `xfailed`, or fails the run as a strict XPASS. Either one is a finding.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_mcp_server.py --ignore=tests/integration/test_mcp_reads.py --ignore=tests/e2e/test_cli_mcp.py` | at least 1670 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python -m pip check` (after the install) | `No broken requirements found.` |
| G3 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1710 passed, 0 failed, 0 skipped |
| G4 | `.venv/bin/python -m pytest tests/integration/test_mcp_server.py tests/integration/test_mcp_reads.py tests/e2e/test_cli_mcp.py --no-cov -q` | `40 passed` |
| G5 | `.venv/bin/python -m coverage report --include=src/docket/reads.py,src/docket/mcp_server/__init__.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G6 | `.venv/bin/python docs/verification/probe-06a.py` | last line `FAILURES 0` |
| G7 | `grep -c "^## Phase 6a: " docs/progress.md` | `1` |
| G8 | `.venv/bin/python scripts/check_reports.py --phase 6a` | `Reports OK.` |
| G9 | `git diff HEAD --stat -- pyproject.toml src/docket/cli.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/mcp_cases.py docs/verification/probe-06a.py` | no output |
| G10 | `git diff b577343 --stat -- tests/integration/test_mcp_server.py tests/integration/test_mcp_reads.py tests/e2e/test_cli_mcp.py` | no output (the markers are gone and nothing else changed) |
| G11 | `git status --short` | only the Scope paths |
| G12 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (39 before this phase, plus `mcp` and the 12 packages the spec names) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reads.py`, list_tasks | overdue as `deadline.at < now` instead of `<=` | `tests/integration/test_mcp_reads.py::test_list_tasks_filters_by_status[overdue-includes-exactly-now]` | ['t3', 't8', 't9'] | ['t3', 't8'] |
| S2 | `reads.py`, list_tasks | compare the deadline's and today's UTC dates instead of their dates in `zone` | `tests/integration/test_mcp_reads.py::test_due_follows_the_home_zones_day_across_daylight_saving[spring-forward-23-hour-day]` | due ['t2'] | due [] |
| S3 | `reads.py`, list_tasks | due as `now < deadline.at <= now + timedelta(days=1)` instead of the same date in `zone` | `tests/integration/test_mcp_reads.py::test_due_follows_the_home_zones_day_across_daylight_saving[spring-forward-23-hour-day]` | due ['t2'] | due ['t2', 't3'] |
| S4 | `reads.py`, list_tasks | match due and overdue in every state, not only open and in progress | `tests/integration/test_mcp_reads.py::test_list_tasks_filters_by_status[overdue-includes-exactly-now]` | ['t3', 't8', 't9'] | ['t3', 't6', 't8', 't9'] |
| S5 | `reads.py`, list_tasks | set `next_after` when the page is full (`>= PAGE_SIZE` matches) instead of when more follow | `tests/integration/test_mcp_reads.py::test_a_page_holds_fifty_tasks_and_names_the_next` | (50, 't1', 't50', None) | (50, 't1', 't50', 't50') |
| S6 | `reads.py`, task_record | keep voided reminders | `tests/integration/test_mcp_reads.py::test_get_task_returns_sent_and_pending_reminders_and_leaves_out_voided` | 11 reminders | 19 reminders |
| S7 | `reads.py`, list_tasks | check the cursor before the status | `tests/integration/test_mcp_reads.py::test_refusals_are_constant_codes[status-checked-before-cursor]` | invalid_status | invalid_cursor |
| S8 | `mcp_server/server.py`, build_server | `log_level="ERROR"` | `tests/integration/test_mcp_server.py::test_the_server_is_named_and_logs_nothing_below_critical` | CRITICAL | ERROR |
| S9 | `mcp_server/server.py`, the deadline result | fill `time` whether or not a time was given | `tests/integration/test_mcp_reads.py::test_a_listed_task_carries_its_deadline_and_work_time` | t2 time None | t2 time '17:00' |
| S10 | `mcp_server/server.py`, list_tasks tool | re-raise the `ReadRefused` instead of raising `ToolError(error.code)` | `tests/integration/test_mcp_reads.py::test_refusals_are_constant_codes[cursor-t0]` | Error executing tool list_tasks: invalid_cursor | Error executing tool list_tasks |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-06a.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The oracle classifies a fixed set of rows on the 2026-11-01 New York day by its own rule. Two walks then create 50 tasks without deadlines (an exactly full page), then about 100 more with deadlines from two days late to three days ahead, start, finish, cancel and reopen them at random, and move the clock across the fall-back day. At every step it compares each status's joined pages with the tasks table, the reminders of three tasks with the reminders table, sends 27 junk inputs and checks each refusal is a constant code, and compares a database dump before and after, so no call writes. It reaches cases the given tests fix only once: many pages, both daylight-saving sides, and long runs of state changes.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no environment, machine zone or locale in this phase's modules | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/reads.py src/docket/mcp_server/__init__.py src/docket/mcp_server/server.py` |
| Q6 | nothing reads the machine's time zone | `git grep --untracked -n -E 'tzlocal\|time\.tzname\|localtime\(\|astimezone\(\)\|environ\[.TZ.\]' -- src` |
| Q7 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q8 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/reads.py src/docket/mcp_server/__init__.py src/docket/mcp_server/server.py` |
| Q9 | the read path imports no core, opens no transaction, reads no secret and approves nothing | `git grep --untracked -n -E 'docket\.core\|import core\|\.transaction\(\|keychain\|keyring\|approve' -- src/docket/reads.py src/docket/mcp_server` |
| Q10 | no tracing and no logging set-up in docket code | `git grep --untracked -n -E 'opentelemetry\|basicConfig\|getLogger' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Paging by filtering the store's list in Python or by a slice; either way the order is by id.
- Checking the cursor with a pattern in `reads.py` that matches the store's id rule, as long as `t0`, `t01`, `T1` and the empty string are refused.
- Building the results with a private helper per model, or with `model_validate` on a dict.
- Defining the two tools as closures inside `build_server` or as module functions that take the settings and zone another way, as long as each call opens and closes its own store.
- A deadline's local `date` and `time` taken from one `astimezone(ZoneInfo(zone))` call.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-06a-mcp-read-tools.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 6a`), then run `.venv/bin/python scripts/check_reports.py --phase 6a`; it must print `Reports OK.`
