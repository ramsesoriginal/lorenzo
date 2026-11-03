// What Studio and Shelf say when an Owner has retired a repository (RFC 0038 §7, ADR 0383), as plain
// functions over what the API returns. No DOM and nothing but ./types, so they run under Node in the
// unit tests. The API calls this deprecated; people read "retired" (identity.md §14.3): "Retire this
// repository", "This repository is retired", "Bring it back". The words are those of §14.3 as well:
// library, repository, copy, update, Owner; never "tenant", "grant" or "subscription".
//
// Every sentence is true of the API as it is: a retired repository keeps its updates for the
// libraries that hold it, cannot be copied by anyone (an invitation that was not used included), and
// is not on Discover. Its own members read it and edit it as ever. A library reads the Owner's
// message, never who retired it.

import type { DeprecatedNoticeOut, DeprecatedOut } from './types';

export const RETIRED_PILL = 'Retired';

// The longest message an Owner leaves, as the API holds it.
export const RETIRE_MESSAGE_MAX = 500;

// --- Studio: the Owner's card ---------------------------------------------------------------

export const RETIRE_HEADING = 'Retire this repository';

export const RETIRE_EXPLANATION =
  'Libraries that already copied it keep their copy and its updates. Nobody can copy it any more, and it leaves Discover.';

export const RETIRE_MESSAGE_LABEL = 'Message for the libraries (optional)';

export const RETIRE_MESSAGE_HELP =
  'The libraries that hold this repository read it, and so does everyone who works on it. You could say what to use instead.';

export const RETIRE_BUTTON = 'Retire…';

export const RETIRE_CONFIRM = 'Retire it';

export const BRING_BACK_BUTTON = 'Bring it back';

export const BRING_BACK_NOTE =
  'The libraries that hold it will be told. It can be copied again, and it is on Discover again if it is public.';

export const RETIRED_STATE = 'This repository is retired.';

export function retiredAt(deprecated: Pick<DeprecatedOut, 'at'>): string {
  return `Retired on ${deprecated.at.slice(0, 10)}.`;
}

// How far the message is from its limit, for the counter under the field.
export function messageCount(text: string): string {
  return `${text.trim().length} of ${RETIRE_MESSAGE_MAX} characters`;
}

// Why the message cannot be sent yet, or null when it can. An empty message is fine: it is optional.
export function messageProblem(text: string): string | null {
  return text.trim().length > RETIRE_MESSAGE_MAX
    ? `A message is at most ${RETIRE_MESSAGE_MAX} characters.`
    : null;
}

// What `PUT .../deprecation` is sent: the message when there is one, nothing when the field is empty.
export function retireBody(text: string): { message?: string } {
  const message = text.trim();

  return message === '' ? {} : { message };
}

export function retireDialogTitle(name: string): string {
  return `Retire ${name}?`;
}

// What retiring does, said before it does it. `libraries` is how many libraries and repositories hold
// it (copied it or were invited to it), as the Studio's "Libraries using it" counts them.
export function retireDialogLines(libraries: number): string[] {
  const holders =
    libraries === 0
      ? 'No library holds it yet.'
      : libraries === 1
        ? '1 library holds it. It keeps its copy and its updates, and it will be told that you retired it.'
        : `${libraries} libraries hold it. They keep their copy and its updates, and they will be told that you retired it.`;

  return [
    holders,
    'Nobody can copy it any more, and it leaves Discover.',
    'You can bring it back at any time.',
  ];
}

export type RetireCard = {
  retired: boolean;
  // The Owner's words, or null when they left none, for a retired repository.
  message: string | null;
  // When it was retired, as a sentence, for a retired repository.
  since: string | null;
};

// What the card shows: the form to retire it, or, where it is retired, the message and the way back.
export function retireCard(deprecated: DeprecatedOut | null | undefined): RetireCard {
  if (!deprecated) return { retired: false, message: null, since: null };

  return { retired: true, message: deprecated.message, since: retiredAt(deprecated) };
}

// The words around a message, for whoever reads it.
export function messageLine(message: string | null | undefined): string | null {
  return message ? `Message: ${message}` : null;
}

// --- Studio: the notice every member reads -------------------------------------------------

export type RetiredNotice = {
  pill: string;
  title: string;
  effect: string;
  message: string | null;
};

export const RETIRED_TITLE = 'This repository is retired.';

export const RETIRED_EFFECT =
  'Libraries that copied it keep their copy and its updates. It cannot be copied or found in Discover.';

// The notice for the members of a retired repository, or null for one that is not.
export function retiredNotice(deprecated: DeprecatedOut | null | undefined): RetiredNotice | null {
  if (!deprecated) return null;

  return {
    pill: RETIRED_PILL,
    title: RETIRED_TITLE,
    effect: RETIRED_EFFECT,
    message: messageLine(deprecated.message),
  };
}

// On the visibility card: why "Make public…" cannot be pressed while it is retired, and, for a
// repository that is public already, what being retired means for it.
export const RETIRED_CANNOT_BE_MADE_PUBLIC =
  'It cannot be made public while it is retired. Bring it back first.';

export const RETIRED_PUBLIC_NOTE =
  'It is public, and retired: nobody can find it or copy it until you bring it back.';

// --- Shelf: what a library reads of a repository it holds ---------------------------------

export type RetiredHere = {
  pill: string;
  // What it means for this library.
  sentence: string;
  message: string | null;
};

export const RETIRED_KEPT =
  'Its Owner retired this repository. Your library keeps its copy and its updates, and it cannot be copied again.';

export const RETIRED_CANNOT_COPY = 'This repository is retired and can no longer be copied.';

// What a library that holds a repository reads of it being retired, or null for one that is not. A
// library that has not copied it is told it cannot; one that has is told what it keeps.
export function retiredHere(
  deprecated: DeprecatedNoticeOut | null | undefined,
  copied: boolean,
): RetiredHere | null {
  if (!deprecated) return null;

  return {
    pill: RETIRED_PILL,
    sentence: copied ? RETIRED_KEPT : RETIRED_CANNOT_COPY,
    message: deprecated.message ? `Message from its Owner: ${deprecated.message}` : null,
  };
}
