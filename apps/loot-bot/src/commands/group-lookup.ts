import type { GroupSummary, LorenzoApiClient } from "../lorenzo-client.js";

/**
 * "Create it, if not yet present" (ADR 0068), shared by `/add-to-group`
 * and `/add-channel-to-group`: an exact, case-sensitive name match against
 * `listGroups`'s first page (same "first page only" convention every
 * other catalog-sized listing in this client already accepts) if one
 * exists, otherwise a fresh group created with `initialMemberCharacterIds`
 * already attached in the same call (`GroupCreate.member_character_ids`,
 * ADR 0064) - one round trip instead of create-then-add.
 */
export async function resolveOrCreateGroup(
  client: LorenzoApiClient,
  tenantId: string,
  name: string,
  accessToken: string,
  initialMemberCharacterIds: readonly string[],
): Promise<Readonly<{ group: GroupSummary; created: boolean }>> {
  const groups = await client.listGroups(tenantId, accessToken);
  const existing = groups.find((group) => group.name === name);
  if (existing) {
    return { group: existing, created: false };
  }

  const group = await client.createGroup(tenantId, name, initialMemberCharacterIds, accessToken);
  return { group, created: true };
}
