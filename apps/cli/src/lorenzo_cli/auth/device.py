"""`lorenzo login --token`: a personal access token through the device flow (ADR 0269).

The CLI asks the API for a code, prints it with the address of the account hub's "Connect a
device" page, and polls until the person has approved it there. The token it receives is kept in
the same file as any other login and used as the bearer token. Nothing here needs Authgear.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from socket import gethostname

import httpx

from lorenzo_cli.auth.store import CredentialsFile, StoredLogin


class DeviceLoginError(Exception):
    """The device login couldn't be completed."""


def _problem_kind(response: httpx.Response) -> str:
    """The last path segment of the problem's `type` ("authorization-pending", "slow-down", ...)."""
    try:
        kind = response.json().get("type", "")
    except ValueError:
        return ""
    return str(kind).rstrip("/").rsplit("/", 1)[-1]


def run_device_login(
    api_url: str,
    *,
    http_client: httpx.Client,
    store: CredentialsFile,
    echo: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    client_name: str | None = None,
) -> StoredLogin:
    base = api_url.rstrip("/")
    name = client_name or f"lorenzo CLI on {gethostname()}"[:80]
    try:
        started = http_client.post(f"{base}/device-codes", json={"client_name": name})
    except httpx.HTTPError as exc:
        raise DeviceLoginError(f"Couldn't reach {base}: {exc}") from exc
    if started.status_code == 429:
        raise DeviceLoginError("Too many attempts just now. Wait a minute and try again.")
    if started.status_code != 201:
        raise DeviceLoginError(f"The API refused to start a login (HTTP {started.status_code}).")
    flow = started.json()
    echo("To connect this computer, open this address in a browser where you are signed in:\n")
    echo(flow["verification_uri_complete"] + "\n")
    echo(f"or go to {flow['verification_uri']} and enter the code {flow['user_code']}.")
    echo("Waiting for you to approve it. Press Ctrl+C to give up.")

    interval = float(flow["interval"])
    deadline = now() + float(flow["expires_in"])
    while True:
        sleep(interval)
        if now() >= deadline:
            raise DeviceLoginError("The code expired before it was approved. Run the login again.")
        try:
            polled = http_client.post(
                f"{base}/device-codes/token", json={"device_code": flow["device_code"]}
            )
        except httpx.HTTPError as exc:
            raise DeviceLoginError(f"Lost the connection to {base}: {exc}") from exc
        if polled.status_code == 200:
            break
        kind = _problem_kind(polled)
        if kind == "authorization-pending":
            continue
        if kind == "slow-down" or polled.status_code == 429:
            interval += 5
            continue
        if kind == "access-denied":
            raise DeviceLoginError("The request was denied in the account hub.")
        if kind == "device-code-expired":
            raise DeviceLoginError("The code expired before it was approved. Run the login again.")
        raise DeviceLoginError(f"Unexpected answer from the API (HTTP {polled.status_code}).")

    issued = polled.json()
    expires_at: float | None = None
    if issued.get("expires_at"):
        expires_at = datetime.fromisoformat(issued["expires_at"]).timestamp()
    login = StoredLogin(
        issuer="",
        client_id="",
        access_token=issued["access_token"],
        expires_at=expires_at,
        token_name=issued["name"],
    )
    store.save(login)
    return login
