// Slugs in inventory-web (ADR 0107, 0113): suggesting one for an item or an
// instance, checking it, saving it, and finding what holds one.
import { slugify } from '@lorenzo/lorenzoscript';
import { client, type components, LorenzoApiError, unwrap } from './api';

export type ResolvedSlug = components['schemas']['ResolvedSlugOut'];

/** ADR 0107's grammar, so every slug can be written in a link: `[text](slug)`. */
const GRAMMAR = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const MAX_LENGTH = 100;
/** How many candidates one resolve request checks (ADR 0113). */
const CANDIDATES = 20;

export type SlugKind = 'item' | 'instance';

/**
 * What a slug for something shown as `title` could be, best first. A catalog item takes the
 * title itself, the slug `[[Title]]` looks for, then `-2`, `-3`; an instance numbers from
 * `-1`, leaving the bare title to its item. None if the title has no letters or digits.
 */
export function slugCandidates(title: string, kind: SlugKind): string[] {
  const base = slugify(title);
  if (!base) return [];
  return Array.from({ length: CANDIDATES }, (_, i) => {
    const suffix = kind === 'item' && i === 0 ? '' : `-${i + 1}`;
    return base.slice(0, MAX_LENGTH - suffix.length).replace(/-+$/, '') + suffix;
  });
}

/** The entities holding any of `slugs`, in one request (ADR 0107). */
export async function resolveSlugs(tenantId: string, slugs: string[]): Promise<ResolvedSlug[]> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path: { tenant_id: tenantId }, query: { slug: slugs } },
    }),
  );
}

/** The first candidate nothing in the tenant holds, or '' if there's none to give. */
export async function suggestSlug(
  tenantId: string,
  title: string,
  kind: SlugKind,
): Promise<string> {
  const candidates = slugCandidates(title, kind);
  if (candidates.length === 0) return '';
  const taken = new Set((await resolveSlugs(tenantId, candidates)).map((found) => found.slug));
  return candidates.find((candidate) => !taken.has(candidate)) ?? '';
}

/** Why `value` can't be a slug, or null if it can. */
export function slugProblem(value: string): string | null {
  if (value.length > MAX_LENGTH) return `A slug has at most ${MAX_LENGTH} characters.`;
  if (!GRAMMAR.test(value)) {
    return 'A slug starts with a letter or digit, and has only letters, digits, - and _.';
  }
  return null;
}

/** Saves a slug field's value: nothing if it's unchanged, a clear if it's empty, else a set. */
export async function saveSlug(
  tenantId: string,
  entityId: string,
  current: string | null,
  value: string,
): Promise<void> {
  const wanted = value.trim();
  if (wanted === (current ?? '')) return;
  const params = { path: { tenant_id: tenantId, entity_id: entityId } };
  const path = '/tenants/{tenant_id}/entities/{entity_id}/slug';
  if (!wanted) {
    await unwrap(await client.DELETE(path, { params }));
    return;
  }
  const problem = slugProblem(wanted);
  if (problem) throw new Error(problem);
  try {
    await unwrap(await client.PUT(path, { params, body: { slug: wanted } }));
  } catch (e) {
    if (e instanceof LorenzoApiError && e.status === 409) {
      throw new Error(`Another entity already uses “${wanted}”.`);
    }
    throw e;
  }
}
