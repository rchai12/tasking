from importlib import metadata

import docket
from tests.support import run


def test_version_prints_the_name_and_version() -> None:
    result = run("version")
    assert result.exit_code == 0
    assert result.output == "docket 0.1.0\n"


def test_the_package_version_matches_the_installed_one() -> None:
    assert docket.__version__ == metadata.version("docket") == "0.1.0"


def test_the_docket_command_runs_the_cli() -> None:
    (found,) = metadata.entry_points(group="console_scripts", name="docket")
    assert found.value == "docket.cli:app"
