import { getContainerPrototypeId, setContainerPrototypeId } from "../db.js";
import { type LorenzoApiClient, LorenzoApiError } from "../lorenzo-client.js";

/** The catalog item every `/container-new` sack is an instance of, found
 * (or created) by this exact name. */
export const SACK_NAME = "Sack";

export type SackPrototype = { kind: "ok"; prototypeId: string } | { kind: "needs-catalog-access" };

/**
 * Which catalog item to make a sack from (ADR 0091).
 *
 * Instantiating a prototype for your own character is self-service (ADR
 * 0032), but *finding* the prototype is not: every `/items` route requires
 * a tenant `Membership`, which ordinary players deliberately don't have. So
 * the id is stored once per tenant and reused by everyone:
 *
 * 1. Stored? Use it - no API call, works for any player.
 * 2. Otherwise look for a catalog item titled "Sack" and, failing that,
 *    create one - as the *caller*, with the caller's own token (this bot has
 *    no shared service token, ADR 0050). Whoever first runs the command
 *    with catalog access sets it up for everybody.
 * 3. If the caller has no catalog access (404 - a non-member is
 *    indistinguishable from a missing tenant, ADR 0023 - or 403), report
 *    "needs catalog access" so the command can tell them who to ask.
 *
 * The match is on `title`, case-insensitively: it's all `ItemOut` exposes,
 * and equals the item's name unless someone authored a description title.
 * The server-side `q` filter narrows by *name*, so a differently-titled
 * "Sack" is found by the search but not matched - and a second one is
 * created rather than guessing.
 */
export async function resolveSackPrototype(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
): Promise<SackPrototype> {
  const stored = await getContainerPrototypeId(tenantId);
  if (stored) return { kind: "ok", prototypeId: stored };

  try {
    const matches = await client.findItemsByName(tenantId, SACK_NAME, accessToken);
    const existing = matches.find(
      (item) => item.title.trim().toLowerCase() === SACK_NAME.toLowerCase(),
    );
    const prototypeId =
      existing?.entity_id ?? (await client.createItem(tenantId, SACK_NAME, accessToken)).entity_id;
    await setContainerPrototypeId(tenantId, prototypeId);
    return { kind: "ok", prototypeId };
  } catch (error) {
    if (error instanceof LorenzoApiError && (error.status === 404 || error.status === 403)) {
      return { kind: "needs-catalog-access" };
    }
    throw error;
  }
}
