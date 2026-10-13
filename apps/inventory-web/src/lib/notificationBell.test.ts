import { describe, expect, it } from 'vitest';
import {
  badgeText,
  bellLabel,
  hubNotificationsUrl,
  notificationLink,
  pollDelay,
} from './notificationBell';

const base = { scope: 'tenant', type: 'x', tenant_id: 't1', source_id: null };

describe('badgeText', () => {
  it('says nothing for none, the number, and 99+ past that', () => {
    expect(badgeText(0)).toBe('');
    expect(badgeText(7)).toBe('7');
    expect(badgeText(99)).toBe('99');
    expect(badgeText(100)).toBe('99+');
  });
});

describe('bellLabel', () => {
  it('announces the count', () => {
    expect(bellLabel(0)).toBe('Notifications, none unread');
    expect(bellLabel(3)).toBe('Notifications, 3 unread');
  });
});

describe('notificationLink', () => {
  it('sends sorted items to the library board', () => {
    expect(notificationLink({ ...base, type: 'items_sorted' })).toBe('/board/?tenant=t1');
  });

  it("sends a character's message to that character", () => {
    expect(notificationLink({ ...base, scope: 'character', source_id: 'c 1' })).toBe(
      '/board/?tenant=t1&character=c%201',
    );
  });

  it('has no link for what is not about this app', () => {
    expect(notificationLink(base)).toBeNull();
    expect(notificationLink({ ...base, type: 'items_sorted', tenant_id: null })).toBeNull();
  });
});

describe('hubNotificationsUrl', () => {
  it('joins without doubling the slash', () => {
    expect(hubNotificationsUrl('https://hub.example/')).toBe('https://hub.example/notifications/');
    expect(hubNotificationsUrl('https://hub.example')).toBe('https://hub.example/notifications/');
  });
});

describe('pollDelay', () => {
  it('never polls a hidden tab', () => {
    expect(pollDelay(false, 0)).toBeNull();
  });

  it('asks every minute, backing off after failures to five minutes', () => {
    expect(pollDelay(true, 0)).toBe(60_000);
    expect(pollDelay(true, 1)).toBe(120_000);
    expect(pollDelay(true, 2)).toBe(240_000);
    expect(pollDelay(true, 9)).toBe(300_000);
  });
});
