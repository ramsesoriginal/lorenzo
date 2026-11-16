import { describe, expect, it } from 'vitest';
import { emptyWords, unreadIds, unreadSummary } from '../../src/lib/notificationsView';

describe('unreadSummary', () => {
  it('counts what is unread, or says nothing is', () => {
    expect(unreadSummary(3)).toBe('3 unread');
    expect(unreadSummary(1)).toBe('1 unread');
    expect(unreadSummary(0)).toBe('Nothing unread');
  });
});

describe('unreadIds', () => {
  it('is the unread ones, in order', () => {
    expect(
      unreadIds([
        { id: 'a', read_at: null },
        { id: 'b', read_at: '2026-11-01T00:00:00Z' },
        { id: 'c', read_at: null },
      ]),
    ).toEqual(['a', 'c']);
  });
});

describe('emptyWords', () => {
  it('says caught up either way, and what is meant', () => {
    expect(emptyWords(true).title).toBe('You’re all caught up');
    expect(emptyWords(true).text).toMatch(/Nothing is waiting/);
    expect(emptyWords(false).text).toMatch(/No notifications yet/);
  });
});
