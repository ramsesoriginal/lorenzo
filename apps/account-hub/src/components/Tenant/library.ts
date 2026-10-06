// What someone can see and do in one library (ADR 0178's "library", a tenant of kind `play`):
// edit it, its campaigns with their people, GMs, invite links and pictures, a campaign to make,
// its administrators, the activity log, a notification to send, and leaving it.
//
// Loading and filling are apart: everything is asked for first, and only then put in the slots of
// <Tenant />, so a library that is no longer the open one never touches the page. Each piece is a
// component, cloned from its <template> and bound by its own renderer.

import { knownNames } from '../../lib/activityNames';
import { type CampaignRole, campaignRoleFor, isTenantAdmin } from '../../lib/format';
import { type LibraryReads, readLibrary } from '../../lib/libraryData';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import { rosterFromPlayers } from '../../lib/roster';
import { bindTabs } from '../../lib/tabs';
import { requiredIn } from '../../lib/template';
import {
  campaignPictureUrl,
  createCampaignNotification,
  createTenantNotification,
  deleteCampaignPicture,
  deleteTenantPicture,
  tenantPictureUrl,
  uploadCampaignPicture,
  uploadTenantPicture,
} from '../../lib/tenants';
import type {
  CampaignSummaryOut,
  MembershipRosterEntryOut,
  MeOut,
  TenantSummaryOut,
} from '../../lib/types';
import { renderActivityLog } from '../ActivityLog/renderer';
import { renderCampaignEdit } from '../CampaignEdit/renderer';
import { renderCampaignForm } from '../CampaignForm/renderer';
import { renderCampaignRoster } from '../CampaignRoster/renderer';
import { renderGmManagement } from '../GmManagement/renderer';
import { renderInviteLinks } from '../InviteLinks/renderer';
import { renderInvitePlayer } from '../InvitePlayer/renderer';
import { renderMembershipAdmin } from '../MembershipAdmin/renderer';
import { renderNotificationComposer } from '../NotificationComposer/renderer';
import { renderPictureUpload } from '../PictureUpload/renderer';
import type { TenantHooks } from './hooks';
import { cloneComponent, fillSlot } from './slots';
import { bindStepDownAsGm } from './stepDownAsGm';

const required = requiredIn('Tenant');

export type LibraryData = LibraryReads & {
  // Bound to what it fetched but not in the page yet, for administrators.
  activity: HTMLElement | null;
};

function roleLabel(role: CampaignRole): string {
  switch (role) {
    case 'gm':
      return 'GM';
    case 'player':
      return 'Player';
    case 'visible':
      return 'Visible';
  }
}

export async function loadLibrary(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  me: MeOut,
): Promise<LibraryData> {
  const reads = await readLibrary(tenant, me);
  let activity: HTMLElement | null = null;

  if (isTenantAdmin(tenant)) {
    activity = cloneComponent(root, '[data-activity-log-template]');
    await renderActivityLog(
      activity,
      tenant,
      knownNames({
        tenant,
        campaigns: reads.campaigns,
        roster: reads.roster,
        players: [...reads.playersByCampaign.values()].flat(),
      }),
    );
  }

  return { ...reads, activity };
}

