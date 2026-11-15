import uvicorn
from fastapi import FastAPI

from docket.clients import client_tokens
from docket.config import Settings
from docket.store import Store, open_store
from docket.web import create_app

NO_CLIENTS_MESSAGE = "No clients yet: run docket clients add email."


class ServeError(Exception):
    pass


def build_app(settings: Settings) -> FastAPI:
    tokens = client_tokens()
    if not tokens:
        raise ServeError(NO_CLIENTS_MESSAGE)
    opened = open_store(settings)
    opened.close()

    def open_for_request() -> Store:
        return open_store(settings)

    return create_app(open_store=open_for_request, tokens=tokens, port=settings.web_port)


def run_app(app: FastAPI, port: int) -> None:
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        access_log=False,
        server_header=False,
        proxy_headers=False,
        log_level="warning",
    )
