// What Studio's publish dialog says before it does anything (RFC 0036 §4, ADR 0206), as plain
// functions over what the API returns. No DOM and nothing but ./types, so they run under Node in
// the unit tests. The words are those of identity.md §14.3. Every sentence is true of the API as it
// is: publishing tells the members of every library with an invitation (ADR 0118), reads are live
// (ADR 0183), a copy needs every repository this one is built on to be published and offered to
// the library (ADR 0120), GM-only text travels with a copy (ADR 0119), and unpublishing sends
// nothing and leaves every copy where it is.

import type { SubscriberOut, SubscriptionOut } from './types';

export type PublishMode = 'publish' | 'announce' | 'unpublish';

// A repository this one is built on, and what stands in the way of copying this one because of it.
export type BuiltOnFact = { name: string; published: boolean };

export type PublishFacts = {
  // Libraries with an invitation: the ones a publish tells.
  invited: number;
  // Of every library that holds a copy, with or without an invitation.
  copied: number;
  builtOn: BuiltOnFact[];
};

// What is known before a publish, from the repository's subscribers and the repositories it copies.
export function publishFacts(
  subscribers: readonly SubscriberOut[],
  copiedFrom: readonly SubscriptionOut[],
): PublishFacts {
  return {
    invited: subscribers.filter((s) => s.granted_at !== null).length,
    copied: subscribers.filter((s) => s.copied_at !== null).length,
    builtOn: copiedFrom
      .filter((s) => s.copied_at !== null)
      .map((s) => ({ name: s.repository.name, published: s.repository.published_at !== null }))
      .sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' })),
  };
}

function libraries(count: number): string {
  return count === 1 ? '1 library' : `${count} libraries`;
}

export type DialogContent = {
  title: string;
  // What will happen, in order.
  lines: string[];
  // What to look at first: each is something that would make a copy fail or surprise someone.
  warnings: string[];
  confirm: string;
  // Whether the choice cannot be taken back as it stands (it can be undone by the opposite act, but
  // not unsent).
  careful: boolean;
};

export const GM_ONLY_LINE =
  'Notes marked GM only are copied along with everything else, and stay GM only: players never see them.';

export const LIVE_LINE =
  'A library reads this repository as it is, not as it was when you published: edits you make later are what it sees when it next checks for updates.';

function toldLine(invited: number, verb: string): string {
  return invited === 0
    ? `No library is invited to it yet, so nobody is told. You can invite one in Libraries using it.`
    : `${libraries(invited)} ${invited === 1 ? 'has' : 'have'} an invitation and ${invited === 1 ? 'is' : 'are'} told when you ${verb}: each one's Owners and Organizers get a notification.`;
}

// Why a copy of this repository would be refused, for each repository it is built on.
function builtOnWarnings(builtOn: readonly BuiltOnFact[]): string[] {
  const warnings = builtOn
    .filter((fact) => !fact.published)
    .map(
      (fact) =>
        `${fact.name} is not published. A copy of this repository is refused until it is, since a copy brings what it is built on.`,
    );

  if (builtOn.length > 0) {
    warnings.push(
      `This repository is built on ${builtOn.map((fact) => fact.name).join(', ')}. A library needs an invitation to each of them as well to copy this one: invitations are not passed on.`,
    );
  }

  return warnings;
}

// The dialog for each of the three things an Owner can do.
export function dialogFor(mode: PublishMode, name: string, facts: PublishFacts): DialogContent {
  switch (mode) {
    case 'publish':
      return {
        title: `Publish ${name}`,
        lines: [
          toldLine(facts.invited, 'publish'),
          'Once it is published, the libraries invited to it can look inside it, copy it and take its updates.',
          LIVE_LINE,
          GM_ONLY_LINE,
        ],
        warnings: builtOnWarnings(facts.builtOn),
        confirm: facts.invited === 0 ? 'Publish' : `Publish and tell ${libraries(facts.invited)}`,
        careful: facts.invited > 0,
      };
    case 'announce':
      return {
        title: `Tell libraries about an update to ${name}`,
        lines: [
          toldLine(facts.invited, 'announce it'),
          'Publishing again changes nothing in what libraries read: they read the repository as it is. It only says "look now".',
          LIVE_LINE,
          GM_ONLY_LINE,
        ],
        warnings: builtOnWarnings(facts.builtOn),
        confirm: facts.invited === 0 ? 'Publish again' : `Tell ${libraries(facts.invited)}`,
        careful: facts.invited > 0,
      };
    case 'unpublish':
      return {
        title: `Unpublish ${name}`,
        lines: [
          'It goes back to a draft.',
          facts.invited === 0
            ? 'No library is invited to it, so nobody loses anything.'
            : `${libraries(facts.invited)} ${facts.invited === 1 ? 'has' : 'have'} an invitation and can no longer look inside it, copy it or check for updates until you publish it again.`,
          facts.copied === 0
            ? 'No library has copied it.'
            : `What ${libraries(facts.copied)} already copied stays with ${facts.copied === 1 ? 'it' : 'them'}, and nothing is deleted.`,
          'Nobody is sent a message about it.',
        ],
        warnings: [],
        confirm: 'Unpublish',
        careful: false,
      };
  }
}

// Only an Owner can publish or unpublish; an Organizer is told so where the buttons would be.
export const OWNER_ONLY_NOTE = 'Only an Owner can publish or unpublish a repository.';
