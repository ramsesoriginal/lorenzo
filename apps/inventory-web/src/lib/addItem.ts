// Adding an item from the board: whether to offer it, and what to offer (ADR 0187).
import type { Suggestion } from '../components/Combobox/renderer';
import { findCatalogItems } from './items';
import type { CatalogItem } from './types';

// 'allowed' shows the form; 'off' says the GM has switched making your own items off; 'hidden'
// shows nothing at all.
export type AddItemStanding = 'allowed' | 'off' | 'hidden';

// The part of one of the viewer's seats that matters here (MePlayerOut).
export type Seat = Readonly<{
  characters: readonly Readonly<{ entity_id: string }>[];
  self_service_effective: boolean;
}>;

export type AddItemViewer = Readonly<{
  viewerIsGm: boolean;
  // The being whose board this is, or null for a group's and the unowned board.
  holderId: string | null;
  // The viewer's own seats in this library.
  seats: readonly Seat[];
}>;

// A convenience to decide what to show, never authorization: the API judges the write, and what it
// says is shown as it says it.
export function addItemStanding({ viewerIsGm, holderId, seats }: AddItemViewer): AddItemStanding {
  if (holderId === null) return 'hidden';
  // A GM is a manager, whose standing the API reads from the being's campaigns, not from a switch.
  if (viewerIsGm) return 'allowed';

  const mine = seats.filter((seat) => seat.characters.some((c) => c.entity_id === holderId));

  if (mine.length === 0) return 'hidden';

  // One seat that's on is enough for the character, wherever else it's off (ADR 0186).
  return mine.some((seat) => seat.self_service_effective) ? 'allowed' : 'off';
}

// How many suggestions to offer: a short list, then search.
const SUGGESTIONS = 8;

/** Catalog items matching `query`, or the first few with none, as a combobox offers them. */
export async function searchAddableItems(
  tenantId: string,
  query: string,
): Promise<Suggestion<CatalogItem>[]> {
  const found = await findCatalogItems(tenantId, query, SUGGESTIONS);

  return found.map((item) => ({ label: item.title, value: item }));
}
