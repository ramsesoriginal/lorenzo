"""`plan` and `apply` end to end (RFC 0025 §2, R6, ADR 0144): evaluate the files, map them, look at
the tenant, and work out what would change."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.evalworker import Engine, EvalError, EvalRequest, read_sources
from lorenzo_cli.importer.manifest import Manifest, default_path
from lorenzo_cli.importer.mapping import load_mapping
from lorenzo_cli.importer.plan import ImportPlan, Options, build_plan
from lorenzo_cli.seed import load_builtin
from lorenzo_cli.tenants import require_repository, resolve_tenant


def prepare(
    client: LorenzoClient,
    engine: Engine,
    env: Mapping[str, str],
    *,
    tenant_ref: str,
    files: Sequence[Path],
    base: Sequence[Path],
    map_text: str | None,
    taught: str = "",
    allow_play_tenant: bool,
    options: Options,
    state_path: Path | None,
) -> tuple[ImportPlan, Manifest]:
    # The map first: a wrong map should fail before anything is read from anywhere.
    loaded = load_mapping(map_text, taught=taught)
    result = engine.evaluate(EvalRequest(base=read_sources(base), files=read_sources(files)))
    if not result.ok:
        raise EvalError(result.error or "The JavaScript host could not finish.")
    tenant = resolve_tenant(client, tenant_ref)
    require_repository(tenant, allow_play=allow_play_tenant)
    manifest = Manifest.load(state_path or default_path(env, tenant.id))
    plan = build_plan(client, tenant, loaded, result, load_builtin(), manifest, options)
    return plan, manifest
