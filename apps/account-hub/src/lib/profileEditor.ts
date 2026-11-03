// What Studio's Profile tab says and checks (RFC 0036 §4 T5, RFC 0038 §2, ADR 0385), as plain
// functions over what the API returns: the fields of a repository's profile as a draft, the rules of
// each as the API keeps them, what changed, what a refusal means next to which field, the language
// names, and what the listing will show. No DOM and nothing but ./types, ./visibility, ./discover and
// ./describeError, so they run under Node in the unit tests. The words are those of identity.md
// §14.3: library, repository, release, Owner, entry, copy; never "tenant", "grant" or "subscription".
//
// The rules mirror `schemas/repository_profiles.py` (ADR 0213), so that a screen tells a person what
// the API would only refuse after the request. The API is what decides: whatever it still refuses is
// shown next to the field it names, in its own words (`apiProblems`), and keeps nothing.

import { ApiError } from './apiError';
import { describeError, isSessionExpired } from './describeError';
import { type CardLines, creditLine, languageLabel, licenceLine } from './discover';
import type {
  CreditOut,
  LicenceOut,
  MemberProfileOut,
  RepositoryProfileOut,
  RepositoryProfileUpdate,
} from './types';
import { oneLine, summaryProblem } from './visibility';

// ---------------------------------------------------------------------------------------------
// The limits, as the API sets them (ADR 0213, `schemas/repository_profiles.py`).

export const LICENCE_LABEL_MAX = 80;
export const CREDITS_MAX = 20;
export const CREDIT_NAME_MAX = 80;
export const CREDIT_ROLE_MAX = 60;
export const TAGS_MAX = 12;
export const TAG_MAX = 32;
export const SYSTEM_MAX = 40;
export const LANGUAGES_MAX = 8;
export const URL_MAX = 500;

// ---------------------------------------------------------------------------------------------
// The words of the tab.

export const PROFILE_HEADING = 'Profile';
export const PROFILE_INTRO =
  'What this repository says about itself. People read it on Discover before they copy it.';
export const ONLY_AN_OWNER = 'Only an Owner can change this.';

export const SUMMARY_LABEL = 'Summary';
export const LICENCE_LABEL = 'Licence';
export const LICENCE_NAME_LABEL = 'Name of the licence';
export const LICENCE_LINK_LABEL = 'Link to the licence (optional)';
export const LICENCE_LINK_HELP = 'A web address that starts with https://.';
export const NO_LICENCE_CHOICE = 'No licence stated';
export const NO_LICENCE_HELP =
  '"No licence stated" is not a licence. It says nothing about what people may do with what they copy.';
export const OTHER_LICENCE_CHOICE = 'Other…';
export const CREDITS_LABEL = 'Credits';
export const CREDITS_HELP = `Who made it: a name, what they did, and a link if you want one. Up to ${CREDITS_MAX} credits. This is not who published it: that is shown from the accounts of the Owners.`;
export const TAGS_LABEL = 'Tags';
export const TAGS_HELP = `Words people can search for. Up to ${TAGS_MAX} tags of at most ${TAG_MAX} characters, in lower case and without repeats. Press Enter to add one.`;
export const SYSTEM_LABEL = 'Game system';
export const SYSTEM_HELP = `The game this is for, as people know it (at most ${SYSTEM_MAX} characters).`;
export const LANGUAGES_LABEL = 'Languages';
export const LANGUAGES_HELP = `The languages it is written in, as language codes such as en, de or pt-br. Up to ${LANGUAGES_MAX}. Press Enter to add one.`;

export const SAVE_LABEL = 'Save';
export const REVERT_LABEL = 'Revert';
export const SAVING = 'Saving…';
export const SAVED = 'Saved.';
export const UNSAVED = 'You have unsaved changes.';
export const NOTHING_CHANGED = 'Nothing has changed.';
export const LEAVE_UNSAVED = 'You have unsaved changes to the profile. Leave without saving them?';