// One campaign of the library, from <Tenant />'s template, with the controls its caller may use.
function renderCampaign(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  me: MeOut,
  data: LibraryData,
  onChanged: () => void,
): HTMLElement {
  const item = cloneComponent(root, '[data-campaign-template]');
  const role = campaignRoleFor(campaign.id, me);

  required<HTMLElement>(item, '[data-campaign-name]').textContent = campaign.name;
  showLorenzoScript(
    required<HTMLElement>(item, '[data-campaign-description]'),
    data.descriptions.get(campaign.id) ?? '',
  );
  required<HTMLElement>(item, '[data-campaign-meta]').textContent =
    `${campaign.game_system} · ${roleLabel(role)}${campaign.secret ? ' · secret' : ''}`;

  const admin = isTenantAdmin(tenant);
  // can_manage_campaign's real two-way gate: a tenant admin, or this
  // specific campaign's own GM (RFC 0014) - not just one branch of it.
  const canManage = admin || role === 'gm';
  // RFC 0017 (a)'s own "any tenant-wide member" is, by construction,
  // exactly admin (owner/orga) - MembershipRole has no plain-member
  // role, so get_tenant_context's gate on the underlying roster fetch
  // already excludes anyone else. roster is null (not fetched at all)
  // for a non-admin tenant - a participant-only caller (Player/
  // CampaignGm standing, no Membership row) got an uncaught 404 here
  // before this fix, breaking this whole page for them. A GM with no
  // Membership still manages the campaign (ADR 0170), and gets its
  // players from GET .../players instead, by user id: no names there.
  const players = canManage ? (data.playersByCampaign.get(campaign.id) ?? []) : null;
  const shownRoster = data.roster ?? (players ? rosterFromPlayers(campaign.id, players) : null);

  if (shownRoster) {
    const roster = cloneComponent(root, '[data-campaign-roster-template]');

    renderCampaignRoster(
      roster,
      campaign,
      shownRoster,
      players ? { tenant, players, onChanged } : undefined,
    );
    fillSlot(item, '[data-campaign-roster-slot]', roster);
  }

  if (admin) {
    const edit = cloneComponent(root, '[data-campaign-edit-template]');
    const gms = cloneComponent(root, '[data-gm-management-template]');

    renderCampaignEdit(edit, tenant, campaign, onChanged);
    renderGmManagement(
      gms,
      tenant,
      campaign,
      data.gmsByCampaign.get(campaign.id) ?? [],
      data.roster ?? [],
      onChanged,
    );
    fillSlot(item, '[data-campaign-edit-slot]', edit);
    fillSlot(item, '[data-campaign-gms-slot]', gms);
  }

  // The same gate as the roster's controls above; matches
  // upload_campaign_picture's own gate too (ADR 0085).
  if (canManage) {
    const picture = cloneComponent(root, '[data-picture-upload-template]');
    const invitePlayer = cloneComponent(root, '[data-invite-player-template]');
    const inviteLinks = cloneComponent(root, '[data-invite-links-template]');
    const notify = cloneComponent(root, '[data-notification-composer-template]');

    renderPictureUpload(picture, {
      url: campaignPictureUrl(tenant.id, campaign.id),
      onUpload: (file) => uploadCampaignPicture(tenant.id, campaign.id, file),
      onDelete: () => deleteCampaignPicture(tenant.id, campaign.id),
    });
    renderInvitePlayer(invitePlayer, tenant, campaign);
    renderInviteLinks(inviteLinks, tenant, campaign);
    renderNotificationComposer(notify, (body) =>
      createCampaignNotification(tenant.id, campaign.id, body),
    );
    fillSlot(item, '[data-campaign-picture-slot]', picture);
    fillSlot(item, '[data-campaign-invite-player-slot]', invitePlayer);
    fillSlot(item, '[data-campaign-invite-links-slot]', inviteLinks);
    fillSlot(item, '[data-campaign-notify-slot]', notify);
  }

  // Wherever the caller is a GM, administrator or not (ADR 0170): the
  // API lets anyone revoke their own grant.
  if (role === 'gm') {
    const stepDown = required<HTMLElement>(item, '[data-campaign-step-down]');

    stepDown.hidden = false;
    bindStepDownAsGm(stepDown, tenant, campaign, me.id, onChanged);
  }

  // Everything the tabs hold is for those who manage the campaign.
  if (canManage) {
    const tabs = required<HTMLElement>(item, '[data-campaign-tabs]');

    tabs.hidden = false;
    bindTabs(tabs);
  }

  return item;
}

// Puts the library's pieces in <Tenant />'s slots, each only for those who may use it.
export function fillLibrary(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  me: MeOut,
  hooks: TenantHooks,
  data: LibraryData,
): void {
  const { onChanged } = hooks;
  const admin = isTenantAdmin(tenant);

  // Same gate upload_tenant_picture itself enforces (ADR 0056/0085) -
  // ORGA+, day-to-day tenant administration.
  if (admin) {
    const picture = cloneComponent(root, '[data-picture-upload-template]');

    renderPictureUpload(picture, {
      url: tenantPictureUrl(tenant.id),
      onUpload: (file) => uploadTenantPicture(tenant.id, file),
      onDelete: () => deleteTenantPicture(tenant.id),
    });
    fillSlot(root, '[data-picture-slot]', picture);
  }

  required<HTMLElement>(root, '[data-campaigns]').hidden = false;
  required<HTMLElement>(root, '[data-no-campaigns]').hidden = data.campaigns.length > 0;
  required<HTMLElement>(root, '[data-campaign-list]').replaceChildren(
    ...data.campaigns.map((campaign) =>
      renderCampaign(root, tenant, campaign, me, data, onChanged),
    ),
  );

  if (admin) {
    const create = cloneComponent(root, '[data-create-campaign-template]');

    renderCampaignForm(create, { mode: 'create', tenant, onDone: onChanged });
    fillSlot(root, '[data-create-campaign-slot]', create);
  }

  // RFC 0017 (e) - bulk invite is confirmed _require_owner-gated; the
  // single-item actions here are gated identically for consistency
  // rather than assumed looser (showing nothing to an orga who might
  // technically have single-item rights is the safe direction of a
  // wrong guess). tenant.role === 'owner' implies admin, so roster is
  // never null here.
  if (tenant.role === 'owner' && data.roster) {
    const memberships = cloneComponent(root, '[data-membership-admin-template]');

    renderMembershipAdmin(
      memberships,
      tenant,
      data.roster.filter((r): r is MembershipRosterEntryOut => r.kind === 'membership'),
      onChanged,
    );
    fillSlot(root, '[data-memberships-slot]', memberships);
  }

  // RFC 0017 (f)/(g) - gated the same as list_tenant_roster/
  // update_tenant themselves: get_tenant_context, which is admin-only
  // by construction (see the roster fetch in loadLibrary) - not owner-only, but
  // not "any participant" either.
  fillSlot(root, '[data-activity-slot]', data.activity);

  if (admin) {
    const notify = cloneComponent(root, '[data-notification-composer-template]');

    renderNotificationComposer(notify, (body) => createTenantNotification(tenant.id, body));
    fillSlot(root, '[data-notifications-slot]', notify);
  }
}
