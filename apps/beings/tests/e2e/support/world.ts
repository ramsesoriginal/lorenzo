// A test's own world, built through the API as its people would build it (ADR 0114): a library whose
// owner GMs its one campaign, two players with a character each, an NPC, the stats the page shows,
// and a few things to carry. Each test builds its own, with fresh people, so tests can't see each other.
import { randomUUID } from 'node:crypto';
import { type Api, apiAs, ok } from './api.ts';

export type Person = { name: string; subject: string; userId: string; api: Api };
export type Player = Person & { playerId: string; character: { entity_id: string; name: string } };

export async function person(name: string, roles: string[] = []): Promise<Person> {
  const subject = `${name.toLowerCase()}-${randomUUID()}`;
  const api = await apiAs(subject, roles);
  const me = await ok(api.GET('/me'));
  await ok(api.PATCH('/me', { body: { display_name: name } }));
  return { name, subject, userId: me.id, api };
}

export async function buildWorld() {
  const [gm, piaWho, oskarWho] = await Promise.all([
    person('Gwen', ['tenant_creator']),
    person('Pia'),
    person('Oskar'),
  ]);
  const api = gm.api;
  const tenant = await ok(api.POST('/tenants', { body: { name: `Vale of ${randomUUID()}` } }));
  const t = { params: { path: { tenant_id: tenant.id } } };

  const campaign = await ok(
    api.POST('/tenants/{tenant_id}/campaigns', {
      ...t,
      body: {
        name: 'The Sunken Crown',
        game_system: 'D&D 5e',
        slug: 'sunken-crown',
        description: '',
        secret: false,
      },
    }),
  );
  const other = await ok(
    api.POST('/tenants/{tenant_id}/campaigns', {
      ...t,
      body: {
        name: 'Ash Road',
        game_system: 'D&D 5e',
        slug: 'ash-road',
        description: '',
        secret: false,
      },
    }),
  );

  async function seat(
    who: Person,
    characterName: string,
    campaignId = campaign.id,
  ): Promise<Player> {
    const seated = await ok(
      api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
        params: { path: { tenant_id: tenant.id, campaign_id: campaignId } },
        body: { user_id: who.userId },
      }),
    );
    const character = await ok(
      api.POST('/tenants/{tenant_id}/characters', {
        ...t,
        body: { name: characterName, owner_player_id: seated.id, player_ids: [seated.id] },
      }),
    );
    return { ...who, playerId: seated.id, character };
  }

  const [pia, oskar] = await Promise.all([
    seat(piaWho, 'Ashfang'),
    seat(oskarWho, 'Brisk'),
    ok(
      api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
        params: { path: { tenant_id: tenant.id, campaign_id: campaign.id, user_id: gm.userId } },
      }),
    ),
    ok(
      api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
        params: { path: { tenant_id: tenant.id, campaign_id: other.id, user_id: gm.userId } },
      }),
    ),
  ]);

  /** An NPC: a character no player plays. */
  async function npc(name: string): Promise<{ entity_id: string; name: string }> {
    return ok(
      api.POST('/tenants/{tenant_id}/characters', { ...t, body: { name, player_ids: [] } }),
    );
  }

  /** A player of the second campaign, with a character there. */
  async function playerOfAshRoad(name: string, characterName: string): Promise<Player> {
    return seat(await person(name), characterName, other.id);
  }

  /** Writes a description (public), as a GM does. */
  async function describe(entityId: string, content: string) {
    await ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { title: '', type: 'description', is_public: true, content, locale: 'en' },
      }),
    );
  }

  /** Adds a note, as a GM does; private unless `isPublic`. */
  async function note(
    entityId: string,
    title: string,
    content: string,
    isPublic = false,
    type = 'note',
  ) {
    return ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { title, type, is_public: isPublic, content, locale: 'en' },
      }),
    );
  }

  /** A stat definition in a group of its own, for the page to show and edit. */
  const groups = new Map<string, string>();

  /** A stat definition, in its group (made the first time it is named); `extra` sets how it is shown. */
  async function defineStat(
    group: string,
    name: string,
    value_type: 'int' | 'bool',
    extra: {
      adjustable_in_play?: boolean;
      pin?: boolean;
      signed?: boolean;
      unit?: string;
      max_hint_id?: string;
      min_hint_id?: string;
      resolved_hint_id?: string;
    } = {},
  ) {
    let groupId = groups.get(group);

    if (!groupId) {
      const created = await ok(
        api.POST('/tenants/{tenant_id}/stat-groups', {
          ...t,
          body: { name: group, priority: 0, mandatory: false },
        }),
      );

      groupId = created.id;
      groups.set(group, groupId);
    }

    return ok(
      api.POST('/tenants/{tenant_id}/stat-definitions', {
        ...t,
        body: {
          name,
          stat_group_id: groupId,
          value_type,
          adjustable_in_play: false,
          pin: false,
          signed: false,
          ...extra,
        },
      }),
    );
  }

  async function setStat(entityId: string, definitionId: string, value: number) {
    await ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
        params: {
          path: { tenant_id: tenant.id, entity_id: entityId, stat_definition_id: definitionId },
        },
        body: { value, acquire_group: true },
      }),
    );
  }

  /** A linear formula an entity holds: `source × multiplier + offset`. */
  async function formula(
    entityId: string,
    definitionId: string,
    sourceId: string,
    multiplier: string,
    offset: string,
  ) {
    await ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat_definition_id}', {
        params: {
          path: { tenant_id: tenant.id, entity_id: entityId, stat_definition_id: definitionId },
        },
        body: {
          kind: 'linear',
          source_stat_definition_id: sourceId,
          multiplier,
          offset,
          round_mode: 'none',
        },
      }),
    );
  }

  /** An item, and an instance of it owned by `owner`; the instance's entity id. */
  async function carry(owner: { entity_id: string }, name: string, quantity = 1) {
    const item = await ok(
      api.POST('/tenants/{tenant_id}/items', {
        ...t,
        body: { name, prototype_ids: [], in_public_catalog: false },
      }),
    );
    const made = await ok(
      api.POST('/tenants/{tenant_id}/item-instances', {
        ...t,
        body: {
          prototype_id: item.entity_id,
          owner_character_id: owner.entity_id,
          container_entity_id: null,
          slug: null,
          override: false,
          quantity,
        },
      }),
    );
    return made.entity_id;
  }

  /** An item instance the being holds directly: equipped, with stats of its own. */
  async function equip(
    being: { entity_id: string },
    name: string,
    stats: [definitionId: string, value: number][] = [],
  ) {
    const item = await ok(
      api.POST('/tenants/{tenant_id}/items', {
        ...t,
        body: { name, prototype_ids: [], in_public_catalog: false },
      }),
    );
    const made = await ok(
      api.POST('/tenants/{tenant_id}/item-instances', {
        ...t,
        body: {
          prototype_id: item.entity_id,
          owner_character_id: being.entity_id,
          container_entity_id: being.entity_id,
          slug: null,
          override: false,
          quantity: 1,
        },
      }),
    );

    for (const [definitionId, value] of stats) await setStat(made.entity_id, definitionId, value);

    return made.entity_id;
  }

  /** Tells the library where the datasheet finds weapons and abilities. */
  async function configureSheet(weaponGroupId: string | null, abilityType: string | null) {
    await ok(
      api.PATCH('/tenants/{tenant_id}', {
        ...t,
        body: { weapon_stat_group_id: weaponGroupId, ability_information_type: abilityType },
      }),
    );
  }

  async function slug(entityId: string, value: string) {
    await ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { slug: value },
      }),
    );
  }

  return {
    tenantId: tenant.id,
    tenantSlug: tenant.slug,
    tenantName: tenant.name,
    campaignId: campaign.id,
    otherCampaignId: other.id,
    gm,
    pia,
    oskar,
    npc,
    playerOfAshRoad,
    describe,
    note,
    defineStat,
    setStat,
    formula,
    equip,
    configureSheet,
    carry,
    slug,
  };
}

export type World = Awaited<ReturnType<typeof buildWorld>>;
