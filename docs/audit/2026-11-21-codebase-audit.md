# Codebase audit, Nov 21, 2026

Read-only review of `src/docket`, `docket_tools`, `scripts`, `tests`, `docs` and `.claude/skills`. The tree is at commit `b577343`: Phases 0 to 3e are built and verified, and the Phase 6a spec and its given tests are committed but not implemented.

The previous audit (`docs/audit.md`, Nov 15, Phase 2e) stays as the record of that tree, as the roadmap asks. This report checks what happened to its nine findings, then lists what is new.

## Size of things

| Area | Lines |
| --- | --- |
| Product code, `src/docket` (28 files) | 3,445 |
| Repository tooling, `docket_tools` and `scripts` | 1,267 |
| Architect tooling, `.claude/skills/phase-architect/*.py` | 1,236 |
| Tests (all of `tests/`) | 20,869 |
| of which tests about tests, tooling and frozen files | about 5,800, plus 2,800 lines of JSON manifests |
| Docs (`docs/`, 140+ files) | 16,346 |

Tests are six times the product, and docs nearly five times. That is not a problem by itself. The problem is how much of the test and doc volume describes the history of the code rather than its behaviour (findings 1 and 9).

`scripts/check.py` currently ends with `Check failed at: tests`: 34 failed and 5 errors, all in the Phase 6a given tests (see finding 2).

## What is solid

- Every task change still goes through `docket.core` in one `BEGIN IMMEDIATE` transaction, with its audit row and, since Phase 3b, its reminder rows.
- SQL is parameterized. The f-strings build column lists and `?` placeholders only.
- The loopback API is careful: host check, bearer token mapped to a client identity, streamed 64 KiB cap, store work off the event loop, no access log, telemetry off, `Cache-Control: no-store`.
- Reminders are durable rows with claims, retry keys persisted once and reused, and a notifier contract of "once per key". A crash mid-send cannot lose or double-send a reminder, given that contract.
- Error text is constant plus an id. Keychain errors name the item, never the value.
- Tests are offline, synthetic and deterministic, with clock and id injection.

## Status of the Nov 15 findings

| # | Finding | Status | Notes |
| --- | --- | --- | --- |
| 1 | Token not tied to client | Fixed (2f) | `web._bearer` returns the identity; intake requires it |
| 2 | Email reference fields unchecked | Fixed (2g) | `docket.references`, migration 3 |
| 3 | SQLite on the event loop; migration race | Fixed (2h, 2i) | `run_in_threadpool`, streamed cap, startup flock |
| 4 | Two create paths, two JSON writers | Fixed (2j, 2k) | `_insert_open_task`, `serialization.canonical_json`, `docket.parsing` |
| 5 | Closed lists copied | Mostly fixed (2k) | `docket.domain` now owns them. Reminder kinds were added later and are copied again (finding 6 below) |
| 6 | `Store` owns every table | Partly fixed, and worse in size | SQL moved to `_store_*.py`, but the `Store` class grew from 490 to 962 lines (finding 3) |
| 7 | Tooling in product, split tests | Partly fixed | Tooling moved to `docket_tools` (2n); product `*_more.py` folded (2p, 2q). Tooling `*_more.py` remain (2r deferred). `docs/testing.md` has drifted from `critical_modules.txt` again |
| 8 | No type checker | Open (2s deferred) | `cast` still used after membership tests in `core.py` |
| 9 | Id rules; stored-time checks | Ids resolved. Time checks partly fixed | Task, reminder, post and digest times are checked. Audit, link and request-key times are not (finding 8) |

## New findings

| # | Severity | Where | Issue |
| --- | --- | --- | --- |
| 1 | High (maintainability) | `tests/*_manifest.json`, `tests/preservation_cases.py` | Byte and AST freezes pin most of the repository, three times over |
| 2 | High (process) | `main`, `cli.py:80` | `main` is red, and `docket mcp serve` crashes with a traceback |
| 3 | Medium | `store.py` | One 962-line class with copied helpers |
| 4 | Medium | `reminders.py`, `run_loop` | Loop failures are silent and one bad row stops every reminder |
| 5 | Medium | `core`, `reminders`, `store`, `views` | Import cycle hidden by function-level imports; `reminders.py` mixes pure and I/O code |
| 6 | Medium | `domain.py`, `reminders.py`, `core.py`, `intake.py` | New copies of closed lists and magic values |
| 7 | Low-Medium | `core.edit_task` | Untyped `deadline` / `work` reach the store unchecked |
| 8 | Low | `store.py` | Audit, link and request-key rows are decoded without checks |
| 9 | Medium (docs) | `docs/` | Architecture is a phase changelog; several docs are stale |
| 10 | Low | various | Smaller risks: digest race, file modes, `.gitignore`, no lockfile, N+1 reads |

