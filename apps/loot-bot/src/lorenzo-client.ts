import createClient from "openapi-fetch";
import { z } from "zod";
import type { components, paths } from "./lorenzo-schema.js";

export type OwnedByResponse = components["schemas"]["OwnedByResponse"];
export type ItemInstanceOut = components["schemas"]["ItemInstanceOut"];
export type ItemOut = components["schemas"]["ItemOut"];
export type EntityDetailOut = components["schemas"]["EntityDetailOut"];
export type InformationOut = components["schemas"]["InformationOut"];
export type BulkAssignItem = components["schemas"]["BulkAssignItem"];
export type BulkAssignResultItem = components["schemas"]["BulkAssignResultItem"];
export type GroupMemberResultItem = components["schemas"]["GroupMemberResultItem"];
export type BulkMoveResultItem = components["schemas"]["BulkMoveResultItem"];

/** A read paired with the `ETag` the server sent alongside it, if any -
 * `null` until every write route actually sends one back (tracked
 * separately; some already do, see ADR 0051's amendment). Passed back as
 * `If-Match` on a subsequent write against the *same* instance to guard
 * against clobbering a concurrent change - optimistic concurrency, not a
 * lock: absent or stale just means "someone else touched this first,"
 * surfaced as a 412 the caller decides how to handle. */
export type WithEtag<T> = Readonly<{ data: T; etag: string | null }>;

/** One of the caller's own characters (a `being`), as far as this client cares. */
export type ControlledCharacter = Readonly<{ entityId: string; name: string }>;

/** One `Player` row of the caller's own (`GET /me`), keeping `campaignId` -
 * `getControlledCharacters` deliberately drops it, but `/give`'s target
 * autocomplete (ADR 0051) needs it to know which campaign's roster to
 * search. */
export type MyPlayer = Readonly<{
  campaignId: string;
  characters: readonly ControlledCharacter[];
}>;

/**
 * Everything `/whoami` (and `/introduce`'s curated subset of it) shows,
 * out of one `GET /me` call. `email`/`nickname`/`displayName`/`pronouns`/
 * `bio`/`locales`/`color`/`pictureUrl` are ADR 0060's profile fields,
 * carried straight through - none of them are tenant-scoped, unlike the
 * three below:
 *
 * `membershipRole` and `characters` are filtered to this bot's own tenant
 * the same way {@link getMyPlayers}/{@link getControlledCharacters}
 * already do (flat, not grouped by campaign like `MyPlayer` -
 * `PlayerContextOut` carries a campaign *id*, not its name, and a raw
 * UUID wouldn't read as "presented nicely"; character names alone are
 * enough for an identity check). `gmCampaignCount` deliberately isn't
 * tenant-filtered - `/me`'s `campaign_gm_grants` carries no `tenant_id` at
 * all, the same cross-tenant imprecision {@link isCampaignGm}'s own doc
 * comment already flags, so this is honestly a global count, not a
 * per-tenant one.
 */
export type MyProfile = Readonly<{
  email: string | null;
  nickname: string | null;
  displayName: string | null;
  pronouns: string | null;
  bio: string | null;
  locales: readonly string[];
  color: string | null;
  pictureUrl: string;
  membershipRole: string | null;
  characters: readonly ControlledCharacter[];
  gmCampaignCount: number;
}>;

/** One item instance the caller owns, flattened out of whichever
 * character/container it's actually grouped under - `/give`'s and
 * `/item`'s own "item" autocomplete both just want a flat pickable list. */
export type OwnedItem = Readonly<{
  entityId: string;
  title: string;
  quantity: number | null;
  /** ADR 0066 (main's) computed field - `true`/`false` when explicitly
   * tagged, `true` when unset but the instance currently holds something,
   * else `null` ("unknown"). `/move`'s and `/set-current`'s own container
   * autocomplete (ADR 0068) narrow to `isContainer === true` instead of
   * "everything you own." */
  isContainer: boolean | null;
  /** ADR 0043's tenant-unique, human-assigned name - `null` for the
   * (common) instance nobody ever named. Surfaced in replies so a GM who
   * prepped a container in `apps/inventory-web` can find it again by name
   * (RFC 0021). */
  slug: string | null;
}>;

