// A test's own world, built through the API as its people would build it (ADR 0114): a tenant
// whose owner GMs its one campaign, two players with a character each, and the stats the
// app shows. Each test builds its own, with fresh people, so tests can't see each other.
import { randomUUID } from 'node:crypto';
import { type Api, apiAs, ok } from './api.ts';

export type Person = { name: string; subject: string; userId: string; api: Api };
export type Player = Person & { playerId: string; character: { entity_id: string; name: string } };

const STATS = {
  tags: ['is_container', 'is_magical', 'is_cursed'],
  physical: ['weight'],
  economic: ['price'],
} as const;
type Stat = (typeof STATS)[keyof typeof STATS][number];

export type ItemOptions = {
  prototypes?: string[];
  description?: string;
  /** Tags set on for this item. */
  tags?: Stat[];
  stats?: Partial<Record<Stat, number>>;
  /** In the public catalog, for players to list (ADR 0116). */
  public?: boolean;
};

export type InstanceOptions = { owner?: Player; container?: string; slug?: string };

export async function person(name: string, roles: string[] = []): Promise<Person> {
  const subject = `${name.toLowerCase()}-${randomUUID()}`;
  const api = await apiAs(subject, roles);
  const me = await ok(api.GET('/me'));
  await ok(api.PATCH('/me', { body: { display_name: name } }));
  return { name, subject, userId: me.id, api };
}

export async function buildWorld() {
  const gm = await person('Gwen', ['tenant_creator']);
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
  await ok(
    api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: tenant.id, campaign_id: campaign.id, user_id: gm.userId } },
    }),
  );

  async function player(name: string, characterName: string): Promise<Player> {
    const who = await person(name);
    const seat = await ok(
      api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
        params: { path: { tenant_id: tenant.id, campaign_id: campaign.id } },
        body: { user_id: who.userId },
      }),
    );
    const character = await ok(
      api.POST('/tenants/{tenant_id}/characters', {
        ...t,
        body: { name: characterName, owner_player_id: seat.id, player_ids: [seat.id] },
      }),
    );
    return { ...who, playerId: seat.id, character };
  }

  const stats = {} as Record<Stat, string>;
  for (const [group, names] of Object.entries(STATS)) {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/stat-groups', {
        ...t,
        body: { name: group, priority: 0, mandatory: false },
      }),
    );
    for (const name of names) {
      const value_type = group === 'tags' ? 'bool' : 'int';
      const definition = await ok(
        api.POST('/tenants/{tenant_id}/stat-definitions', {
          ...t,
          body: { name, stat_group_id: created.id, value_type },
        }),
      );
      stats[name] = definition.id;
    }
  }

  /** Writes a public description, as a GM does. */
  async function describe(entityId: string, content: string, title = '') {
    await ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { title, type: 'description', is_public: true, content, locale: 'en' },
      }),
    );
  }

  async function item(name: string, options: ItemOptions = {}): Promise<string> {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/items', {
        ...t,
        body: {
          name,
          prototype_ids: options.prototypes ?? [],
          in_public_catalog: options.public ?? false,
        },
      }),
    );
    const entity = { tenant_id: tenant.id, entity_id: created.entity_id };
    for (const tag of options.tags ?? []) {
      await ok(
        api.PUT('/tenants/{tenant_id}/entities/{entity_id}/tags/{stat_definition_id}', {
          params: { path: { ...entity, stat_definition_id: stats[tag] } },
        }),
      );
    }
    for (const [stat, value] of Object.entries(options.stats ?? {})) {
      await ok(
        api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
          params: { path: { ...entity, stat_definition_id: stats[stat as Stat] } },
          body: { value },
        }),
      );
    }
    if (options.description) await describe(created.entity_id, options.description);
    return created.entity_id;
  }

  async function instance(itemId: string, options: InstanceOptions = {}): Promise<string> {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/item-instances', {
        ...t,
        body: {
          prototype_id: itemId,
          owner_character_id: options.owner?.character.entity_id ?? null,
          container_entity_id: options.container ?? null,
          slug: options.slug ?? null,
        },
      }),
    );
    return created.entity_id;
  }

  /** `count` of an item as one stack in `container` (a stack's count lives on its containment). */
  async function stack(
    itemId: string,
    count: number,
    options: InstanceOptions & { container: string },
  ) {
    const [first, ...rest] = await Promise.all(
      Array.from({ length: count }, () => instance(itemId, options)),
    );
    for (const other of rest) {
      await ok(
        api.POST('/tenants/{tenant_id}/item-instances/{entity_id}/merge', {
          params: { path: { tenant_id: tenant.id, entity_id: other } },
          body: { into_entity_id: first as string },
        }),
      );
    }
    return first as string;
  }

  async function slug(entityId: string, value: string) {
    await ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
        params: { path: { tenant_id: tenant.id, entity_id: entityId } },
        body: { slug: value },
      }),
    );
  }

  /** What `player`'s character carries, as the API says: `Container: Item ×n` lines, sorted. */
  async function carried(player: Player): Promise<string[]> {
    const owned = await ok(
      api.GET('/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}', {
        params: { path: { tenant_id: tenant.id, owner_entity_id: player.character.entity_id } },
      }),
    );
    return owned.groups
      .flatMap((group) =>
        group.item_instances.map((item) => {
          const count = item.quantity && item.quantity > 1 ? ` ×${item.quantity}` : '';
          return `${group.container?.name ?? '(none)'}: ${item.title}${count}`;
        }),
      )
      .sort();
  }

  return {
    tenantId: tenant.id,
    tenantName: tenant.name,
    campaignId: campaign.id,
    gm,
    pia: await player('Pia', 'Ashfang'),
    oskar: await player('Oskar', 'Brisk'),
    stats,
    describe,
    item,
    instance,
    stack,
    slug,
    carried,
  };
}

export type World = Awaited<ReturnType<typeof buildWorld>>;