export const PREVIEW_HEADING = 'What people will see';
export const PREVIEW_INTRO =
  'This is how Discover shows it in the list, and what its own page says of it, with what you have written here. The release and its size are added once it is public.';

// ---------------------------------------------------------------------------------------------
// The text rules, as the API keeps them.

// Whitespace runs, newlines included, become one space, and the ends are dropped (`_words`).
function words(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(' ');
}

const NOT_PRINTABLE = /[\p{C}]/u;

// Why a one-line field cannot be kept, or null: nothing that is not printable.
function plainProblem(text: string): string | null {
  return NOT_PRINTABLE.test(text) ? 'Use plain text, without control characters' : null;
}

function plain(raw: string, limit: number, what: string): string | null {
  const text = words(raw);

  if (text === '') return `${what} can't be empty`;
  if (text.length > limit) return `${what} is at most ${limit} characters`;

  return plainProblem(text);
}

// A link, as `_https` keeps it: https only, with a host, and no name or password in it.
export function linkProblem(raw: string): string | null {
  const text = raw.trim();

  if (text === '') return null;
  if (text.length > URL_MAX) return `A link is at most ${URL_MAX} characters`;
  if (!text.toLowerCase().startsWith('https://')) return 'A link must start with https://';
  if (NOT_PRINTABLE.test(text) || /\s/.test(text)) return "A link can't hold spaces";

  const rest = text.slice('https://'.length);

  if (rest === '' || rest.startsWith('/') || rest.startsWith('?') || rest.startsWith('#')) {
    return 'A link needs a host, as in https://example.com';
  }

  let url: URL;

  try {
    url = new URL(text);
  } catch {
    return "That isn't a web address";
  }

  if (!url.hostname) return 'A link needs a host, as in https://example.com';
  if (url.username !== '' || url.password !== '') {
    return "A link can't hold a user name or a password";
  }

  return null;
}

// The link as it is kept: the scheme in lower case, or null for none.
export function linkOf(raw: string): string | null {
  const text = raw.trim();

  return text === '' ? null : `https://${text.slice('https://'.length)}`;
}

// A tag as it is kept: in lower case, whitespace made single.
export function tagOf(raw: string): string {
  return words(raw).toLowerCase();
}

// A language code as it is kept: trimmed and in lower case.
export function languageCodeOf(raw: string): string {
  return raw.trim().toLowerCase();
}

const LANGUAGE_CODE = /^[a-z]{2,3}(-[a-z0-9]{2,8}){0,2}$/;

export function languageProblem(raw: string): string | null {
  return LANGUAGE_CODE.test(languageCodeOf(raw))
    ? null
    : `'${raw}' isn't a language code such as en, de or pt-br`;
}

// ---------------------------------------------------------------------------------------------
// The licences to choose from. A licence is a name and, optionally, a link to its text; "Other…" is
// a name of the author's own. Nothing here is a value the API refuses.

export type LicenceChoice = { label: string; url: string | null };

