import { describe, expect, it } from 'vitest';
import {
  contentsDone,
  contentsQuestion,
  keptNote,
  nothingToGive,
  withContentsDone,
  withContentsQuestion,
} from './givingContents';
import type { ContentsResult } from './types';

function given(title: string): ContentsResult {
  return { entity_id: title, title, status: 'ok', owner: { id: 'brisk', name: 'Brisk' } };
}

function kept(title: string, owner: string | null): ContentsResult {
  return {
    entity_id: title,
    title,
    status: 'kept',
    owner: owner ? { id: owner, name: owner } : null,
    problem: { type: 'item-not-yours-to-give', title: 'Forbidden', status: 403 },
  };
}

describe('keptNote', () => {
  it('says nothing when everything goes', () => {
    expect(keptNote([given('Rope')])).toBeNull();
  });

  it('says whose a kept thing stays', () => {
    expect(keptNote([given('Rope'), kept('Potion', 'Pia')])).toBe("1 thing inside stays Pia's.");
    expect(keptNote([kept('Potion', 'Pia'), kept('Ring', 'Pia')])).toBe(
      "2 things inside stay Pia's.",
    );
  });

  it('counts by owner when there are several', () => {
    expect(keptNote([kept('Potion', 'Pia'), kept('Ring', 'Pia'), kept('Map', 'Oskar')])).toBe(
      "3 things inside stay with their owners: 2 are Pia's, 1 is Oskar's.",
    );
  });

  it('names no one for something no one owns', () => {
    expect(keptNote([kept('Gem', null)])).toBe("1 thing inside stays no one's.");
  });
});

describe('withContentsQuestion', () => {
  it('asks about what goes along and what stays', () => {
    expect(
      withContentsQuestion('Backpack', 'Brisk', [
        given('Rope'),
        given('Coin'),
        given('Map'),
        kept('Potion', 'Pia'),
      ]),
    ).toBe("Give the Backpack and 3 things inside it to Brisk? 1 thing inside stays Pia's.");
  });

  it('says when nothing inside can go along', () => {
    expect(withContentsQuestion('Backpack', 'Brisk', [kept('Potion', 'Pia')])).toBe(
      "Give the Backpack to Brisk? Nothing inside it can go along. 1 thing inside stays Pia's.",
    );
  });

  it("doesn't ask when there's nothing inside to ask about", () => {
    expect(withContentsQuestion('Backpack', 'Brisk', [])).toBeNull();
  });
});

describe('withContentsDone', () => {
  it('says what went along', () => {
    expect(withContentsDone('Brisk', [given('Rope')])).toBe('Given to Brisk, with 1 thing inside.');
    expect(withContentsDone('Brisk', [])).toBe('Given to Brisk.');
  });
});

describe('contentsQuestion', () => {
  it('asks about what goes', () => {
    expect(contentsQuestion('Backpack', 'Brisk', [given('Rope'), kept('Potion', 'Pia')])).toBe(
      "Give 1 thing inside the Backpack to Brisk? 1 thing inside stays Pia's.",
    );
  });

  it("doesn't ask when nothing can go", () => {
    expect(contentsQuestion('Backpack', 'Brisk', [kept('Potion', 'Pia')])).toBeNull();
  });
});

describe('nothingToGive', () => {
  it("says there's nothing inside", () => {
    expect(nothingToGive('Backpack', 'Brisk', [])).toBe(
      "There's nothing inside the Backpack to give to Brisk.",
    );
  });

  it('says whose what is inside is', () => {
    expect(nothingToGive('Backpack', 'Brisk', [kept('Potion', 'Pia')])).toBe(
      "Nothing inside the Backpack can be given. 1 thing inside stays Pia's.",
    );
  });
});

describe('contentsDone', () => {
  it('says what went', () => {
    expect(contentsDone('Backpack', 'Brisk', [given('Rope'), given('Coin')])).toBe(
      'Gave 2 things inside the Backpack to Brisk.',
    );
  });
});