### 1. Freeze manifests pin most of the repository

`tests/product_support_manifest.json`, `tests/product_organization_manifest.json` and `tests/product_consolidation_manifest.json` each hold a `frozen` map. Together they pin the sha256 of:

- every product module except `core.py` and `store.py` (`cli.py`, `config.py`, `web.py`, `intake.py`, `views.py`, `schema.py` and the rest),
- `AGENTS.md`, `pyproject.toml`, every script, `critical_modules.txt`, `tooling_modules.txt`,
- every verifier review in `docs/reviews/`.

`core.py` and `store.py` get structural freezes: 38 and 86 AST nodes that must stay byte-identical, with only named functions allowed to change (`tests/unit/test_feature_preservation.py:66`). The consolidation manifest also stores full `ast.dump` text of moved test bodies.

The same file is usually pinned in all three manifests. When a phase changes a pinned file on purpose, the architect runs `.claude/skills/phase-architect/rehash.py` to rewrite the hashes. So the pins do not stop intended change. They stop *unplanned* change, which includes:

- any bug fix outside a phase spec,
- every refactor this audit recommends (findings 3, 5, 6),
- a one-word fix to `AGENTS.md` or a typo in a review.

Each of those now needs a rehash, then a reviewer who checks that the rehash moved only what it should. The guards were useful while 2n to 2q moved files and had to prove nothing changed. Those phases are verified. The pins now test history, not behaviour, and they are the single biggest cost on every future change.

Recommendation: retire the byte pins for product code, scripts, `AGENTS.md` and `pyproject.toml`. Keep behaviour tests and coverage gates. If review docs must stay immutable, keep one pin list for `docs/reviews/` only, in one manifest. Let the verifier rely on `git diff --stat` against the phase's base commit instead of hashes. Delete `product_organization_*` and `product_consolidation_*` once nothing reads them; fold `preservation_cases.py` away with them.

### 2. `main` is red

`b577343` committed the Phase 6a given tests (40 cases in `test_mcp_reads.py`, `test_mcp_server.py`, `test_cli_mcp.py`) and the `docket mcp serve` command in `cli.py`, but not `docket.mcp_server` or `docket.reads`. Today:

- `scripts/check.py` fails on `main` with 34 failed and 5 errors.
- `docket mcp serve` raises `ModuleNotFoundError` from the lazy import at `cli.py:80`. That is a traceback, not the plain stderr refusal every other command gives.

The workflow in `docs/README.md` says to commit the spec and given files first so `git status` is clean. That works, but it leaves `main` failing until the coder lands. A bisect, a hotfix, or a second session starting from `main` all see red.

Recommendation: commit a phase's given tests and stub wiring on a phase branch (`phase/06a`), and merge to `main` only after verification. Or mark given tests `xfail(strict=True)` until the phase lands, so `main` stays green and the coder's first job is to remove the marker.

### 3. `Store` is one 962-line class

The Nov 15 audit warned that `store.py` would become the file everyone is afraid to edit. The SQL moved into `_store_*.py`, but every table's validation, decoding and record mapping stayed on `Store`, and Phases 3b to 3d added reminders, posts and digests to it. It is now the largest product file by a factor of two.

Copied code inside it:

- Five id parsers that differ only in a letter: `_number`, `_link_number`, `_reminder_number`, `_post_number`, `_digest_number` (`store.py:169-196`), each with its own regex.
- Three identical time decoders: `_reminder_time`, `_post_time`, `_digest_time` (`store.py:618`, `825`, `929`). `_task_from` has a fourth variant inline.
- The same retry-key check in `queue_post` and `queue_digest` (`store.py:727`, `851`), which also matches `core._check_key` and `intake._valid_key`.
- `queued_at is None` checks in `_post_from` and `_digest_from` that duplicate each other.

Layout problems:

