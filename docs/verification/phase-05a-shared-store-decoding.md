# Verification guide: Phase 5a (Shared store decoding)

Spec: `docs/phases/phase-05a-shared-store-decoding.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 5a: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05a-shared-store-decoding.md tests/integration/test_store_decoding.py docs/verification/probe-05a.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05a-shared-store-decoding.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5a --guide` runs them and the searches, one line each. Given test count: 25.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_decoding.py` | at least 1850 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1875 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_store_decoding.py --no-cov -q` | `25 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05a.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5a: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5a` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-05a.py tests/support.py tests/conftest.py tests/reference_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts src/docket/core.py src/docket/schema.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_store_decoding.py` | `0	8	tests/integration/test_store_decoding.py` (the markers, nothing else) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (the count before this phase, plus each package the spec adds) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `store.py`, the JSON-object decoder | accept any decoded JSON that is not `None` (drop the dict check) | `tests/integration/test_store_decoding.py::test_a_bad_audit_row_is_refused_without_library_text[list]` | `invalid stored audit entry: t1` | `DID NOT RAISE StoreError` |
| S2 | `store.py`, `_utc` | drop the `tzinfo is not UTC` check | `tests/integration/test_store_decoding.py::test_a_bad_audit_row_is_refused_without_library_text[naive]` | `invalid stored audit entry: t1` | `DID NOT RAISE StoreError` |
| S3 | `store.py`, `_utc` | raise the parse refusal without `from None` | `tests/integration/test_store_decoding.py::test_a_bad_link_row_is_refused_without_library_text[unparseable]` | no cause, context suppressed | `assert (ValueError(...) is None or False)` |
| S4 | `store.py`, `request_key` | name the stored key instead of its task in the refusal | `tests/integration/test_store_decoding.py::test_a_bad_request_key_row_is_refused_without_library_text[list]` | `invalid stored request key: t1` | `... run-1:step-1' == '... t1'` |
| S5 | `store.py`, the side-file `chmod` | check `exists()` first and drop the handling of a missing file | `tests/integration/test_store_decoding.py::test_a_side_file_that_vanishes_before_its_chmod_is_not_an_error` | the store opens | `FileNotFoundError: [Errno 2] synthetic vanished side file` |
| S6 | `store.py`, `Store.__init__` | let the `OSError` from creating the database file pass on | `tests/integration/test_store_decoding.py::test_a_database_that_cannot_be_created_gives_the_constant_startup_error` | `store startup unavailable` | `PermissionError: [Errno 13] synthetic-private-library-text` |
| S7 | `store.py`, the link decoder | name the link's task instead of the link in the refusal | `tests/integration/test_store_decoding.py::test_a_bad_link_row_is_refused_without_library_text[naive]` | `invalid stored link: l2` | `'invalid stored link: t1' == 'invalid stored link: l2'` |
| S8 | `store.py`, `Store.__init__` | skip the side files' `chmod` | `tests/integration/test_store_decoding.py::test_leftover_wal_and_shm_files_are_made_private` | `(384, 384, 384)` | `(384, 420, 420) == (384, 384, 384)` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05a.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It first forces every bad time and every bad JSON text of its tables, each alone in its own data folder beside a good audit, link and key row of another task, so a refusal must name the bad row's own id and leave the other task's rows readable. It then plants 40 seeded rows (seeds 51 to 53), mostly good, across four tasks' audit, link and key rows, and checks that each reader returns exactly the model's decoded times, ids and requests, or the model's one constant message, that a missing key stays missing, and that no read changes the database. Last it checks the database is `0600` when `sqlite3.connect` is first called under umask `022`, that leftover `-wal` and `-shm` files become `0600`, and the three `.gitignore` lines.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/store.py` |
| Q5 | every stored time and JSON goes through the shared decoders; the old parsers and regexes are gone | `git grep --untracked -n -E '(datetime\.fromisoformat\|json\.loads)\(row\|def _(link\|reminder\|post\|digest)_number\|def _(reminder\|post\|digest)_time\|re\.compile\(r"[tlrpd]\[' -- src/docket/store.py` |
| Q6 | no process-wide umask (owner's decision) | `git grep --untracked -n -E 'umask' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The two helpers' names, argument order and where in `store.py` they sit, as long as one id parser and one time decoder serve every reader; a JSON-object helper of its own, or the check written beside each `json.loads`.
- The `Z` form of a stored time accepted, as today; any other UTC spelling `datetime.fromisoformat` reads as `UTC` too.
- `os.open` with `O_RDWR` or `O_WRONLY`, closed at once or handed on, as long as SQLite never creates the file itself.
- The side files' `chmod` through `Path.chmod` or `os.chmod`, catching `FileNotFoundError` or a wider `OSError` subclass for a missing file only.
- `queue_post` and `queue_digest` sharing a helper that takes the message, or one that returns a flag.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05a-shared-store-decoding.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5a`), then run `.venv/bin/python scripts/check_reports.py --phase 5a`; it must print `Reports OK.`
