"""Phase 2c probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-02c.py

It sends 2000 random requests (host, method, path, token, size, key and body each good or bad)
through FastAPI's test client and checks each answer against the web layer's own order of checks;
a request that passes them all must get one of intake's answers. Every answer is JSON with only
`id` or `error`, never a 500, and a store is opened only for a request that reaches intake.
`--oracle-only` prints the reach counts from the rules alone, for the architect.
It uses temporary folders and touches no network, Keychain or real data folder.
"""

import json
import random
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
STEPS = 2000
TOKEN = "tok-email-0123456789abcdefghijklmnopqrstuvw"
HOSTS = ["127.0.0.1:8767", "localhost:8767", "example.com", "127.0.0.1:9999", "localhost"]
PATHS = ["/tasks", "/tasks/t1/links", "/tasks/t99999/links", "/", "/tasks/t1", "/proposals"]
AUTH = [f"Bearer {TOKEN}", None, "Bearer nope", f"bearer {TOKEN}", f"Bearer {TOKEN} "]
BODY = {
    "source": "email",
    "title": "Pay rent",
    "deadline": None,
    "provider": "gmail",
    "message_id": "personal/1",
    "link": "https://mail.example/1",
}
LINK = {"source": "email", "provider": "gmail", "message_id": "personal/2", "link": "https://m/2"}
INTAKE = {200, 201, 400, 404, 409, 422}


def expected(host, method, path, auth, size, key, parses):
    """The web layer's answer, or None when the request reaches intake."""
    if host not in ("127.0.0.1:8767", "localhost:8767"):
        return 400, "wrong_host"
    if method != "POST" or path not in ("/tasks", "/tasks/t1/links", "/tasks/t99999/links"):
        return 404, "not_found"
    if auth != f"Bearer {TOKEN}":
        return 401, "unauthorized"
    if size > 65536:
        return 413, "too_large"
    if key is None or not 1 <= len(key) <= 200:
        return 400, "missing_key"
    if not parses:
        return 422, "invalid_json"
    return None


assert expected("example.com", "GET", "/", None, 9, None, False) == (400, "wrong_host")
assert expected("localhost:8767", "GET", "/tasks", None, 9, None, False) == (404, "not_found")
assert expected("localhost:8767", "POST", "/tasks", None, 9, None, False) == (401, "unauthorized")
assert expected("localhost:8767", "POST", "/tasks", f"Bearer {TOKEN}", 70000, None, False)[0] == 413
assert expected("localhost:8767", "POST", "/tasks", f"Bearer {TOKEN}", 9, "k", True) is None
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


def content_for(rng: random.Random, path: str) -> tuple[bytes, bool]:
    roll = rng.random()
    if roll < 0.1:
        return b"{", False
    if roll < 0.15:
        return b"\xff\xfe", False
    if roll < 0.2:
        text = json.dumps(BODY)
        return (text + " " * (65537 - len(text))).encode(), True
    body = dict(LINK if "links" in path else BODY)
    if rng.random() < 0.3:
        body[rng.choice(list(body))] = rng.choice([None, 7, "", ["x"], "Pay rent today"])
    return json.dumps(body).encode(), True


def walk() -> bool:
    rng = random.Random(81)
    reached = {
        "400-host": 0,
        "404": 0,
        "401": 0,
        "413": 0,
        "400-key": 0,
        "422-json": 0,
        "intake": 0,
    }
    if not ORACLE_ONLY:
        from fastapi.testclient import TestClient

        from docket import clock, core
        from docket.store import Store
        from docket.web import create_app

        start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
        count = [0]

        def now() -> datetime:
            count[0] += 1
            return start + timedelta(seconds=count[0])

        clock.now = now
        path_on_disk = Path(tempfile.mkdtemp()) / "docket.sqlite3"
        with Store(path_on_disk) as store:
            core.create_task(store, title="Seed", source="owner")
        opened = [0]

        def open_store() -> Store:
            opened[0] += 1
            return Store(path_on_disk)

        app = create_app(open_store=open_store, tokens={TOKEN: "email"}, port=8767)
        client = TestClient(app, base_url="http://127.0.0.1:8767", raise_server_exceptions=False)
    for step in range(STEPS):
        good = rng.random() < 0.55
        host = HOSTS[0] if good or rng.random() < 0.5 else rng.choice(HOSTS)
        method = "POST" if good or rng.random() < 0.6 else rng.choice(["GET", "PUT", "DELETE"])
        path = rng.choice(PATHS[:3]) if good or rng.random() < 0.5 else rng.choice(PATHS)
        auth = AUTH[0] if good or rng.random() < 0.5 else rng.choice(AUTH)
        key = (
            f"k{rng.randrange(40)}"
            if good or rng.random() < 0.6
            else rng.choice([None, "", "k" * 201])
        )
        content, parses = content_for(rng, path)
        wanted = expected(host, method, path, auth, len(content), key, parses)
        name = (
            {
                "wrong_host": "400-host",
                "not_found": "404",
                "unauthorized": "401",
                "too_large": "413",
                "missing_key": "400-key",
                "invalid_json": "422-json",
            }[wanted[1]]
            if wanted
            else "intake"
        )
        reached[name] += 1
        if ORACLE_ONLY:
            continue
        headers = {"Host": host}
        if auth is not None:
            headers["Authorization"] = auth
        if key is not None:
            headers["Idempotency-Key"] = key
        before = opened[0]
        answer = client.request(method, path, content=content, headers=headers)
        if answer.headers.get("content-type") != "application/json":
            print(f"  step {step}: content-type {answer.headers.get('content-type')}")
            return False
        found = answer.json()
        if wanted is not None:
            if (answer.status_code, found) != (wanted[0], {"error": wanted[1]}):
                status = answer.status_code
                print(f"  step {step}: {method} {path} {host}: {status} {found} != {wanted}")
                return False
            if opened[0] != before:
                print(f"  step {step}: a store was opened for a refused request")
                return False
        elif answer.status_code not in INTAKE or set(found) - {"id", "error"} or len(found) != 1:
            print(f"  step {step}: {answer.status_code} {found}")
            return False
        if TOKEN in answer.text or (key and len(key) > 3 and key in answer.text):
            print(f"  step {step}: the answer echoes the request")
            return False
    if ORACLE_ONLY:
        print(f"  reached {reached}")
        return True
    if not all(value >= 30 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


check(f"{STEPS} random requests follow the web layer's order of checks", walk)

print(f"FAILURES {FAILURES}")
