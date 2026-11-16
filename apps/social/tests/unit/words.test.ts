import { expect, test } from 'vitest';
import {
  audienceWords,
  defaultName,
  directionWords,
  sentence,
  stateWords,
} from '../../src/lib/words';

const ends = { endA: 'Mara', endB: 'Wren', oneWay: true };

test('direction is said in words', () => {
  expect(directionWords(ends)).toBe('From Mara to Wren');
  expect(directionWords({ ...ends, oneWay: false })).toBe('Between Mara and Wren, both ways');
});

test('a relationship reads as a sentence, with the library verbs, the type name or neither', () => {
  expect(sentence(ends, { name: 'Parent of', readsAs: 'is the parent of' })).toBe(
    'Mara is the parent of Wren',
  );
  expect(
    sentence(
      { ...ends, oneWay: false },
      { name: 'Sibling of', readsAs: 'is a sibling of', readsAsBack: 'is a sibling of' },
    ),
  ).toBe('Mara is a sibling of Wren; Wren is a sibling of Mara');
  expect(sentence(ends, { name: 'Parent of' })).toBe('Mara → Wren: Parent of');
  expect(sentence({ ...ends, oneWay: false })).toBe('Mara and Wren');
});

test('a new relationship is named for its ends and type', () => {
  expect(defaultName('Mara', 'Wren', 'Parent of')).toBe('Mara - Parent of - Wren');
  expect(defaultName('Mara', 'Wren')).toBe('Mara - Wren');
});

test('who may see it is a neutral phrase, and nothing for a reader who is not told', () => {
  expect(audienceWords(true)).toBe('Everyone in the library');
  expect(audienceWords(false)).toBe('Restricted');
  expect(audienceWords(null)).toBe('');
});

test('where a relationship stands as of an Event is said in words', () => {
  expect(stateWords('holds')).toBe('Holds');
  expect(stateWords('not_yet')).toBe('Has not begun');
  expect(stateWords('ended')).toBe('Has ended');
  expect(stateWords('unknown')).toBe('Not known from what you can see');
  expect(stateWords('limit_reached')).toBe('Too many Events to say');
  expect(stateWords(null)).toBe('');
});
