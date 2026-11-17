"""Small jobs the phase-architect checklist repeats, each printing only what the next step needs.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py searches SPEC [--cwd DIR]
        Run each command of the spec's "### Searches" block in DIR (default: the repository) and
        print how many lines each one matched. Use it on today's code (expect 0s) and on a copy
        with planted lines (expect matches).

    Add --plant FILE to append each `path<TAB>line` of FILE to its file (in --cwd), run the
        searches, and restore every file exactly; each search should then match. `--plant auto`
        plants each catalog search's own line (SEARCHES); a phase's own search needs a FILE.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py context MODULE...
        Print the public outline of each module: signatures, dataclass fields, public constants.
        MODULE is a file path, `reminders`, or `docket.reminders`.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py clone 1h --scratch DIR
        Make (or remake) DIR/fail01h from the repository with the venv linked, and say whether
        `docket` imports from the clone.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py failcheck CLONE TEST...
        Run only these tests in the clone and print the summary and each distinct failure reason.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py stubcheck CLONE \
            [--stub src/docket/views.py=NAMES.py ...] -- TEST...
        In a throwaway copy of the clone (fail<NN>-names), append names-only stubs (generated
        from the tests' `from docket.<module> import` lines, or the --stub files), then print
        each test file's function and test counts, the distinct failure reasons, and every test
        that passes on the stub (a guard, or a weak test). The copy is deleted afterwards.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py promote CLONE FILE... \
            [--ignore TEST...]
        Copy given files from the clone into the repository, compare each byte for byte, then run
        the Start command (the whole suite without the --ignore files) and print its last line.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py new --id 1b \
            --slug tasks-store --title "Tasks store" --n 96 --given tests/unit/test_store.py \
            --create src/docket/store.py [--edit src/docket/cli.py] \
            [--searches network,output,clock,model,exclusions] [--sections core] [--out DIR]
        Write a spec skeleton with every fixed section filled (Start, Acceptance with the probe,
        the stop rule, the catalog searches); the architect replaces each TODO.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py lint SPEC GUIDE [--clone DIR]
        Check the spec and guide against each other and against what pytest collects in DIR (a
        throwaway copy with names-only stubs): per-file and total test counts, the Start and
        at-least counts, named paths existing, spot-check test ids, the searches, TODOs and
        banned wording. Prints `Lint OK.` or each problem. A test file git already tracks is an
        earlier one the phase edits and is not counted; `--promoted` counts every listed test file,
        for a phase already in the repository that edited no earlier test file.

    .venv/bin/python .claude/skills/phase-architect/phase_tools.py guide SPEC [--out FILE]
        Write the verification guide's fixed parts from a finished spec: Coder ran, Gates (the
        Start row as an at-least count), the probe section, Searches (catalog rules filled) and
        Verdict. Spot checks, the probe line and variations are left as TODO.

Only `clone`, `promote` and `--plant` write files: the clone, the given files, and planted lines
that are restored before it returns.
"""

import argparse
import ast
import filecmp
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def search_commands(spec: str) -> list[str]:
    lines = spec.splitlines()
    try:
        start = lines.index("### Searches")
    except ValueError:
        return []
    commands, inside = [], False
    for line in lines[start + 1 :]:
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside and line.strip():
            commands.append(line)
    return commands


def run_searches(spec_path: Path, cwd: Path) -> int:
    commands = search_commands(spec_path.read_text(encoding="utf-8"))
    if not commands:
        print("no ### Searches block")
        return 1
    for command in commands:
        done = subprocess.run(["zsh", "-c", command], cwd=cwd, capture_output=True, text=True)
        count = len([line for line in done.stdout.splitlines() if line.strip()])
        print(f"{count:3}  {command[:90]}")
    return 0


def auto_plants(spec_path: Path) -> list[tuple[str, str]]:
    """Each catalog search's own plant line, in the file it covers; phase searches need a file."""
    plants = []
    for command in search_commands(spec_path.read_text(encoding="utf-8")):
        entry = catalog_entry(command)
        if entry is None:
            print(f"no catalog plant (give --plant FILE): {command[:70]}")
            continue
        plants.append((plant_path(command), entry[1]))
    return plants


