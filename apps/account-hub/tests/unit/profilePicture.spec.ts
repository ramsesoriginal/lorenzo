import { describe, expect, it } from 'vitest';
import { pictureProblem } from '../../src/lib/profilePicture';

describe('profile picture size limit', () => {
  it('accepts pictures up to and including 10 MB', () => {
    for (const size of [2_000_001, 10_000_000]) {
      expect(pictureProblem({ type: 'image/jpeg', size })).toBeNull();
    }
  });

  it('rejects pictures above 10 MB with the current limit', () => {
    expect(pictureProblem({ type: 'image/jpeg', size: 10_000_001 })).toBe(
      'That picture is over 10 MB. Choose a smaller one.',
    );
  });
});
