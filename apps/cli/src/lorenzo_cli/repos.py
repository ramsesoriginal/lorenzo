"""The CLI's side of repositories (RFC 0024; ADR 0159, 0160).

The commands are one per API step. What lives here is what is more than one call: naming a
repository or a subscriber, answering a copy's collisions, choosing the updates that need no
decision, and offering a repository to a tenant.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import (
    AddedOut,
    ApplyUpdatesOut,
    ApplyUpdatesRequest,
    CollisionOut,
    CopyOut,
    CopyPlanOut,
    CopyRequest,
    ResolutionIn,
    RowChangeOut,
    SubscriberOut,
    SubscriptionOut,
    TenantKind,
    TenantOut,
    TenantSummaryOut,
    UpdateActionIn,
    UpdatesOut,
)
from lorenzo_cli.client.ops import (
    APPLY_REPOSITORY_UPDATES,
    COPY_REPOSITORY,
    GRANT_REPOSITORY,
    LIST_REPOSITORIES,
    LIST_REPOSITORY_UPDATES,
    LIST_SUBSCRIBERS,
    LIST_TENANTS,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient

OnCollision = Literal["merge", "skip"]


class RepoError(Exception):
    """A repository command can't go ahead as asked, said in words."""


def as_uuid(reference: str) -> UUID | None:
    try:
        return UUID(reference)
    except ValueError:
        return None


# --- naming things -----------------------------------------------------------------------------


def require_repository_tenant(tenant: TenantOut, *, what: str = "published or granted") -> None:
    if tenant.kind != TenantKind.repository:
        raise RepoError(
            f"“{tenant.slug}” is a play tenant, not a repository, so it can't be {what}. "
            "A tenant's kind is fixed when it is created."
        )


def list_subscribers(client: LorenzoClient, repository_id: UUID) -> list[SubscriberOut]:
    return list(
        all_items(client, LIST_SUBSCRIBERS, path={"tenant_id": repository_id}, of=SubscriberOut)
    )


def list_repositories(client: LorenzoClient, tenant_id: UUID) -> list[SubscriptionOut]:
    return list(
        all_items(client, LIST_REPOSITORIES, path={"tenant_id": tenant_id}, of=SubscriptionOut)
    )


def resolve_repository(client: LorenzoClient, tenant: TenantOut, reference: str) -> UUID:
    """A repository's id: given as one, or a slug among those granted to the tenant or copied.

    No route looks a repository up by slug (ADR 0135), so the tenant's own list is the lookup.
    """
    given = as_uuid(reference)
    if given is not None:
        return given
    for subscription in list_repositories(client, tenant.id):
        if subscription.repository.slug == reference:
            return subscription.repository.id
    raise RepoError(
        f"There's no repository “{reference}” granted to “{tenant.slug}” or copied by it. "
        f"`lorenzo repo list --tenant {tenant.slug}` shows the ones there are."
    )


def repository_name(client: LorenzoClient, tenant: TenantOut, repository_id: UUID) -> str:
    for subscription in list_repositories(client, tenant.id):
        if subscription.repository.id == repository_id:
            return subscription.repository.name or subscription.repository.slug
    return str(repository_id)


def resolve_subscriber_to_grant(client: LorenzoClient, reference: str) -> UUID:
    """A tenant to grant a repository to: an id, or a slug among the caller's own tenants.

    The API keeps no directory of tenants (ADR 0118): a grant names its subscriber by an id its
    members pass on, so a tenant the caller doesn't belong to can only be named by id.
    """
    given = as_uuid(reference)
    if given is not None:
        return given
    for summary in all_items(client, LIST_TENANTS, of=TenantSummaryOut):
        if summary.slug == reference:
            return summary.id
    raise RepoError(
        f"There's no tenant “{reference}” among the ones you belong to. To grant a repository to "
        "someone else's tenant, ask its members for its id (`lorenzo tenant show` prints it)."
    )


def resolve_subscriber_to_revoke(
    client: LorenzoClient, repository_id: UUID, reference: str
) -> SubscriberOut:
    """A grant's subscriber, found in the repository's own list, which names every one by slug."""
    given = as_uuid(reference)
    for subscriber in list_subscribers(client, repository_id):
        if subscriber.tenant_id == given or subscriber.slug == reference:
            return subscriber
    raise RepoError(
        f"“{reference}” holds no grant for this repository. `lorenzo repo subscribers` lists them."
    )