def plant_and_search(spec_path: Path, cwd: Path, plant: Path) -> int:
    planted: dict[Path, list[str]] = {}
    if str(plant) == "auto":
        lines = [(path, text) for path, text in auto_plants(spec_path)]
    else:
        text = plant.read_text(encoding="utf-8")
        lines = [tuple(line.split("\t", 1)) for line in text.splitlines() if line.strip()]
    for path, text in lines:
        planted.setdefault(cwd / path, []).append(text)
    saved = {path: path.read_bytes() if path.exists() else None for path in planted}
    try:
        for path, lines in planted.items():
            before = (saved[path] or b"").decode()
            if before and not before.endswith("\n"):
                before += "\n"
            path.write_text(before + "\n".join(lines) + "\n", encoding="utf-8")
        return run_searches(spec_path, cwd)
    finally:
        for path, content in saved.items():
            if content is None:
                path.unlink()
            else:
                path.write_bytes(content)
        print("planted lines removed")


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"def {node.name}({ast.unparse(node.args)}){returns}"


def module_path(name: Path) -> Path:
    """A file path as given; `reminders` or `docket.reminders` as its file in src/docket."""
    if name.suffix == ".py":
        return name
    return ROOT / "src" / "docket" / (str(name).removeprefix("docket.") + ".py")


def outline(path: Path) -> list[str]:
    lines = [f"== {path}"]
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                lines.append(signature(node))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            lines.append(f"class {node.name}({bases})" if bases else f"class {node.name}")
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    lines.append("    " + ast.unparse(item))
                elif isinstance(item, ast.FunctionDef) and (
                    not item.name.startswith("_") or item.name == "__init__"
                ):
                    lines.append("    " + signature(item))
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [ast.unparse(target) for target in targets]
            if all(name[0].isupper() and (name.isupper() or "_" not in name) for name in names):
                text = ast.unparse(node).replace("\n", " ")
                lines.append(text if len(text) <= 100 else text[:97] + "...")
    return lines


def clone_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": "src:.", "PYTHONDONTWRITEBYTECODE": "1"}


def make_clone(phase: str, scratch: Path) -> int:
    dest = scratch.resolve() / f"fail{file_id(phase)}"
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(["git", "clone", "-q", str(ROOT), str(dest)], check=True)
    (dest / ".venv").symlink_to(ROOT / ".venv")
    found = subprocess.run(
        [".venv/bin/python", "-c", "import docket; print(docket.__file__)"],
        cwd=dest,
        env=clone_env(),
        capture_output=True,
        text=True,
    ).stdout.strip()
    inside = Path(found).resolve().is_relative_to(dest)
    print(f"{dest}\ndocket imports from the clone: {'yes' if inside else 'NO: ' + found}")
    return 0 if inside else 1


def fail_check(clone: Path, tests: list[str]) -> int:
    done = subprocess.run(
        [".venv/bin/python", "-m", "pytest", "--no-cov", "-q", "-p", "no:cacheprovider", "-rfE"]
        + ["--tb=line", *tests],
        cwd=clone,
        env=clone_env(),
        capture_output=True,
        text=True,
    )
    lines = done.stdout.splitlines()
    reasons: Counter[str] = Counter()
    for line in lines:
        found = re.fullmatch(r"\S+:[0-9]+: (.*)", line)
        if found is not None:
            reasons[found.group(1)[:110]] += 1
    for reason, count in reasons.most_common():
        print(f"{count:4}  {reason}")
    print(lines[-1] if lines else "no output")
    return 0


