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
  async function note(entityId: string, title: string, content: string, isPublic = false) {
    return ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { title, type: 'note', is_public: isPublic, content, locale: 'en' },
      }),
    );
  }

  /** A stat definition in a group of its own, for the page to show and edit. */
  async function defineStat(group: string, name: string, value_type: 'int' | 'bool') {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/stat-groups', {
        ...t,
        body: { name: group, priority: 0, mandatory: false },
      }),
    );
    return ok(
      api.POST('/tenants/{tenant_id}/stat-definitions', {
        ...t,
        body: { name, stat_group_id: created.id, value_type },
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
    carry,
    slug,
  };
}

export type World = Awaited<ReturnType<typeof buildWorld>>;
