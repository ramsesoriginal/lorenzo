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
// An Owner agrees to the terms line before the last button, and the dialog says which account names
// are shown as the publisher (RFC 0038 §6, ADR 0299). The terms line is the maintainer's wording,
// approved on 2026-10-16, and is kept here in one constant.

import { DELISTED_CANNOT_BE_MADE_PUBLIC, DELISTED_PUBLIC_NOTE } from './delisting';
import { type ComposerForm, composerProblem, publishBody } from './releases';
import { RETIRED_CANNOT_BE_MADE_PUBLIC, RETIRED_PUBLIC_NOTE } from './retiring';
import { studioHref } from './studio';
import type {
  FlipCheckOut,
  MakeProtectedRequest,
  MakePublicRequest,
  PublisherOut,
  RepositoryProfileOut,
  TenantRole,
} from './types';

// What a repository is (ADR 0434): the API declares the set extensible, so the hub says the three it knows.
export type Visibility = 'private' | 'protected' | 'public';
// What the card can start: the three flips.
export type FlipMode = 'public' | 'protected' | 'private';
export type PreviewChoice = RepositoryProfileOut['preview'];

export const SUMMARY_MAX = 280;

function libraries(count: number): string {
  return count === 1 ? '1 library' : `${count} libraries`;
}

// ---------------------------------------------------------------------------------------------
// The card on the Overview.

export const VISIBILITY_HEADING = 'Who can find it';

export const PROTECTED_LABEL = 'Protected';
export const PROTECTED_SENTENCE =
  'Not on Discover, and not copied on its own. A library gets it with a public repository built on it, and keeps reading it only as long as it holds one. The libraries you invite read it as they read any repository.';

export type VisibilityAction = { mode: FlipMode; label: string; disabled: boolean };

export type VisibilityCard = {
  visibility: Visibility;
  label: string;
  sentence: string;
  button: string;
  // What the button starts, and the second button where there is one: a repository can go to either
  // of the other two (RFC 0051 H3).
  mode: FlipMode;
  alt: VisibilityAction | null;
  // A button that cannot be pressed, with the reason (while the platform's operators have the
  // repository off Discover it cannot be made public), and a sentence to read beside it.
  disabled: boolean;
  note: string | null;
  // The switch for being on Discover (RFC 0051 H2, ADR 0432): only for a public repository that the
  // platform's operators and its Owner have not already taken off it.
  listed: ListedSwitch | null;
};

// What the card shows, or null where it is not shown at all: to anyone who is not an Owner, before
// the repository has been read, and while the deployment does not accept public repositories and
// the repository is private (there is nothing to switch). A public repository shows its card either
// way, so that it can be made private.
export function visibilityCard(
  check: Pick<
    FlipCheckOut,
    'available' | 'visibility' | 'listed' | 'delisted' | 'deprecated'
  > | null,
  role: TenantRole,
): VisibilityCard | null {
  if (role !== 'owner' || check === null) return null;

  const closed = Boolean(check.delisted || check.deprecated);

  if (check.visibility === 'public') {
    return {
      visibility: 'public',
      label: 'Public',
      sentence:
        'Anyone signed in to Lorenzo can copy it into a library and take its updates, as well as the libraries you invited.',
      button: 'Make private…',
      mode: 'private',
      // Refused while it is off Discover or retired, as making it public is: it would publish what is closed.
      alt: closed ? null : { mode: 'protected', label: 'Make protected…', disabled: false },
      disabled: false,
      note: check.delisted ? DELISTED_PUBLIC_NOTE : check.deprecated ? RETIRED_PUBLIC_NOTE : null,
      listed: check.delisted || check.deprecated ? null : listedSwitch(check.listed),
    };
  }

  if (check.visibility === 'protected') {
    return {
      visibility: 'protected',
      label: PROTECTED_LABEL,
      sentence: PROTECTED_SENTENCE,
      button: 'Make public…',
      mode: 'public',
      alt: { mode: 'private', label: 'Make private…', disabled: false },
      disabled: closed,
      note: check.delisted
        ? DELISTED_CANNOT_BE_MADE_PUBLIC
        : check.deprecated
          ? RETIRED_CANNOT_BE_MADE_PUBLIC
          : null,
      listed: null,
    };
  }

  if (!check.available) return null;

  return {
    visibility: 'private',
    label: 'Private',
    sentence:
      'Only the people who work on it and the libraries you invite can see it. Nobody else can find it or copy it.',
    button: 'Make public…',
    mode: 'public',
    alt: { mode: 'protected', label: 'Make protected…', disabled: closed },
    // Refused by the API (409 repository-delisted, 409 repository-deprecated): the button says so
    // before it is pressed, and the operators' word comes first where both hold.
    disabled: closed,
    note: check.delisted
      ? DELISTED_CANNOT_BE_MADE_PUBLIC
      : check.deprecated
        ? RETIRED_CANNOT_BE_MADE_PUBLIC
        : null,
    listed: null,
  };
}

