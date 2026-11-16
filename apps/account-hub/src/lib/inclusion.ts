// What Studio says about how a repository carries one it is built on, and about what repositories built
// on it may do with it (RFC 0051 H1, ADR 0431), as plain functions over what the API returns: the
// words of the choice, what each choice does, why one is not offered, the note on changing it, the
// terms card, the lines of a storefront that includes something, and the lines of a release that
// would be breaking because of it. No DOM and nothing but ./types and ./discover, so they run under
// Node in the unit tests.
//
// The words are those of the RFC's table and identity.md §14.3: library, repository, release, Owner,
// entry, copy, update, "built on". The screens never say tenant, grant, subscription, flatten or
// source.

import { licenceLine, NO_LICENCE } from './discover';
import type {
  BuiltOnSourceOut,
  IncludableOut,
  IncludedSourceOut,
  InclusionChangeOut,
  InclusionOut,
  SubscriptionOut,
  TermsOut,
} from './types';

// The three ways a repository carries one it is built on (RFC 0051, ADR 0431, ADR 0437). The API names the
// value as an extensible enum, so a word added later reads as null here and never as a guess.
export type Inclusion = 'show' | 'include' | 'hide';

export function asInclusion(value: string | null | undefined): Inclusion | null {
  return value === 'show' || value === 'include' || value === 'hide' ? value : null;
}

// ---------------------------------------------------------------------------------------------
// The choice, for each repository a repository is built on.

export const INCLUSION_LEGEND = 'How is it carried in this repository?';

export const INCLUSION_LABEL: Record<Inclusion, string> = {
  show: 'Keep separate and visible',
  include: 'Include in this repository',
  hide: 'Keep separate and hidden',
};

export const INCLUSION_CHOICES: readonly Inclusion[] = ['show', 'hide', 'include'];

// The choices to offer: "Include in this repository" only where the user may include it. What is already
// chosen stays offered, so that it shows as chosen even where it could not be chosen again.
export function offeredChoices(
  includable: Pick<IncludableOut, 'allowed'> | null | undefined,
  current: Inclusion,
  showable?: Pick<IncludableOut, 'allowed'> | null,
  hidable?: Pick<IncludableOut, 'allowed'> | null,
): Inclusion[] {
  return INCLUSION_CHOICES.filter((choice) => {
    if (choice === current) return true;
    if (choice === 'include') return includable?.allowed === true;
    // `hide` is offered where the API says it may be (RFC 0051 H4, ADR 0437): a reply that says nothing
    // of it is an older one, and offers what it knows.
    if (choice === 'hide') return hidable?.allowed === true;

    // `show` is offered unless the repository's terms forbid it (RFC 0051 H3, ADR 0434).
    return showable?.allowed !== false;
  });
}

// What each choice does, said before it is chosen: for a library that copies this repository, and for
// this repository's own Owner. `isPublic` is for what hiding means of a repository anyone can copy.
export function inclusionEffect(
  choice: Inclusion,
  name: string,
  isProtected = false,
  isPublic = false,
): string {
  if (choice === 'include') {
    return `The entries of ${name} become this repository’s own when you publish a release. A library that copies this repository does not need ${name} and never reads it. Your copy of ${name} here is not changed, and you keep taking its updates.`;
  }

  if (choice === 'hide') {
    return `${name} stays a repository of its own, and a library that copies this repository holds its entries and does not see them: they are not listed, searched or opened, and the entries of this repository still inherit from them. ${
      isPublic
        ? 'Anyone can copy it, so hiding it only tidies the libraries that copy this repository.'
        : 'It is a way to tidy, not a secret: what they give this repository’s entries reaches the library as values.'
    }`;
  }

  return isProtected
    ? `${name} stays a protected repository of its own. A library that copies this repository gets it with this one, and keeps reading it only for as long as it holds this repository or another public repository built on it.`
    : `${name} stays a repository of its own. A library that copies this repository is given ${name} too, so it has to be one the library can read.`;
}

