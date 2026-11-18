# Phase 2k: Shared domain rules and parsing

## Goal

Give current Python consumers one definition of domain lists and repeated limits, one strict date/time parser, and one cached exact zone-name set. Preserve boundary-specific validation and messages, and explicitly map settings errors so an unknown field never becomes a web-port refusal. This finishes findings 4 and 5 and the settings-mapping part of finding 8 before the store split; no feature or schema change.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1074, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_shared_parsing.py --ignore=tests/unit/test_domain_rules.py --ignore=tests/unit/test_settings_error_mapping.py --ignore=tests/integration/test_domain_schema.py --ignore=tests/integration/test_shared_parser_adapters.py --ignore=tests/e2e/test_shared_parse_refusals.py` must show `1074 passed`. The ignored files specify this phase, including imports of its new modules.

## Facts

Checked 2026-11-17 against baseline `231a760`:

- Phase 2j is committed and independently PASS: 1,074 tests, no findings/deviations/follow-ups. Baseline check.py passed; all eight existing modules in this phase's coverage command already have 100% line and branch coverage.
- CLI and intake separately compile ASCII YYYY-MM-DD / HH:MM patterns and call the standard-library ISO readers. Their callers distinguish omitted time from malformed time and use different safe messages. CLI plan/add/edit and intake all need the shared parser; strict parsing does not move time policy out of deadlines.py.
- Core repeats closed lists and title/key bounds; CLI/views repeat open states; config/deadlines repeat work bounds and separately acquire exact zone names. References already owns its 512/2,048 caps; keep those public names there. Core clients email/agent differ intentionally from token issuance's email-only CLIENTS.
- Current SQL repeats the same contract deliberately: tasks state/source/provider, links provider, request_keys client, audit actor/action; title/key/work and both tables' reference bounds. Given tests compare the current database schema against shared definitions without editing shipped SQL.
- Standard-library zoneinfo confirmed fall-back 2026-11-01 01:30 New York = 05:30 UTC, spring-forward 2027-03-14 02:30 = 07:30 UTC, and date-only 17:00 = 22:00/21:00 UTC respectively. The probe independently asserts these literals.
- Real synthetic Pydantic ValidationErrors can have unknown, root (empty location), nested or no errors. Current get_settings misreports unknown/empty errors as WEB_PORT_MESSAGE and root errors raise IndexError. Error-list order must not determine established field priority.
- Baseline settings/CLI tests give four intended settings failures and eleven preservation guards. Names-only modules collect 87 cases from 19 functions; preservation guards are identified below. Separate discarded patches passed ten settings-mapping cases and two shared-zone cases. No shared parser/domain implementation or combined reference phase was built.

## Owner's decisions

No new owner decision. This phase implements the approved audit-remediation row and preserves all previous approval, identity, time, retry, reference and startup choices. The generic unknown-settings message below is an architect-selected safe diagnostic, not a new field or setting.

## Architect's decisions

- Add `docket.domain` as the dependency-free policy owner (standard library only). It imports no config, core, store, deadlines, CLI or intake module. Tuples retain the order below; mappings are read-only MappingProxyType objects and forbidden categories are a frozenset. Existing public deadlines.WORK_MINUTES_MIN/MAX remain re-exports. References keeps its cap constants and predicate.
- Add `docket.parsing.ParseError(ValueError)`, `parse_date(value: object) -> date` and `parse_time(value: object) -> time`. Refusals use exactly `invalid date or time` and suppress library-error chains. The caller handles optional None time and maps ParseError to its existing refusal. Both CLI and intake call parsing through the module, enabling the same replaceable functions.
- `domain.zone_names() -> frozenset[str]` is functools.cache-decorated and calls zoneinfo.available_timezones() once per cache lifetime. Config and deadlines call it through the module; no second cache or name normalization. Only tests clear the cache.
- Add config.SETTINGS_MESSAGE = `Invalid docket settings.`. Explicit recognized-field priority is data_dir, time_zone, work_minutes, web_port; when none is recognized, use SETTINGS_MESSAGE, including root/empty errors. Recognized fields win over unknown fields in the same validation failure. Do not expose the errors' input, context, library text or location as a message.
- Add both new modules to the given critical-module list. Estimate under 200 implementation lines, including policy declarations and adapter changes; no table extraction or validation redesign is part of this phase.

Domain public values (literal cases in the given test pin every value):

| Name | Value |
|---|---|
| STATES | tuple of STATE_LABELS keys, in order open, in_progress, done, cancelled |
| OPEN_STATES / ENDED_STATES | (open, in_progress) / (done, cancelled) |
| SOURCES | (email, agent, proposal, owner) |
| CORE_CLIENTS | (email, agent); does not replace clients.CLIENTS |
| ACTORS | (owner, agent, email) |
| STATE_ACTIONS | (start, done, cancel, reopen) |
| AUDIT_ACTIONS | (create, start, done, cancel, reopen, retitle, deadline, work_time) |
| PROVIDERS | (gmail, outlook, yahoo) |
| SOURCE_ACTORS | email→email, agent→agent, proposal→owner, owner→owner |
| STATE_LABELS | open→open, in_progress→in progress, done→done, cancelled→cancelled |
| FORBIDDEN_TEXT_CATEGORIES | frozenset of Cc, Cf, Zl, Zp |
| TITLE_MAX / REQUEST_KEY_MAX | 100 / 200; existing minimum 1 remains at each boundary |
| WORK_MINUTES_MIN / WORK_MINUTES_MAX | 5 / 720 |

## Requirements

1. **Shared domain values:** implement the table above without changing a token, label, order or bound. Keep all collections immutable and preserve the existing source-to-actor map. Domain knows no product layer. Given: literal/immutability test and schema comparisons.
2. **Use the shared policy:** core consumes sources, core clients, actors, state actions, providers, source actors, open/ended states, title/key bounds and forbidden categories. CLI consumes OPEN_STATES; views consumes STATE_LABELS and OPEN_STATES; references consumes the forbidden categories. Deadlines/config consume work bounds, retaining deadlines' old exported names. HTTP, intake and core each retain their own key check but use REQUEST_KEY_MAX. Keep token issuance email-only and intake's explicit email-only identity rule. Remove the copied list/mapping declarations and numeric bounds; fixed human-readable messages and single semantic comparisons such as source == email stay literal. Given: structural/presentation tests, prior approval and limit tests; coder adds boundary assertions below.
3. **SQL agreement without migration:** keep schema.py, migration strings and version 3 byte-identical. Current CHECK enumerations and numeric bounds must agree with domain/references, including provider membership and reference caps in both tasks and links. SQL stays a deliberate literal copy, tested against Python; do not generate historic SQL from imports or change stored data. Given: seven enumeration and seven bound cases.
4. **Strict shared parsers:** accept only strings matching the full ASCII shapes YYYY-MM-DD or HH:MM, then validate calendar/clock values using the standard library. Reject compact and week dates, Unicode digits, spaces/newlines, invalid dates, seconds, fractions, offsets and timezone suffixes. Reject non-strings, including None; optional None is handled by adapters. Return date or naive time with zero seconds/microseconds; never trim or rewrite input. Raise the safe typed ParseError described above. Given: 40 unit cases and probe oracle.
5. **Thin adapters and stable order:** CLI add/edit/plan and intake deadline parsing use the shared module functions, with no local regex or ISO parser. Keep shape/type checks, optional time handling and refusal order at their current boundaries. Map ParseError to DUE_MESSAGE/AT_MESSAGE or PLAN_DATE_MESSAGE/PLAN_TIME_MESSAGE in CLI, and 422 invalid_deadline in intake; print no parser/library text. A bad date still precedes a bad time, deadline errors precede core title errors, and CLI parsing still precedes task lookup. No database write or added clock read on a parsing refusal. Keep successful rendering, field shapes and omitted-time flags unchanged. Given: four routing cases, four intake refusals, five CLI refusals, previous CLI/intake tests; coder adds HTTP/order cases below.
6. **Shared exact zones and unchanged time policy:** config and deadlines use the one cached exact zone-name set. Preserve case sensitivity, existing TIME_ZONE_MESSAGE/ZONE_MESSAGE, UTC identity checks, fold=0 DST behavior, 17:00 date-only default, work end rules and all existing clock reads. Do not move datetime parsing at the stored-time boundary into this strict user-input parser. Given: cache and routing tests, four DST/optional-time intake cases, prior deadline/store tests and probe.
7. **Explicit settings error map:** get_settings maps recognized validation locations to their existing field messages in the stated priority, independently of error order; nested locations use their first component. Unknown-only, root-only and empty error lists give SETTINGS_MESSAGE without IndexError. Suppress the library-error chain and emit nothing; settings fields, coercion, defaults, environment prefix and validation constraints remain unchanged. Given: ten mapping/message cases and existing settings tests.
8. **Scope and coverage:** no new dependency, setting, source capability, network call, task field, migration or change to core/store public signatures. Preserve the Phase 2j shared creation/JSON path, Phase 2i startup/read safeguards and all earlier given files. Every line and branch of both new modules and the eight edited modules must be covered.

9. **Progress entry** for `## Phase 2k: Shared domain rules and parsing (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_shared_parsing.py` | 40 tests from 5 functions (requirement 4) |
| `tests/unit/test_domain_rules.py` | 3 tests from 3 functions (requirements 1, 6) |
| `tests/unit/test_settings_error_mapping.py` | 10 tests from 2 functions (requirement 7) |
| `tests/integration/test_domain_schema.py` | 17 tests from 5 functions (requirements 1–3) |
| `tests/integration/test_shared_parser_adapters.py` | 12 tests from 3 functions (requirements 5–6) |
| `tests/e2e/test_shared_parse_refusals.py` | 5 tests from 1 function (requirement 5) |
| `scripts/critical_modules.txt` | Given gate additions for domain.py and parsing.py |
| `docs/verification/probe-02k.py` | The verifier's probe |

