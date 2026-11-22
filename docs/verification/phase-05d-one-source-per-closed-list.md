# Verification guide: Phase 5d (One source per closed list)

Spec: `docs/phases/phase-05d-one-source-per-closed-list.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `grep -c "^## Phase 5d: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05d-one-source-per-closed-list.md tests/integration/test_closed_lists.py tests/integration/test_domain_schema.py docs/verification/probe-05d.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05d-one-source-per-closed-list.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5d --guide` runs them and the searches, one line each. Given test count: 27.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_closed_lists.py` | at least 1908 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1935 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_closed_lists.py --no-cov -q` | `27 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/domain.py,src/docket/core.py,src/docket/intake.py,src/docket/web.py,src/docket/store.py,src/docket/deadlines.py,src/docket/reminder_plan.py,src/docket/reads.py,src/docket/clients.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05d.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5d: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5d` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-05d.py tests/integration/test_domain_schema.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/critical_modules.txt scripts/tooling_modules.txt src/docket/schema.py src/docket/views.py src/docket/cli.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_closed_lists.py` | `0	8	tests/integration/test_closed_lists.py` (the markers, nothing else) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (no package added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `domain.py`, `OPEN_STATES` | spell it `STATES[:2]` again | `tests/integration/test_closed_lists.py::test_domain_spells_out_each_list_once[open-states]` | `('open', 'in_progress')` spelled out | `assert ('STATES[:2]'...in_progress')) == ("('open', 'i...in_progress'))` |
| S2 | `domain.py`, `valid_request_key` | make the upper bound `< REQUEST_KEY_MAX` | `tests/integration/test_closed_lists.py::test_valid_request_key[two-hundred]` | `True` | `AssertionError: assert False is True` |
| S3 | `web.py`, the header check | check `1 <= len(key) <= domain.REQUEST_KEY_MAX` inline again | `tests/integration/test_closed_lists.py::test_each_key_check_asks_domain[web]` | `400` before the body is parsed | `assert ((422, {'erro...d_json'}), []) == ((400, {'erro...etic-key-5d'])` |
| S4 | `store.py`, the retry-key check | check the length inline again | `tests/integration/test_closed_lists.py::test_each_key_check_asks_domain[store]` | `invalid digest key` | `assert ('task not open: t1', []) == ('invalid dig...etic-key-5d'])` |
| S5 | `reminder_plan.py`, `LATE_MINUTES` | write its first entry as `30` again | `tests/integration/test_closed_lists.py::test_derived_values_follow_domain` | `[45, 60, ...]` after the change | `assert {'due_window'...etic-client']} == {'due_window'...etic-client']}` |
| S6 | `core.py`, `_replace_reminders` | void `kinds=("start",)` again | `tests/integration/test_closed_lists.py::test_no_module_but_domain_lists_states_or_kinds` | `[]` | `assert [('core.py', <line>, 'kinds')] == []` |
| S7 | `clients.py`, `CLIENTS` | assign `("email",)` again | `tests/integration/test_closed_lists.py::test_the_email_client_is_named_only_in_domain` | `[]` | `assert [('clients.py', <line>)] == []` |
| S8 | `intake.py`, `_REPLAY` | write `_CREATED - 1` again | `tests/integration/test_closed_lists.py::test_a_replay_answers_a_plain_200` | `200` | `assert '_CREATED - 1' == '200'` |
| S9 | `intake.py`, `accept_task` | pass `source=_text(parsed["source"])` again | `tests/integration/test_closed_lists.py::test_intake_reads_only_the_deadline_zone_through_text` | `["value['time_zone']"]` | `assert ["value['time...ed['source']"] == ["value['time_zone']"]` |
| S10 | `config.py`, `work_minutes` (unchanged code: proves the narrowed guard still bites) | change `ge=domain.WORK_MINUTES_MIN` to `ge=5` | `tests/integration/test_domain_schema.py::test_consumers_do_not_keep_copied_parsers_domains_or_limits` | passes | `AssertionError: docket.config duplicates a limit` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05d.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It extracts `src` from the spec commit with `git archive` and compares, answer by answer with the current code: every key check at no key, a number, and 0, 1, 200 and 201 characters (ASCII and `é`) through intake, core and the store, and the web header with no key and 0, 1, 200 and 201 characters; a ten-step intake walk (create, replay, reused key, another client, a bad provider, a bad zone, a link, its replay, a link from another client, a link with another source); 120 seeded plans either side of both 2026-11-01 and 2027-03-14 New York changes, and the deadline status at -1, 0, 29, 30, 31 and 600 minutes after each instant; and the reminder rows after one create and five deadline and work-time edits. Last it checks each derived name equals `domain`'s value. It needs the spec commit in the history.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/domain.py src/docket/core.py src/docket/intake.py src/docket/web.py src/docket/store.py src/docket/deadlines.py src/docket/reminder_plan.py src/docket/reads.py src/docket/clients.py` |
| Q5 | the key bound is named only in domain, and the helper is called through the module | `git grep --untracked -n -E 'REQUEST_KEY_MAX\|from docket\.domain import .*valid_request_key' -- src ':!src/docket/domain.py'` |
| Q6 | no slice, copy or arithmetic stands in for a domain value | `git grep --untracked -n -E '_CREATED - 1\|_OPEN_STATES\|STATES\[\|minutes=30\|\(30, 60' -- src` |
| Q7 | the email client is named only in domain | `git grep --untracked -n -E 'client != "email"\|client="email"\|request_key\("email"\|CLIENTS = \("email"' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Keeping `core._check_key`, `intake._valid_key` or `store._check_retry_key` as private wrappers that call `domain.valid_request_key`.
- Reading the constants with `from docket.domain import ...` (only the helper must be called through the module).
- Building `_KIND_ORDER` with a comprehension or `dict(zip(...))`, and passing intake's checked strings with `typing.cast` or another way that does not call `_text`.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05d-one-source-per-closed-list.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5d`), then run `.venv/bin/python scripts/check_reports.py --phase 5d`; it must print `Reports OK.`
