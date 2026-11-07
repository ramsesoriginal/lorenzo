// Where an item's description or picture comes from (ADR 0111, ADR 0437). The API says it with
// `from_entity`: null for the item's own, the ancestor otherwise - and, for a text that comes from
// an entry the library hides, `from_entity: null` too, with `from_hidden: true`. A null
// `from_entity` alone therefore no longer means "its own": every reading of it goes through here.

import type { components } from './api';

type EntitySummary = components['schemas']['EntitySummary'];

/** What a description or picture says about where it comes from. */
export type TextOrigin = {
  from_entity?: EntitySummary | null;
  from_hidden?: boolean | null;
};

/** What a hidden entry is called wherever a name would give it away (the brand's wording). */
export const HIDDEN_SOURCE_LABEL = 'From a hidden entry';

/** The item's own text, not inherited from any entry, hidden or not. */
export const isOwnText = (part: TextOrigin): boolean => !part.from_entity && !part.from_hidden;

/** Inherited from an entry the library hides: no name, no id, no link. */
export const isFromHiddenEntry = (part: TextOrigin): boolean =>
  !part.from_entity && part.from_hidden === true;

/** Whether the item has a description of its own, which is what the editor changes. */
export const hasOwnText = (parts: readonly TextOrigin[]): boolean => parts.some(isOwnText);

/**
 * The entry a text belongs to, for what its `my/` links and `{stats}` mean (ADR 0240): the
 * ancestor it comes from, and for the item's own text or one from a hidden entry (whose id is
 * never given) the item itself.
 */
export const textHome = (part: TextOrigin, entityId: string): string =>
  part.from_entity?.id ?? entityId;

/** One place the texts of an item come from, in the order they first appear. */
export type TextSource =
  | { kind: 'own'; id: string }
  | { kind: 'entry'; id: string; source: EntitySummary }
  // Every hidden ancestor, together: they cannot be told apart, and none is named.
  | { kind: 'hidden' };

/**
 * The item's own text first, then each ancestor the texts and pictures name, in the order they
 * come, with the hidden ones as one group.
 */
export function textSources(entityId: string, parts: readonly TextOrigin[]): TextSource[] {
  const found: TextSource[] = [{ kind: 'own', id: entityId }];
  const seen = new Set<string>([entityId]);
  let hidden = false;
  for (const part of parts) {
    if (part.from_entity) {
      if (seen.has(part.from_entity.id)) continue;
      seen.add(part.from_entity.id);
      found.push({ kind: 'entry', id: part.from_entity.id, source: part.from_entity });
    } else if (isFromHiddenEntry(part) && !hidden) {
      hidden = true;
      found.push({ kind: 'hidden' });
    }
  }
  return found;
}