def defined_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def missing_imports(root: Path, tests: list[str]) -> dict[str, list[str]]:
    """Names the given tests import from `docket.<module>` that the module doesn't define yet."""
    missing: dict[str, list[str]] = {}
    for test in tests:
        for node in ast.walk(ast.parse((root / test).read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("docket."):
                source = "src/" + node.module.replace(".", "/") + ".py"
                have = defined_names(root / source)
                for alias in node.names:
                    if alias.name not in have and alias.name not in missing.get(source, []):
                        missing.setdefault(source, []).append(alias.name)
    return missing


def stub_text(names: list[str]) -> str:
    """Names only: constants a placeholder, classes an exception, functions NotImplementedError."""
    lines = []
    for name in names:
        if name.isupper():
            lines.append(f'{name} = "stub"')
        elif name[:1].isupper():
            lines.append(f"class {name}(Exception):\n    pass")
        else:
            lines.append(f"def {name}(*args, **kwargs):\n    raise NotImplementedError")
    return "\n\n\n".join(lines) + "\n"


def stub_check(clone: Path, stubs: list[str], tests: list[str]) -> int:
    copy = clone.resolve().with_name(clone.resolve().name + "-names")
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(clone, copy, symlinks=True)
    try:
        if not stubs:
            for path, names in missing_imports(copy, tests).items():
                print(f"auto stub {path}: {', '.join(names)}")
                with (copy / path).open("a", encoding="utf-8") as handle:
                    handle.write("\n\n" + stub_text(names))
        for pair in stubs:
            path, _, stub = pair.partition("=")
            with (copy / path).open("a", encoding="utf-8") as handle:
                handle.write("\n" + Path(stub).read_text(encoding="utf-8"))
        for test in tests:
            done = subprocess.run(
                [".venv/bin/python", "-m", "pytest", "--collect-only", "-q"]
                + ["-p", "no:cacheprovider", test],
                cwd=copy,
                env=clone_env(),
                capture_output=True,
                text=True,
            )
            source = (copy / test).read_text(encoding="utf-8")
            functions = len(re.findall(r"^def test_", source, re.MULTILINE))
            last = done.stdout.splitlines()[-1] if done.stdout else "no output"
            print(f"{test}: {functions} functions, {last}")
        fail_check(copy, tests)
        passed = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "--no-cov", "-q", "-p", "no:cacheprovider", "-rA"]
            + tests,
            cwd=copy,
            env=clone_env(),
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        for line in passed:
            if line.startswith("PASSED "):
                print(f"  passes on the stub: {line.removeprefix('PASSED ')}")
    finally:
        shutil.rmtree(copy)
    return 0


def collected_ids(clone: Path, tests: list[str]) -> dict[str, list[str]]:
    """Every test id per file, collected in a throwaway copy with names-only stubs."""
    copy = clone.resolve().with_name(clone.resolve().name + "-lint")
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(clone, copy, symlinks=True)
    try:
        for path, names in missing_imports(copy, tests).items():
            with (copy / path).open("a", encoding="utf-8") as handle:
                handle.write("\n\n" + stub_text(names))
        done = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
            + tests,
            cwd=copy,
            env=clone_env(),
            capture_output=True,
            text=True,
        )
    finally:
        shutil.rmtree(copy)
    ids: dict[str, list[str]] = {test: [] for test in tests}
    for line in done.stdout.splitlines():
        path, _, _ = line.partition("::")
        if path in ids:
            ids[path].append(line)
    return ids


