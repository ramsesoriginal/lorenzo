"""Apply a reviewed manuscript graph in one transaction (ADR 0438)."""

import copy
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.description_payloads import write_description
from lorenzo_api.exceptions import InvalidRepositoryUpdateError
from lorenzo_api.information_bundles import touch_bundle
from lorenzo_api.learning import require_no_learning
from lorenzo_api.manuscript_access import (
    require_no_new_readers,
    require_no_wider_manuscript_audience,
)
from lorenzo_api.manuscript_graph import validate
from lorenzo_api.manuscript_review import Review
from lorenzo_api.models import (
    CarrierCoverage,
    ContentReference,
    Edition,
    Entity,
    Information,
    ManuscriptContents,
    ManuscriptNumbering,
    ManuscriptPlacement,
    ManuscriptRedirect,
    ManuscriptRepositoryUpdate,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    RepositoryCopyLinkEntity,
    SceneTelling,
    User,
    WritingReviewGrant,
)
from lorenzo_api.repository_copying import Step, _Planner, write_rows
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.svg_lint import SvgRefused, check_svg


def reject(detail: str) -> NoReturn:
    raise InvalidRepositoryUpdateError(detail=detail)


def reviewer_reach(
    graph: dict[str, dict[str, Any]], grants: dict[str, set[uuid.UUID]]
) -> dict[str, set[uuid.UUID]]:
    result: dict[str, set[uuid.UUID]] = {}
    for id, record in graph.items():
        current = id
        seen = set()
        while current in graph and current not in seen:
            seen.add(current)
            if current in grants:
                people = grants[current]
                result.setdefault(id, set()).update(people)
                telling = record["structure"]["telling"]
                if telling and telling["shared"]:
                    result.setdefault(telling["scene"], set()).update(people)
                break
            placement = graph[current]["structure"]["placement"]
            if not placement:
                break
            current = placement["parent"]
    return result