- Methods are in arrival order, not grouped. `_migrate` sits between `request_key` and `insert_reminders`; `due_reminders` follows `_task_from`; the reminder backfill lives between migration helpers.
- `insert_task` passes a positional 14-tuple to `_store_tasks.insert_task`, whose column order lives in another file. A swapped pair of same-typed columns would pass every type check.
- `_store_tasks.update_task` has eight copies of `if "x" in fields: assignments.append(...)`. A loop over a fixed allow-list of column names does the same.

Recommendation, after finding 1 is done (otherwise the structural freeze blocks it):

1. One `_row_number(prefix: str, value: str) -> int | None` and one `_utc(value, label, identifier) -> datetime | None`.
2. Split `Store` into per-aggregate classes that share one connection and one `transaction()`: tasks and audit, links and keys, reminders and posts, digests. `Store` keeps startup, migrations and `transaction()`, and exposes the parts (`store.reminders.due(at)`) or keeps thin delegating methods so `core` does not change.
3. Move migration and backfill code to `_store_migrate.py`.

### 4. The reminder loop fails silently, and one bad row blocks all reminders

`run_pass` catches `Exception` for each half and returns `PassResult(sent, digest, failed)`. `run_loop` (`reminders.py:195`) throws the result away. The product has no logging at all. A persistent failure loops every 30 seconds forever with no signal anywhere.

This matters because of how the pass is shaped. `send_due` reads every due reminder and queues every post in one transaction (`reminders.py:62`). `due_reminders` decodes every row and raises `StoreError` on the first malformed time. So one corrupt reminder row, or one task whose `queue_post` raises, rolls back the whole pass, and every other task's reminders stop too. The digest half has the same shape. "A reminder is never lost" is the app's first promise in `docs/architecture.md`; a reminder that is never sent and never reported is close to lost.

Stage 5 plans to turn repeated failures into alerts. Until it does, nothing notices.

Recommendation:

