import { expect, it } from 'vitest';
import { reviewedLink } from './reviewed-link';

const replace = (source: string, selected: string) => {
  const start = source.indexOf(selected);
  return reviewedLink(source, start, start + selected.length, 'harbour-scribe');
};

it('keeps the precise label in ordinary prose and nested formatting', () => {
  for (const source of [
    'Met Éira Vale today.',
    '**Éira Vale**',
    '> - Éira Vale',
    'Éira Vale and Éira Vale',
  ])
    expect(replace(source, 'Éira Vale')).toBe('[[harbour-scribe|Éira Vale]]');
});

it('rejects selections in protected syntax or spanning inline nodes', () => {
  for (const source of [
    '`Eira`',
    '```\nEira\n```',
    '$Eira$',
    '[Eira](https://example.test)',
    '[[old|Eira]]',
    '![Eira](image.png)',
    'xEira',
    'Eira2',
    '[one](https://example.test/Eira)',
  ])
    expect(replace(source, 'Eira')).toBeNull();
  expect(replace('Ei**ra** Vale', 'Ei**ra** Vale')).toBeNull();
  expect(replace('Line one\nLine two', 'one\nLine')).toBeNull();
});
