import secrets

from docket.keychain import SecretMissing, get_secret, set_secret

CLIENTS = ("email",)
ALREADY_MESSAGE = "email already has a token; use --replace to issue a new one."
UNKNOWN_CLIENT_MESSAGE = "Clients are: email."


class ClientError(Exception):
    pass


def token_name(client: str) -> str:
    return f"client.{client}"


def issue_token(client: str, *, replace: bool = False) -> str:
    if client not in CLIENTS:
        raise ClientError(UNKNOWN_CLIENT_MESSAGE)
    name = token_name(client)
    if not replace:
        try:
            get_secret(name)
        except SecretMissing:
            pass
        else:
            raise ClientError(ALREADY_MESSAGE)
    token = secrets.token_urlsafe(32)
    set_secret(name, token)
    return token


def client_tokens() -> dict[str, str]:
    found: dict[str, str] = {}
    for client in CLIENTS:
        try:
            found[get_secret(token_name(client))] = client
        except SecretMissing:
            continue
    return found
