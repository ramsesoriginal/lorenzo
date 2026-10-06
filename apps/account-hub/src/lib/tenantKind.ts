// Libraries and repositories (ADR 0178), and who may create either (ADR 0175).
// Pure and dependency-free like format.ts: the page and the DOM modules ask
// these, and a test holds them to what the API says.
//
// The API has one thing, a tenant, with a kind. The product has two nouns: a
// tenant of kind `play` is a library, one of kind `repository` is a
// repository, and it is not a library and not part of one (identity §14.3).
import type { MeOut, TenantSummaryOut } from './types';

export type TenantKind = TenantSummaryOut['kind'];

type WithKind = Pick<TenantSummaryOut, 'kind'>;

export function isRepository(tenant: WithKind): boolean {
  return tenant.kind === 'repository';
}

// What product copy calls it, lower case, for a sentence.
export function kindNoun(kind: TenantKind): 'library' | 'repository' {
  return kind === 'repository' ? 'repository' : 'library';
}

// The same, for the start of a label or a heading.
export function kindNounCapitalized(kind: TenantKind): 'Library' | 'Repository' {
  return kind === 'repository' ? 'Repository' : 'Library';
}

// One `GET /tenants` answer, two lists, in the order they came.
export function splitByKind<T extends WithKind>(
  tenants: readonly T[],
): { libraries: T[]; repositories: T[] } {
  return {
    libraries: tenants.filter((tenant) => !isRepository(tenant)),
    repositories: tenants.filter(isRepository),
  };
}

// `GET /me`'s `capabilities.create_tenant` (ADR 0175). A client treats a
// missing key as false: an older API, or a capability that does not exist yet,
// says nothing, and nothing is offered.
export function canCreateTenants(me: { capabilities?: Partial<MeOut['capabilities']> }): boolean {
  return me.capabilities?.create_tenant === true;
}

// A repository's draft/published state, from `TenantOut.published_at` (ADR
// 0118): read-only here, publishing stays on the CLI. The date is the UTC day,
// so the sentence reads the same wherever it is read.
export function publishedLabel(publishedAt: string | null): string {
  return publishedAt === null ? 'Draft' : `Published ${publishedAt.slice(0, 10)}`;
}

// Where a library or repository is on /tenants: the page opens the one an address names, by slug
// or by id.
export function tenantHref(slugOrId: string): string {
  return `/tenants/?tenant=${encodeURIComponent(slugOrId)}`;
}
