import hmac
import json
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from docket import domain
from docket.intake import MISSING_KEY, Answer, accept_link, accept_task
from docket.store import Store

WRONG_HOST = "wrong_host"
NOT_FOUND = "not_found"
UNAUTHORIZED = "unauthorized"
TOO_LARGE = "too_large"
INVALID_JSON = "invalid_json"
MAX_BODY = 65536

_BEARER = "Bearer "


def create_app(
    *,
    open_store: Callable[[], Store],
    tokens: Mapping[str, str],
    port: int,
) -> FastAPI:
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        telemetry={
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
            "auto_configure": False,
        },
    )
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def require_host(
        request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]
    ) -> JSONResponse:
        if request.headers.get("host") not in allowed:
            return _error(WRONG_HOST, 400)
        return await call_next(request)

    async def not_found(request: Request, exc: Exception) -> JSONResponse:
        return _error(NOT_FOUND, 404)

    app.add_exception_handler(404, not_found)
    app.add_exception_handler(405, not_found)

    @app.post("/tasks")
    async def post_task(request: Request) -> JSONResponse:
        return await _handle(request, open_store, tokens, None)

    @app.post("/tasks/{task_id}/links")
    async def post_link(task_id: str, request: Request) -> JSONResponse:
        return await _handle(request, open_store, tokens, task_id)

    return app


async def _handle(
    request: Request,
    open_store: Callable[[], Store],
    tokens: Mapping[str, str],
    task_id: str | None,
) -> JSONResponse:
    client = _bearer(request.headers.get("authorization"), tokens)
    if client is None:
        return _error(UNAUTHORIZED, 401, authenticate=True)
    raw = await _bounded_body(request)
    if raw is None:
        return _error(TOO_LARGE, 413)
    key = request.headers.get("idempotency-key")
    if not domain.valid_request_key(key):
        return _error(MISSING_KEY, 400)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(INVALID_JSON, 422)
    answer = await run_in_threadpool(_intake, open_store, client, key, body, task_id)
    return JSONResponse(
        answer.body, status_code=answer.status, headers={"Cache-Control": "no-store"}
    )


async def _bounded_body(request: Request) -> bytes | None:
    parts: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        if total + len(chunk) > MAX_BODY:
            return None
        parts.append(chunk)
        total += len(chunk)
    return b"".join(parts)


def _intake(
    open_store: Callable[[], Store],
    client: str,
    key: str,
    body: object,
    task_id: str | None,
) -> Answer:
    with open_store() as store:
        if task_id is None:
            return accept_task(store, client=client, key=key, body=body)
        return accept_link(store, task_id, client=client, key=key, body=body)


def _bearer(header: str | None, tokens: Mapping[str, str]) -> str | None:
    if header is None or not header.startswith(_BEARER):
        return None
    presented = header[len(_BEARER) :]
    for known, identity in tokens.items():
        if hmac.compare_digest(presented, known):
            return identity
    return None


def _error(code: str, status: int, *, authenticate: bool = False) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": code}, status_code=status, headers=headers)
