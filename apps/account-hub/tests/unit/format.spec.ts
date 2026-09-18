import { describe, expect, it } from 'vitest';
import {
  campaignRoleFor,
  countUnread,
  localesToText,
  textOrNull,
  textToLocales,
} from '../../src/lib/format';
import type { MeOut, Notification } from '../../src/lib/types';

function notification(read_at: string | null): Notification {
  return {
    id: crypto.randomUUID(),
    batch_id: crypto.randomUUID(),
    user_id: crypto.randomUUID(),
    scope: 'platform',
    type: 'test',
    tenant_id: null,
    source_id: null,
    title: 'Title',
    body: 'Body',
    read_at,
    created_at: new Date().toISOString(),
  };
}

function me(overrides: Partial<MeOut> = {}): MeOut {
  return {
    id: crypto.randomUUID(),
    authgear_subject_id: 'subj',
    email: null,
    nickname: null,
    display_name: null,
    pronouns: null,
    bio: null,
    locales: [],
    user_color: null,
    picture_url: 'https://example.com/pic',
    memberships: [],
    players: [],
    campaign_gm_grants: [],
    ...overrides,
  };
}

describe('textToLocales', () => {
  it('splits, trims, and drops empty entries', () => {
    expect(textToLocales('en, de ,  , fr')).toEqual(['en', 'de', 'fr']);
  });

  it('returns an empty array for blank input', () => {
    expect(textToLocales('   ')).toEqual([]);
  });
});

describe('localesToText', () => {
  it('joins with a comma and space', () => {
    expect(localesToText(['en', 'de'])).toBe('en, de');
  });

  it('round-trips through textToLocales', () => {
    const locales = ['en', 'de', 'fr'];
    expect(textToLocales(localesToText(locales))).toEqual(locales);
  });
});

describe('textOrNull', () => {
  it('returns null for blank/whitespace-only input', () => {
    expect(textOrNull('')).toBeNull();
    expect(textOrNull('   ')).toBeNull();
  });

  it('returns the value unchanged otherwise', () => {
    expect(textOrNull('Cael')).toBe('Cael');
  });
});

describe('countUnread', () => {
  it('counts only notifications with a null read_at', () => {
    const items = [notification(null), notification('2026-01-01T00:00:00Z'), notification(null)];
    expect(countUnread(items)).toBe(2);
  });

  it('returns 0 for an empty list', () => {
    expect(countUnread([])).toBe(0);
  });

  it('returns 0 when everything is already read', () => {
    expect(countUnread([notification('2026-01-01T00:00:00Z')])).toBe(0);
  });
});

describe('campaignRoleFor', () => {
  const campaignId = crypto.randomUUID();

  it('returns gm when the campaign is in campaign_gm_grants', () => {
    const caller = me({
      campaign_gm_grants: [
        { id: campaignId, slug: 's', name: 'N', game_system: 'dnd5e', secret: false },
      ],
    });
    expect(campaignRoleFor(campaignId, caller)).toBe('gm');
  });

  it('returns player when the campaign is in players', () => {
    const caller = me({
      players: [
        {
          id: crypto.randomUUID(),
          tenant_id: crypto.randomUUID(),
          campaign_id: campaignId,
          characters: [],
        },
      ],
    });
    expect(campaignRoleFor(campaignId, caller)).toBe('player');
  });

  it('returns visible when the campaign is in neither', () => {
    expect(campaignRoleFor(campaignId, me())).toBe('visible');
  });

  it('prefers gm over player if somehow both are present', () => {
    const caller = me({
      campaign_gm_grants: [
        { id: campaignId, slug: 's', name: 'N', game_system: 'dnd5e', secret: false },
      ],
      players: [
        {
          id: crypto.randomUUID(),
          tenant_id: crypto.randomUUID(),
          campaign_id: campaignId,
          characters: [],
        },
      ],
    });
    expect(campaignRoleFor(campaignId, caller)).toBe('gm');
  });
});
