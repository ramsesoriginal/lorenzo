// Deleting a library or repository (ADR 0267, on the route of ADR 0184), as plain functions and
// sentences: who is offered the button, what is said is lost, when the typed name opens it, and
// what a refusal means in words. No DOM and nothing but ./types and ./apiError, so they run under
// Node in the unit tests. The words are those of identity.md §14.3.
import { ApiError } from './apiError';
import { kindNoun, type TenantKind } from './tenantKind';
import type { RosterEntry } from './types';

// Where a person stands toward the delete button of one library or repository.
//   allowed          an Owner whose account may delete: the button is there.
//   owner-only       an Organizer, who edits it but may not delete it.
//   needs-permission an Owner whose account lacks the platform permission that deleting also needs
//                    (the one that creates libraries, ADR 0184).
//   none             anyone else sees nothing.
export type DeleteStanding = 'allowed' | 'owner-only' | 'needs-permission' | 'none';

export function deleteStanding(
  tenant: { role: string },
  accountMayDelete: boolean,
): DeleteStanding {
  if (tenant.role === 'orga') return 'owner-only';
  if (tenant.role !== 'owner') return 'none';

  return accountMayDelete ? 'allowed' : 'needs-permission';
}

// The sentence in place of the button, for a standing that has none; null where there is a button
// (or nothing to say).
export function standingNote(standing: DeleteStanding, kind: TenantKind): string | null {
  const noun = kindNoun(kind);

  if (standing === 'owner-only') {
    return `Only an Owner can delete this ${noun}. Ask one of its Owners if it should go.`;
  }

  if (standing === 'needs-permission') {
    return `You are an Owner of this ${noun}, but deleting one also needs the permission to create libraries and repositories, which your account doesn't have yet.`;
  }

  return null;
}

// What the counts are of; null where a count could not be read, which is then not claimed.
export type Losses = { campaigns: number | null; entries: number | null; people: number | null };

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// The people of a roster, each counted once however many roles they hold there.
export function distinctPeople(roster: readonly RosterEntry[]): number {
  return new Set(
    roster.flatMap((entry) => ('user_id' in entry && entry.user_id ? [entry.user_id] : [])),
  ).size;
}

// What goes with it, one line each, for the dialog. A repository has no campaigns, so a null count
// leaves its line out.
export function lossLines(losses: Losses): string[] {
  const lines: string[] = [];

  if (losses.campaigns !== null) lines.push(plural(losses.campaigns, 'campaign', 'campaigns'));
  if (losses.entries !== null) lines.push(plural(losses.entries, 'entry', 'entries'));
  if (losses.people !== null)
    lines.push(plural(losses.people, 'person with a role', 'people with a role'));

  return lines;
}

export function deleteIntro(name: string): string {
  return `This deletes "${name}" and everything in it for good. There is no undo.`;
}

export function deleteFootnote(kind: TenantKind): string {
  return kind === 'repository'
    ? 'Libraries that already copied it keep what they copied, but it can no longer give them updates. Its people are told.'
    : 'Characters and items that were copied out of it elsewhere are not touched. Its people are told.';
}

// Typing the name is what opens the button: exactly the name, apart from space around it.
export function nameMatches(typed: string, name: string): boolean {
  return typed.trim() === name.trim() && name.trim() !== '';
}

export function typeNamePrompt(name: string): string {
  return `Type "${name}" to confirm`;
}

export function deletedMessage(name: string, kind: TenantKind): string {
  return `Deleted ${kindNoun(kind)} "${name}".`;
}

// A refusal of the delete in words, from the API's problem type; null for anything else, which
// describeError then handles.
export function refusalMessage(error: unknown, kind: TenantKind): string | null {
  if (!(error instanceof ApiError)) return null;

  const noun = kindNoun(kind);

  switch (error.problemType) {
    case 'repository-still-granted':
      return `Other libraries still draw on this ${noun}, so it can't be deleted yet. On the Libraries using it tab, stop inviting each of them, then try again. Libraries that already copied it keep their copies.`;
    case 'tenant-deletion-forbidden':
      return `Only an Owner can delete this ${noun}.`;
    case 'tenant-creation-forbidden':
      return `Your account doesn't have the permission deleting a ${noun} needs: the one that creates libraries and repositories.`;
    default:
      return null;
  }
}
