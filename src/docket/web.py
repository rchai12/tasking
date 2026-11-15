import hmac
import json
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from docket.intake import MISSING_KEY, accept_link, accept_task
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
    if not _bearer(request.headers.get("authorization"), tokens):
        return _error(UNAUTHORIZED, 401, authenticate=True)
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return _error(TOO_LARGE, 413)
    key = request.headers.get("idempotency-key")
    if key is None or len(key) not in range(1, 201):
        return _error(MISSING_KEY, 400)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(INVALID_JSON, 422)
    with open_store() as store:
        if task_id is None:
            answer = accept_task(store, key=key, body=body)
        else:
            answer = accept_link(store, task_id, key=key, body=body)
    return JSONResponse(
        answer.body, status_code=answer.status, headers={"Cache-Control": "no-store"}
    )


def _bearer(header: str | None, tokens: Mapping[str, str]) -> bool:
    if header is None or not header.startswith(_BEARER):
        return False
    presented = header[len(_BEARER) :]
    return any(hmac.compare_digest(presented, known) for known in tokens)


def _error(code: str, status: int, *, authenticate: bool = False) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": code}, status_code=status, headers=headers)