def lint(spec_path: Path, guide_path: Path, clone: Path, promoted: bool = False) -> int:
    """Check a spec and its guide against each other and against what pytest collects."""
    spec = spec_path.read_text(encoding="utf-8")
    guide = guide_path.read_text(encoding="utf-8")
    problems: list[str] = []
    for name, text in (("spec", spec), ("guide", guide)):
        for number, line in enumerate(text.splitlines(), start=1):
            if "TODO" in line:
                problems.append(f"{name}:{number}: a TODO is left")
            for word in BANNED:
                if word in line.lower():
                    problems.append(f"{name}:{number}: banned wording {word!r}")
    if not spec.startswith("# Phase "):
        problems.append("spec:1: must start with '# Phase <id>: <title>'")
    given_rows = table_rows(section(spec, "## Given files"))
    given = [path for row in given_rows for path in paths_in(row[0])]
    for row in table_rows(section(spec, "## Scope")):
        if row[1].startswith("edit"):
            given += paths_in(row[0])
    for path in given:
        if not (clone / path).exists():
            problems.append(f"spec: {path} is named but does not exist in the clone")
    diff_rows = [
        row[0] for row in table_rows(section(spec, "## Acceptance")) if "git diff" in row[0]
    ]
    for path in [path for row in given_rows for path in paths_in(row[0])]:
        if not any(path in row for row in diff_rows):
            problems.append(
                f"spec: given file {path} is missing from the `git diff HEAD --stat` row"
            )
    tests = [path for path in given if Path(path).name.startswith("test_") and path.endswith(".py")]
    tests = [path for path in tests if any(path in row[0] for row in given_rows)]
    if not promoted:
        tests = [path for path in tests if path not in tracked(clone, tests)]
    ids = collected_ids(clone, tests)
    total = sum(len(found) for found in ids.values())
    for row in given_rows:
        stated = re.search(r"([0-9]+) tests from ([0-9]+) functions", row[1])
        files = [path for path in paths_in(row[0]) if path in ids]
        if stated and len(files) == 1:
            source = (clone / files[0]).read_text(encoding="utf-8")
            functions = len(re.findall(r"^def test_", source, re.MULTILINE))
            found = (len(ids[files[0]]), functions)
            if found != (int(stated.group(1)), int(stated.group(2))):
                problems.append(f"spec: {files[0]} has {found[0]} tests from {found[1]} functions")
    count = re.search(r"Given test count: \*\*([0-9]+)\*\*", spec)
    if count is None or int(count.group(1)) != total:
        problems.append(f"spec: the given test count should be {total}")
    base = re.search(r"N is ([0-9]+),", spec)
    if base is not None:
        n = int(base.group(1))
        start = re.search(r"Start: `[^`]+` must show `([0-9]+) passed`", spec)
        if start is None or int(start.group(1)) != n:
            problems.append(f"spec: the Start count should be {n}")
        least = re.search(r"at least ([0-9]+) passed", section(spec, "## Acceptance"))
        if least is None or int(least.group(1)) != n + total:
            problems.append(f"spec: acceptance should say at least {n + total} passed")
    if f"`{total} passed`" not in section(spec, "## Acceptance"):
        problems.append(f"spec: acceptance should name `{total} passed` for the given tests")
    wanted = [gate_row(row) for row in table_rows(section(spec, "## Acceptance"))]
    gates = [" | ".join(row[1:3]) for row in table_rows(section(guide, "## 2. Gates"))]
    if gates[: len(wanted)] != wanted:
        problems.append("guide: its gates differ from the spec's acceptance (regenerate the guide)")
    known = {line for found in ids.values() for line in found}
    for test_id in re.findall(r"`(tests/[^`]+::[^`]+)`", guide):
        if test_id not in known:
            problems.append(f"guide: {test_id} is not a collected test id")
    if search_commands(spec) != [
        cell.strip("`").replace("\\|", "|")
        for row in table_rows(section(guide, "## 5. Searches"))
        for cell in row[2:3]
    ]:
        problems.append("guide: its searches differ from the spec's")
    for problem in problems:
        print(problem)
    print("Lint OK." if not problems else f"{len(problems)} problems.")
    return 1 if problems else 0


