import { describe, expect, it } from 'vitest';
import {
  linkTasks,
  needsYou,
  orderTasks,
  pageTitle,
  parseRecent,
  playerTasks,
  rememberPage,
  splitTables,
  updateTasks,
} from '../../src/lib/home';

const card = (name: string, roles: string[]) => ({ name, roles }) as never;

describe('splitTables', () => {
  it('puts a seat in where you play, and any other role in what you run', () => {
    const { play, run } = splitTables([
      card('Zorro', ['Player']),
      card('Heist', ['GM']),
      card('Both', ['Player', 'Organizer']),
    ]);

    expect(play.map((c) => c.name)).toEqual(['Zorro', 'Both']);
    expect(run.map((c) => c.name)).toEqual(['Heist', 'Both']);
  });
});

describe('needsYou', () => {
  const href = (slug: string) => `/repositories/?repository=${slug}`;

  it('is a task for each repository still a draft, and none for the rest', () => {
    const tasks = needsYou(
      [
        { name: 'Orla', slug: 'orla', role: 'Owner', status: 'Draft' },
        { name: 'Vale', slug: 'vale', role: 'Author', status: 'Published 2026-10-01' },
        { name: 'Odd', slug: 'odd', role: 'Author', status: null },
      ],
      href,
    );

    expect(tasks).toEqual([
      {
        id: 'draft:orla',
        text: 'Orla is still a draft.',
        action: 'Open it',
        href: '/repositories/?repository=orla',
      },
    ]);
  });

  it('is empty on a quiet day', () => {
    expect(needsYou([], href)).toEqual([]);
  });
});

const NOW = Date.parse('2026-11-07T12:00:00Z');
const DAY = 24 * 60 * 60 * 1000;
const iso = (offset: number) => new Date(NOW + offset).toISOString();

describe('updateTasks', () => {
  const subscription = (
    name: string,
    published: string | null,
    copied: string | null,
    synced: string | null,
  ) =>
    ({
      repository: { id: `id-${name}`, name, slug: name.toLowerCase(), published_at: published },
      granted_at: '2026-01-01T00:00:00Z',
      copied_at: copied,
      synced_at: synced,
    }) as never;

  it('is a task for each copied repository published since the last update, and none for the rest', () => {
    const tasks = updateTasks({ name: 'Thursday table', slug: 'thursday' }, [
      subscription('Core', '2026-11-01T00:00:00Z', '2026-10-01T00:00:00Z', null),
      subscription('Vale', '2026-09-01T00:00:00Z', '2026-10-01T00:00:00Z', null),
      subscription('Fresh', '2026-11-01T00:00:00Z', null, null),
    ]);

    expect(tasks).toEqual([
      {
        id: 'update:thursday:id-Core',
        text: 'Core has an update announced for Thursday table.',
        action: 'Review updates',
        href: '/repositories/?tenant=thursday&repository=core&updates=1',
      },
    ]);
  });
});

describe('linkTasks', () => {
  const invite = (over: Record<string, unknown>) =>
    ({
      id: 'i1',
      expires_at: iso(2 * DAY),
      max_uses: 10,
      use_count: 3,
      revoked_at: null,
      is_active: true,
      ...over,
    }) as never;
  const where = { label: 'The harbour job', slug: 'thursday' };

  it('is a task for a link that works and ends within three days', () => {
    expect(linkTasks(where, [invite({})], NOW)).toEqual([
      {
        id: 'link:i1',
        text: 'An invite link for The harbour job ends in 2 days (used 3 of 10 times).',
        action: 'Make a new link',
        href: '/tenants/?tenant=thursday',
      },
    ]);
  });

  it('says within a day when it ends inside one, and counts uses of a link with no limit', () => {
    const [task] = linkTasks(
      where,
      [invite({ expires_at: iso(3 * 60 * 60 * 1000), max_uses: null })],
      NOW,
    );

    expect(task?.text).toBe('An invite link for The harbour job ends within a day (used 3 times).');
  });

  it('is none for a link that is far off, revoked, used up or already over', () => {
    expect(
      linkTasks(
        where,
        [
          invite({ id: 'far', expires_at: iso(10 * DAY) }),
          invite({ id: 'revoked', revoked_at: iso(-DAY), is_active: false }),
          invite({ id: 'used-up', is_active: false }),
          invite({ id: 'over', expires_at: iso(-DAY) }),
        ],
        NOW,
      ),
    ).toEqual([]);
  });
});

describe('playerTasks', () => {
  const entry = (over: Record<string, unknown>) =>
    ({
      action: 'campaign_invite.redeemed',
      detail: 'campaign=c1, player=p1',
      created_at: iso(-DAY),
      ...over,
    }) as never;
  const campaigns = new Map([['c1', { name: 'The harbour job', slug: 'thursday' }]]);

  it('is one task for a campaign a new player joined, saying how many', () => {
    expect(playerTasks([entry({})], campaigns, NOW)).toEqual([
      {
        id: 'players:c1',
        text: 'A new player joined The harbour job.',
        action: 'See players',
        href: '/tenants/?tenant=thursday',
      },
    ]);
    expect(
      playerTasks([entry({}), entry({ detail: 'campaign=c1, player=p2' })], campaigns, NOW)[0]
        ?.text,
    ).toBe('2 new players joined The harbour job.');
  });

  it('is none for a GM who joined, an old join, another campaign or another action', () => {
    expect(
      playerTasks(
        [
          entry({ detail: 'campaign=c1, role=gm, gm=u1' }),
          entry({ created_at: iso(-10 * DAY) }),
          entry({ detail: 'campaign=other, player=p3' }),
          entry({ action: 'player.removed' }),
        ],
        campaigns,
        NOW,
      ),
    ).toEqual([]);
  });
});

describe('orderTasks', () => {
  it('keeps each group together, in the order given', () => {
    const task = (id: string) => ({ id, text: id, action: 'Open', href: '/' });

    expect(orderTasks([task('u')], [task('l')], [task('p')], [task('d')]).map((t) => t.id)).toEqual(
      ['u', 'l', 'p', 'd'],
    );
  });
});

describe('rememberPage', () => {
  it('puts the page just opened first, with no repeats, at most three', () => {
    let recent = rememberPage([], { href: '/a/', title: 'A' });

    recent = rememberPage(recent, { href: '/b/', title: 'B' });
    recent = rememberPage(recent, { href: '/c/', title: 'C' });
    recent = rememberPage(recent, { href: '/a/', title: 'A' });
    recent = rememberPage(recent, { href: '/d/', title: 'D' });

    expect(recent.map((p) => p.href)).toEqual(['/d/', '/a/', '/c/']);
  });
});

describe('parseRecent', () => {
  it('keeps only well-formed local entries and survives rubbish', () => {
    expect(
      parseRecent('[{"href":"/a/","title":"A"},{"href":"https://x","title":"X"},{"title":"?"}]'),
    ).toEqual([{ href: '/a/', title: 'A' }]);
    expect(parseRecent('not json')).toEqual([]);
    expect(parseRecent('{}')).toEqual([]);
    expect(parseRecent(null)).toEqual([]);
  });
});

describe('pageTitle', () => {
  it('drops the product', () => {
    expect(pageTitle('Your profile — Lorenzo')).toBe('Your profile');
    expect(pageTitle('Lorenzo - Account')).toBe('Lorenzo - Account');
  });
});