// ---------------------------------------------------------------------------------------------
// Being on Discover (RFC 0051 H2, ADR 0432): a public repository is listed unless its Owner leaves it
// off. Its page and its address work either way, so the sentence says what stays.

export const LISTED_LABEL = 'Listed on Discover';
// The way to the repository's page, which is what an Owner shares when it is not on Discover: the link is
// the address.
export const LISTED_PAGE_LINK = 'Open its page';
export const LISTED_SAVING = 'Saving…';
export const LISTED_SAVED = 'Saved.';

export type ListedSwitch = { checked: boolean; label: string; help: string };

export function listedHelp(listed: boolean): string {
  return listed
    ? 'Anyone signed in to Lorenzo can find it on Discover.'
    : 'It is not on Discover, and no search finds it. Anyone who has its address can still open its page and copy it, so share the address only with people you want to have it.';
}

export function listedSwitch(listed: boolean): ListedSwitch {
  return { checked: listed, label: LISTED_LABEL, help: listedHelp(listed) };
}

// What is sent when the switch is turned: a repository that is not public cannot be left off Discover
// (the API says 409 repository-not-public), and the switch is not shown for one.
export function listedPatch(listed: boolean): { listed: boolean } {
  return { listed };
}

// ---------------------------------------------------------------------------------------------
// What stands in the way: said in words, first in the dialog, and the last button waits for them.

export type Blocker = {
  text: string;
  // Where to go about it: the Studio page of a repository the Owner owns.
  link?: { href: string; label: string };
};

// A repository this one is built on, and what it needs before this one can be public. Where this one
// may include it (RFC 0051, ADR 0431), it is offered as the other way: the choice is in the list
// below.
export function publicBlockers(
  check: Pick<FlipCheckOut, 'built_on_not_public' | 'built_on_behind'> &
    Partial<Pick<FlipCheckOut, 'built_on'>>,
): Blocker[] {
  const blockers: Blocker[] = [];

  for (const upstream of check.built_on_not_public) {
    const mayInclude = check.built_on?.find((row) => row.id === upstream.id)?.includable.allowed;
    const instead = mayInclude ? ' Or include it in this repository, below.' : '';

    blockers.push(
      upstream.owned
        ? {
            text: `${upstream.name} is private. This repository is built on it, and a library that copies this one gets it too, so it has to be public or protected first.${instead}`,
            link: {
              href: studioHref(upstream.id),
              label: `Open ${upstream.name} to make it public or protected`,
            },
          }
        : {
            text: `${upstream.name} is private. This repository is built on it, so it has to be public or protected first: ask its Owner to make it one of them.${instead}`,
          },
    );
  }

  // Included, and no longer allowed (its Owner took the yes back, or someone else chose it): the release
  // would publish what this user may not.
  for (const upstream of check.built_on ?? []) {
    if (upstream.inclusion === 'include' && !upstream.includable.allowed) {
      blockers.push({
        text: `${upstream.name} is included in this repository, and you may not include it: its Owner has not allowed it, and you are not one of its Owners. Keep it separate below, or ask its Owner to turn on “May be included”.`,
      });
    }
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
          text: `${dependent.name} is built on this repository and others can copy it. Make it private first, or have it include this repository, so that what it is built on can still be copied.`,
          link: {
            href: studioHref(dependent.id),
            label: `Open ${dependent.name} to make it private`,
          },
        }
      : {
          text: `${dependent.name} is built on this repository and others can copy it. It has to be private, or include this repository, first, so that what it is built on can still be copied: ask its Owner.`,
        },
  );
}

