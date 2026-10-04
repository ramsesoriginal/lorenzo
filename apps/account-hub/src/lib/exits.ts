// What a person is asked, and told, when they leave something of their own
// (ADR 0170). Pure and dependency-free like format.ts: the sentences live here
// so a test can hold them to what the API actually does.
import { ApiError } from './apiError';

// apps/api's LastOwnerError names the tenant in its detail: "User <id> is the
// sole OWNER of tenant <id>" (DELETE /me and DELETE .../memberships/{me}).
const SOLE_OWNER_OF =
  /sole OWNER of tenant ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;

export type Exit = 'leave-library' | 'delete-account';

// The library a 409 LastOwnerError is about, or null when it is anything else.
export function soleOwnerLibraryId(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.problem.detail;
  return typeof detail === 'string' ? (SOLE_OWNER_OF.exec(detail)?.[1] ?? null) : null;
}

// Plain words for "you are the only owner": which library, and what to do. null
// for any other error, which describeError then handles. A library id that
// isn't in `libraryNames` (the API checks every library a person owns and
// names the first) is still said, just without a name.
export function soleOwnerMessage(
  error: unknown,
  libraryNames: ReadonlyMap<string, string>,
  exit: Exit,
): string | null {
  const id = soleOwnerLibraryId(error);
  if (id === null) return null;
  const name = libraryNames.get(id);
  const library = name === undefined ? 'one of your libraries' : `"${name}"`;
  const blocked =
    exit === 'leave-library' ? "you can't leave it yet" : "your account can't be deleted yet";
  return `You're the only owner of ${library}, so ${blocked}. Make someone else an owner first, then try again.`;
}

// What ADR 0084 says a departure does: the tenant-wide membership ends and
// nothing else: nothing they made is deleted and campaign seats stay.
export function leaveLibraryConfirmation(libraryName: string): string {
  return `Leave "${libraryName}"? Your membership ends, so you won't be able to administer it any more. Nothing you made there is deleted, and any campaign seat or GM role you hold in it stays as it is. You'll get a notification confirming it.`;
}

// Revoking your own GM grant (ADR 0034). A library administrator keeps the
// campaign through their administrator standing.
export function stepDownConfirmation(campaignName: string): string {
  return `Step down as GM of "${campaignName}"? You'll stop managing this campaign unless you also administer its library. A library administrator or another GM can make you its GM again.`;
}

// DELETE /me (ADR 0036, ADR 0084's addendum): what it removes, what it leaves,
// and what it does not touch: the Authgear login.
export function deleteAccountConfirmation(): string {
  return "Delete your Lorenzo account? This removes your account and ends every membership, player seat, GM role and campaign opt-out you hold, in every library. What you made stays, but no longer names you. It does not delete your Authgear login: if you log in again, you'll get a fresh, empty Lorenzo account.";
}
