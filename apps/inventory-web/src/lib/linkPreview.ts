// What a link to an entity shows when pointed at (ADR 0264): the card the API makes for it, kept
// for the page, and the pure pieces of deciding when to show it. components/LinkPreview draws it.
import { client, type components, LorenzoApiError, unwrap } from './api';

export type Card = components['schemas']['LinkPreviewOut'];

/** The library and entity a rendered link leads to, or null when it is not a link to an entity. */
export function previewTarget(href: string | null): { tenant: string; id: string } | null {
  if (!href) return null;
  let url: URL;
  try {
    url = new URL(href, 'http://app.invalid');
  } catch {
    return null;
  }
  if (url.origin !== 'http://app.invalid') return null;
  const tenant = url.searchParams.get('tenant');
  // descriptions.ts links by entity id: an item's page by `id`, a character's board by `character`.
  const id = url.searchParams.get(url.pathname.startsWith('/board') ? 'character' : 'id');
  return tenant && id ? { tenant, id } : null;
}

/** What the card calls each kind of entry, by what the person sees it as (identity 14.3). */
const KIND_LABELS: Record<string, string> = {
  character: 'Character',
  being: 'Being',
  item_instance: 'Inventory item',
  item: 'Item',
};

/** The one word under a card's name: its most specific kind, or "Entry" for a bare one. */
export function kindLabel(kinds: readonly string[]): string {
  for (const kind of ['character', 'being', 'item_instance', 'item']) {
    if (kinds.includes(kind)) return KIND_LABELS[kind] ?? 'Entry';
  }
  return 'Entry';
}

/** A stat on a card as the person reads it: "weight 3". */
export function statText(stat: Card['stats'][number]): string {
  return `${stat.name.replace(/_/g, ' ')} ${stat.value}`;
}

/**
 * Cards by entity, asked for once per page. A missing or hidden entry is remembered as null (it
 * stays missing for the page); any other failure is forgotten so the next hover asks again.
 */
export function createCardCache(
  fetchCard: (tenant: string, id: string) => Promise<Card>,
): (tenant: string, id: string) => Promise<Card | null> {
  const cards = new Map<string, Promise<Card | null>>();
  return (tenant, id) => {
    const key = `${tenant}/${id}`;
    const known = cards.get(key);
    if (known) return known;
    const loading = fetchCard(tenant, id).catch((error: unknown) => {
      if (error instanceof LorenzoApiError && error.status === 404) return null;
      cards.delete(key);
      return null;
    });
    cards.set(key, loading);
    return loading;
  };
}

export const loadCard = createCardCache(async (tenant, id) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/preview', {
      params: { path: { tenant_id: tenant, entity_id: id } },
    }),
  ),
);
