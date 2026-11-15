from pathlib import Path

import pytest

from tests.support import load_script

spot = load_script("spot_check")
MODULE = 'HOST = "127.0.0.1"\n'
RAISED = "/work/tests/unit/test_x.py:5: KeyError: 'l1'\n1 failed in 0.00s\n"
TEST = "tests/unit/test_x.py::test_host"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "src" / "docket").mkdir(parents=True)
    (tmp_path / "src" / "docket" / "web.py").write_text(MODULE, encoding="utf-8")
    return tmp_path


class Pytest:
    def __init__(self, root: Path, answer: tuple[int, str]) -> None:
        self.root = root
        self.answer = answer
        self.calls: list[tuple[str, Path, str]] = []

    def __call__(self, test: str, cwd: Path) -> tuple[int, str]:
        module = (self.root / "src" / "docket" / "web.py").read_text(encoding="utf-8")
        self.calls.append((test, cwd, module))
        return self.answer


def args(root: Path, *more: str) -> list[str]:
    return [
        "src/docket/web.py",
        "--old",
        '"127.0.0.1"',
        "--new",
        '"0.0.0.0"',
        "--test",
        TEST,
        "--root",
        str(root),
        *more,
    ]


def test_a_failing_test_is_one_line_and_the_module_comes_back(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = Pytest(root, (1, RAISED))
    assert spot.main(args(root, "--row", "S7"), run=runner) == 0
    assert capsys.readouterr().out == "S7 fails: KeyError: 'l1'\n"
    assert runner.calls == [(TEST, root, 'HOST = "0.0.0.0"\n')]
    assert (root / "src" / "docket" / "web.py").read_text(encoding="utf-8") == MODULE


def test_a_passing_test_exits_one(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert spot.main(args(root), run=Pytest(root, (0, "1 passed\n"))) == 1
    assert capsys.readouterr().out == "passes\n"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["src/docket/web.py", "--old", "x", "--new", "y", "--test", TEST],
            "Error: the old text must match exactly once: found 0\n",
        ),
        (
            ["tests/unit/test_x.py", "--old", "x", "--new", "y", "--test", TEST],
            "Error: the module must be under src/\n",
        ),
        (
            ["../src/docket/web.py", "--old", "x", "--new", "y", "--test", TEST],
            "Error: the module must be under src/\n",
        ),
    ],
    ids=["no-match", "a-test-file", "outside-the-root"],
)
def test_a_bad_change_runs_nothing(
    root: Path, capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_x.py").write_text("x = 1\n", encoding="utf-8")
    runner = Pytest(root, (0, ""))
    assert spot.main([*argv, "--root", str(root)], run=runner) == 2
    assert (capsys.readouterr().err, runner.calls) == (message, [])
    assert (root / "src" / "docket" / "web.py").read_text(encoding="utf-8") == MODULE
