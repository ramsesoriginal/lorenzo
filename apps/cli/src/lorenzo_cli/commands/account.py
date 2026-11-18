"""`login`, `logout`, `whoami` and `legal` (ADR 0137, 0157, 0164, 0269, 0439)."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

import httpx
import typer
from rich.table import Table

from lorenzo_cli import completion, console
from lorenzo_cli.auth.device import run_device_login
from lorenzo_cli.auth.login import run_login
from lorenzo_cli.client.errors import (
    LorenzoApiError,
    LorenzoConnectionError,
)
from lorenzo_cli.client.ops import (
    GET_ME,
)
from lorenzo_cli.config import (
    ConfigError,
    Settings,
)
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _out,
    _reporting_errors,
)

app = typer.Typer()


def _require_address(name: str, value: str | None) -> None:
    """A remembered address has to look like one, or the next run would fail far from the cause."""
    if value is None:
        return
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigError(f"{name} “{value}” isn't an address: it should start with https://")


def _signing_in(settings: Settings) -> str:
    """Where `login` is about to sign in and for which API, before anything opens (ADR 0164)."""
    where = f"Signing in at {settings.issuer}"
    if settings.api_url:
        where += f", for the API at {settings.api_url}"
    return where + (" (the official Lorenzo)." if settings.defaulted else ".")


def _remember(runtime: Runtime, settings: Settings) -> None:
    """After a login that worked, keep the three settings it used for the next one (ADR 0157)."""
    if runtime.config is None:
        return
    if settings.defaulted:
        # The official set is never kept: a copy would outlive the defaults it came from.
        if runtime.config.delete():
            _out.print(
                f"Forgot the settings remembered in {runtime.config.path}: "
                "the official Lorenzo is the default again."
            )
        return
    used = {
        key: value
        for key, value in (
            ("api_url", settings.api_url),
            ("issuer", settings.issuer),
            ("client_id", settings.client_id),
        )
        if value
    }
    before = runtime.config.load()
    if all(before.get(key) == value for key, value in used.items()):
        return
    runtime.config.save(used)
    _out.print(
        f"Remembered the {', '.join(_SETTING_NAMES[k] for k in used)} in {runtime.config.path}."
    )


_SETTING_NAMES = {"api_url": "API URL", "issuer": "issuer", "client_id": "client id"}


@app.command()
def login(
    ctx: typer.Context,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser", help="Print the address and paste the redirect back (WSL, SSH)."
        ),
    ] = False,
    issuer: Annotated[
        str | None,
        typer.Option("--issuer", help="The Authgear issuer (or LORENZO_AUTHGEAR_ISSUER)."),
    ] = None,
    client_id: Annotated[
        str | None,
        typer.Option(
            "--client-id", help="The Authgear client's id (or LORENZO_AUTHGEAR_CLIENT_ID)."
        ),
    ] = None,
    personal_token: Annotated[
        bool,
        typer.Option(
            "--token",
            help="Connect with a personal access token you approve in the account hub: no "
            "browser sign-in here, and no expiry unless you set one.",
        ),
    ] = False,
) -> None:
    """Sign in and store the login, and remember the API URL, issuer and client id it used."""
    runtime: Runtime = ctx.obj
    with (
        _reporting_errors(),
        httpx.Client(transport=runtime.transport, timeout=30.0) as http_client,
    ):
        if personal_token:
            settings = runtime.resolve_settings()
            api_url = settings.require_api_url()
            _require_address("The API URL", api_url)
            run_device_login(
                api_url,
                http_client=http_client,
                store=runtime.store,
                echo=_out.print,
                sleep=runtime.sleep,
            )
            _remember(runtime, settings)
            _out.print("Connected with a personal access token.")
            return
        settings = runtime.resolve_settings(issuer=issuer, client_id=client_id)
        _require_address("The API URL", settings.api_url)
        _require_address("The issuer", settings.issuer)
        if settings.issuer:
            _out.print(_signing_in(settings), highlight=False, soft_wrap=True)
        run_login(
            settings,
            no_browser=no_browser,
            http_client=http_client,
            store=runtime.store,
            echo=_out.print,
            read_line=lambda prompt: typer.prompt(prompt, prompt_suffix=""),
        )
        _remember(runtime, settings)
    _out.print("Signed in.")


def _token_origin(runtime: Runtime) -> str:
    """Where the token came from, in the order ADR 0137 fixes."""
    if runtime.token_stdin:
        return "--token-stdin"
    if runtime.env.get("LORENZO_TOKEN"):
        return "LORENZO_TOKEN"
    return "the stored login"


@app.command()
def legal(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Print the addresses as JSON.")] = False,
) -> None:
    """Where the legal notice and the privacy policy of the Lorenzo you use are.

    Asks the API's public registry, so it needs no login and names whatever deployment you talk
    to; nothing about any operator is built into the command (ADR 0439).
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors():
        base_url = runtime.settings.require_api_url()
        try:
            with httpx.Client(transport=runtime.transport, timeout=30.0) as http:
                response = http.get(f"{base_url.rstrip('/')}/app-links")
            response.raise_for_status()
            registry = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LorenzoConnectionError(f"Could not read {base_url}/app-links: {exc}") from exc
    links = registry.get("links", {}) if isinstance(registry, dict) else {}
    rows = {
        "legal notice": links.get("legal_notice_en"),
        "impressum": links.get("legal_notice_de"),
        "privacy policy": links.get("legal_privacy_en"),
        "datenschutzerklärung": links.get("legal_privacy_de"),
        "support": registry.get("support_url") if isinstance(registry, dict) else None,
    }
    found = {
        name: address for name, address in rows.items() if isinstance(address, str) and address
    }
    if as_json:
        console.emit(found)
        return
    if not any(name != "support" for name in found):
        _err.print(f"{base_url} has not published a legal notice or a privacy policy.")
        raise typer.Exit(1)
    table = Table(show_header=False, box=None)
    for name, address in found.items():
        table.add_row(name, address)
    _out.print(table)


