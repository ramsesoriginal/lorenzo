import { expect, it } from 'vitest';
import { mentioned, nameKey } from './mentioned-names';

it('matches complete literal names across case, accents and spaces', () => {
  const passages = ['The E\u0301ira   Vale legend meets A+B (Jr.) and {Ash}.'].map(nameKey);
  for (const name of ['ÉIRA VALE', 'A+B (Jr.)', '{Ash}'])
    expect(mentioned(passages, name)).toBe(true);
  for (const name of ['ira', 'legendary', 'A.B', '']) expect(mentioned(passages, name)).toBe(false);
});

it('respects Unicode word boundaries and separate prose passages', () => {
  const passages = ['月Eira', 'Eira_2', 'North', 'Bank'].map(nameKey);
  expect(mentioned(passages, 'Eira')).toBe(false);
  expect(mentioned(passages, 'North Bank')).toBe(false);
});
