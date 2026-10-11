import { describe, expect, it } from 'vitest';
import {
  codeFromSearch,
  neverUsed,
  normalizeUserCode,
  revokeTokenConfirmation,
  suggestedTokenName,
  TOKEN_EXPIRY_PRESETS,
  tokenExpiryFor,
  tokenState,
} from '../../src/lib/personalTokens';

const NOW = new Date('2026-10-11T12:00:00.000Z');

describe('normalizeUserCode', () => {
  it('accepts a code in any case, with or without the dash or spaces', () => {
    for (const text of ['BCDF-GHJK', 'bcdf-ghjk', 'bcdfghjk', ' bcdf ghjk ', 'BCDF GHJK']) {
      expect(normalizeUserCode(text)).toBe('BCDF-GHJK');
    }
  });

  it('refuses what cannot be a code: wrong length, vowels, digits', () => {
    for (const text of ['', 'BCDF', 'BCDF-GHJKM', 'ABCD-EFGH', 'BCDF-GH1K', 'BCDF-GHJ!']) {
      expect(normalizeUserCode(text)).toBeNull();
    }
  });
});

describe('codeFromSearch', () => {
  it('reads ?code= from the address', () => {
    expect(codeFromSearch('?code=bcdf-ghjk')).toBe('BCDF-GHJK');
  });

  it('is null when there is none or it is not a code', () => {
    expect(codeFromSearch('')).toBeNull();
    expect(codeFromSearch('?code=nope')).toBeNull();
    expect(codeFromSearch('?other=BCDF-GHJK')).toBeNull();
  });
});

describe('token expiry', () => {
  it('offers "Never" first, which sends no expiry', () => {
    expect(TOKEN_EXPIRY_PRESETS[0].id).toBe('never');
    expect(tokenExpiryFor('never', NOW)).toBeNull();
  });

  it('counts the other presets from now', () => {
    expect(tokenExpiryFor('30d', NOW)).toBe('2026-11-10T12:00:00.000Z');
    expect(tokenExpiryFor('1y', NOW)).toBe('2027-10-11T12:00:00.000Z');
  });

  it('refuses an unknown preset', () => {
    expect(() => tokenExpiryFor('soon', NOW)).toThrow();
  });
});

describe('the list', () => {
  const token = {
    id: 'a',
    name: 'Laptop',
    hint: 'abcd',
    created_at: NOW.toISOString(),
    last_used_at: null,
    expires_at: null,
    is_expired: false,
  };

  it('names the state and whether it was ever used', () => {
    expect(tokenState(token)).toBe('active');
    expect(tokenState({ ...token, is_expired: true })).toBe('expired');
    expect(neverUsed(token)).toBe(true);
    expect(neverUsed({ ...token, last_used_at: NOW.toISOString() })).toBe(false);
  });

  it('suggests the device name, trimmed, or a plain one', () => {
    expect(suggestedTokenName('  lorenzo CLI on laptop ')).toBe('lorenzo CLI on laptop');
    expect(suggestedTokenName(null)).toBe('My device');
    expect(suggestedTokenName('x'.repeat(200))).toHaveLength(80);
  });

  it('asks before revoking, naming the token', () => {
    expect(revokeTokenConfirmation('Laptop')).toContain('"Laptop"');
  });
});
