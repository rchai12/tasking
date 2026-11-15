"""Phase 2e probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-02e.py

It checks five properties of the phase tooling:
- 600 random spot checks (a match, no match or two, a run that answers or raises) always leave
  the module byte for byte as it was;
- 300 random progress entries put into a log with other entries leave every other entry as it
  was, keep one entry per phase, and read back;
- every committed spec and guide from Phase 1a on gives its rows: the spec its Acceptance
  commands and searches, the guide G1, G2, ... and Q1, Q2, ... in order;
- `scripts/accept.py` and `scripts/spot_check.py` work with their real runners on a temporary
  project (real shell commands, a real pytest run on a changed module);
- `scripts/check.py --quiet --section tooling` prints its table, its result and the log folder,
  and no test progress.
`--oracle-only` prints the reach counts of the random walks, for the architect.
It uses temporary folders, touches no network or Keychain, and changes no repository file.
"""

import random
import re
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
ROOT = Path.cwd()
PYTHON = sys.executable
SPOTS = 600
ENTRIES = 300


def spot_case(rng: random.Random) -> tuple[str, str, str]:
    """A module text, an old text and how the run behaves."""
    module = "".join(rng.choice(["A = 1\n", "B = 2\n", "C = 'x'\n"]) for _ in range(4))
    old = rng.choice(["A = 1", "B = 2", "C = 'x'", "D = 4"])
    return module, old, rng.choice(["answers", "raises"])


def spot_outcome(module: str, old: str, behaviour: str) -> str:
    if module.count(old) != 1:
        return "refused"
    return behaviour


assert spot_outcome("A = 1\nA = 1\n", "A = 1", "answers") == "refused"
assert spot_outcome("A = 1\n", "D = 4", "raises") == "refused"
assert spot_outcome("A = 1\nB = 2\n", "A = 1", "raises") == "raises"
print("oracle: ok")


def check(label: str, function) -> None:
    global FAILURES
    try:
        passed = function()
    except Exception as error:  # noqa: BLE001
        passed = False
        label = f"{label} (raised {type(error).__name__})"
    if not passed:
        FAILURES += 1
    print(f"{label}: {'ok' if passed else 'FAIL'}")


class ProbeRunBroke(Exception):
    pass


