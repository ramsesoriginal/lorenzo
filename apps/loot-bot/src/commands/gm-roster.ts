import type { ControlledCharacter, LorenzoApiClient } from "../lorenzo-client.js";

/**
 * Every character in a campaign the caller GMs, deduplicated - extracted
 * from `/award`'s own original `findAwardTargets` (ADR 0068) once
 * `/inspect`, `/confiscate`, and `/reassign` all needed the identical
 * lookup. `getGmCampaignIds` isn't tenant-scoped (see its own docstring),
 * so a campaign belonging to a different tenant just fails this
 * tenant-scoped roster lookup and is silently skipped, rather than
 * failing the whole autocomplete request.
 */
export async function findGmControlledCharacters(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
): Promise<readonly ControlledCharacter[]> {
  const campaignIds = await client.getGmCampaignIds(accessToken);
  const rosters = await Promise.all(
    campaignIds.map((campaignId) =>
      client.getCampaignPlayers(tenantId, campaignId, accessToken).catch(() => []),
    ),
  );
  const byId = new Map(rosters.flat().map((character) => [character.entityId, character]));
  return [...byId.values()];
}
