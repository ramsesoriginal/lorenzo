import { describe, expect, it } from 'vitest';
import { BUILT_IN, footLine, parseViews, partOf, toggled, viewName, withView } from './regions';

describe('the parts of a Session page', () => {
  it('knows which part a region belongs to, and the head to none', () => {
    expect(partOf('coverage')).toBe('gametime');
    expect(partOf('adder')).toBe('scenes');
    expect(partOf('head')).toBeUndefined();
  });
  it('names the view a set of parts is, in any order', () => {
    expect(viewName(BUILT_IN.Prepare, [])).toBe('Prepare');
    expect(viewName(['notes', 'played'], [])).toBe('Played');
    expect(viewName(['notes'], [])).toBe('Custom');
    expect(viewName(['notes'], [{ name: 'Mine', parts: ['notes'] }])).toBe('Mine');
  });
  it('says what is hidden, and nothing when nothing is', () => {
    expect(footLine(BUILT_IN.All)).toBe('');
    expect(footLine(BUILT_IN.Prepare)).toContain('Hidden: References, Game time, Played');
    expect(footLine(BUILT_IN.Prepare)).toContain('nothing is deleted');
  });
  it('turns a part on and off', () => {
    expect(toggled(['notes'], 'roster')).toEqual(['notes', 'roster']);
    expect(toggled(['notes', 'roster'], 'notes')).toEqual(['roster']);
  });
  it('reads back only the views it can trust', () => {
    expect(parseViews(null)).toEqual([]);
    expect(parseViews('not json')).toEqual([]);
    expect(parseViews('{"a":1}')).toEqual([]);
    expect(
      parseViews(
        '[{"name":" Mine ","parts":["notes","nonsense"]},{"name":"","parts":[]},{"parts":[]}]',
      ),
    ).toEqual([{ name: 'Mine', parts: ['notes'] }]);
  });
  it('keeps a view under its name, the same name replacing it, and refuses the built-in names', () => {
    const one = withView([], 'Mine', ['notes']) ?? [];
    expect(one).toEqual([{ name: 'Mine', parts: ['notes'] }]);
    expect(withView(one, 'Mine', ['roster'])).toEqual([{ name: 'Mine', parts: ['roster'] }]);
    expect(withView(one, 'Prepare', ['roster'])).toBeNull();
    expect(withView(one, '  ', ['roster'])).toBeNull();
  });
});