def spots() -> bool:
    rng = random.Random(7)
    reached = {"answers": 0, "raises": 0, "refused": 0}
    if not ORACLE_ONLY:
        from docket.spotcheck import SpotError, spot_check

        folder = Path(tempfile.mkdtemp())
    for step in range(SPOTS):
        module, old, behaviour = spot_case(rng)
        wanted = spot_outcome(module, old, behaviour)
        reached[wanted] += 1
        if ORACLE_ONLY:
            continue
        path = folder / f"m{step}.py"
        path.write_bytes(module.encode("utf-8"))
        seen: list[str] = []

        def run(path: Path = path, behaviour: str = behaviour) -> tuple[int, str]:
            seen.append(path.read_text(encoding="utf-8"))
            if behaviour == "raises":
                raise ProbeRunBroke
            return 1, "/w/t.py:1: AssertionError: assert 1 == 2\n"

        try:
            spot_check(path, old, "Z = 9", run)
            found = "answers"
        except ProbeRunBroke:
            found = "raises"
        except SpotError:
            found = "refused"
        if found != wanted:
            print(f"  step {step}: {wanted} expected, {found} found for old {old!r}")
            return False
        if path.read_bytes() != module.encode("utf-8"):
            print(f"  step {step}: the module was not restored after {found}")
            return False
        if wanted != "refused" and seen != [module.replace(old, "Z = 9")]:
            print(f"  step {step}: the run saw {seen!r}, not the changed module")
            return False
        if wanted == "refused" and seen:
            print(f"  step {step}: a refused change still ran the test")
            return False
    if ORACLE_ONLY:
        print(f"  reached {reached}")
        return True
    if not all(value >= 30 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def entries() -> bool:
    from docket.reports import ProgressEntry, parse_progress, put_entry

    rng = random.Random(11)
    base = ProgressEntry(
        phase="1a",
        title="Example",
        date=date(2026, 11, 15),
        tests_before=1,
        tests_after=2,
        given=1,
        new_names="None",
        changed_files=1,
        deviations=(),
        follow_ups=(),
        line=0,
    )
    text = "# Progress\n\nOne entry per phase.\n"
    replaced = 0
    for step in range(ENTRIES):
        phase = rng.choice(["1a", "1b", "2", "2e", "3a", "10c"])
        entry = replace(
            base,
            phase=phase,
            title=rng.choice(["Example", "Phase tooling", "A | B"]),
            tests_after=rng.randrange(2, 900),
            deviations=tuple(rng.choice(["One", "Two two"]) for _ in range(rng.randrange(3))),
            follow_ups=tuple(rng.choice(["Stopped: G3 | x | y", "Later"]) for _ in range(2)),
        )
        before, _ = parse_progress(text)
        others = {found.phase: found for found in before if found.phase != phase}
        replaced += any(found.phase == phase for found in before)
        text = put_entry(text, entry)
        after, problems = parse_progress(text)
        if problems:
            print(f"  step {step}: {problems[0].text}")
            return False
        phases = [found.phase for found in after]
        if len(phases) != len(set(phases)):
            print(f"  step {step}: phase {phase} appears twice")
            return False
        for found in after:
            if found.phase == phase:
                wanted = replace(entry, deviations=entry.deviations or ("None",), line=found.line)
                if found != wanted:
                    print(f"  step {step}: phase {phase} read back as {found}")
                    return False
            elif replace(found, line=0) != replace(others[found.phase], line=0):
                print(f"  step {step}: phase {found.phase} changed when {phase} was put")
                return False
    if replaced < 30:
        print(f"  replaced only {replaced} times")
        return False
    return True


SPAN = re.compile(r"`([^`]+)`")


def committed_docs() -> bool:
    from docket.acceptance import read_rows

    specs = sorted((ROOT / "docs" / "phases").glob("phase-0[1-9]*.md"))
    guides = sorted((ROOT / "docs" / "verification").glob("phase-0[1-9]*.md"))
    if len(specs) < 11 or len(guides) < 11:
        print(f"  found {len(specs)} specs and {len(guides)} guides")
        return False
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        rows = read_rows(text, "Acceptance")
        section = text.split("\n## Acceptance\n", 1)[1].split("\n## ", 1)[0]
        tables = [
            line
            for line in section.split("```")[0].split("\n")
            if line.startswith("| `") or (line.startswith("|") and SPAN.search(line))
        ]
        commands = [row for row in rows if row.label.startswith("A")]
        if len(commands) != len(tables) or "scripts/check.py" not in commands[1].command:
            print(f"  {spec.name}: {len(commands)} rows for {len(tables)} table lines")
            return False
        block = section.split("```zsh\n", 1)[1].split("```", 1)[0] if "```zsh" in section else ""
        searches = [row.command for row in rows if row.label.startswith("Q")]
        if searches != [line for line in block.split("\n") if line.strip()]:
            print(f"  {spec.name}: the searches differ from its zsh block")
            return False
    for guide in guides:
        text = guide.read_text(encoding="utf-8")
        gates = read_rows(text, "2. Gates")
        found = read_rows(text, "5. Searches")
        if [row.label for row in gates] != [f"G{n}" for n in range(1, len(gates) + 1)]:
            print(f"  {guide.name}: gates {[row.label for row in gates]}")
            return False
        if [row.label for row in found] != [f"Q{n}" for n in range(1, len(found) + 1)]:
            print(f"  {guide.name}: searches {[row.label for row in found]}")
            return False
        if any("\\|" in row.command for row in gates + found) or not found:
            print(f"  {guide.name}: an escaped pipe was left in, or no searches")
            return False
    return True


def real_runners() -> bool:
    project = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "docs" / "phases").mkdir(parents=True)
    (project / "src" / "docket").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "docs" / "phases" / "phase-09z-probe.md").write_text(
        "## Acceptance\n\n| Command | Must show |\n|---|---|\n"
        "| `printf 'a\\nb\\n24 passed\\n'` | `24 passed` |\n"
        "| `false` | exit 1 |\n\n### Searches\n\n```zsh\ngit grep -n x -- nowhere\n```\n",
        encoding="utf-8",
    )
    module = project / "src" / "docket" / "x.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    (project / "tests" / "test_x.py").write_text(
        "from pathlib import Path\n\n\ndef test_value():\n"
        "    text = (Path(__file__).parent.parent / 'src' / 'docket' / 'x.py').read_text()\n"
        "    assert text == 'VALUE = 1\\n'\n",
        encoding="utf-8",
    )
    logs = project / "logs"
    accepted = subprocess.run(
        [PYTHON, "scripts/accept.py", "--phase", "9z", "--root", str(project), "--log-dir", logs],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    wanted = f"A1: 24 passed\nA2: empty (exit 1)\nQ1: empty\nLogs: {logs}\n"
    if accepted.stdout != wanted:
        print(f"  accept printed {accepted.stdout!r} {accepted.stderr[-200:]!r}")
        return False
    spotted = subprocess.run(
        [PYTHON, "scripts/spot_check.py", "src/docket/x.py", "--old", "1", "--new", "2"]
        + ["--test", "tests/test_x.py::test_value", "--row", "S1", "--root", str(project)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if spotted.returncode != 0 or not spotted.stdout.startswith("S1 fails: AssertionError"):
        print(f"  spot_check printed {spotted.stdout!r} {spotted.stderr[-200:]!r}")
        return False
    if module.read_text(encoding="utf-8") != "VALUE = 1\n":
        print("  spot_check left the module changed")
        return False
    return True


def quiet_check() -> bool:
    logs = Path(tempfile.mkdtemp()) / "check-logs"
    done = subprocess.run(
        [PYTHON, "scripts/check.py", "--quiet", "--section", "tooling", "--log-dir", str(logs)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = done.stdout.splitlines()
    shape = (
        done.returncode == 0
        and lines[0] == "Sections:"
        and lines[1].startswith("  tooling ")
        and lines[-2:] == ["Section tooling: passed.", f"Logs: {logs}"]
        and len(lines) == 4
    )
    if not shape or "passed" not in (logs / "section.log").read_text(encoding="utf-8"):
        print(f"  check.py printed {done.stdout[-300:]!r}")
        return False
    return True


check(f"{SPOTS} random spot checks always restore the module", spots)
if not ORACLE_ONLY:
    check(f"{ENTRIES} random progress entries leave the others as they were", entries)
    check("every committed spec and guide gives its rows", committed_docs)
    check("accept.py and spot_check.py work with their real runners", real_runners)
    check("check.py --quiet prints only its table, result and logs", quiet_check)

print(f"FAILURES {FAILURES}")
