// What Studio says about running a repository (RFC 0036 §4, ADR 0202), as plain functions and
// sentences: where it is, what a role means, what a repository's state means. No DOM and nothing
// but ./types, so they run under Node in the unit tests. The words are those of identity.md §14.3.

import type { TenantRole } from './types';

// The address of Studio: the list, or one repository by its link name (slug) or id.
export function studioHref(repository?: string): string {
  if (!repository) return '/studio/';

  return `/studio/?${new URLSearchParams({ repository }).toString()}`;
}

// The address that opens the form for a new repository.
export const STUDIO_NEW_HREF = '/studio/?new=1';

// What an address asks for: a repository, or the form that makes one. Either may be absent.
export function readStudioLocation(search: string): {
  repository: string | null;
  create: boolean;
} {
  const query = new URLSearchParams(search);

  return { repository: query.get('repository'), create: query.get('new') === '1' };
}

// A role as a person reads it. Only an Owner or an Organizer works on a repository today; the
// Author role (RFC 0040) adds a third.
export function roleLabel(role: string): string {
  switch (role) {
    case 'owner':
      return 'Owner';
    case 'orga':
      return 'Organizer';
    default:
      return role;
  }
}

export type RoleMeaning = { role: 'owner' | 'orga'; label: string; meaning: string };

// What each role can do on a repository, written next to the people who have it. Each is what the
// API enforces: publishing, unpublishing, inviting and revoking a library, and changing people are
// an Owner's alone; editing the repository and its content is an Owner's or an Organizer's.
export const ROLE_MEANINGS: readonly RoleMeaning[] = [
  {
    role: 'owner',
    label: 'Owner',
    meaning:
      'Full control: publishes the repository, invites libraries to it, adds and removes people, and edits its content.',
  },
  {
    role: 'orga',
    label: 'Organizer',
    meaning:
      'Edits the repository and its content. Cannot publish it, invite libraries or change who works on it.',
  },
];

// Said once under the roles: the one who edits is an Organizer, until the role for someone who
// only writes exists (RFC 0040).
export const ROLES_NOTE =
  'Until there is a role for people who only write content, an Organizer is the one who edits.';

export type RepositoryState = {
  published: boolean;
  // "Draft", or "Published 2026-10-03": the UTC day, so it reads the same wherever it is read.
  label: string;
  explanation: string;
};

// A repository's state in words, from `TenantOut.published_at` (ADR 0118).
export function repositoryState(publishedAt: string | null): RepositoryState {
  if (publishedAt === null) {
    return {
      published: false,
      label: 'Draft',
      explanation:
        'Not published yet. Libraries it has been offered to cannot look inside it or copy it until you publish it.',
    };
  }

  return {
    published: true,
    label: `Published ${publishedAt.slice(0, 10)}`,
    explanation:
      'Published. The libraries it has been offered to can look inside it, copy it and take its updates.',
  };
}

// True of the API as it is (ADR 0183): publishing is an announcement and reads are live, so what a
// library sees when it next checks is what is in the repository then. Shown on a published
// repository, where it matters.
export const LIVE_NOTICE =
  'Libraries that copy from this repository see your edits when they next check for updates.';

// Whether the controls that change who works on a repository are shown: an Owner's, as the API
// has it (and bulk invite, which is gated the same).
export function canChangePeople(role: TenantRole): boolean {
  return role === 'owner';
}

// What the sentence about creating says when the account may not.
export const CREATE_NOT_OPEN = "Creating a repository isn't open to your account yet.";
