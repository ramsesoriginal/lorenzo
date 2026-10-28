import type { EntryCard } from './types';

/**
 * Cards by entry, asked for once per page. A missing or hidden entry is remembered as null (it
 * stays missing for the page); any other failure is forgotten so the next hover asks again.
 * `isMissing` says which failure is the first kind: the package knows nothing of an API client.
 */
export function createCardCache(
  fetchCard: (tenant: string, id: string) => Promise<EntryCard>,
  isMissing: (error: unknown) => boolean = () => false,
): (tenant: string, id: string) => Promise<EntryCard | null> {
  const cards = new Map<string, Promise<EntryCard | null>>();

  return (tenant, id) => {
    const key = `${tenant}/${id}`;
    const known = cards.get(key);

    if (known) return known;

    const loading = fetchCard(tenant, id).catch((error: unknown) => {
      if (isMissing(error)) return null;

      cards.delete(key);

      return null;
    });

    cards.set(key, loading);

    return loading;
  };
}
