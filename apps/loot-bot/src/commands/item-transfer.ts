import type { ItemInstanceOut, LorenzoApiClient } from "../lorenzo-client.js";

/**
 * The split-vs-whole-transfer decision `/give` (ADR 0051) and `/drop`'s
 * take/apply-claims (ADR 0052) both need against an already-fetched,
 * already-etagged read of the *same* item - re-fetching is the caller's
 * job (each has its own reason to control exactly when: `/give` once,
 * right before deciding; apply-claims once per claim, every iteration of
 * its own loop), this is just what happens once that fresh state is in
 * hand.
 *
 * `requestedQuantity` given against a non-stacked item (`current.quantity`
 * is `null`) is rejected as `"not-a-stack"` rather than attempted - the
 * caller decides how to word that. `requestedQuantity` omitted, or at
 * least the current stack size, transfers the *whole* instance outright
 * (no split) - matches the split endpoint's own "splitting off all of it
 * isn't a split" rule. A caller wanting a stricter "there isn't enough
 * left" rejection (apply-claims, ADR 0052) checks that itself before
 * calling this - silently capping to "everything available" is `/give`'s
 * own accepted behavior, not assumed correct for every caller.
 */
export type TransferResult =
  | { kind: "not-a-stack" }
  | {
      kind: "transferred";
      given: ItemInstanceOut;
      splitting: boolean;
      requestedQuantity: number | null;
    };

export async function transferItem(
  client: LorenzoApiClient,
  tenantId: string,
  current: ItemInstanceOut,
  etag: string | null,
  requestedQuantity: number | null,
  targetCharacterId: string,
  accessToken: string,
): Promise<TransferResult> {
  if (requestedQuantity !== null && current.quantity === null) {
    return { kind: "not-a-stack" };
  }

  const currentQuantity = current.quantity ?? 1;
  const splitting = requestedQuantity !== null && requestedQuantity < currentQuantity;

  const given = splitting
    ? await splitAndTransfer(
        client,
        tenantId,
        current.entity_id,
        requestedQuantity,
        targetCharacterId,
        accessToken,
        etag,
      )
    : await client.setItemInstanceOwner(
        tenantId,
        current.entity_id,
        targetCharacterId,
        accessToken,
        etag ?? undefined,
      );

  return { kind: "transferred", given, splitting, requestedQuantity };
}

// `requestedQuantity` is a plain `number` here (not `number | null`) purely
// to keep transferItem's own ternary honest about which branch actually
// needs it - splitting is only ever true when it's already non-null.
//
// One call, not split-then-PUT-owner (ADR 0044's "split-with-owner") -
// closes the race window a separate follow-up owner-PUT would leave open
// between the two writes.
async function splitAndTransfer(
  client: LorenzoApiClient,
  tenantId: string,
  sourceEntityId: string,
  requestedQuantity: number,
  targetCharacterId: string,
  accessToken: string,
  sourceEtag: string | null,
): Promise<ItemInstanceOut> {
  const { data: given } = await client.splitItemInstance(
    tenantId,
    sourceEntityId,
    requestedQuantity,
    accessToken,
    sourceEtag ?? undefined,
    targetCharacterId,
  );
  return given;
}
