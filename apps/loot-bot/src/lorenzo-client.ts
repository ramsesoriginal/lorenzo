import createClient from "openapi-fetch";
import { z } from "zod";
import type { components, paths } from "./lorenzo-schema.js";

export type OwnedByResponse = components["schemas"]["OwnedByResponse"];
export type ItemInstanceOut = components["schemas"]["ItemInstanceOut"];

/** A read paired with the `ETag` the server sent alongside it, if any -
 * `null` until every write route actually sends one back (tracked
 * separately; some already do, see ADR 0043's amendment). Passed back as
 * `If-Match` on a subsequent write against the *same* instance to guard
 * against clobbering a concurrent change - optimistic concurrency, not a
 * lock: absent or stale just means "someone else touched this first,"
 * surfaced as a 412 the caller decides how to handle. */
export type WithEtag<T> = Readonly<{ data: T; etag: string | null }>;

/** One of the caller's own characters (a `being`), as far as this client cares. */
export type ControlledCharacter = Readonly<{ entityId: string; name: string }>;

/** One `Player` row of the caller's own (`GET /me`), keeping `campaignId` -
 * `getControlledCharacters` deliberately drops it, but `/give`'s target
 * autocomplete (ADR 0043) needs it to know which campaign's roster to
 * search. */
export type MyPlayer = Readonly<{
  campaignId: string;
  characters: readonly ControlledCharacter[];
}>;

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
     * Every item instance `characterEntityId` owns, grouped by direct
     * container - GET /tenants/{tenant_id}/item-instances/owned-by/{id}
     * (routers/item_instances.py). Requires the backend access-gate loosening
     * described in ADR 0042 to succeed for a caller with no tenant-wide
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

    /** GET /tenants/{tenant_id}/item-instances/{entity_id} - the current
     * state of one instance, used by /give (ADR 0043) to decide split-vs-
     * transfer against a fresh quantity rather than a possibly-stale
     * autocomplete value. Returns the response's `ETag` alongside the body
     * (Phase 0 amendment to ADR 0043) - pass it back as `ifMatch` on
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

    /** POST .../item-instances/{entity_id}/split (ADR 0041) - splits
     * `quantity` units off the source's current stack into a new sibling
     * instance (same owner/container as the source) and returns that new
     * instance. `ifMatch`, if given, guards the *source* stack against a
     * concurrent change (e.g. someone else already split or took part of
     * it) - sent as `If-Match`, a stale value 412s. The new instance's own
     * `ETag` comes back alongside its data, for chaining into the
     * `setItemInstanceOwner` call that normally follows a split. */
    async splitItemInstance(
      tenantId: string,
      entityId: string,
      quantity: number,
      accessToken: string,
      ifMatch?: string,
    ): Promise<WithEtag<ItemInstanceOut>> {
      const { data, error, response } = await client.POST(
        "/tenants/{tenant_id}/item-instances/{entity_id}/split",
        {
          params: {
            path: { tenant_id: tenantId, entity_id: entityId },
            ...(ifMatch !== undefined ? { header: { "if-match": ifMatch } } : {}),
          },
          headers: { Authorization: `Bearer ${accessToken}` },
          body: { quantity },
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
     * documented limitation, not an oversight (see ADR 0043's amendment). */
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

    /**
     * Every character in `campaignId`'s roster (GM's own characters aren't
     * distinguished here - GMing isn't tied to a character). Only a
     * participant of this specific campaign (a player, its GM, or a tenant
     * admin) can call this - exactly who `/give`'s target autocomplete
     * (ADR 0043) should be offering choices to anyway. First page only
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
     * for /give's (ADR 0043) confirmation message: Discord autocomplete
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
  };
}
