// Campaign roster view - RFC 0017 (a). Who's playing (with their characters)
// and who's GMing this specific campaign, resolved to real display names from
// the tenant's own roster fetch. For whoever can manage the campaign it also
// carries "Remove" on each player and "Unlink" on each of their characters
// (ADR 0170).

import { removePlayerConfirmation } from '../../lib/adminCopy';
import { displayNameFor } from '../../lib/format';
import { playerIdForUser } from '../../lib/roster';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { removePlayer, updatePlayer } from '../../lib/tenants';
import type {
  CampaignSummaryOut,
  PlayerRosterEntryOut,
  PlayerSummaryOut,
  RosterEntry,
  TenantSummaryOut,
} from '../../lib/types';
import { bindUnlinkCharacter } from './unlinkCharacter';

const required = requiredIn('Campaign roster');

// Given for a caller who passes can_manage_campaign: a library administrator or
// the campaign's own GM. `players` is GET .../players, the only place a
// player's own id is given.
export interface RosterManagement {
  tenant: TenantSummaryOut;
  players: PlayerSummaryOut[];
  onChanged: () => void;
}

function bindPlayerControls(
  row: ParentNode,
  campaign: CampaignSummaryOut,
  entry: PlayerRosterEntryOut,
  playerId: string,
  management: RosterManagement,
): void {
  const name = displayNameFor(entry);
  const controls = required<HTMLElement>(row, '[data-controls]');
  const removeButton = required<HTMLButtonElement>(row, '[data-remove]');
  const selfService = required<HTMLSelectElement>(row, '[data-self-service]');
  const status = required<HTMLElement>(row, '[data-status]');

  controls.hidden = false;

  removeButton.addEventListener('click', async () => {
    if (!window.confirm(removePlayerConfirmation(name, campaign.name))) return;

    removeButton.disabled = true;
    say(status, 'Removing…');

    try {
      await removePlayer(management.tenant.id, campaign.id, playerId);
      management.onChanged();
    } catch (e) {
      removeButton.disabled = false;
      sayError(status, e);
    }
  });

  // ADR 0188: this player's say on making their own items, over the campaign's.
  selfService.setAttribute('aria-label', `Making their own items: ${name}`);

  const current = management.players.find((p) => p.id === playerId)?.self_service ?? null;
  let shown = current === null ? '' : String(current);

  selfService.value = shown;
  selfService.addEventListener('change', async () => {
    selfService.disabled = true;
    say(status, 'Saving…');

    try {
      await updatePlayer(
        management.tenant.id,
        campaign.id,
        playerId,
        selfService.value === '' ? null : selfService.value === 'true',
      );
      shown = selfService.value;
      say(status, 'Saved.');
    } catch (e) {
      selfService.value = shown;
      sayError(status, e);
    } finally {
      selfService.disabled = false;
    }
  });
}

function bindPlayerCharacters(
  root: HTMLElement,
  row: ParentNode,
  campaign: CampaignSummaryOut,
  entry: PlayerRosterEntryOut,
  playerId: string | null,
  management: RosterManagement | undefined,
): void {
  const characters = required<HTMLElement>(row, '[data-characters]');
  // The player's own line, which a manager's unlink buttons answer in.
  const status = required<HTMLElement>(row, '[data-status]');

  characters.hidden = false;

  if (!management || playerId === null) {
    characters.textContent = entry.characters.map((c) => c.name).join(', ');

    return;
  }

  entry.characters.forEach((character) => {
    const fragment = fromTemplate(root, '[data-character-template]');

    required<HTMLElement>(fragment, '[data-character-name]').textContent = character.name;
    bindUnlinkCharacter(
      required<HTMLButtonElement>(fragment, '[data-unlink]'),
      status,
      {
        tenantId: management.tenant.id,
        characterId: character.entity_id,
        characterName: character.name,
        playerId,
        campaignName: campaign.name,
        playerName: displayNameFor(entry),
      },
      management.onChanged,
    );
    characters.append(fragment);
  });
}

// `root` is the <CampaignRoster /> panel.
export function renderCampaignRoster(
  root: HTMLElement,
  campaign: CampaignSummaryOut,
  roster: RosterEntry[],
  management?: RosterManagement,
): void {
  const empty = required<HTMLElement>(root, '[data-empty]');
  const list = required<HTMLElement>(root, '[data-list]');

  const entries = roster.filter(
    (r) => (r.kind === 'player' || r.kind === 'gm') && r.campaign_id === campaign.id,
  );

  empty.hidden = entries.length > 0;
  list.hidden = entries.length === 0;
  list.replaceChildren(
    ...entries.map((entry) => {
      const row = fromTemplate(root, '[data-entry-template]');

      required<HTMLElement>(row, '[data-name]').textContent = displayNameFor(entry);
      required<HTMLElement>(row, '[data-role]').textContent = entry.kind;

      if (entry.kind === 'player') {
        const playerId = management ? playerIdForUser(management.players, entry.user_id) : null;

        if (management && playerId !== null) {
          bindPlayerControls(row, campaign, entry, playerId, management);
        }

        if (entry.characters.length > 0) {
          bindPlayerCharacters(root, row, campaign, entry, playerId, management);
        }
      }

      return rootElement(row);
    }),
  );
}
