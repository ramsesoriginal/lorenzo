import { describe, expect, it } from 'vitest';
import { DEFAULT_GM_WORDS, gmWords, gmWordsOfBeing } from './gmTitle';

const campaign = (id: string, title = 'GM', plural = 'GMs') => ({
  id,
  gm_title: title,
  gm_title_plural: plural,
});
const seat = (campaign_id: string) => ({ campaign_id });

describe('gmWords', () => {
  it('says GM for no campaign at all', () => {
    expect(gmWords([])).toEqual({ title: 'GM', plural: 'GMs' });
    expect(DEFAULT_GM_WORDS).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it("uses a campaign's own words, as written", () => {
    expect(gmWords([campaign('a', 'Storyteller', 'Storytellers')])).toEqual({
      title: 'Storyteller',
      plural: 'Storytellers',
    });
    expect(gmWords([campaign('a', 'dungeon Master', 'dungeon Masters')]).title).toBe(
      'dungeon Master',
    );
  });

  it('uses them when every campaign involved has the same ones', () => {
    expect(
      gmWords([
        campaign('a', 'Storyteller', 'Storytellers'),
        campaign('b', 'Storyteller', 'Storytellers'),
      ]),
    ).toEqual({ title: 'Storyteller', plural: 'Storytellers' });
  });

  it('says GM when the campaigns disagree, on either word', () => {
    expect(gmWords([campaign('a', 'Storyteller', 'Storytellers'), campaign('b')])).toEqual(
      DEFAULT_GM_WORDS,
    );
    expect(
      gmWords([campaign('a', 'Master', 'Masters'), campaign('b', 'Master', 'Maestri')]),
    ).toEqual(DEFAULT_GM_WORDS);
  });
});

describe('gmWordsOfBeing', () => {
  const campaigns = [
    campaign('a', 'Narrator', 'Narrators'),
    campaign('b', 'Narrator', 'Narrators'),
    campaign('c'),
  ];

  it('says GM for a being that is no character, or in no campaign', () => {
    expect(gmWordsOfBeing(null, campaigns)).toEqual(DEFAULT_GM_WORDS);
    expect(gmWordsOfBeing({ players: [] }, campaigns)).toEqual(DEFAULT_GM_WORDS);
  });

  it('reads the words of the campaign a character plays in', () => {
    expect(gmWordsOfBeing({ players: [seat('a')] }, campaigns)).toEqual({
      title: 'Narrator',
      plural: 'Narrators',
    });
  });

  it('reads the shared words of two campaigns that agree, and counts a campaign once', () => {
    expect(gmWordsOfBeing({ players: [seat('a'), seat('b'), seat('a')] }, campaigns)).toEqual({
      title: 'Narrator',
      plural: 'Narrators',
    });
  });

  it('says GM for a character in two campaigns that name theirs differently', () => {
    expect(gmWordsOfBeing({ players: [seat('a'), seat('c')] }, campaigns)).toEqual(
      DEFAULT_GM_WORDS,
    );
  });

  it("says GM when a campaign it plays in isn't one the viewer can list", () => {
    expect(gmWordsOfBeing({ players: [seat('a'), seat('secret')] }, campaigns)).toEqual(
      DEFAULT_GM_WORDS,
    );
  });
});