// Why "Include in this repository" is not offered, or null where it is. Only the Owner of a repository
// can say yes to it being included elsewhere: an Owner of it, or the choice it made for repositories
// built on it.
export function notOfferedReason(
  name: string,
  includable: Pick<IncludableOut, 'allowed'> | null | undefined,
): string | null {
  if (includable?.allowed !== false) return null;

  return `You cannot include ${name} here: its Owner has not allowed repositories built on it to include it, and you are not one of its Owners. Ask its Owner to turn on “${TERMS_INCLUDE_LABEL}”, or keep it separate.`;
}

// Why "Keep separate and visible" is not offered, or null where it is: the Owner of a protected repository
// can ask that what is built on it does not show it (RFC 0051 H3, ADR 0434), and then only include is
// left, unless this user is one of its Owners.
export function notShowableReason(
  name: string,
  showable: Pick<IncludableOut, 'allowed'> | null | undefined,
): string | null {
  if (showable?.allowed !== false) return null;

  return `You cannot keep ${name} separate and visible here: its Owner has asked that what is built on it does not show it. Include it in this repository instead, or ask its Owner.`;
}

// Why "Keep separate and hidden" is not offered, or null where it is: the Owner of a protected repository
// can ask that what is built on it is not hidden (RFC 0051 H4, ADR 0437), and then it is kept visible or
// included, unless this user is one of its Owners.
export function notHidableReason(
  name: string,
  hidable: Pick<IncludableOut, 'allowed'> | null | undefined,
): string | null {
  if (hidable?.allowed !== false) return null;

  return `You cannot keep ${name} separate and hidden here: its Owner has asked that what is built on it is not hidden. Keep it separate and visible instead, or ask its Owner.`;
}

// After the repository's first public release a choice made again makes the next release breaking: the
// rows libraries hold change where they come from. Said beside the choice once a release carried it.
export const BREAKING_NOTE = 'Changing how this is included makes a breaking release.';

export function breakingNote(
  row: Partial<Pick<SubscriptionOut, 'inclusion_in_release'>> &
    Partial<Pick<BuiltOnSourceOut, 'in_release'>>,
): string | null {
  const carried = row.inclusion_in_release ?? row.in_release;

  return carried === null || carried === undefined ? null : BREAKING_NOTE;
}

// What is said once a choice was changed: whether the next release is breaking for it.
export function inclusionSaved(answer: InclusionOut): string {
  return answer.breaking_next_release
    ? `Saved. ${BREAKING_NOTE} You will be asked to acknowledge it when you publish.`
    : 'Saved.';
}

// ---------------------------------------------------------------------------------------------
// A repository's terms: what repositories built on it may do with it.

export const TERMS_HEADING = 'How repositories built on this one may use it';
export const TERMS_INTRO =
  'You decide whether a repository built on this one may carry it in its own release, and whether it may keep it separate, visible or hidden. Nobody else can say yes for you.';
export const TERMS_INCLUDE_LABEL = 'May be included';
export const TERMS_INCLUDE_HELP =
  'A repository built on this one may include it: its entries become that repository’s own, and a library that copies that repository never reads this one.';

// What the switch says now, from what the API reports, in a sentence under it: who chose, and what
// it follows when nobody did.
export function termsLine(
  terms: Pick<TermsOut, 'may_be_included' | 'is_default'>,
  visibility?: string,
): string {
  if (!terms.is_default) {
    return terms.may_be_included
      ? 'You allowed it. Repositories built on this one may include it.'
      : 'You did not allow it. Only an Owner of this repository can include it in another.';
  }

  if (visibility === 'protected' && terms.may_be_included) {
    return 'Nobody chose: a protected repository may be included. Turn the switch off to say otherwise.';
  }

  return terms.may_be_included
    ? 'Nobody chose: a public repository may be included, since anyone can copy it. Turn the switch off to say otherwise.'
    : 'Nobody chose: a private repository may not be included, except by its own Owners. Turn the switch on to allow it.';
}

export function termsPatch(on: boolean): { terms: { may_be_included: boolean } } {
  return { terms: { may_be_included: on } };
}

export const TERMS_SHOWN_LABEL = 'May be shown';
export const TERMS_SHOWN_HELP =
  'A repository built on this one may keep it separate and visible: a library that copies that repository reads the entries of this one as a repository of its own.';
