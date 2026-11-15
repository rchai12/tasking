"""Phase 2d probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-02d.py

It tries 400 random start-ups (the port setting, the keychain, the email token and the store each
good or bad) and checks each against the start-up's own order of refusals: a refused start-up
calls no server and, when it stops before the store, leaves no database behind. A start-up that
passes serves only on 127.0.0.1. Then it serves the built app over real loopback twice, with a
restart between, and checks that a repeated request creates one task and that the task survives.
`--oracle-only` prints the reach counts from the rules alone, for the architect.
It uses temporary folders, an in-memory keychain and 127.0.0.1 only; no real Keychain or data.
"""

import os
import random
import socket
import sqlite3
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import keyring.core
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
STEPS = 400
PORTS = ["8767", "9000", "1024", "65535", "80", "1023", "65536", "x"]
BODY = {
    "source": "email",
    "title": "Pay rent",
    "deadline": None,
    "provider": "gmail",
    "message_id": "personal/1",
    "link": "https://mail.example/1",
}


def expected(port: str, keychain_up: bool, has_token: bool, schema: str) -> str:
    """The first refusal a start-up meets, or "started"."""
    if not (port.isdigit() and 1024 <= int(port) <= 65535):
        return "bad-port"
    if not keychain_up:
        return "keychain-down"
    if not has_token:
        return "no-clients"
    if schema == "newer":
        return "newer-store"
    return "started"


assert expected("80", False, False, "newer") == "bad-port"
assert expected("8767", False, False, "newer") == "keychain-down"
assert expected("8767", True, False, "newer") == "no-clients"
assert expected("65535", True, True, "newer") == "newer-store"
assert expected("1024", True, True, "current") == "started"
print("oracle: ok")


class ProbeKeychain(KeyringBackend):
    priority = 0  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.secrets: dict[tuple[str, str], str] = {}
        self.up = True

    def get_password(self, service: str, username: str) -> str | None:
        if not self.up:
            raise KeyringError("probe keychain down")
        return self.secrets.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.secrets[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        raise KeyringError("probe never deletes")


KEYCHAIN = ProbeKeychain()
keyring.core._keyring_backend = KEYCHAIN


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


def fresh_folder(schema: str) -> Path:
    data = Path(tempfile.mkdtemp()) / "data"
    os.environ["DOCKET_DATA_DIR"] = str(data)
    if schema != "absent":
        data.mkdir(mode=0o700)
        connection = sqlite3.connect(data / "docket.sqlite3")
        connection.execute(f"PRAGMA user_version = {99 if schema == 'newer' else 0}")
        connection.close()
    return data


def start_up() -> tuple[str, list[dict[str, object]]]:
    """Runs `docket serve` with uvicorn replaced; returns its outcome and the run calls."""
    import uvicorn
    from typer.testing import CliRunner

    from docket.cli import app

    calls: list[dict[str, object]] = []
    real = uvicorn.run
    uvicorn.run = lambda served, **kwargs: calls.append(kwargs)
    try:
        result = CliRunner().invoke(app, ["serve"])
    finally:
        uvicorn.run = real
    return f"{result.exit_code}:{result.stderr.strip()}", calls


MESSAGES = {
    "bad-port": "1:DOCKET_WEB_PORT must be 1024 to 65535",
    "keychain-down": "1:keychain unavailable: client.email",
    "no-clients": "1:No clients yet: run docket clients add email.",
    "newer-store": "1:unsupported schema version: 99",
    "started": "0:",
}


def walk() -> bool:
    rng = random.Random(42)
    reached = dict.fromkeys(MESSAGES, 0)
    for step in range(STEPS):
        port = rng.choice(PORTS[:4]) if rng.random() < 0.6 else rng.choice(PORTS)
        keychain_up = rng.random() < 0.85
        has_token = rng.random() < 0.8
        schema = rng.choice(["absent", "current", "newer"])
        wanted = expected(port, keychain_up, has_token, schema)
        reached[wanted] += 1
        if ORACLE_ONLY:
            continue
        os.environ["DOCKET_WEB_PORT"] = port
        data = fresh_folder(schema)
        KEYCHAIN.up = True
        KEYCHAIN.secrets.clear()
        if has_token:
            from docket.clients import issue_token

            issue_token("email")
        KEYCHAIN.up = keychain_up
        outcome, calls = start_up()
        if outcome != MESSAGES[wanted]:
            print(f"  step {step}: {port} {keychain_up} {has_token} {schema}: {outcome!r}")
            return False
        if wanted == "started":
            if [(call["host"], call["port"]) for call in calls] != [("127.0.0.1", int(port))]:
                print(f"  step {step}: served with {calls}")
                return False
        elif calls:
            print(f"  step {step}: a refused start-up called the server")
            return False
        if wanted != "newer-store" and wanted != "started" and schema == "absent":
            if data.exists():
                print(f"  step {step}: a refused start-up made the data folder")
                return False
    if ORACLE_ONLY:
        print(f"  reached {reached}")
        return True
    if not all(value >= 30 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve_once(token: str, port: int) -> list[tuple[int, object]]:
    import httpx2
    import uvicorn

    from docket.config import get_settings
    from docket.server import build_app

    app = build_app(get_settings())
    running = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    answers = []
    try:
        for _ in range(250):
            if running.started:
                break
            time.sleep(0.02)
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "gmail:personal/1"}
        for _ in range(2):
            answer = httpx2.post(f"http://127.0.0.1:{port}/tasks", json=BODY, headers=headers)
            answers.append((answer.status_code, answer.json()))
    finally:
        running.should_exit = True
        thread.join(timeout=10)
    return answers


def restart() -> bool:
    from docket import clock
    from docket.clients import issue_token

    start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
    count = [0]

    def now() -> datetime:
        count[0] += 1
        return start + timedelta(seconds=count[0])

    clock.now = now
    port = free_port()
    os.environ["DOCKET_WEB_PORT"] = str(port)
    data = fresh_folder("absent")
    KEYCHAIN.up = True
    KEYCHAIN.secrets.clear()
    token = issue_token("email")
    first = serve_once(token, port)
    second = serve_once(token, port)
    rows = sqlite3.connect(data / "docket.sqlite3").execute("SELECT number, title FROM tasks").fetchall()
    if first[0][0] != 201 or {answer[1]["id"] for answer in first + second} != {"t1"}:
        print(f"  answers {first} {second}")
        return False
    if rows != [(1, "Pay rent")]:
        print(f"  rows {rows}")
        return False
    return True


check(f"{STEPS} random start-ups follow the order of refusals", walk)
if not ORACLE_ONLY:
    check("a repeated request across a restart makes one task, and it survives", restart)

print(f"FAILURES {FAILURES}")
