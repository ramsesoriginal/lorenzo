// Campaign roster view - RFC 0017 (a). Read-only: who's playing (with
// their characters) and who's GMing this specific campaign, resolved to
// real display names from the tenant's own roster fetch.

import { displayNameFor } from './format';
import type { CampaignSummaryOut, RosterEntry } from './types';

export function renderCampaignRoster(
  campaign: CampaignSummaryOut,
  roster: RosterEntry[],
): HTMLElement {
  const section = document.createElement('div');
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
  list.className = 'roster-list';
  for (const entry of entries) {
    const item = document.createElement('li');
    const nameEl = document.createElement('span');
    nameEl.textContent = displayNameFor(entry);
    item.append(nameEl);

    const roleBadge = document.createElement('span');
    roleBadge.className = 'tenant-role';
    roleBadge.textContent = entry.kind;
    item.append(roleBadge);

    if (entry.kind === 'player' && entry.characters.length > 0) {
      const characters = document.createElement('span');
      characters.className = 'campaign-meta';
      characters.textContent = entry.characters.map((c) => c.name).join(', ');
      item.append(characters);
    }

    list.append(item);
  }
  section.append(list);

  return section;
}
