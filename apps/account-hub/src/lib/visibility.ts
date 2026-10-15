// What Studio says about a repository being private or public (RFC 0036 §4 T7, RFC 0038 §1, §5 and §7,
// ADR 0290), as plain functions over what the API returns: the card on the Overview, the two
// dialogs' lines and blockers, the checks on the form and the bodies sent. No DOM and nothing but
// ./types, ./studio and ./releases, so they run under Node in the unit tests. The words are those of
// identity.md §14.3: library, repository, release, Owner, entry, copy, update, built on; never
// "tenant", "grant" or "subscription".
//
// Every sentence is true of the API as it is: a public repository is read from its releases, so what
// an Owner edits between two of them is not seen until the next (ADR 0289); the text of an entry that
// is GM only travels with a copy like every other text (ADR 0119, RFC 0038 §7); what a library copied
// stays with it whatever happens to the repository (ADR 0289); and the libraries that copied it by
// themselves are told and lose its updates when it goes private, while the ones invited keep theirs.
// Nothing here says anything of the terms an Owner agrees to or the account shown as publisher: those
// are RFC 0038 D6's, and the maintainer's words.

import { DELISTED_CANNOT_BE_MADE_PUBLIC, DELISTED_PUBLIC_NOTE } from './delisting';
import { type ComposerForm, composerProblem, publishBody } from './releases';
import { studioHref } from './studio';
import type {
  BreakingRowOut,
  FlipCheckOut,
  MakePublicRequest,
  RepositoryProfileOut,
  TenantRole,
} from './types';

export type Visibility = FlipCheckOut['visibility'];
export type PreviewChoice = RepositoryProfileOut['preview'];

export const SUMMARY_MAX = 280;

function libraries(count: number): string {
  return count === 1 ? '1 library' : `${count} libraries`;
}

// ---------------------------------------------------------------------------------------------
// The card on the Overview.

export const VISIBILITY_HEADING = 'Who can find it';

export type VisibilityCard = {
  visibility: Visibility;
  label: string;
  sentence: string;
  button: string;
  // A button that cannot be pressed, with the reason (while the platform's operators have the
  // repository off Discover it cannot be made public), and a sentence to read beside it.
  disabled: boolean;
  note: string | null;
};

// What the card shows, or null where it is not shown at all: to anyone who is not an Owner, before
// the repository has been read, and while the deployment does not accept public repositories and
// the repository is private (there is nothing to switch). A public repository shows its card either
// way, so that it can be made private.
export function visibilityCard(
  check: Pick<FlipCheckOut, 'available' | 'visibility' | 'delisted'> | null,
  role: TenantRole,
): VisibilityCard | null {
  if (role !== 'owner' || check === null) return null;

  if (check.visibility === 'public') {
    return {
      visibility: 'public',
      label: 'Public',
      sentence:
        'Anyone signed in to Lorenzo can copy it into a library and take its updates, as well as the libraries you invited.',
      button: 'Make private…',
      disabled: false,
      note: check.delisted ? DELISTED_PUBLIC_NOTE : null,
    };
  }

  if (!check.available) return null;

  return {
    visibility: 'private',
    label: 'Private',
    sentence:
      'Only the people who work on it and the libraries you invite can see it. Nobody else can find it or copy it.',
    button: 'Make public…',
    // Refused by the API (409 repository-delisted): the button says so before it is pressed.
    disabled: Boolean(check.delisted),
    note: check.delisted ? DELISTED_CANNOT_BE_MADE_PUBLIC : null,
  };
}

// ---------------------------------------------------------------------------------------------
// What stands in the way: said in words, first in the dialog, and the last button waits for them.

export type Blocker = {
  text: string;
  // Where to go about it: the Studio page of a repository the Owner owns.
  link?: { href: string; label: string };
};