export const LICENCES: readonly LicenceChoice[] = [
  { label: 'CC0 1.0', url: 'https://creativecommons.org/publicdomain/zero/1.0/' },
  { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
  { label: 'CC BY-SA 4.0', url: 'https://creativecommons.org/licenses/by-sa/4.0/' },
  { label: 'CC BY-NC 4.0', url: 'https://creativecommons.org/licenses/by-nc/4.0/' },
  { label: 'CC BY-NC-SA 4.0', url: 'https://creativecommons.org/licenses/by-nc-sa/4.0/' },
  { label: 'ORC License', url: null },
  { label: 'OGL 1.0a', url: null },
  { label: 'All rights reserved', url: null },
];

// The value of the licence select for "Other…".
export const OTHER_LICENCE = '__other__';

// What the select shows for a saved licence: the listed one it names, or "Other…".
export function licenceChoiceOf(licence: LicenceOut | null): string {
  if (!licence) return '';

  return LICENCES.some((choice) => choice.label === licence.label) ? licence.label : OTHER_LICENCE;
}

// The usual link of a listed licence, for the link field to start from; null for any other.
export function usualLink(choice: string): string | null {
  return LICENCES.find((licence) => licence.label === choice)?.url ?? null;
}

// ---------------------------------------------------------------------------------------------
// The draft: what the form holds, as text.

export type CreditDraft = { name: string; role: string; url: string };

export type Draft = {
  summary: string;
  // '' for none, a listed licence's name, or OTHER_LICENCE.
  licence: string;
  licenceOther: string;
  licenceUrl: string;
  credits: CreditDraft[];
  tags: string[];
  system: string;
  languages: string[];
};

export function draftOf(profile: RepositoryProfileOut): Draft {
  const choice = licenceChoiceOf(profile.licence);

  return {
    summary: profile.summary,
    licence: choice,
    licenceOther: choice === OTHER_LICENCE ? (profile.licence?.label ?? '') : '',
    licenceUrl: profile.licence?.url ?? '',
    credits: profile.credits.map((credit) => ({
      name: credit.name,
      role: credit.role ?? '',
      url: credit.url ?? '',
    })),
    tags: [...profile.tags],
    system: profile.system ?? '',
    languages: [...profile.languages],
  };
}

// What a draft would keep, as the API would keep it. Two drafts that keep the same are not a change.
export type Kept = {
  summary: string;
  licence: LicenceOut | null;
  credits: CreditOut[];
  tags: string[];
  system: string | null;
  languages: string[];
};

export function licenceOf(draft: Draft): LicenceOut | null {
  if (draft.licence === '') return null;

  const label = draft.licence === OTHER_LICENCE ? words(draft.licenceOther) : draft.licence;

  return { label, url: linkOf(draft.licenceUrl) };
}

function unique(values: readonly string[]): string[] {
  return values.filter((value, index) => values.indexOf(value) === index);
}

export function keptOf(draft: Draft): Kept {
  return {
    summary: oneLine(draft.summary),
    licence: licenceOf(draft),
    credits: draft.credits.map((credit) => ({
      name: words(credit.name),
      role: words(credit.role) || null,
      url: linkOf(credit.url),
    })),
    tags: unique(draft.tags.map(tagOf)),
    system: words(draft.system) || null,
    languages: unique(draft.languages.map(languageCodeOf)),
  };
}

export function savedOf(
  profile: Pick<
    RepositoryProfileOut,
    'summary' | 'licence' | 'credits' | 'tags' | 'system' | 'languages'
  >,
): Kept {
  return {
    summary: profile.summary,
    licence: profile.licence,
    credits: profile.credits.map((credit) => ({
      name: credit.name,
      role: credit.role ?? null,
      url: credit.url ?? null,
    })),
    tags: profile.tags,
    system: profile.system ?? null,
    languages: profile.languages,
  };
}

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// The fields that differ from what is saved, by name.
export function changedFields(
  profile: RepositoryProfileOut,
  draft: Draft,
): (keyof RepositoryProfileUpdate)[] {
  const saved = savedOf(profile);
  const kept = keptOf(draft);
  const changed: (keyof RepositoryProfileUpdate)[] = [];

  if (kept.summary !== saved.summary) changed.push('summary');
  if (!same(kept.licence, saved.licence)) changed.push('licence');
  if (!same(kept.credits, saved.credits)) changed.push('credits');
  if (!same(kept.tags, saved.tags)) changed.push('tags');
  if (kept.system !== saved.system) changed.push('system');
  if (!same(kept.languages, saved.languages)) changed.push('languages');

  return changed;
}

export function isChanged(profile: RepositoryProfileOut, draft: Draft): boolean {
  return changedFields(profile, draft).length > 0;
}

// The body of `PATCH .../profile`: only what changed, as one request. A field left out is unchanged
// (ADR 0213); `null` clears the licence and the game system.
export function patchOf(profile: RepositoryProfileOut, draft: Draft): RepositoryProfileUpdate {
  const kept = keptOf(draft);
  const patch: RepositoryProfileUpdate = {};

  for (const field of changedFields(profile, draft)) {
    if (field === 'summary') patch.summary = kept.summary;
    else if (field === 'licence') {
      patch.licence = kept.licence ? { label: kept.licence.label, url: kept.licence.url } : null;
    } else if (field === 'credits') {
      patch.credits = kept.credits.map((credit) => ({
        name: credit.name,
        role: credit.role,
        url: credit.url,
      }));
    } else if (field === 'tags') patch.tags = kept.tags;
    else if (field === 'system') patch.system = kept.system;
    else if (field === 'languages') patch.languages = kept.languages;
  }

  return patch;
}

// ---------------------------------------------------------------------------------------------
// What is wrong with a draft, next to the field. The keys: `summary`, `licence` (its name),
// `licenceLink`, `credits`, `credit.<n>.name|role|url`, `tags`, `system`, `languages`, and `form` for
// what belongs to none.

export type Problems = Record<string, string>;

export function creditKey(index: number, part: 'name' | 'role' | 'url'): string {
  return `credit.${index}.${part}`;
}

// The first of these is where the cursor goes.
export function problemsOf(draft: Draft): Problems {
  const problems: Problems = {};
  const summary = oneLine(draft.summary);

  // A profile may have no summary: only making it public asks for one.
  if (summary !== '') {
    const problem = summaryProblem(draft.summary);

    if (problem) problems.summary = problem;
  }

  const kept = keptOf(draft);

  if (draft.licence === OTHER_LICENCE && kept.licence) {
    const problem = plain(draft.licenceOther, LICENCE_LABEL_MAX, 'A licence name');

    if (problem) problems.licence = problem;
  }

  if (draft.licence !== '') {
    const problem = linkProblem(draft.licenceUrl);

    if (problem) problems.licenceLink = problem;
  } else if (draft.licenceUrl.trim() !== '') {
    problems.licenceLink = 'Choose a licence for the link, or take the link out.';
  }

  if (draft.credits.length > CREDITS_MAX) problems.credits = `At most ${CREDITS_MAX} credits`;

  draft.credits.forEach((credit, index) => {
    const name = plain(credit.name, CREDIT_NAME_MAX, 'A name');

    if (name) problems[creditKey(index, 'name')] = name;

    if (words(credit.role) !== '') {
      const role = plain(credit.role, CREDIT_ROLE_MAX, 'A role');

      if (role) problems[creditKey(index, 'role')] = role;
    }

    const link = linkProblem(credit.url);

    if (link) problems[creditKey(index, 'url')] = link;
  });

  if (kept.tags.length > TAGS_MAX) problems.tags = `At most ${TAGS_MAX} tags`;
  for (const tag of kept.tags) {
    const problem = tag === '' ? "A tag can't be empty" : plain(tag, TAG_MAX, 'A tag');

    if (problem) problems.tags = problem;
  }

  const system = words(draft.system);

  if (system.length > SYSTEM_MAX) problems.system = `A system is at most ${SYSTEM_MAX} characters`;
  else if (system !== '') {
    const problem = plainProblem(system);

    if (problem) problems.system = problem;
  }

  if (kept.languages.length > LANGUAGES_MAX)
    problems.languages = `At most ${LANGUAGES_MAX} languages`;
  for (const code of draft.languages) {
    const problem = languageProblem(code);

    if (problem) problems.languages = problem;
  }

  return problems;
}

// ---------------------------------------------------------------------------------------------
// Adding to the lists.

export type Added = { list: string[]; problem: string | null };

// A tag typed in: commas separate several. Added in the form the API keeps; a repeat is not added,
// and past the cap or a tag too long is refused, in words.
export function addTags(current: readonly string[], typed: string): Added {
  const list = [...current];

  for (const part of typed.split(',')) {
    const tag = tagOf(part);

    if (tag === '') continue;
    if (tag.length > TAG_MAX) {
      return { list, problem: `A tag is at most ${TAG_MAX} characters` };
    }

    const problem = plainProblem(tag);

    if (problem) return { list, problem };
    if (list.includes(tag)) continue;
    if (list.length >= TAGS_MAX) return { list, problem: `At most ${TAGS_MAX} tags` };

    list.push(tag);
  }

  return { list, problem: null };
}

// A language typed in, as a code: several may be separated by commas.
export function addLanguages(current: readonly string[], typed: string): Added {
  const list = [...current];

  for (const part of typed.split(',')) {
    if (part.trim() === '') continue;

    const problem = languageProblem(part);

    if (problem) return { list, problem };

    const code = languageCodeOf(part);

    if (list.includes(code)) continue;
    if (list.length >= LANGUAGES_MAX)
      return { list, problem: `At most ${LANGUAGES_MAX} languages` };

    list.push(code);
  }

  return { list, problem: null };
}

// "3 of 12", beside a list.
export function capLine(count: number, max: number, noun: string, nouns: string): string {
  return `${count} of ${max} ${max === 1 ? noun : nouns}`;
}

// A credit moved up or down the list, or the same list at either end.
export function moved<T>(list: readonly T[], index: number, by: -1 | 1): T[] {
  const target = index + by;
  const next = [...list];

  if (index < 0 || index >= list.length || target < 0 || target >= list.length) return next;

  const [item] = next.splice(index, 1);

  if (item !== undefined) next.splice(target, 0, item);

  return next;
}

// ---------------------------------------------------------------------------------------------
// The names of the languages, in the reader's own.

// "German (de)" for a code the browser knows, in the language it is asked in; the code itself for
// one it does not.
export function languageName(code: string, locales: string | string[] = 'en'): string {
  return languageLabel(code, locales);
}

// The choices a list of suggestions offers: the ones people use first, then a few common ones, never
// one already chosen.
export const COMMON_LANGUAGES = ['en', 'de', 'fr', 'es', 'it', 'pt-br', 'nl', 'pl', 'ru', 'ja'];

export type Suggestion = { value: string; label: string };

export function suggestLanguages(
  fromDiscover: readonly { value: string }[],
  chosen: readonly string[],
  locales: string | string[] = 'en',
): Suggestion[] {
  const taken = new Set(chosen);

  return unique([...fromDiscover.map((facet) => facet.value), ...COMMON_LANGUAGES])
    .filter((code) => !taken.has(code))
    .map((code) => ({ value: code, label: languageName(code, locales) }));
}

export function suggestValues(
  fromDiscover: readonly { value: string }[],
  chosen: readonly string[],
): string[] {
  const taken = new Set(chosen);

  return unique(fromDiscover.map((facet) => facet.value)).filter((value) => !taken.has(value));
}

// ---------------------------------------------------------------------------------------------
// What the API refused, next to the field it names.

type ErrorEntry = { loc?: unknown; msg?: unknown };

function tidy(message: string): string {
  const text = message.trim().replace(/^Value error,\s*/i, '');

  return text.endsWith('.') ? text.slice(0, -1) : text;
}

// The key of a field from where the API says it is in the request (`['body', 'credits', 1, 'url']`),
// or null for one that is not a field of the profile.
export function keyOfLocation(loc: unknown): string | null {
  if (!Array.isArray(loc)) return null;

  const path = loc.filter((part) => part !== 'body');
  const [field, index, part] = path;

  switch (field) {
    case 'summary':
    case 'system':
    case 'tags':
    case 'languages':
      return field;
    case 'licence':
      return index === 'url' ? 'licenceLink' : 'licence';
    case 'credits':
      if (typeof index === 'number' && (part === 'name' || part === 'role' || part === 'url')) {
        return creditKey(index, part);
      }

      return 'credits';
    default:
      return null;
  }
}

// A refused `PATCH`, read for the screen: the words next to each field it names, and what is left
// over (a 403, a session that ended, a refusal that names no field) as one sentence in `form`.
// Nothing the API said is rewritten; unknown problems are its own detail.
export function apiProblems(error: unknown): Problems {
  const problems: Problems = {};

  if (error instanceof ApiError && error.status === 422 && Array.isArray(error.problem.errors)) {
    for (const entry of error.problem.errors as ErrorEntry[]) {
      if (typeof entry !== 'object' || entry === null || typeof entry.msg !== 'string') continue;

      const key = keyOfLocation(entry.loc);
      const message = tidy(entry.msg);

      if (message === '') continue;
      if (key === null) problems.form ??= message;
      else problems[key] ??= message;
    }

    if (Object.keys(problems).length > 0) return problems;
  }

  problems.form = describeError(error);

  return problems;
}

export function needsLogin(error: unknown): boolean {
  return isSessionExpired(error);
}

// ---------------------------------------------------------------------------------------------
// What the listing will show.

// What Discover's card says of the repository with what is in the draft: its name and summary, its
// tags and the game system; the release and the size are what a public repository adds.
export function previewCard(name: string, draft: Draft): CardLines {
  const kept = keptOf(draft);

  return {
    name,
    summary: kept.summary,
    tags: kept.tags,
    publishedBy: null,
    meta: kept.system ? [kept.system] : [],
  };
}

export type ProfileFact = { term: string; value: string; url?: string | null };

// What a repository's own page says besides the card: the game system and languages, the licence, and
// the credits, each a line.
export function factsOfKept(kept: Kept, locales: string | string[] = 'en'): ProfileFact[] {
  const facts: ProfileFact[] = [];

  if (kept.system) facts.push({ term: 'Game system', value: kept.system });
  if (kept.languages.length > 0) {
    facts.push({
      term: 'Languages',
      value: kept.languages.map((code) => languageName(code, locales)).join(', '),
    });
  }

  const licence = licenceLine(kept.licence?.label ? kept.licence : null);

  facts.push({ term: 'Licence', value: licence.text, url: licence.url });

  for (const credit of kept.credits.filter((entry) => entry.name !== '')) {
    const line = creditLine(credit);

    facts.push({
      term: 'Credit',
      value: line.role ? `${line.name}, ${line.role}` : line.name,
      url: line.url,
    });
  }

  return facts;
}

export function previewFacts(draft: Draft, locales: string | string[] = 'en'): ProfileFact[] {
  return factsOfKept(keptOf(draft), locales);
}

// The same, for a profile that was saved: what a member who cannot change it reads.
export function savedFacts(
  profile: Pick<
    MemberProfileOut,
    'summary' | 'licence' | 'credits' | 'tags' | 'system' | 'languages'
  >,
  locales: string | string[] = 'en',
): ProfileFact[] {
  return factsOfKept(savedOf(profile), locales);
}

// ---------------------------------------------------------------------------------------------
// The cover.

export const COVER_HEADING = 'Cover';
export const COVER_HELP =
  'A wide picture shown at the top of the repository’s page and beside it in the list. It is cropped to a strip about three times as wide as it is high. PNG, JPEG, WebP or GIF, up to 10 MB.';
export const NO_COVER = 'No cover yet.';
export const NO_COVER_INSTEAD =
  'In the list Discover shows the first letter of the repository’s name instead, and its own page shows no picture.';
export const COVER_CHOOSE = 'Choose a picture…';
export const COVER_REPLACE = 'Replace the picture…';
export const COVER_UPLOAD = 'Upload';
export const COVER_CANCEL = 'Cancel';
export const COVER_REMOVE = 'Remove the cover';
export const COVER_STAGED =
  'This is how it will look. Upload it to use it as the cover, or cancel.';
export const COVER_UPLOADING = 'Uploading…';
export const COVER_UPLOADED = 'The cover was updated.';
export const COVER_REMOVING = 'Removing…';
export const COVER_REMOVED = 'The cover was removed.';
export const COVER_REMOVE_CONFIRM =
  'Remove the cover? Discover will show the first letter of the repository’s name instead.';

// ---------------------------------------------------------------------------------------------

// Whether this person may change the profile: the API lets an Owner, and only an Owner (ADR 0213).
export function mayEditProfile(role: string): boolean {
  return role === 'owner';
}
