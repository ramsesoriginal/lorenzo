import { describe, expect, it } from 'vitest';
import { defaultHolder, type Holder } from './lastHolder';

const ashfang: Holder = { kind: 'character', id: 'ashfang' };
const brisk: Holder = { kind: 'character', id: 'brisk' };
const company: Holder = { kind: 'group', id: 'company' };

describe('defaultHolder', () => {
  it('opens the one last opened, character or group', () => {
    expect(defaultHolder([ashfang, brisk, company], brisk)).toEqual(brisk);
    expect(defaultHolder([ashfang, company], company)).toEqual(company);
  });

  it('opens the only character when nothing is remembered, groups aside', () => {
    expect(defaultHolder([ashfang, company], null)).toEqual(ashfang);
  });

  it('forgets one that is no longer in the list', () => {
    expect(defaultHolder([ashfang], brisk)).toEqual(ashfang);
    expect(defaultHolder([ashfang, company], { kind: 'group', id: 'gone' })).toEqual(ashfang);
  });

  it('opens nothing among several characters with nothing remembered', () => {
    expect(defaultHolder([ashfang, brisk], null)).toBeNull();
    expect(defaultHolder([], null)).toBeNull();
  });
});