@app.command()
def whoami(
    ctx: typer.Context,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print what the API says as JSON.")
    ] = False,
) -> None:
    """Ask the API who the token you would use belongs to: a check that a login works."""
    runtime: Runtime = ctx.obj
    origin = _token_origin(runtime)
    with _reporting_errors(), _client(runtime) as client:
        try:
            me = client.call(GET_ME).value
        except LorenzoApiError as exc:
            if exc.status == 401:
                raise LorenzoApiError(
                    f"The API didn't accept the token from {origin}. Run `lorenzo login` again, "
                    "or check LORENZO_TOKEN.",
                    exc.status,
                    exc.problem,
                ) from exc
            raise
    if as_json:
        console.emit(me.model_dump(mode="json"))
        return
    table = Table(show_header=False, box=None)
    table.add_row("user", str(me.id))
    name = me.display_name or me.nickname
    if name:
        table.add_row("name", name)
    if me.email:
        table.add_row("email", me.email)
    settings = runtime.settings
    table.add_row("api", f"{settings.api_url}{' (the default)' if settings.defaulted else ''}")
    stored = runtime.store.load() if origin == "the stored login" else None
    if stored is not None and stored.token_name is not None:
        table.add_row("token", f"{origin}: personal access token “{stored.token_name}”")
    else:
        table.add_row("token", origin)
    table.add_row("tenants", str(len(me.memberships)))
    _out.print(table)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Forget the stored login and the names it cached for completion (the API URL, issuer and
    client id it remembered stay)."""
    runtime: Runtime = ctx.obj
    stored = runtime.store.load()
    api_url = runtime.settings.api_url
    account = completion.account_of(stored.access_token) if stored is not None else None
    cached = completion.cache_path(runtime.env, api_url, account) if api_url and account else None
    removed = runtime.store.delete()
    if cached is not None:
        completion.forget(cached)  # ADR 0507: the names go with the login
    _out.print("Signed out." if removed else "There was no stored login.")
    if stored is not None and stored.token_name is not None:
        _out.print(
            f"The personal access token “{stored.token_name}” still works until you revoke it "
            "in the account hub (Profile, Personal access tokens)."
        )