// Only a protected repository can ask that what is built on it does not show it: a public one is
// copied by anybody, and a private one is read by the people its Owner invites (ADR 0434).
export const TERMS_SHOWN_ONLY_PROTECTED =
  'Only a protected repository can say no to this. Make it protected first.';

export function termsShownLine(
  terms: Pick<TermsOut, 'may_be_shown' | 'may_be_shown_is_default'>,
  visibility: string,
): string {
  if (visibility !== 'protected') return TERMS_SHOWN_ONLY_PROTECTED;
  if (terms.may_be_shown_is_default) {
    return 'Nobody chose: a protected repository may be shown. Turn the switch off, or choose “Stay hidden”, to say otherwise.';
  }

  return terms.may_be_shown
    ? 'You allowed it. Repositories built on this one may keep it separate and visible.'
    : 'You did not allow it. Repositories built on this one can include it, and only its Owners can keep it separate and visible.';
}

export function termsShownPatch(on: boolean): { terms: { may_be_shown: boolean } } {
  return { terms: { may_be_shown: on } };
}

export const TERMS_HIDDEN_LABEL = 'May be hidden';
export const TERMS_HIDDEN_HELP =
  'A repository built on this one may keep it separate and hidden: a library that copies that repository holds the entries of this one and does not see them, and the entries of that repository still inherit from them.';

export function termsHiddenLine(
  terms: Pick<TermsOut, 'may_be_hidden' | 'may_be_hidden_is_default'>,
  visibility: string,
): string {
  if (visibility !== 'protected') return TERMS_SHOWN_ONLY_PROTECTED;
  if (terms.may_be_hidden_is_default) {
    return 'Nobody chose: a protected repository may be hidden. Turn the switch off to say otherwise.';
  }

  return terms.may_be_hidden
    ? 'You allowed it. Repositories built on this one may keep it separate and hidden.'
    : 'You did not allow it. Repositories built on this one can show it or include it, and only its Owners can keep it separate and hidden.';
}

export function termsHiddenPatch(on: boolean): { terms: { may_be_hidden: boolean } } {
  return { terms: { may_be_hidden: on } };
}

// The two presets of the screen (RFC 0051): `Open` lets a repository built on this one carry it any way
// it has, `Stay hidden` leaves only include. The switches under them say each one.
export type TermsPreset = 'open' | 'stay-hidden';

export const TERMS_PRESETS: readonly { id: TermsPreset; label: string; help: string }[] = [
  {
    id: 'open',
    label: 'Open',
    help: 'Repositories built on this one may include it, or keep it separate, visible or hidden.',
  },
  {
    id: 'stay-hidden',
    label: 'Stay hidden',
    help: 'Repositories built on this one may include it or keep it separate and hidden, and may not show it.',
  },
];

export const TERMS_PRESET_LEGEND = 'Start from';

// What a preset sets: both switches, so that it is the same whatever was said before.
export function presetPatch(preset: TermsPreset): {
  terms: { may_be_included: boolean; may_be_shown: boolean; may_be_hidden: boolean };
} {
  return {
    terms: { may_be_included: true, may_be_shown: preset === 'open', may_be_hidden: true },
  };
}

// Which preset the switches say, or none where they say something else.
export function presetOf(
  terms: Pick<TermsOut, 'may_be_included' | 'may_be_shown' | 'may_be_hidden'>,
  visibility: string,
): TermsPreset | null {
  if (!terms.may_be_included || !terms.may_be_hidden) return null;
  if (terms.may_be_shown) return 'open';

  return visibility === 'protected' ? 'stay-hidden' : null;
}

export const TERMS_SAVING = 'Saving…';
export const TERMS_SAVED = 'Saved.';

// ---------------------------------------------------------------------------------------------
// What a storefront says of a repository that includes another.

export type IncludesLine = { text: string; name: string; licence: string; url: string | null };