def promote(clone: Path, files: list[str], ignore: list[str]) -> int:
    differ = []
    for name in files:
        (ROOT / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(clone / name, ROOT / name)
        if not filecmp.cmp(clone / name, ROOT / name, shallow=False):
            differ.append(name)
    print(f"copied {len(files)}; differ: {', '.join(differ) or 'none'}")
    done = subprocess.run(
        [".venv/bin/python", "-m", "pytest", "--no-cov", "-q", "-p", "no:cacheprovider"]
        + [f"--ignore={name}" for name in ignore],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
    )
    lines = done.stdout.splitlines()
    print("Start:", lines[-1] if lines else "no output")
    return 1 if differ else 0


# Searches every phase draws from: name -> (rule, command, plant line). `{modules}` is the
# phase's own source modules. The plant line goes into the first file the command names, or into
# src/docket/_planted.py when it names only folders, and must make that search match.
SEARCHES: dict[str, tuple[str, str, str]] = {
    "network": (
        "no network code",
        "git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)"
        "|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src",
        "import httpx",
    ),
    "output": (
        "no output outside the CLI",
        "git grep --untracked -n -E 'print\\(|logging|logger|warnings\\.warn' -- src"
        " ':!src/docket/cli.py'",
        "print(1)",
    ),
    "clock": (
        "time read only in clock.py, through the module",
        "git grep --untracked -n -E 'datetime\\.now|datetime\\.utcnow|date\\.today|time\\.time\\(|"
        "from docket\\.(clock|ids) import' -- src ':!src/docket/clock.py'",
        "x = datetime.now()",
    ),
    "writes": (
        "only the core writes tasks, audit rows, links and keys",
        "git grep --untracked -n -E "
        "'\\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\\(' -- src"
        " ':!src/docket/core.py' ':!src/docket/store.py'",
        'store.insert_task(title="x")',
    ),
    "owner": (
        "the command line acts only as the owner",
        "git grep --untracked -n -E 'actor=.(agent|email).' -- src/docket/cli.py",
        'change_state(store, "t1", "done", actor="agent")',
    ),
    "environment": (
        "no environment, machine zone or locale in this phase's modules",
        "git grep --untracked -n -E 'os\\.environ|getenv\\(|strftime\\(|import locale'"
        " -- {modules}",
        'zone = os.environ["TZ"]',
    ),
    "machine-zone": (
        "nothing reads the machine's time zone",
        "git grep --untracked -n -E 'tzlocal|time\\.tzname|localtime\\(|astimezone\\(\\)|"
        "environ\\[.TZ.\\]' -- src",
        "zone = time.tzname[0]",
    ),
    "model": (
        "no model client",
        "git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src",
        "import ollama",
    ),
    "exclusions": (
        "no coverage or lint exclusions in this phase's modules",
        "git grep --untracked -n -E 'pragma: no cover|noqa' -- {modules}",
        "x = 1  # noqa",
    ),
}
DEFAULT_SEARCHES = "network,output,clock,model,exclusions"
BANNED = ("as appropriate", "or similar", "if needed", "etc.")


def expand_search(name: str, modules: list[str]) -> str:
    if name not in SEARCHES:
        raise SystemExit(f"unknown search {name!r}; known: {', '.join(SEARCHES)}")
    return SEARCHES[name][1].replace("{modules}", " ".join(modules) or "src")


def catalog_entry(command: str) -> tuple[str, str] | None:
    """The catalog's (rule, plant line) for an expanded command, or None for a phase's own."""
    for rule, template, plant in SEARCHES.values():
        before, marker, after = template.partition("{modules}")
        if command == template:
            return rule, plant
        if marker and command.startswith(before) and command.endswith(after):
            return rule, plant
    return None


def plant_path(command: str) -> str:
    _, _, paths = command.partition(" -- ")
    for token in paths.split():
        token = token.strip("'")
        if token.endswith(".py") and not token.startswith(":!"):
            return token
    return "src/docket/_planted.py"


def tracked(root: Path, paths: list[str]) -> set[str]:
    """The paths git already tracks in root: an earlier file the phase edits, not a new one."""
    done = subprocess.run(
        ["git", "ls-files", "--", *paths], cwd=root, capture_output=True, text=True, check=False
    )
    return set(done.stdout.split())


def file_id(phase: str) -> str:
    found = re.fullmatch(r"(0|[1-9][0-9]*)([a-z]?)", phase)
    if found is None:
        raise SystemExit("phase id must look like 0 or 1b")
    return f"{int(found.group(1)):02d}{found.group(2)}"


def spec_skeleton(args: argparse.Namespace) -> str:
    padded = file_id(args.id)
    probe = f"docs/verification/probe-{padded}.py"
    args.given = [path for path in args.given if path != probe]  # the template adds it
    tests = [path for path in args.given if Path(path).name.startswith("test_")]
    earlier = tracked(ROOT, tests)
    given_tests = [path for path in tests if path not in earlier]
    modules = [path for path in [*args.create, *args.edit] if path.startswith("src/")]
    ignores = " ".join(f"--ignore={path}" for path in given_tests)
    start = f".venv/bin/python -m pytest --no-cov -q {ignores}"
    given_rows = "\n".join(f"| `{path}` | TODO |" for path in args.given)
    scope_rows = "\n".join(
        [f"| `{path}` | create |" for path in args.create]
        + [f"| `{path}` | edit: TODO |" for path in args.edit]
    )
    names = [name for name in args.searches.split(",") if name]
    searches = "\n".join(expand_search(name, modules) for name in names)
    return f"""# Phase {args.id}: {args.title}

## Goal

TODO: one paragraph: what this phase makes possible, and what it leaves for later.

Sections: `{args.sections}`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is {args.n}, the tests the previous phase left passing.

Start: `{start}` must show `{args.n} passed`. The ignored files import names you create.

## Facts

TODO: what spikes and the library's code showed, each checked on this machine.

## Owner's decisions

TODO

## Architect's decisions

TODO

## Requirements

1. TODO

N. **Progress entry** for `## Phase {args.id}: {args.title} (YYYY-MM-DD)` at the end of \
`docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
{given_rows}
| `{probe}` | The verifier's probe |

Given test count: **TODO**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests \
in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
{scope_rows}
| `docs/progress.md` | append your entry |

## Out of scope

- TODO: what a capable coder would over-deliver.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- TODO: the project rules this phase could break.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never \
`from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up \
(`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `{start}` (before you start) | `{args.n} passed` |
| `.venv/bin/python scripts/check.py --first {args.sections}` | last line `All checks passed.`; \
summary lists `tests ({args.sections}): passed`; at least TODO passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest {" ".join(given_tests)} --no-cov -q` | `TODO passed` |
| `.venv/bin/python -m coverage report --include={",".join(modules) or "TODO"} --fail-under=100`, \
right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python {probe}` | last line `FAILURES 0` |
| `grep -c "^## Phase {args.id}: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase {args.id}` | `Reports OK.` |
| `git diff HEAD --stat -- {" ".join(args.given)} {probe}` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
{searches}
```
"""


def section(text: str, heading: str) -> str:
    """The text under a heading line (matched at a line's start), up to the next heading."""
    found = re.search(rf"^{re.escape(heading)}[ \t]*$", text, flags=re.MULTILINE)
    if found is None:
        raise ValueError(f"no heading line: {heading}")
    start = found.end()
    following = re.search(r"^#{2,3} ", text[start:], flags=re.MULTILINE)
    return text[start : start + following.start()] if following else text[start:]


def table_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip("|"))]
            rows.append(cells)
    return rows[1:]


