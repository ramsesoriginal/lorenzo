import { describe, expect, it } from 'vitest';
import {
  canCreateTenants,
  isRepository,
  kindNoun,
  kindNounCapitalized,
  publishedLabel,
  splitByKind,
} from '../../src/lib/tenantKind';

const library = (name: string) => ({ name, kind: 'play' as const });
const repository = (name: string) => ({ name, kind: 'repository' as const });

describe('kindNoun', () => {
  it('says library for a play tenant and repository for a repository', () => {
    expect(kindNoun('play')).toBe('library');
    expect(kindNoun('repository')).toBe('repository');
    expect(kindNounCapitalized('play')).toBe('Library');
    expect(kindNounCapitalized('repository')).toBe('Repository');
  });
});

describe('isRepository / splitByKind', () => {
  it('tells the two kinds apart', () => {
    expect(isRepository(repository('Core'))).toBe(true);
    expect(isRepository(library('Home'))).toBe(false);
  });

  it('splits one list into libraries and repositories, each in its own order', () => {
    const tenants = [library('B'), repository('Core'), library('A'), repository('Extras')];
    const { libraries, repositories } = splitByKind(tenants);
    expect(libraries.map((t) => t.name)).toEqual(['B', 'A']);
    expect(repositories.map((t) => t.name)).toEqual(['Core', 'Extras']);
  });

  it('is two empty lists for no tenants, and never loses one', () => {
    expect(splitByKind([])).toEqual({ libraries: [], repositories: [] });
    const all = [library('A'), repository('B'), library('C')];
    const { libraries, repositories } = splitByKind(all);
    expect(libraries.length + repositories.length).toBe(all.length);
  });
});

describe('canCreateTenants', () => {
  it('is true only when the API says so', () => {
    expect(canCreateTenants({ capabilities: { create_tenant: true } })).toBe(true);
    expect(canCreateTenants({ capabilities: { create_tenant: false } })).toBe(false);
  });

  it('treats a missing capability as false (an older API, or one that says nothing)', () => {
    expect(canCreateTenants({})).toBe(false);
    expect(canCreateTenants({ capabilities: {} })).toBe(false);
    expect(canCreateTenants({ capabilities: undefined })).toBe(false);
  });
});

describe('publishedLabel', () => {
  it('says Draft until the first publish', () => {
    expect(publishedLabel(null)).toBe('Draft');
  });

  it('says the UTC day of the publish, whatever the zone it was written in', () => {
    expect(publishedLabel('2026-10-04T23:30:00Z')).toBe('Published 2026-10-04');
    expect(publishedLabel('2026-10-04T00:00:01.123456+00:00')).toBe('Published 2026-10-04');
  });
});
