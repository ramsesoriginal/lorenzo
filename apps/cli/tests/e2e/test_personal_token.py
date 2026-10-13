"""`lorenzo login --token` against the real API: the device flow, a request with the token, the
stored file, `whoami` naming the token, revoking it in the hub, and `logout` (ADR 0269)."""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path

import psycopg
import pytest
from typer.testing import CliRunner

from e2e.stack import Stack
from lorenzo_cli.auth import device
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()


def _pending_code(stack: Stack, client_name: str) -> str:
    with psycopg.connect(stack.database_dsn) as db:
        row = db.execute(
            "SELECT user_code FROM device_authorization WHERE client_name = %s", (client_name,)
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_login_token_connects_this_computer_and_the_token_acts_as_the_user(
    stack: Stack, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = f"pat-{uuid.uuid4().hex[:8]}"
    session = stack.creator_token(subject)
    approved: list[str] = []

    def approve_in_the_hub(_: float) -> None:
        # What the person does in the account hub while the CLI waits.
        if approved:
            return
        code = _pending_code(stack, f"lorenzo CLI on {subject}")
        with stack.api(session) as hub:
            seen = hub.get(f"/me/device-codes/{code}")
            assert seen.status_code == 200
            done = hub.post(f"/me/device-codes/{code}/approve", json={"name": "E2E laptop"})
            assert done.status_code == 204, done.text
        approved.append(code)

    store = CredentialsFile(tmp_path / "credentials.json")

    def runtime() -> Runtime:
        return Runtime(
            env={"LORENZO_API_URL": stack.api_url, "XDG_STATE_HOME": str(tmp_path / "state")},
            stdin=io.StringIO(),
            store=store,
            sleep=approve_in_the_hub,
        )

    # The CLI names itself after the host; make that name known to the approving side.
    monkeypatch.setattr(device, "gethostname", lambda: subject)
    login = runner.invoke(app, ["login", "--token"], obj=runtime())
    assert login.exit_code == 0, login.output
    assert approved

    stored = json.loads(store.path.read_text())
    assert stored["access_token"].startswith("lor_pat_") and stored["token_name"] == "E2E laptop"

    who = runner.invoke(app, ["whoami"], obj=runtime())
    assert who.exit_code == 0, who.output
    assert "E2E laptop" in who.output
    assert "tenants" in who.output

    # Full as the user: the creator role carried over, so a tenant can be made with it.
    slug = f"e2e-{uuid.uuid4().hex[:8]}"
    made = runner.invoke(app, ["tenant", "create", slug, "--kind", "repository"], obj=runtime())
    assert made.exit_code == 0, made.output

    # Revoked in the hub, the next request is refused.
    with stack.api(session) as hub:
        listed = hub.get("/me/tokens").json()
        assert [t["name"] for t in listed] == ["E2E laptop"]
        assert hub.delete(f"/me/tokens/{listed[0]['id']}").status_code == 204
    refused = runner.invoke(app, ["whoami"], obj=runtime())
    assert refused.exit_code == 1

    out = runner.invoke(app, ["logout"], obj=runtime())
    assert out.exit_code == 0 and not store.path.exists()
