import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  DEAD_LINK_MESSAGE,
  EXPIRY_PRESETS,
  expiresAtFor,
  forgetInviteToken,
  INVITE_TOKEN_KEY,
  inviteStatus,
  inviteUrl,
  joinedMessage,
  LINK_SHOWN_ONCE_NOTICE,
  parseMaxUses,
  readInviteToken,
  rememberInviteToken,
  STATUS_LABELS,
  storedInviteToken,
  usesLabel,
} from '../../src/lib/inviteLink';

// 43 URL-safe characters, the shape of what apps/api issues (256 random bits).
const TOKEN = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG';
const NOW = new Date('2026-10-04T12:00:00.000Z');

function invite(overrides: Partial<Parameters<typeof inviteStatus>[0]> = {}) {
  return {
    is_active: true,
    revoked_at: null,
    expires_at: '2026-10-11T12:00:00.000Z',
    max_uses: null,
    use_count: 0,
    ...overrides,
  };
}

function fakeStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial));
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
  };
}

describe('the link', () => {
  it('puts the token in the fragment, which no server or Referer ever sees', () => {
    expect(inviteUrl('https://hub.example', TOKEN)).toBe(`https://hub.example/join/#${TOKEN}`);
  });

  it('reads a token back out of a location hash, with or without the #', () => {
    expect(readInviteToken(`#${TOKEN}`)).toBe(TOKEN);
    expect(readInviteToken(TOKEN)).toBe(TOKEN);
  });

  it.each([
    [''],
    ['#'],
    ['#short'],
    ['#has spaces in it, so not a token at all'],
    [`#${TOKEN}/extra`],
    [`#${'a'.repeat(300)}`],
    ['#<script>alert(1)</script>'],
  ])('refuses what is not a token: %s', (hash) => {
    expect(readInviteToken(hash)).toBeNull();
  });
});

describe('expiry presets', () => {
  it('offers one hour to four weeks, and nothing the API would refuse', () => {
    expect(EXPIRY_PRESETS.map((p) => p.id)).toEqual(['1h', '1d', '1w', '4w']);
    const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
    expect(Math.max(...EXPIRY_PRESETS.map((p) => p.ms))).toBeLessThan(thirtyDaysMs);
  });

  it.each([
    ['1h', '2026-10-04T13:00:00.000Z'],
    ['1d', '2026-10-05T12:00:00.000Z'],
    ['1w', '2026-10-11T12:00:00.000Z'],
    ['4w', '2026-11-01T12:00:00.000Z'],
  ] as const)('%s from now', (id, expected) => {
    expect(expiresAtFor(id, NOW)).toBe(expected);
  });
});

describe('parseMaxUses', () => {
  it('treats an empty box as no limit', () => {
    expect(parseMaxUses('')).toEqual({ maxUses: null });
    expect(parseMaxUses('   ')).toEqual({ maxUses: null });
  });

  it('takes a whole number of 1 or more', () => {
    expect(parseMaxUses('1')).toEqual({ maxUses: 1 });
    expect(parseMaxUses(' 25 ')).toEqual({ maxUses: 25 });
  });

  it.each([['0'], ['-3'], ['2.5'], ['ten'], ['1e3'], ['1 2'], ['99999999999999999999']])(
    'refuses %s',
    (text) => {
      expect(parseMaxUses(text)).toBeNull();
    },
  );
});

describe('inviteStatus', () => {
  it('is Active for a live link', () => {
    expect(inviteStatus(invite(), NOW)).toBe('active');
  });

  it('is Revoked once revoked, whatever else is true', () => {
    const revoked = invite({ revoked_at: '2026-10-04T11:00:00Z', max_uses: 1, use_count: 1 });
    expect(inviteStatus(revoked, NOW)).toBe('revoked');
  });

  it('is Expired at and after its expiry', () => {
    expect(inviteStatus(invite({ expires_at: NOW.toISOString() }), NOW)).toBe('expired');
    expect(inviteStatus(invite({ expires_at: '2026-10-01T00:00:00Z' }), NOW)).toBe('expired');
  });

  it('is Used up at its limit, and Active just under it', () => {
    expect(inviteStatus(invite({ max_uses: 3, use_count: 3 }), NOW)).toBe('used-up');
    expect(inviteStatus(invite({ max_uses: 3, use_count: 2 }), NOW)).toBe('active');
    expect(inviteStatus(invite({ max_uses: null, use_count: 500 }), NOW)).toBe('active');
  });

  it('never shows Active for a link the API calls inactive', () => {
    expect(inviteStatus(invite({ is_active: false }), NOW)).toBe('expired');
  });

  it('has a label for every status', () => {
    expect(STATUS_LABELS).toEqual({
      active: 'Active',
      revoked: 'Revoked',
      expired: 'Expired',
      'used-up': 'Used up',
    });
  });
});

