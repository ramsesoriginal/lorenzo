"""The completion cache against the real API (ADR 0493): the commands a person already runs fill it,
and a delete takes a name out again."""

from __future__ import annotations

from pathlib import Path

from e2e.helpers import make_tenant, run_cli, tenant_id
from e2e.stack import Stack
from lorenzo_cli import completion


def test_applying_and_listing_fill_the_cache_and_a_delete_empties_it(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("completing")
    library = make_tenant(stack, token, "repository")

    def ok(*args: str) -> None:
        result = run_cli(stack, token, tmp_path, *args)
        assert result.exit_code == 0, result.output

    ok("apply", "--starter", "neutral", "-t", library, "--yes")
    ok("apply", "--starter", "dnd5e", "-t", library, "--yes")
    ok("system", "list", "-t", library)
    env = {"XDG_CACHE_HOME": str(tmp_path / "cache")}
    path = completion.cache_path(env, stack.api_url, completion.account_of(token) or "")
    with stack.api(token) as api:
        library_id = tenant_id(api, library)

    data = completion.load(path)
    assert completion.library_slugs(data, library[:4]) == [library]
    assert completion.names(data, library, "systems", "") == ["dnd5e"]
    assert "dnd5e_strength" in completion.names(data, library, "stats", "dnd5e_s")
    assert "physical" in completion.names(data, library_id, "stat_groups", "")

    ok("system", "create", "zed", "Zed", "-t", library, "--yes")
    assert completion.names(completion.load(path), library, "systems", "") == ["dnd5e", "zed"]
    ok("system", "delete", "zed", "-t", library, "--yes")

    assert completion.names(completion.load(path), library, "systems", "") == ["dnd5e"]