export const PRIVATE_BLOCKERS_TITLE = 'Before you can make it private';
export const PROTECTED_BLOCKERS_TITLE = 'Before you can make it protected';

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

// The terms line the Owner ticks before a repository goes public. The maintainer's wording,
// approved on 2026-10-16 (RFC 0038 §6, ADR 0299): the only place it is written in the hub.
export const TERMS_LINE =
  'I have the right to publish this repository. Publishing cannot be recalled: libraries that copied it keep their copies.';

export const TERMS_PROBLEM = 'Tick the box to agree before you make it public.';

// Who a storefront will say published it, as the API reads their account names: what the dialog says
// before the Owner agrees to it.
export function publisherLine(publishers: readonly PublisherOut[]): string {
  const names = publishers.map((publisher) => publisher.display_name);

  if (names.length === 0) return 'People will see who published it, by the name of your account.';
  if (names.length === 1) {
    return `People will see who published it, by the name of your account: ${names[0]}. You can change it in your profile.`;
  }

  return `People will see who published it, by the names of the accounts of its Owners: ${names.join(', ')}. Each Owner can change theirs in their profile.`;
}

export function makePublicTitle(name: string): string {
  return `Make ${name} public`;
}

export const MAKE_PUBLIC_CONFIRM = 'Make public and publish release';

export const MAKE_PUBLIC_DONE = 'Public. A release was published.';