function toOwnedItem(item: OwnedByResponse["groups"][number]["item_instances"][number]): OwnedItem {
  return {
    entityId: item.entity_id,
    title: item.title ?? "(untitled)",
    quantity: item.quantity,
    isContainer: item.is_container,
    slug: item.slug,
  };
}

/** One group entity (ADR 0028/0045) - a bare `entity` with no dedicated
 * table, defined purely by having members; `/note`'s `visibility:group`
 * option (ADR 0052) sources its autocomplete from this. */
export type GroupSummary = Readonly<{ entityId: string; name: string }>;

export class LorenzoApiError extends Error {
  readonly status: number;
  readonly problemType: string | undefined;

  constructor(message: string, status: number, problemType?: string) {
    super(message);
    this.name = "LorenzoApiError";
    this.status = status;
    this.problemType = problemType;
  }
}

// RFC 9457 "Problem Details" - every apps/api error response is shaped this
// way (errors.py/exceptions.py, ADR 0020). Only used to extract a message;
// deliberately permissive (all fields optional) since we don't control this
// shape and a slightly-different-than-expected problem body should still
// produce a readable error, not a second failure.
const problemSchema = z.object({
  type: z.string().optional(),
  title: z.string().optional(),
  detail: z.string().optional(),
});

function toApiError(error: unknown, status: number): LorenzoApiError {
  const parsed = problemSchema.safeParse(error);
  const problem = parsed.success ? parsed.data : undefined;
  return new LorenzoApiError(
    problem?.detail ?? problem?.title ?? `Lorenzo API request failed (${status})`,
    status,
    problem?.type,
  );
}

export type LorenzoApiClient = ReturnType<typeof createLorenzoApiClient>;

