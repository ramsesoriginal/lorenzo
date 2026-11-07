import { describe, expect, it } from 'vitest';
import { appsByJob } from '../src/apps';
import { clockLocale, clockText, splitTabs, timeText } from '../src/pure';

describe('appsByJob', () => {
  it('lists the deployed apps by job, in the order of the design', () => {
    const jobs = appsByJob({
      apps: {
        account_hub: { url: 'https://hub.example' },
        sessions: { url: 'https://sessions.example' },
        beings: { url: 'https://beings.example' },
        calendars: { url: 'https://calendars.example' },
        writing: { url: 'https://writing.example' },
      },
    });

    expect(jobs.map((job) => job.label)).toEqual(['Play', 'World', 'Build', 'You']);
    expect(jobs[0]?.apps.map((app) => app.name)).toEqual(['Sessions', 'Beings']);
    expect(jobs[1]?.apps.map((app) => app.name)).toEqual(['Calendars']);
    expect(jobs[2]?.apps.map((app) => app.name)).toEqual(['Writing']);
    expect(jobs[3]?.apps[0]).toMatchObject({ name: 'Account', url: 'https://hub.example' });
  });

  it('leaves out an app with no address, an empty one, and a group with nothing in it', () => {
    const jobs = appsByJob({ apps: { sessions: { url: '' }, beings: { url: '  ' }, maps: {} } });

    expect(jobs).toEqual([]);
  });

  it('ignores an app it has no place for', () => {
    expect(appsByJob({ apps: { somewhere_new: { url: 'https://x.example' } } })).toEqual([]);
  });
});

describe('splitTabs', () => {
  it('keeps up to three links in the tab bar and the rest for the More sheet', () => {
    expect(splitTabs(['a', 'b'])).toEqual({ tabs: ['a', 'b'], rest: [] });
    expect(splitTabs(['a', 'b', 'c', 'd', 'e'])).toEqual({
      tabs: ['a', 'b', 'c'],
      rest: ['d', 'e'],
    });
  });
});

describe('clockText', () => {
  it('writes the day and the time as the design draws them', () => {
    expect(clockText(new Date(2026, 10, 6, 9, 41), 'en-GB')).toBe('Fri 6 November at 09:41');
  });

  it('writes the time alone for "Synced 19:40"', () => {
    expect(timeText(new Date(2026, 10, 6, 19, 40), 'en-GB')).toBe('19:40');
  });

  it('writes plain English the day-first way, and any other language as it is', () => {
    expect(clockLocale('en')).toBe('en-GB');
    expect(clockLocale('EN')).toBe('en-GB');
    expect(clockLocale('de')).toBe('de');
    expect(clockLocale('en-US')).toBe('en-US');
    expect(clockLocale('')).toBeUndefined();
    expect(clockLocale(undefined)).toBeUndefined();
  });
});
