// View as a subscriber (RFC 0036 §4, T6, ADR 0261): a scratch Test library the repository's Owner
// owns, invited to the repository, so the Owner opens Shelf for it and sees what a library's admin
// sees. Plain functions over what the API returns, and the making of the library with its API
// calls passed in, so the cleanup on a failure is unit-tested. No DOM. The words are identity §14.3's.

import type { SubscriberOut, TenantSummaryOut } from './types';

// The Test library of a repository is told by its name: the API has no marker for a scratch
// library, and nothing is added to it for this (RFC 0036).
export function testLibraryName(repositoryName: string): string {
  return `Test library: ${repositoryName}`;
}

export type TestLibrary = { id: string; slug: string; copied: boolean };

// The Test library the person already has for this repository, if any: a library they own, with
// the Test library's name, that the repository has an invitation to. The invitation is required so
// that a library of the same name that is not part of this is never taken for it.
export function findTestLibrary(
  repositoryName: string,
  subscribers: readonly SubscriberOut[],
  mine: readonly Pick<TenantSummaryOut, 'id' | 'role' | 'kind'>[],
): TestLibrary | null {
  const name = testLibraryName(repositoryName);
  const owned = new Set(
    mine.filter((t) => t.kind === 'play' && t.role === 'owner').map((t) => t.id),
  );
  const found = subscribers.find(
    (s) => s.name === name && s.granted_at !== null && owned.has(s.tenant_id),
  );

  return found ? { id: found.tenant_id, slug: found.slug, copied: found.copied_at !== null } : null;
}

// Whether the button is offered: an Owner who may create libraries (and so remove the Test library
// again, which the API gates the same way, ADR 0184), on a published repository (a draft cannot be
// copied).
export function canViewAsSubscriber(
  role: TenantSummaryOut['role'],
  mayCreate: boolean,
  published: boolean,
): boolean {
  return role === 'owner' && mayCreate && published;
}

export const SUBSCRIBER_HEADING = 'See it as a subscriber';

export const SUBSCRIBER_EXPLANATION =
  'Opens Shelf for a Test library of your own, invited to this repository, so you copy it and take its updates exactly as a library would. Nothing of a real library is touched.';

// What explains the missing button.
export function subscriberUnavailable(
  role: TenantSummaryOut['role'],
  mayCreate: boolean,
  published: boolean,
): string | null {
  if (role !== 'owner') return 'Only an Owner can set up a Test library.';
  if (!mayCreate) return "Making a Test library isn't open to your account yet.";
  if (!published) return 'Publish this repository first: a library cannot copy a draft.';

  return null;
}

export function testLibraryLine(library: TestLibrary | null): string {
  if (library === null) return 'You have no Test library for this repository yet.';

  return library.copied
    ? 'Your Test library has copied this repository. Publish a change and it will see the update, as a library would.'
    : 'Your Test library is invited and has not copied this repository yet.';
}

export const RESET_CONFIRMATION =
  'Reset the Test library? It copies this repository again and replaces what it copied before. Nothing else is touched.';

export const REMOVE_CONFIRMATION =
  'Remove the Test library? It is deleted with everything in it. This repository and its invitations to real libraries are not touched.';

export const RESET_DONE = 'The Test library has copied this repository afresh.';
export const REMOVED = 'The Test library is removed.';

// What is left behind when the clean-up fails too: said so that it can be removed by hand.
export function leftBehind(name: string): string {
  return `The Test library “${name}” could not be removed again. Remove it from your libraries.`;
}

// The calls making a Test library takes; the hub's are in lib/tenants.ts and lib/repositories.ts.
export type TestLibraryCalls = {
  create(name: string): Promise<{ id: string; slug: string }>;
  invite(repositoryId: string, libraryId: string): Promise<void>;
  remove(libraryId: string): Promise<void>;
};

// Thrown when making the Test library failed; `cleanedUp` is false when the library made before the
// failure could not be removed either.
export class TestLibraryError extends Error {
  constructor(
    readonly cause: unknown,
    readonly cleanedUp: boolean,
    readonly libraryName: string,
  ) {
    super(cause instanceof Error ? cause.message : String(cause));
  }
}

// Makes the Test library and invites it. Whatever fails after the library exists removes it again,
// so none is left half made.
export async function makeTestLibrary(
  calls: TestLibraryCalls,
  repository: { id: string; name: string },
): Promise<TestLibrary> {
  const name = testLibraryName(repository.name);
  const library = await calls.create(name);

  try {
    await calls.invite(repository.id, library.id);
  } catch (cause) {
    let cleanedUp = true;

    try {
      await calls.remove(library.id);
    } catch {
      cleanedUp = false;
    }

    throw new TestLibraryError(cause, cleanedUp, name);
  }

  return { id: library.id, slug: library.slug, copied: false };
}