// “Includes content from Armoury, CC BY 4.0”: the name and the licence as they were when the release
// was made, and “no licence stated” where there was none.
export function includesLine(source: IncludedSourceOut): IncludesLine {
  const licence = licenceLine(source.licence);
  const said = licence.text === NO_LICENCE ? 'no licence stated' : licence.text;

  return {
    text: `Includes content from ${source.name}, ${said}`,
    name: source.name,
    licence: said,
    url: licence.url,
  };
}

export function includesLines(sources: readonly IncludedSourceOut[] | undefined): IncludesLine[] {
  return (sources ?? []).map(includesLine);
}

// The same as facts of the profile preview in Studio: the term and the value, with the licence's link.
export function includesFacts(
  sources: readonly IncludedSourceOut[] | undefined,
): { term: string; value: string; url: string | null }[] {
  return includesLines(sources).map((line) => ({
    term: 'Includes content from',
    value: `${line.name}, ${line.licence}`,
    url: line.url,
  }));
}

// ---------------------------------------------------------------------------------------------
// A release that is breaking for how it carries something, in the release composer.

export function inclusionChangeLine(change: Pick<InclusionChangeOut, 'name' | 'before' | 'after'>) {
  if (change.before !== 'include' && change.after !== 'include') {
    return change.after === 'hide'
      ? `“${change.name}” was kept separate and visible in the last public release and is kept separate and hidden now. A library that holds this repository keeps its entries and stops seeing them.`
      : `“${change.name}” was kept separate and hidden in the last public release and is kept separate and visible now. A library that holds this repository sees the entries it did not see.`;
  }

  return change.after === 'include'
    ? `“${change.name}” was kept separate in the last public release and is included now. A library that holds this repository gets its entries as this repository’s own, which changes them there.`
    : `“${change.name}” was included in the last public release and is kept separate now. Its entries leave this repository, and a library that holds it needs ${change.name} as a repository of its own.`;
}

export function inclusionChangeLines(changes: readonly InclusionChangeOut[] | undefined): string[] {
  return (changes ?? []).map(inclusionChangeLine);
}

// The API's refusal of a release lists them in its problem; read what it carries, or nothing.
export function inclusionChangesOf(problem: Record<string, unknown>): InclusionChangeOut[] {
  const changes = problem.inclusion_changes;

  if (!Array.isArray(changes)) return [];

  return changes.filter(
    (change): change is InclusionChangeOut =>
      typeof change === 'object' &&
      change !== null &&
      typeof (change as InclusionChangeOut).name === 'string' &&
      ['show', 'include', 'hide'].includes((change as InclusionChangeOut).after),
  );
}

// ---------------------------------------------------------------------------------------------
// The built-on list of the "Make public" dialog.

export const BUILT_ON_CHOICES_TITLE = 'How this repository carries what it is built on';

// A repository this one is built on, as the dialog offers its choice: what it is, what is chosen, and
// why "Include in this repository" is not offered, where it is not.
export type BuiltOnChoice = {
  id: string;
  name: string;
  state: string;
  // A protected repository: a library reads it as a step of the copy of this one (ADR 0434).
  protected: boolean;
  // A public one: keeping it separate and hidden only tidies the libraries that copy this one.
  public: boolean;
  inclusion: Inclusion;
  offered: readonly Inclusion[];
  notOffered: string | null;
  effect: string;
  note: string | null;
};

export function builtOnChoices(sources: readonly BuiltOnSourceOut[] | undefined): BuiltOnChoice[] {
  return (sources ?? []).map((source) => {
    const inclusion = asInclusion(source.inclusion) ?? 'show';
    const notOffered =
      [
        notOfferedReason(source.name, source.includable),
        notShowableReason(source.name, source.showable),
        notHidableReason(source.name, source.hidable),
      ]
        .filter((reason): reason is string => reason !== null)
        .join(' ') || null;
    const offered = offeredChoices(source.includable, inclusion, source.showable, source.hidable);

    return {
      id: source.id,
      name: source.name,
      state: source.public ? 'Public' : source.protected ? 'Protected' : 'Private',
      protected: source.protected === true,
      public: source.public,
      inclusion,
      offered,
      notOffered,
      effect: inclusionEffect(inclusion, source.name, source.protected === true, source.public),
      note: breakingNote(source),
    };
  });
}
