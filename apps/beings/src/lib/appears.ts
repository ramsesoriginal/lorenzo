// Where an entry appears (BN11): the pieces of information that link to it, which is how the
// Scenes and Sessions that name it, and the other entries that do, are found (ADR 0110). Pure, so
// it is tested without a browser; the read is lib/descriptions.ts's getBacklinks.

import type { components } from './api';

type Backlink = components['schemas']['BacklinkOut'];

/** One entry that links here, with the titles of the pieces of information that do. */
export type Appearance = {
  entityId: string;
  name: string;
  kinds: Backlink['kinds'];
  titles: string[];
};

export type Appearances = {
  sessions: Appearance[];
  scenes: Appearance[];
  others: Appearance[];
};

const SCENE_KINDS = new Set(['scene', 'scene_appearance', 'scene_telling']);

/** The links to an entry, one row per entry that holds them, sorted by name, in three groups. */
export function groupAppearances(links: readonly Backlink[]): Appearances {
  const byEntry = new Map<string, Appearance>();

  for (const link of links) {
    const known = byEntry.get(link.entity_id);
    const title = link.title.trim() || link.type;

    if (known) {
      if (!known.titles.includes(title)) known.titles.push(title);
    } else {
      byEntry.set(link.entity_id, {
        entityId: link.entity_id,
        name: link.name,
        kinds: link.kinds,
        titles: [title],
      });
    }
  }

  const rows = [...byEntry.values()].sort((a, b) => a.name.localeCompare(b.name));
  const result: Appearances = { sessions: [], scenes: [], others: [] };

  for (const row of rows) {
    if (row.kinds.includes('session')) result.sessions.push(row);
    else if (row.kinds.some((kind) => SCENE_KINDS.has(kind))) result.scenes.push(row);
    else result.others.push(row);
  }

  return result;
}