Given test count: **87** (19 functions). Names-only modules give 63 failures and 24 passing guards: the typed-error declaration, six existing settings-priority cases, four existing reference-cap cases, eight intake time/refusal cases and five CLI refusal cases. Structural and routing checks reject a behaviour-preserving no-op.

## Tests to write

Write `tests/integration/test_domain_adapter_contracts.py`:

- Preserve the 100/101 title, 200/201 retry key and 5/720 work bounds at the consumers. Through synthetic HTTP, show an overlong key is refused before malformed JSON or store opening. At intake/core, combine bad keys, clients and bodies to retain their established order and no writes.
- Prove the shared open-state list and label/actor mappings are actually used by CLI/views/core, with deciding task states and all four sources; do not only import the new module.
- Exercise a public CLI date-only add after a DST change and a work plan at a range boundary; assert literal output and stored UTC instant, retaining exactly the prior time policy.
- Assert real invalid settings still report data_dir before time_zone before work_minutes before web_port; ensure a future error mixed with a known location never leaks the synthetic marker.
- Cover remaining branches of shared parsing, cached zones, consumer adapters and fallback mapping with deciding assertions. No earlier test, critical gate or given file is edited.

## Scope

| Path | Change |
|---|---|
| `src/docket/domain.py` | create |
| `src/docket/parsing.py` | create |
| `tests/integration/test_domain_adapter_contracts.py` | create |
| `src/docket/config.py` | edit: shared work bounds and zone names; explicit safe settings error mapping |
| `src/docket/deadlines.py` | edit: shared work bounds and zone names, with old public bounds re-exported |
| `src/docket/core.py` | edit: shared domain collections and bounds without changing validation order or creation |
| `src/docket/views.py` | edit: shared state labels and open states |
| `src/docket/cli.py` | edit: shared parsers and open states, preserving message mapping |
| `src/docket/intake.py` | edit: shared parsers and key bound, preserving validation order |
| `src/docket/web.py` | edit: shared retry-key bound only |
| `src/docket/references.py` | edit: shared forbidden text categories; cap constants and predicate unchanged |
| `docs/progress.md` | append your entry |

