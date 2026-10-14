import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  DEAD_LINK_MESSAGE,
  EXPIRY_PRESETS,
  expiresAtFor,
  forgetInviteToken,
  GM_EXPIRY_PRESETS,
  gmLinkShownOnceNotice,
  INVITE_TOKEN_KEY,
  inviteOffer,
  inviteStatus,
  inviteUrl,
  joinedMessage,
  joinedMessageFor,
  LIBRARY_LINK_NOTICE,
  LINK_ROLES,
  LINK_SHOWN_ONCE_NOTICE,
  libraryLinkWho,
  linkKindLabel,
  MAX_TEAM,
  NO_SHARE_TARGET_MESSAGE,
  offerFor,
  PASTE_ERROR,
  parseMaxUses,
  parseTeamSize,
  pastedInvite,
  readInviteToken,
  rememberInviteToken,
  roleLinkNotice,
  STATUS_LABELS,
  shareTargets,
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

describe('GM links (ADR 0177)', () => {
  it('offers expiries of at most a week, with slack under the API limit', () => {
    const now = new Date('2026-10-04T12:00:00Z');
    for (const preset of GM_EXPIRY_PRESETS) {
      const ms = new Date(expiresAtFor(preset.id, now)).getTime() - now.getTime();
      expect(ms).toBeGreaterThan(0);
      // The API allows 7 days; a client clock that runs a little fast must stay inside it.
      expect(ms).toBeLessThan(7 * 24 * 60 * 60 * 1000);
    }
    expect(GM_EXPIRY_PRESETS.map((p) => p.id)).toEqual(['1h', '1d', '3d', '6d']);
  });

  it('computes a GM preset like any other', () => {
    const now = new Date('2026-10-04T12:00:00Z');
    expect(expiresAtFor('3d', now)).toBe('2026-10-07T12:00:00.000Z');
    expect(expiresAtFor('1w', now)).toBe('2026-10-11T12:00:00.000Z');
  });

  it('says what a link makes someone, on the page and on its button', () => {
    expect(inviteOffer('player')).toEqual({
      sentence: "You've been invited to join this campaign as a player.",
      joinLabel: 'Join',
    });
    expect(inviteOffer('gm').sentence).toContain('as a GM');
    expect(inviteOffer('gm').joinLabel).toBe('Join as a GM');
    expect(linkKindLabel('gm', 'GM')).toBe('GM link');
    expect(linkKindLabel('player', 'GM')).toBe('Player link');
  });

  it("says joined as a GM in a GM link's own words, and a player link's as before", () => {
    expect(joinedMessage('Zorro', false)).toBe("You're in. Zorro lists you as a player.");
    expect(joinedMessage('Zorro', true)).toBe("You're already a player in Zorro.");
    expect(joinedMessage('Zorro', false, 'gm')).toBe("You're in. Zorro lists you among its GMs.");
    expect(joinedMessage('Zorro', true, 'gm')).toBe("You're already one of the GMs of Zorro.");
  });

  it('warns that a GM link works once and makes a GM', () => {
    const notice = gmLinkShownOnceNotice('GMs');

    expect(notice).toContain('works once');
    expect(notice).toContain('joins the GMs of this campaign');
    expect(notice).toContain("won't be shown again");
  });

  // ADR 0294: a campaign that names its game master says so, with no article that a title could
  // break and no GM left over.
  it("speaks of a campaign's game master by the campaign's own title", () => {
    const storytellers = { title: 'Storyteller', plural: 'Storytellers' };
    const texts = [
      linkKindLabel('gm', storytellers.title),
      joinedMessage('Zorro', false, 'gm', storytellers),
      joinedMessage('Zorro', true, 'gm', storytellers),
      gmLinkShownOnceNotice(storytellers.plural),
    ];

    expect(texts[0]).toBe('Storyteller link');
    expect(texts[1]).toBe("You're in. Zorro lists you among its Storytellers.");
    expect(texts[2]).toBe("You're already one of the Storytellers of Zorro.");
    for (const text of texts) expect(text).not.toMatch(/\bGMs?\b/);
  });

  it('says joined with the title of the campaign the link opened (joinedMessageFor)', () => {
    const preview = { kind: 'campaign', name: 'Zorro', tenant_kind: null, role: 'gm' } as const;

    expect(
      joinedMessageFor(preview, { already_joined: false, role: 'gm' }, '', {
        title: 'Narrator',
        plural: 'Narrators',
      }),
    ).toBe("You're in. Zorro lists you among its Narrators.");
    // With no campaign to read it from, it is "GM".
    expect(joinedMessageFor(preview, { already_joined: false, role: 'gm' })).toBe(
      "You're in. Zorro lists you among its GMs.",
    );
  });
});

