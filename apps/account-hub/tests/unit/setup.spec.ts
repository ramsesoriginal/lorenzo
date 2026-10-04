import { describe, expect, it } from 'vitest';
import {
  emptySetupState,
  runSetup,
  type SetupApi,
  SetupFailure,
  type SetupInput,
  type StepId,
  slugify,
  stepDoneLabel,
  stepLabel,
  stepsFor,
} from '../../src/lib/setup';

// The API's slug grammar (apps/api's slug check, ADR 0136's editor uses the same).
const SLUG_GRAMMAR = /^[a-z0-9]+(-[a-z0-9]+)*$/;

describe('slugify', () => {
  it('makes a slug of a name: lowercase, single hyphens between words', () => {
    expect(slugify('The Open Table')).toBe('the-open-table');
    expect(slugify('  Zorro!!  ')).toBe('zorro');
    expect(slugify('D&D 5e: Curse of Strahd')).toBe('d-d-5e-curse-of-strahd');
  });

  it('folds accents to their letter and drops what has none', () => {
    expect(slugify('Château de Légende')).toBe('chateau-de-legende');
    expect(slugify('Ærø Ünlü')).toBe('r-unlu');
  });

  it('is always a valid slug, even for a name with nothing in it', () => {
    for (const name of ['', '   ', '!!!', '日本語', '---', 'a--b', '-a-']) {
      expect(slugify(name)).toMatch(SLUG_GRAMMAR);
    }
    expect(slugify('!!!')).toBe('campaign');
    expect(slugify('!!!', 'library')).toBe('library');
  });

  it('keeps a long name inside a sane length, never ending on a hyphen', () => {
    const slug = slugify(`${'word '.repeat(40)}end`);
    expect(slug.length).toBeLessThanOrEqual(60);
    expect(slug).toMatch(SLUG_GRAMMAR);
  });
});

describe('stepsFor / labels', () => {
  it('makes the library, the campaign, the GM, then the player link', () => {
    expect(stepsFor({ kind: 'me' })).toEqual(['library', 'campaign', 'gm', 'player-link']);
    expect(stepsFor({ kind: 'user', userId: 'u' })).toEqual([
      'library',
      'campaign',
      'gm',
      'player-link',
    ]);
  });

  it('makes a GM link instead of a GM when the GM is sent a link', () => {
    expect(stepsFor({ kind: 'link' })).toEqual(['library', 'campaign', 'gm-link', 'player-link']);
  });

  it('says each step as it runs and when it is done', () => {
    for (const step of ['library', 'campaign', 'gm', 'gm-link', 'player-link'] as StepId[]) {
      expect(stepLabel(step)).not.toBe('');
      expect(stepDoneLabel(step)).not.toBe('');
    }
    // Product words: library, never tenant.
    for (const step of ['library', 'campaign', 'gm', 'gm-link', 'player-link'] as StepId[]) {
      expect(`${stepLabel(step)} ${stepDoneLabel(step)}`.toLowerCase()).not.toContain('tenant');
    }
  });
});

// A fake API that records what it was asked, and can be told to fail a call.
function fakeApi(fail: Partial<Record<keyof SetupApi, number>> = {}) {
  const calls: string[] = [];
  const failures = { ...fail };
  function maybeFail(name: keyof SetupApi) {
    const left = failures[name] ?? 0;
    if (left > 0) {
      failures[name] = left - 1;
      throw new Error(`${name} failed`);
    }
  }
  let invites = 0;
  const api: SetupApi = {
    async createLibrary(name) {
      calls.push(`library:${name}`);
      maybeFail('createLibrary');
      return { id: 'lib-1' };
    },
    async createCampaign(libraryId, campaign) {
      calls.push(`campaign:${libraryId}:${campaign.name}:${campaign.slug}:${campaign.gameSystem}`);
      maybeFail('createCampaign');
      return { id: 'camp-1' };
    },
    async grantGm(libraryId, campaignId, userId) {
      calls.push(`gm:${libraryId}:${campaignId}:${userId}`);
      maybeFail('grantGm');
    },
    async createInvite(libraryId, campaignId, role) {
      calls.push(`invite:${libraryId}:${campaignId}:${role}`);
      maybeFail('createInvite');
      invites += 1;
      return { token: `token-${role}-${invites}` };
    },
  };
  return { api, calls };
}

const INPUT: SetupInput = {
  libraryName: 'The Shattered Realms',
  campaignName: 'The Open Table',
  gameSystem: 'D&D 5e',
  gm: { kind: 'me' },
  meId: 'me-1',
};

