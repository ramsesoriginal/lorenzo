// Unsorted items from the board (ADR 0238): what a player adds when the catalog does not know it.
// The placeholder is the library's `unsorted` item (ADR 0192); the notes are written exactly as
// `lorenzo inventory import` writes them (ADR 0193), so a GM reads the same thing from either.
import { addKnower, createInformation } from './information';
import { createItemInstance } from './items';
import { resolveSlugs } from './slugs';
import type { ItemInstance } from './types';

export const UNSORTED_SLUG = 'unsorted';

/** The library's `unsorted` item, or null if it has none (nobody ran `lorenzo seed --layer core`). */
export async function findUnsortedItem(tenantId: string): Promise<string | null> {
  const [found] = await resolveSlugs(tenantId, [UNSORTED_SLUG]);

  return found?.kinds.includes('item') ? found.entity_id : null;
}

/** Whether `item` is a placeholder: its prototypes include the library's `unsorted` item. */
export function isUnsorted(item: Pick<ItemInstance, 'prototype_ids'>, unsortedId: string | null) {
  return unsortedId !== null && item.prototype_ids.includes(unsortedId);
}

/** What the form holds, as typed. */
export type UnsortedDraft = Readonly<{
  name: string;
  description: string;
  weight: string;
  value: string;
}>;

/** What the form means, once read. */
export type UnsortedItem = Readonly<{
  name: string;
  description: string | null;
  // Pounds, for one.
  weight: number | null;
  value: string | null;
}>;

// A number of pounds, as the CLI reads one: `0.5`, `0,5`, `2 lb`.
const POUNDS = /^(\d+(?:[.,]\d+)?)\s*(?:lbs?\.?|pounds?)?$/i;

export type ReadDraft = { ok: true; item: UnsortedItem } | { ok: false; problem: string };

export function readDraft(draft: UnsortedDraft): ReadDraft {
  const name = draft.name.trim();

  if (!name) return { ok: false, problem: 'Give it a name.' };

  let weight: number | null = null;
  const typed = draft.weight.trim();

  if (typed) {
    const match = POUNDS.exec(typed);

    if (!match?.[1]) return { ok: false, problem: 'Weight is a number of pounds, such as 0.5.' };

    weight = Number(match[1].replace(',', '.'));
  }

  return {
    ok: true,
    item: {
      name,
      description: draft.description.trim() || null,
      weight,
      value: draft.value.trim() || null,
    },
  };
}

/** The "Details" note: a line for each of the weight and the value, as the CLI writes them. */
export function detailsNote(item: Pick<UnsortedItem, 'weight' | 'value'>): string | null {
  const rows: string[] = [];

  if (item.weight !== null) rows.push(`Weight: ${item.weight} lb`);
  if (item.value !== null) rows.push(`Value: ${item.value}`);

  return rows.length > 0 ? rows.join('\n') : null;
}

export type AddedUnsorted = {
  instance: ItemInstance;
  // The notes that could not be saved, once the item was made (it stays).
  notesNotSaved: string[];
};

/**
 * Makes the placeholder in the player's own name, owned and not carried, then its notes: private,
 * and told to the owner's character, which is how the player reads what they wrote (ADR 0192).
 */
export async function addUnsortedItem(
  tenantId: string,
  unsortedId: string,
  ownerId: string,
  item: UnsortedItem,
): Promise<AddedUnsorted> {
  const instance = await createItemInstance(tenantId, unsortedId, ownerId, undefined, item.name);
  const notesNotSaved: string[] = [];

  for (const [title, content] of [
    ['Note', item.description],
    ['Details', detailsNote(item)],
  ] as const) {
    if (!content) continue;

    try {
      const note = await createInformation(tenantId, instance.entity_id, {
        title,
        type: 'note',
        isPublic: false,
        content,
      });

      await addKnower(tenantId, note.id, ownerId);
    } catch {
      notesNotSaved.push(title);
    }
  }

  return { instance, notesNotSaved };
}
