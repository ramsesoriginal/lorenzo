// The datasheet's own read (ADR 0281): what a being has equipped, as a table of the library's weapon
// stats, and its abilities, in one request. What the viewer may see of either is the API's call.

import { client, type components, unwrap } from './api';

export type Sheet = components['schemas']['SheetOut'];
export type SheetWeapon = Sheet['weapons'][number];

/** The being's equipped weapons and abilities. `campaignId` is accepted and changes nothing yet. */
export async function getSheet(
  tenantId: string,
  entityId: string,
  campaignId?: string,
): Promise<Sheet> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/beings/{entity_id}/sheet', {
      params: {
        path: { tenant_id: tenantId, entity_id: entityId },
        query: campaignId ? { campaign_id: campaignId } : {},
      },
    }),
  );
}