- Have `run_loop` keep the last `PassResult` and a count of consecutive failures per half, readable by the caller (Stage 5's `docket status` and alerts need it anyway). Record it in a table or a file if `docket status` runs in another process.
- Isolate per task: queue each task's post in its own transaction (or a savepoint), and skip a task whose rows fail to decode, recording its id. A corrupt row should silence one task, not all of them.
- Write this into the Stage 5 spec as a requirement, so it is not lost.

### 5. Import cycle, and two jobs in `reminders.py`

The dependency graph has a cycle that two function-level imports hide:

```
core     -> reminders   (plan_reminders)
reminders -> store      (Store, Task)
store    -> reminders   lazily, in _backfill_reminders (store.py:552)
reminders -> views      lazily, in send_digest (reminders.py:117)
views    -> core        (Outcome)
```

The lazy imports work, but the next change that moves one of them to the top of a file breaks startup with a partial-import error, and the cause is far from the symptom.

`reminders.py` also holds four separate things: pure planning (`plan_reminders`, critical and side-effect free), the sender (`send_due`), the digest (`send_digest`, which also formats text), and the loop. The pure planner is the part the migration backfill needs; the rest depends on the notifier, clock and ids.

Recommendation: move `PlannedReminder` and `plan_reminders` into `reminder_plan.py` with no import of `store` (pass the deadline and work time, or depend on a small protocol instead of `Task`). Move digest and notice text into `views` or a new `notices.py`. Move `Outcome` out of `core` (or have `views` take a `Task` and a `changed` flag) so `views` no longer imports `core`. Then `store` imports the planner at the top and the cycle is gone.

### 6. New copies of closed lists and magic values

`docket.domain` fixed this for states, sources and providers. Phase 3 added new copies:

| Fact | Copies |
| --- | --- |
| Reminder kinds | `domain.REMINDER_KINDS`, `PlannedReminder.kind`'s `Literal[...]`, `reminders._KIND_ORDER`, `reminders._NOTICE`, the schema CHECK, and `core._replace_reminders`'s literal `("before", "due_soon", "due", "late")` (`core.py:348`) |
| "Due" window 30 minutes | `deadlines.DUE_WINDOW` and `reminders.LATE_MINUTES[0]`, which the architecture says are the same thing |
| Open states | `domain.OPEN_STATES = STATES[:2]`, a slice that depends on dict order in `STATE_LABELS` |
| The email-only client | `client != "email"` in `intake.py:44`, `intake.py:76`, `core.py:251`; `clients.CLIENTS = ("email",)` separate from `domain.CORE_CLIENTS`; `clients.ALREADY_MESSAGE` hardcodes "email" |
| Retry-key bounds | `core._check_key`, `intake._valid_key`, `web._handle`, `Store.queue_post`, `Store.queue_digest` (the HTTP and core checks are intentional; the five spellings are not) |

Smaller oddities in the same vein:

- `intake._REPLAY = _CREATED - 1` means 200. Write `200`.
- `intake._text` raises `_BadDeadline` but is also used for `source`, `provider`, `message_id` and `link`. It can never raise there because `_object` already checked them, so the name misleads and the branch is dead.
- `views.refusal_text` raises `KeyError` for any code missing from `_REFUSALS` (`invalid_client`, `invalid_key`, `key_reused`). The CLI never produces those today; the MCP write tools in 6b may.

Recommendation: add `DEADLINE_KINDS` (everything but `start`) and `ENDED_STATES` / `OPEN_STATES` as explicit tuples to `domain`; derive `_KIND_ORDER` from `REMINDER_KINDS`; make `DUE_WINDOW` and `LATE_MINUTES[0]` one constant or assert they match; name the email client once. Add a test that every `CoreError` code has a refusal sentence.

### 7. `edit_task` accepts anything as a deadline or work time

`core.edit_task(deadline: object = UNCHANGED, work: object = UNCHANGED)` (`core.py:130`) never checks that `deadline` is a `Deadline` or `None`. A string or dict passes `_work_after_deadline` (which returns `False` for non-instances) and reaches `Store._deadline_values`, which fails with `AttributeError`, not `CoreError`. The CLI always passes a real value, so nothing breaks today. Phase 6c's `change_deadline` and `plan_work_time` MCP tools will call this function with values built from agent input. Add `isinstance` checks that raise a fixed code before 6c, the way 2f did for `create_task_once`.

### 8. Some stored rows are still decoded without checks

`Store.audit` (`store.py:368`), `_link_from` (`store.py:657`) and `request_key` (`store.py:439`) call `datetime.fromisoformat` and `json.loads` directly. A malformed row raises `ValueError` or `JSONDecodeError` carrying library text, instead of the `StoreError("invalid stored ...: <id>")` every other record type now gives. `docs/architecture.md` line 92 calls this out as outside Phase 2i, and no later phase picked it up. Phase 6a's `get_task` will read reminders, and a later audit tool will read these. Use the shared `_utc` helper from finding 3.

### 9. Docs: stale content and a changelog where the architecture should be

**`docs/architecture.md` describes phases, not the system.** Most sections after the data model are paragraphs of the form "Phase 2i specifies...", "Phase 2l specifies...", stacked in phase order, with spec-level detail ("migration-3-only foreign-key relaxation", "without double-closing the reference rebuild path"). A reader who wants to know how the store starts up today has to merge four paragraphs. The phase specs and reviews already hold this history. Rewrite each section as the current design in present tense, and move phase references to one line ("since Phase 2i") or drop them.

**Specific stale statements:**

| Doc | Statement | Reality |
| --- | --- | --- |
| `architecture.md` "Package layout (planned)" | `intake/` and `cli/` are packages; the list omits `web.py`, `server.py`, `views.py`, `domain.py`, `parsing.py`, `serialization.py`, `clients.py`, `notifier.py` and the seven `_store_*.py` modules | All are single modules that exist; the layout mixes built and planned files without saying which is which |
| `architecture.md` "How it runs" | "A claim older than 5 minutes with no sent time is released" | Reminders are claimed once when queued into a post and never released; it is the *post* claim that expires and is taken again |
| `architecture.md` line 92 | Audit/link/request-key timestamp decoding "is outside this phase" | Still true three phases later, with no phase planned (finding 8) |
| `roadmap.md` Stage 3 row | 3e "(specified)" | Line 3 of the same file says 3e is verified |
| `testing.md` "Critical modules" | Lists through `_store_reminders.py` | `critical_modules.txt` also has `_store_posts.py` and `_store_digests.py` (added in 3c, 3d) |
| `testing.md` rules 12, 13 | Phase 2o/2p procedure (fixture import forms, AST-body preservation, selector migration) | These are one-off phase instructions, not testing rules; a new contributor cannot follow them without reading three specs |
| `open-questions.md` | "Package name. `docket` is assumed; easy to change before Phase 0." still open | Shipped as `docket` at Phase 0 |
| `README.md` | Audit row points only at the Phase 2e audit | Should also point at `docs/audit/` |

**Other doc maintenance costs:**

- `docs/verification/` holds 31 `probe-*.py` scripts (about 5,800 lines). `pyproject.toml` excludes `docs` from ruff, so these scripts are never linted or formatted, and nothing runs them after their phase. Either move them to a tooling folder that is linted, or treat them as frozen history and say so.
- `docs/decisions.md`, `roadmap.md` and `architecture.md` all repeat the same owner decisions (id policy, digest rules, loop rules). When one changes, three files need the edit.

### 10. Smaller risks

- **Empty digest race.** `send_digest` claims the digest in one transaction, then re-reads its tasks outside it (`reminders.py:141`). If the owner marks the last overdue task done in between, the notifier receives "Still open past their deadlines: 0 tasks." with no lines. Skip the send (and mark it sent) when `lines` is empty.
- **File modes.** `Store.__init__` runs `path.chmod(0o600)` after `sqlite3.connect` creates the file, and never on `docket.sqlite3-wal` and `-shm`, which SQLite creates with the process umask. The data folder is `0700`, which covers this in practice. Setting `os.umask(0o077)` around the open closes the gap fully.
- **`.gitignore`** covers `*.sqlite3` and `*.db-wal` but not `*.sqlite3-wal`, `*.sqlite3-shm` or `*.startup.lock`. The default data folder is outside the repo, so this only bites when `DOCKET_DATA_DIR` points inside it under a name other than `data/`.
- **No lockfile.** Dependencies are version ranges in `pyproject.toml`, with nothing pinning exact versions or hashes. A fresh `.venv` can differ from the verified one. A `uv.lock` or a hashed `requirements.txt` makes rebuilds reproducible.
- **Tokens are read once.** `server.build_app` reads client tokens at startup. `docket clients add email --replace` has no effect on a running server until restart, and the old token keeps working until then. Say so in the command's output or the docs.
- **N+1 reads.** `_post_from` and `_digest_from` run one query per row for their members, and `queue_digest` decodes a full task per id. Harmless for one person's tasks; worth a join if `get_task` lists posts.
- **Type checking.** Still none (2s deferred). `send_due` uses a bare `dict[str, list]`; `core` uses `cast` after membership tests. A checker in `scripts/check.py` would have caught finding 7.
- **Tooling tests still split.** `test_reports_more.py`, `test_reports_put_more.py`, `test_reports_phase_more.py`, `test_acceptance_more.py`, `test_spotcheck_more.py` and `test_tooling_boundary_more.py` remain (2r deferred). `tests/` also has 20 `*_cases.py` helper modules and four JSON manifests at its top level beside `conftest.py`; a `tests/support/` package would separate helpers from tests.
- **`phase_tools.py`** is 898 lines, the largest Python file in the repo, with template text and lint checks still in the same functions (deferred from the Nov 15 audit).

## What this review did not treat as a problem

- `core.py` (425 lines) and `cli.py` (287) are still one idea per file.
- The duplicate key-length check at HTTP and in core. Both are needed; the issue in finding 6 is spelling the bound five ways.
- Repeat sends after a 5-minute claim expiry. They reuse the persisted key, and once-per-key delivery is the notifier's documented contract.
- Test volume in the product tests. They are specific, offline and fast (the full suite runs in about 17 seconds).

## Suggested order

1. **Now:** get `main` green (finding 2), either by landing 6a or by moving its given tests behind `xfail` or onto a branch.
2. **Before the next refactor of any kind:** retire the byte and AST freezes (finding 1). Every later item is cheaper once they are gone.
3. **Before Stage 5's `docket run`:** make loop failures visible and isolate per-task failures (finding 4).
4. **Before Phase 6b/6c:** type-check `edit_task` inputs and complete the refusal-text map (findings 7, 6).
5. **As one cleanup phase:** shared id and time helpers, split `Store` by aggregate, break the import cycle, collapse the reminder-kind copies (findings 3, 5, 6, 8).
6. **Docs pass, any time:** rewrite `architecture.md` as current design, fix the stale rows in finding 9, and link this report from `docs/README.md`.
