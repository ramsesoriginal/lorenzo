// What opening a library asks the API for, apart from what is then drawn: shared by <Tenant /> and by
// the hover prefetch (lib/prefetch.ts), so warming a library asks for exactly what opening it does.
import { campaignRoleFor, isTenantAdmin } from './format';
import {
  getCampaign,
  getTenant,
  listActivityLog,
  listCampaignGms,
  listCampaignPlayers,
  listTenantCampaigns,
  listTenantRoster,
} from './tenants';
import type {
  CampaignSummaryOut,
  MeOut,
  PlayerSummaryOut,
  RosterEntry,
  TenantSummaryOut,
} from './types';

export type LibraryReads = {
  // LorenzoScript, as written; empty when there is none.
  description: string;
  // Each campaign's description, LorenzoScript as written, by campaign id.
  descriptions: Map<string, string>;
  campaigns: CampaignSummaryOut[];
  // Null where the caller isn't an administrator: it isn't fetched at all.
  roster: RosterEntry[] | null;
  gmsByCampaign: Map<string, string[]>;
  playersByCampaign: Map<string, PlayerSummaryOut[]>;
};

export async function readLibrary(tenant: TenantSummaryOut, me: MeOut): Promise<LibraryReads> {
  const admin = isTenantAdmin(tenant);
  // get_tenant_context (the real gate behind list_tenant_roster/
  // list_activity_log/create_tenant_notification_route) requires an
  // actual Membership row, which by construction means admin
  // (owner/orga) - MembershipRole has no plain-member role. Fetching
  // this for every tenant listMyTenants() returns, including
  // participant-only ones (Player/CampaignGm standing, no Membership),
  // 404'd uncaught and broke this whole page for that caller.
  const [campaignPage, rosterPage, detail] = await Promise.all([
    listTenantCampaigns(tenant.id),
    admin ? listTenantRoster(tenant.id) : null,
    // The summary has no description; the detail read does.
    getTenant(tenant.id),
    // The activity log is drawn from its own read; asking now holds it for then, alongside the rest.
    admin ? listActivityLog(tenant.id).catch(() => undefined) : null,
  ]);
  const campaigns = campaignPage.items;
  // The players of every campaign the caller manages: where a player's
  // own id comes from (ADR 0170).
  const managed = campaigns.filter((c) => admin || campaignRoleFor(c.id, me) === 'gm');

  // Everything that needs the campaigns, at once: one round after the first, not three.
  const [gmLists, playerPages, details] = await Promise.all([
    admin ? Promise.all(campaigns.map((c) => listCampaignGms(tenant.id, c.id))) : [],
    Promise.all(managed.map((c) => listCampaignPlayers(tenant.id, c.id))),
    // The list has no descriptions; each campaign's own read does.
    Promise.all(campaigns.map((c) => getCampaign(tenant.id, c.id))),
  ]);

  return {
    description: detail.tenant.description,
    descriptions: new Map(details.map((c) => [c.id, c.description])),
    campaigns,
    roster: rosterPage?.items ?? null,
    gmsByCampaign: new Map(
      campaigns.map((c, i) => [c.id, (gmLists[i] ?? []).map((g) => g.user_id)]),
    ),
    playersByCampaign: new Map(managed.map((c, i) => [c.id, playerPages[i]?.items ?? []])),
  };
}