describe('runSetup', () => {
  it('makes the library, the campaign, the creator as GM, and the player link, in that order', async () => {
    const { api, calls } = fakeApi();
    const state = await runSetup(INPUT, emptySetupState(), api);
    expect(calls).toEqual([
      'library:The Shattered Realms',
      'campaign:lib-1:The Open Table:the-open-table:D&D 5e',
      'gm:lib-1:camp-1:me-1',
      'invite:lib-1:camp-1:player',
    ]);
    expect(state).toEqual({
      libraryId: 'lib-1',
      campaignId: 'camp-1',
      gmDone: true,
      gmLinkToken: null,
      playerLinkToken: 'token-player-1',
    });
  });

  it('makes the person found the GM', async () => {
    const { api, calls } = fakeApi();
    await runSetup({ ...INPUT, gm: { kind: 'user', userId: 'friend-9' } }, emptySetupState(), api);
    expect(calls).toContain('gm:lib-1:camp-1:friend-9');
    expect(calls.join(' ')).not.toContain('me-1');
  });

  it('makes a single-use GM link instead, and no GM grant', async () => {
    const { api, calls } = fakeApi();
    const state = await runSetup({ ...INPUT, gm: { kind: 'link' } }, emptySetupState(), api);
    expect(calls).toEqual([
      'library:The Shattered Realms',
      'campaign:lib-1:The Open Table:the-open-table:D&D 5e',
      'invite:lib-1:camp-1:gm',
      'invite:lib-1:camp-1:player',
    ]);
    expect(state.gmDone).toBe(false);
    expect(state.gmLinkToken).toBe('token-gm-1');
    expect(state.playerLinkToken).toBe('token-player-2');
  });

  it('reports each step as it starts and finishes', async () => {
    const { api } = fakeApi();
    const heard: string[] = [];
    await runSetup(INPUT, emptySetupState(), api, (step, status) =>
      heard.push(`${step}:${status}`),
    );
    expect(heard).toEqual([
      'library:start',
      'library:done',
      'campaign:start',
      'campaign:done',
      'gm:start',
      'gm:done',
      'player-link:start',
      'player-link:done',
    ]);
  });

  it('stops at the step that failed, names it, and keeps what was made', async () => {
    const { api, calls } = fakeApi({ createCampaign: 1 });
    const state = emptySetupState();
    const failure = await runSetup(INPUT, state, api).catch((e) => e);
    expect(failure).toBeInstanceOf(SetupFailure);
    expect(failure.step).toBe('campaign');
    expect((failure.original as Error).message).toBe('createCampaign failed');
    expect(state.libraryId).toBe('lib-1');
    expect(state.campaignId).toBeNull();
    expect(calls).toHaveLength(2); // nothing after the failure was attempted
  });

  it('resumes from the failed step: nothing already made is made twice', async () => {
    const { api, calls } = fakeApi({ createCampaign: 1 });
    const state = emptySetupState();
    await runSetup(INPUT, state, api).catch(() => undefined);
    await runSetup(INPUT, state, api);
    expect(calls.filter((c) => c.startsWith('library:'))).toHaveLength(1);
    expect(calls.filter((c) => c.startsWith('campaign:'))).toHaveLength(2); // the failure, then the retry
    expect(state).toMatchObject({ libraryId: 'lib-1', campaignId: 'camp-1', gmDone: true });
    expect(state.playerLinkToken).not.toBeNull();
  });

  it('keeps the GM link when only the player link fails, and does not make a second one', async () => {
    const { api, calls } = fakeApi();
    // Fail the second createInvite call (the player link) once.
    let invites = 0;
    const flaky: SetupApi = {
      ...api,
      async createInvite(libraryId, campaignId, role) {
        invites += 1;
        if (invites === 2) throw new Error('player link failed');
        return api.createInvite(libraryId, campaignId, role);
      },
    };
    const state = emptySetupState();
    const failure = await runSetup({ ...INPUT, gm: { kind: 'link' } }, state, flaky).catch(
      (e) => e,
    );
    expect(failure.step).toBe('player-link');
    expect(state.gmLinkToken).toBe('token-gm-1');
    await runSetup({ ...INPUT, gm: { kind: 'link' } }, state, flaky);
    expect(calls.filter((c) => c.endsWith(':gm'))).toHaveLength(1);
    expect(state.playerLinkToken).not.toBeNull();
  });

  it('does not make the GM twice when only the player link failed', async () => {
    const { api, calls } = fakeApi({ createInvite: 1 });
    const state = emptySetupState();
    const failure = await runSetup(INPUT, state, api).catch((e) => e);
    expect(failure.step).toBe('player-link');
    expect(state.gmDone).toBe(true);
    await runSetup(INPUT, state, api);
    expect(calls.filter((c) => c.startsWith('gm:'))).toHaveLength(1);
  });
});
