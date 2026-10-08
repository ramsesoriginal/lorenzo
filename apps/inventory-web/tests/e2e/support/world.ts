// A test's own world, built through the API as its people would build it (ADR 0114): a tenant
// whose owner GMs its one campaign, two players with a character each, and the stats the
// app shows. Each test builds its own, with fresh people, so tests can't see each other.
import { randomUUID } from 'node:crypto';
import { type Api, apiAs, ok } from './api.ts';

export type Person = { name: string; subject: string; userId: string; api: Api };
export type Player = Person & { playerId: string; character: { entity_id: string; name: string } };

const STATS = {
  tags: ['is_container', 'is_magical', 'is_cursed'],
  physical: ['weight', 'carry_capacity'],
  economic: ['price'],
} as const;
type Stat = (typeof STATS)[keyof typeof STATS][number];
/** The well-known enum stat binding reads (ADR 0129). */
export type Binding = 'on_own' | 'on_pickup' | 'on_equip' | 'none';

export type ItemOptions = {
  prototypes?: string[];
  description?: string;
  /** Tags set on for this item. */
  tags?: Stat[];
  stats?: Partial<Record<Stat, number>>;
  binding?: Binding;
  /** In the public catalog, for players to list (ADR 0116). */
  public?: boolean;
};

export type InstanceOptions = {
  owner?: Player;
  /** Any owning entity, such as a group (ADR 0124); `owner` wins if both are given. */
  ownerId?: string;
  container?: string;
  slug?: string;
};

export async function person(name: string, roles: string[] = []): Promise<Person> {
  const subject = `${name.toLowerCase()}-${randomUUID()}`;
  const api = await apiAs(subject, roles);
  const me = await ok(api.GET('/me'));
  await ok(api.PATCH('/me', { body: { display_name: name } }));
  return { name, subject, userId: me.id, api };
}

// A world is built before every test, and a round trip each, one after another, was most of the
// time that took. What doesn't depend on something else is made side by side. Nothing here reads
// the order things were made in: the app sorts by name, by position, or by random id.
export async function buildWorld() {
  const [gm, piaWho, oskarWho] = await Promise.all([
    person('Gwen', ['tenant_creator']),
    person('Pia'),
    person('Oskar'),
  ]);
  const api = gm.api;
  const tenant = await ok(api.POST('/tenants', { body: { name: `Vale of ${randomUUID()}` } }));
  const t = { params: { path: { tenant_id: tenant.id } } };

  async function seatPlayers() {
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

    async function player(who: Person, characterName: string): Promise<Player> {
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

    const [pia, oskar] = await Promise.all([
      player(piaWho, 'Ashfang'),
      player(oskarWho, 'Brisk'),
      ok(
        api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
          params: { path: { tenant_id: tenant.id, campaign_id: campaign.id, user_id: gm.userId } },
        }),
      ),
    ]);
    return { campaignId: campaign.id, pia, oskar };
  }

  async function defineStats() {
    const stats = {} as Record<Stat, string>;
    const groups = Object.entries(STATS).map(async ([group, names]) => {
      const created = await ok(
        api.POST('/tenants/{tenant_id}/stat-groups', {
          ...t,
          body: { name: group, priority: 0, mandatory: false },
        }),
      );
      await Promise.all(
        names.map(async (name) => {
          const value_type = group === 'tags' ? 'bool' : 'int';
          const definition = await ok(
            api.POST('/tenants/{tenant_id}/stat-definitions', {
              ...t,
              body: { name, stat_group_id: created.id, value_type },
            }),
          );
          stats[name] = definition.id;
        }),
      );
    });
    const rules = (async () => {
      const created = await ok(
        api.POST('/tenants/{tenant_id}/stat-groups', {
          ...t,
          body: { name: 'rules', priority: 0, mandatory: false },
        }),
      );
      return ok(
        api.POST('/tenants/{tenant_id}/stat-definitions', {
          ...t,
          body: {
            name: 'binding',
            stat_group_id: created.id,
            value_type: 'enum',
            enum_values: ['on_own', 'on_pickup', 'on_equip', 'none'],
          },
        }),
      );
    })();
    const [, binding] = await Promise.all([Promise.all(groups), rules]);
    return { stats, binding };
  }

  const [{ campaignId, pia, oskar }, { stats, binding }] = await Promise.all([
    seatPlayers(),
    defineStats(),
  ]);

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
    // Each of these is its own row on the new item, so they go in together.
    const setUp: Promise<unknown>[] = [];
    for (const tag of options.tags ?? []) {
      setUp.push(
        ok(
          api.PUT('/tenants/{tenant_id}/entities/{entity_id}/tags/{stat_definition_id}', {
            params: { path: { ...entity, stat_definition_id: stats[tag] } },
          }),
        ),
      );
    }
    for (const [stat, value] of Object.entries(options.stats ?? {})) {
      setUp.push(
        ok(
          api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
            params: { path: { ...entity, stat_definition_id: stats[stat as Stat] } },
            body: { value, acquire_group: false },
          }),
        ),
      );
    }
    if (options.binding) {
      setUp.push(
        ok(
          api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
            params: { path: { ...entity, stat_definition_id: binding.id } },
            body: { value: options.binding, acquire_group: false },
          }),
        ),
      );
    }
    if (options.description) setUp.push(describe(created.entity_id, options.description));
    await Promise.all(setUp);
    return created.entity_id;
  }

  async function instance(itemId: string, options: InstanceOptions = {}): Promise<string> {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/item-instances', {
        ...t,
        body: {
          prototype_id: itemId,
          owner_character_id: options.owner?.character.entity_id ?? options.ownerId ?? null,
          container_entity_id: options.container ?? null,
          slug: options.slug ?? null,
          override: false,
          quantity: 1,
        },
      }),
    );
    return created.entity_id;
  }

  /** Sets a stat on any entity - an instance, a character - as a GM does. */
  async function setStat(entityId: string, stat: Stat, value: number) {
    await ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
        params: {
          path: { tenant_id: tenant.id, entity_id: entityId, stat_definition_id: stats[stat] },
        },
        body: { value, acquire_group: false },
      }),
    );
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

  /** A group of `members`' characters, as a GM makes one (ADR 0064); its entity id. */
  async function group(name: string, members: Player[]): Promise<string> {
    const created = await ok(
      api.POST('/tenants/{tenant_id}/groups', {
        ...t,
        body: { name, member_character_ids: members.map((m) => m.character.entity_id) },
      }),
    );
    return created.id;
  }

  /** What `ownerId` owns, as the API says: `Container: Item` lines, sorted. */
  async function ownedBy(ownerId: string): Promise<string[]> {
    const owned = await ok(
      api.GET('/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}', {
        params: { path: { tenant_id: tenant.id, owner_entity_id: ownerId } },
      }),
    );
    return owned.groups
      .flatMap((g) => g.item_instances.map((i) => `${g.container?.name ?? '(none)'}: ${i.title}`))
      .sort();
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
    tenantSlug: tenant.slug,
    tenantName: tenant.name,
    campaignId,
    gm,
    pia,
    oskar,
    stats,
    describe,
    item,
    instance,
    setStat,
    stack,
    slug,
    carried,
    group,
    ownedBy,
  };
}

export type World = Awaited<ReturnType<typeof buildWorld>>;
