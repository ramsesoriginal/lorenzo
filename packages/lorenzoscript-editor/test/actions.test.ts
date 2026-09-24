// The pure actions (ADR 0106). In each case `[…]` is the selection and `|` the cursor,
// before and after: `he[llo]` selects "llo", `he|llo` has the cursor after "he".
import { describe, expect, test } from 'vitest';
import { ACTIONS, type Action, date, indent, newline, type State } from '../src';

/** `text` without the character at `i`. */
const cut = (text: string, i: number) => text.slice(0, i) + text.slice(i + 1);

/** A marked-up case as a state: `open`…`close` is the selection, `cursor` (if any) a cursor. */
const read =
  (open: string, close: string, cursor?: string) =>
  (marked: string): State => {
    const at = cursor ? marked.indexOf(cursor) : -1;
    if (at >= 0) return { text: cut(marked, at), start: at, end: at };
    const start = marked.indexOf(open);
    const end = marked.indexOf(close) - 1;
    return { text: cut(cut(marked, start), end), start, end };
  };
/** A state marked up the same way. */
const write =
  (open: string, close: string, cursor?: string) =>
  ({ text, start, end }: State) =>
    cursor && start === end
      ? `${text.slice(0, start)}${cursor}${text.slice(start)}`
      : `${text.slice(0, start)}${open}${text.slice(start, end)}${close}${text.slice(end)}`;

const state = read('[', ']', '|');
const mark = write('[', ']', '|');
const check = (action: Action, cases: [string, string][]) =>
  test.each(cases)('%j → %j', (before, after) => expect(mark(action(state(before)))).toBe(after));

// Cases whose text contains `[` or `]` use a different marker below.
describe('wrapping', () => {
  describe('bold', () => {
    check(ACTIONS.bold.run, [
      ['a |b', 'a **[bold text]**b'],
      ['a [word] b', 'a **[word]** b'],
      ['a **[word]** b', 'a [word] b'],
    ]);
  });
  describe('strikethrough', () => check(ACTIONS.strike.run, [['[gone]', '~~[gone]~~']]));
  describe('math', () => check(ACTIONS.math.run, [['|', '$[x^2]$']]));
});

describe('line prefixes', () => {
  describe('heading cycles', () => {
    check(ACTIONS.heading.run, [
      ['Ti|tle', '# Ti|tle'],
      ['# Ti|tle', '## Ti|tle'],
      ['### Ti|tle', 'Ti|tle'],
    ]);
  });
  describe('bullets', () => {
    check(ACTIONS.bullets.run, [
      ['[a\nb]', '[- a\n- b]'],
      ['[- a\n- b]', '[a\nb]'],
      ['1. |a', '- |a'],
    ]);
  });
  describe('numbers replace bullets', () => {
    check(ACTIONS.numbers.run, [['[- a\n- b]', '[1. a\n2. b]']]);
  });
  describe('quote', () => check(ACTIONS.quote.run, [['a|b', '> a|b']]));
});

describe('blocks', () => {
  describe('code block', () => {
    check(ACTIONS.codeblock.run, [
      ['text|', 'text\n\n```\n[code]\n```'],
      ['a\n[x = 1]\nb', 'a\n\n```\n[x = 1]\n```\n\nb'],
    ]);
  });
  describe('rule', () => check(ACTIONS.rule.run, [['a|', 'a\n\n---|']]));
});

describe('newline', () => {
  const enter = (s: State) => newline(s) ?? { ...s, text: `${s.text} (browser newline)` };
  check(enter, [
    ['- a|', '- a\n- |'],
    ['3. a|', '3. a\n4. |'],
    ['- [x] done|', '- [x] done\n- [ ] |'],
    ['> quoted|', '> quoted\n> |'],
    ['> - a|', '> - a\n> - |'],
    ['    - nested|', '    - nested\n    - |'],
    ['- a\n- |', '- a\n|'],
    ['> a\n> |', '> a\n|'],
    ['plain|', 'plain| (browser newline)'],
  ]);
});

describe('indent', () => {
  describe('Tab', () => {
    check(indent(), [
      ['- a|', '    - a|'],
      ['text|', 'text    |'],
      ['[a\nb]', '    [a\n    b]'],
    ]);
  });
  describe('Shift-Tab', () => {
    check(indent(true), [
      ['    - a|', '- a|'],
      ['  - a|', '- a|'],
      ['[    a\n  b]', '[a\nb]'],
    ]);
  });
});

describe('with brackets in the text', () => {
  // `⟨…⟩` marks the selection here, since the text itself holds `[`, `]`, and `|`;
  // an empty `⟨⟩` is the cursor.
  const at = read('⟨', '⟩');
  const show = write('⟨', '⟩');

  test.each([
    ['link, selected text', ACTIONS.link.run, 'see ⟨the map⟩', 'see [the map](⟨url⟩)'],
    ['link, nothing selected', ACTIONS.link.run, 'see ⟨⟩', 'see [⟨text⟩](url)'],
    ['entity', ACTIONS.entity.run, '⟨Ashfang⟩', '[[⟨Ashfang⟩]]'],
    ['image', ACTIONS.image.run, '⟨⟩', '![⟨description⟩](url)'],
    ['tasks', ACTIONS.tasks.run, '⟨- a⟩', '⟨- [ ] a⟩'],
    ['tasks off', ACTIONS.tasks.run, '⟨- [x] a⟩', '⟨a⟩'],
    ['bullets from tasks', ACTIONS.bullets.run, '⟨- [ ] a⟩', '⟨- a⟩'],
    ['table', ACTIONS.table.run, '⟨⟩', '| ⟨Column⟩ | Column |\n| --- | --- |\n|  |  |'],
  ] as const)('%s', (_, action, before, after) => expect(show(action(at(before)))).toBe(after));

  test('footnote: the next free number, its definition at the end', () => {
    const s = at('Forged in Emberdeep.[^1] By Oda⟨⟩, who left.\n\n[^1]: A city.\n');
    expect(show(ACTIONS.footnote.run(s))).toBe(
      'Forged in Emberdeep.[^1] By Oda[^2], who left.\n\n[^1]: A city.\n\n[^2]: ⟨⟩',
    );
  });
});

test("date: today's, in the writer's time zone", () => {
  const action = date(() => new Date(2026, 8, 4, 23, 59));
  expect(mark(action(state('on |')))).toBe('on {{date 2026-09-04}}|');
});
