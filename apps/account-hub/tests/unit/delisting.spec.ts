import { describe, expect, it } from 'vitest';
import {
  DELISTED_CANNOT_BE_MADE_PUBLIC,
  DELISTED_EFFECT,
  DELISTED_PILL,
  DELISTED_PUBLIC_NOTE,
  DELISTED_TITLE,
  delistedNotice,
  delistedReason,
} from '../../src/lib/delisting';

describe('the notice of a repository that is off Discover', () => {
  it('is nothing for a repository that is listed', () => {
    expect(delistedNotice(null)).toBeNull();
    expect(delistedNotice(undefined)).toBeNull();
  });

  it('says what happened, why, and what it means for the libraries that copied it', () => {
    const notice = delistedNotice({
      reason: 'It copies another publisher',
      at: '2026-10-15T09:00:00Z',
    });

    expect(notice).toEqual({
      pill: 'Off Discover',
      title: "This repository was taken off Discover by the platform's operators.",
      reason: 'Reason: It copies another publisher',
      effect:
        'Libraries that copied it keep their copies, and cannot update from it until it is listed again.',
    });
  });

  it('keeps the reason as the operators wrote it', () => {
    expect(delistedReason('  odd:  words ')).toBe('Reason:   odd:  words ');
  });

  it('is never said in the words of the architecture, and names no person', () => {
    const words = [
      DELISTED_PILL,
      DELISTED_TITLE,
      DELISTED_EFFECT,
      DELISTED_CANNOT_BE_MADE_PUBLIC,
      DELISTED_PUBLIC_NOTE,
    ].join('\n');

    expect(words).not.toMatch(/tenant|grant|subscri|delist/i);
    expect(words).toMatch(/platform.s operators/);
  });
});
