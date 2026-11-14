"""Phase 0 probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-00.py

It installs its own fake keychain and temporary HOME and data folders before importing docket,
so it never reads the real Keychain or the real data folder.
"""

import os
import random
import stat
import subprocess
import tempfile
from pathlib import Path

import keyring.core
from keyring.backend import KeyringBackend
from keyring.compat import properties
from keyring.errors import KeyringError, PasswordSetError

FAILURES = 0


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


class Fake(KeyringBackend):
    def __init__(self) -> None:
        super().__init__()
        self.secrets: dict[tuple[str, str], str] = {}
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    @properties.classproperty
    def priority(cls) -> float:
        return 0

    def get_password(self, service, username):
        self.calls.append((service, username))
        if self.error is not None:
            raise self.error
        return self.secrets.get((service, username))

    def set_password(self, service, username, password):
        raise AssertionError("no writes")

    def delete_password(self, service, username):
        raise AssertionError("no deletes")


FAKE = Fake()
keyring.core._keyring_backend = FAKE
WORK = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(WORK / "home")
for key in list(os.environ):
    if key.startswith("DOCKET_"):
        del os.environ[key]

# Oracle: a secret name is 1 to 64 characters from this table, the first a lowercase letter.
FIRST = set("abcdefghijklmnopqrstuvwxyz")
REST = FIRST | set("0123456789._-")


def oracle_valid(name: str) -> bool:
    return 1 <= len(name) <= 64 and name[0] in FIRST and all(c in REST for c in name[1:])


assert oracle_valid("google.token")
assert oracle_valid("a" * 64)
assert not oracle_valid("a" * 65)
assert not oracle_valid("google.token\n")
assert not oracle_valid("googleé")
assert not oracle_valid("")
assert not oracle_valid("1google")
print("oracle: ok")

try:
    from docket import config, keychain  # noqa: E402
except ImportError:
    print("import docket.config and docket.keychain: FAIL")
    print("FAILURES 1")
    raise SystemExit(1) from None


def name_case(name: str) -> bool:
    FAKE.calls.clear()
    FAKE.error = None
    FAKE.secrets[("docket", name)] = "value-1"
    try:
        found = keychain.get_secret(name)
    except ValueError as error:
        return not oracle_valid(name) and str(error) == "invalid secret name" and FAKE.calls == []
    return oracle_valid(name) and found == "value-1"


for name in [
    "google.token\n",
    "google\ntoken",
    "googleé",
    "google٣",
    "ｇoogle",
    "google\t",
    "\ngoogle",
]:
    check(f"name {name!r}", lambda name=name: name_case(name))

BASE = "google.token"
EXTRA = "abcxyz09._-AZ /\\:é\n\t~*"
rng = random.Random(0)
for _ in range(40):
    where = rng.randrange(len(BASE) + 1)
    char = rng.choice(EXTRA)
    name = BASE[:where] + char + BASE[where:]
    check(f"name {name!r}", lambda name=name: name_case(name))


def hides(error: Exception) -> bool:
    FAKE.error = error
    try:
        keychain.get_secret("google.token")
    except keychain.KeychainUnavailable as raised:
        text = str(raised)
        return text == "keychain unavailable: google.token" and "value-1" not in repr(raised)
    finally:
        FAKE.error = None
    return False


check("a KeyringError subclass is hidden", lambda: hides(PasswordSetError("value-1")))
check("a bare KeyringError is hidden", lambda: hides(KeyringError("token value-1")))


def data_dir(value: str) -> Path:
    os.environ["DOCKET_DATA_DIR"] = value
    try:
        return config.get_settings().data_dir
    finally:
        del os.environ["DOCKET_DATA_DIR"]


check("'~' alone is the home folder", lambda: data_dir("~") == WORK / "home")
check("a trailing slash is dropped", lambda: data_dir(str(WORK / "x") + "/") == WORK / "x")


def refused(value: str) -> bool:
    try:
        data_dir(value)
    except config.ConfigError as error:
        return str(error) == "DOCKET_DATA_DIR must be an absolute path"
    return False


check("'data/~' is refused", lambda: refused("data/~"))
check("'.' is refused", lambda: refused("."))


def private_under(umask: int, name: str) -> bool:
    old = os.umask(umask)
    try:
        os.environ["DOCKET_DATA_DIR"] = str(WORK / name)
        found = config.prepare_data_dir(config.get_settings())
    finally:
        os.umask(old)
        del os.environ["DOCKET_DATA_DIR"]
    return stat.S_IMODE(found.stat().st_mode) == 0o700


check("private under umask 000", lambda: private_under(0o000, "u000"))
check("private under umask 077", lambda: private_under(0o077, "u077"))


def prepare_twice() -> bool:
    os.environ["DOCKET_DATA_DIR"] = str(WORK / "twice")
    try:
        first = config.prepare_data_dir(config.get_settings())
        second = config.prepare_data_dir(config.get_settings())
    finally:
        del os.environ["DOCKET_DATA_DIR"]
    return first == second == WORK / "twice"


check("prepare twice is harmless", prepare_twice)


def command(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(Path(".venv/bin/docket")), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "COLUMNS": "200"},
    )


check(
    "the installed command prints the version",
    lambda: command("version").stdout == "docket 0.1.0\n",
)
check(
    "the installed command lists version in help",
    lambda: "version" in command("--help").stdout,
)

print(f"FAILURES {FAILURES}")
