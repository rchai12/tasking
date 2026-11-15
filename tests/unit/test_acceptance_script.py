from pathlib import Path

import pytest

from tests.support import load_script

accept = load_script("accept")
SPEC = """\
## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest -q` | `24 passed` |

### Searches

```zsh
git grep -n -E 'ollama' -- src
```
"""
GUIDE = """\
## 2. Gates

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python docs/verification/probe-09z.py` | `FAILURES 0` |

## 5. Searches

| # | Rule | Command |
|---|---|---|
| Q1 | no model client | `git grep -n -E 'ollama\\|openai' -- src` |
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A project folder apart from `tmp_path`, which the settings fixture makes the working one."""
    project = tmp_path / "project"
    (project / "docs" / "phases").mkdir(parents=True)
    (project / "docs" / "verification").mkdir()
    (project / "docs" / "phases" / "phase-09z-example.md").write_text(SPEC, encoding="utf-8")
    (project / "docs" / "verification" / "phase-09z-example.md").write_text(GUIDE, encoding="utf-8")
    return project


class Shell:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, command: str, cwd: Path) -> tuple[int, str]:
        self.calls.append((command, cwd))
        return (0, "FAILURES 0\n") if "probe" in command else (0, "")


def test_the_spec_rows_run_from_the_root(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell()
    logs = tmp_path / "logs"
    argv = ["--phase", "9z", "--root", str(root), "--log-dir", str(logs)]
    assert accept.main(argv, run=shell) == 0
    assert shell.calls == [
        (".venv/bin/python -m pytest -q", root),
        ("git grep -n -E 'ollama' -- src", root),
    ]
    assert capsys.readouterr().out == f"A1: empty\nQ1: empty\nLogs: {logs}\n"


def test_the_guide_rows_are_its_gates_then_its_searches(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell()
    logs = tmp_path / "logs"
    argv = ["--phase", "9z", "--guide", "--root", str(root), "--log-dir", str(logs)]
    assert accept.main(argv, run=shell) == 0
    assert [command for command, _ in shell.calls] == [
        ".venv/bin/python docs/verification/probe-09z.py",
        "git grep -n -E 'ollama|openai' -- src",
    ]
    assert capsys.readouterr().out == f"G1: FAILURES 0\nQ1: empty\nLogs: {logs}\n"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--phase", "9y"], "Error: no spec for phase 9y\n"),
        (["--phase", "9y", "--guide"], "Error: no guide for phase 9y\n"),
        (["--phase", "9Z"], "Error: phase must be a phase id such as 0 or 5a\n"),
    ],
    ids=["no-spec", "no-guide", "bad-id"],
)
def test_a_phase_without_its_file_is_refused(
    root: Path, capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    shell = Shell()
    assert accept.main([*argv, "--root", str(root)], run=shell) == 2
    assert (capsys.readouterr().err, shell.calls) == (message, [])
