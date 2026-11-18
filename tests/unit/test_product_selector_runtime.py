import shlex

from tests.product_consolidation_cases import MANIFEST, run_pytest

PHASE_1E = 1
PHASE_2D = 3


def _passed(index: int, count: int) -> None:
    command = shlex.split(MANIFEST["selections"][index]["after"])[3:]
    done = run_pytest(command, collect=False)
    assert done.returncode == 0, done.stdout[-1600:] + done.stderr[-500:]
    summary = next(line for line in done.stdout.splitlines() if " passed" in line)
    assert summary.startswith(f"{count} passed")
    assert "failed" not in summary
    assert "error" not in summary
    assert "skipped" not in summary


def test_the_phase_1e_given_selector_passes_66() -> None:
    _passed(PHASE_1E, 66)


def test_the_phase_2d_given_selector_passes_24() -> None:
    _passed(PHASE_2D, 24)
