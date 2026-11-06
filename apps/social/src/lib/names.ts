import { client, fetchAllPages, unwrap } from './api';

// The words a page uses for where it is: the library. They only label the page, so a name that
// cannot be read is left out, not an error.
const libraries = new Map<string, Promise<string | null>>();

export function libraryName(tenant: string) {
  let name = libraries.get(tenant);
  if (!name) {
    name = client
      .GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant } } })
      .then((result) => (result.response.ok && result.data ? result.data.name : null))
      .catch(() => null);
    libraries.set(tenant, name);
  }
  return name;
}

/** Every library the person can open, with their role in it. */
export async function myLibraries() {
  return fetchAllPages(async (page) =>
    unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
  );
}

let standing: Promise<Set<string>> | undefined;

/**
 * Whether the person may write Locations in a library: an Owner, Organizer or Author, or a GM of
 * one of its campaigns. It only decides what is offered; the API decides the write.
 */
export async function canManage(tenant: string) {
  standing ??= (async () => {
    const found = new Set<string>();
    try {
      for (const library of await myLibraries()) {
        if (['owner', 'orga', 'author'].includes(library.role)) found.add(library.id);
      }
      const managed = await unwrap(await client.GET('/me/managed'));
      for (const library of managed.tenants) {
        if (library.campaigns.some((campaign) => campaign.is_gm)) found.add(library.tenant_id);
      }
    } catch {
      // Without a role nothing to write is offered.
    }
    return found;
  })();
  return (await standing).has(tenant);
}

// A name and a role are read for one person; the next one to sign in reads their own.
if (typeof window !== 'undefined') {
  window.addEventListener('lorenzo:sign-out', () => {
    libraries.clear();
    standing = undefined;
  });
}
