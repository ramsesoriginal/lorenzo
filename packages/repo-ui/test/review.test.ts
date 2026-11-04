// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DELETED,
  EMPTY,
  type ReviewItem,
  type ReviewSide,
  renderReview,
  reviewWords,
} from '../src';

const name: ReviewItem = {
  id: 'name',
  label: 'Name',
  change: { kind: 'value', was: 'Longsword', theirs: 'Longsword +1', mine: 'My blade' },
  choice: { chosen: null },
};

const terms = (root: HTMLElement) => [...root.querySelectorAll('dt')].map((dt) => dt.textContent);
const values = (root: HTMLElement) => [...root.querySelectorAll('dd')].map((dd) => dd.textContent);
const radios = (root: HTMLElement) => [
  ...root.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
];
const buttons = (root: HTMLElement) => [...root.querySelectorAll<HTMLButtonElement>('button')];
const status = (root: HTMLElement) => root.querySelector('[role="status"]')?.textContent;

beforeEach(() => {
  document.body.replaceChildren();
});

describe('a field', () => {
  it('has its name, and its values stacked in the order Was, Now, Yours', () => {
    const root = renderReview([name]);

    expect(root.querySelector('.repo-review-label')?.textContent).toBe('Name');
    expect(terms(root)).toEqual(['Was', 'Now', 'Yours']);
    expect(values(root)).toEqual(['Longsword', 'Longsword +1', 'My blade']);
  });

  it('has no Yours where the host did not change it, and asks nothing', () => {
    const root = renderReview([
      { id: 'slug', label: 'Link name', change: { kind: 'value', was: 'a', theirs: 'b' } },
    ]);

    expect(terms(root)).toEqual(['Was', 'Now']);
    expect(radios(root)).toHaveLength(0);
    expect(buttons(root)).toHaveLength(0);
    expect(root.querySelector('fieldset')).toBeNull();
  });

  it('says a missing value as No value and a removed one as Deleted, apart from text', () => {
    const root = renderReview([
      { id: 'a', label: 'A', change: { kind: 'value', was: EMPTY, theirs: DELETED, mine: 'x' } },
    ]);
    const cells = [...root.querySelectorAll('dd')];

    expect(values(root)).toEqual(['No value', 'Deleted', 'x']);
    expect(cells.map((cell) => (cell as HTMLElement).dataset.value)).toEqual([
      'empty',
      'deleted',
      'text',
    ]);
  });

  it('shows a number, a long text and an empty string as the text they are', () => {
    const long = 'x'.repeat(500);
    const root = renderReview([
      { id: 'n', label: 'Weight', change: { kind: 'value', was: '12', theirs: long, mine: '' } },
    ]);

    expect(values(root)).toEqual(['12', long, '']);
  });

  it('draws a set as what was added and what was removed, and nothing for a side with none', () => {
    const root = renderReview([
      { id: 's', label: 'Inherits from', change: { kind: 'set', added: ['Weapon'], removed: [] } },
    ]);

    expect(terms(root)).toEqual(['Added']);
    expect(values(root)).toEqual(['Weapon']);
  });

  it('has no list at all for a set that changed nothing', () => {
    const root = renderReview([
      { id: 's', label: 'Stat groups', change: { kind: 'set', added: [], removed: [] } },
    ]);

    expect(root.querySelector('dl')).toBeNull();
  });

  it('carries a note under the values, and none when there is none', () => {
    const noted = renderReview([{ ...name, note: 'It cannot be applied.' }]);
    const plain = renderReview([name, { ...name, id: 'b', note: '' }]);

    expect(noted.querySelector('.repo-review-note')?.textContent).toBe('It cannot be applied.');
    expect(plain.querySelector('.repo-review-note')).toBeNull();
  });

  it('draws nothing for no fields but its status line', () => {
    const root = renderReview([]);

    expect(root.querySelectorAll('.repo-review-item')).toHaveLength(0);
    expect(root.querySelector('[role="status"]')).not.toBeNull();
  });

  it('draws one block for each field and says which field it is for', () => {
    const root = renderReview([name, { ...name, id: 'slug', label: 'Link name' }]);
    const items = [...root.querySelectorAll<HTMLElement>('.repo-review-item')];

    expect(items.map((item) => item.dataset.reviewItem)).toEqual(['name', 'slug']);
  });
});

