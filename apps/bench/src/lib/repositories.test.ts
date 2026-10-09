import { describe, expect, it } from 'vitest';
import { authoredRepositories, repositoryToOpen, type TenantSummary } from './repositories';

const t = (id: string, name: string, role: string, kind: 'play' | 'repository'): TenantSummary =>
  ({ id, slug: id, name, role, kind }) as TenantSummary;

const all = [
  t('1', 'Zeta', 'owner', 'repository'),
  t('2', 'Alpha', 'orga', 'repository'),
  t('3', 'Table', 'owner', 'play'),
  t('4', 'Read only', 'participant', 'repository'),
  t('5', 'Mine too', 'author', 'repository'),
];

describe('authoredRepositories', () => {
  it('keeps repositories where the person edits, by name', () => {
    expect(authoredRepositories(all).map((r) => r.name)).toEqual(['Alpha', 'Mine too', 'Zeta']);
  });
  it('is empty for someone with only libraries', () => {
    expect(authoredRepositories([t('3', 'Table', 'owner', 'play')])).toEqual([]);
  });
});

describe('repositoryToOpen', () => {
  const repos = authoredRepositories(all);
  it('prefers the last one while it is still theirs', () => {
    expect(repositoryToOpen(repos, '1')?.id).toBe('1');
  });
  it('falls back to the first, and to nothing', () => {
    expect(repositoryToOpen(repos, 'gone')?.id).toBe('2');
    expect(repositoryToOpen([], null)).toBeNull();
  });
});
