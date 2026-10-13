// Who is signed in and which repository is open. Everything that needs a network or the Authgear
// SDK is loaded only when sign-in is configured, so the bare page still works without it.

import { authoredRepositories, repositoryToOpen, type TenantSummary } from '../lib/repositories';

export type Session =
  | { kind: 'unconfigured' }
  | { kind: 'signed-out' }
  | { kind: 'error'; message: string }
  | {
      kind: 'signed-in';
      userId: string;
      name: string;
      repositories: TenantSummary[];
      current: TenantSummary | null;
      /** The open repository is published, so libraries that copied it see its edits. */
      published: boolean;
    };

const REPO_KEY = 'bench:repo:';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export async function loadSession(): Promise<Session> {
  const auth = await import('../lib/auth');
  if (!auth.isAuthConfigured()) return { kind: 'unconfigured' };
  try {
    if (!(await auth.isAuthenticated())) return { kind: 'signed-out' };
    const { client, fetchAllPages, unwrap, MAX_PAGE_SIZE } = await import('../lib/api');
    const me = await unwrap(await client.GET('/me'));
    const tenants = await fetchAllPages(
      async (page) =>
        await unwrap(
          await client.GET('/tenants', {
            params: { query: { kind: 'repository', page, size: MAX_PAGE_SIZE } },
          }),
        ),
    );
    const repositories = authoredRepositories(tenants);
    const current = repositoryToOpen(repositories, read(REPO_KEY + me.id));
    return {
      kind: 'signed-in',
      userId: me.id,
      name: me.display_name ?? me.nickname ?? me.email ?? 'You',
      repositories,
      current,
      published: current ? await isPublished(current.id) : false,
    };
  } catch (e) {
    return { kind: 'error', message: e instanceof Error ? e.message : 'Could not sign in.' };
  }
}

/**
 * Whether a repository is published. A failed read says no: the banner is a notice, and a
 * missing one must not stop the editor from opening.
 */
async function isPublished(tenantId: string): Promise<boolean> {
  try {
    const { client, unwrap } = await import('../lib/api');
    const tenant = await unwrap(
      await client.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenantId } } }),
    );
    return tenant.published_at !== null;
  } catch {
    return false;
  }
}

export function chooseRepository(userId: string, id: string) {
  try {
    localStorage.setItem(REPO_KEY + userId, id);
  } catch {
    /* not remembered */
  }
}

/** What the device keeps about the person who is leaving: the next sign-in starts empty. */
export function forgetPerson() {
  try {
    for (const k of Object.keys(localStorage))
      if (k.startsWith(REPO_KEY)) localStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}

export async function signIn() {
  await (await import('../lib/auth')).login();
}

export async function signOut() {
  forgetPerson();
  await (await import('../lib/auth')).logout();
}