// A repository this one is built on, and what it needs before this one can be public.
export function publicBlockers(check: FlipCheckOut): Blocker[] {
  const blockers: Blocker[] = [];

  for (const upstream of check.built_on_not_public) {
    blockers.push(
      upstream.owned
        ? {
            text: `${upstream.name} is not public. This repository is built on it, and a library that copies this one gets it too, so it has to be public first.`,
            link: {
              href: studioHref(upstream.id),
              label: `Open ${upstream.name} to make it public`,
            },
          }
        : {
            text: `${upstream.name} is not public. This repository is built on it, so it has to be public first: ask its Owner to make it public.`,
          },
    );
  }

  for (const upstream of check.built_on_behind) {
    const place =
      upstream.taken && upstream.current
        ? ` This repository took release ${upstream.taken.label}, and the latest is ${upstream.current.label}.`
        : '';

    blockers.push({
      text: `${upstream.name} has a release this repository has not taken.${place} Take the new release of ${upstream.name} first: open Built on.`,
    });
  }

  return blockers;
}

export const PUBLIC_BLOCKERS_TITLE = 'Before you can make it public';

// The public repositories built on this one, which have to be made private first.
export function privateBlockers(check: FlipCheckOut): Blocker[] {
  return check.public_dependents.map((dependent) =>
    dependent.owned
      ? {
          text: `${dependent.name} is public and built on this repository. Make it private first, so that what it is built on can still be copied.`,
          link: {
            href: studioHref(dependent.id),
            label: `Open ${dependent.name} to make it private`,
          },
        }
      : {
          text: `${dependent.name} is public and built on this repository. It has to be private first, so that what it is built on can still be copied: ask its Owner to make it private.`,
        },
  );
}

export const PRIVATE_BLOCKERS_TITLE = 'Before you can make it private';

// ---------------------------------------------------------------------------------------------
// The "Make public" dialog.

export const PREVIEW_CHOICES: readonly { value: PreviewChoice; label: string }[] = [
  { value: 'showcase', label: 'People can look at the entries you feature before copying.' },
  { value: 'public', label: 'People can look at every entry.' },
  { value: 'off', label: 'People see its summary and counts only.' },
];

export const PREVIEW_DEFAULT: PreviewChoice = 'showcase';
export const PREVIEW_LEGEND = 'What can people look at before they copy it?';

export const SUMMARY_HELP = `One or two lines that say what this repository is. People read it before they copy it. At most ${SUMMARY_MAX} characters.`;

export function makePublicTitle(name: string): string {
  return `Make ${name} public`;
}

export const MAKE_PUBLIC_CONFIRM = 'Make public and publish release';

export const MAKE_PUBLIC_DONE = 'Public. A release was published.';

// What will happen, in order.
export function makePublicLines(
  check: Pick<FlipCheckOut, 'invited_libraries'>,
  name: string,
): string[] {
  const lines = [
    `Making ${name} public publishes a release of it, with the label and notes below. Anyone signed in to Lorenzo can then copy it into a library and take its updates.`,
    'A public repository is read from its releases: what you edit between two releases is not seen by a library until you publish the next one.',
  ];

  if (check.invited_libraries > 0) {
    lines.push(
      `${libraries(check.invited_libraries)} ${check.invited_libraries === 1 ? 'has' : 'have'} an invitation and ${check.invited_libraries === 1 ? 'is' : 'are'} told when you publish: each one's Owners and Organizers get a notification.`,
    );
  }

  return lines;
}

// What to look at first, whatever else is in the way.
export function makePublicWarnings(): string[] {
  return [
    "The text of an entry is copied along with it, and that includes text marked GM only: whoever copies this repository gets it, and the Owners and Organizers of their library can read it. Players never see it. Text that is Everyone's is copied too. Mark what you want to keep back as GM only, or take it out, before you make it public.",
    'Libraries that copy it keep their copies, whatever you do to this repository later.',
  ];
}

export type MakePublicForm = ComposerForm & {
  summary: string;
  preview: PreviewChoice;
};

