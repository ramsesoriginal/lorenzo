import createClient from "openapi-fetch";
import { z } from "zod";
import type { components, paths } from "./lorenzo-schema.js";

export type OwnedByResponse = components["schemas"]["OwnedByResponse"];
export type ItemInstanceOut = components["schemas"]["ItemInstanceOut"];

/** One of the caller's own characters (a `being`), as far as this client cares. */
export type ControlledCharacter = Readonly<{ entityId: string; name: string }>;

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
     * This caller's own controlled characters in `tenantId`, sourced from
     * `GET /me`'s `players[].characters` (ADR 0031/RFC 0004 - now part of
     * the real generated schema, no longer provisional). A `Player` row's
     * `characters` come from `character_player` - every character that
     * player's user account pilots, not just their primary-owned one.
     */
    async getControlledCharacters(
      tenantId: string,
      accessToken: string,
    ): Promise<readonly ControlledCharacter[]> {
      const { data, error, response } = await client.GET("/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (error !== undefined) throw toApiError(error, response.status);

      return data.players
        .filter((player) => player.tenant_id === tenantId)
        .flatMap((player) =>
          player.characters.map((c) => ({ entityId: c.entity_id, name: c.name }) as const),
        );
    },
  };
}
