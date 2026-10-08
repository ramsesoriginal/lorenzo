import { describe, expect, it } from 'vitest';
import {
  COMMAND_LINE_NOTE,
  canChangePeople,
  LIVE_NOTICE,
  ROLE_MEANINGS,
  readStudioLocation,
  repositoryState,
  roleLabel,
  STUDIO_NEW_HREF,
  studioHref,
} from '../../src/lib/studio';

describe('studioHref and readStudioLocation', () => {
  it('builds the address of the list, and of one repository', () => {
    expect(studioHref()).toBe('/studio/');
    expect(studioHref('core-rules')).toBe('/studio/?repository=core-rules');
    expect(STUDIO_NEW_HREF).toBe('/studio/?new=1');
  });

  it('escapes what it is given', () => {
    expect(studioHref('a b&c')).toBe('/studio/?repository=a+b%26c');
  });

  it('reads them back, and says nothing for what the address leaves out', () => {
    expect(readStudioLocation('?repository=core-rules')).toEqual({
      repository: 'core-rules',
      create: false,
    });
    expect(readStudioLocation('?new=1')).toEqual({ repository: null, create: true });
    expect(readStudioLocation('')).toEqual({ repository: null, create: false });
    expect(readStudioLocation('?new=0').create).toBe(false);
  });
});

describe('roles', () => {
  it('are called Owner and Organizer, never the API’s words', () => {
    expect(roleLabel('owner')).toBe('Owner');
    expect(roleLabel('orga')).toBe('Organizer');
  });

  it('each carry what it can do, in the order of how much they can', () => {
    expect(ROLE_MEANINGS.map((r) => r.label)).toEqual(['Owner', 'Organizer']);
    expect(ROLE_MEANINGS[0]?.meaning).toMatch(/publishes/);
    expect(ROLE_MEANINGS[1]?.meaning).toMatch(/Cannot publish/);
  });

  it('only an Owner changes who works on a repository', () => {
    expect(canChangePeople('owner')).toBe(true);
    expect(canChangePeople('orga')).toBe(false);
  });
});

describe('repositoryState', () => {
  it('is a draft until it is published', () => {
    const state = repositoryState(null);

    expect(state).toMatchObject({ published: false, label: 'Draft' });
    expect(state.explanation).toMatch(/cannot look inside it or copy it/);
  });

  it('says the day it was published, in UTC', () => {
    const state = repositoryState('2026-10-03T23:59:00Z');

    expect(state).toMatchObject({ published: true, label: 'Published 2026-10-03' });
  });
});

describe('the sentences', () => {
  it('use the glossary: libraries and repositories, never tenants', () => {
    const text = [LIVE_NOTICE, COMMAND_LINE_NOTE, ...ROLE_MEANINGS.map((r) => r.meaning)].join(' ');

    expect(text).not.toMatch(/tenant|subscri|grant/i);
    expect(LIVE_NOTICE).toMatch(/next check for updates/);
  });
});