// A summary on one line, as the API keeps it: whitespace of any kind runs together into one space.
export function oneLine(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

export function summaryProblem(summary: string): string | null {
  const text = oneLine(summary);

  if (text === '') return 'Write a summary: one or two lines that say what this repository is.';
  if (text.length > SUMMARY_MAX) {
    return `A summary is at most ${SUMMARY_MAX} characters. This one is ${text.length}.`;
  }

  return null;
}

// How the count under the summary reads.
export function summaryCount(summary: string): string {
  return `${oneLine(summary).length} of ${SUMMARY_MAX}`;
}

// Why the form cannot be sent yet, or null: the summary first, then what a release asks.
export function makePublicProblem(
  form: MakePublicForm,
  hits: readonly BreakingRowOut[],
): string | null {
  return summaryProblem(form.summary) ?? composerProblem(form, hits);
}

// The body of `PUT .../public`: what a publish sends, and the summary and the choice of preview.
export function makePublicBody(
  form: MakePublicForm,
  hits: readonly BreakingRowOut[],
): MakePublicRequest {
  return { ...publishBody(form, hits), summary: oneLine(form.summary), preview: form.preview };
}

// ---------------------------------------------------------------------------------------------
// The "Make private" dialog.

export function makePrivateTitle(name: string): string {
  return `Make ${name} private`;
}

export const MAKE_PRIVATE_CONFIRM = 'Make private';

export function makePrivateLines(check: FlipCheckOut): string[] {
  const copied = check.public_libraries;
  const invited = check.invited_libraries;
  const lines = [
    copied === 0
      ? 'No library copied it by itself while it was public, so none loses anything.'
      : `${libraries(copied)} copied it while it was public: ${copied === 1 ? 'it keeps' : 'they keep'} what ${copied === 1 ? 'it' : 'they'} copied and ${copied === 1 ? 'loses' : 'lose'} its updates. The Owners and Organizers of ${copied === 1 ? 'that library are' : 'those libraries are'} told.`,
  ];

  if (invited > 0) {
    lines.push(
      `${libraries(invited)} you invited ${invited === 1 ? 'keeps its' : 'keep their'} access, and read${invited === 1 ? 's' : ''} the repository as it is again, not its releases.`,
    );
  }

  lines.push(
    'From then on, only the people who work on it and the libraries you invite can see it.',
  );

  return lines;
}

// What an Owner says they understand when libraries are cut off: only asked when there are any.
export function privateAcknowledgement(
  check: Pick<FlipCheckOut, 'public_libraries'>,
): string | null {
  const copied = check.public_libraries;

  if (copied === 0) return null;

  return `I understand that ${libraries(copied)} will lose the updates of this repository and keep what ${copied === 1 ? 'it' : 'they'} copied.`;
}

export function makePrivateProblem(
  check: Pick<FlipCheckOut, 'public_libraries'>,
  acknowledged: boolean,
): string | null {
  if (check.public_libraries > 0 && !acknowledged) {
    return 'Libraries lose its updates. Say you understand, to make it private.';
  }

  return null;
}

// `DELETE .../public`: asking for the cut-off is the acknowledgement.
export function makePrivateQuery(
  check: Pick<FlipCheckOut, 'public_libraries'>,
  acknowledged: boolean,
): boolean {
  return check.public_libraries > 0 && acknowledged;
}

// What the status line says after it was made private, from how many libraries were cut off.
export function madePrivateDone(revoked: number): string {
  return revoked === 0
    ? 'Private again.'
    : `Private again. ${libraries(revoked)} lost its updates and ${revoked === 1 ? 'keeps what it' : 'keep what they'} copied.`;
}

// The refusals that mean something changed under the dialog: what it says is read again, and the
// dialog stays open with what is true now.
const CHANGED_UNDER_IT = new Set([
  'built-on-not-public',
  'built-on-behind',
  'public-repositories-built-on-it',
  'public-copies-would-be-cut-off',
  'repository-already-public',
  'repository-already-private',
  'repository-delisted',
]);

export function changedUnderTheDialog(problemType: string | undefined): boolean {
  return problemType !== undefined && CHANGED_UNDER_IT.has(problemType);
}