describe('usesLabel', () => {
  it('counts against a limit, or says there is none', () => {
    expect(usesLabel({ max_uses: 10, use_count: 3 })).toBe('3 of 10');
    expect(usesLabel({ max_uses: null, use_count: 3 })).toBe('3, no limit');
  });
});

describe('keeping the token across a login', () => {
  it('keeps it under one key and forgets it', () => {
    const storage = fakeStorage();
    expect(rememberInviteToken(storage, TOKEN)).toBe(true);
    expect([...storage.items.keys()]).toEqual([INVITE_TOKEN_KEY]);
    expect(storedInviteToken(storage)).toBe(TOKEN);
    forgetInviteToken(storage);
    expect(storedInviteToken(storage)).toBeNull();
  });

  it('does not trust what is already in storage', () => {
    expect(storedInviteToken(fakeStorage({ [INVITE_TOKEN_KEY]: 'not a token' }))).toBeNull();
    expect(storedInviteToken(fakeStorage())).toBeNull();
  });

  it('says so when it could not keep it, instead of throwing', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    };
    expect(rememberInviteToken(broken, TOKEN)).toBe(false);
    expect(rememberInviteToken(undefined, TOKEN)).toBe(false);
    expect(storedInviteToken(broken)).toBeNull();
    expect(storedInviteToken(undefined)).toBeNull();
    expect(() => forgetInviteToken(broken)).not.toThrow();
    expect(() => forgetInviteToken(undefined)).not.toThrow();
  });
});

describe('what is said', () => {
  it('has one sentence for every dead link, which tells no case apart', () => {
    expect(DEAD_LINK_MESSAGE).toBe(
      "This link doesn't work any more. Ask whoever sent it for a new one.",
    );
    for (const reason of ['expired', 'revoked', 'used', 'unknown', 'exhausted']) {
      expect(DEAD_LINK_MESSAGE.toLowerCase()).not.toContain(reason);
    }
  });

  it('says a link is shown once, and what holding it means', () => {
    expect(LINK_SHOWN_ONCE_NOTICE).toContain("won't be shown again");
    expect(LINK_SHOWN_ONCE_NOTICE).toContain('join this campaign as a player');
  });

  it('says whether the visitor joined or already had', () => {
    expect(joinedMessage('Zorro', false)).toBe("You're in. Zorro lists you as a player.");
    expect(joinedMessage('Zorro', true)).toBe("You're already a player in Zorro.");
  });
});

// ADR 0092 requirement 7, in the file Cloudflare Pages reads: the landing path
// must send Referrer-Policy: no-referrer, with and without the trailing slash.
// A path line starts in column 0 and its headers are the indented lines below.
function headerRules(text: string): Map<string, string[]> {
  const rules = new Map<string, string[]>();
  let current: string[] | undefined;
  for (const line of text.split('\n')) {
    if (line.trim() === '' || line.startsWith('#')) continue;
    if (/^\s/.test(line)) {
      current?.push(line.trim());
    } else {
      current = [];
      rules.set(line.trim(), current);
    }
  }
  return rules;
}

describe('public/_headers', () => {
  const rules = headerRules(
    readFileSync(new URL('../../public/_headers', import.meta.url), 'utf8'),
  );

  it.each(['/join', '/join/*'])('sets Referrer-Policy: no-referrer for %s', (path) => {
    expect(rules.get(path)).toContain('Referrer-Policy: no-referrer');
  });

  it('has no rule that weakens it', () => {
    for (const headers of rules.values()) {
      expect(headers.filter((h) => h.startsWith('Referrer-Policy:'))).toEqual([
        'Referrer-Policy: no-referrer',
      ]);
    }
  });
});
