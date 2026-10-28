import type { EntryCard } from './types';

/** What the card calls each kind of entry, by what the person sees it as. */
const KIND_LABELS: Record<string, string> = {
  character: 'Character',
  being: 'Being',
  item_instance: 'Inventory item',
  item: 'Item',
  location: 'Location',
  map: 'Map',
};

/** The kinds in the order the registry of the API prefers them (ADR 0264, 0350). */
const KIND_ORDER = ['character', 'being', 'item_instance', 'item', 'location', 'map'];

/** The one word under a card's name: its most specific kind, or "Entry" for any other. */
export function kindLabel(kinds: readonly string[]): string {
  for (const kind of KIND_ORDER) {
    if (kinds.includes(kind)) return KIND_LABELS[kind] ?? 'Entry';
  }
  return 'Entry';
}

/** A stat on a card as the person reads it: "weight 3". */
export function statText(stat: EntryCard['stats'][number]): string {
  return `${stat.name.replace(/_/g, ' ')} ${stat.value}`;
}