## Out of scope

- Type-checker installation or annotation cleanup; validation redesign; changing title/reference/key policy, token capabilities or HTTP contracts.
- Table-module extraction (2l), moving phase tooling (2m), test consolidation (2n), or changing established public signatures/messages except the new unknown-settings fallback.
- Dynamic migration SQL, schema/version changes, historic data rewrites, repair commands, stricter stored-time grammar or normalization.
- Reminder/calendar/Discord/MCP features, new dependencies, settings, clocks, services or live accounts.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval:** CORE_CLIENTS is not the token issuance list. HTTP/intake remain email-only; source still comes from the authenticated identity.
- **Layering:** share definitions and parsing, retain boundary checks and refusal order. Only core writes tasks; preserve one transaction and one audit path.
- **Privacy:** safe constant errors only. Never display a request value, title, Pydantic input/context or library exception text.
- **Determinism/time:** no new clock or timezone inference. Shared parsers read no clock; DST policy stays in deadlines.py; synthetic data only.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_shared_parsing.py --ignore=tests/unit/test_domain_rules.py --ignore=tests/unit/test_settings_error_mapping.py --ignore=tests/integration/test_domain_schema.py --ignore=tests/integration/test_shared_parser_adapters.py --ignore=tests/e2e/test_shared_parse_refusals.py` (before you start) | `1074 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1161 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_shared_parsing.py tests/unit/test_domain_rules.py tests/unit/test_settings_error_mapping.py tests/integration/test_domain_schema.py tests/integration/test_shared_parser_adapters.py tests/e2e/test_shared_parse_refusals.py --no-cov -q` | `87 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/domain.py,src/docket/parsing.py,src/docket/config.py,src/docket/deadlines.py,src/docket/core.py,src/docket/views.py,src/docket/cli.py,src/docket/intake.py,src/docket/web.py,src/docket/references.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02k.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2k: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2k` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_shared_parsing.py tests/unit/test_domain_rules.py tests/unit/test_settings_error_mapping.py tests/integration/test_domain_schema.py tests/integration/test_shared_parser_adapters.py tests/e2e/test_shared_parse_refusals.py scripts/critical_modules.txt docs/verification/probe-02k.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/domain.py src/docket/parsing.py src/docket/config.py src/docket/deadlines.py src/docket/core.py src/docket/views.py src/docket/cli.py src/docket/intake.py src/docket/web.py src/docket/references.py
```

## Test path migration (Phase 2q)

The product continuation paths above now use behaviour names. This is a byte-identical file move; function names, parameter IDs, counts and original implementation history are unchanged. The phase's immutable move inventory records every old/new selector.
