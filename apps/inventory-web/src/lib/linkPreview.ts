// What a link to an entity shows when pointed at (ADR 0264): which links open a card, and for which
// entity. The card itself, its timing and its words are packages/entry-preview's (ADR 0349).

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
