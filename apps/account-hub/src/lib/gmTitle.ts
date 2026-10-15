// What a campaign calls its game master (ADR 0294), as plain functions. Dependency-free like
// format.ts, so a test can hold the rule to what the ADR says.
//
// The API sends the title with every campaign it sends, always set: the campaign's own, or "GM" and
// "GMs". A surface about ONE campaign says that title. A surface with several campaigns in it, or
// none, goes through `gmWords`, so no surface decides alone. Nothing here is a default a campaign
// could be missing: the pair below is the word of the API for where no one campaign is in play,
// and what the settings screen shows as "unset".

export interface GmTitled {
  gm_title: string;
  gm_title_plural: string;
}

// The two words a text uses: `title` for one, `plural` for several. Spelled as the table wrote them,
// never lower-cased: a text is written so it reads right at the start of a sentence and in the
// middle of one.
export interface GmWords {
  title: string;
  plural: string;
}

export const GM_WORDS: GmWords = { title: 'GM', plural: 'GMs' };

// The words for the campaigns a text is about. One campaign: its own. Several: its own only when
// every one of them has the same pair, otherwise "GM" and "GMs". No campaign (or none known yet):
// "GM" and "GMs", the word the API, the catalog and a repository share.
export function gmWords(campaigns: readonly GmTitled[]): GmWords {
  const [first, ...rest] = campaigns;

  if (first === undefined) return GM_WORDS;

  const same = rest.every(
    (campaign) =>
      campaign.gm_title === first.gm_title && campaign.gm_title_plural === first.gm_title_plural,
  );

  return same ? { title: first.gm_title, plural: first.gm_title_plural } : GM_WORDS;
}

// --- The settings field ----------------------------------------------------------------------

// A title and its plural are 1 to 30 characters each once trimmed (the API's own limit).
export const MAX_GM_TITLE = 30;

export interface GmTitleFields {
  title: string;
  plural: string;
}

// What the two text boxes start as. A title equal to the default is the unset state: the boxes are
// empty and their placeholders say "GM" and "GMs".
export function gmTitleFields(campaign: GmTitled): GmTitleFields {
  const unset =
    campaign.gm_title === GM_WORDS.title && campaign.gm_title_plural === GM_WORDS.plural;

  return unset
    ? { title: '', plural: '' }
    : { title: campaign.gm_title, plural: campaign.gm_title_plural };
}

export const GM_TITLE_INVALID_MESSAGE =
  'Give both, as plain text of at most 30 characters: letters, numbers, spaces and the punctuation of a name.';

// What is typed in the two boxes, trimmed, or the reason it cannot be saved: both or neither, and
// no longer than the API keeps. Anything else that is not plain text is the API's to refuse
// (`campaign-gm-title-invalid`), and is said with the same words.
export function readGmTitleFields(entered: GmTitleFields): GmTitleFields | { error: string } {
  const title = entered.title.trim();
  const plural = entered.plural.trim();

  if ((title === '') !== (plural === '')) return { error: GM_TITLE_INVALID_MESSAGE };
  // Counted as the API counts, in characters and not in UTF-16 units.
  if ([...title].length > MAX_GM_TITLE || [...plural].length > MAX_GM_TITLE) {
    return { error: GM_TITLE_INVALID_MESSAGE };
  }

  // Typing the default is the same as having none: both go back to the default.
  if (title === GM_WORDS.title && plural === GM_WORDS.plural) return { title: '', plural: '' };

  return { title, plural };
}

// The part of a campaign's PATCH that this field makes: nothing when the boxes say what the
// campaign already has, else both texts, empty for "back to the default".
export function gmTitlePatch(
  campaign: GmTitled,
  entered: GmTitleFields,
): { gm_title: string; gm_title_plural: string } | { error: string } | null {
  const read = readGmTitleFields(entered);

  if ('error' in read) return read;

  const current = gmTitleFields(campaign);

  if (read.title === current.title && read.plural === current.plural) return null;

  return { gm_title: read.title, gm_title_plural: read.plural };
}

// A refusal of the API's in words, from its problem type; null for anything else.
export function isGmTitleRefusal(problemType: string | undefined): boolean {
  return problemType === 'campaign-gm-title-invalid';
}
