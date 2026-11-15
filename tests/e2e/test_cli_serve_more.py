from pathlib import Path

import pytest
from keyring.errors import KeyringError

from tests.fakes import FakeKeychain
from tests.support import run


def test_a_bad_port_leaves_no_data_folder(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    result = run("serve")
    assert (result.exit_code, result.stderr) == (
        1,
        "DOCKET_WEB_PORT must be 1024 to 65535\n",
    )
    assert not (tmp_path / "data").exists()


def test_a_down_keychain_leaves_no_data_folder(fake_keychain: FakeKeychain, tmp_path: Path) -> None:
    fake_keychain.error = KeyringError("backend detail")
    result = run("serve")
    assert (result.exit_code, result.stderr) == (1, "keychain unavailable: client.email\n")
    assert not (tmp_path / "data").exists()