def paths_in(cell: str) -> list[str]:
    paths, folder = [], ""
    for name in re.findall(r"`([^`]+)`", cell):
        if "/" in name:
            folder = name.rsplit("/", 1)[0] + "/"
            paths.append(name)
        else:
            paths.append(folder + name)
    return paths


def guide_from_spec(spec_path: Path) -> str:
    spec = spec_path.read_text(encoding="utf-8")
    head = re.match(r"# Phase ([0-9]+[a-z]?): (.+)", spec)
    if head is None:
        raise SystemExit("the spec must start with '# Phase <id>: <title>'")
    phase, title = head.groups()
    padded = file_id(phase)
    given = [p for row in table_rows(section(spec, "## Given files")) for p in paths_in(row[0])]
    scope = table_rows(section(spec, "## Scope"))
    created = [paths_in(row[0])[0] for row in scope if row[1] == "create"]
    acceptance = table_rows(section(spec, "## Acceptance"))
    searches = search_commands(spec)
    search_intro = section(spec, "### Searches").strip().splitlines()[0]
    count = re.search(r"Given test count: \*\*([0-9]+)\*\*", spec)
    tracked = " ".join([f"docs/phases/{spec_path.name}", *given])
    gates = "\n".join(
        f"| G{number} | {gate_row(row)} |" for number, row in enumerate(acceptance, start=1)
    )
    last = len(acceptance) + 1
    search_rows = "\n".join(
        f"| Q{number} | {(catalog_entry(command) or ('TODO',))[0]} | "
        f"`{command.replace('|', chr(92) + '|')}` |"
        for number, command in enumerate(searches, start=1)
    )
    present = "\n".join(f"- `{path}`" for path in created)
    return f"""# Verification guide: Phase {phase} ({title})

Spec: `docs/phases/{spec_path.name}`. Follow `docs/phase-conventions.md` ("For the verifier"). \
Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email \
service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

{present}
- `grep -c "^## Phase {phase}: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with \
`Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, \
`git status --short` tells "the coder did not run" (no Scope path changed) from "the coder \
broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch {tracked}` \
fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase \
{phase} --guide` runs them and the searches, one line each. Given test count: \
{count.group(1) if count else "TODO"}.

| # | Command | Must show |
|---|---|---|
{gates}
| G{last} | `.venv/bin/python -m pip list --format=freeze \\| wc -l` | `TODO` (the count before \
this phase, plus each package the spec adds) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder \
wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test \
'<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with \
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm \
it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is \
as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | TODO | TODO | TODO | TODO | TODO |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-{padded}.py` from the repository root. It is a given \
file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at \
the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it \
under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

TODO: one line on what the probe checks that the given tests do not.

## 5. Searches

{search_intro} A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
{search_rows}

(In the table, `\\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- TODO
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/{spec_path.name}` in the form `docs/phase-conventions.md` gives \
(`# Review: Phase {phase}`), then run `.venv/bin/python scripts/check_reports.py --phase {phase}`; \
it must print `Reports OK.`
"""


