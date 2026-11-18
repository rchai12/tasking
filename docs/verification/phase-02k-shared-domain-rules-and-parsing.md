# Verification guide: Phase 2k (Shared domain rules and parsing)

Spec: `docs/phases/phase-02k-shared-domain-rules-and-parsing.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/domain.py`
- `src/docket/parsing.py`
- `tests/integration/test_domain_adapter_contracts.py`
- `grep -c "^## Phase 2k: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02k-shared-domain-rules-and-parsing.md tests/unit/test_shared_parsing.py tests/unit/test_domain_rules.py tests/unit/test_settings_error_mapping.py tests/integration/test_domain_schema.py tests/integration/test_shared_parser_adapters.py tests/e2e/test_shared_parse_refusals.py scripts/critical_modules.txt docs/verification/probe-02k.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2k --guide` runs them and the searches, one line each. Given test count: 87.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_shared_parsing.py --ignore=tests/unit/test_domain_rules.py --ignore=tests/unit/test_settings_error_mapping.py --ignore=tests/integration/test_domain_schema.py --ignore=tests/integration/test_shared_parser_adapters.py --ignore=tests/e2e/test_shared_parse_refusals.py` | at least 1074 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1161 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_shared_parsing.py tests/unit/test_domain_rules.py tests/unit/test_settings_error_mapping.py tests/integration/test_domain_schema.py tests/integration/test_shared_parser_adapters.py tests/e2e/test_shared_parse_refusals.py --no-cov -q` | `87 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/domain.py,src/docket/parsing.py,src/docket/config.py,src/docket/deadlines.py,src/docket/core.py,src/docket/views.py,src/docket/cli.py,src/docket/intake.py,src/docket/web.py,src/docket/references.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02k.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2k: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2k` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_shared_parsing.py tests/unit/test_domain_rules.py tests/unit/test_settings_error_mapping.py tests/integration/test_domain_schema.py tests/integration/test_shared_parser_adapters.py tests/e2e/test_shared_parse_refusals.py scripts/critical_modules.txt docs/verification/probe-02k.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no package is added) |

## 3. Spot checks

Inspect the entire consumer diff first: shared definitions are used at every named boundary; validation and error priority stay local. Confirm token issuance remains email-only, CORE_CLIENTS is not used to enable a route, old deadlines work-limit exports still resolve, schema.py is unchanged, and stored-time decoding is not replaced by the strict input grammar. Fixed message strings and individual state/source comparisons may stay literal; verb captions remain presentation text. Confirm domain imports no product layer and no mutable registry escapes.

Run mutations in a clean disposable checkout containing the planning baseline and implementation, with PYTHONPATH=src:. directed at that checkout. Never mutate the owner's live checkout. Rows S1–S4 are paper checks of the not-yet-built pure parser; translate them to its private shape. S5–S8 were confirmed against separate small discarded patches/constant declarations. No combined reference phase was built.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | parsing.py, parse_date or its private reader | Replace its full-shape refusal condition with False, retaining ISO value validation | `tests/unit/test_shared_parsing.py::test_strict_date_refusals_do_not_echo_input[compact]` | ParseError | compact 20261120 accepted as a date |
| S2 | parsing.py, parse_time or its private reader | Replace its full-shape refusal condition with False, retaining ISO value validation | `tests/unit/test_shared_parsing.py::test_strict_time_refusals_do_not_echo_input[seconds]` | ParseError | 17:00:00 accepted as a time |
| S3 | parsing.py, date reader after string-type check | Insert one line value = value.strip() before shape/value checks | `tests/unit/test_shared_parsing.py::test_strict_date_refusals_do_not_echo_input[newline]` | ParseError | trailing-newline date accepted |
| S4 | parsing.py, date shape refusal | Replace the constant ParseError argument with the input value | `tests/unit/test_shared_parsing.py::test_strict_date_refusals_do_not_echo_input[private-marker]` | invalid date or time | PRIVATE_SYNTHETIC |
| S5 | config.py, unknown-field fallback | Replace SETTINGS_MESSAGE with WEB_PORT_MESSAGE in the fallback raise | `tests/unit/test_settings_error_mapping.py::test_settings_mapping_is_explicit_and_safe[unknown]` | Invalid docket settings. | web-port refusal |
| S6 | config.py, validation-location collection | Remove the empty-location guard before reading loc[0] | `tests/unit/test_settings_error_mapping.py::test_settings_mapping_is_explicit_and_safe[root]` | generic ConfigError | IndexError |
| S7 | config.py, zone membership check | Replace domain.zone_names() with frozenset({"UTC", "America/New_York"}) | `tests/unit/test_domain_rules.py::test_settings_and_deadlines_use_the_same_zone_function` | two shared function calls | one shared function call |
| S8 | domain.py, PROVIDERS | Replace ("gmail", "outlook", "yahoo") with ("gmail", "outlook") | `tests/integration/test_domain_schema.py::test_current_sql_enumerations_match_domain[link-providers]` | SQL and Python both have three providers | SQL has yahoo; Python does not |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02k.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe independently asserts a standard-library grammar table and fold=0 DST oracle, then checks shared parsers, both provider CHECKs, unchanged bounds and safe fallback for unknown/root validation locations. `--oracle-only` must show FAILURES 0. Baseline has four named failures for the new modules and missing safe fallback; it never crashes at an import. It reads only temporary synthetic databases.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/domain.py src/docket/parsing.py src/docket/config.py src/docket/deadlines.py src/docket/core.py src/docket/views.py src/docket/cli.py src/docket/intake.py src/docket/web.py src/docket/references.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private parser helpers, compiled regex organization and module-vs-name imports for immutable constants. CLI/intake still call parse_date/parse_time through their module; config/deadlines call zone_names through domain.
- Keeping old private names as aliases to shared immutable constants, or replacing their uses directly. No local domain copies, secondary zone cache or duplicated parsing policy remains.
- Deriving STATES from STATE_LABELS and AUDIT_ACTIONS from the state actions; the required tuple orders and literal contents stay fixed.
- Mapping settings messages with a private ordered dictionary/table or explicit branches, provided every known field is explicit and root/unknown fallback is safe.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02k-shared-domain-rules-and-parsing.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2k`), then run `.venv/bin/python scripts/check_reports.py --phase 2k`; it must print `Reports OK.`

## Test path migration (Phase 2q)

The product continuation paths above now use behaviour names. This is a byte-identical file move; function names, parameter IDs, counts and original implementation history are unchanged. The phase's immutable move inventory records every old/new selector.
