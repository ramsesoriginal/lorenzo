import { describe, expect, it } from 'vitest';
import {
  dialogFor,
  GM_ONLY_LINE,
  LIVE_LINE,
  OWNER_ONLY_NOTE,
  type PublishFacts,
  publishFacts,
} from '../../src/lib/publishing';
import type { SubscriberOut, SubscriptionOut } from '../../src/lib/types';

function subscriber(overrides: Partial<SubscriberOut> = {}): SubscriberOut {
  return {
    tenant_id: 't',
    name: 'T',
    slug: 't',
    granted_at: '2026-10-01T10:00:00Z',
    granted_by: null,
    copied_at: null,
    synced_at: null,
    ...overrides,
  } as SubscriberOut;
}

function copiedFrom(name: string, published: boolean): SubscriptionOut {
  return {
    repository: {
      id: name,
      name,
      slug: name.toLowerCase(),
      description: '',
      published_at: published ? '2026-10-01T10:00:00Z' : null,
    },
    granted_at: '2026-10-01T10:00:00Z',
    copied_at: '2026-10-02T10:00:00Z',
    synced_at: null,
    contributed: null,
  } as SubscriptionOut;
}

const none: PublishFacts = { invited: 0, copied: 0, builtOn: [] };

describe('what is known before a publish', () => {
  it('counts the libraries a publish tells and those that hold a copy', () => {
    const facts = publishFacts(
      [
        subscriber(),
        subscriber({ copied_at: '2026-10-02T10:00:00Z' }),
        subscriber({ granted_at: null, copied_at: '2026-10-02T10:00:00Z' }),
      ],
      [],
    );

    expect(facts).toMatchObject({ invited: 2, copied: 2 });
  });

  it('lists what it is built on by name, with whether each is published', () => {
    const facts = publishFacts([], [copiedFrom('Rules', false), copiedFrom('Core', true)]);

    expect(facts.builtOn).toEqual([
      { name: 'Core', published: true },
      { name: 'Rules', published: false },
    ]);
  });
});

describe('the publish dialog', () => {
  it('says how many libraries are told, and what they can do after', () => {
    const dialog = dialogFor('publish', 'Core', { ...none, invited: 3 });

    expect(dialog.title).toBe('Publish Core');
    expect(dialog.lines[0]).toBe(
      "3 libraries have an invitation and are told when you publish: each one's Owners and Organizers get a notification.",
    );
    expect(dialog.confirm).toBe('Publish and tell 3 libraries');
    expect(dialog.lines).toContain(LIVE_LINE);
    expect(dialog.lines).toContain(GM_ONLY_LINE);
  });

  it('says so when nobody is told', () => {
    const dialog = dialogFor('publish', 'Core', none);

    expect(dialog.lines[0]).toMatch(/nobody is told/);
    expect(dialog.confirm).toBe('Publish');
  });

  it('says it in the singular for one library', () => {
    expect(dialogFor('publish', 'Core', { ...none, invited: 1 }).lines[0]).toMatch(
      /^1 library has an invitation and is told/,
    );
    expect(dialogFor('publish', 'Core', { ...none, invited: 1 }).confirm).toBe(
      'Publish and tell 1 library',
    );
  });

  it('warns about a repository it is built on that is not published, and that invitations are not passed on', () => {
    const dialog = dialogFor('publish', 'Bridge', {
      ...none,
      builtOn: [
        { name: 'Core', published: true },
        { name: 'Rules', published: false },
      ],
    });

    expect(dialog.warnings[0]).toBe(
      'Rules is not published. A copy of this repository is refused until it is, since a copy brings what it is built on.',
    );
    expect(dialog.warnings[1]).toMatch(/built on Core, Rules.*invitations are not passed on/);
    expect(dialogFor('publish', 'Core', none).warnings).toEqual([]);
  });

  it('is a new release, with what a release is', () => {
    const dialog = dialogFor('announce', 'Core', { ...none, invited: 2 });

    expect(dialog.title).toBe('Publish a new release of Core');
    expect(dialog.lines[1]).toMatch(/a label and notes/);
    expect(dialog.confirm).toBe('Publish release and tell 2 libraries');
  });

  it('says what unpublishing does: libraries lose the look, the copy and the updates, and keep what they copied', () => {
    const dialog = dialogFor('unpublish', 'Core', { invited: 2, copied: 1, builtOn: [] });

    expect(dialog.lines).toEqual([
      'It goes back to a draft.',
      '2 libraries have an invitation and can no longer look inside it, copy it or check for updates until you publish it again.',
      'What 1 library already copied stays with it, and nothing is deleted.',
      'Nobody is sent a message about it.',
    ]);
    expect(dialog.confirm).toBe('Unpublish');
  });

  it('uses the glossary', () => {
    const text = [
      ...dialogFor('publish', 'X', {
        invited: 2,
        copied: 1,
        builtOn: [{ name: 'Y', published: false }],
      }).lines,
      ...dialogFor('unpublish', 'X', { invited: 2, copied: 1, builtOn: [] }).lines,
      OWNER_ONLY_NOTE,
    ].join(' ');

    expect(text).not.toMatch(/tenant|grant|subscri/i);
  });
});