def gate_row(row: list[str]) -> str:
    """A spec's acceptance row as a gate; the coder's Start row becomes an at-least count."""
    command, shows = row[0], row[1]
    found = re.fullmatch(r"(`[^`]+`) \(before you start\)", command)
    passed = re.fullmatch(r"`([0-9]+) passed`", shows)
    if found and passed:
        return (
            f"{found.group(1)} | at least {passed.group(1)} passed, 0 failed (the coder's "
            "`*_more.py` tests add to the count)"
        )
    return f"{command} | {shows}"


def target(out: Path | None, name: str) -> Path | None:
    """`--out` may name a folder (the file keeps its phase name) or the file itself."""
    return out / name if out is not None and out.is_dir() else out


def write(text: str, out: Path | None) -> int:
    if out is None:
        print(text, end="")
    else:
        out.write_text(text, encoding="utf-8")
        todos = text.count("TODO")
        print(f"wrote {out} ({len(text.splitlines())} lines, {todos} TODO)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    searches = commands.add_parser("searches")
    searches.add_argument("spec", type=Path)
    searches.add_argument("--cwd", type=Path, default=ROOT)
    searches.add_argument("--plant", type=Path)
    context = commands.add_parser("context")
    context.add_argument("modules", nargs="+", type=Path)
    clone = commands.add_parser("clone")
    clone.add_argument("id")
    clone.add_argument("--scratch", type=Path, required=True)
    failcheck = commands.add_parser("failcheck")
    failcheck.add_argument("clone", type=Path)
    failcheck.add_argument("tests", nargs="+")
    stubcheck = commands.add_parser("stubcheck")
    stubcheck.add_argument("clone", type=Path)
    stubcheck.add_argument("--stub", nargs="+", default=[], metavar="PATH=STUBFILE")
    stubcheck.add_argument("tests", nargs="+")
    linter = commands.add_parser("lint")
    linter.add_argument("spec", type=Path)
    linter.add_argument("guide", type=Path)
    linter.add_argument("--clone", type=Path, default=ROOT)
    linter.add_argument("--promoted", action="store_true")
    given = commands.add_parser("promote")
    given.add_argument("clone", type=Path)
    given.add_argument("files", nargs="+")
    given.add_argument("--ignore", nargs="+", default=[])
    new = commands.add_parser("new")
    new.add_argument("--id", required=True)
    new.add_argument("--slug", required=True)
    new.add_argument("--title", required=True)
    new.add_argument("--n", required=True, type=int)
    new.add_argument("--sections", default="core")
    new.add_argument("--given", nargs="+", default=[])
    new.add_argument("--create", nargs="+", default=[])
    new.add_argument("--edit", nargs="+", default=[])
    new.add_argument("--searches", default=DEFAULT_SEARCHES)
    new.add_argument("--out", type=Path)
    guide = commands.add_parser("guide")
    guide.add_argument("spec", type=Path)
    guide.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "searches":
        if args.plant is not None:
            return plant_and_search(args.spec, args.cwd, args.plant)
        return run_searches(args.spec, args.cwd)
    if args.command == "context":
        for module in args.modules:
            print("\n".join(outline(module_path(module))))
        return 0
    if args.command == "clone":
        return make_clone(args.id, args.scratch)
    if args.command == "failcheck":
        return fail_check(args.clone, args.tests)
    if args.command == "lint":
        return lint(args.spec, args.guide, args.clone, args.promoted)
    if args.command == "stubcheck":
        return stub_check(args.clone, args.stub, args.tests)
    if args.command == "promote":
        return promote(args.clone, args.files, args.ignore)
    if args.command == "new":
        name = f"phase-{file_id(args.id)}-{args.slug}.md"
        return write(spec_skeleton(args), target(args.out, name))
    return write(guide_from_spec(args.spec), target(args.out, args.spec.name))


if __name__ == "__main__":
    sys.exit(main())
