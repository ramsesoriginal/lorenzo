import type { components } from './api';

export type TenantSummary = components['schemas']['TenantSummaryOut'];

/**
 * The repositories a person authors, in name order: tenants of kind `repository` where they hold
 * a role that edits content. "Pinned = every repository you author" (RFC 0039). A library, or a
 * repository they only read or are granted, is not one. `author` is the role of RFC 0040 and is
 * not in the API's schema yet, so roles are compared as plain strings.
 */
export function authoredRepositories(tenants: readonly TenantSummary[]): TenantSummary[] {
  const edits = new Set(['owner', 'orga', 'author']);
  return tenants
    .filter((t) => t.kind === 'repository' && edits.has(t.role as string))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** The repository to open: the one chosen last time if it is still theirs, else the first. */
export function repositoryToOpen(
  repositories: readonly TenantSummary[],
  lastId: string | null,
): TenantSummary | null {
  return repositories.find((r) => r.id === lastId) ?? repositories[0] ?? null;
}
