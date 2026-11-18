import { expect, it } from 'vitest';
import { boundaryBefore } from './blocks-pure';

const text = 'One.\n\nTwo.\n\n\nThree.';

it('finds the start of the section the caret is in', () => {
  expect(boundaryBefore(text, 0)).toBeNull();
  expect(boundaryBefore(text, 3)).toBeNull();
  expect(boundaryBefore(text, 6)).toBe(6);
  expect(boundaryBefore(text, 9)).toBe(6);
  expect(boundaryBefore(text, text.length)).toBe(text.indexOf('Three'));
});
