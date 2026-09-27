import { describe, expect, it, vi } from 'vitest';
import { matchingGroups } from './groups';

vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

describe('matchingGroups', () => {
  const groups = [
    { entity_id: 'company', name: 'The Company' },
    { entity_id: 'watch', name: 'City Watch' },
  ];

  it('finds groups whose name contains the query, whatever its case', () => {
    expect(matchingGroups(groups, 'comp')).toEqual([groups[0]]);
    expect(matchingGroups(groups, 'WATCH')).toEqual([groups[1]]);
  });

  it('offers nothing for an empty query', () => {
    expect(matchingGroups(groups, '  ')).toEqual([]);
  });
});