describe('what a value is drawn as', () => {
  const evil = '<img src=x onerror="window.pwned=1"><script>window.pwned=2</script>&amp;';

  it('is text, never markup, for every value, name, note and part of a set', () => {
    const root = renderReview(
      [
        {
          id: 'a',
          label: evil,
          note: evil,
          change: { kind: 'value', was: evil, theirs: evil, mine: evil },
          choice: { chosen: null },
        },
        { id: 'b', label: 'Set', change: { kind: 'set', added: [evil], removed: [evil] } },
      ],
      { words: { keepMine: evil, takeTheirs: evil, choiceLegend: evil } },
    );

    document.body.append(root);

    expect(root.querySelector('img')).toBeNull();
    expect(root.querySelector('script')).toBeNull();
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined();
    expect(root.querySelector('.repo-review-label')?.textContent).toBe(evil);
    expect(values(root).filter((text) => text === evil)).toHaveLength(5);
    expect(root.textContent).toContain('&amp;');
  });

  it('is text in the act mode too', () => {
    const root = renderReview([name], {
      mode: 'act',
      words: { keepMine: '<b>Keep</b>', takeTheirs: '<i>Use</i>' },
    });

    expect(root.querySelector('b, i')).toBeNull();
    expect(buttons(root).map((button) => button.textContent)).toEqual([
      '<b>Keep</b>',
      '<i>Use</i>',
    ]);
  });
});

describe('the choice, as radio buttons (choose)', () => {
  it('is a group named by the field and the question, with the two sides as labelled radios', () => {
    const root = renderReview([name]);

    document.body.append(root);

    const group = root.querySelector('fieldset');
    const inputs = radios(root);

    expect(group?.querySelector('legend')?.textContent).toBe('This is changed in your library too');
    expect(inputs.map((input) => input.value)).toEqual(['mine', 'theirs']);
    expect(inputs.map((input) => input.closest('label')?.textContent)).toEqual([
      'Keep yours',
      'Take the update, and replace yours',
    ]);
    expect(new Set(inputs.map((input) => input.name)).size).toBe(1);
    expect(inputs.every((input) => input.required)).toBe(true);

    const named = (group?.getAttribute('aria-labelledby') ?? '').split(' ');

    expect(named).toHaveLength(2);
    expect(named.map((id) => document.getElementById(id)?.textContent)).toEqual([
      'Name',
      'This is changed in your library too',
    ]);
  });

  it('shows what is chosen, and nothing while nothing is', () => {
    const none = radios(renderReview([name]));
    const mine = radios(renderReview([{ ...name, choice: { chosen: 'mine' } }]));
    const theirs = radios(renderReview([{ ...name, choice: { chosen: 'theirs' } }]));

    expect(none.map((input) => input.checked)).toEqual([false, false]);
    expect(mine.map((input) => input.checked)).toEqual([true, false]);
    expect(theirs.map((input) => input.checked)).toEqual([false, true]);
  });

  it('tells the host the field and the side when one is chosen, and again when it changes', () => {
    const chosen: [string, ReviewSide][] = [];
    const root = renderReview([name, { ...name, id: 'slug' }], {
      onChoose: (id, side) => chosen.push([id, side]),
    });

    document.body.append(root);

    const [first, second, third] = radios(root);

    first?.click();
    second?.click();
    third?.click();

    expect(chosen).toEqual([
      ['name', 'mine'],
      ['name', 'theirs'],
      ['slug', 'mine'],
    ]);
  });

  it('does not tell the host again for the side that is already chosen', () => {
    const onChoose = vi.fn();
    const root = renderReview([{ ...name, choice: { chosen: 'mine' } }], { onChoose });

    document.body.append(root);
    radios(root)[0]?.click();

    expect(onChoose).not.toHaveBeenCalled();
  });

  it('is chosen by pressing its label, as a finger does', () => {
    const onChoose = vi.fn();
    const root = renderReview([name], { onChoose });

    document.body.append(root);
    radios(root)[1]?.closest('label')?.click();

    expect(onChoose).toHaveBeenCalledWith('name', 'theirs');
    expect(radios(root)[1]?.checked).toBe(true);
  });

  it('keeps each field its own group, so choosing in one leaves the other alone', () => {
    const root = renderReview([name, { ...name, id: 'slug' }]);

    document.body.append(root);

    const all = radios(root);

    expect(all[0]?.name).not.toBe(all[2]?.name);
    all[0]?.click();
    all[2]?.click();
    expect(all.map((input) => input.checked)).toEqual([true, false, true, false]);
  });

  it('can be reached and used from the keyboard: native radios, in the tab order', () => {
    const root = renderReview([name]);

    document.body.append(root);

    for (const input of radios(root)) {
      expect(input.tagName).toBe('INPUT');
      expect(input.tabIndex).toBe(0);
      expect(input.disabled).toBe(false);
    }

    radios(root)[0]?.focus();
    expect(document.activeElement).toBe(radios(root)[0]);
  });

  it('says what was chosen, politely, for a screen reader', () => {
    const root = renderReview([name]);

    document.body.append(root);
    expect(status(root)).toBe('');
    radios(root)[0]?.click();
    expect(status(root)).toBe('Keeping yours for Name.');
    radios(root)[1]?.click();
    expect(status(root)).toBe('Taking the update for Name.');
  });
});

