import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { type RunRow, tableCards } from '../../src/lib/campaigns';
import {
  GM_TITLE_INVALID_MESSAGE,
  GM_WORDS,
  gmTitleFields,
  gmTitlePatch,
  gmWords,
  isGmTitleRefusal,
  readGmTitleFields,
} from '../../src/lib/gmTitle';
import { GM_ONLY_LINE } from '../../src/lib/publishing';

const storyteller = { gm_title: 'Storyteller', gm_title_plural: 'Storytellers' };
const narrator = { gm_title: 'Narrator', gm_title_plural: 'Narrators' };
const plain = { gm_title: 'GM', gm_title_plural: 'GMs' };

describe('gmWords (ADR 0294: the one function that decides)', () => {
  it("is one campaign's own title and plural", () => {
    expect(gmWords([storyteller])).toEqual({ title: 'Storyteller', plural: 'Storytellers' });
    expect(gmWords([plain])).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it('uses the title when every campaign has the same one', () => {
    expect(gmWords([storyteller, { ...storyteller }, storyteller])).toEqual({
      title: 'Storyteller',
      plural: 'Storytellers',
    });
  });

  it('says GM and GMs when the campaigns differ', () => {
    expect(gmWords([storyteller, narrator])).toEqual(GM_WORDS);
    expect(gmWords([storyteller, plain])).toEqual(GM_WORDS);
    expect(gmWords([plain, storyteller])).toEqual(GM_WORDS);
  });

  it('says GM and GMs when only the plural differs, since the pair is what is shared', () => {
    expect(gmWords([storyteller, { gm_title: 'Storyteller', gm_title_plural: 'Tellers' }])).toEqual(
      GM_WORDS,
    );
  });

  it('says GM and GMs with no campaign in play', () => {
    expect(gmWords([])).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it('never changes the case of what a table wrote', () => {
    expect(gmWords([{ gm_title: 'DM', gm_title_plural: 'DMs' }]).title).toBe('DM');
    expect(gmWords([{ gm_title: 'the Narrator', gm_title_plural: 'Narrators' }]).title).toBe(
      'the Narrator',
    );
  });
});

describe('the settings field', () => {
  it('shows a title equal to the default as the unset state', () => {
    expect(gmTitleFields(plain)).toEqual({ title: '', plural: '' });
    expect(gmTitleFields(storyteller)).toEqual({ title: 'Storyteller', plural: 'Storytellers' });
  });

  it('sends nothing when the boxes say what the campaign already has', () => {
    expect(gmTitlePatch(plain, { title: '', plural: '' })).toBeNull();
    expect(gmTitlePatch(plain, { title: '  ', plural: '' })).toBeNull();
    expect(gmTitlePatch(storyteller, { title: 'Storyteller', plural: 'Storytellers' })).toBeNull();
  });

  it('sends both texts, trimmed, when the table names its game master', () => {
    expect(gmTitlePatch(plain, { title: ' Storyteller ', plural: 'Storytellers' })).toEqual({
      gm_title: 'Storyteller',
      gm_title_plural: 'Storytellers',
    });
    expect(gmTitlePatch(storyteller, { title: 'Narrator', plural: 'Narrators' })).toEqual({
      gm_title: 'Narrator',
      gm_title_plural: 'Narrators',
    });
  });

  it('sends both empty to go back to the default, also when the default is typed out', () => {
    expect(gmTitlePatch(storyteller, { title: '', plural: '' })).toEqual({
      gm_title: '',
      gm_title_plural: '',
    });
    expect(gmTitlePatch(storyteller, { title: 'GM', plural: 'GMs' })).toEqual({
      gm_title: '',
      gm_title_plural: '',
    });
    expect(gmTitlePatch(plain, { title: 'GM', plural: 'GMs' })).toBeNull();
  });

  it('refuses one without the other, and more than 30 characters, in the words the field uses', () => {
    const refusal = { error: GM_TITLE_INVALID_MESSAGE };

    expect(gmTitlePatch(plain, { title: 'Storyteller', plural: '' })).toEqual(refusal);
    expect(gmTitlePatch(plain, { title: '', plural: 'Storytellers' })).toEqual(refusal);
    expect(readGmTitleFields({ title: 'x'.repeat(31), plural: 'y' })).toEqual(refusal);
    expect(readGmTitleFields({ title: 'x'.repeat(30), plural: 'y'.repeat(30) })).toEqual({
      title: 'x'.repeat(30),
      plural: 'y'.repeat(30),
    });
    expect(GM_TITLE_INVALID_MESSAGE).toBe(
      'Give both, as plain text of at most 30 characters: letters, numbers, spaces and the punctuation of a name.',
    );
  });

  it('counts characters as the API does, not UTF-16 units', () => {
    // 30 astral characters are 60 units but 30 characters.
    const thirty = '𝔸'.repeat(30);

    expect(readGmTitleFields({ title: thirty, plural: thirty })).toEqual({
      title: thirty,
      plural: thirty,
    });
  });

  it("knows the API's refusal by its problem type", () => {
    expect(isGmTitleRefusal('campaign-gm-title-invalid')).toBe(true);
    expect(isGmTitleRefusal('something-else')).toBe(false);
    expect(isGmTitleRefusal(undefined)).toBe(false);
  });
});

describe('the cards of the home page', () => {
  const row = (name: string, gm: { title: string; plural: string }): RunRow => ({
    tenantId: 't',
    tenantName: 'Realms',
    tenantSlug: 'realms',
    campaignId: `c-${name}`,
    campaignName: name,
    role: 'gm',
    gm,
  });

  it("show a campaign's own title for the game master among its roles", () => {
    const cards = tableCards({
      seats: [],
      rows: [
        row('Hood', { title: 'Storyteller', plural: 'Storytellers' }),
        row('Open', { title: 'GM', plural: 'GMs' }),
      ],
      libraries: new Map(),
      campaigns: new Map(),
    });

    expect(cards.map((card) => [card.name, card.roles])).toEqual([
      ['Hood', ['Storyteller']],
      ['Open', ['GM']],
    ]);
  });
});

// A campaign's surface has no literal GM in it (ADR 0294): what it says comes from the campaign.
// What a text does not say through the title is read in the source here, with its comments taken out,
// since a test cannot paint the page; the sentences built in lib/ are held to it where they are tested.
function readSource(path: string): string {
  return readFileSync(new URL(`../../src/${path}`, import.meta.url), 'utf8')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/\s\/\/\s.*$/gm, '');
}

const LITERAL = /\bGMs?\b/;

describe("a campaign's surface says no literal GM", () => {
  const surfaces = [
    'components/GmManagement/GmManagement.astro',
    'components/GmManagement/renderer.ts',
    'components/RunCampaign/RunCampaign.astro',
    'components/RunCampaign/renderer.ts',
    'components/InviteLinks/InviteLinks.astro',
    'components/InviteLinks/renderer.ts',
    'components/CampaignRoster/CampaignRoster.astro',
    'components/CampaignRoster/renderer.ts',
    'components/Tenant/Tenant.astro',
    'components/Tenant/library.ts',
    'components/Tenant/stepDownAsGm.ts',
    'components/DeleteAccount/DeleteAccount.astro',
    'components/DeleteAccount/renderer.ts',
    'components/Briefing/tables.ts',
    'components/CampaignsPanel/renderer.ts',
    'lib/campaigns.ts',
  ];

  for (const path of surfaces) {
    it(path, () => {
      expect(readSource(path)).not.toMatch(LITERAL);
    });
  }

  it("keeps the settings field's own words, which explain the title and the role", () => {
    const form = readSource('components/CampaignForm/CampaignForm.astro');

    expect(form).toContain('What does your table call its game master?');
    expect(form).toContain('placeholder="GM"');
    expect(form).toContain('placeholder="GMs"');
    expect(form).toContain(
      'Shown wherever this campaign appears. It does not change what a GM may do.',
    );
    expect(form).toContain('maxlength="30"');
  });
});

describe('what has no one campaign still says GM', () => {
  it('a repository and a copy say GM only', () => {
    expect(GM_ONLY_LINE).toContain('GM only');
    expect(readSource('lib/copyWizard.ts')).toContain('GM only');
    expect(readSource('lib/showcase.ts')).toContain('GM only');
    expect(readSource('lib/visibility.ts')).toContain('GM only');
  });

  it('a campaign that is not made yet, a stranger to every campaign and the empty page say GM', () => {
    expect(readSource('lib/setup.ts')).toContain('GM');
    expect(readSource('components/NewUser/NewUser.astro')).toMatch(LITERAL);
    expect(readSource('components/BeingsPanel/BeingsPanel.astro')).toMatch(LITERAL);
    expect(readSource('components/Setup/Setup.astro')).toMatch(LITERAL);
  });
});
