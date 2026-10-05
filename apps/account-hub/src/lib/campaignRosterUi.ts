// Campaign roster view - RFC 0017 (a). Who's playing (with their characters)
// and who's GMing this specific campaign, resolved to real display names from
// the tenant's own roster fetch. For whoever can manage the campaign it also
// carries "Remove" on each player and "Unlink" on each of their characters
// (ADR 0170).

import { removePlayerConfirmation } from './adminCopy';
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import { displayNameFor } from './format';
import { playerIdForUser } from './roster';
import { renderUnlinkCharacter } from './rosterLinkUi';
import { removePlayer, updatePlayer } from './tenants';
import type {
  CampaignSummaryOut,
  PlayerRosterEntryOut,
  PlayerSummaryOut,
  RosterEntry,
  TenantSummaryOut,
} from './types';

// Given for a caller who passes can_manage_campaign: a library administrator or
// the campaign's own GM. `players` is GET .../players, the only place a
// player's own id is given.
export interface RosterManagement {
  tenant: TenantSummaryOut;
  players: PlayerSummaryOut[];
  onChanged: () => void;
}

function renderPlayerControls(
  campaign: CampaignSummaryOut,
  entry: PlayerRosterEntryOut,
  playerId: string,
  management: RosterManagement,
): HTMLElement {
  const controls = document.createElement('span');
  const name = displayNameFor(entry);
  const removeButton = document.createElement('button');
  removeButton.type = 'button';
  removeButton.textContent = 'Remove';
  const status = createStatusSpan();
  removeButton.addEventListener('click', async () => {
    if (!window.confirm(removePlayerConfirmation(name, campaign.name))) return;
    removeButton.disabled = true;
    status.textContent = 'Removing…';
    try {
      await removePlayer(management.tenant.id, campaign.id, playerId);
      management.onChanged();
    } catch (e) {
      removeButton.disabled = false;
      showError(status, e);
    }
  });
  // ADR 0188: this player's say on making their own items, over the campaign's.
  const selfService = document.createElement('select');
  selfService.setAttribute('aria-label', `Making their own items: ${name}`);
  for (const [value, label] of [
    ['', 'Follows the campaign'],
    ['true', 'Can make their own items'],
    ['false', "Can't make their own items"],
  ]) {
    selfService.append(new Option(label, value));
  }
  const current = management.players.find((p) => p.id === playerId)?.self_service ?? null;
  let shown = current === null ? '' : String(current);
  selfService.value = shown;
  selfService.addEventListener('change', async () => {
    selfService.disabled = true;
    status.textContent = 'Saving…';
    try {
      await updatePlayer(
        management.tenant.id,
        campaign.id,
        playerId,
        selfService.value === '' ? null : selfService.value === 'true',
      );
      shown = selfService.value;
      status.textContent = 'Saved.';
    } catch (e) {
      selfService.value = shown;
      showError(status, e);
    } finally {
      selfService.disabled = false;
    }
  });
  controls.append(selfService, removeButton, status);
  return controls;
}

function renderPlayerCharacters(
  campaign: CampaignSummaryOut,
  entry: PlayerRosterEntryOut,
  playerId: string | null,
  management: RosterManagement | undefined,
): HTMLElement {
  const characters = document.createElement('span');
  characters.className = 'campaign-meta';
  if (!management || playerId === null) {
    characters.textContent = entry.characters.map((c) => c.name).join(', ');
    return characters;
  }
  entry.characters.forEach((character, index) => {
    const label = document.createElement('span');
    label.textContent = index === 0 ? character.name : `, ${character.name}`;
    characters.append(
      label,
      ' ',
      renderUnlinkCharacter(
        {
          tenantId: management.tenant.id,
          characterId: character.entity_id,
          characterName: character.name,
          playerId,
          campaignName: campaign.name,
          playerName: displayNameFor(entry),
        },
        management.onChanged,
      ),
    );
  });
  return characters;
}

export function renderCampaignRoster(
  campaign: CampaignSummaryOut,
  roster: RosterEntry[],
  management?: RosterManagement,
): HTMLElement {
  const section = document.createElement('div');
  section.className = 'panel';
  const heading = document.createElement('p');
  heading.textContent = 'Roster:';
  section.append(heading);

  const entries = roster.filter(
    (r) => (r.kind === 'player' || r.kind === 'gm') && r.campaign_id === campaign.id,
  );

  if (entries.length === 0) {
    const none = document.createElement('p');
    none.className = 'status-text';
    none.textContent = 'No one here yet.';
    section.append(none);
    return section;
  }

  const list = document.createElement('ul');
  list.className = 'list';
  for (const entry of entries) {
    const item = document.createElement('li');
    const nameEl = document.createElement('span');
    nameEl.textContent = displayNameFor(entry);
    item.append(nameEl);

    const roleBadge = document.createElement('span');
    roleBadge.className = 'badge';
    roleBadge.textContent = entry.kind;
    item.append(roleBadge);

    if (entry.kind === 'player') {
      const playerId = management ? playerIdForUser(management.players, entry.user_id) : null;
      if (management && playerId !== null) {
        item.append(renderPlayerControls(campaign, entry, playerId, management));
      }
      if (entry.characters.length > 0) {
        item.append(renderPlayerCharacters(campaign, entry, playerId, management));
      }
    }

    list.append(item);
  }
  section.append(list);

  return section;
}
