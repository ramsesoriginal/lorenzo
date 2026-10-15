import { describe, expect, it } from 'vitest';
import {
  charactersLine,
  personLabel,
  runRoleLabel,
  runRows,
  seatsIn,
} from '../../src/lib/campaigns';
import type { ManagedScopeOut, MePlayerOut } from '../../src/lib/types';

const managed = (tenants: ManagedScopeOut['tenants']): ManagedScopeOut => ({ tenants });

const tenant = (
  name: string,
  campaigns: [string, boolean, [string, string]?][],
  kind: 'play' | 'repository' = 'play',
): ManagedScopeOut['tenants'][number] => ({
  tenant_id: `t-${name}`,
  name,
  slug: name.toLowerCase(),
  role: 'owner',
  kind,
  campaigns: campaigns.map(([campaignName, is_gm, titles]) => ({
    campaign_id: `c-${name}-${campaignName}`,
    name: campaignName,
    is_gm,
    gm_title: titles?.[0] ?? 'GM',
    gm_title_plural: titles?.[1] ?? 'GMs',
  })),
});

describe('runRows', () => {
  it('lists the campaigns you run, a GM grant as GM and the rest as Admin', () => {
    const rows = runRows(
      managed([
        tenant('Realms', [
          ['Open Table', true],
          ['Hood', false],
        ]),
      ]),
    );
    expect(rows.map((r) => [r.campaignName, r.role])).toEqual([
      ['Hood', 'admin'],
      ['Open Table', 'gm'],
    ]);
    expect(runRoleLabel('gm', 'GM')).toBe('GM');
    expect(runRoleLabel('admin', 'GM')).toBe('Admin');
  });

  it("keeps each campaign's own title for its game master (ADR 0294)", () => {
    const rows = runRows(
      managed([
        tenant('Realms', [
          ['Hood', true, ['Storyteller', 'Storytellers']],
          ['Open Table', true],
        ]),
      ]),
    );
    const hood = rows.find((r) => r.campaignName === 'Hood');
    const open = rows.find((r) => r.campaignName === 'Open Table');

    expect(hood?.gm).toEqual({ title: 'Storyteller', plural: 'Storytellers' });
    expect(open?.gm).toEqual({ title: 'GM', plural: 'GMs' });
    expect(runRoleLabel('gm', hood?.gm.title ?? '')).toBe('Storyteller');
    // An administrator who is not its GM is an Admin whatever the table calls its game master.
    expect(runRoleLabel('admin', 'Storyteller')).toBe('Admin');
  });

  it('names the library each is in, and sorts by library then campaign, ignoring case', () => {
    const rows = runRows(
      managed([
        tenant('beta', [
          ['Zed', true],
          ['alpha', true],
        ]),
        tenant('Alpha Library', [['Mid', false]]),
      ]),
    );
    expect(rows.map((r) => `${r.tenantName}/${r.campaignName}`)).toEqual([
      'Alpha Library/Mid',
      'beta/alpha',
      'beta/Zed',
    ]);
    expect(rows[0]).toMatchObject({
      tenantId: 't-Alpha Library',
      campaignId: 'c-Alpha Library-Mid',
    });
  });

  it('leaves a repository out: nobody plays in one', () => {
    const rows = runRows(
      managed([tenant('Core', [], 'repository'), tenant('Realms', [['Open Table', true]])]),
    );
    expect(rows.map((r) => r.tenantName)).toEqual(['Realms']);
  });

  it('is empty for nothing to run', () => {
    expect(runRows(managed([]))).toEqual([]);
    expect(runRows(managed([tenant('Realms', [])]))).toEqual([]);
  });
});

describe('seatsIn', () => {
  const seat = (tenantId: string): MePlayerOut => ({
    id: `p-${tenantId}`,
    tenant_id: tenantId,
    campaign_id: `c-${tenantId}`,
    characters: [],
    self_service_effective: true,
  });

  it('keeps only the seats in the libraries given', () => {
    const me = { players: [seat('a'), seat('repo'), seat('b')] };
    expect(seatsIn(me, new Set(['a', 'b'])).map((p) => p.tenant_id)).toEqual(['a', 'b']);
    expect(seatsIn(me, new Set())).toEqual([]);
  });
});

describe('charactersLine', () => {
  it('says what a player plays, or that they play nothing yet', () => {
    expect(charactersLine([{ name: 'Cael' }, { name: 'Mira' }])).toBe('Cael, Mira');
    expect(charactersLine([])).toBe('no character yet');
  });
});

describe('personLabel', () => {
  const person = (over: Partial<Parameters<typeof personLabel>[0]> = {}) => ({
    display_name: null,
    nickname: null,
    user_id: 'u-1',
    ...over,
  });

  it('falls back from display name to nickname to the user id', () => {
    expect(personLabel(person({ display_name: 'Pia Player', nickname: 'pia' }), 'me')).toBe(
      'Pia Player',
    );
    expect(personLabel(person({ nickname: 'pia' }), 'me')).toBe('pia');
    expect(personLabel(person(), 'me')).toBe('u-1');
  });

  it('says "you" for the signed-in person', () => {
    expect(personLabel(person({ display_name: 'Cleo' }), 'u-1')).toBe('Cleo (you)');
  });
});
