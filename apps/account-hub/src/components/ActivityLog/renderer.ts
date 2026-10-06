// Tenant activity log - RFC 0017 (f). actor_id/target_id are raw ids, and `detail` holds more of
// them, with no guarantee of a name: an actor may no longer be in the roster, a target may have
// been deleted. So an id is shown as its slug or its person's name, in an <abbr> that keeps the id
// as its title, wherever one is known, and as the id itself where none is.

import { type Segment, entityIdsIn, segments } from '../../lib/activityNames';
import { getEntityLabel } from '../../lib/entities';
import { formatTimestamp } from '../../lib/relativeTime';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { listActivityLog } from '../../lib/tenants';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Activity log');

// An item, a character or a group has a name only by asking for it, so those are asked for a few at
// a time after the log is shown, and not for more than this many.
const LOOKUPS_AT_ONCE = 4;
const MAX_LOOKUPS = 25;

// `root` is the <ActivityLog /> block. `names` are the ids the page already has a name for
// (knownNames). A failed fetch of the log rejects, for the caller to show.
export async function renderActivityLog(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  names: ReadonlyMap<string, string>,
): Promise<void> {
  const empty = required<HTMLElement>(root, '[data-empty]');
  const list = required<HTMLElement>(root, '[data-entries]');
  const entries = await listActivityLog(tenant.id);

  const known = new Map(names);
  // The entities in the log nobody has named yet. Until its answer comes, such an id is shown
  // as itself, in the <abbr> that its name will go into.
  const wanted = [...new Set(entries.items.flatMap(entityIdsIn))]
    .filter((id) => !known.has(id))
    .slice(0, MAX_LOOKUPS);
  const pending = new Set(wanted);

  function show(segment: Segment): Node {
    if (typeof segment === 'string') return document.createTextNode(segment);

    const abbr = rootElement(fromTemplate(root, '[data-abbr-template]'));

    abbr.textContent = segment.label;
    abbr.title = segment.id;
    abbr.dataset.ref = segment.id;

    return abbr;
  }

  empty.hidden = entries.items.length > 0;
  list.hidden = entries.items.length === 0;
  list.replaceChildren();

  for (const entry of entries.items) {
    const item = fromTemplate(root, '[data-entry-template]');
    const parts = [
      `by ${entry.actor_id ?? 'unknown'}`,
      entry.target_id ? `on ${entry.target_id}` : null,
      entry.detail,
      formatTimestamp(entry.created_at),
    ].filter((part): part is string => Boolean(part));

    required<HTMLElement>(item, '[data-summary]').textContent =
      `${entry.action} · ${entry.target_type}`;
    required<HTMLElement>(item, '[data-meta]').replaceChildren(
      ...segments(parts.join(' · '), (id) => known.get(id) ?? (pending.has(id) ? id : undefined)).map(
        show,
      ),
    );
    list.append(item);
  }

  // Each name goes into every place its id is shown. One that can't be read (a deleted item) stays
  // as its id.
  const queue = [...wanted];

  async function lookUp(): Promise<void> {
    for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
      const label = await getEntityLabel(tenant.id, id);

      if (label === null) continue;

      known.set(id, label);

      for (const abbr of root.querySelectorAll<HTMLElement>(`abbr[data-ref="${id}"]`)) {
        abbr.textContent = label;
      }
    }
  }

  // Not waited for: the log is there already, and gets its names as they arrive.
  void Promise.all(Array.from({ length: Math.min(LOOKUPS_AT_ONCE, queue.length) }, lookUp));
}