def has_published_since(subscription: SubscriptionOut) -> bool:
    """Whether the repository has published since the tenant copied or last synced it (ADR 0121)."""
    published: datetime | None = subscription.repository.published_at
    since = subscription.synced_at or subscription.copied_at
    return published is not None and since is not None and published > since


# --- collisions --------------------------------------------------------------------------------


def read_json_file(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RepoError(f"Couldn't read {path}: {exc.strerror}.") from exc
    except ValueError as exc:
        raise RepoError(f"{path} isn't valid JSON ({what}): {exc}.") from exc


def read_choices(path: Path) -> list[ResolutionIn]:
    """A file of choices: the API's own resolutions, as a list or under `resolutions`."""
    data = read_json_file(path, "a list of choices")
    if isinstance(data, dict):
        data = data.get("resolutions")
    if not isinstance(data, list):
        raise RepoError(f'{path} should hold a list of choices, or {{"resolutions": [...]}}.')
    try:
        return [ResolutionIn.model_validate(entry) for entry in data]
    except ValidationError as exc:
        raise RepoError(f"A choice in {path} isn't right: {_first_problem(exc)}") from exc


def _first_problem(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}"


def _key(kind: Any, source_id: UUID) -> tuple[str, UUID]:
    return (getattr(kind, "value", kind), source_id)


def answer_collisions(
    collisions: Sequence[CollisionOut],
    *,
    explicit: Sequence[ResolutionIn],
    on_collision: OnCollision | None,
) -> tuple[list[ResolutionIn], list[CollisionOut]]:
    """The choice for each collision, and the collisions still without one.

    A choice named in a file wins. `--on-collision` answers every other collision it is allowed
    for (a slug can't be merged). A file's choice is sent as written, and the API refuses one that
    can't work (`422`); choices that match no collision are passed on untouched.
    """
    by_key = {_key(c.kind, c.source_id): c for c in collisions}
    answered = {_key(choice.kind, choice.source_id): choice for choice in explicit}
    for key, collision in by_key.items():
        if key in answered or on_collision is None:
            continue
        if on_collision in {c.value for c in collision.choices}:
            answered[key] = ResolutionIn.model_validate(
                {
                    "kind": collision.kind.value,
                    "source_id": collision.source_id,
                    "action": on_collision,
                }
            )
    unanswered = [c for key, c in by_key.items() if key not in answered]
    return list(answered.values()), unanswered


@dataclass(frozen=True)
class NeedsChoices:
    """A copy that stopped before writing anything, because these collisions have no choice."""

    collisions: list[CollisionOut]


def copy_with_choices(
    client: LorenzoClient,
    tenant_id: UUID,
    repository_id: UUID,
    *,
    explicit: Sequence[ResolutionIn],
    on_collision: OnCollision | None,
    dry_run: bool,
    again: Literal["keep", "purge"] | None,
) -> CopyOut | NeedsChoices:
    """Copy, answering collisions as they are reported.

    The API names every collision, with the choices each allows, in a `409`. That is what the
    answers are matched against, so it works for `again` too, where the collisions come from the
    rows an earlier copy left behind and no plan beforehand can show them. At most one retry:
    the answers either cover everything, or the copy is left as it is and the rest is reported.
    """
    resolutions = list(explicit)
    for attempt in (1, 2):
        request: dict[str, Any] = {}
        if resolutions:
            request["resolutions"] = [r.model_dump(mode="json") for r in resolutions]
        if dry_run:
            request["dry_run"] = True
        if again:
            request["again"] = again
        body = CopyRequest.model_validate(request)
        try:
            return client.call(
                COPY_REPOSITORY,
                path={"tenant_id": tenant_id, "repository_id": repository_id},
                body=body,
            ).value
        except LorenzoApiError as exc:
            if exc.problem_type != "repository-copy-needs-choices":
                raise
            collisions = [CollisionOut.model_validate(c) for c in exc.problem.get("collisions", [])]
            resolutions_now, open_ = answer_collisions(
                collisions, explicit=resolutions, on_collision=on_collision
            )
            if open_ or attempt == 2 or not collisions:
                return NeedsChoices(open_ or collisions)
            resolutions = resolutions_now
    raise AssertionError("unreachable")  # the loop returns on both attempts


# --- updates -----------------------------------------------------------------------------------


@dataclass
class CleanUpdates:
    """What `repo updates --apply` takes, and what it leaves for a decision."""

    actions: list[UpdateActionIn] = field(default_factory=list)
    conflicts: list[RowChangeOut] = field(default_factory=list)
    collisions: list[AddedOut] = field(default_factory=list)
    removed: int = 0

    @property
    def left(self) -> bool:
        return bool(self.conflicts or self.collisions or self.removed)


def clean_updates(updates: UpdatesOut) -> CleanUpdates:
    """Every change that needs no decision, and nothing else (ADR 0159).

    A changed row with only clean fields is applied; one with a conflict is left, since the
    tenant's own edit is never overwritten without being named. An added row with no collision is
    copied. A row gone upstream is left: detaching it is a decision about a row that may be in
    play.
    """
    chosen = CleanUpdates(removed=len(updates.removed))
    for row in updates.changed:
        states = {f.state.value for f in row.fields}
        if "conflict" in states:
            chosen.conflicts.append(row)
        elif "clean" in states:
            chosen.actions.append(_action(row.kind.value, row.source_id, "apply"))
    for added in updates.added:
        if added.collision is not None:
            chosen.collisions.append(added)
        else:
            chosen.actions.append(_action(added.kind.value, added.source_id, "add"))
    return chosen


def _action(kind: str, source_id: UUID, action: str) -> UpdateActionIn:
    return UpdateActionIn.model_validate({"kind": kind, "source_id": source_id, "action": action})


def read_actions(path: Path) -> list[UpdateActionIn]:
    """A file of the API's own actions, as a list or under `actions`."""
    data = read_json_file(path, "a list of actions")
    if isinstance(data, dict):
        data = data.get("actions")
    if not isinstance(data, list):
        raise RepoError(f'{path} should hold a list of actions, or {{"actions": [...]}}.')
    try:
        return [UpdateActionIn.model_validate(entry) for entry in data]
    except ValidationError as exc:
        raise RepoError(f"An action in {path} isn't right: {_first_problem(exc)}") from exc


def apply_updates(
    client: LorenzoClient,
    tenant_id: UUID,
    repository_id: UUID,
    actions: Sequence[UpdateActionIn],
    *,
    dry_run: bool,
) -> ApplyUpdatesOut:
    request: dict[str, Any] = {
        "actions": [a.model_dump(mode="json", exclude_none=True) for a in actions]
    }
    if dry_run:
        request["dry_run"] = True
    body = ApplyUpdatesRequest.model_validate(request)
    return client.call(
        APPLY_REPOSITORY_UPDATES,
        path={"tenant_id": tenant_id, "repository_id": repository_id},
        body=body,
    ).value


def updates_waiting(updates: UpdatesOut) -> bool:
    """Whether there is anything to take, leave or detach (what was deleted here is not)."""
    return bool(updates.changed or updates.added or updates.removed)


# --- the plan's verdict ------------------------------------------------------------------------


def copy_plan_blockers(plan: CopyPlanOut, repository_id: UUID) -> list[str]:
    """Why the API would refuse this copy as it stands, in words (empty when it wouldn't)."""
    blockers: list[str] = []
    for step in plan.steps:
        if step.repository_id == repository_id and step.already_copied:
            blockers.append(
                f"{step.name} is already copied here: take its changes with `lorenzo repo "
                "updates`, or copy it afresh with --again keep|purge."
            )
        elif not step.already_copied and not (step.granted and step.published):
            why = "isn't granted to this tenant" if not step.granted else "isn't published"
            blockers.append(f"{step.name} {why}: ask its owners for access, or to publish it.")
    return blockers


def copy_plan_exit_code(plan: CopyPlanOut, repository_id: UUID) -> int:
    """0 the copy could go ahead as it stands, 2 it needs choices, 1 it would be refused."""
    if copy_plan_blockers(plan, repository_id):
        return 1
    return 2 if plan.collisions else 0


# --- offering ----------------------------------------------------------------------------------


@dataclass
class OfferState:
    """What there is to do to offer a repository to a tenant, read without writing anything."""

    repository: TenantOut
    subscriber: TenantOut
    granted: bool
    copied: bool
    published_since: bool

    @property
    def steps(self) -> list[str]:
        steps = [] if self.granted else ["grant"]
        if not self.copied:
            steps.append("copy")
        return steps


@dataclass
class OfferResult:
    granted: Literal["new", "existing"] = "existing"
    copied: Literal["copied", "already"] = "already"
    copy: CopyOut | None = None
    updates_applied: ApplyUpdatesOut | None = None
    updates_waiting: int = 0
    needs_choices: list[CollisionOut] = field(default_factory=list)


def read_offer_state(
    client: LorenzoClient, repository: TenantOut, subscriber: TenantOut
) -> OfferState:
    """Refuses what could never work, before anything is written (ADR 0160)."""
    require_repository_tenant(repository, what="offered")
    if repository.published_at is None:
        raise RepoError(
            f"“{repository.slug}” isn't published yet, so a copy of it would be refused. "
            f"Publish it first: lorenzo repo publish --tenant {repository.slug}"
        )
    if subscriber.id == repository.id:
        raise RepoError("A repository can't be offered to itself.")
    granted = any(s.tenant_id == subscriber.id for s in list_subscribers(client, repository.id))
    held = next(
        (s for s in list_repositories(client, subscriber.id) if s.repository.id == repository.id),
        None,
    )
    return OfferState(
        repository=repository,
        subscriber=subscriber,
        granted=granted,
        copied=held is not None and held.copied_at is not None,
        published_since=held is not None and has_published_since(held),
    )


def perform_offer(
    client: LorenzoClient,
    state: OfferState,
    *,
    explicit: Sequence[ResolutionIn],
    on_collision: OnCollision | None,
    apply_clean_updates: bool,
) -> OfferResult:
    """Grant, copy into the subscriber, and optionally take the clean updates (ADR 0160).

    Each step is safe to repeat, so the whole is: a grant that exists is fine, and a copy the
    tenant already has is a success. Collisions without a choice stop it after the grant, which
    stays, and are reported in the result.
    """
    result = OfferResult()
    if not state.granted:
        reply = client.call(
            GRANT_REPOSITORY,
            path={"tenant_id": state.repository.id, "subscriber_tenant_id": state.subscriber.id},
        )
        result.granted = "new" if reply.status == 201 else "existing"
    repository_id = state.repository.id
    subscriber_id = state.subscriber.id
    if not state.copied:
        try:
            copied = copy_with_choices(
                client,
                subscriber_id,
                repository_id,
                explicit=explicit,
                on_collision=on_collision,
                dry_run=False,
                again=None,
            )
        except LorenzoApiError as exc:
            # Copied between the check and the copy: the tenant has it, which is the point.
            if exc.problem_type != "repository-already-copied":
                raise
        else:
            if isinstance(copied, NeedsChoices):
                result.needs_choices = copied.collisions
            else:
                result.copied = "copied"
                result.copy = copied
            return result
    updates = client.call(
        LIST_REPOSITORY_UPDATES,
        path={"tenant_id": subscriber_id, "repository_id": repository_id},
    ).value
    chosen = clean_updates(updates)
    if not apply_clean_updates:
        result.updates_waiting = len(updates.changed) + len(updates.added) + len(updates.removed)
        return result
    if chosen.actions:
        result.updates_applied = apply_updates(
            client, subscriber_id, repository_id, chosen.actions, dry_run=False
        )
    # What is left is what needed a decision, whether or not anything was taken.
    result.updates_waiting = len(chosen.conflicts) + len(chosen.collisions) + chosen.removed
    return result


def in_words(error: LorenzoApiError) -> LorenzoApiError:
    """The API's refusals about repositories that say more than their status."""
    if error.problem_type == "repository-copy-needs-grants":
        missing = error.problem.get("missing")
        if isinstance(missing, list):
            lines = [
                f"\n  - {entry.get('name')} "
                f"({'not granted' if not entry.get('granted') else 'not published'})"
                for entry in missing
                if isinstance(entry, dict)
            ]
            return LorenzoApiError(f"{error}{''.join(lines)}", error.status, error.problem)
    if error.problem_type == "repository-already-copied":
        return LorenzoApiError(
            f"{error}. Take its changes with `lorenzo repo updates`, or copy it afresh with "
            "--again keep|purge.",
            error.status,
            error.problem,
        )
    return error
