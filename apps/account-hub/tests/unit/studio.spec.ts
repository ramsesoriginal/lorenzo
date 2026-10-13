import { describe, expect, it } from 'vitest';
import {
  canChangePeople,
  LIVE_NOTICE,
  readStudioLocation,
  repositoryState,
  roleLabel,
  roleMeanings,
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
  it('are called Owner, Organizer and Author, never the API’s words', () => {
    expect(roleLabel('owner')).toBe('Owner');
    expect(roleLabel('orga')).toBe('Organizer');
    expect(roleLabel('author')).toBe('Author');
  });

  it('each carry what it can do, in the order of how much they can, in a library and a repository', () => {
    for (const kind of ['play', 'repository'] as const) {
      expect(roleMeanings(kind).map((r) => r.label)).toEqual(['Owner', 'Organizer', 'Author']);
      expect(roleMeanings(kind).map((r) => r.role)).toEqual(['owner', 'orga', 'author']);
    }

    const repository = roleMeanings('repository');

    expect(repository[0]?.meaning).toMatch(/publishes/);
    expect(repository[1]?.meaning).toMatch(/Cannot publish/);
    expect(repository[2]?.meaning).toMatch(/Cannot publish/);
    expect(repository[2]?.meaning).toMatch(/delete stat groups/);
    expect(roleMeanings('play')[2]?.meaning).toMatch(/Reaches no campaign/);
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
    const text = [
      LIVE_NOTICE,
      ...roleMeanings('play').map((r) => r.meaning),
      ...roleMeanings('repository').map((r) => r.meaning),
    ].join(' ');

    expect(text).not.toMatch(/tenant|subscri|grant/i);
    expect(LIVE_NOTICE).toMatch(/next check for updates/);
  });
});
