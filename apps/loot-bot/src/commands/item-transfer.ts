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

/**
 * `/confiscate`'s own split-vs-whole decision (ADR 0064) - the same shape
 * as {@link transferItem} above, minus the owner-reassignment step: a
 * partial-stack confiscation splits the requested amount off into a new
 * sibling instance first, then deletes *that* split-off instance, leaving
 * the rest with its original owner untouched; a whole-instance
 * confiscation just deletes the instance outright.
 */
export type DestroyResult =
  | { kind: "not-a-stack" }
  | { kind: "destroyed"; destroyedTitle: string; requestedQuantity: number | null };

export async function destroyItem(
  client: LorenzoApiClient,
  tenantId: string,
  current: ItemInstanceOut,
  etag: string | null,
  requestedQuantity: number | null,
  accessToken: string,
): Promise<DestroyResult> {
  if (requestedQuantity !== null && current.quantity === null) {
    return { kind: "not-a-stack" };
  }

  const currentQuantity = current.quantity ?? 1;
  const splitting = requestedQuantity !== null && requestedQuantity < currentQuantity;

  if (splitting) {
    const { data: splitOff } = await client.splitItemInstance(
      tenantId,
      current.entity_id,
      requestedQuantity,
      accessToken,
      etag ?? undefined,
    );
    await client.deleteItemInstance(tenantId, splitOff.entity_id, accessToken);
    return {
      kind: "destroyed",
      destroyedTitle: splitOff.title ?? "(untitled)",
      requestedQuantity,
    };
  }

  await client.deleteItemInstance(tenantId, current.entity_id, accessToken, etag ?? undefined);
  return {
    kind: "destroyed",
    destroyedTitle: current.title ?? "(untitled)",
    requestedQuantity,
  };
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