async def apply(
    session: AsyncSession,
    tenant: uuid.UUID,
    root: uuid.UUID,
    user: User,
    reviewed: Review,
    choices: dict[str, Literal["local", "upstream"]],
) -> uuid.UUID:
    for affected in sorted(reviewed.result.affected_entries):
        await session.scalar(
            select(Entity)
            .where(Entity.tenant_id == tenant, Entity.id == affected)
            .with_for_update()
        )
        await session.scalar(
            select(Information)
            .where(
                Information.tenant_id == tenant,
                Information.entity_id == affected,
                Information.type == "manuscript",
            )
            .with_for_update()
        )
    rows = {row.id: row for row in reviewed.result.rows if row.selectable}
    if not choices or set(choices) - rows.keys():
        reject("Choose only changes in the current review.")
    root_row = await session.get(Entity, root)
    assert root_row is not None
    root_row.updated_at = datetime.now(UTC)
    root_row.updated_by = user.id
    target = copy.deepcopy(reviewed.local)
    bundles, structures, additions = set(), set(), set()
    for key, choice in choices.items():
        if choice == "local":
            continue
        source_id, field = key.rsplit(":", 1)
        if field == "entry":
            target[source_id] = copy.deepcopy(reviewed.source[source_id])
            additions.add(source_id)
            bundles.add(source_id)
            structures.add(source_id)
        else:
            target[source_id][field] = copy.deepcopy(reviewed.source[source_id][field])
            (bundles if field == "bundle" else structures).add(source_id)
    external = set(reviewed.identities.values()) | {
        "local:" + str(id) for id in reviewed.local_content.entities
    }
    try:
        validate(
            {key: value for key, value in target.items() if key in reviewed.connected}, external
        )
    except ValueError as error:
        reject(str(error))

    def owners(graph: dict[str, dict[str, Any]]) -> dict[str, str]:
        return {
            p["id"]: id
            for id, record in graph.items()
            for p in (record.get("bundle") or {}).get("payloads", [])
        }

    before_owners, source_owners, target_owners = (
        owners(reviewed.local),
        owners(reviewed.source),
        owners(target),
    )
    for element, destination in source_owners.items():
        previous = before_owners.get(element)
        if (
            previous
            and previous != destination
            and {previous, destination} & bundles
            and target_owners.get(element) != destination
        ):
            reject(
                "This element moved between manuscripts. Accept both manuscript changes together."
            )
    grants: dict[str, set[uuid.UUID]] = {}
    for grant in await session.scalars(
        select(WritingReviewGrant).where(WritingReviewGrant.tenant_id == tenant)
    ):
        if not await is_tenant_author(session, tenant_id=tenant, user_id=grant.user_id):
            key = reviewed.identities.get(str(grant.edition_id), "local:" + str(grant.edition_id))
            grants.setdefault(key, set()).add(grant.user_id)
    old_readers, new_readers = (
        reviewer_reach(reviewed.local, grants),
        reviewer_reach(target, grants),
    )
    if any(people - old_readers.get(id, set()) for id, people in new_readers.items()):
        reject("These changes would add reviewers to writing. Review Edition sharing first.")
    mapping = {source: uuid.UUID(local) for local, source in reviewed.identities.items()}

    def local(value: str | None) -> uuid.UUID | None:
        if value is None:
            return None
        if value.startswith("local:"):
            return uuid.UUID(value[6:])
        if value not in mapping:
            reject("A selected change needs an entry that has not been copied.")
        return mapping[value]

    # New entries use the existing copy planner, without applying their graph twice.
    if additions:
        content = copy.deepcopy(reviewed.source_content)
        content.manuscript_placements.clear()
        content.manuscript_redirects.clear()
        content.carrier_coverage.clear()
        content.manuscript_numbering.clear()
        content.manuscript_contents.clear()
        manuscript_infos = {
            key for key, value in content.information.items() if value.type == "manuscript"
        }
        content.information = {
            key: value for key, value in content.information.items() if key not in manuscript_infos
        }
        content.payloads = {
            key: value
            for key, value in content.payloads.items()
            if value.information_id not in manuscript_infos
        }
        # Manuscript payloads are written below using the shared identity map. In particular,
        # extracting an existing element into a newly added Chapter must not copy that element.
        planner = _Planner(tenant, user.id, reviewed.local_content.links, {})
        await planner.load_local_names(session)
        step = Step(
            repository_id=reviewed.repository_id,
            name="",
            granted=True,
            published=True,
            already_copied=True,
            content=content,
        )
        planner.plan_step(
            step,
            only={
                "entity": {uuid.UUID(id) for id in additions},
                "stat_group": set(),
                "stat_definition": set(),
            },
            record_copy=False,
        )
        if planner.collisions or step.dropped:
            reject(
                "Copy the missing world dependencies or resolve link-name collisions before "
                "accepting this writing."
            )
        # New writing never imports public or participant audiences or knowledge grants.
        for copied_info in planner.rows["information"]:
            copied_info["is_public"] = False
            copied_info["shared_with_participants"] = False
        for key in ("knowledge", "entity_knowledge", "entity_audience"):
            if key == "entity_audience":
                for audience in planner.rows[key]:
                    audience["is_public"] = False
                    if "shared_with_participants" in audience:
                        audience["shared_with_participants"] = False
            else:
                planner.rows[key].clear()
        await write_rows(session, planner.rows)
        for id in additions:
            link = await session.get(RepositoryCopyLinkEntity, (tenant, uuid.UUID(id)))
            assert link is not None
            reviewed.links[id] = link
            assert link.entity_id is not None
            mapping[id] = link.entity_id
            mapping.update(
                {
                    origin: uuid.UUID(own)
                    for own, origin in (link.manuscript_baseline or {})
                    .get("identities", {})
                    .items()
                }
            )
    changed = bundles | structures
    infos: dict[str, Information | None] = {}
    # Lock in stable order and check every destination before touching its prose.
    for id in sorted(changed):
        entity_id = local(id)
        changed_entity = await session.scalar(
            select(Entity)
            .where(Entity.id == entity_id, Entity.tenant_id == tenant)
            .with_for_update()
        )
        assert changed_entity is not None
        changed_entity.updated_at = datetime.now(UTC)
        changed_entity.updated_by = user.id
        info = await session.scalar(
            select(Information)
            .where(
                Information.tenant_id == tenant,
                Information.entity_id == entity_id,
                Information.type == "manuscript",
            )
            .with_for_update()
        )
        if info:
            await authorize_information_edit(session, tenant_id=tenant, user=user, information=info)
        infos[id] = info
        if (
            id not in additions
            and target[id]["structure"]["kinds"] != reviewed.local[id]["structure"]["kinds"]
        ):
            reject(
                "Change entry kinds through the ordinary repository review before updating "
                "this composition."
            )
    # Remove selected edges before changing payload ownership/anchors; all changes remain private
    # to this transaction and an exception rolls the whole operation back.
    for id in structures:
        entity_id = local(id)
        for edge_model, column in (
            (ManuscriptPlacement, ManuscriptPlacement.child_entity_id),
            (ManuscriptRedirect, ManuscriptRedirect.source_id),
            (CarrierCoverage, CarrierCoverage.carrier_id),
            (ManuscriptNumbering, ManuscriptNumbering.entity_id),
            (ManuscriptContents, ManuscriptContents.entity_id),
        ):
            await session.execute(
                delete(edge_model).where(edge_model.tenant_id == tenant, column == entity_id)
            )
    original_owners: dict[uuid.UUID, str] = {}
    existing_payloads: dict[uuid.UUID, Payload] = {}
    payload: Payload | None
    for id in sorted(bundles):
        info = infos[id]
        if not info:
            continue
        for payload in await session.scalars(
            select(Payload)
            .where(Payload.information_id == info.id, Payload.tenant_id == tenant)
            .options(selectinload(Payload.description))
            .with_for_update()
        ):
            existing_payloads[payload.id] = payload
            original_owners[payload.id] = id
    if existing_payloads:
        # Trigger each old bundle's revision before a payload moves to another owner.
        minimum = min(payload.order for payload in existing_payloads.values())
        if minimum - len(existing_payloads) < -2147483648:
            reject("The manuscript positions need arranging before this update.")
        for index, payload in enumerate(existing_payloads.values(), 1):
            payload.order = minimum - index
        await session.flush()
    retained: set[uuid.UUID] = set()
    for id in sorted(bundles):
        incoming = target[id]["bundle"]
        info = infos[id]
        if incoming is None:
            if info:
                # Retain the former designated bundle and its recovery history as an ordinary note.
                info.type = "note"
                touch_bundle(info)
                retained.update(
                    payload.id
                    for payload in existing_payloads.values()
                    if payload.information_id == info.id
                )
            continue
        if info is None:
            info = Information(
                id=uuid.uuid4(),
                tenant_id=tenant,
                entity_id=local(id),
                type="manuscript",
                title=incoming["title"],
                created_by=user.id,
                is_public=False,
                shared_with_participants=False,
            )
            session.add(info)
            await session.flush()
            infos[id] = info
        for item in incoming["payloads"]:
            payload_id = mapping.setdefault(item["id"], uuid.uuid4())
            payload = existing_payloads.get(payload_id)
            if payload is None:
                payload = Payload(
                    id=payload_id,
                    tenant_id=tenant,
                    information_id=info.id,
                    order=item["order"],
                    description=None,
                )
                session.add(payload)
            else:
                previous_owner = original_owners[payload_id]
                if previous_owner != id:
                    source_entry, destination_entry = local(previous_owner), local(id)
                    assert source_entry is not None and destination_entry is not None
                    previous_info = infos[previous_owner]
                    assert previous_info is not None
                    await require_no_wider_manuscript_audience(
                        session, tenant, source_entry, destination_entry, previous_info, info
                    )
                    await require_no_new_readers(
                        session,
                        tenant,
                        source_entry,
                        destination_entry,
                        infos[previous_owner],
                        info,
                    )
                payload.information_id = info.id
                payload.order = item["order"]
                payload.updated_at = datetime.now(UTC)
            retained.add(payload_id)
            source_payload = reviewed.source_content.payloads[uuid.UUID(item["id"])]
            fields = source_payload.fields
            old_kind = next(
                (
                    p["kind"]
                    for record in reviewed.local.values()
                    for p in (record.get("bundle") or {}).get("payloads", [])
                    if p["id"] == item["id"]
                ),
                None,
            )
            if old_kind and old_kind != item["kind"]:
                concrete_models: dict[
                    str,
                    type[PayloadDescription]
                    | type[PayloadPicture]
                    | type[PayloadDocument]
                    | type[PayloadNumber],
                ] = {
                    "description": PayloadDescription,
                    "picture": PayloadPicture,
                    "document": PayloadDocument,
                    "number": PayloadNumber,
                }
                old_model = concrete_models[old_kind]
                old_concrete = await session.get(old_model, payload_id)
                if old_concrete is not None:
                    await session.delete(old_concrete)
                if old_kind == "description":
                    await session.execute(
                        delete(ContentReference).where(
                            ContentReference.tenant_id == tenant,
                            ContentReference.payload_id == payload_id,
                        )
                    )
                    payload.description = None
                await session.flush()
            if item["kind"] == "description":
                await write_description(
                    session, payload=payload, content=fields["content"], locale=fields["locale"]
                )
            else:
                model = {
                    "picture": PayloadPicture,
                    "document": PayloadDocument,
                    "number": PayloadNumber,
                }[item["kind"]]
                if item["kind"] == "picture" and fields["file_type"] == "image/svg+xml":
                    try:
                        check_svg(fields["data"])
                    except SvgRefused:
                        reject("This repository picture is not a supported SVG.")
                concrete = await session.get(model, payload_id)
                if concrete is None:
                    session.add(model(payload_id=payload_id, tenant_id=tenant, **fields))
                else:
                    for key, value in fields.items():
                        setattr(concrete, key, value)
        info.title = incoming["title"]
        touch_bundle(info)
    for payload_id, payload in existing_payloads.items():
        if payload_id not in retained:
            await require_no_learning(session, tenant, information_id=payload.information_id)
            await session.delete(payload)
    await session.flush()
    for id in sorted(structures):
        entity_id = local(id)
        structure = target[id]["structure"]
        if structure["book"]:
            edition = await session.get(Edition, entity_id)
            assert edition is not None
            book_id = local(structure["book"])
            assert book_id is not None
            edition.book_entity_id = book_id
        telling = structure["telling"]
        if telling:
            telling_row = await session.get(SceneTelling, entity_id)
            assert telling_row is not None
            scene_id = local(telling["scene"])
            assert scene_id is not None
            telling_row.scene_entity_id = scene_id
            telling_row.viewpoint_entity_id = local(telling["viewpoint"])
            telling_row.uses_scene_manuscript = telling["shared"]
        placement = structure["placement"]
        if placement:
            session.add(
                ManuscriptPlacement(
                    tenant_id=tenant,
                    child_entity_id=entity_id,
                    parent_entity_id=local(placement["parent"]),
                    before_payload_id=local(placement["before"]),
                    position=placement["position"],
                )
            )
        redirect = structure["redirect"]
        if redirect:
            session.add(
                ManuscriptRedirect(
                    tenant_id=tenant,
                    source_id=entity_id,
                    destination_id=local(redirect["destination"]),
                    payload_id=local(redirect["payload"]),
                    child_id=local(redirect["child"]),
                )
            )
        for covered in structure["coverage"]:
            coverage_id = mapping.setdefault(covered["id"], uuid.uuid4())
            session.add(
                CarrierCoverage(
                    id=coverage_id,
                    tenant_id=tenant,
                    carrier_id=entity_id,
                    target_entity_id=local(covered["entry"]),
                    target_payload_id=local(covered["payload"]),
                    before_payload_id=local(covered["before"]),
                    position=covered["position"],
                )
            )
        for field, settings_model in (
            ("numbering", ManuscriptNumbering),
            ("contents", ManuscriptContents),
        ):
            if structure[field] is not None:
                session.add(
                    settings_model(entity_id=entity_id, tenant_id=tenant, settings=structure[field])
                )
    for key in choices:
        id, field = key.rsplit(":", 1)
        link = reviewed.links.get(id)
        if not link:
            continue  # Keeping an incoming addition does not create a copy link.
        saved = dict(link.manuscript_baseline or {"format": 1})
        if "information_id" not in saved:
            saved["information_id"] = next(
                (
                    str(info_id)
                    for info_id, value in reviewed.local_content.information.items()
                    if value.entity_id == link.entity_id and value.type == "manuscript"
                ),
                None,
            )
        if field == "entry":
            saved.update({field: reviewed.source[id][field] for field in ("bundle", "structure")})
        else:
            saved[field] = reviewed.source[id][field]
        info = infos.get(id)
        if id in bundles:
            saved["information_id"] = (
                str(info.id) if info and target[id]["bundle"] is not None else None
            )
        all_payloads = (target.get(id, {}).get("bundle") or {}).get("payloads", [])
        identities = dict(saved.get("identities", {}))
        identities.update(
            {str(mapping[p["id"]]): p["id"] for p in all_payloads if p["id"] in mapping}
        )
        saved["identities"] = identities
        coverage = dict(saved.get("coverage_identities", {}))
        coverage.update(
            {
                str(mapping[p["id"]]): p["id"]
                for p in target.get(id, {}).get("structure", {}).get("coverage", [])
                if p["id"] in mapping
            }
        )
        saved["coverage_identities"] = coverage
        link.manuscript_baseline = saved
    checkpoint = ManuscriptRepositoryUpdate(
        id=uuid.uuid4(),
        tenant_id=tenant,
        entry_id=root,
        actor_id=user.id,
        checkpoint={
            "before": {id: reviewed.local.get(id) for id in changed},
            "after": {id: target[id] for id in changed},
            "choices": choices,
            "entries": [str(local(id)) for id in changed],
            "information": [str(info.id) for info in infos.values() if info],
        },
    )
    session.add(checkpoint)
    await session.flush()
    return checkpoint.id
