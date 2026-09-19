// Tenant activity log - RFC 0017 (f). actor_id/target_id are raw UUIDs
// with no guaranteed cross-reference (an actor may no longer be in the
// roster, a target may be a campaign/membership row, not a user) - shown
// as-is, not enriched, rather than guessing at a join that isn't always
// meaningful.

import { listActivityLog } from './tenants';
import type { TenantSummaryOut } from './types';

export async function renderActivityLog(tenant: TenantSummaryOut): Promise<HTMLElement> {
  const section = document.createElement('div');
  section.className = 'panel';
  const heading = document.createElement('h3');
  heading.textContent = 'Activity log';
  section.append(heading);

  const entries = await listActivityLog(tenant.id);
  if (entries.items.length === 0) {
    const none = document.createElement('p');
    none.className = 'status-text';
    none.textContent = 'No activity recorded yet.';
    section.append(none);
    return section;
  }

  const list = document.createElement('ul');
  list.className = 'roster-list';
  for (const entry of entries.items) {
    const item = document.createElement('li');
    const summary = document.createElement('span');
    summary.textContent = `${entry.action} · ${entry.target_type}`;
    const meta = document.createElement('span');
    meta.className = 'campaign-meta';
    const parts = [
      `by ${entry.actor_id ?? 'unknown'}`,
      entry.target_id ? `on ${entry.target_id}` : null,
      entry.detail,
      new Date(entry.created_at).toLocaleString(),
    ].filter((p): p is string => Boolean(p));
    meta.textContent = parts.join(' · ');
    item.append(summary, meta);
    list.append(item);
  }
  section.append(list);
  return section;
}