// What will happen, in order.
export function makePublicLines(
  check: Pick<FlipCheckOut, 'invited_libraries' | 'publishers'>,
  name: string,
): string[] {
  const lines = [
    `Making ${name} public publishes a release of it, with the label and notes below. Anyone signed in to Lorenzo can then copy it into a library and take its updates.`,
    'A public repository is read from its releases: what you edit between two releases is not seen by a library until you publish the next one.',
    publisherLine(check.publishers),
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
  // Whether the Owner ticked the terms line.
  terms: boolean;
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

// Why the form cannot be sent yet, or null: the summary first, then the terms, then what a release
// asks.
export function makePublicProblem(form: MakePublicForm, hits: readonly unknown[]): string | null {
  return (
    summaryProblem(form.summary) ??
    (form.terms ? null : TERMS_PROBLEM) ??
    composerProblem(form, hits)
  );
}

// The body of `PUT .../public`: what a publish sends, the summary, the choice of preview and the
// terms line agreed to.
export function makePublicBody(form: MakePublicForm, hits: readonly unknown[]): MakePublicRequest {
  return {
    ...publishBody(form, hits),
    summary: oneLine(form.summary),
    preview: form.preview,
    accept_terms: form.terms,
  };
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
      ? check.visibility === 'protected'
        ? 'No library copied it by itself while it was public. No public repository is built on it that shows it, so no library reads it through one: none loses anything.'
        : 'No library copied it by itself while it was public, so none loses anything.'
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

// ---------------------------------------------------------------------------------------------
// The "Make protected" dialog (RFC 0051 H3, ADR 0434). A private repository is made protected with
// its first release, as it is made public: the same label and notes. A public one stays as it is,
// with no release, and leaves Discover. No summary and no terms line are asked: nothing says what a
// protected repository is to anybody who does not hold it.

export function makeProtectedTitle(name: string): string {
  return `Make ${name} protected`;
}

export const MAKE_PROTECTED_CONFIRM_PRIVATE = 'Make protected and publish release';
export const MAKE_PROTECTED_CONFIRM_PUBLIC = 'Make protected';

export function makeProtectedConfirm(visibility: Visibility): string {
  return visibility === 'public' ? MAKE_PROTECTED_CONFIRM_PUBLIC : MAKE_PROTECTED_CONFIRM_PRIVATE;
}

export const MAKE_PROTECTED_DONE = 'Protected. A release was published.';
export const MADE_PROTECTED_FROM_PUBLIC = 'Protected. It is off Discover.';

// What will happen, in order.
export function makeProtectedLines(
  check: Pick<FlipCheckOut, 'visibility' | 'invited_libraries' | 'public_libraries'>,
  name: string,
): string[] {
  const lines =
    check.visibility === 'public'
      ? [
          `${name} leaves Discover, and nobody who is not invited can open its page, find it or copy it on its own. It is still read from its releases.`,
          'A library that holds a public repository built on it keeps reading it through that repository. A library that copied it by itself keeps what it copied.',
        ]
      : [
          `Making ${name} protected publishes a release of it, with the label and notes below. It is not on Discover, nobody finds it, and nobody copies it on its own.`,
          'A library that copies a public repository built on it gets it with that repository, and keeps reading it for as long as it holds one. Repositories you invite can be built on it, as before.',
          'A protected repository is read from its releases: what you edit between two releases is not seen by a library until you publish the next one.',
        ];

  if (check.visibility !== 'public' && check.invited_libraries > 0) {
    lines.push(
      `${libraries(check.invited_libraries)} ${check.invited_libraries === 1 ? 'has' : 'have'} an invitation and ${check.invited_libraries === 1 ? 'is' : 'are'} told when you publish.`,
    );
  }

  return lines;
}

export function makeProtectedWarnings(): string[] {
  return [
    'The text of an entry is copied along with it, and that includes text marked GM only: whoever copies a public repository built on this one gets it, and the Owners and Organizers of their library can read it. Players never see it. Mark what you want to keep back as GM only, or take it out, before you make it protected.',
    'Libraries that copy it keep their copies, whatever you do to this repository later.',
  ];
}

// What an Owner says they understand when libraries that copied it by themselves would lose its
// updates: only asked of a public repository that has any.
export function protectedAcknowledgement(
  check: Pick<FlipCheckOut, 'visibility' | 'public_libraries'>,
): string | null {
  if (check.visibility !== 'public' || check.public_libraries === 0) return null;

  const copied = check.public_libraries;

  return `I understand that ${libraries(copied)} will get the updates of this repository only through a public repository built on it that ${copied === 1 ? 'it holds' : 'they hold'}, and keep what ${copied === 1 ? 'it' : 'they'} copied.`;
}

// Why the form cannot be sent yet, or null: what a release asks (for a private repository), then the
// acknowledgement where there are libraries to tell.
export function makeProtectedProblem(
  form: ComposerForm,
  hits: readonly unknown[],
  check: Pick<FlipCheckOut, 'visibility' | 'public_libraries'>,
  acknowledged: boolean,
): string | null {
  if (check.visibility === 'public') {
    return protectedAcknowledgement(check) !== null && !acknowledged
      ? 'Libraries lose its updates alone. Say you understand, to make it protected.'
      : null;
  }

  return composerProblem(form, hits);
}

// The body of `PUT .../protected`: a release as a publish sends it, and the acknowledgement.
export function makeProtectedBody(
  form: ComposerForm,
  hits: readonly unknown[],
  check: Pick<FlipCheckOut, 'visibility' | 'public_libraries'>,
  acknowledged: boolean,
): MakeProtectedRequest {
  return {
    // A public repository has its releases already: only the acknowledgement is sent.
    ...(check.visibility === 'public'
      ? { breaking: false, acknowledge_breaking: false }
      : publishBody(form, hits)),
    acknowledge_revokes: protectedAcknowledgement(check) !== null && acknowledged,
  };
}

// The refusals that mean something changed under the dialog: what it says is read again, and the
// dialog stays open with what is true now.
const CHANGED_UNDER_IT = new Set([
  'built-on-not-public',
  'built-on-behind',
  'repository-not-includable',
  'repository-not-showable',
  'public-repositories-built-on-it',
  'public-copies-would-be-cut-off',
  'repository-already-public',
  'repository-already-protected',
  'repository-already-private',
  'repository-delisted',
  'repository-deprecated',
]);

export function changedUnderTheDialog(problemType: string | undefined): boolean {
  return problemType !== undefined && CHANGED_UNDER_IT.has(problemType);
}