describe('the other kinds of link (ADR 0220)', () => {
  const library = {
    kind: 'tenant_role',
    name: 'A table',
    tenant_kind: 'play',
    role: 'author',
  } as const;
  const repository = {
    kind: 'tenant_role',
    name: 'Faerûn',
    tenant_kind: 'repository',
    role: 'orga',
  } as const;
  const sharing = {
    kind: 'library_access',
    name: 'Faerûn',
    tenant_kind: 'repository',
    role: null,
  } as const;

  it('offers a role in a library or a repository in the three names, never the API’s word', () => {
    expect(offerFor(library)).toEqual({
      sentence: "You've been invited to join the library A table as an Author.",
      actionLabel: 'Join as an Author',
    });
    expect(offerFor(repository)).toEqual({
      sentence: "You've been invited to join the repository Faerûn as an Organizer.",
      actionLabel: 'Join as an Organizer',
    });
    expect(offerFor(repository).sentence).not.toMatch(/orga\b/);
  });

  it('offers a repository to share, and asks which library, without a word of tenant', () => {
    const { sentence, actionLabel } = offerFor(sharing);
    expect(sentence).toContain('The repository Faerûn is being shared with a library of yours.');
    expect(actionLabel).toBe('Share');
    expect(`${sentence} ${NO_SHARE_TARGET_MESSAGE}`).not.toMatch(/tenant|grant|subscri/i);
  });

  it('keeps a campaign link as it was', () => {
    expect(offerFor({ kind: 'campaign', name: 'Zorro', tenant_kind: null, role: 'gm' })).toEqual({
      sentence: "You've been invited to run this campaign as a GM.",
      actionLabel: 'Join as a GM',
    });
  });

  it('says what happened to a person who used one, and that a link changes no role', () => {
    expect(joinedMessageFor(library, { already_joined: false, role: 'author' })).toBe(
      "You're in. A table lists you as an Author.",
    );
    expect(joinedMessageFor(library, { already_joined: true, role: 'author' })).toBe(
      "You already belong to A table. A link doesn't change anyone's role.",
    );
    expect(joinedMessageFor(sharing, { already_joined: false, role: null }, 'A table')).toBe(
      'Faerûn is now shared with A table.',
    );
    expect(joinedMessageFor(sharing, { already_joined: true, role: null }, 'A table')).toBe(
      'Faerûn is already shared with A table.',
    );
    expect(
      joinedMessageFor(
        { kind: 'campaign', name: 'Zorro', tenant_kind: null, role: 'player' },
        { already_joined: false, role: 'player' },
      ),
    ).toBe("You're in. Zorro lists you as a player.");
  });

  it('labels every link in the list in the three names', () => {
    expect(linkKindLabel('author', 'GM')).toBe('Author link');
    expect(linkKindLabel('orga', 'GM')).toBe('Organizer link');
    expect(linkKindLabel(null, 'GM')).toBe('Library link');
  });

  it('offers to share with the libraries and repositories you own, and no other', () => {
    const managed = {
      tenants: [
        { tenant_id: 'a', name: 'Zed table', role: 'owner', kind: 'play' },
        { tenant_id: 'b', name: 'Run by me', role: 'orga', kind: 'play' },
        { tenant_id: 'c', name: 'Bridge', role: 'owner', kind: 'repository' },
        { tenant_id: 'd', name: 'Written by me', role: 'author', kind: 'repository' },
        { tenant_id: 'e', name: 'GM only', role: null, kind: 'play' },
      ],
    } as const;
    expect(shareTargets(managed)).toEqual([
      { id: 'c', name: 'Bridge', label: 'Bridge (repository)' },
      { id: 'a', name: 'Zed table', label: 'Zed table (library)' },
    ]);
    expect(shareTargets({ tenants: [] })).toEqual([]);
  });

  it('opens what was pasted, a whole link or only its code, and says so when it is neither', () => {
    expect(pastedInvite(`https://hub.example/join/#${TOKEN}`, 'https://other.example')).toEqual({
      href: `https://other.example/join/#${TOKEN}`,
    });
    expect(pastedInvite(`  ${TOKEN}  `, 'https://hub.example')).toEqual({
      href: `https://hub.example/join/#${TOKEN}`,
    });
    expect(pastedInvite('hello', 'https://hub.example')).toEqual({ error: PASTE_ERROR });
    expect(PASTE_ERROR).not.toMatch(/GM/);
  });
});

describe('the links of a library or repository (ADR 0212)', () => {
  it('takes one person by default and a small team up to the ceiling', () => {
    expect(parseTeamSize('')).toEqual({ size: 1 });
    expect(parseTeamSize(' 4 ')).toEqual({ size: 4 });
    expect(parseTeamSize(String(MAX_TEAM))).toEqual({ size: MAX_TEAM });
    for (const refused of ['0', '-1', String(MAX_TEAM + 1), 'lots', '2.5']) {
      expect(parseTeamSize(refused)).toBeNull();
    }
  });

  it('offers Author and Organizer and never Owner', () => {
    expect(LINK_ROLES.map((r) => r.label)).toEqual(['Author', 'Organizer']);
    expect(JSON.stringify(LINK_ROLES)).not.toMatch(/owner/i);
  });

  it('says once what a link does, in the three names and without a word of tenant', () => {
    const author = roleLinkNotice('author', 'library', 1);
    const team = roleLinkNotice('author', 'repository', 5);
    const organizer = roleLinkNotice('orga', 'library', 1);

    expect(author).toContain("won't be shown again");
    expect(author).toContain('becomes an Author of this library');
    expect(team).toContain('The first 5 people');
    expect(team).toContain('Authors of this repository');
    expect(organizer).toContain('becomes an Organizer');
    for (const notice of [author, team, organizer, LIBRARY_LINK_NOTICE]) {
      expect(notice).not.toMatch(/tenant|grant|subscri|\borga\b/i);
    }
    expect(author).toContain('never makes an Owner');
    expect(LIBRARY_LINK_NOTICE).toContain('private repository is open to whoever uses it first');
    expect(libraryLinkWho(1)).toBe('one library');
    expect(libraryLinkWho(3)).toBe('up to 3 libraries');
  });
});