describe('the choice, as buttons (act)', () => {
  it('is two buttons in a group named for the field, the side that keeps the host first', () => {
    const root = renderReview([name], { mode: 'act' });

    document.body.append(root);

    const group = root.querySelector('[role="group"]');

    expect(radios(root)).toHaveLength(0);
    expect(group?.getAttribute('aria-label')).toBe('Choose for Name');
    expect(buttons(root).map((button) => [button.type, button.textContent])).toEqual([
      ['button', 'Keep yours'],
      ['button', 'Take the update, and replace yours'],
    ]);
    expect(buttons(root).map((button) => button.dataset.side)).toEqual(['mine', 'theirs']);
    expect(
      document.getElementById(group?.getAttribute('aria-describedby') ?? '')?.textContent,
    ).toBe('Name');
  });

  it('acts at once: pressing a button is the choice, whatever was chosen before', () => {
    const chosen: [string, ReviewSide][] = [];
    const root = renderReview([{ ...name, choice: { chosen: 'mine' } }], {
      mode: 'act',
      onChoose: (id, side) => chosen.push([id, side]),
    });

    document.body.append(root);
    buttons(root)[0]?.click();
    buttons(root)[0]?.click();
    buttons(root)[1]?.click();

    expect(chosen).toEqual([
      ['name', 'mine'],
      ['name', 'mine'],
      ['name', 'theirs'],
    ]);
  });

  it('is native buttons, in the tab order', () => {
    const root = renderReview([name], { mode: 'act' });

    document.body.append(root);

    for (const button of buttons(root)) {
      expect(button.tabIndex).toBe(0);
      expect(button.disabled).toBe(false);
    }
  });

  it('says what was pressed for a screen reader', () => {
    const root = renderReview([name], { mode: 'act' });

    buttons(root)[1]?.click();
    expect(status(root)).toBe('Taking the update for Name.');
  });
});

describe('a host with words of its own', () => {
  const bench = {
    mine: 'Mine',
    theirs: 'Theirs',
    keepMine: 'Keep mine',
    takeTheirs: 'Use theirs',
    keptMine: (label: string) => `Keeping mine for ${label}.`,
  };

  it('has them for the values, the choice and the status, and the defaults for the rest', () => {
    const root = renderReview([name], { mode: 'act', words: bench });

    expect(terms(root)).toEqual(['Was', 'Theirs', 'Mine']);
    expect(buttons(root).map((button) => button.textContent)).toEqual(['Keep mine', 'Use theirs']);

    buttons(root)[0]?.click();
    expect(status(root)).toBe('Keeping mine for Name.');
    buttons(root)[1]?.click();
    expect(status(root)).toBe('Taking the update for Name.');
  });

  it('can be the same words as reviewWords gives', () => {
    expect(reviewWords(bench).takeTheirs).toBe('Use theirs');
  });
});

describe('several reviews on one page', () => {
  it('do not share a radio group or an id', () => {
    const one = renderReview([name]);
    const two = renderReview([name]);

    document.body.append(one, two);

    const names = new Set([...radios(one), ...radios(two)].map((input) => input.name));
    const ids = [...document.querySelectorAll('[id]')].map((element) => element.id);

    expect(names.size).toBe(2);
    expect(new Set(ids).size).toBe(ids.length);

    radios(one)[0]?.click();
    radios(two)[1]?.click();
    expect(radios(one).map((input) => input.checked)).toEqual([true, false]);
    expect(radios(two).map((input) => input.checked)).toEqual([false, true]);
  });
});
