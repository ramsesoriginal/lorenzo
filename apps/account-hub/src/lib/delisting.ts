// What Studio says when the platform's operators have taken a repository off Discover (RFC 0038 §6,
// ADR 0303), as plain functions over what the API returns: the notice on the Overview, which every
// member of the repository reads, and the sentence on the visibility card. No DOM and nothing but
// ./types, so they run under Node in the unit tests. The words are those of identity.md §14.3:
// library, repository, copy, update; never "tenant", "grant" or "subscription". The operators are
// "the platform's operators", never a person.
//
// Every sentence is true of the API as it is: a delisted repository leaves Discover and its page,
// is closed to new copies, and reads as unpublished to every library, so the libraries that copied it
// keep their copies and cannot check it for updates; its own members read it and edit it as ever
// (they have to be able to fix it).

import type { DelistedOut } from './types';

export type DelistedNotice = {
  pill: string;
  title: string;
  reason: string;
  effect: string;
};

export const DELISTED_PILL = 'Off Discover';

export const DELISTED_TITLE = "This repository was taken off Discover by the platform's operators.";

export const DELISTED_EFFECT =
  'Libraries that copied it keep their copies, and cannot update from it until it is listed again.';

export function delistedReason(reason: string): string {
  return `Reason: ${reason}`;
}

// The notice for the members of a delisted repository, or null for one that is listed. It says what
// happened, why, and what it means for the libraries that copied it, in that order.
export function delistedNotice(delisted: DelistedOut | null | undefined): DelistedNotice | null {
  if (!delisted) return null;

  return {
    pill: DELISTED_PILL,
    title: DELISTED_TITLE,
    reason: delistedReason(delisted.reason),
    effect: DELISTED_EFFECT,
  };
}

// On the visibility card: why "Make public…" cannot be pressed while it is off Discover, and for a
// repository that is public already what being off Discover means for it.
export const DELISTED_CANNOT_BE_MADE_PUBLIC =
  "It cannot be made public while it is off Discover. The platform's operators can list it again.";

export const DELISTED_PUBLIC_NOTE =
  'It is public, and off Discover: nobody can find it or copy it until the platform’s operators list it again.';