export function createLorenzoApiClient(baseUrl: string) {
  const client = createClient<paths>({ baseUrl });

  return {
    /**
     * Direct contents of `containerEntityId` (ADR 0052's `/drop`) - never
     * recursive, matching how `/give`/`/set-current` already treat "what's
     * in here." First page only (up to the API's own default page size) -
     * a drop's own select menus cap out at Discord's 25-option limit
     * anyway, so nothing past that would ever be shown regardless.
     */
    async getItemInstancesByContainer(
      tenantId: string,
      containerEntityId: string,
      accessToken: string,
    ): Promise<readonly ItemInstanceOut[]> {
      const { data, error, response } = await client.GET("/tenants/{tenant_id}/item-instances", {
        params: {
          path: { tenant_id: tenantId },
          query: { container_id: containerEntityId, recursive: false },
        },
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data.items;
    },

    /**
     * Every item instance `characterEntityId` owns, grouped by direct
     * container - GET /tenants/{tenant_id}/item-instances/owned-by/{id}
     * (routers/item_instances.py). Requires the backend access-gate loosening
     * described in ADR 0050 to succeed for a caller with no tenant-wide
     * Membership; the response shape itself needs no change.
     */
    async getItemInstancesOwnedBy(
      tenantId: string,
      characterEntityId: string,
      accessToken: string,
    ): Promise<OwnedByResponse> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}",
        {
          params: { path: { tenant_id: tenantId, owner_entity_id: characterEntityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /**
     * Whether the caller holds at least one `CampaignGm` grant, anywhere -
     * `/me`'s `campaign_gm_grants` carries no `tenant_id`, so this can't
     * be narrowed to just this bot's own tenant client-side. Used only as
     * a fast, friendly gate before showing GM-only affordances (`/drop`,
     * "apply claims" - ADR 0052); the real authorization boundary is each
     * write's own server-side `can_manage_campaign` check, evaluated
     * against the real `tenant_id` in the request path and unaffected by
     * this method's own cross-tenant imprecision.
     */
    async isCampaignGm(accessToken: string): Promise<boolean> {
      const { data, error, response } = await client.GET("/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data.campaign_gm_grants.length > 0;
    },

    /** Every campaign id the caller holds a `CampaignGm` grant for -
     * `/award`'s own "which characters can I award to" source, same
     * cross-tenant caveat as {@link isCampaignGm}. */
    async getGmCampaignIds(accessToken: string): Promise<readonly string[]> {
      const { data, error, response } = await client.GET("/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data.campaign_gm_grants.map((grant) => grant.id);
    },

    /**
     * This caller's own `Player` rows in `tenantId` (each with the
     * characters it pilots), sourced from `GET /me`'s `players[]` (ADR
     * 0031/RFC 0004 - now part of the real generated schema, no longer
     * provisional).
     */
    async getMyPlayers(tenantId: string, accessToken: string): Promise<readonly MyPlayer[]> {
      const { data, error, response } = await client.GET("/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);

      return data.players
        .filter((player) => player.tenant_id === tenantId)
        .map((player) => ({
          campaignId: player.campaign_id,
          characters: player.characters.map((c) => ({ entityId: c.entity_id, name: c.name })),
        }));
    },

    /**
     * `/whoami` (ADR 0050) - one `GET /me` call rather than composing
     * getMyPlayers/isCampaignGm separately, which would hit this same
     * endpoint two or three times for what's really one screen of
     * information.
     */
    async getMyProfile(tenantId: string, accessToken: string): Promise<MyProfile> {
      const { data, error, response } = await client.GET("/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);

      return {
        email: data.email,
        nickname: data.nickname,
        displayName: data.display_name,
        pronouns: data.pronouns,
        bio: data.bio,
        locales: data.locales,
        color: data.user_color,
        pictureUrl: data.picture_url,
        membershipRole: data.memberships.find((m) => m.tenant_id === tenantId)?.role ?? null,
        characters: data.players
          .filter((player) => player.tenant_id === tenantId)
          .flatMap((player) =>
            player.characters.map((c) => ({ entityId: c.entity_id, name: c.name })),
          ),
        gmCampaignCount: data.campaign_gm_grants.length,
      };
    },

    /**
     * This caller's own controlled characters in `tenantId`, across every
     * campaign - a flattened view of `getMyPlayers`, for callers (like
     * `/inventory`) that don't care which campaign a character belongs to.
     */
    async getControlledCharacters(
      tenantId: string,
      accessToken: string,
    ): Promise<readonly ControlledCharacter[]> {
      const players = await this.getMyPlayers(tenantId, accessToken);
      return players.flatMap((player) => player.characters);
    },

    /** Every item instance owned by any of the caller's own characters,
     * flattened across characters and containers - `/give`'s and `/item`'s
     * "item" autocomplete both source from this. */
    async getMyItemInstances(tenantId: string, accessToken: string): Promise<readonly OwnedItem[]> {
      const characters = await this.getControlledCharacters(tenantId, accessToken);
      const perCharacter = await Promise.all(
        characters.map(async (character) => {
          const response = await this.getItemInstancesOwnedBy(
            tenantId,
            character.entityId,
            accessToken,
          );
          return response.groups.flatMap((group) => group.item_instances.map(toOwnedItem));
        }),
      );
      return perCharacter.flat();
    },

    /** GET /tenants/{tenant_id}/item-instances/unowned - every instance with
     * no owner at all, flattened out of the API's per-container grouping.
     * What a GM's pre-made loot container looks like before `/drop` (ADR
     * 0052) hands it out: nothing owns it, so `getMyItemInstances` can
     * never see it. Ownerless instances are visible to any tenant
     * participant (ADR 0040), so this needs no GM gate of its own. Not
     * paginated, matching `owned-by`. */
    async getUnownedItemInstances(
      tenantId: string,
      accessToken: string,
    ): Promise<readonly OwnedItem[]> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/item-instances/unowned",
        {
          params: { path: { tenant_id: tenantId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data.groups.flatMap((group) => group.item_instances.map(toOwnedItem));
    },

    /** GET /tenants/{tenant_id}/item-instances/{entity_id} - the current
     * state of one instance, used by /give (ADR 0051) to decide split-vs-
     * transfer against a fresh quantity rather than a possibly-stale
     * autocomplete value. Returns the response's `ETag` alongside the body
     * (Phase 0 amendment to ADR 0051) - pass it back as `ifMatch` on
     * whichever write acts on this same instance next. */
    async getItemInstance(
      tenantId: string,
      entityId: string,
      accessToken: string,
    ): Promise<WithEtag<ItemInstanceOut>> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/item-instances/{entity_id}",
        {
          params: { path: { tenant_id: tenantId, entity_id: entityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return { data, etag: response.headers.get("etag") };
    },

    /** GET .../item-instances/by-slug/{slug} (ADR 0043) - resolves a
     * human-assigned slug to its current instance state, same `WithEtag`
     * shape as {@link getItemInstance}. `/drop`'s `container` option (ADR
     * 0052) accepts either a raw entity id or a slug; this is the slug
     * path. 404s (`LorenzoApiError`) if nothing in this tenant currently
     * has that slug. */
    async getItemInstanceBySlug(
      tenantId: string,
      slug: string,
      accessToken: string,
    ): Promise<WithEtag<ItemInstanceOut>> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/item-instances/by-slug/{slug}",
        {
          params: { path: { tenant_id: tenantId, slug } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return { data, etag: response.headers.get("etag") };
    },

    /** POST .../item-instances/{entity_id}/split (ADR 0041) - splits
     * `quantity` units off the source's current stack into a new sibling
     * instance and returns that new instance. `ifMatch`, if given, guards
     * the *source* stack against a concurrent change (e.g. someone else
     * already split or took part of it) - sent as `If-Match`, a stale value
     * 412s. `ownerCharacterId`, if given, hands the split-off instance
     * straight to that character instead of copying the source's own owner
     * (ADR 0044's "split-with-owner") - one call instead of this followed
     * by a separate `setItemInstanceOwner`, closing the race window between
     * them. Omitted, the split-off instance keeps the source's owner,
     * unchanged from before ADR 0044. */
    async splitItemInstance(
      tenantId: string,
      entityId: string,
      quantity: number,
      accessToken: string,
      ifMatch?: string,
      ownerCharacterId?: string,
    ): Promise<WithEtag<ItemInstanceOut>> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/item-instances/{entity_id}/split",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: {
            quantity,
            ...(ownerCharacterId !== undefined ? { owner_character_id: ownerCharacterId } : {}),
          },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return { data, etag: response.headers.get("etag") };
    },

    /** PUT .../item-instances/{entity_id}/owner - replaces the instance's
     * owner outright (works for both "set for the first time" and
     * "transfer"). `ifMatch`, if given, is sent as `If-Match` - a stale
     * value 412s rather than silently overwriting a concurrent change.
     * Note: owner writes don't change the instance's own `ETag` (ADR 0032
     * deliberately never touches `entity.updated_at` for this), so this
     * only actually catches a race against an intervening rename, not
     * against another owner/container write to the same instance - a real,
     * documented limitation, not an oversight (see ADR 0051's amendment). */
    async setItemInstanceOwner(
      tenantId: string,
      entityId: string,
      ownerCharacterId: string,
      accessToken: string,
      ifMatch?: string,
    ): Promise<ItemInstanceOut> {
      const { data, error, response } = await client.PUT(
        "/tenants/{tenant_id}/item-instances/{entity_id}/owner",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: { owner_character_id: ownerCharacterId },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** DELETE .../item-instances/{entity_id} - a plain cascade delete
     * (ADR 0068's `/confiscate`, GM-only in this bot even though the
     * route itself is self-or-managed like every other write here - a
     * player destroying their own item isn't a scenario this bot exposes
     * a command for). `ifMatch`, if given, is sent as `If-Match`, same
     * treatment as every other write below. */
    async deleteItemInstance(
      tenantId: string,
      entityId: string,
      accessToken: string,
      ifMatch?: string,
    ): Promise<void> {
      const { error, response } = await client.DELETE(
        "/tenants/{tenant_id}/item-instances/{entity_id}",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
    },

    /** PATCH .../item-instances/{entity_id} - renames an instance
     * (ADR 0068's `/rename`; owner/container have their own dedicated
     * sub-resource actions, per `ItemInstanceUpdate`'s own docstring, so
     * this is the only field this route ever actually changes today).
     * Same `ifMatch` treatment as every other write below. */
    async renameItemInstance(
      tenantId: string,
      entityId: string,
      name: string,
      accessToken: string,
      ifMatch?: string,
    ): Promise<ItemInstanceOut> {
      const { data, error, response } = await client.PATCH(
        "/tenants/{tenant_id}/item-instances/{entity_id}",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: { name },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** POST .../item-instances/{entity_id}/merge - consumes `entityId`'s
     * whole current stack into `intoEntityId`'s, then deletes `entityId`
     * (ADR 0044/0064's `/merge`). Returns the *surviving* instance
     * (`intoEntityId`'s new shape) - it keeps its own existing container
     * untouched, which is what already satisfies "a merge has to end up
     * in a container," not a separate mechanism. `ifMatch`, if given,
     * guards the *source* (`entityId`) only, mirroring split's own
     * single-sided precondition. */
    async mergeItemInstance(
      tenantId: string,
      entityId: string,
      intoEntityId: string,
      accessToken: string,
      ifMatch?: string,
    ): Promise<ItemInstanceOut> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: { into_entity_id: intoEntityId },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** PUT .../item-instances/{entity_id}/container - moves an item to a
     * new container, `/move`'s own write. Same `ifMatch` treatment as
     * {@link setItemInstanceOwner}. */
    async setItemInstanceContainer(
      tenantId: string,
      entityId: string,
      containerEntityId: string,
      accessToken: string,
      ifMatch?: string,
    ): Promise<ItemInstanceOut> {
      const { data, error, response } = await client.PUT(
        "/tenants/{tenant_id}/item-instances/{entity_id}/container",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: { container_entity_id: containerEntityId },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** POST .../entities/{entity_id}/information - `/note`'s own write.
     * `isPublic: false` and no follow-up {@link addInformationKnower} call
     * makes it GM-private (relies on ADR 0035's GM-reachability bypass);
     * `isPublic: false` plus one knower call makes it visible to exactly
     * that one entity (plus GM/orga) - the API has no "the author sees
     * their own writes for free" default, so a private note needs that
     * explicit follow-up every time. */
    async createInformation(
      tenantId: string,
      entityId: string,
      fields: { title: string; type: string; isPublic: boolean; content: string },
      accessToken: string,
    ): Promise<InformationOut> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/entities/{entity_id}/information",
        {
          params: { path: { tenant_id: tenantId, entity_id: entityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: {
            title: fields.title,
            type: fields.type,
            is_public: fields.isPublic,
            content: fields.content,
            // No per-user locale concept in this bot yet (same call this
            // codebase already made for /item's own descriptions) - the
            // API's own default, sent explicitly since openapi-typescript
            // still marks a defaulted field required.
            locale: "en-US",
          },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** PUT .../information/{information_id}/knowers/{knower_entity_id} -
     * grants one more entity (a character, or a group once one exists)
     * visibility into an already-created `Information` row. */
    async addInformationKnower(
      tenantId: string,
      informationId: string,
      knowerEntityId: string,
      accessToken: string,
    ): Promise<InformationOut> {
      const { data, error, response } = await client.PUT(
        "/tenants/{tenant_id}/information/{information_id}/knowers/{knower_entity_id}",
        {
          params: {
            path: {
              tenant_id: tenantId,
              information_id: informationId,
              knower_entity_id: knowerEntityId,
            },
          },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /**
     * Every character in `campaignId`'s roster (GM's own characters aren't
     * distinguished here - GMing isn't tied to a character). Only a
     * participant of this specific campaign (a player, its GM, or a tenant
     * admin) can call this - exactly who `/give`'s target autocomplete
     * (ADR 0051) should be offering choices to anyway. First page only
     * (up to 50 players) - a party roster is bounded by construction.
     */
    async getCampaignPlayers(
      tenantId: string,
      campaignId: string,
      accessToken: string,
    ): Promise<readonly ControlledCharacter[]> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        {
          params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);

      return data.items.flatMap((player) =>
        player.characters.map((c) => ({ entityId: c.entity_id, name: c.name })),
      );
    },

    /** GET /tenants/{tenant_id}/characters/{character_id} - just the name,
     * for /give's (ADR 0051) confirmation message: Discord autocomplete
     * only returns the `value` a user picked, not the `name` they saw, so
     * a friendly "gave it to X" reply needs a fresh lookup. */
    async getCharacterName(
      tenantId: string,
      characterId: string,
      accessToken: string,
    ): Promise<string> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/characters/{character_id}",
        {
          params: { path: { tenant_id: tenantId, character_id: characterId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data.name;
    },

    /** GET /tenants/{tenant_id}/items - the item *catalog* (prototypes),
     * not instances. First page only - no search query param exists on
     * this endpoint, so `/award`'s item autocomplete filters this
     * client-side, same caveat every other catalog-sized autocomplete in
     * this codebase already accepts. */
    async listItems(tenantId: string, accessToken: string): Promise<readonly ItemOut[]> {
      const { data, error, response } = await client.GET("/tenants/{tenant_id}/items", {
        params: { path: { tenant_id: tenantId } },
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data.items;
    },

    /** POST /tenants/{tenant_id}/item-instances - instantiates a new item
     * instance from a catalog prototype, `/award`'s own write. `quantity`
     * isn't a creation-time field (ADR 0041 - it lives on `Containment`,
     * not `ItemInstance`), so awarding a stack needs `containerEntityId`
     * given; `/award` itself is responsible for deciding what to do when
     * it's missing, not this method. */
    async createItemInstance(
      tenantId: string,
      prototypeId: string,
      ownerCharacterId: string,
      containerEntityId: string | undefined,
      accessToken: string,
    ): Promise<ItemInstanceOut> {
      const { data, error, response } = await client.POST("/tenants/{tenant_id}/item-instances", {
        params: { path: { tenant_id: tenantId } },
        headers: { Authorization: `Bearer ${accessToken}` },
        body: {
          prototype_id: prototypeId,
          owner_character_id: ownerCharacterId,
          ...(containerEntityId !== undefined ? { container_entity_id: containerEntityId } : {}),
        },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** GET /tenants/{tenant_id}/entities/{entity_id} - `/item`'s own read
     * (ADR: display item). Chosen over `GET /item-instances/{id}`
     * deliberately: `EntityDetailOut.information` is the full,
     * already-visibility-filtered list of every `Information` row on the
     * entity (any `type`, not just ones literally typed "description"),
     * where `ItemInstanceOut.descriptions`/`.pictures` only surface
     * description/picture-kind payloads - the fuller shape is what "show
     * me everything about this item, including GM/player notes I'm
     * allowed to see" needs. */
    async getEntity(
      tenantId: string,
      entityId: string,
      accessToken: string,
    ): Promise<EntityDetailOut> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/entities/{entity_id}",
        {
          params: { path: { tenant_id: tenantId, entity_id: entityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** POST .../item-instances/bulk-assign (ADR 0044) - resolves several
     * already-decided claim assignments in one request. Always `200`, one
     * `BulkAssignResultItem` per input entry regardless of outcome - a
     * stale `if_match`/already-taken/not-enough-left item becomes that
     * entry's own `"error"` status, not a thrown exception, so `/drop`'s
     * apply-claims (ADR 0052) can map every result to a per-claim outcome
     * without a partial-failure try/catch of its own. */
    async bulkAssignItemInstances(
      tenantId: string,
      items: readonly BulkAssignItem[],
      accessToken: string,
    ): Promise<readonly BulkAssignResultItem[]> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/item-instances/bulk-assign",
        {
          params: { path: { tenant_id: tenantId } },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: [...items],
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** GET .../groups (ADR 0045) - every group entity this tenant currently
     * has (a group is just an entity with at least one `GroupMember` row
     * naming it, no dedicated table). First page only, same convention as
     * every other catalog-sized listing in this client. `/note`'s
     * `visibility:group` option (ADR 0052) sources its autocomplete here. */
    async listGroups(tenantId: string, accessToken: string): Promise<readonly GroupSummary[]> {
      const { data, error, response } = await client.GET("/tenants/{tenant_id}/groups", {
        params: { path: { tenant_id: tenantId } },
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return data.items.map((group) => ({ entityId: group.id, name: group.name }));
    },

    /** GET .../characters/{character_id}/groups (ADR 0045's "reverse
     * direction" addition) - every group a specific character belongs to.
     * `/my-groups`'s own source (ADR 0068), one call per controlled
     * character. Not paginated - bounded by one character's own
     * memberships, same convention as `getItemInstancesOwnedBy`. */
    async getCharacterGroups(
      tenantId: string,
      characterEntityId: string,
      accessToken: string,
    ): Promise<readonly GroupSummary[]> {
      const { data, error, response } = await client.GET(
        "/tenants/{tenant_id}/characters/{character_id}/groups",
        {
          params: { path: { tenant_id: tenantId, character_id: characterEntityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data.map((group) => ({ entityId: group.id, name: group.name }));
    },

    /** POST /tenants/{tenant_id}/groups (ADR 0064) - creates a new group
     * entity, optionally with its initial members in the same call.
     * `/add-to-group`/`/add-channel-to-group`'s own "create it, if not yet
     * present" path (ADR 0068). */
    async createGroup(
      tenantId: string,
      name: string,
      memberCharacterIds: readonly string[],
      accessToken: string,
    ): Promise<GroupSummary> {
      const { data, error, response } = await client.POST("/tenants/{tenant_id}/groups", {
        params: { path: { tenant_id: tenantId } },
        headers: { Authorization: `Bearer ${accessToken}` },
        body: { name, member_character_ids: [...memberCharacterIds] },
      });
      if (error !== undefined) throw toApiError(error, response.status);
      return { entityId: data.id, name: data.name };
    },

    /** PUT .../groups/{group_entity_id}/members/{character_entity_id}
     * (ADR 0064) - idempotent single-member add, returns the group's full
     * updated member list. */
    async addGroupMember(
      tenantId: string,
      groupEntityId: string,
      characterEntityId: string,
      accessToken: string,
    ): Promise<readonly GroupSummary[]> {
      const { data, error, response } = await client.PUT(
        "/tenants/{tenant_id}/groups/{group_entity_id}/members/{character_entity_id}",
        {
          params: {
            path: {
              tenant_id: tenantId,
              group_entity_id: groupEntityId,
              character_entity_id: characterEntityId,
            },
          },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data.map((member) => ({ entityId: member.id, name: member.name }));
    },

    /** POST .../groups/{group_entity_id}/members/bulk (ADR 0064) - adds
     * several characters to an existing group in one call, never
     * all-or-nothing (one result per input id regardless of outcome). */
    async bulkAddGroupMembers(
      tenantId: string,
      groupEntityId: string,
      characterEntityIds: readonly string[],
      accessToken: string,
    ): Promise<readonly GroupMemberResultItem[]> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/groups/{group_entity_id}/members/bulk",
        {
          params: { path: { tenant_id: tenantId, group_entity_id: groupEntityId } },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: [...characterEntityIds],
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },

    /** POST .../item-instances/bulk-move (ADR 0065) - `/move-bulk`'s own
     * write (ADR 0068): empties every item directly inside
     * `fromContainerEntityId` into `toContainerEntityId` in one call, never
     * all-or-nothing. The API also supports an explicit `items` list mode
     * (mutually exclusive with `fromContainerEntityId`) - not used by this
     * bot yet, no wrapper needed for it until something actually calls it. */
    async bulkMoveItemInstancesFromContainer(
      tenantId: string,
      fromContainerEntityId: string,
      toContainerEntityId: string,
      accessToken: string,
    ): Promise<readonly BulkMoveResultItem[]> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/item-instances/bulk-move",
        {
          params: { path: { tenant_id: tenantId } },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: {
            to_container_entity_id: toContainerEntityId,
            from_container_entity_id: fromContainerEntityId,
          },
        },
      );
      if (error !== undefined) throw toApiError(error, response.status);
      return data;
    },
  };
}
